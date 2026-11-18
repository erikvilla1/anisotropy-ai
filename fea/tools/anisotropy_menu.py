"""What the two entries of the Anisotropy menu in Abaqus/CAE do (ADR-0094, step 8). `anisotropy_plugin.py` registers them; a click
makes Abaqus/CAE's kernel import this module and call `open_from_anisotropy()` or `send_to_anisotropy()`.

Open from Anisotropy: asks for a coupon file, the data Send to Abaqus left on this PC (`<coupon>-coupon.json` in `Anisotropy/<coupon>/`
in the home directory), offering the newest, and builds the coupon from it again with the connector's own code
(`anisotropy_build.py`): one model and one job, nothing saved. The file is read as data and checked field by field. This entry runs
no script (amendment 4): a build script downloaded from a run's page is the user's to run with Abaqus's own File > Run Script.

Send to Anisotropy: asks for the finished job's ODB (offering the one on the screen, or the newest finished job in the work
directory), the units, and, to send as well, Anisotropy's address and the file that holds the upload key. It then does what the
connector's command does (`anisotropy_connector.py`): one file, `<job>-anisotropy.zip`, beside the ODB, sent when an address is given.
Two things differ from the command, because here the model is open:

- the model as built is read from the session, from the model the job of the ODB's name was created for. No `.cae` is opened or
  saved. When the session has no job of that name the file is written without the model, and the menu says so;
- the ODB is read from a copy in a temporary folder, because reading ends by closing the ODB, and the one on the screen stays open;
- a model built from Anisotropy says, in its description, which coupon of Anisotropy's it is and in which units. The units
  are offered in the box, and the coupon's name goes with the file, so the site puts it beside your newest finished run of that
  coupon with nothing typed. A model drawn by hand names no coupon, and the file is then sent without one.

Since amendment 1 a click on the site can start Abaqus/CAE with the coupon built (`anisotropy_link.py`, `anisotropy_start.py`), and
`opened_from_the_site` is what runs then: the same build from the coupon file the helper fetched and checked, and from then on the results of that model's job go back to the run it
was opened from when the job completes, with nothing typed. Only a model opened that way in this session is sent by itself; a model
drawn by hand, or built from the menu, is sent when its user sends it. On a PC connected from the site the box of Send to Anisotropy
comes with the address and the key's file filled in.

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
import os
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

COUPONS = "*coupon.json"  # the helper writes <coupon>-coupon.json in the coupon's folder (`anisotropy_link.open_run`)
BUILT = re.compile(r"Built by anisotropy_fea \S+ from (\S+), spec sha256 [0-9a-f]+, units (\S+)")  # the model's description, as the site writes it
UNITS_FIRST = "mm-MPa"
KEPT = ("units", "address", "token_file")
ODB_FIELD = "The finished job's ODB:"
UNITS_FIELD = "Units of your model (mm-MPa or m-Pa):"
ADDRESS_FIELD = "Send to: Anisotropy's address (leave empty to write the file only):"
KEY_FIELD = "The file that holds your upload key:"
SEND_LABEL = ("One file is written beside the ODB: its results, the input file and the model as built. "
              "With an address it is also sent, and it is yours alone.")
OPEN_PROMPT = "The coupon file that Send to Abaqus left on this PC (its name ends in coupon.json):"
RUNS = {}  # for this session: the model's name -> the run on the site it was opened from (`opened_from_the_site`)
WATCHING = False  # whether Abaqus/CAE was asked to tell us when a job completes


class NotDone(Exception):
    """What was asked cannot be done; the message says why and what to do."""


def here() -> Path:
    return Path(__file__).resolve().parent


def beside(file: str, name: str):
    """One of the connector's own files, loaded once from beside this file under a name of its own."""
    if name not in sys.modules:
        path = here() / file
        if not path.is_file():
            raise NotDone(f"{file} is not beside the menu: keep the connector's files together in one folder")
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


