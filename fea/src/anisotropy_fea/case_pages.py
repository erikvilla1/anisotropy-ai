"""The generated parts of the case pages and the indexes, written from the records and specs (ADR-0039).

A case page is the README of a model folder (`models/<test>/README.md`). Its title is the coupon's name (ADR-0038), then the
case line, the problem, the result, the attempt log and where to look. Only the text between `<!-- generated: <name> -->`
and `<!-- end generated -->` is written here:

    result       in each case page: the CalculiX record against our kernel and, when the team built the coupon, the team
                 summary (`records/<coupon>-team-summary.toml`, written by docs/models/coupon.py)
    tests        in models/README.md: one row per case page
    benchmarks   in checks/README.md: one row per check record and case, and the engine's validation cases

Every number comes from a record or a team summary; none is typed. The case line and the attempt log are written by hand,
and the tests index reads them. `fea/tools/case_pages.py` writes the files; `fea/tests/test_case_pages.py` checks they are
current, as the deck test does for decks.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .cases import load_case
from .compare import load_record
from .report import ComparisonRow, comparison_rows
from .spec import coupon_card, load_spec

BLOCK = re.compile(r"(<!-- generated: (?P<name>[\w-]+) -->\n)(?P<body>.*?)(<!-- end generated -->)", re.S)
CASE_LINE = re.compile(r"^\*\*Case\.\*\* Category: (?P<category>[^|\n]+?) \| Status: (?P<status>[^|\n]+?) \| "
                       r"Accepted attempt: (?P<accepted>[^|\n]+?)$", re.M)
ATTEMPT_ROW = re.compile(r"^\| (?P<number>\d{2}) \|", re.M)
STATUSES = ("in progress", "verified", "validated")  # verified: agrees with a reference solver; validated: agrees with test data
ENGINE_CASES = paths.ROOT / "engine" / "validation" / "cases"
SOLVER_NAMES = {"calculix": "CalculiX", "abaqus": "Abaqus"}  # as the records store them, lower case


class CasePageError(ValueError):
    pass


@dataclass(frozen=True)
class Case:
    """What the hand-written part of a case page states."""

    folder: Path
    category: str
    status: str
    accepted: str
    attempts: int  # rows of the attempt log


def rel(path: Path) -> str:
    return Path(path).resolve().relative_to(paths.ROOT).as_posix()


def read_case(folder: Path) -> Case:
    """The case line and the attempt count of a model folder's README; refused by name when either is missing."""
    readme = folder / "README.md"
    text = readme.read_text(encoding="utf-8")
    match = CASE_LINE.search(text)
    if match is None:
        raise CasePageError(f"{rel(readme)}: no case line '**Case.** Category: ... | Status: ... | Accepted attempt: ...'")
    if match["status"] not in STATUSES:
        raise CasePageError(f"{rel(readme)}: status {match['status']!r} is not one of {STATUSES}")
    if "\n## Attempt log\n" not in text:
        raise CasePageError(f"{rel(readme)}: no '## Attempt log' section")
    log = text.split("\n## Attempt log\n", 1)[1].split("\n## ", 1)[0]
    attempts = ATTEMPT_ROW.findall(log)
    if not attempts:
        raise CasePageError(f"{rel(readme)}: the attempt log has no rows")
    if attempts != [f"{k:02d}" for k in range(1, len(attempts) + 1)]:
        raise CasePageError(f"{rel(readme)}: attempts must be numbered 01, 02, ... in order; found {attempts}")
    return Case(folder, match["category"].strip(), match["status"], match["accepted"].strip(), len(attempts))


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    return "\n".join(lines + ["| " + " | ".join(cell.replace("|", "/") for cell in row) + " |" for row in rows]) + "\n"


def solver_text(solver: dict) -> str:
    return f"{SOLVER_NAMES.get(solver['name'], solver['name'])} {solver['version']} {solver['element_type']}"


def signed(reference: float, ours: float) -> str:
    return f"{100 * (ours - reference) / abs(reference):+.2f} %" if reference else "--"


# --- one model's result ------------------------------------------------------------------------------------------------


def calculix_record(folder: Path) -> Path:
    return folder / "records" / f"{folder.name}-calculix.toml"


def record_rows(record_path: Path) -> tuple[list[list[str]], list[ComparisonRow], dict]:
    """The rows a CalculiX record gives the result table, its comparison rows and the record."""
    record = load_record(record_path)
    rows, problems = comparison_rows(record)
    solver, expected = record["solver"], record["expected"]
    agreeing = sum(row.agrees for row in rows)
    out = [[f"Values compared ({record_path.name})", f"{solver_text(solver)}, {len(rows)} values",
            "our kernel", f"{agreeing} of {len(rows)} within {100 * expected['tolerance']:g} % (floor {100 * expected.get('floor', 0.0):g} %)"]]
    for row in rows:
        if row.group == "rf" and row.name == "Grip-Top" and row.component == 1:
            out.append(["Reaction at Grip-Top, along the coupon", f"{row.reference:.6g} N", f"{row.kernel:.6g} N", signed(row.reference, row.kernel)])
    for row in rows:
        if row.group == "strain" and row.component == 1:
            out.append([f"Strain eps_y at element {row.name}", f"{row.reference:.5g}", f"{row.kernel:.5g}", signed(row.reference, row.kernel)])
    if problems:
        out.append(["Problems", "; ".join(problems), "", ""])
    return out, rows, record


