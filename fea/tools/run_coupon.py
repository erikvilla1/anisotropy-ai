"""Take a coupon from its input form, its values file or its folder, to its package with one command (ADR-0049, ADR-0051).

    uv run python tools/run_coupon.py <filled form>.xlsx --run-by "Erik Villa"   # a new coupon: its form is read first
    uv run python tools/run_coupon.py <values>.json --run-by "Erik Villa"        # the same rows as the studio sends them
    uv run python tools/run_coupon.py <coupon> --run-by "Erik Villa"             # a coupon that has its specs, after an edit

Runs the steps of the case page's Rebuild section in order, with its placeholders filled: reads the input (as coupon_from_form.py),
writes the decks (as regenerate_decks.py --ccx), starts the next attempt (as new_attempt.py), solves the coupon with our engine
(build_model.py, without its drawings), runs the CalculiX twin (run_calculix.py) and writes the CalculiX record (record_from_dat.py).
That is the result: the progress file says it (`result`) before anything else is made, so the studio shows it while the rest is
built (ADR-0064). Then the documents: the engine's drawings (build_model.py --drawings only) and the package (as
docs/models/coupon.py). Last it adds the attempt's row to the case page's attempt log, a failed try included, refreshes the page's
result and lists the files to open. It stops at the first step before the result that fails and names it; a document that fails
after the result leaves the result standing, and the row and the outcome say which document is missing and why. Nothing is written before CalculiX
is found (ANISOTROPY_CCX or ccx on PATH) and the coupon's case page reads. An input that the setup check blocks is refused with the
failing items named, before anything is written.

Options: --machine (default: the operating system and the CalculiX version found), --replace (with an input: rewrite the specs of a
coupon that has them), --no-pdf (the package without its PDF, where Tectonic is missing), --no-theory, --result <file> (the outcome
as JSON, for the API's coupon jobs), --progress <file> (the stage reached and the files made so far, rewritten after every step, for
the studio), --gate <file> (once the coupon is named and its specs are written, wait for this file before the attempt: `go` goes on,
any other text refuses the run with that text; the hosted tier's solver claims the coupon there, ADR-0056 amendment 3).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from anisotropy_fea import __version__, paths
from anisotropy_fea.attempts import AttemptError, attempt_number, attempts, start_attempt
from anisotropy_fea.calculix import CalculixError, ccx_version, find_ccx
from anisotropy_fea.case_pages import ATTEMPT_ROW, CasePageError, fill, page_blocks, read_case, record_summary, rel, signed
from anisotropy_fea.checks import setup_checklist
from anisotropy_fea.femodel import build_model
from anisotropy_fea.intake import VALUES_SUFFIX, IntakeError, convert, gauge_probes, read_input
from anisotropy_fea.preview import preview_data
from anisotropy_fea.quality import element_quality
from anisotropy_fea.spec import load_spec

from regenerate_decks import regenerate  # noqa: E402  (tools share a folder)

TOLERANCE, FLOOR = 0.03, 0.02  # the CalculiX record's, as the case page's Rebuild section gives them (intake.next_commands)
LEFT_OUT = {  # why the record keeps the gauge probes only, in the words the coupons' records use
    "open_hole_tension": "gauge node and far element only: beside the hole the bilinear kernel element and S8R differ in the small components",
    None: "centre probe only: the near-grip element was left out because the two element types differ most beside a tab line, in the small components",
}
COUPON_DOCUMENT = "anisotropy_models_coupon"  # docs/models/coupon.py, loaded under the name its tests use
INPUT_SUFFIXES = (".xlsx", VALUES_SUFFIX)
STAGES = ("the setup check", "the input", "the decks", "the attempt", "our engine", "CalculiX", "the CalculiX record", "the result", "the drawings",
          "the package", "the outputs")
DOCUMENT_STAGES = STAGES[STAGES.index("the drawings"):]  # after the result: made in the background of the studio's view (ADR-0064)
STUDIO = "studio"  # the attempt's run/studio/: the checklist and the preview the studio showed before the run
GATE_GO = "go"  # the word at the gate that lets a held run go on
GATE_POLL_S = 0.1
GATE_WAIT_S = 600.0  # a held run that hears nothing in this long is refused: whatever was to answer has gone


class Refused(ValueError):
    """The run cannot start; nothing was written."""


class StepFailed(RuntimeError):
    """A step stopped the run; the attempt's row says which."""

    coupon: str | None = None
    attempt: Path | None = None