def connector():
    """The connector: what reads a finished job, writes its bundle and sends it."""
    return beside("anisotropy_connector.py", "anisotropy_connector_of_the_menu")


def builder():
    """The check of a coupon's data and the code that builds it in Abaqus/CAE."""
    return beside("anisotropy_build.py", "anisotropy_build_of_the_menu")


SESSION = "ANISOTROPY_SESSION"  # the link's helper sets it for the Abaqus/CAE it starts: a name of that one window's own
SESSION_SHAPE = re.compile(r"[0-9a-f]{16}")
HELD = None  # while a job-message callback runs, the lines it says (`job_completed`)


def show(text: str, error: bool = False) -> None:
    """A line in the message area: with the window open that is where the kernel's print goes. Inside a job-message callback the line is
    held instead: a print from the kernel can hold back the answer to a command the window has just sent, so the click that sent it
    looks unfinished until the next one (the twelfth trial)."""
    if HELD is not None:
        HELD.append(text)
        return
    print(text)


def window_files(folder: Path | None = None):
    """(where this session's held lines go, the file by which its window says that it shows them); None when this Abaqus/CAE was
    not started from the site, which is the only start that names the session."""
    name = os.environ.get(SESSION, "")
    if not SESSION_SHAPE.fullmatch(name):
        return None
    folder = folder or (Path.home() / ".anisotropy")
    return folder / f"messages-{name}.txt", folder / f"messages-{name}.window"


def hand_over(lines: list, folder: Path | None = None) -> None:
    """The held lines, for the window's own side to show (`anisotropy_plugin.py`). They are printed after all when no window has
    said that it shows them, or when they cannot be written: a line said late is better than a line never seen."""
    if not lines:
        return
    files = window_files(folder)
    try:
        if files is None or not files[1].is_file():
            raise OSError("no window shows them")
        with io.open(str(files[0]), "a", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(line + "\n" for line in lines))
    except OSError:
        for line in lines:
            print(line)


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

def coupon_files(folders) -> list:
    """The coupon files in these folders, the newest first."""
    found = []
    for folder in folders:
        try:
            found += [path for path in Path(folder).glob(COUPONS) if path.is_file()]
        except OSError:
            continue
    return sorted(set(found), key=lambda path: path.stat().st_mtime, reverse=True)


def kept_coupons(work: Path | None = None) -> list:
    """Where Send to Abaqus leaves a coupon: the work directory, and each coupon's folder under `Anisotropy` in the home directory."""
    work = work or (Path.home() / "Anisotropy")
    try:
        folders = [folder for folder in work.iterdir() if folder.is_dir()]
    except OSError:
        folders = []
    return coupon_files([Path.cwd(), *folders])


def open_coupon(path: Path) -> dict:
    """Build the coupon a coupon file states, with the connector's own code, and return what `anisotropy_build.build` returns. The
    file is data: it is checked and its values are handed to Abaqus/CAE. Nothing in it is run, and a script is refused."""
    if path.suffix.lower() == ".py":
        raise NotDone(f"{path.name} is a script, and this entry runs none. A build script from a run's page is run with File > Run Script; "
                      "this entry takes the coupon file that Send to Abaqus left on this PC")
    build = builder()
    try:
        data = build.read(path)
    except build.NotACoupon as exc:
        raise NotDone(f"{path.name} is not a coupon file this connector builds: " + "; ".join(exc.problems[:3])[:400]) from None
    return build.build(data)


def on_the_screen(built: dict) -> None:
    """The new model in the viewport; where that fails the model is still there, in the model tree."""
    try:
        from abaqus import mdb, session
        session.viewports[session.currentViewportName].setValues(displayedObject=mdb.models[built["model"]].rootAssembly)
    except Exception:  # noqa: BLE001
        pass


