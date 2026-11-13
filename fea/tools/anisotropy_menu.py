"""What the two entries of the Anisotropy menu in Abaqus/CAE do (ADR-0094, step 8). `anisotropy_plugin.py` registers them; a click
makes Abaqus/CAE's kernel import this module and call `open_from_anisotropy()` or `send_to_anisotropy()`.

Open from Anisotropy: asks for the build script downloaded from a run's page, offering the newest `*-build.py` it finds in the work
directory and in Downloads, and runs it as File > Run Script would. It runs only a script whose first lines say that Anisotropy wrote
it; any other script is the user's to run from File > Run Script. The script adds one model and one job and saves nothing.

Send to Anisotropy: asks for the finished job's ODB (offering the one on the screen, or the newest finished job in the work
directory), the units, and, to send as well, Anisotropy's address and the file that holds the upload key. It then does what the
connector's command does (`anisotropy_connector.py`): one file, `<job>-anisotropy.zip`, beside the ODB, sent when an address is given.
Two things differ from the command, because here the model is open:

- the model as built is read from the session, from the model the job of the ODB's name was created for. No `.cae` is opened or
  saved. When the session has no job of that name the file is written without the model, and the menu says so;
- the ODB is read from a copy in a temporary folder, because reading ends by closing the ODB, and the one on the screen stays open;
- a model that Open from Anisotropy built says, in its description, which coupon of Anisotropy's it is and in which units. The units
  are offered in the box, and the coupon's name goes with the file, so the site puts it beside your newest finished run of that
  coupon with nothing typed. A model drawn by hand names no coupon, and the file is then sent without one.

Every line is shown in the message area under the viewport. The answers, never the key itself, are kept in
`.anisotropy/connector.json` in the home directory and offered the next time. Nothing here draws a window of its own: the questions
are Abaqus's own input boxes (`getInput`, `getInputs`), which exist only when Abaqus/CAE runs with its window.

The standard library and Abaqus's own modules only. Abaqus's modules are imported inside the two entry functions, so everything else
is plain Python that the tests run without Abaqus. Python 3, so Abaqus 2024 or later.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

MARK = "# Built by anisotropy_fea "  # in the first lines of every build script (`write_cae_script`)
HEAD_LINES = 4
SCRIPTS = "*-build.py"
BUILT = re.compile(r"Built by anisotropy_fea \S+ from (\S+), spec sha256 [0-9a-f]+, units (\S+)")  # the model's description, by the same writer
UNITS_FIRST = "mm-MPa"
KEPT = ("units", "address", "token_file")
ODB_FIELD = "The finished job's ODB:"
UNITS_FIELD = "Units of your model (mm-MPa or m-Pa):"
ADDRESS_FIELD = "Send to: Anisotropy's address (leave empty to write the file only):"
KEY_FIELD = "The file that holds your upload key:"
SEND_LABEL = ("One file is written beside the ODB: its results, the input file and the model as built. "
              "With an address it is also sent, and it is yours alone.")
OPEN_PROMPT = "The build script downloaded from the run's page (its name ends in -build.py):"


class NotDone(Exception):
    """What was asked cannot be done; the message says why and what to do."""


def here() -> Path:
    return Path(__file__).resolve().parent


def connector():
    """The connector, loaded once from beside this file under a name of its own."""
    name = "anisotropy_connector_of_the_menu"
    if name not in sys.modules:
        path = here() / "anisotropy_connector.py"
        if not path.is_file():
            raise NotDone("anisotropy_connector.py is not beside the menu: keep the connector's files together in one folder")
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


def show(text: str, error: bool = False) -> None:
    """A line in the message area: with the window open that is where the kernel's print goes."""
    print(text)


class Listening:
    """While this holds, every line the connector says goes to the message area."""

    def __init__(self, module):
        self.module = module

    def __enter__(self):
        self.before, self.module.LISTENER = self.module.LISTENER, show
        return self.module

    def __exit__(self, *exc):
        self.module.LISTENER = self.before
        return False


def settings_file() -> Path:
    return Path.home() / ".anisotropy" / "connector.json"


def kept_answers(path: Path | None = None) -> dict:
    """The answers given the last time, or nothing; a file that is not ours is ignored."""
    path = path or settings_file()
    try:
        with io.open(str(path), encoding="utf-8") as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        return {}
    return {key: found[key] for key in KEPT if isinstance(found, dict) and isinstance(found.get(key), str)}