@dataclass(frozen=True)
class Outcome:
    """What a finished run made: the attempt, the record's summary and every file to open, by key."""

    coupon: str
    attempt: Path
    result: str
    outputs: dict[str, Path]
    documents: str = "written"  # "written", or what is missing and why: a document can fail after the result stands (ADR-0064)
    result_at: float | None = None  # time.perf_counter() when the result was reported


class Progress:
    """The stage reached and the files made so far, written as JSON after every step when a path is given (the studio polls it)."""

    def __init__(self, path: Path | None):
        self.path = path
        self.stage: str | None = None
        self.done: list[str] = []
        self.outputs: dict[str, Path] = {}
        self.coupon: str | None = None
        self.attempt: Path | None = None
        self.held = False  # waiting at the gate (--gate)
        self.result: str | None = None  # the result's one line, once the solve and the record are done (ADR-0064)

    def start(self, stage: str) -> None:
        if self.stage is not None:
            self.done.append(self.stage)
        self.stage = stage
        print(f"\n== {stage}", flush=True)
        self.write()

    def made(self, **outputs: Path) -> None:
        self.outputs.update({key: path for key, path in outputs.items() if path.exists()})
        self.write()

    def write(self) -> None:
        if self.path is None:
            return
        data = {"stage": self.stage, "done": list(self.done), "stages": list(STAGES), "outputs": {key: rel(p) for key, p in self.outputs.items()},
                "coupon": self.coupon, "attempt": None if self.attempt is None else rel(self.attempt), "held": self.held, "result": self.result}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def calculix() -> str:
    """The version of the CalculiX this run will use; refused, before anything is written, when there is none."""
    ccx = find_ccx()
    if ccx is None:
        raise Refused("CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md); nothing was written")
    version = ccx_version(ccx)
    if version is None:
        raise Refused(f"{ccx} printed no version for -v; nothing was written")
    return version


def check_coupon(name: str) -> None:
    """Both specs exist, and the case page reads with its attempt log level with the attempt folders, so the next row is the next folder."""
    folder = paths.local_test(name)
    ours = folder / paths.OURS
    missing = [p.name for p in (ours / f"{name}.toml", ours / f"{name}-nodal.toml") if not p.is_file()]
    if missing:
        raise Refused(f"{name}: no {', '.join(missing)} in {rel(ours)}; start the coupon from its input form")
    logged = read_case(folder).attempts
    found = attempts(name)
    if found and attempt_number(found[-1]) > logged:
        raise Refused(f"{name}: ours/runs/ holds {found[-1].name} but the attempt log ends at row {logged:02d}; "
                      f"add the missing rows to {rel(folder / 'README.md')} first (ADR-0039)")


def check_setup(source: str):
    """The studio's setup check on an input file (ADR-0051): refused, with the failing items named, when it blocks the run."""
    checklist, model, quality = setup_checklist(read_input(source), paths.LOCAL)
    if checklist.state == "blocked":
        failing = [f"{item.label}: {item.message}" for item in checklist.items if item.state in ("fail", "missing")]
        raise Refused("the setup check blocks the run: " + "; ".join(failing) + "; nothing was written")
    return checklist, model, quality


def wait_at_gate(gate: Path | None, progress: Progress) -> None:
    """With a gate file: the coupon is named and its specs are written, and no attempt is numbered yet. The progress says `held`, and
    the run waits until the file appears: `go` goes on; any other text refuses the run with that text. The hosted tier's solver
    claims the coupon here, so two jobs never number attempts of one coupon at once (ADR-0056 amendment 3)."""
    if gate is None:
        return
    progress.held = True
    progress.write()
    deadline = time.monotonic() + GATE_WAIT_S
    while not gate.is_file():
        if time.monotonic() > deadline:
            raise Refused(f"no word at the gate {gate.name} in {GATE_WAIT_S:g} s; the run was not continued")
        time.sleep(GATE_POLL_S)
    word = gate.read_text(encoding="utf-8").strip()
    progress.held = False
    progress.write()
    if word != GATE_GO:
        raise Refused(word or "the gate refused the run")


def script(step: str, args: list[str], cwd: Path) -> None:
    """One of our scripts under this Python, its output straight to the console; a nonzero exit stops the run at `step`."""
    done = subprocess.run([sys.executable, *args], cwd=cwd, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False)
    if done.returncode:
        raise StepFailed(f"{step}: {Path(args[0]).name} exited with code {done.returncode}")