def open_from_anisotropy() -> None:
    """The menu's first entry."""
    try:
        from abaqus import getInput
        found = kept_coupons()
        answer = getInput(OPEN_PROMPT, str(found[0]) if found else "")
        if answer is None:
            return  # cancelled
        if not typed(answer):
            raise NotDone("name the coupon file: Send to Abaqus on a run's page leaves it in Anisotropy/<coupon>/ in your home directory")
        built = open_coupon(Path(typed(answer)))
        on_the_screen(built)
        show("built: model %s, %d nodes and %d %s elements, job %s, units %s; nothing is saved until you save it" % (
            built["model"], built["nodes"], built["elements"], built["element"], built["job"], built["units"]))
    except NotDone as exc:
        show(f"not opened: {exc}", error=True)
    except Exception as exc:  # noqa: BLE001  the build's own refusal (a name that is taken), or Abaqus's error, in its words
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
    """What a build from Anisotropy wrote on the model it made: the coupon's name in Anisotropy and the units. Nothing for a model
    drawn by hand, or one whose description was changed."""
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


def send(odb: str, units: str, address: str = "", token_file: str = "", mdb=None, read_job=None, poster=None, our_run=None) -> dict:
    """Write the job's bundle and, with an address, send it; the model as built comes from the open session `mdb`. It is sent beside
    `our_run`, or beside the run the model was opened from in this session, when there is one. Returns what the connector's
    `deliver` returns. Raises `NotDone`, or the connector's own refusals."""
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
    name = model_of(mdb, args.odb.stem) if mdb is not None else None
    our_run = our_run or RUNS.get(name)
    url, token = (c.send_address(args.send, our_run), c.token_of(args.token_file)) if args.send is not None else (None, None)
    as_built = c.model_as_built(mdb.models[name], name) if name is not None else None
    if name is None:
        show(f"the model as built is not in the file: this session has no job named {args.odb.stem}, so it cannot tell which model that "
             "job solved. The results and the input file are")
    else:
        args.journal = journal_of(mdb)
        built = built_as(mdb, name)
        if built and built["units"] != units:
            show(f"note: this model was built from Anisotropy in {built['units']} and you stated {units}. The file says {units}; if the model "
                 "was not changed to them, send it again with the model's own units")
        if built:
            args.coupon = built["coupon"]
            beside = "" if not address else ": the site puts the file beside the run it was opened from" if our_run else \
                ": the site puts the file beside your newest finished run of it"
            show(f"this model was built from Anisotropy's coupon {built['coupon']}{beside}")
    return c.deliver(args, url, token, reading_a_copy(read_job), None, poster or c.post, as_built)


def send_and_say(odb: str, units: str, address: str, token_file: str, mdb, read_job=None, poster=None, our_run=None):
    """`send`, with every refusal said in the message area: what `send` returns, or None when it was refused."""
    with Listening(connector()) as c:
        try:
            return send(odb, units, address, token_file, mdb, read_job, poster, our_run)
        except SystemExit:
            return None  # the connector's own reading of the answers, which has said why
        except c.Refused as exc:
            show(f"refused: {exc}", error=True)
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ not in ("NotDone", "ExtractError", "BundleRefused"):
                raise
            show(f"refused: {exc}", error=True)
    return None


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
        if send_and_say(odb, units, address, token_file, mdb) is not None:
            keep_answers({"units": units, "address": address, "token_file": token_file})
    except NotDone as exc:
        show(f"refused: {exc}", error=True)
    except Exception:  # noqa: BLE001  nothing leaves a menu entry unsaid
        show("Send to Anisotropy stopped:\n" + traceback.format_exc(), error=True)


# ------------------------------------------------------------------------------------------------ opened from the site (amendment 1)

def watch_jobs() -> bool:
    """Ask Abaqus/CAE to tell this module when a job completes, once for the session. False where it cannot be asked (without the
    window Abaqus sends no job messages), and the reason is said."""
    global WATCHING
    if WATCHING:
        return True
    try:
        from abaqus import monitorManager
        from jobMessage import ANY_JOB, JOB_COMPLETED
        monitorManager.addMessageCallback(jobName=ANY_JOB, messageType=JOB_COMPLETED, callback=job_completed, userData=None)
    except Exception as exc:  # noqa: BLE001
        show(f"Anisotropy: this session does not say when a job completes ({exc}), so send the results with Plug-ins > Anisotropy > "
             "Send to Anisotropy")
        return False
    WATCHING = True
    return True


