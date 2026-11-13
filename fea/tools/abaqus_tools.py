"""The three tools of a round trip through the user's own Abaqus (ADR-0094, step 4; ADR-0048): build, run, send.

    uv run python tools/abaqus_tools.py state <coupon>.toml --folder <work> [--json]
    uv run python tools/abaqus_tools.py build <coupon>.toml --folder <work>
    uv run python tools/abaqus_tools.py run   <coupon>.toml --folder <work>
    uv run python tools/abaqus_tools.py send  <coupon>.toml --folder <work>
    uv run python tools/abaqus_tools.py plan  <coupon>.toml --folder <work> --tools build run send

Each tool is one fixed command of Abaqus, on the machine that has it (ANISOTROPY_ABAQUS, or abaqus on PATH):

    build   abaqus cae noGUI=<coupon>-build.py -- save=<coupon>.cae     the script of `write_cae_script`, written from the spec
    run     abaqus job=<job> input=<job>.inp interactive ...            the input file Abaqus/CAE wrote for that model
    send    abaqus cae noGUI=anisotropy_connector.py -- <job>.odb ...   the connector's bundle, with the model as built read by name
                                                                        from the .cae, then our comparison of it

Nothing in a command is free text. The names in it are the ones our code derives from the spec (`cae_facts`), checked against a short
alphabet, and every file argument is a bare name in the one work folder. Whoever chooses the tools, a person or the assistant's model,
chooses among three names: no script, no path and no number comes from them (ADR-0001). A tool whose output is already in the folder is
refused, so nothing is written over, and a chain with a gap (send before run) is refused whole before anything runs.

Until an upload has somewhere to go (ADR-0094, step 5), `send` hands the bundle to the comparison on this machine: it solves the same
spec with our kernel into `<work>/ours/` and writes `<job>-comparison.json`, what `abaqus_upload.py compare` gives.

Every call is written to `<work>/abaqus-tools.json`: the tool, who chose it, the command as run, when, how long, what was said and
each file it left with its size and SHA-256. Abaqus/CAE ends with exit code 0 whatever happened (seen on Abaqus 2025), so a tool
judges by the files it finds and never by the exit code.

Exit 0 done (for send and plan: the bundle agrees with ours), 1 the bundle differs or could not be compared whole, 2 refused.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import abaqus_upload as upload  # noqa: E402  the bundle's check and comparison: one set of rules for every way in

from anisotropy_fea import __version__  # noqa: E402
from anisotropy_fea.abaqus import COMPLETED, AbaqusError, analysis_problems, find_abaqus  # noqa: E402
from anisotropy_fea.abaqus_reader import read_deck  # noqa: E402
from anisotropy_fea.bundle import BundleRefused  # noqa: E402
from anisotropy_fea.every_output import write_ours  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.kernel import solve_deck  # noqa: E402
from anisotropy_fea.mesher import MeshError  # noqa: E402
from anisotropy_fea.spec import SpecError, load_spec  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402
from anisotropy_fea.write_cae_script import CaeScriptError, cae_facts, write_cae_script  # noqa: E402

FORMAT = 1
RECORD = "abaqus-tools.json"
CONNECTOR = TOOLS / "anisotropy_connector.py"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")  # a model, a job and every file name a command carries
UNSAFE = set('"&|<>^%!\r\n')  # Abaqus is started through a .bat on Windows: a path with one of these is refused, not quoted
TIMEOUTS = {"build": 900.0, "run": 3600.0, "send": 900.0}
# What a chooser is told of each tool: its name and one sentence. The model sees these, the engineer's words and which steps are done.
DEFINITIONS = (
    {"name": "build", "description": "Build the coupon in Abaqus/CAE as a native model, from the script our code wrote for it, and save "
                                     "the model with its job's input file."},
    {"name": "run", "description": "Run that job in Abaqus/Standard and wait until it has finished."},
    {"name": "send", "description": "Read the finished job with the connector into one bundle and compare it with our own solve of the "
                                    "same coupon."},
)
ORDER = tuple(d["name"] for d in DEFINITIONS)
DONE = {"build": "built", "run": "ran", "send": "sent"}
NEEDS = {"build": None, "run": "build", "send": "run"}


class Refused(Exception):
    """A tool did not do its work; `problems` says why, every reason at once (ADR-0003)."""

    def __init__(self, problems, said: tuple[str, ...] = (), command: tuple[str, ...] = (), seconds: float = 0.0):
        self.problems = tuple([problems] if isinstance(problems, str) else problems)
        self.said, self.command, self.seconds = tuple(said), tuple(command), seconds
        super().__init__("; ".join(self.problems))


@dataclasses.dataclass(frozen=True)
class Done:
    """What a command left: its exit code and everything it printed."""

    returncode: int
    output: str


Runner = Callable[[list[str], Path, float], Done]


def start(argv: list[str], folder: Path, timeout_s: float) -> Done:
    """Run one command in the work folder and wait for it. No shell: the arguments go as a list."""
    done = subprocess.run(argv, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s, check=False)
    return Done(done.returncode, (done.stdout or "") + (done.stderr or ""))


@dataclasses.dataclass(frozen=True)
class Session:
    """One coupon in one work folder: the names every command carries, derived from the spec by our code."""

    spec_path: Path
    folder: Path
    coupon: str
    job: str
    units: str
    element: str
    spec_sha256: str

    @property
    def script(self) -> Path:
        return self.folder / f"{self.coupon}-build.py"

    @property
    def cae(self) -> Path:
        return self.folder / f"{self.coupon}.cae"

    @property
    def inp(self) -> Path:
        return self.folder / f"{self.job}.inp"

    @property
    def odb(self) -> Path:
        return self.folder / f"{self.job}.odb"

    @property
    def bundle(self) -> Path:
        return self.folder / f"{self.job}-anisotropy.zip"

    @property
    def comparison(self) -> Path:
        return self.folder / f"{self.job}-comparison.json"

    @property
    def ours(self) -> Path:
        return self.folder / "ours"


def unsafe_in(path: Path) -> list[str]:
    return sorted({c for c in str(path) if c in UNSAFE})


def session_of(spec_path: Path, folder: Path):
    """(the session, the spec, the model our deck and the build script are written from). Refused with every reason when the coupon is
    not one the build script draws, or when a name or the folder could not go into a command as it is."""
    try:
        spec = load_spec(spec_path)
        model = build_model(spec)
        facts = cae_facts(model)
    except CaeScriptError as exc:
        raise Refused(exc.problems) from exc
    except (SpecError, MeshError, ValueError, OSError) as exc:
        raise Refused(str(exc).splitlines()[0] if str(exc) else type(exc).__name__) from exc
    problems = [f"the {what} name {name!r} cannot go into a command: letters, digits, '.', '_' and '-' only, at most 80"
                for what, name in (("model", facts["model"]), ("job", facts["job"])) if not NAME.match(str(name))]
    folder = Path(folder).resolve()
    for what, path in (("work folder", folder), ("connector", CONNECTOR)):
        if unsafe_in(path):
            problems.append(f"the {what}'s path {path} holds {' '.join(unsafe_in(path))}, which a command started on Windows may not carry")
    if folder.exists() and not folder.is_dir():
        problems.append(f"{folder} is not a folder")
    if problems:
        raise Refused(problems)
    return Session(Path(spec_path).resolve(), folder, facts["model"], facts["job"], facts["units"], facts["element"], spec.source_sha256), spec, model


def completed(session: Session) -> bool:
    sta = session.folder / f"{session.job}.sta"
    return session.odb.is_file() and sta.is_file() and COMPLETED in sta.read_text(encoding="utf-8", errors="replace")


def state_of(session: Session) -> dict:
    """Which steps are done in the folder, by the files that are there, and the tool that can run next (None when all three are done)."""
    state = {"built": session.cae.is_file() and session.inp.is_file(), "ran": completed(session), "sent": session.bundle.is_file()}
    state["next"] = next((tool for tool in ORDER if not state[DONE[tool]]), None)
    return state


def plan_problems(tools: list[str], state: dict) -> list[str]:
    """Why a chain of tools cannot run from this state, every reason; empty when it can. The order is the physics', not the chooser's:
    a model is built before its job runs, and a job has finished before it is sent."""
    problems = [f"{tool!r} is not one of the tools: {', '.join(ORDER)}" for tool in tools if tool not in ORDER]
    if problems:
        return problems
    if not tools:
        return ["no tool was chosen"]
    done = {tool: bool(state[DONE[tool]]) for tool in ORDER}
    for tool in tools:
        if done[tool]:
            problems.append(f"{tool}: already done in this folder, and nothing is written over; use an empty folder for another round trip")
        elif NEEDS[tool] is not None and not done[NEEDS[tool]]:
            problems.append(f"{tool}: needs {NEEDS[tool]} first, which is not done and is not chosen before it")
        else:
            done[tool] = True
    return problems


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def files_of(session: Session, paths: list[Path]) -> dict:
    return {str(path.relative_to(session.folder).as_posix()): {"bytes": path.stat().st_size, "sha256": sha256_of(path)}
            for path in paths if path.is_file()}


def lines_of(output: str, limit: int = 40) -> list[str]:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    return lines[-limit:]


def replay_tail(session: Session, limit: int = 15) -> list[str]:
    """The end of `abaqus.rpy`, where Abaqus/CAE writes a script's error and nowhere else."""
    replay = session.folder / "abaqus.rpy"
    if not replay.is_file():
        return []
    return [f"abaqus.rpy: {line}" for line in lines_of(replay.read_text(encoding="utf-8", errors="replace"), limit)]


