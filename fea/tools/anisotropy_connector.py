"""The connector: one command, run by the user with their own Abaqus, that turns a finished job into one exchange bundle (ADR-0094, step 2).

    abaqus python anisotropy_connector.py <job>.odb --units mm-MPa
        [--inp <job>.inp] [--journal <model>.jnl] [--out <bundle>.zip] [--step Step-1] [--frame -1] [--instance COUPON-1] [--coupon <name>]
    abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units mm-MPa --cae <model>.cae [--model Model-1]

The first form needs no seat of Abaqus/CAE. It reads the job's ODB as `abaqus_every_output.py` does (every element and ply at each
layer's middle section point, and the reactions), takes the input file Abaqus solved from beside the ODB, and writes
`<job>-anisotropy.zip` beside it: a bundle of version 1 (`bundle.py`), each file with its SHA-256. The second form runs inside
Abaqus/CAE without its window and also reads the model as built from the `.cae` (the parts, the materials, the layup ply by ply, the
steps, the boundary conditions, the output requests) into `<job>-model.json`, and takes the `.jnl` beside the `.cae` as text.

The deck system is stated, never inferred: an Abaqus model carries no units (ADR-0002, ADR-0003). Nothing is sent anywhere: the
command writes one file, and the user decides where it goes. No path of the user's machine is written into the manifest; a journal
is the user's own file and goes in as it is.

The connector is four files kept in one folder: this one, `bundle.py`, `abaqus_every_output.py` and `abaqus_extract_fields.py`.
`uv run python tools/abaqus_upload.py connector --out anisotropy-connector.zip` writes them as one zip to hand over; in the repository
they are found where they live. The `.cae` is opened and read, never saved.

The standard library and Abaqus's own modules only; `odbAccess` and `abaqus` are imported inside the two readers, so everything else
is plain Python that the tests run without Abaqus. What the model reader could not read is listed in the file under `not_read`
instead of stopping the bundle: its attribute names are Abaqus's scripting interface as documented, UNVERIFIED on a real `.cae`
until the first run on the founder's machine.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import math
import platform
import sys
import tempfile
from pathlib import Path

CONNECTOR = "anisotropy-connector 0.1.0"
MODEL_FORMAT = 1
UNITS = ("mm-MPa", "m-Pa")
FILES = ("anisotropy_connector.py", "bundle.py", "abaqus_every_output.py", "abaqus_extract_fields.py")  # what is handed over, together
TEXT_LIMIT = 400  # an Abaqus object printed as text is cut here: a region's repr can run to thousands of characters


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


def say(text: str, error: bool = False) -> None:
    """A line for the user. Inside Abaqus/CAE without its window, print() goes to a message area nobody sees, so the terminal's own
    stream is written instead."""
    if hasattr(sys.modules.get("abaqus"), "mdb"):  # Abaqus/CAE's kernel
        stream = (sys.__stderr__ if error else sys.__stdout__) or (sys.stderr if error else sys.stdout)
    else:
        stream = sys.stderr if error else sys.stdout
    stream.write(text + "\n")
    stream.flush()


def command_line(argv: list[str]) -> list[str]:
    """Our arguments: everything after `--` when Abaqus/CAE started the script (its own arguments come first), else all of them."""
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


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
STEP = ("previous", "description", "nlgeom", "timePeriod", "initialInc", "minInc", "maxInc", "maxNumInc", "stabilizationMethod")
CONDITION = ("createStepName", "category", "region", "distributionType", "localCsys", "u1", "u2", "u3", "ur1", "ur2", "ur3", "cf1", "cf2", "cf3",
             "magnitude", "amplitude", "fixed", "buckleCase")
CONSTRAINT = ("controlPoint", "surface", "influenceRadius", "couplingType", "localCsys", "u1", "u2", "u3", "ur1", "ur2", "ur3", "suppressed")
OUTPUT = ("createStepName", "variables", "frequency", "numIntervals", "region", "sectionPoints", "layupNames", "layupLocationMethod",
          "outputAtPlyTop", "outputAtPlyMid", "outputAtPlyBottom", "position", "directions")


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
        described["plies"] = [attributes(plies[i], PLY) for i in range(len(plies))]
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

    def listed_as(repository, names):
        return lambda: [dict(name=entry_name, kind=kind(entry), **attributes(entry, names)) for entry_name, entry in entries(repository())]

    group("parts", lambda: [dict(name=part_name, **part_as_built(part)) for part_name, part in entries(model.parts)])
    group("materials", materials)
    group("sections", sections)
    group("assembly", assembly)
    group("steps", listed_as(lambda: model.steps, STEP))
    group("boundary_conditions", listed_as(lambda: model.boundaryConditions, CONDITION))
    group("loads", listed_as(lambda: model.loads, CONDITION))
    group("constraints", listed_as(lambda: model.constraints, CONSTRAINT))
    group("field_output_requests", listed_as(lambda: model.fieldOutputRequests, OUTPUT))
    return out


def read_cae(path: Path, model_name) -> dict:
    """The model as built, read inside Abaqus/CAE. Only here are Abaqus/CAE's own modules imported. The file is opened and read; it
    is never saved."""
    try:
        from abaqus import openMdb
    except Exception:  # noqa: BLE001  not Abaqus/CAE's kernel: abaqus python, or no Abaqus at all
        raise Refused("reading a .cae needs Abaqus/CAE: run  abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units ... --cae "
                      f"{path.name}  (abaqus python reads the ODB only)") from None
    try:
        mdb = openMdb(pathName=str(path))
    except Exception as exc:  # noqa: BLE001  Abaqus's own error, in its words: a file of a newer release, or one it cannot open
        raise Refused(f"Abaqus/CAE could not open {path.name}: {exc}") from None
    names = [str(key) for key in mdb.models.keys()]
    if model_name is None and len(names) != 1:
        raise Refused(f"{path.name} holds the models {names}; name one with --model")
    if model_name is not None and model_name not in names:
        raise Refused(f"{path.name} holds no model {model_name}; it holds {names}")
    name = model_name or names[0]
    return model_as_built(mdb.models[name], name)


# ------------------------------------------------------------------------------------------------ the bundle

def abaqus_python() -> str:
    return platform.python_version()


def files_of(args, folder: Path, read_job=None, read_model=None) -> tuple[dict, dict]:
    """Everything the bundle holds, written or found: role -> file, and where the results were read in the ODB. `read_job` and
    `read_model` stand in for the two readers in the tests."""
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
    if args.cae:
        model = (read_model or read_cae)(args.cae.resolve(), args.model)
        files["model"] = folder / f"{stem}-model.json"
        with io.open(str(files["model"]), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(model, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return files, results


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="anisotropy_connector.py", description=__doc__.splitlines()[0])
    parser.add_argument("odb", type=Path, help="the finished job's .odb")
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
    return parser.parse_args(argv)


def main(argv=None, read_job=None, read_model=None) -> int:
    args = parse(command_line(sys.argv) if argv is None else argv)
    bundle = load("bundle")
    out = args.out or args.odb.with_name(f"{args.odb.stem}-anisotropy.zip")
    with tempfile.TemporaryDirectory() as folder:
        files, results = files_of(args, Path(folder), read_job, read_model)
        written = bundle.write_bundle(out, files, args.units, CONNECTOR, abaqus=results["solver"], python=abaqus_python(), job=args.odb.stem,
                                      coupon=args.coupon, results=results)
    say(f"{out}: bundle version {written.manifest['bundle_version']} of {args.odb.stem}, in {args.units}")
    for role, entry in written.files.items():
        say(f"  {role}: {entry.path}, {entry.bytes} bytes")
    if "model" not in written.files:
        say("  the model as built is not in it: add --cae <model>.cae under  abaqus cae noGUI=anisotropy_connector.py -- ...")
    say(f"SHA-256 {written.sha256}")
    return 0


def run(argv=None, read_job=None, read_model=None) -> int:
    """`main`, with a refusal said in one line: exit 0 written, 2 refused."""
    try:
        return main(argv, read_job, read_model)
    except Refused as exc:
        say(f"refused: {exc}", error=True)
    except Exception as exc:  # the ODB reader's and the bundle's own refusals, by their names: both say what to do
        if type(exc).__name__ not in ("ExtractError", "BundleRefused"):
            raise
        say(f"refused: {exc}", error=True)
    return 2


if __name__ == "__main__":
    sys.exit(run())