def completed(job: str, mdb, folder: Path | None = None, read_job=None, poster=None):
    """A job completed: when its model was opened from the site in this session, its results go back to that run. What `send`
    returns; None for any other model, which nobody asked to send, and when it could not be sent, with the reason said."""
    model = model_of(mdb, job)
    run = RUNS.get(model)
    if run is None:
        return None
    units = built_as(mdb, model).get("units")
    kept = kept_answers()
    odb = (folder or Path.cwd()) / f"{job}.odb"
    if not units:
        show(f"Anisotropy: the job {job} completed, and its model's description no longer says the units it was built in, so its results "
             "were not sent by themselves. Send them with Plug-ins > Anisotropy > Send to Anisotropy", error=True)
        return None
    if not kept.get("address") or not kept.get("token_file"):
        show(f"Anisotropy: the job {job} completed, and this PC is not connected to your account, so its results were not sent. Click "
             "Connect this PC on the run's page, then Plug-ins > Anisotropy > Send to Anisotropy", error=True)
        return None
    show(f"Anisotropy: the job {job} completed. Its results go back to the run this model was opened from")
    done = send_and_say(str(odb), units, kept["address"], kept["token_file"], mdb, read_job, poster, run)
    if done is not None and "upload" in done:
        show("Anisotropy: the comparison is on the run's page on the site")
    return done


def job_completed(jobName, messageType, data, userData) -> None:  # noqa: N803  Abaqus's own names
    """What Abaqus/CAE calls when a job completes. Nothing it raises may reach Abaqus: under Abaqus 2025 an exception that leaves a
    job-message callback makes Abaqus/CAE report the job itself as aborted, though the solver completed, and the exception's text
    is written nowhere (the tenth trial). So everything is caught here, a stop of the interpreter's own included, and said. What it says
    is held while it runs and handed to the window's side at the end (`show`, `hand_over`)."""
    global HELD
    HELD = []
    try:
        from abaqus import mdb
        completed(str(jobName), mdb)
    except BaseException:  # noqa: BLE001
        try:
            show("Anisotropy: sending the results stopped. The job itself completed:\n" + traceback.format_exc(), error=True)
        except BaseException:  # noqa: BLE001  not even the saying may reach Abaqus
            pass
    finally:
        held, HELD = HELD, None
        try:
            hand_over(held)
        except BaseException:  # noqa: BLE001
            pass


def opened_from_the_site(facts: dict) -> None:
    """What `anisotropy_start.py` calls when a click on the site started Abaqus/CAE: build the coupon from the data the helper
    fetched and checked, put it on the screen, and send its job's results back to the run when the job completes."""
    try:
        named = facts.get("coupon_file")
        if not isinstance(named, str) or not named:
            raise NotDone("the start names no coupon file: click Send to Abaqus on the run's page again")
        built = open_coupon(Path(named))
        on_the_screen(built)
        model, job, run = built["model"], built["job"], str(facts.get("run") or "")
        if model and run:
            RUNS[model] = run
        show(f"Anisotropy: {facts.get('coupon') or model} is built from your run as the model {model}, with the job {job}. Nothing is saved "
             "until you save it.")
        if model and run and watch_jobs():
            show(f"Change what you want to study, then submit the job (right-click {job} under Jobs, Submit). When it completes, its "
                 "results go back to your run by themselves.")
    except NotDone as exc:
        show(f"not opened: {exc}", error=True)
    except Exception as exc:  # noqa: BLE001  the build's own refusal, or Abaqus's error, in its words
        show(f"not built: {exc}", error=True)