def keep_answers(answers: dict, path: Path | None = None) -> None:
    """The units, the address and where the key's file is, for the next time. The key itself is never read here or written."""
    path = path or settings_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            json.dump({key: answers.get(key, "") for key in KEPT}, handle, indent=1, sort_keys=True)
            handle.write("\n")
    except OSError:
        pass  # the answers are a convenience: the next box starts empty


def typed(answer) -> str:
    """An answer as typed, without the quotes a path copied from Windows comes in."""
    return str(answer or "").strip().strip('"').strip()


# ------------------------------------------------------------------------------------------------ Open from Anisotropy

def is_ours(path: Path) -> bool:
    """Whether the file's first lines say that Anisotropy's build-script writer wrote it."""
    try:
        with io.open(str(path), encoding="utf-8", errors="replace") as handle:
            return any(handle.readline().startswith(MARK) for _ in range(HEAD_LINES))
    except OSError:
        return False


def build_scripts(folders) -> list:
    """The build scripts of ours in these folders, the newest first."""
    found = []
    for folder in folders:
        try:
            found += [path for path in Path(folder).glob(SCRIPTS) if path.is_file() and is_ours(path)]
        except OSError:
            continue
    return sorted(set(found), key=lambda path: path.stat().st_mtime, reverse=True)


def open_script(path: Path) -> dict:
    """Run a build script of ours as File > Run Script would, and return what it defined. The script says its own ending."""
    if not path.is_file():
        raise NotDone(f"no file at {path}")
    if not is_ours(path):
        raise NotDone(f"{path.name} is not a build script Anisotropy wrote, so this entry does not run it. Download the build script from "
                      "the run's page; any other script runs from File > Run Script")
    with io.open(str(path), encoding="utf-8") as handle:
        text = handle.read()
    space = {"__name__": "__main__", "__file__": str(path)}
    exec(compile(text, str(path), "exec"), space)  # noqa: S102  the user's own click on a script our own code wrote
    return space


def open_from_anisotropy() -> None:
    """The menu's first entry."""
    try:
        from abaqus import getInput
        found = build_scripts([Path.cwd(), Path.home() / "Downloads"])
        answer = getInput(OPEN_PROMPT, str(found[0]) if found else "")
        if answer is None:
            return  # cancelled
        if not typed(answer):
            raise NotDone("name the build script: download it from the run's page on Anisotropy (\"Open in Abaqus/CAE\")")
        built = open_script(Path(typed(answer)))
        try:  # the new model on the screen; where that fails the model is still there, in the model tree
            from abaqus import mdb, session
            session.viewports[session.currentViewportName].setValues(displayedObject=mdb.models[built["MODEL"]].rootAssembly)
        except Exception:  # noqa: BLE001
            pass
    except NotDone as exc:
        show(f"not opened: {exc}", error=True)
    except Exception as exc:  # noqa: BLE001  the build script's own refusal (a name that is taken), or Abaqus's error, in its words
        show(f"not built: {exc}", error=True)


# ------------------------------------------------------------------------------------------------ Send to Anisotropy

def shown_odb(session) -> str:
    """The ODB on the screen, when the viewport shows one."""
    try:
        shown = session.viewports[session.currentViewportName].displayedObject
        path = str(getattr(shown, "path", "") or "")
    except Exception:  # noqa: BLE001
        return ""
    return path if path.lower().endswith(".odb") else ""


def finished_jobs(folder: Path) -> list:
    """The ODBs of jobs that completed in this folder, the newest first."""
    state = connector().job_state
    try:
        found = [path for path in Path(folder).glob("*.odb") if state(path) == "completed"]
    except OSError:
        return []
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def model_of(mdb, job: str):
    """The name of the model the job of this name was created for in the open session, or None when the session has no such job."""
    try:
        if job not in [str(key) for key in mdb.jobs.keys()]:
            return None
        name = str(mdb.jobs[job].model)
        return name if name in [str(key) for key in mdb.models.keys()] else None
    except Exception:  # noqa: BLE001
        return None


def built_as(mdb, model) -> dict:
    """What the build script wrote on the model it made: the coupon's name in Anisotropy and the units. Nothing for a model drawn by
    hand, or one whose description was changed."""
    try:
        found = BUILT.search(str(getattr(mdb.models[model], "description", "") or "")) if model is not None else None
    except Exception:  # noqa: BLE001
        return {}
    return {"coupon": found.group(1), "units": found.group(2)} if found else {}


