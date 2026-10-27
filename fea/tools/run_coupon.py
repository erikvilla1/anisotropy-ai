"""Take a coupon from its input form, or from its folder, to its package with one command (ADR-0049).

    uv run python tools/run_coupon.py <filled form>.xlsx --run-by "Erik Villa"   # a new coupon: its form is read first
    uv run python tools/run_coupon.py <coupon> --run-by "Erik Villa"             # a coupon that has its specs, after an edit

Runs the steps of the case page's Rebuild section in order, with its placeholders filled: reads the form (as coupon_from_form.py),
writes the decks (as regenerate_decks.py --ccx), starts the next attempt (as new_attempt.py), solves the coupon with our engine
(build_model.py), runs the CalculiX twin (run_calculix.py), writes the CalculiX record (record_from_dat.py) and builds the package
(as docs/models/coupon.py). Then it adds the attempt's row to the case page's attempt log, a failed try included, refreshes the
page's result and lists the files to open. It stops at the first step that fails and names it. Nothing is written before CalculiX
is found (ANISOTROPY_CCX or ccx on PATH) and the coupon's case page reads.

Options: --machine (default: the operating system and the CalculiX version found), --replace (with a form: rewrite the specs of a
coupon that has them), --no-pdf (the package without its PDF, where Tectonic is missing), --no-theory.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from anisotropy_fea import __version__, paths
from anisotropy_fea.attempts import AttemptError, attempt_number, attempts, start_attempt
from anisotropy_fea.calculix import CalculixError, ccx_version, find_ccx
from anisotropy_fea.case_pages import ATTEMPT_ROW, CasePageError, fill, page_blocks, read_case, record_summary, rel, signed
from anisotropy_fea.intake import IntakeError, convert, gauge_probes
from anisotropy_fea.spec import load_spec

from regenerate_decks import regenerate  # noqa: E402  (tools share a folder)

TOLERANCE, FLOOR = 0.03, 0.02  # the CalculiX record's, as the case page's Rebuild section gives them (intake.next_commands)
LEFT_OUT = {  # why the record keeps the gauge probes only, in the words the coupons' records use
    "open_hole_tension": "gauge node and far element only: beside the hole the bilinear kernel element and S8R differ in the small components",
    None: "centre probe only: the near-grip element was left out because the two element types differ most beside a tab line, in the small components",
}
COUPON_DOCUMENT = "anisotropy_models_coupon"  # docs/models/coupon.py, loaded under the name its tests use


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


def script(step: str, args: list[str], cwd: Path) -> None:
    """One of our scripts under this Python, its output straight to the console; a nonzero exit stops the run at `step`."""
    print(f"\n== {step}", flush=True)
    done = subprocess.run([sys.executable, *args], cwd=cwd, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False)
    if done.returncode:
        raise StepFailed(f"{step}: {Path(args[0]).name} exited with code {done.returncode}")


def package(name: str, pdf: bool, theory: bool) -> Path:
    """The coupon's document and package, built in this process so that they read the coupon where this run wrote it; returns the
    package folder, which docs/models/coupon.py names by the day it is built."""
    print("\n== the package", flush=True)
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


def run(source: str, run_by: str, machine: str | None = None, replace: bool = False, pdf: bool = True, theory: bool = True) -> Outcome:
    """Every step for one coupon, from a filled-in form (.xlsx) or the name of a coupon that has its specs."""
    day = date.today().isoformat()
    version = calculix()
    machine = machine or f"{platform.system()} {platform.release()}, CalculiX {version}"
    if source.lower().endswith(".xlsx"):
        print("== the input form", flush=True)
        intake = convert(source, root=paths.LOCAL, day=day, replace=replace)
        for path in intake.written:
            print(f"written    {rel(path)}")
        name = intake.designation.name
    else:
        name = source
    check_coupon(name)
    folder = paths.local_test(name)
    spec, twin = paths.ours(name) / f"{name}.toml", paths.ours(name) / f"{name}-nodal.toml"
    print("\n== the decks", flush=True)
    for path in (spec, twin):
        for line in regenerate(path, ccx=True):
            print(line)
    attempt, deleted = start_attempt(name, day)
    for path in deleted:
        print(f"deleted {rel(path)} (a later attempt has a run of the same kind)")
    number, out = attempt_number(attempt), attempt / "run"
    print(f"attempt folder: {rel(attempt)}")
    record = paths.verification(name) / f"{name}-calculix.toml"
    kind = load_spec(twin).kind
    nodes, elements = gauge_probes(kind)
    notes = f"written by fea/tools/run_coupon.py, attempt {number:02d}; {LEFT_OUT.get(kind, LEFT_OUT[None])}"
    steps = [
        ("our engine", [str(paths.FEA / "examples/build_model.py"), str(spec), "--out", str(out / "kernel")]),
        ("CalculiX", [str(paths.FEA / "examples/run_calculix.py"), str(twin), "--out", str(out / "calculix")]),
        ("the CalculiX record", [str(paths.FEA / "tools/record_from_dat.py"), str(twin), str(out / "calculix" / f"{name}-nodal-ccx.dat"),
                                 "--version", version, "--run-by", run_by, "--machine", machine, "--tolerance", str(TOLERANCE), "--floor", str(FLOOR),
                                 "--node-probes", *nodes, "--element-probes", *elements, "--notes", notes, "--out", str(record)]),
    ]
    what = (f"`fea/tools/run_coupon.py`, run by {run_by}: the decks, our engine on `{spec.name}`, CalculiX {version} on `{twin.name}`, "
            "the CalculiX record and the package")
    try:
        for step, args in steps:
            script(step, args, paths.FEA)
        delivered = package(name, pdf, theory)
        opens = [("package", "the package for the team", delivered)] + (
            [("document", "its document", delivered / f"{name}.pdf")] if pdf else []) + [
            ("abaqus_deck", "open in Abaqus/CAE", delivered / "2-our-model" / "abaqus" / f"{name}-abaqus.inp"),
            ("prepomax_deck", "open in PrePoMax (File, Import)", out / "calculix" / f"{name}-nodal-ccx.inp"),
            ("prepomax_results", "its results in PrePoMax (File, Open results)", out / "calculix" / f"{name}-nodal-ccx.frd"),
            ("kernel_summary", "our engine: the summary, first-ply failure included", out / "kernel" / "summary.txt"),
            ("kernel_vtu", "our engine: every ply's stresses, for ParaView", out / "kernel" / f"{name}.vtu"),
            ("record", "the CalculiX record", record),
        ]
        missing = [path for _, _, path in opens if not path.exists()]
        if missing:
            hint = " (no Tectonic? run again with --no-pdf)" if delivered / f"{name}.pdf" in missing else ""
            raise StepFailed(f"the outputs: {', '.join(rel(path) for path in missing)} not written{hint}")
    except StepFailed as exc:
        add_row(folder, [f"{number:02d}", day, what, "--", f"stopped at {exc}", f"`ours/runs/{attempt.name}/run/`"])
        exc.coupon, exc.attempt = name, attempt
        raise
    rows, _ = record_summary(folder)
    reaction = [signed(r.reference, r.kernel) for r in rows if r.group == "rf" and r.name == "Grip-Top" and r.component == 1]
    result = f"{sum(r.agrees for r in rows)} of {len(rows)} recorded values agree with CalculiX" + "".join(
        f"; our reaction {value} from CalculiX's" for value in reaction)
    evidence = f"`ours/runs/{attempt.name}/run/`; `ours/{paths.VERIFICATION}/{record.name}`; `{paths.DOCUMENTS}/{delivered.name}/`"
    add_row(folder, [f"{number:02d}", day, what, result, "package written" if pdf else "package written without its PDF", evidence])
    refresh_page(folder)
    print(f"\nDone: attempt {number:02d} of {name}; its row is in {rel(folder / 'README.md')}. {result}.")
    for _, label, path in opens:
        print(f"  {label:52} {rel(path)}")
    if not record.with_suffix(".md").is_file():
        print(f"Next, by hand: the record's reading, {rel(record.with_suffix('.md'))}: what the numbers show (ADR-0031); the local tests "
              "name a record without one")
    return Outcome(name, attempt, result, {key: path for key, _, path in opens})


def write_result(path: Path | None, status: str, message: str, coupon: str | None = None, attempt: Path | None = None,
                 outputs: dict[str, Path] | None = None) -> None:
    """The run's outcome as JSON, for the API's coupon jobs (ADR-0050): done, stopped or refused, and the files by key."""
    if path is None:
        return
    data = {"status": status, "message": message, "coupon": coupon, "attempt": None if attempt is None else rel(attempt),
            "outputs": {key: rel(p) for key, p in (outputs or {}).items()}, "fea_version": __version__}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # the steps print the library's units (10⁻⁶/°C), as build_model.py does
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="a filled-in coupon input form (.xlsx), or the name of a coupon under .local/fea/ that has its specs")
    parser.add_argument("--run-by", required=True, help="who runs it, as the CalculiX record and the attempt log name them")
    parser.add_argument("--machine", default=None, help="the machine, as the record names it; default the operating system and the CalculiX version")
    parser.add_argument("--replace", action="store_true", help="with a form: rewrite the two specs of a coupon that already has them")
    parser.add_argument("--no-pdf", action="store_true", help="write the package's LaTeX but not its PDF (Tectonic missing)")
    parser.add_argument("--no-theory", action="store_true", help="leave the equations and code of Chapter 2 out of the document")
    parser.add_argument("--result", type=Path, default=None, help="also write the outcome to this JSON file (the API's coupon jobs read it)")
    args = parser.parse_args()
    try:
        done = run(args.source, args.run_by, args.machine, args.replace, pdf=not args.no_pdf, theory=not args.no_theory)
    except StepFailed as exc:
        write_result(args.result, "stopped", f"stopped at {exc}", exc.coupon, exc.attempt)
        sys.exit(f"run_coupon: stopped at {exc}; the step's own message is above")
    except (Refused, IntakeError, AttemptError, CasePageError, CalculixError) as exc:
        write_result(args.result, "refused", str(exc))
        sys.exit(f"run_coupon: {exc}")
    write_result(args.result, "done", done.result, done.coupon, done.attempt, done.outputs)


if __name__ == "__main__":
    main()