def package(name: str, pdf: bool, theory: bool) -> Path:
    """The coupon's document and package, built in this process so that they read the coupon where this run wrote it; returns the
    package folder, which docs/models/coupon.py names by the day it is built."""
    module = sys.modules.get(COUPON_DOCUMENT)
    if module is None:
        spec = importlib.util.spec_from_file_location(COUPON_DOCUMENT, paths.ROOT / "docs" / "models" / "coupon.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[COUPON_DOCUMENT] = module
        spec.loader.exec_module(module)
    try:
        _, folder = module.build_document(module.sources(name, paths.LOCAL), pdf=pdf, theory=theory)
    except SystemExit as exc:  # the document code stops with a message, as a script does
        raise StepFailed(f"the package: {exc}") from None
    return folder


def add_row(folder: Path, cells: list[str]) -> None:
    """The attempt's row, after the last row of the case page's attempt log."""
    readme = folder / "README.md"
    text = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index("\n## Attempt log\n")
    end = text.find("\n## ", start + 1)
    last = list(ATTEMPT_ROW.finditer(text, start, len(text) if end < 0 else end))[-1]
    after = text.find("\n", last.start()) + 1 or len(text)
    row = "| " + " | ".join(cell.replace("|", "/") for cell in cells) + " |\n"
    readme.write_text(text[:after] + row + text[after:], encoding="utf-8", newline="\n")


def refresh_page(folder: Path) -> None:
    """The case page's generated blocks, rewritten from the record as tools/case_pages.py would."""
    readme = folder / "README.md"
    text = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
    readme.write_text(fill(text, page_blocks(folder, text), readme), encoding="utf-8", newline="\n")


def write_studio(out: Path, checklist, model, quality) -> dict[str, Path]:
    """The checklist and the preview of this attempt's input, in run/studio/, so the attempt keeps what the studio showed."""
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    if checklist is not None:
        path = out / "checklist.json"
        path.write_text(json.dumps(checklist.as_dict(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        written["checklist"] = path
    if model is not None:
        path = out / "preview.json"
        path.write_text(json.dumps(preview_data(model, quality), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        written["preview"] = path
    return written


def run(source: str, run_by: str, machine: str | None = None, replace: bool = False, pdf: bool = True, theory: bool = True,
        progress: Progress | None = None, gate: Path | None = None) -> Outcome:
    """Every step for one coupon, from a filled-in form (.xlsx), a values file (.json) or the name of a coupon that has its specs.
    With `gate`, the run waits there once the coupon is named, before the decks and the attempt (`wait_at_gate`)."""
    progress = progress or Progress(None)
    day = date.today().isoformat()
    version = calculix()
    machine = machine or f"{platform.system()} {platform.release()}, CalculiX {version}"
    checklist = model = quality = None
    if source.lower().endswith(INPUT_SUFFIXES):
        progress.start("the setup check")
        checklist, model, quality = check_setup(source)
        progress.start("the input")
        intake = convert(source, root=paths.LOCAL, day=day, replace=replace)
        for path in intake.written:
            print(f"written    {rel(path)}")
        name = intake.designation.name
    else:
        name = source
    progress.coupon = name
    check_coupon(name)
    wait_at_gate(gate, progress)
    folder = paths.local_test(name)
    spec, twin = paths.ours(name) / f"{name}.toml", paths.ours(name) / f"{name}-nodal.toml"
    if model is None:  # a coupon run on its specs: the preview of the model as the specs stand
        loaded = load_spec(spec)
        model = build_model(loaded)
        quality = element_quality(model.mesh.xy, model.mesh.corners)
    progress.start("the decks")
    for path in (spec, twin):
        for line in regenerate(path, ccx=True):
            print(line)
    progress.start("the attempt")
    attempt, deleted = start_attempt(name, day)
    for path in deleted:
        print(f"deleted {rel(path)} (a later attempt has a run of the same kind)")
    number, out = attempt_number(attempt), attempt / "run"
    progress.attempt = attempt
    print(f"attempt folder: {rel(attempt)}")
    progress.made(**write_studio(out / STUDIO, checklist, model, quality))
    record = paths.verification(name) / f"{name}-calculix.toml"
    kind = load_spec(twin).kind
    nodes, elements = gauge_probes(kind)
    notes = f"written by fea/tools/run_coupon.py, attempt {number:02d}; {LEFT_OUT.get(kind, LEFT_OUT[None])}"
    steps = [
        ("our engine", [str(paths.FEA / "examples/build_model.py"), str(spec), "--out", str(out / "kernel"), "--drawings", "without"],
         {"kernel_summary": out / "kernel" / "summary.txt", "fields": out / "kernel" / f"{name}-fields.json",
          "explanation": out / "kernel" / f"{name}-explanation.json"}),
        ("CalculiX", [str(paths.FEA / "examples/run_calculix.py"), str(twin), "--out", str(out / "calculix")],
         {"prepomax_deck": out / "calculix" / f"{name}-nodal-ccx.inp", "prepomax_results": out / "calculix" / f"{name}-nodal-ccx.frd"}),
        ("the CalculiX record", [str(paths.FEA / "tools/record_from_dat.py"), str(twin), str(out / "calculix" / f"{name}-nodal-ccx.dat"),
                                 "--version", version, "--run-by", run_by, "--machine", machine, "--tolerance", str(TOLERANCE), "--floor", str(FLOOR),
                                 "--node-probes", *nodes, "--element-probes", *elements, "--notes", notes, "--out", str(record)],
         {"record": record}),
    ]
    what = (f"`fea/tools/run_coupon.py`, run by {run_by}: the decks, our engine on `{spec.name}`, CalculiX {version} on `{twin.name}`, "
            "the CalculiX record and the package")
    answer = [  # the result: what the studio shows once it is reported
        ("prepomax_deck", "open in PrePoMax (File, Import)", out / "calculix" / f"{name}-nodal-ccx.inp"),
        ("prepomax_results", "its results in PrePoMax (File, Open results)", out / "calculix" / f"{name}-nodal-ccx.frd"),
        ("kernel_summary", "our engine: the summary, first-ply failure included", out / "kernel" / "summary.txt"),
        ("fields", "our engine: every field and the summary, for the studio's viewer", out / "kernel" / f"{name}-fields.json"),
        ("explanation", "our engine: the explanation of the result", out / "kernel" / f"{name}-explanation.json"),
        ("record", "the CalculiX record", record),
    ] + [(key, {"checklist": "the setup check of this attempt's input", "preview": "the model the studio showed before the run"}[key], path)
         for key, path in progress.outputs.items() if key in ("checklist", "preview")]
    try:
        for step, args, made in steps:
            progress.start(step)
            script(step, args, paths.FEA)
            progress.made(**made)
        progress.start("the result")
        missing = [path for _, _, path in answer if not path.exists()]
        if missing:
            raise StepFailed(f"the result: {', '.join(rel(path) for path in missing)} not written")
        result = outcome_line(folder)
    except StepFailed as exc:
        add_row(folder, [f"{number:02d}", day, what, "--", f"stopped at {exc}", f"`ours/runs/{attempt.name}/run/`"])
        exc.coupon, exc.attempt = name, attempt
        raise
    progress.result, result_at = result, time.perf_counter()
    progress.made(**{key: path for key, _, path in answer})
    print(f"\nResult: attempt {number:02d} of {name}: {result}. The drawings and the package follow.", flush=True)
    opens, documents, delivered = documents_of(name, out, spec, pdf, theory, progress)
    evidence = f"`ours/runs/{attempt.name}/run/`; `ours/{paths.VERIFICATION}/{record.name}`" + ("" if delivered is None else f"; `{paths.DOCUMENTS}/{delivered.name}/`")
    written = ("package written" if pdf else "package written without its PDF") if documents == "written" else documents
    add_row(folder, [f"{number:02d}", day, what, result, written, evidence])
    refresh_page(folder)
    opens = [(key, label, path) for key, label, path in opens if path.exists()] + answer
    outputs = {key: path for key, _, path in opens}
    progress.made(**outputs)
    print(f"\nDone: attempt {number:02d} of {name}; its row is in {rel(folder / 'README.md')}. {result}.")
    if documents != "written":
        print(f"The documents: {documents}")
    for _, label, path in opens:
        print(f"  {label:52} {rel(path)}")
    if not record.with_suffix(".md").is_file():
        print(f"Next, by hand: the record's reading, {rel(record.with_suffix('.md'))}: what the numbers show (ADR-0031); the local tests "
              "name a record without one")
    return Outcome(name, attempt, result, outputs, documents, result_at)


def outcome_line(folder: Path) -> str:
    """The result's one line, from the CalculiX record: how many recorded values agree, and our reaction against CalculiX's."""
    rows, _ = record_summary(folder)
    reaction = [signed(r.reference, r.kernel) for r in rows if r.group == "rf" and r.name == "Grip-Top" and r.component == 1]
    return f"{sum(r.agrees for r in rows)} of {len(rows)} recorded values agree with CalculiX" + "".join(
        f"; our reaction {value} from CalculiX's" for value in reaction)


def documents_of(name: str, out: Path, spec: Path, pdf: bool, theory: bool, progress: Progress) -> tuple[list[tuple[str, str, Path]], str, Path | None]:
    """After the result (ADR-0064): our engine's drawings and the package. Returns the files to open, "written" or what is missing
    and why, and the package folder when it was built. A failure here is reported, not raised: the result already stands."""
    kernel = out / "kernel"
    opens: list[tuple[str, str, Path]] = []
    failed: list[str] = []
    progress.start("the drawings")
    try:
        script("the drawings", [str(paths.FEA / "examples/build_model.py"), str(spec), "--out", str(kernel), "--drawings", "only"], paths.FEA)
    except StepFailed as exc:
        failed.append(f"the drawings not written ({exc})")
    opens.append(("kernel_vtu", "our engine: every ply's stresses, for ParaView", kernel / f"{name}.vtu"))
    progress.made(kernel_vtu=opens[-1][2])
    progress.start("the package")
    delivered = None
    try:
        delivered = package(name, pdf, theory)
        progress.made(package=delivered)
    except StepFailed as exc:
        failed.append(f"the package not written ({exc})")
    progress.start("the outputs")
    if delivered is not None:
        opens = [("package", "the package for the team", delivered)] + (
            [("document", "its document", delivered / f"{name}.pdf")] if pdf else []) + [
            ("abaqus_deck", "open in Abaqus/CAE", delivered / "2-our-model" / "abaqus" / f"{name}-abaqus.inp")] + opens
    missing = [path for _, _, path in opens if not path.exists()]
    if missing and delivered is not None:
        hint = " (no Tectonic? run again with --no-pdf)" if delivered / f"{name}.pdf" in missing else ""
        failed.append(f"{', '.join(rel(path) for path in missing)} not written{hint}")
    return opens, "; ".join(failed) or "written", delivered


def write_result(path: Path | None, status: str, message: str, coupon: str | None = None, attempt: Path | None = None,
                 outputs: dict[str, Path] | None = None, documents: str | None = None, result: str | None = None) -> None:
    """The run's outcome as JSON, for the API's coupon jobs (ADR-0050): done, stopped or refused, and the files by key; for a done
    run, `result` is the result's one line and `documents` "written" or what is missing and why (ADR-0064)."""
    if path is None:
        return
    data = {"status": status, "message": message, "coupon": coupon, "attempt": None if attempt is None else rel(attempt),
            "outputs": {key: rel(p) for key, p in (outputs or {}).items()}, "result": result, "documents": documents, "fea_version": __version__}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # the steps print the library's units (10⁻⁶/°C), as build_model.py does
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="a filled-in coupon input form (.xlsx), a values file (.json), or the name of a coupon under .local/fea/ that has its specs")
    parser.add_argument("--run-by", required=True, help="who runs it, as the CalculiX record and the attempt log name them")
    parser.add_argument("--machine", default=None, help="the machine, as the record names it; default the operating system and the CalculiX version")
    parser.add_argument("--replace", action="store_true", help="with an input file: rewrite the two specs of a coupon that already has them")
    parser.add_argument("--no-pdf", action="store_true", help="write the package's LaTeX but not its PDF (Tectonic missing)")
    parser.add_argument("--no-theory", action="store_true", help="leave the equations and code of Chapter 2 out of the document")
    parser.add_argument("--result", type=Path, default=None, help="also write the outcome to this JSON file (the API's coupon jobs read it)")
    parser.add_argument("--progress", type=Path, default=None, help="rewrite this JSON file after every step: the stage and the files so far")
    parser.add_argument("--gate", type=Path, default=None, help="once the coupon is named, wait for this file before the attempt: 'go' goes on, other text refuses")
    args = parser.parse_args()
    progress = Progress(args.progress)
    try:
        done = run(args.source, args.run_by, args.machine, args.replace, pdf=not args.no_pdf, theory=not args.no_theory, progress=progress,
                   gate=args.gate)
    except StepFailed as exc:
        write_result(args.result, "stopped", f"stopped at {exc}", exc.coupon, exc.attempt, progress.outputs)
        sys.exit(f"run_coupon: stopped at {exc}; the step's own message is above")
    except (Refused, IntakeError, AttemptError, CasePageError, CalculixError) as exc:
        write_result(args.result, "refused", str(exc))
        sys.exit(f"run_coupon: {exc}")
    message = done.result if done.documents == "written" else f"{done.result}; {done.documents}"
    write_result(args.result, "done", message, done.coupon, done.attempt, done.outputs, done.documents, done.result)


if __name__ == "__main__":
    main()
