"""The connector: one command, run by the user with their own Abaqus, that turns a finished job into one exchange bundle (ADR-0094, step 2).

    abaqus python anisotropy_connector.py <job>.odb --units mm-MPa
        [--inp <job>.inp] [--journal <model>.jnl] [--out <bundle>.zip] [--step Step-1] [--frame -1] [--instance COUPON-1] [--coupon <name>]
    abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units mm-MPa --cae <model>.cae [--model Model-1]
    ... --send https://<the site>/api [--token-file <file>] [--our-run <id of a run of ours>]
    abaqus python anisotropy_connector.py --watch <folder> --units mm-MPa [--send ... --token-file <file>] [--every 5] [--existing] [--once]

The first form needs no seat of Abaqus/CAE. It reads the job's ODB as `abaqus_every_output.py` does (every element and ply at each
layer's middle section point, and the reactions), takes the input file Abaqus solved from beside the ODB, and writes
`<job>-anisotropy.zip` beside it: a bundle of version 1 (`bundle.py`), each file with its SHA-256. The second form runs inside
Abaqus/CAE without its window and also reads the model as built from the `.cae` (the parts, the materials, the layup ply by ply, the
steps, the boundary conditions, the output requests) into `<job>-model.json`, and takes the `.jnl` beside the `.cae` as text.

The deck system is stated, never inferred: an Abaqus model carries no units (ADR-0002, ADR-0003). Nothing is sent anywhere unless the
user asks with `--send`: the command writes one file, and the user decides where it goes. No path of the user's machine is written
into the manifest; a journal is the user's own file and goes in as it is.

With `--send <address>` (step 5) the bundle just written, and nothing else, goes to Anisotropy at that address with the upload token the
user created on the site: read from the file `--token-file` names, or from the environment variable ANISOTROPY_UPLOAD_TOKEN, never from
the command line, where Abaqus would write it into `abaqus.rpy`. The token is not printed. The address must be https, or this machine
itself. The upload is its owner's alone; the answer says whether it agrees with a run of ours (`--our-run`, or the owner's newest
finished run of `--coupon`). A redirect is not followed, so the token is never passed on to another address. When the sending fails
the bundle is still beside the ODB, and the line printed says why: `sent:` or `not sent:`. Read that line and not the exit code. This
script ends with 1 when the bundle was written and not sent, but Abaqus's own launcher on Windows (`abaqus.bat`) ends with 0 whatever a
script returned, under `abaqus python` as under Abaqus/CAE (Abaqus 2025, the eighth trial).

With `--watch <folder>` (step 8) the command stays, looks at the folder every few seconds, and does the same for each job as it
finishes there: a job is finished when its `.sta` says the analysis completed and its `.lck` is gone. Jobs that had finished before the
watch started are left alone unless `--existing` is given. What was done for each job is kept in `anisotropy-watch.json` in the
folder, so no ODB is sent twice; an ODB that changes (the job run again) is a new one. A job that cannot be bundled or sent is said
and the watch goes on. It ends with Ctrl+C. The watch reads ODBs only, so it runs under `abaqus python` and takes no seat of
Abaqus/CAE.

The connector is six files kept in one folder: this one, `bundle.py`, `abaqus_every_output.py` and `abaqus_extract_fields.py`, and
for the menu in Abaqus/CAE `anisotropy_menu.py` and `anisotropy_plugin.py` (step 8).
`uv run python tools/abaqus_upload.py connector --out anisotropy-connector.zip` writes them as one zip to hand over; in the repository
they are found where they live.

The user's `.cae` is never opened: a copy in a temporary folder is. Opening a `.cae` changes the file even when nothing is saved
(Abaqus 2025, the first trial: another SHA-256 after `openMdb` alone). Under Abaqus/CAE the ODB comes first among our arguments,
because Abaqus 2025's launcher drops the `--` and ours are then found from the ODB on; and the exit code says nothing there (Abaqus/CAE
ends with 0 whatever the script did), so the line the command prints is the answer: the bundle's path, or `refused:` with the reason.

The standard library and Abaqus's own modules only; `odbAccess` and `abaqus` are imported inside the two readers, so everything else
is plain Python that the tests run without Abaqus. What the model reader could not read is listed in the file under `not_read`
instead of stopping the bundle. Its attribute names are Abaqus's scripting interface as documented; those a model imported from an
input file has were read on Abaqus 2025, the rest (a model drawn in Abaqus/CAE: its sections, loads and constraints) are UNVERIFIED.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import importlib.util
import io
import json
import math
import platform
import shutil
import sys
import tempfile
import os
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONNECTOR = "anisotropy-connector 0.4.0"
MODEL_FORMAT = 1
UNITS = ("mm-MPa", "m-Pa")
FILES = ("anisotropy_connector.py", "bundle.py", "abaqus_every_output.py", "abaqus_extract_fields.py",  # what is handed over, together
         "anisotropy_menu.py", "anisotropy_plugin.py")  # the last two are the menu in Abaqus/CAE (step 8)
TEXT_LIMIT = 400  # an Abaqus object printed as text is cut here: a region's repr can run to thousands of characters
SEND_ROUTE = "/v1/connector/uploads"  # the one route of the API an upload token opens (ADR-0094 step 5)
TOKEN_VARIABLE = "ANISOTROPY_UPLOAD_TOKEN"
TOKEN_PREFIX = "anisotropy_upload_"
SEND_TIMEOUT_S = 300.0
THIS_MACHINE = ("localhost", "127.0.0.1", "::1")
VERDICTS = {"agrees": "Agrees with ours", "differs": "Differs from ours", "incomplete": "Not every part could be compared",
            "refused": "The comparison does not take this bundle beside that run"}
WATCH_RECORD = "anisotropy-watch.json"  # in the watched folder: what was done for each job's ODB, so none is sent twice
WATCH_EVERY_S = 5.0
COMPLETED = "THE ANALYSIS HAS COMPLETED SUCCESSFULLY"  # the last line of a job's .sta, in Abaqus's words
NOT_COMPLETED = "THE ANALYSIS HAS NOT BEEN COMPLETED"
STA_TAIL = 4096  # the ending of a .sta is in its last lines
LISTENER = None  # the menu in Abaqus/CAE sets this to show every line in the window's message area (`anisotropy_menu.py`)


class Refused(Exception):
    pass


def here() -> Path:
    """This file's folder. `abaqus cae noGUI=` runs a script without `__file__`, so the command line is read then."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        for argument in sys.argv:
            name = argument.split("=", 1)[-1]
            if name.endswith("anisotropy_connector.py") and Path(name).is_file():
                return Path(name).resolve().parent
        return Path.cwd()


