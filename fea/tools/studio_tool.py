"""What the API's coupon studio asks of the fea package, as one command per question (ADR-0051).

    uv run python tools/studio_tool.py check <values.json> --out <dir>     # checklist.json, and preview.json when the inputs build a model
    uv run python tools/studio_tool.py coupons                              # every coupon on this machine, as JSON on stdout
    uv run python tools/studio_tool.py values <coupon>                      # a coupon's rows, as the values JSON the studio edits
    uv run python tools/studio_tool.py live <values.json> --out <dir>       # check + our kernel, no mesh study or CalculiX: the edit-by-edit preview
    uv run python tools/studio_tool.py serve                                # `live` again and again, one JSON line per request: the API's warm worker
    uv run python tools/studio_tool.py fixtures <values.json> --out <dir>   # live + the mesh study: the files the browser tests read
    uv run python tools/studio_tool.py tow <values.json> --out <dir>        # a fibre tow record (ASTM D4018): tow.json, its checklist and result

`check` judges a values file the way `tools/run_coupon.py` will (`checks.setup_checklist`) and exits 0 whatever it finds: the
checklist says. `coupons` reads each coupon's spec and case page. `values` is the inverse of the form's reading
(`intake.values_of_spec`). `live` runs the checks and, when nothing blocks, our engine alone (ADR-0086): checklist.json, preview.json,
fields.json and explanation.json, with the answer (ADR-0085), and timings.json, each stage's seconds; no mesh study, no CalculiX, no attempt,
no document. `serve` is `live` kept warm (ADR-0086): it imports the package once, prints {"ready": true}, then reads one JSON request
per line on stdin, {"values": <path>, "out": <folder>}, and answers each with one line, {"state": ...} or {"error": ...}; anything else
it would print goes to stderr. `fixtures` is `live` and the mesh study a run adds (ADR-0068), on the public values given, so the browser
tests need neither CalculiX nor the API. --root moves the coupons'
folder (default .local/fea) for tests. `tow` reads a fibre tow record, which is no coupon (ADR-0074), and writes its checklist and,
when nothing blocks, its result (`tow_test.tow_answer`); it exits 0 whatever it finds. Nothing here computes a result: the modules named do.
"""

from __future__ import annotations

import time

_STARTED = time.perf_counter()  # the imports below are most of a live solve's start-up (ADR-0086)

import argparse
import json
import sys
import tempfile
from pathlib import Path

from anisotropy_fea import enabled, paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.case_pages import CasePageError, read_case
from anisotropy_fea.checks import ITEMS, Checklist, CheckItem, setup_checklist
from anisotropy_fea.convergence import convergence_study
from anisotropy_fea.explain import explanation
from anisotropy_fea.fields import field_data
from anisotropy_fea.intake import IntakeError, read_input, values_of_spec
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.preview import preview_data
from anisotropy_fea.spec import TEST_CODES, SpecError, layup_text, load_spec
from anisotropy_fea.test_quantities import method_inputs
from anisotropy_fea.tow_test import tow_answer
from anisotropy_fea.units import deck_units_of
from anisotropy_fea.write_abaqus import write_abaqus

IMPORT_SECONDS = time.perf_counter() - _STARTED
# The full run's own tools: CalculiX, which checks our result, and the document builder. Our kernel needs neither, so a live solve goes
# ahead without them; the checklist still says so, and the full run stays blocked until they are installed (ADR-0086).
RUN_ONLY = ("solver", "document")


def write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path


