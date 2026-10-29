"""What the API's coupon studio asks of the fea package, as one command per question (ADR-0051).

    uv run python tools/studio_tool.py check <values.json> --out <dir>     # checklist.json, and preview.json when the inputs build a model
    uv run python tools/studio_tool.py coupons                              # every coupon on this machine, as JSON on stdout
    uv run python tools/studio_tool.py values <coupon>                      # a coupon's rows, as the values JSON the studio edits
    uv run python tools/studio_tool.py fixtures <values.json> --out <dir>   # check + a kernel solve: the files the browser tests read

`check` judges a values file the way `tools/run_coupon.py` will (`checks.setup_checklist`) and exits 0 whatever it finds: the
checklist says. `coupons` reads each coupon's spec and case page. `values` is the inverse of the form's reading
(`intake.values_of_spec`). `fixtures` runs the checks and our engine on the public values given and writes checklist.json,
preview.json, fields.json and explanation.json, so the browser tests need neither CalculiX nor the API. --root moves the coupons'
folder (default .local/fea) for tests. Nothing here computes a result: the modules named do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.case_pages import CasePageError, read_case
from anisotropy_fea.checks import ITEMS, Checklist, CheckItem, setup_checklist
from anisotropy_fea.explain import explanation
from anisotropy_fea.fields import field_data
from anisotropy_fea.intake import IntakeError, read_input, values_of_spec
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.preview import preview_data
from anisotropy_fea.spec import TEST_CODES, SpecError, layup_text, load_spec
from anisotropy_fea.write_abaqus import write_abaqus


def write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path


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
        spec = load_spec(folder / paths.OURS / f"{folder.name}.toml")
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
    return values_of_spec(load_spec(spec_path))


def fixtures(values_path: Path, out: Path, root: Path) -> None:
    form = read_input(values_path)
    checklist, model, quality = setup_checklist(form, root)
    write_json(out / "checklist.json", checklist.as_dict())
    if model is None:
        raise IntakeError("the values do not build a model: " + "; ".join(checklist.problems))
    write_json(out / "preview.json", preview_data(model, quality))
    spec = model.spec
    deck_text = write_abaqus(model)
    deck_path = out / f"{spec.coupon.designation if spec.coupon else 'coupon'}-abaqus.inp"
    deck_path.write_text(deck_text, encoding="utf-8", newline="\n")
    deck = read_deck(deck_path, spec.units)
    solution = solve_membrane(deck)
    coupon = {"designation": spec.coupon.designation if spec.coupon else None, "title": spec.title, "kind": spec.kind,
              "test": TEST_CODES[spec.kind][1], "layup": layup_text(spec)}
    data = field_data(deck, solution, spec.units, criteria=tuple(spec.output.fpf_criteria), quality=quality, coupon=coupon)
    write_json(out / "fields.json", data)
    write_json(out / "explanation.json", explanation(data["summary"], coupon, spec.units, data["labels"], checklist.as_dict()))
    print(f"written checklist.json, preview.json, {deck_path.name}, fields.json, explanation.json in {out}")


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
    p = commands.add_parser("fixtures", help="the checks and a kernel solve of a values file, for the browser tests")
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
        else:
            fixtures(args.values, args.out, args.root)
    except (IntakeError, SpecError, KernelError, CasePageError) as exc:
        sys.exit(f"studio_tool: {exc}")


if __name__ == "__main__":
    main()