def journal_of(mdb):
    """The journal beside the session's saved `.cae`, when there is one."""
    try:
        saved = str(getattr(mdb, "pathName", "") or "")
    except Exception:  # noqa: BLE001
        return None
    journal = Path(saved).with_suffix(".jnl") if saved else None
    return journal if journal is not None and journal.is_file() else None


def reading_a_copy(read):
    """The ODB reader, given a copy of the ODB in a temporary folder: reading ends by closing the ODB, and the one the user has on
    the screen is the same file."""
    def reader(path, step, frame, instance):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            copied = Path(folder) / Path(path).name
            shutil.copyfile(str(path), str(copied))
            return (read or connector().load("abaqus_every_output").read)(copied, step, frame, instance)
    return reader


def send(odb: str, units: str, address: str = "", token_file: str = "", mdb=None, read_job=None, poster=None) -> dict:
    """Write the job's bundle and, with an address, send it; the model as built comes from the open session `mdb`. Returns what the
    connector's `deliver` returns. Raises `NotDone`, or the connector's own refusals."""
    c = connector()
    if not odb:
        raise NotDone("name the finished job's ODB")
    if units not in c.UNITS:
        raise NotDone(f"the units are one of {' or '.join(c.UNITS)}: an Abaqus model carries none, so they are stated")
    argv = [odb, "--units", units]
    if address:
        argv += ["--send", address] + (["--token-file", token_file] if token_file else [])
    elif token_file:
        show("no address was given, so the file is written and not sent")
    args = c.parse(argv)
    url, token = (c.send_address(args.send, None), c.token_of(args.token_file)) if args.send is not None else (None, None)
    name = model_of(mdb, args.odb.stem) if mdb is not None else None
    as_built = c.model_as_built(mdb.models[name], name) if name is not None else None
    if name is None:
        show(f"the model as built is not in the file: this session has no job named {args.odb.stem}, so it cannot tell which model that "
             "job solved. The results and the input file are")
    else:
        args.journal = journal_of(mdb)
        built = built_as(mdb, name)
        if built and built["units"] != units:
            show(f"note: the build script made this model in {built['units']} and you stated {units}. The file says {units}; if the model "
                 "was not changed to them, send it again with the model's own units")
        if built:
            args.coupon = built["coupon"]
            show(f"this model was built from Anisotropy's coupon {built['coupon']}" + (": the site puts the file beside your newest finished "
                 "run of it" if address else ""))
    return c.deliver(args, url, token, reading_a_copy(read_job), None, poster or c.post, as_built)


def send_to_anisotropy() -> None:
    """The menu's second entry."""
    try:
        from abaqus import getInputs, mdb, session
        kept = kept_answers()
        finished = finished_jobs(Path.cwd())
        offered = shown_odb(session) or (str(finished[0]) if finished else "")
        built = built_as(mdb, model_of(mdb, Path(offered).stem)) if offered else {}
        fields = ((ODB_FIELD, offered), (UNITS_FIELD, built.get("units") or kept.get("units") or UNITS_FIRST),
                  (ADDRESS_FIELD, kept.get("address", "")), (KEY_FIELD, kept.get("token_file", "")))
        answers = getInputs(fields=fields, label=SEND_LABEL, dialogTitle="Send to Anisotropy")
        if answers is None or len(answers) != len(fields) or answers[0] is None:
            return  # cancelled
        odb, units, address, token_file = (typed(answer) for answer in answers)
        with Listening(connector()) as c:
            try:
                send(odb, units, address, token_file, mdb)
                keep_answers({"units": units, "address": address, "token_file": token_file})
            except SystemExit:
                pass  # the connector's own reading of the answers, which has said why
            except c.Refused as exc:
                show(f"refused: {exc}", error=True)
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ not in ("NotDone", "ExtractError", "BundleRefused"):
                    raise
                show(f"refused: {exc}", error=True)
    except NotDone as exc:
        show(f"refused: {exc}", error=True)
    except Exception:  # noqa: BLE001  nothing leaves a menu entry unsaid
        show("Send to Anisotropy stopped:\n" + traceback.format_exc(), error=True)