def team_rows(summary_path: Path) -> list[list[str]]:
    """The rows a team summary gives the result table: the model item by item, then the inner band per quantity and the worst
    value over the whole free length."""
    s = tomllib.loads(summary_path.read_text(encoding="utf-8"))
    team, eq, unit = s["team"], s["equivalence"], s["units"].split("-")[0]
    out = [["The model, item by item", f"the team's {team['deck']} ({team['solver']}, {team['run_date']})", "our generated deck",
            f"{eq['same']} of {eq['items']} the same; nodes within {eq['largest_node_offset']:.3g} {unit}"]]
    for a in s["agreement"]:
        if a["band"] == "inner":
            out.append([f"{a['quantity']}, y {a['y'][0]:g} to {a['y'][1]:g} {unit}", f"the team's Abaqus, {a['values']} values", "our kernel",
                        f"{a['agree']} of {a['values']} within {100 * a['within']:g} %; largest {100 * a['largest_difference']:.2f} %"])
    free = [a for a in s["agreement"] if a["band"] == "free length"]
    if free:
        worst = max(free, key=lambda a: a["largest_difference"])
        out.append([f"Whole free length, y {worst['y'][0]:g} to {worst['y'][1]:g} {unit}", "the team's Abaqus", "our kernel",
                    f"largest {100 * worst['largest_difference']:.2f} % ({worst['quantity']}); the reading says where"])
    return out


def result_block(folder: Path) -> str:
    rows, _, _ = record_rows(calculix_record(folder))
    summary = paths.team_summary(folder)
    if summary.is_file():
        rows += team_rows(summary)
    note = ("Differences are ours minus the reference, as a share of the reference; agreement against the team is a share of the "
            "quantity's largest team value in the band. Generated by `fea/tools/case_pages.py` from `records/`.\n")
    return table(["What", "Reference", "Ours", "Agreement"], rows) + "\n" + note


# --- the indexes -------------------------------------------------------------------------------------------------------


def model_folders() -> list[Path]:
    return [d for d in sorted(paths.MODELS.iterdir()) if d.is_dir() and (d / f"{d.name}.toml").is_file()]


def tests_block() -> str:
    rows = []
    for folder in model_folders():
        case = read_case(folder)
        card = dict(coupon_card(load_spec(folder / f"{folder.name}.toml")))
        _, record, _ = record_rows(calculix_record(folder))
        reaction = [r for r in record if r.group == "rf" and r.name == "Grip-Top" and r.component == 1]
        calculix = f"{sum(r.agrees for r in record)} of {len(record)}" + (f"; reaction {signed(reaction[0].reference, reaction[0].kernel)}" if reaction else "")
        summary = paths.team_summary(folder)
        if summary.is_file():
            s = tomllib.loads(summary.read_text(encoding="utf-8"))
            inner = [a for a in s["agreement"] if a["band"] == "inner"]
            team = (f"{s['equivalence']['same']} of {s['equivalence']['items']} items the same; inner band within "
                    f"{100 * max(a['largest_difference'] for a in inner):.2f} %")
        else:
            team = card["Team's model"]
        rows.append([f"**{card['Coupon']}**", card["Test"], f"[{folder.name}]({folder.name}/README.md)", case.status,
                     f"{case.attempts} (accepted {case.accepted})", calculix, team, card["Test data"].split(":")[0]])
    return table(["Coupon", "Test", "Folder", "Status", "Attempts", "CalculiX against our kernel", "The team's Abaqus against our kernel",
                  "Test data"], rows)


def benchmarks_block() -> str:
    rows = []
    for record_path in paths.all_records():
        if paths.CHECKS not in record_path.parents:
            continue
        _, record, raw = record_rows(record_path)
        reaction = [r for r in record if r.group == "rf" and r.name == "Grip-Top" and r.component == 1]
        solver = raw["solver"]
        rows.append([f"`{record_path.parent.parent.name}/records/{record_path.stem}`", raw["title"].rsplit(": ", 1)[0],
                     solver_text(solver),
                     f"{sum(r.agrees for r in record)} of {len(record)} agree" + (f"; reaction {signed(reaction[0].reference, reaction[0].kernel)}" if reaction else "")])
    for case_path in sorted(p for p in paths.CASES.glob("*.toml") if not p.name.startswith("_")):
        case = load_case(case_path)
        reference = ("the engine's laminate theory, recomputed live" if "engine-equality" in case_path.stem
                     else "a closed form, by hand; the source is in the case")
        rows.append([f"`cases/{case_path.stem}`", case["title"], reference, "checked by `tests/test_fe_validation_cases.py`"])
    engine = sorted(p for p in ENGINE_CASES.glob("*.toml") if not p.name.startswith("_"))
    rows.append(["`engine/validation/cases/`", f"{len(engine)} laminate-theory cases: textbook, course and constructed problems", "each case's source",
                 "checked by the engine's tests"])
    return table(["Benchmark", "What", "Reference", "Result"], rows)