def abaqus_command(abaqus: str | Path | None) -> str:
    try:
        found = find_abaqus(abaqus)
    except AbaqusError as exc:
        raise Refused(str(exc)) from exc
    if found is None:
        raise Refused("Abaqus not found: set ANISOTROPY_ABAQUS or put abaqus on PATH (docs/installation-fea-tools.md). These tools run "
                      "under your own Abaqus, on the machine that has it")
    if unsafe_in(found):
        raise Refused(f"the path of Abaqus, {found}, holds {' '.join(unsafe_in(found))}, which a command started on Windows may not carry")
    return str(found)


def run_command(tool: str, argv: list[str], session: Session, runner: Runner) -> tuple[Done, float]:
    began = time.perf_counter()
    try:
        done = runner(argv, session.folder, TIMEOUTS[tool])
    except subprocess.TimeoutExpired as exc:
        raise Refused(f"Abaqus did not finish within {TIMEOUTS[tool]:g} s; look in {session.folder} before trying again", command=argv,
                      seconds=time.perf_counter() - began) from exc
    except OSError as exc:
        raise Refused(f"Abaqus could not be started: {exc}", command=argv, seconds=time.perf_counter() - began) from exc
    return done, time.perf_counter() - began


def build(session: Session, model, abaqus: str | Path | None = None, runner: Runner = start) -> dict:
    """Write the build script into the folder and have Abaqus/CAE run it: the model as `<coupon>.cae` and its job's input file."""
    there = [path.name for path in (session.script, session.cae, session.inp) if path.exists()]
    if there:
        raise Refused(f"already in {session.folder}: {', '.join(there)}. Nothing is written over; use an empty folder for another round trip")
    command = abaqus_command(abaqus)
    session.folder.mkdir(parents=True, exist_ok=True)
    session.script.write_text(write_cae_script(model), encoding="utf-8", newline="\n")
    argv = [command, "cae", f"noGUI={session.script.name}", "--", f"save={session.cae.name}"]
    done, seconds = run_command("build", argv, session, runner)
    said = lines_of(done.output)
    missing = [path.name for path in (session.cae, session.inp) if not path.is_file()]
    if missing:
        raise Refused(f"Abaqus/CAE ended without writing {' and '.join(missing)}", said=said + replay_tail(session), command=argv, seconds=seconds)
    _, deck = upload.deck_facts(session.inp, session.units)
    if not deck["read"]:
        raise Refused(f"the model was built, and our reader does not take the input file Abaqus/CAE wrote: {deck['reason']}", said=said,
                      command=argv, seconds=seconds)
    return {"command": argv, "seconds": seconds, "said": said, "files": files_of(session, [session.script, session.cae, session.inp]),
            "facts": {"model": session.coupon, "job": session.job, "units": session.units, "nodes": deck.get("nodes"),
                      "elements": deck.get("elements"), "element_type": deck.get("element_type"), "plies": deck.get("plies")}}