def write_compact(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return path


def serve(root: Path) -> None:
    """`live` kept warm for the API (ADR-0086): one JSON request per line on stdin, one JSON answer per line on stdout, until stdin closes.
    A request that fails is answered with its error and the worker stays; everything `live` prints goes to stderr, so stdout carries the
    answers alone."""
    answers = sys.stdout
    sys.stdout = sys.stderr
    print(json.dumps({"ready": True, "imports": IMPORT_SECONDS}), file=answers, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        started = time.perf_counter()
        try:
            request = json.loads(line)
            answer = {"state": live(Path(request["values"]), Path(request["out"]), root, started=started)}
        except Exception as exc:  # the worker outlives a bad request: the API reads the error and asks again
            answer = {"error": f"{type(exc).__name__}: {exc}".splitlines()[0]}
        print(json.dumps(answer), file=answers, flush=True)


def unreadable(path: Path, message: str) -> Checklist:
    """A checklist for a file the reader refused: every item pending but the first, which carries the reason."""
    items = tuple(CheckItem(item_id, label, "fail" if item_id == "identity" else "pending", message if item_id == "identity" else "")
                  for item_id, label in ITEMS)
    return Checklist(items, None, False, 0, "blocked", (message,))


def check(values_path: Path, out: Path, root: Path):
    try:
        form = read_input(values_path)
    except IntakeError as exc:
        checklist = unreadable(values_path, str(exc))
        write_json(out / "checklist.json", checklist.as_dict())
        print(f"blocked: {exc}")
        return
    checklist, model, quality = setup_checklist(form, root)
    write_json(out / "checklist.json", checklist.as_dict())
    if model is not None:
        write_json(out / "preview.json", preview_data(model, quality))
    counts = {state: sum(item.state == state for item in checklist.items) for state in ("pass", "warn", "fail", "missing", "pending")}
    print(f"{checklist.state}: " + ", ".join(f"{n} {state}" for state, n in counts.items() if n) + (f"; {checklist.designation}" if checklist.designation else ""))


def coupons(root: Path) -> list[dict]:
    folders = [d for d in sorted(root.iterdir()) if d.is_dir() and (d / paths.OURS / f"{d.name}.toml").is_file()] if root.is_dir() else []
    out = []
    for folder in folders:
        try:
            spec = load_spec(folder / paths.OURS / f"{folder.name}.toml")
        except (SpecError, ValueError) as exc:  # listed with why, never taking the list down with it
            out.append({"name": folder.name, "designation": folder.name, "kind": "unreadable", "test": "", "title": "", "layup": "", "status": None,
                        "accepted": None, "attempts": 0, "category": None, "problem": f"its spec no longer passes the checks: {str(exc).splitlines()[0]}"})
            continue
        entry = {"name": folder.name, "designation": spec.coupon.designation if spec.coupon else None, "kind": spec.kind, "test": TEST_CODES[spec.kind][1],
                 "title": spec.title, "layup": layup_text(spec), "status": None, "accepted": None, "attempts": 0, "category": None}
        try:
            case = read_case(folder)
            entry.update(status=case.status, accepted=case.accepted, attempts=case.attempts, category=case.category)
        except (CasePageError, OSError) as exc:
            entry["problem"] = str(exc)
        out.append(entry)
    return out


def values(name: str, root: Path) -> dict:
    spec_path = root / name / paths.OURS / f"{name}.toml"
    if not spec_path.is_file():
        raise IntakeError(f"{name}: no coupon of that name under {root} (no {paths.OURS}/{name}.toml)")
    try:
        spec = load_spec(spec_path)
    except (SpecError, ValueError) as exc:
        raise IntakeError(f"{name}: its spec no longer passes the checks, so it cannot be reopened: {str(exc).splitlines()[0]}") from None
    try:
        enabled.refuse_hidden_kind(spec.kind, name)  # a coupon of a test the studio does not offer yet stays kept, not reopened (ADR-0089)
    except enabled.NotOffered as exc:
        raise IntakeError(str(exc)) from None
    return values_of_spec(spec)


def solved(model, quality, timings: dict[str, float]) -> tuple[dict, dict]:
    """Our kernel on the model the check built: the Abaqus deck as a run writes it, read back and solved, and the fields with the answer
    (ADR-0085). The deck goes to a folder of its own that is removed after, so nothing but the JSON is left behind."""
    spec = model.spec
    clock = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="live-") as folder:
        deck_path = Path(folder) / f"{spec.coupon.designation if spec.coupon else 'coupon'}-abaqus.inp"
        deck_path.write_text(write_abaqus(model), encoding="utf-8", newline="\n")
        deck = read_deck(deck_path, deck_units_of(spec.units))  # the deck is in a deck system; the fields come back in the stated one (ADR-0061)
    timings["deck"] = time.perf_counter() - clock
    clock = time.perf_counter()
    solution = solve_deck(deck)
    timings["solve"] = time.perf_counter() - clock
    coupon = {"designation": spec.coupon.designation if spec.coupon else None, "title": spec.title, "kind": spec.kind,
              "test": TEST_CODES[spec.kind][1], "layup": layup_text(spec)}
    clock = time.perf_counter()
    data = field_data(deck, solution, spec.units, criteria=tuple(spec.output.fpf_criteria), quality=quality, coupon=coupon, method=method_inputs(spec))
    timings["fields"] = time.perf_counter() - clock
    return data, coupon


def solvable(checklist: Checklist, model) -> bool:
    """Our kernel can answer: the model builds, and nothing blocks but the full run's own tools (RUN_ONLY)."""
    return model is not None and all(item.state not in ("fail", "missing") or item.id in RUN_ONLY for item in checklist.items)


def live(values_path: Path, out: Path, root: Path, started: float | None = None) -> str:
    """The edit-by-edit preview (ADR-0086): the setup check and, when nothing blocks, our kernel's solve with its answer and explanation;
    the seconds of each stage in timings.json. Returns the checklist's state. Nothing is recorded as an attempt and no file is kept."""
    timings: dict[str, float] = {"imports": IMPORT_SECONDS} if started is None else {}  # a warm worker imported once, before
    clock = time.perf_counter()
    try:
        form = read_input(values_path)
    except IntakeError as exc:
        write_json(out / "checklist.json", unreadable(values_path, str(exc)).as_dict())
        write_json(out / "timings.json", timings)
        print(f"blocked: {exc}")
        return "blocked"
    checklist, model, quality = setup_checklist(form, root)
    timings["check"] = time.perf_counter() - clock
    write_json(out / "checklist.json", checklist.as_dict())
    if model is not None:
        write_json(out / "preview.json", preview_data(model, quality))
    if not solvable(checklist, model):
        write_json(out / "timings.json", timings)
        print(f"{checklist.state}: nothing solved")
        return checklist.state
    data, coupon = solved(model, quality, timings)
    clock = time.perf_counter()
    write_compact(out / "fields.json", data)  # the largest file by far: no indent (ADR-0086)
    write_json(out / "summary.json", data["summary"])  # what the API records of a live solve, without reading the fields again
    write_json(out / "explanation.json", explanation(data["summary"], coupon, model.spec.units, data["labels"], checklist.as_dict()))
    timings["write"] = time.perf_counter() - clock
    timings["total"] = time.perf_counter() - (_STARTED if started is None else started)
    write_json(out / "timings.json", timings)
    print(f"{checklist.state}: {checklist.designation}, solved by our kernel in {timings['solve']:.2f} s, {timings['total']:.2f} s in all")
    return checklist.state


def fixtures(values_path: Path, out: Path, root: Path) -> None:
    """`live` and the mesh study a run writes into the fields (ADR-0068): the files the browser tests read."""
    live(values_path, out, root)
    if not (out / "fields.json").is_file():
        raise IntakeError("the values do not build a model that can be solved: see checklist.json in " + str(out))
    (out / "timings.json").unlink()  # a fixture is the result, not one machine's seconds
    (out / "summary.json").unlink()  # it is inside fields.json
    _, model, _ = setup_checklist(read_input(values_path), root)
    fields_path = out / "fields.json"
    data = json.loads(fields_path.read_text(encoding="utf-8"))
    data["summary"]["convergence"] = convergence_study(model.spec)  # as a run writes it into the fields (ADR-0068)
    write_json(fields_path, data)
    print(f"written checklist.json, preview.json, fields.json, explanation.json in {out}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=paths.LOCAL, help="the folder holding one folder per coupon (default .local/fea)")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("check", help="judge a values file; write checklist.json and preview.json")
    p.add_argument("values", type=Path)
    p.add_argument("--out", type=Path, required=True)
    commands.add_parser("coupons", help="every coupon on this machine, as JSON")
    p = commands.add_parser("values", help="a coupon's rows as the values JSON")
    p.add_argument("coupon")
    p = commands.add_parser("live", help="the checks and our kernel's solve of a values file, no mesh study or CalculiX (the preview)")
    p.add_argument("values", type=Path)
    p.add_argument("--out", type=Path, required=True)
    commands.add_parser("serve", help="live, kept warm: one JSON request per line on stdin, one answer per line on stdout")
    p = commands.add_parser("fixtures", help="live and the mesh study of a values file, for the browser tests")
    p.add_argument("values", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("tow", help="a fibre tow record (ASTM D4018): write tow.json, its checklist and result")
    p.add_argument("values", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check":
            check(args.values, args.out, args.root)
        elif args.command == "coupons":
            print(json.dumps(coupons(args.root), indent=1, ensure_ascii=False))
        elif args.command == "values":
            print(json.dumps(values(args.coupon, args.root), indent=1, ensure_ascii=False))
        elif args.command == "live":
            live(args.values, args.out, args.root)
        elif args.command == "serve":
            serve(args.root)
        elif args.command == "tow":
            answer = tow_answer(args.values)
            write_json(args.out / "tow.json", answer)
            print(f"{answer['checklist']['state']}: fibre tow record" + (f", {answer['result']['counts']['valid']} valid specimens" if answer["result"] else ""))
        else:
            fixtures(args.values, args.out, args.root)
    except (IntakeError, SpecError, KernelError, CasePageError) as exc:
        sys.exit(f"studio_tool: {exc}")


if __name__ == "__main__":
    main()