def load(name: str):
    """A module of ours loaded from its file: beside this one when the connector is handed over as a folder, or from the package in the
    repository. Loaded by path and under a name of its own, because the package holds a module called `abaqus`, which must never
    stand in front of Abaqus's."""
    for folder in (here(), here().parent / "src" / "anisotropy_fea"):
        path = folder / f"{name}.py"
        if path.is_file():
            spec = importlib.util.spec_from_file_location(f"anisotropy_{name}", str(path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise Refused(f"{name}.py is not beside the connector: keep the connector's files together in one folder")


def under_cae() -> bool:
    """Whether Abaqus/CAE's kernel runs this."""
    return hasattr(sys.modules.get("abaqus"), "mdb")


def say(text: str, error: bool = False) -> None:
    """A line for the user. Inside Abaqus/CAE without its window, print() goes to a message area nobody sees, so the terminal's own
    stream is written instead. From the menu, with the window, the message area is where the user looks: `LISTENER` takes the line."""
    if LISTENER is not None:
        LISTENER(text, error)
        return
    if under_cae():
        stream = (sys.__stderr__ if error else sys.__stdout__) or (sys.stderr if error else sys.stdout)
    else:
        stream = sys.stderr if error else sys.stdout
    stream.write(text + "\n")
    stream.flush()


def command_line(argv: list[str]) -> list[str]:
    """Our arguments. Started by `abaqus python`, all of them. Started by Abaqus/CAE, its own come first (`-cae -noGUI -tmpdir ...`):
    ours are those after `--` where the launcher keeps it, and from the ODB on where it does not (Abaqus 2025 drops it)."""
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    if {"-cae", "-nogui"} & {argument.lower() for argument in argv}:
        for i, argument in enumerate(argv):
            if argument.lower().endswith(".odb"):
                return argv[i:]
        raise Refused("give the job's .odb first, then the options:  abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units mm-MPa "
                      "--cae <model>.cae")
    return argv[1:]


# ------------------------------------------------------------------------------------------------ the model as built, from the .cae

def plain(value, depth: int = 0):
    """An Abaqus value as JSON takes it: numbers, text and lists as they are, anything else as Abaqus prints it (a symbolic constant
    prints as its name)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)) and depth < 6:
        return [plain(v, depth + 1) for v in value]
    text = str(value)
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + " ..."


def attributes(thing, names) -> dict:
    """The named attributes a thing has, as plain values; one it does not have, or cannot give, is left out."""
    out = {}
    for name in names:
        try:
            out[name] = plain(getattr(thing, name))
        except Exception:  # noqa: BLE001  Abaqus raises its own errors for a member that is not set
            continue
    return out


def member(thing, name: str):
    """A member of an Abaqus object, or None when it has none or will not give it (Abaqus raises its own errors for an option that is
    not set)."""
    try:
        return getattr(thing, name)
    except Exception:  # noqa: BLE001
        return None


def count(thing, name: str):
    try:
        return len(getattr(thing, name))
    except Exception:  # noqa: BLE001
        return None


def as_stated(described: dict) -> dict:
    """A step's state with nothing said that Abaqus does not say: a value whose own `...State` is UNSET becomes null. Abaqus gives 0.0
    for a degree of freedom that is left free, which would read as held at zero."""
    for key in list(described):
        if described.get(key + "State") == "UNSET":
            described[key] = None
    return described


def entries(repository) -> list:
    """(name, object) for each entry of an Abaqus repository, in its own order."""
    return [(str(key), repository[key]) for key in repository.keys()]


def kind(thing) -> str:
    return type(thing).__name__


PLY = ("plyName", "material", "thickness", "thicknessType", "orientationType", "orientationValue", "axis", "angle",
       "additionalRotationType", "numIntPoints", "suppressed")
LAYUP = ("symmetric", "elementType", "thicknessAssignment", "offsetType", "offsetValues", "preIntegrate", "integrationRule",
         "poissonDefinition", "poisson", "thicknessModulus", "temperature", "useDensity", "density")
ORIENTATION = ("orientationType", "localCsys", "axis", "angle", "additionalRotationType", "additionalRotationField", "stackDirection")
SECTION = ("symmetric", "preIntegrate", "integrationRule", "poissonDefinition", "poisson", "thicknessModulus", "idealization", "material",
           "thickness", "numIntPts")
LAYER = ("plyName", "material", "thickness", "orientAngle", "numIntPts")
ORIENTATION_ANGLES = {"ANGLE_0": 0.0, "ANGLE_45": 45.0, "ANGLE_90": 90.0, "ANGLE_NEG45": -45.0}  # a ply's angle given as one of Abaqus's choices
STEP = ("previous", "description", "nlgeom", "timePeriod", "initialInc", "minInc", "maxInc", "maxNumInc", "stabilizationMethod")
CONDITION = ("createStepName", "category", "region", "distributionType", "localCsys", "u1", "u2", "u3", "ur1", "ur2", "ur3", "cf1", "cf2", "cf3",
             "magnitude", "amplitude", "fixed", "buckleCase")
CONSTRAINT = ("controlPoint", "surface", "influenceRadius", "couplingType", "localCsys", "u1", "u2", "u3", "ur1", "ur2", "ur3", "suppressed")
# what a boundary condition, a load or an output request is in one step: the values live on the step, not on the object itself
BC_STATE = ("u1", "u2", "u3", "ur1", "ur2", "ur3", "u1State", "u2State", "u3State", "ur1State", "ur2State", "ur3State", "amplitude",
            "amplitudeState", "status")
LOAD_STATE = ("cf1", "cf2", "cf3", "cf1State", "cf2State", "cf3State", "magnitude", "magnitudeState", "amplitude", "amplitudeState", "status")
OUTPUT_STATE = ("variables", "variablesState", "frequency", "frequencyState", "numIntervals", "numIntervalsState", "timeInterval",
                "timeIntervalState", "propagationState", "status")
STATES = (("boundary_conditions", "boundaryConditionStates", BC_STATE), ("loads", "loadStates", LOAD_STATE),
          ("field_output_requests", "fieldOutputRequestStates", OUTPUT_STATE),
          ("history_output_requests", "historyOutputRequestStates", OUTPUT_STATE))
OUTPUT = ("createStepName", "variables", "frequency", "numIntervals", "region", "sectionPoints", "layupNames", "layupLocationMethod",
          "outputAtPlyTop", "outputAtPlyMid", "outputAtPlyBottom", "position", "directions")


def ply_as_built(ply) -> dict:
    """One ply as Abaqus gives it, and `rotation_deg`: its angle in degrees whichever way it was given, as one of Abaqus's four
    choices (ANGLE_45 with an angle of 0.0 beside it) or as a value. A ply turned by a coordinate system has none."""
    described = attributes(ply, PLY)
    given = described.get("orientationType")
    value = described.get("orientationValue")
    if given in ORIENTATION_ANGLES:
        described["rotation_deg"] = ORIENTATION_ANGLES[given]
    elif given == "SPECIFY_ORIENT" and isinstance(value, (int, float)) and not isinstance(value, bool):
        described["rotation_deg"] = float(value)
    return described


def part_as_built(part) -> dict:
    """One part: its geometry and mesh counted, its features, sets and surfaces by name, and each composite layup ply by ply."""
    out = attributes(part, ("space", "type"))
    out.update({name: count(part, name) for name in ("cells", "faces", "edges", "vertices")})
    out.update(nodes=len(part.nodes), elements=len(part.elements))
    out["element_types"] = sorted({str(element.type) for element in part.elements})
    if out["nodes"]:
        box = part.nodes.getBoundingBox()
        out["box"] = plain([box["low"], box["high"]])
    for name in ("features", "sets", "surfaces"):
        repository = member(part, name)
        if repository is not None:
            out[name] = [str(key) for key in repository.keys()]
    layups = []
    for name, layup in entries(member(part, "compositeLayups") or {}):
        described = {"name": name}
        described.update(attributes(layup, LAYUP))
        orientation = member(layup, "orientation")
        if orientation is not None:
            described["orientation"] = attributes(orientation, ORIENTATION)
        plies = layup.plies
        described["plies"] = [ply_as_built(plies[i]) for i in range(len(plies))]
        # a symmetric layup lists half its plies: the count through the thickness is stated beside them
        described["plies_through_thickness"] = len(plies) * (2 if described.get("symmetric") in (True, 1, "ON", "True") else 1)
        layups.append(described)
    out["layups"] = layups
    assignments = member(part, "sectionAssignments")
    if assignments is not None:
        out["section_assignments"] = [attributes(a, ("sectionName", "region", "offsetType", "offset", "thicknessAssignment"))
                                      for a in assignments]
    return out


def model_as_built(model, name: str) -> dict:
    """What a model in a `.cae` is made of, as far as the scripting interface gives it. Each group is read on its own: one that
    cannot be read is named under `not_read` with Abaqus's own words, and the rest still goes into the bundle."""
    out = {"model_format": MODEL_FORMAT, "read_by": CONNECTOR, "model": name, "not_read": []}

    def group(key: str, read) -> None:
        try:
            out[key] = read()
        except Exception as exc:  # noqa: BLE001  the reader must not stop the bundle; what failed is written down
            out["not_read"].append(f"{key}: {type(exc).__name__}: {exc}")

    def materials():
        listed = []
        for material_name, material in entries(model.materials):
            described = {"name": material_name}
            elastic = member(material, "elastic")
            if elastic is not None:
                described["elastic"] = attributes(elastic, ("type", "table", "noCompression", "noTension", "moduli"))
                fail = member(elastic, "failStress")
                if fail is not None:
                    described["fail_stress"] = attributes(fail, ("table",))
            density = member(material, "density")
            if density is not None:
                described["density"] = attributes(density, ("table",))
            listed.append(described)
        return listed

    def sections():
        listed = []
        for section_name, section in entries(model.sections):
            described = {"name": section_name, "kind": kind(section)}
            described.update(attributes(section, SECTION))
            layup = member(section, "layup")
            if layup is not None:
                described["layup"] = [attributes(layup[i], LAYER) for i in range(len(layup))]
            listed.append(described)
        return listed

    def assembly():
        root = model.rootAssembly
        return {"instances": [dict(name=instance_name, nodes=count(instance, "nodes"), elements=count(instance, "elements"),
                                   **attributes(instance, ("partName", "dependent")))
                              for instance_name, instance in entries(root.instances)],
                "sets": [str(key) for key in root.sets.keys()], "surfaces": [str(key) for key in root.surfaces.keys()],
                "reference_points": len(root.referencePoints)}

    def described_as(entry_name, entry, names) -> dict:
        described = dict(name=entry_name, kind=kind(entry), **attributes(entry, names))
        region = described.get("region")
        if isinstance(region, list) and region and isinstance(region[0], str):
            described["region_set"] = region[0]  # Abaqus gives a region as (the set's name, where it lives, ...): the name, apart
        return described

    def listed_as(repository, names):
        return lambda: [described_as(entry_name, entry, names) for entry_name, entry in entries(repository())]

    def steps():
        """Each step, and what every boundary condition, load and output request is in it: a displacement's value and an output
        request's variables are on the step's states, not on the objects."""
        listed = []
        for step_name, step in entries(model.steps):
            described = described_as(step_name, step, STEP)
            for key, source, names in STATES:
                try:
                    states = getattr(step, source)
                    described[key] = [as_stated(dict(name=state_name, **attributes(state, names))) for state_name, state in entries(states)]
                except Exception as exc:  # noqa: BLE001
                    out["not_read"].append(f"steps/{step_name}/{key}: {type(exc).__name__}: {exc}")
            listed.append(described)
        return listed

    group("parts", lambda: [dict(name=part_name, **part_as_built(part)) for part_name, part in entries(model.parts)])
    group("materials", materials)
    group("sections", sections)
    group("assembly", assembly)
    group("steps", steps)
    group("boundary_conditions", listed_as(lambda: model.boundaryConditions, CONDITION))
    group("loads", listed_as(lambda: model.loads, CONDITION))
    group("constraints", listed_as(lambda: model.constraints, CONSTRAINT))
    group("field_output_requests", listed_as(lambda: model.fieldOutputRequests, OUTPUT))
    group("history_output_requests", listed_as(lambda: model.historyOutputRequests, OUTPUT))
    return out


def read_cae(path: Path, model_name) -> dict:
    """The model as built, read inside Abaqus/CAE from `path`, which is a copy of the user's file (`files_of`). Only here are
    Abaqus/CAE's own modules imported. A model's constraints and output requests exist only once `caeModules` is loaded (Abaqus 2025)."""
    try:
        from abaqus import openMdb
        import caeModules  # noqa: F401
    except Exception:  # noqa: BLE001  not Abaqus/CAE's kernel: abaqus python, or no Abaqus at all
        raise Refused("reading a .cae needs Abaqus/CAE: run  abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units ... --cae "
                      f"{path.name}  (abaqus python reads the ODB only)") from None
    try:
        mdb = openMdb(pathName=str(path))
    except Exception as exc:  # noqa: BLE001  Abaqus's own error, in its words: a file of a newer release, or one it cannot open
        raise Refused(f"Abaqus/CAE could not open {path.name}: {exc}") from None
    try:
        names = [str(key) for key in mdb.models.keys()]
        if model_name is None and len(names) != 1:
            raise Refused(f"{path.name} holds the models {names}; name one with --model")
        if model_name is not None and model_name not in names:
            raise Refused(f"{path.name} holds no model {model_name}; it holds {names}")
        name = model_name or names[0]
        return model_as_built(mdb.models[name], name)
    finally:
        try:  # an empty database in its place lets go of the copy, so its folder can be removed
            from abaqus import Mdb
            Mdb()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------------------------------------ the bundle

def abaqus_python() -> str:
    return platform.python_version()


def files_of(args, folder: Path, read_job=None, read_model=None, as_built=None) -> tuple[dict, dict]:
    """Everything the bundle holds, written or found: role -> file, and where the results were read in the ODB. `read_job` and
    `read_model` stand in for the two readers in the tests. `as_built` is the model already read, from the session Abaqus/CAE has
    open (the menu): then no `.cae` is opened at all."""
    odb = args.odb
    if odb.suffix.lower() != ".odb" or not odb.is_file():
        raise Refused(f"no ODB at {odb}")
    deck = args.inp or odb.with_suffix(".inp")
    if not deck.is_file():
        raise Refused(f"no input file at {deck}: the bundle carries the deck Abaqus solved; name it with --inp")
    if args.journal and not args.journal.is_file():
        raise Refused(f"no journal at {args.journal}")
    if args.cae and not args.cae.is_file():
        raise Refused(f"no model file at {args.cae}")
    every = load("abaqus_every_output")
    try:
        data = (read_job or every.read)(odb.resolve(), args.step, args.frame, args.instance)
    except ImportError:
        raise Refused("this command runs under Abaqus's own Python, which reads the ODB: start it with  abaqus python "
                      "anisotropy_connector.py ...  or  abaqus cae noGUI=anisotropy_connector.py -- ...") from None
    rows = every.rows_of(data["points"], data["stress"], data["strain"], data["centroids"], data["components"], data["strain_components"])
    stem = odb.stem
    files = {"deck": deck, "every_output": folder / f"{stem}-every-output.csv"}
    every.write_csv(files["every_output"], every.COLUMNS, rows)
    if data["reactions"]:
        files["reactions"] = folder / f"{stem}-every-output-RF.csv"
        every.write_csv(files["reactions"], every.RF_COLUMNS, data["reactions"])
    results = {key: data[key] for key in ("solver", "created", "step", "frame_index", "frame", "instance")}
    journal = args.journal or (args.cae.with_suffix(".jnl") if args.cae else None)
    if journal is not None and journal.is_file():
        files["journal"] = journal
    model = as_built
    if args.cae:
        copied = folder / "cae" / args.cae.name  # the user's own .cae is never opened: opening one changes the file
        copied.parent.mkdir()
        shutil.copyfile(str(args.cae), str(copied))
        model = (read_model or read_cae)(copied, args.model)
    if model is not None:
        files["model"] = folder / f"{stem}-model.json"
        with io.open(str(files["model"]), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(model, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return files, results


# ------------------------------------------------------------------------------------------------ sending the bundle (step 5)

class NotSent(Exception):
    """The bundle was written and could not be sent."""


def send_address(address: str, our_run=None) -> str:
    """Where the bundle is posted: the site's API address with the connector's route. https only, apart from this machine itself,
    because the request carries the token."""
    parts = urllib.parse.urlsplit(address.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment or parts.username or parts.password:
        raise Refused("--send takes the address of Anisotropy's API and nothing more, such as https://<the site>/api: no name or password in "
                      "it, no question mark, no #")
    if parts.scheme == "http" and parts.hostname not in THIS_MACHINE:
        raise Refused("--send takes an https address: the request carries your upload token, which must not cross a network in the clear")
    query = "?" + urllib.parse.urlencode({"job_id": our_run}) if our_run else ""
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}{SEND_ROUTE}{query}"


def token_of(token_file, environ=None) -> str:
    """The upload token, from the file named or from the environment; refused with what to do when there is none. Never printed."""
    environ = os.environ if environ is None else environ
    if token_file is not None:
        if not token_file.is_file():
            raise Refused(f"no token file at {token_file}")
        with io.open(str(token_file), encoding="utf-8-sig") as handle:
            token = handle.read().strip()
        where = f"the file {token_file.name}"
    else:
        token = environ.get(TOKEN_VARIABLE, "").strip()
        where = f"the environment variable {TOKEN_VARIABLE}"
        if not token:
            raise Refused(f"--send needs your upload token: create one on the site, then name the file that holds it with --token-file, or set "
                          f"{TOKEN_VARIABLE}. It is not taken on the command line, where Abaqus would write it into abaqus.rpy")
    if not token.startswith(TOKEN_PREFIX) or len(token.split()) != 1:
        raise Refused(f"{where} does not hold an upload token: one starts with {TOKEN_PREFIX}")
    return token


def request_of(url: str, token: str, data: bytes):
    """The one request that carries a bundle: its zip as the body, the token in the Authorization header."""
    return urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/zip", "Accept": "application/json", "User-Agent": CONNECTOR})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an answer, not a place to go: the token is for the address the user named and no other."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(request, timeout: float):
    """(status, body) of the request as sent, without following a redirect."""
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as answer:
        return answer.code, answer.read()


def detail_of(body: bytes) -> str:
    """What the API said in a refusal, as one line; nothing when the body is not its JSON (a sign-in page, a proxy's own page)."""
    try:
        detail = json.loads(body.decode("utf-8")).get("detail")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return ""
    return detail if isinstance(detail, str) else json.dumps(detail) if detail is not None else ""


def send(url: str, token: str, bundle: Path, poster=post) -> dict:
    """Post the bundle and return the API's answer, the upload as it now stands. Raises `NotSent` with the reason."""
    with io.open(str(bundle), "rb") as handle:
        data = handle.read()
    try:
        status, body = poster(request_of(url, token, data), SEND_TIMEOUT_S)
    except (urllib.error.URLError, OSError) as exc:
        raise NotSent(f"the address did not answer: {getattr(exc, 'reason', exc)}") from None
    if 300 <= status < 400:
        raise NotSent(f"the address answered with a redirect ({status}), as a sign-in page does: the site does not take a connector's "
                      "upload at this address yet, or the address is not the API's")
    if status != 201:
        said = detail_of(body)
        raise NotSent(f"the site refused it ({status})" + (f": {said}" if said else ""))
    try:
        answer = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        answer = None
    if not isinstance(answer, dict) or not isinstance(answer.get("id"), str):
        raise NotSent("the address answered, and not as Anisotropy's API does: is it the API's address?")
    return answer


def say_sent(answer: dict) -> None:
    """The upload's id, whose it is, and the verdict when the site put it beside a run of ours."""
    say(f"sent: upload {answer['id']}, yours alone ({answer.get('bundle_bytes')} bytes, SHA-256 {answer.get('bundle_sha256')})")
    verdict = answer.get("verdict")
    if verdict in VERDICTS:
        say(f"{VERDICTS[verdict]}: beside the run {answer.get('job_id')}")
    else:
        say(f"not compared yet: {answer.get('not_compared') or 'no run of ours stood beside it'}")


class Parser(argparse.ArgumentParser):
    """argparse, saying its help and its errors where the user sees them (`say`)."""

    def _print_message(self, message, file=None):
        if message:
            say(message.rstrip("\n"), error=file is not sys.stdout)


def parse(argv: list[str]) -> argparse.Namespace:
    parser = Parser(prog="anisotropy_connector.py", description=__doc__.splitlines()[0])
    parser.add_argument("odb", type=Path, nargs="?", default=None, help="the finished job's .odb")
    parser.add_argument("--units", required=True, choices=UNITS, help="the system the model is written in; an Abaqus model carries none")
    parser.add_argument("--inp", type=Path, default=None, help="the input file Abaqus solved; default <job>.inp beside the ODB")
    parser.add_argument("--cae", type=Path, default=None, help="the model's .cae, read for the model as built (needs abaqus cae noGUI=)")
    parser.add_argument("--model", default=None, help="the model's name in the .cae, when it holds several")
    parser.add_argument("--journal", type=Path, default=None, help="Abaqus/CAE's journal; default the .jnl beside the .cae")
    parser.add_argument("--out", type=Path, default=None, help="the bundle to write; default <job>-anisotropy.zip beside the ODB")
    parser.add_argument("--step", default=None)
    parser.add_argument("--frame", type=int, default=None)
    parser.add_argument("--instance", default=None)
    parser.add_argument("--coupon", default=None, help="the coupon's name in Anisotropy, when you know it")
    parser.add_argument("--send", default=None, metavar="ADDRESS", help="also send the bundle to Anisotropy's API at this address, such as "
                                                                       "https://<the site>/api, with your upload token")
    parser.add_argument("--token-file", type=Path, default=None, help=f"the file that holds your upload token; default the environment variable {TOKEN_VARIABLE}")
    parser.add_argument("--our-run", default=None, help="the id of the run of ours to compare beside; default your newest finished run of --coupon")
    parser.add_argument("--watch", type=Path, default=None, metavar="FOLDER", help="stay, and do this for each job as it finishes in this folder "
                                                                                    "(abaqus python only); end with Ctrl+C")
    parser.add_argument("--every", type=float, default=None, metavar="SECONDS", help=f"how often the watch looks; default {WATCH_EVERY_S:g}")
    parser.add_argument("--existing", action="store_true", help="with --watch: also take the jobs that had finished before the watch started")
    parser.add_argument("--once", action="store_true", help="with --watch: look once and end")
    args = parser.parse_args(argv)
    if args.send is None and (args.token_file is not None or args.our_run is not None):
        parser.error("--token-file and --our-run go with --send")
    if (args.odb is None) == (args.watch is None):
        parser.error("give one finished job's .odb, or --watch <folder> for every job that finishes there")
    if args.watch is None and (args.every is not None or args.existing or args.once):
        parser.error("--every, --existing and --once go with --watch")
    if args.watch is not None:
        named = [name for name, value in (("--inp", args.inp), ("--cae", args.cae), ("--model", args.model), ("--journal", args.journal),
                                          ("--out", args.out), ("--our-run", args.our_run)) if value is not None]
        if named:
            parser.error(f"{', '.join(named)} name{'s' if len(named) == 1 else ''} one job's files and cannot go with --watch")
        if args.every is not None and not args.every >= 1.0:
            parser.error("--every takes a number of seconds, 1 or more")
    return args


def deliver(args, url=None, token=None, read_job=None, read_model=None, poster=post, as_built=None) -> dict:
    """One job's bundle, written and, with `url`, sent. Every line is said here. Returns what happened: `bundle` (its path), `sha256`,
    and with a send either `upload` (the site's answer) or `not_sent` (the reason; the bundle is on the disk). Raises `Refused`."""
    bundle = load("bundle")
    out = args.out or args.odb.with_name(f"{args.odb.stem}-anisotropy.zip")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:  # Abaqus/CAE may still hold the copy of the .cae
        files, results = files_of(args, Path(folder), read_job, read_model, as_built)
        written = bundle.write_bundle(out, files, args.units, CONNECTOR, abaqus=results["solver"], python=abaqus_python(), job=args.odb.stem,
                                      coupon=args.coupon, results=results)
    say(f"{out}: bundle version {written.manifest['bundle_version']} of {args.odb.stem}, in {args.units}")
    for role, entry in written.files.items():
        say(f"  {role}: {entry.path}, {entry.bytes} bytes")
    if "model" not in written.files and LISTENER is None:
        say("  the model as built is not in it: add --cae <model>.cae under  abaqus cae noGUI=anisotropy_connector.py -- ...")
    say(f"SHA-256 {written.sha256}")
    done = {"bundle": out, "sha256": written.sha256, "model": "model" in written.files}
    if url is not None:
        try:
            done["upload"] = send(url, token, out, poster)
            say_sent(done["upload"])
        except NotSent as exc:
            done["not_sent"] = str(exc)
            say(f"not sent: {exc}. The bundle is written: {out}", error=True)
    return done


# ------------------------------------------------------------------------------------------------ the watched folder (step 8)

def job_state(odb: Path) -> str:
    """Where a job stands, from the files Abaqus leaves beside its ODB: `running` (its `.lck` is there, or its `.sta` has no ending
    yet), `completed`, `not completed` (Abaqus's own ending), or `no status file` (an ODB that was not solved here)."""
    if odb.with_suffix(".lck").exists():
        return "running"
    sta = odb.with_suffix(".sta")
    if not sta.is_file():
        return "no status file"
    with io.open(str(sta), "rb") as handle:
        handle.seek(max(0, sta.stat().st_size - STA_TAIL))
        ending = handle.read().decode("utf-8", "replace")
    return "completed" if COMPLETED in ending else "not completed" if NOT_COMPLETED in ending else "running"


def mark_of(odb: Path) -> list:
    """What tells one ODB from the same job run again: its size and when it was last written."""
    status = odb.stat()
    return [status.st_size, status.st_mtime_ns]


def watch_record(folder: Path) -> dict:
    path = folder / WATCH_RECORD
    if path.is_file():
        try:
            with io.open(str(path), encoding="utf-8") as handle:
                found = json.load(handle)
            if isinstance(found, dict) and isinstance(found.get("jobs"), dict):
                return found
        except (ValueError, OSError):
            pass
        raise Refused(f"{path} is not the watch's own record: move it away, and the watch starts a new one")
    return {"written_by": CONNECTOR, "jobs": {}}


def keep_record(folder: Path, record: dict) -> None:
    """The record, written beside and then put in place, so a watch stopped in the middle leaves the old one whole."""
    path = folder / WATCH_RECORD
    beside = folder / (WATCH_RECORD + ".new")
    with io.open(str(beside), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(str(beside), str(path))


def watch_pass(args, record: dict, first: bool, url=None, token=None, read_job=None, poster=post) -> tuple[int, int]:
    """One look at the folder: every ODB whose job has ended and that the record does not hold yet is dealt with and written down.
    Returns how many jobs were dealt with and how many of those were not bundled or not sent."""
    dealt = failed = 0
    left = []
    for odb in sorted(args.watch.glob("*.odb")):
        job, mark = odb.stem, mark_of(odb)
        seen = record["jobs"].get(job)
        if seen is not None and seen.get("odb") == mark and not (args.existing and seen.get("state") == "before the watch"):
            continue  # dealt with already; a job an earlier watch left alone is taken once --existing asks for it
        state = job_state(odb)
        if state == "running":
            continue
        entry = {"odb": mark, "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if first and seen is None and not args.existing and state in ("completed", "not completed"):
            entry.update(state="before the watch", said="it had finished before the watch started")
            left.append(job)
        elif state == "no status file":
            entry.update(state="not taken", said=f"no {job}.sta beside the ODB, so the watch cannot tell that the job finished here; send it "
                                                 f"with  abaqus python anisotropy_connector.py {odb.name} --units {args.units} ...")
            say(f"{job}: {entry['said']}", error=True)
        elif state == "not completed":
            entry.update(state="not completed", said="Abaqus did not complete the analysis, so there is nothing to send")
            say(f"{job}: {entry['said']}", error=True)
            dealt, failed = dealt + 1, failed + 1
        else:
            one = copy.copy(args)
            one.odb, one.watch = odb, None
            dealt += 1
            try:
                done = deliver(one, url, token, read_job, None, poster)
            except Refused as exc:
                done = None
                entry.update(state="refused", said=str(exc))
            except Exception as exc:  # noqa: BLE001  one job's trouble does not end the watch
                if type(exc).__name__ not in ("ExtractError", "BundleRefused"):
                    say(f"{job}: the connector stopped on this job:\n" + traceback.format_exc(), error=True)
                done = None
                entry.update(state="refused", said=f"{type(exc).__name__}: {exc}")
            if done is None:
                failed += 1
                say(f"{job}: refused: {entry['said']}", error=True)
            else:
                entry.update(bundle=done["bundle"].name, bundle_sha256=done["sha256"])
                if "upload" in done:
                    answer = done["upload"]
                    entry.update(state="sent", upload=answer["id"], verdict=answer.get("verdict"), said=answer.get("not_compared") or "")
                elif "not_sent" in done:
                    entry.update(state="not sent", said=done["not_sent"])
                    failed += 1
                else:
                    entry.update(state="written", said="")
        record["jobs"][job] = entry
        keep_record(args.watch, record)
    if left:
        say(f"{len(left)} job{'s' if len(left) != 1 else ''} had finished before the watch started and {'are' if len(left) != 1 else 'is'} left "
            f"alone: {', '.join(left)}. Add --existing to take them too")
    return dealt, failed


def watch(args, url=None, token=None, read_job=None, poster=post, sleep=time.sleep) -> int:
    """Stay and deal with each job as it finishes in the folder, until Ctrl+C (or after one look, with `--once`). Exit 0, or 1 when
    `--once` found a job it could not bundle or send."""
    if under_cae():
        raise Refused("--watch runs under  abaqus python  (it reads ODBs only and takes no seat of Abaqus/CAE)")
    if not args.watch.is_dir():
        raise Refused(f"no folder at {args.watch}")
    record = watch_record(args.watch)
    every = args.every or WATCH_EVERY_S
    say(f"watching {args.watch} for jobs that finish, {'once' if args.once else f'every {every:g} s'}; "
        f"{'each bundle is sent to ' + url.split(SEND_ROUTE)[0] if url else 'each bundle is written beside its ODB and nothing is sent'}"
        f"{'' if args.once else '. End with Ctrl+C'}")
    first, failed = True, 0
    try:
        while True:
            failed += watch_pass(args, record, first, url, token, read_job, poster)[1]
            first = False
            if args.once:
                break
            sleep(every)
    except KeyboardInterrupt:
        say("the watch has ended")
        return 0
    return 1 if failed else 0


def main(argv=None, read_job=None, read_model=None, poster=post) -> int:
    args = parse(command_line(sys.argv) if argv is None else argv)
    # what sending needs is judged before the ODB is read, so a missing token costs no time
    url, token = (send_address(args.send, args.our_run), token_of(args.token_file)) if args.send is not None else (None, None)
    if args.watch is not None:
        return watch(args, url, token, read_job, poster)
    return 1 if "not_sent" in deliver(args, url, token, read_job, read_model, poster) else 0


def run(argv=None, read_job=None, read_model=None, poster=post) -> int:
    """`main`, with every ending said in one place: exit 0 written (and sent, when asked), 1 written and not sent, 2 refused or
    stopped. Abaqus/CAE writes an error of a script in `abaqus.rpy` only and ends with 0, and `abaqus.bat` drops the code of
    `abaqus python` too, so nothing may leave this function unsaid: the line is the answer, the code a courtesy."""
    try:
        return main(argv, read_job, read_model, poster)
    except Refused as exc:
        say(f"refused: {exc}", error=True)
    except SystemExit as exc:  # argparse, which has said why
        return exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:  # noqa: BLE001
        if type(exc).__name__ in ("ExtractError", "BundleRefused"):  # the ODB reader's and the bundle's own refusals: both say what to do
            say(f"refused: {exc}", error=True)
        elif under_cae():
            say("the connector stopped, and no bundle was written:\n" + traceback.format_exc(), error=True)
        else:
            raise
    return 2


if __name__ == "__main__":
    sys.exit(run())