def run(session: Session, abaqus: str | Path | None = None, runner: Runner = start, cpus: int = 1) -> dict:
    """Run the job Abaqus/CAE wrote the input file for, in the foreground, and judge it by what Abaqus wrote."""
    if not session.inp.is_file():
        raise Refused(f"no {session.inp.name} in {session.folder}: build the model first")
    lock = session.folder / f"{session.job}.lck"
    if session.odb.exists() or lock.exists():
        raise Refused(f"{(session.odb if session.odb.exists() else lock).name} is already in {session.folder}: this job has run, or Abaqus is "
                      "still running it. Nothing is written over; use an empty folder for another round trip")
    command = abaqus_command(abaqus)
    argv = [command, f"job={session.job}", f"input={session.inp.name}", "interactive", "ask_delete=OFF", f"cpus={int(cpus)}"]
    done, seconds = run_command("run", argv, session, runner)

    def text_of(suffix: str) -> str:
        path = session.folder / f"{session.job}{suffix}"
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    said = lines_of(done.output)
    problems = analysis_problems(done.output, text_of(".sta"), text_of(".msg"), text_of(".dat"))
    if not session.odb.is_file():
        problems.append(f"Abaqus wrote no {session.odb.name}")
    if problems:
        raise Refused(problems, said=said, command=argv, seconds=seconds)
    warnings = sum(text.count("***WARNING") for text in (text_of(".msg"), text_of(".dat")))
    return {"command": argv, "seconds": seconds, "said": said + [COMPLETED.capitalize()],
            "files": files_of(session, [session.odb, session.folder / f"{session.job}.sta"]), "facts": {"job": session.job, "warnings": warnings}}