# --- files -------------------------------------------------------------------------------------------------------------


def fill(text: str, blocks: dict[str, str], where: Path) -> str:
    """The text with each named block replaced; every block in `blocks` must be present exactly once."""
    found = [m["name"] for m in BLOCK.finditer(text)]
    for name in blocks:
        if found.count(name) != 1:
            raise CasePageError(f"{rel(where)}: needs one '<!-- generated: {name} -->' ... '<!-- end generated -->' block, found {found.count(name)}")
    return BLOCK.sub(lambda m: m.group(1) + blocks[m["name"]] + m.group(4) if m["name"] in blocks else m.group(0), text)


def pages() -> dict[Path, str]:
    """Every file this module writes, with the text it should hold today."""
    out = {}
    for folder in model_folders():
        readme = folder / "README.md"
        out[readme] = fill(readme.read_text(encoding="utf-8"), {"result": result_block(folder)}, readme)
    index = paths.MODELS / "README.md"
    out[index] = fill(index.read_text(encoding="utf-8"), {"tests": tests_block()}, index)
    checks = paths.CHECKS / "README.md"
    out[checks] = fill(checks.read_text(encoding="utf-8"), {"benchmarks": benchmarks_block()}, checks)
    return out


# --- the local index (git-ignored) -------------------------------------------------------------------------------------

LOCAL_INDEX = paths.ROOT / ".local" / "INDEX.md"
HOMEWORK_README = paths.ROOT / ".local" / "homework" / "README.md"
PROJECTS = paths.ROOT / ".local" / "projects"
HOMEWORK_ROW = re.compile(r"^\| (?P<hw>HW\d+|PRACTICE|course-reader) \| [^|]* \| [^|]* \| (?P<status>[^|]*?) \|$", re.M)


def local_index() -> str:
    """`.local/INDEX.md`: one row per case in the four categories, with what only this machine has (the runs kept, homework,
    projects). Written by `fea/tools/case_pages.py --local`; never committed."""
    from .attempts import attempt_number, attempts, kinds  # the attempt folders live on this machine only

    tests = []
    for folder in model_folders():
        case = read_case(folder)
        card = dict(coupon_card(load_spec(folder / f"{folder.name}.toml")))
        _, record, _ = record_rows(calculix_record(folder))
        held = "; ".join(f"{attempt_number(a):02d}: {', '.join(kinds(a))}" for a in attempts(folder.name) if kinds(a)) or "none on this machine"
        tests.append([f"**{card['Coupon']}**", card["Test"], f"`fea/models/{folder.name}/`", case.status, f"{case.attempts} (accepted {case.accepted})",
                      held, f"CalculiX {sum(r.agrees for r in record)} of {len(record)}", card["Test data"].split(":")[0]])
    homework = []
    if HOMEWORK_README.is_file():
        for m in HOMEWORK_ROW.finditer(HOMEWORK_README.read_text(encoding="utf-8")):
            prefix = f"se142-{m['hw'].lower()}-" if m["hw"].startswith("HW") else f"{m['hw']}-"
            cases = sorted(ENGINE_CASES.glob(f"{prefix}*.toml"))
            folder = HOMEWORK_README.parent / m["hw"]
            document = folder / "documents" / f"{m['hw']}.pdf"
            homework.append([m["hw"], m["status"], str(len(cases)), f"`.local/homework/{m['hw']}/ours/`" if (folder / "ours").is_dir() else "none",
                             f"`.local/homework/{m['hw']}/documents/{m['hw']}.pdf`" if document.is_file() else "not built"])
    projects = sorted(d for d in PROJECTS.iterdir() if d.is_dir()) if PROJECTS.is_dir() else []
    parts = [
        "# Every case, on this machine",
        "",
        "Written by `fea/tools/case_pages.py --local` (ADR-0039); git-ignored, because homework and projects are private. The committed "
        "indexes are `fea/models/README.md` (team tests) and `fea/checks/README.md` (benchmarks). A case's page is its README.",
        "",
        "## Team tests",
        "",
        table(["Coupon", "Test", "Case page", "Status", "Attempts in the log", "Runs kept (attempt: kinds)", "Result", "Test data"], tests),
        "## Benchmarks",
        "",
        benchmarks_block(),
        "## Homework",
        "",
        table(["Set", "Status (from homework/README.md)", "Engine cases", "Ours", "Document"], homework) if homework else "No homework folder on this machine.\n",
        "## Projects",
        "",
        table(["Project", "Folder"], [[d.name, f"`.local/projects/{d.name}/`"] for d in projects]) if projects
        else "None yet. A customer or research problem gets `.local/projects/<case>/` with a README written as a case page.\n",
    ]
    return "\n".join(parts)