def our_run(session: Session, spec, model) -> tuple[Path, Path]:
    """Our own solve of the same spec, in the files the comparison reads: (ours-every-output.csv, our deck)."""
    session.ours.mkdir(exist_ok=True)
    deck = session.ours / f"{session.coupon}-abaqus.inp"
    deck.write_text(write_abaqus(model), encoding="utf-8", newline="\n")
    solution = solve_deck(read_deck(deck, session.units))
    rows = session.ours / "ours-every-output.csv"
    write_ours(rows, rows.with_suffix(".json"), spec, solution, session.units, session.coupon, session.element, __version__)
    return rows, deck


def send(session: Session, spec, model, abaqus: str | Path | None = None, runner: Runner = start) -> dict:
    """Have the connector write the bundle of the finished job, with the model as built, and compare it with our own solve."""
    if not completed(session):
        raise Refused(f"no finished job {session.job} in {session.folder}: run it first")
    if session.bundle.exists():
        raise Refused(f"{session.bundle.name} is already in {session.folder}. Nothing is written over; use an empty folder for another round trip")
    command = abaqus_command(abaqus)
    argv = [command, "cae", f"noGUI={CONNECTOR}", "--", session.odb.name, "--units", session.units, "--coupon", session.coupon]
    if session.cae.is_file():  # by name: the .cae Abaqus/CAE saved also holds its own empty Model-1 (seen on Abaqus 2025)
        argv += ["--cae", session.cae.name, "--model", session.coupon]
    done, seconds = run_command("send", argv, session, runner)
    said = lines_of(done.output)
    if not session.bundle.is_file():
        raise Refused(f"the connector ended without writing {session.bundle.name}", said=said + replay_tail(session), command=argv, seconds=seconds)
    try:
        checked = upload.check(session.bundle)
        if not checked["in_scope"]:
            reasons = [f"{part}: {checked[part]['reason']}" for part in ("deck", "every_output", "reactions")
                       if checked.get(part) and not checked[part]["read"]]
            raise Refused(["the bundle was written and our comparison does not take it", *reasons], said=said, command=argv, seconds=seconds)
        rows, deck = our_run(session, spec, model)
        result = upload.compare(session.bundle, rows, deck)
    except (BundleRefused, upload.OutOfScope, upload.team.Refused) as exc:
        problems = list(exc.problems) if hasattr(exc, "problems") else [str(exc)]
        raise Refused(["the bundle was written and could not be compared", *problems], said=said, command=argv, seconds=seconds) from exc
    upload.write_json(session.comparison, result)
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        upload.print_comparison(result)
    model_file = checked.get("model")
    return {"command": argv, "seconds": seconds, "said": said + printed.getvalue().splitlines(), "verdict": result["verdict"],
            "files": files_of(session, [session.bundle, session.comparison, rows, deck]),
            "facts": {"bundle_sha256": checked["bundle"]["sha256"], "rows": checked["every_output"]["rows"],
                      "model_as_built": bool(model_file), "not_read": list((model_file or {}).get("not_read", []))}}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(session: Session, entry: dict) -> None:
    """Add one call to the folder's record. The record is rewritten whole each time, so it is always valid JSON."""
    path = session.folder / RECORD
    session.folder.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "format": FORMAT, "written_by": f"anisotropy_fea {__version__}", "coupon": session.coupon, "job": session.job, "units": session.units,
        "spec": {"name": session.spec_path.name, "sha256": session.spec_sha256}, "calls": []}
    data["calls"].append(entry)
    path.write_text(json.dumps(upload.plain(data), indent=1, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def call(tool: str, session: Session, spec, model, chosen_by: str, asked: str | None, abaqus=None, runner: Runner = start) -> dict:
    """One tool, recorded whatever its ending. Returns the record's entry; `outcome` is done or refused."""
    entry = {"tool": tool, "chosen_by": chosen_by, "asked": asked, "started": now()}
    try:
        result = build(session, model, abaqus, runner) if tool == "build" else run(session, abaqus, runner) if tool == "run" \
            else send(session, spec, model, abaqus, runner)
        entry.update(outcome="done", **result)
    except Refused as exc:
        entry.update(outcome="refused", problems=list(exc.problems), command=list(exc.command), seconds=exc.seconds, said=list(exc.said), files={})
    entry["seconds"] = round(float(entry["seconds"]), 3)
    record(session, entry)
    return entry


def print_entry(entry: dict) -> None:
    if entry["outcome"] == "refused":
        print(f"{entry['tool']}: refused\n" + "\n".join(f"  {p}" for p in entry["problems"]), file=sys.stderr)
        for line in entry["said"]:
            print(f"    {line}", file=sys.stderr)
        return
    print(f"{entry['tool']}: done in {entry['seconds']:.1f} s")
    for line in entry["said"]:
        print(f"  {line}")
    for name, facts in entry["files"].items():
        print(f"  wrote {name}, {facts['bytes']} bytes")


def exit_code(entries: list[dict]) -> int:
    if any(entry["outcome"] == "refused" for entry in entries):
        return 2
    verdicts = [entry["verdict"] for entry in entries if "verdict" in entry]
    return 1 if any(verdict != "agrees" for verdict in verdicts) else 0


def main(argv: list[str] | None = None, runner: Runner = start) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("state", "which steps are done in the folder"), *((d["name"], d["description"]) for d in DEFINITIONS),
                       ("plan", "several of the three tools, in the order given; nothing runs when the chain has a gap")):
        c = commands.add_parser(name, help=text)
        c.add_argument("spec", type=Path, help="the coupon's spec (.toml)")
        c.add_argument("--folder", type=Path, required=True, help="the work folder of this round trip; one coupon, one folder")
        if name == "state":
            c.add_argument("--json", action="store_true", help="print the state and the tools' definitions as JSON")
            continue
        c.add_argument("--abaqus", default=None, help="the Abaqus command; default ANISOTROPY_ABAQUS, then abaqus on PATH")
        c.add_argument("--chosen-by", default="the command line", help="who chose the tools, for the record")
        c.add_argument("--asked", default=None, help="the words the tools were chosen from, for the record")
        if name == "plan":
            c.add_argument("--tools", nargs="+", required=True, choices=ORDER)
    args = parser.parse_args(argv)
    try:
        session, spec, model = session_of(args.spec, args.folder)
    except Refused as exc:
        print("refused:\n" + "\n".join(f"  {p}" for p in exc.problems), file=sys.stderr)
        return 2
    state = state_of(session)
    if args.command == "state":
        if args.json:
            print(json.dumps({"coupon": session.coupon, "job": session.job, "units": session.units, "state": state, "tools": list(DEFINITIONS)}))
        else:
            print(f"{session.coupon} in {session.folder}: " + ", ".join(f"{DONE[tool]} {'yes' if state[DONE[tool]] else 'no'}" for tool in ORDER)
                  + (f"; next: {state['next']}" if state["next"] else "; the round trip is done"))
        return 0
    tools = args.tools if args.command == "plan" else [args.command]
    problems = plan_problems(tools, state)
    if problems:
        print("refused, and nothing was run:\n" + "\n".join(f"  {p}" for p in problems), file=sys.stderr)
        return 2
    entries = []
    for tool in tools:
        entries.append(call(tool, session, spec, model, args.chosen_by, args.asked, args.abaqus, runner))
        print_entry(entries[-1])
        if entries[-1]["outcome"] == "refused":
            break
    print(f"record: {session.folder / RECORD}")
    return exit_code(entries)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
