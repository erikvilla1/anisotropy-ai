"""The coupon audit (ADR-0043): the committed rubric reads, agrees with the tools it names, and a malformed one is refused; a
package is scored from what our tools found; the audit form locks our results and opens the auditor's cells."""

import dataclasses
import re
from datetime import datetime

import pytest
from openpyxl import load_workbook

from anisotropy_fea import case_pages, paths  # where the files live (ADR-0036)
from anisotropy_fea.abaqus_reader import parse_deck, read_deck
from anisotropy_fea.abaqus_report import read_field_report
from anisotropy_fea.audit import (AUTO, AUDITOR_FIELDS, COVER, EQUIVALENCE_GROUPS, FINDING_ROWS, FINDINGS, LISTED_ONLY, NOT_BUILT_BY_TEAM, RUBRIC_COLUMNS,
                                  RUBRIC_SHEET, AuditError, Evidence, Finding, Row, RubricError, items_for, load_rubric, parse_rubric, read_form, score,
                                  verdict_of, write_form)
from anisotropy_fea.equivalence import RELATIVE, deck_equivalence
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.model import to_si
from anisotropy_fea.side_by_side import pair_reports

from test_equivalence import FIXTURE_SPEC, GRIPS_FIXTURE, generated
from test_side_by_side import kernel_reports

UNITS = "mm-MPa"
CARD = (("Coupon", "IM7-UNT-L9"), ("Test", "unnotched tension"), ("Standard", "none"), ("Size from", "the grips fixture"),
        ("Team model", "the grips fixture deck"), ("Test data", "none"), ("Material", "IM7/8552"), ("Layup", "[0/30/-30/30/0]s"), ("Size", "25 x 100 mm"))

SMALL = """
version = "0.1"
status = "draft"

[[section]]
id = "A"
title = "Identity"

[[section]]
id = "B"
title = "Model match"

[[item]]
id = "A1"
section = "A"
check = "The coupon card is complete"
acceptance = "No field is blank"
method = "auto"
required = true
source = ["spec.coupon_card"]

[[item]]
id = "B1"
section = "B"
check = "Geometry"
acceptance = "Nodes match"
method = "auto"
required = true
tolerance = { length_m = 1e-8 }
applies_to = ["UNT", "OHT"]
"""


def test_the_committed_rubric_reads():
    rubric = load_rubric(paths.RUBRIC)
    assert [s.id for s in rubric.sections] == ["A", "B", "C", "D", "E"]
    assert len({item.id for item in rubric.items}) == len(rubric.items)
    assert rubric.status == "draft", "the rubric stays a draft until the cofounder confirms it (ADR-0043)"


def test_model_match_uses_the_equivalence_tolerance():
    """B4, B5 and B8 state the tolerance deck_equivalence applies; the two must not drift apart."""
    items = {item.id: item for item in load_rubric().items}
    for item_id in ("B4", "B5", "B8"):
        assert items[item_id].tolerance.relative == RELATIVE, item_id
    assert all(items[f"B{n}"].source == ("equivalence.deck_equivalence",) for n in (1, 2, 3, 4, 5, 7, 8, 9))


def test_an_auditor_item_has_no_tolerance_and_an_unbuilt_check_is_not_required():
    for item in load_rubric().items:
        if item.method == "auditor":
            assert item.tolerance is None, f"{item.id}: the auditor judges it; a tolerance belongs to a computed check"
        if item.method == "auto" and not item.source:
            assert not item.required, f"{item.id}: no function computes it yet, so a Pass verdict cannot need it"


def test_items_follow_the_test():
    rubric = load_rubric()
    unt = {item.id for item in items_for(rubric, "UNT")}
    oht = {item.id for item in items_for(rubric, "OHT")}
    assert "D1" in unt and "D3" not in unt
    assert "D3" in oht and "D4" in oht and "D1" not in oht
    assert {"A1", "B1", "C2", "E4"} <= unt & oht
    with pytest.raises(RubricError, match="not in spec.TEST_CODES"):
        items_for(rubric, "XYZ")


def test_a_small_rubric_reads():
    rubric = parse_rubric(SMALL)
    assert [item.id for item in rubric.items] == ["A1", "B1"]
    assert rubric.items[1].tolerance.length_m == 1e-8
    assert [item.id for item in items_for(rubric, "UNC")] == ["A1"]


@pytest.mark.parametrize("old, new, message", [
    ('id = "B1"', 'id = "B2"', "expected B1"),
    ('id = "B1"\nsection = "B"', 'id = "A2"\nsection = "B"', "its id names A"),
    ('id = "B1"\nsection = "B"', 'id = "C1"\nsection = "C"', "is not one of"),
    ('id = "B"\ntitle', 'id = "A"\ntitle', "used twice"),
    ('method = "auto"\nrequired = true\nsource', 'method = "machine"\nrequired = true\nsource', "method"),
    ("tolerance = { length_m = 1e-8 }", "tolerance = { length_m = 1e-8, relative = 0.01 }", "exactly one"),
    ("tolerance = { length_m = 1e-8 }", "tolerance = { length_m = -1e-8 }", "greater than 0"),
    ('applies_to = ["UNT", "OHT"]', 'applies_to = ["UNT", "XYZ"]', "not in spec.TEST_CODES"),
    ('source = ["spec.coupon_card"]', 'source = ["spec.no_such_function"]', "is not a function of anisotropy_fea"),
    ('source = ["spec.coupon_card"]', 'source = ["coupon_card"]', "is not a function of anisotropy_fea"),
    ('source = ["spec.coupon_card"]', 'source = ["spec.CouponSpec.no_such_method"]', "is not a function of anisotropy_fea"),
    ('source = ["spec.coupon_card"]', 'source = ["spec.TEST_CODES"]', "is not a function of anisotropy_fea"),
    ('status = "draft"', 'status = "approved"', "status"),
    ('check = "Geometry"', 'check = "Geometry"\nowner = "team"', "Extra inputs"),
    ('acceptance = "Nodes match"\n', "", "acceptance"),
])
def test_a_malformed_rubric_is_refused(old, new, message):
    assert SMALL.count(old) == 1, old
    with pytest.raises(RubricError, match=message):
        parse_rubric(SMALL.replace(old, new), "small rubric")


def test_a_section_without_items_is_refused():
    with pytest.raises(RubricError, match=r"sections \['C'\] have no items"):
        parse_rubric(SMALL + '\n[[section]]\nid = "C"\ntitle = "Results"\n')


# --------------------------------------------------------------------------------------------- scoring a package

@pytest.fixture(scope="module")
def grips(tmp_path_factory):
    """The grips fixture as the team's deck, our generated deck of it, and the team's field reports made by our kernel."""
    folder = tmp_path_factory.mktemp("team")
    team = read_deck(GRIPS_FIXTURE, units=UNITS)
    ours = to_si(parse_deck(generated(FIXTURE_SPEC)), UNITS)
    equivalence = deck_equivalence(team, ours, 1e-8, UNITS)
    solution = solve_membrane(ours)
    reports = [read_field_report(path) for path in kernel_reports(GRIPS_FIXTURE, folder)]
    paired = tuple(pair_reports(reports, team, solution, equivalence, UNITS))
    return Evidence(test_code="UNT", units=UNITS, card=CARD, engine_commit="abc1234", attempt="3", our_deck=ours, solution=solution,
                    material="explicit constants", team_deck=team, team_deck_sha256="0" * 64, equivalence=equivalence, paired=paired,
                    inner_band=(10.0, 90.0), free_band=(0.0, 100.0), excluded="10 mm beside each grip line", fpf=("max_stress", 0.5, 1))


def results(evidence: Evidence) -> dict[str, str | None]:
    return {s.item.id: s.result for s in score(load_rubric(), evidence)}


def test_the_same_model_with_the_same_stresses_scores_pass_where_our_tools_judge(grips):
    found = results(grips)
    assert [item_id for item_id, result in found.items() if result == "Pass"] == ["A1", "A2", "A3", "B1", "B2", "B3", "B4", "B5", "B7", "B8", "B9",
                                                                                     "C2", "C3", "D2"]
    assert {item_id for item_id, result in found.items() if result is None} == {"B6", "C5", "C6", "D5", "E1", "E3", "E4"}  # the auditor's
    assert {found[i] for i in ("C1", "C4", "C7", "E2")} == {"Not checked"}  # the team exports none of these; no deck rebuilt from the guide
    assert "D3" not in found and "D4" not in found  # open-hole only


def test_the_scores_say_why(grips):
    by_id = {s.item.id: s for s in score(load_rubric(), grips)}
    assert "Not reported: S12" in by_id["C2"].evidence and "within 1 %" in by_id["C2"].evidence
    assert "unbalanced (2 plies at +30, 1 at -30)" not in by_id["B3"].evidence  # the full laminate counts both halves
    assert "unbalanced (4 plies at +30, 2 at -30), symmetric" in by_id["B3"].evidence
    assert "max stress at 0.5 of the applied loading, ply 1" in by_id["C7"].evidence


def test_a_stress_beyond_the_tolerance_fails(grips):
    worst = next(p for p in grips.paired if p.quantity == "S22" and 10.0 <= p.y <= 90.0)
    changed = tuple(dataclasses.replace(p, reference=p.reference * 0.95) if p is worst else p for p in grips.paired)
    found = results(dataclasses.replace(grips, paired=changed))
    assert found["C2"] == "Fail" and found["C3"] == "Pass"


def test_a_coupon_the_team_has_not_built_cannot_be_checked_against_their_model(grips):
    alone = dataclasses.replace(grips, team_deck=None, team_deck_sha256=None, equivalence=None, paired=(), inner_band=None, excluded=None)
    by_id = {s.item.id: s for s in score(load_rubric(), alone)}
    assert all(by_id[f"B{n}"].result == "Not checked" for n in (1, 2, 3, 4, 5, 7, 8, 9))
    assert by_id["C2"].result == "Not checked" and by_id["C2"].evidence == NOT_BUILT_BY_TEAM
    assert by_id["A2"].result == "Pass" and by_id["D2"].result == "Pass"


def test_a_build_from_uncommitted_changes_or_without_an_attempt_cannot_be_traced(grips):
    assert results(dataclasses.replace(grips, engine_commit="abc1234 + local changes"))["A2"] == "Fail"
    assert results(dataclasses.replace(grips, attempt=None))["A2"] == "Fail"
    assert results(dataclasses.replace(grips, card=CARD[:-1] + (("Size", " "),)))["A1"] == "Fail"


def test_every_item_our_tools_judge_has_a_scorer_and_every_equivalence_item_has_a_place(grips):
    assert {item.id for item in load_rubric().items if item.method == "auto"} == set(AUTO)
    for item in grips.equivalence.items:
        homes = [item_id for item_id, pattern in EQUIVALENCE_GROUPS.items() if re.fullmatch(pattern, item.item)]
        assert len(homes) + (item.item in LISTED_ONLY) == 1, item.item


# --------------------------------------------------------------------------------------------- the audit form

def test_the_form_locks_our_results_and_opens_the_auditors_cells(grips, tmp_path):
    rubric = load_rubric()
    scored = score(rubric, grips)
    path = write_form(tmp_path / "audit.xlsx", rubric, scored, [("Coupon", "IM7-UNT-L9"), ("Attempt", "3")], UNITS)
    book = load_workbook(path)
    assert book.sheetnames == [COVER, RUBRIC_SHEET, FINDINGS]
    cover = book[COVER]
    labels = {cover.cell(r, 1).value: r for r in range(1, cover.max_row + 1)}
    assert cover.cell(labels["Attempt"], 2).value == "3" and cover.cell(labels["Rubric"], 2).value == "version 0.1 (draft)"
    assert all(not cover.cell(labels[field], 2).protection.locked for field in AUDITOR_FIELDS) and cover.protection.sheet
    sheet = book[RUBRIC_SHEET]
    assert [c.value for c in sheet[1]] == list(RUBRIC_COLUMNS)
    result = RUBRIC_COLUMNS.index("Result") + 1
    rows = {sheet.cell(r, 1).value: r for r in range(2, sheet.max_row + 1)}
    assert list(rows) == [s.item.id for s in scored]
    for s in scored:
        cell = sheet.cell(rows[s.item.id], result)
        if s.result is None:
            assert cell.value is None and not cell.protection.locked, s.item.id
        else:
            assert cell.value == s.result and cell.protection.locked, s.item.id
    lists = {v.formula1 for v in sheet.data_validations.dataValidation}
    assert lists == {'"Pass,Fail,N/A,Not checked"'}
    findings = book[FINDINGS]
    assert findings.max_row == FINDING_ROWS + 1 and findings.cell(2, 1).value == "F1" and not findings.cell(2, 5).protection.locked
    assert '"Blocker,Major,Minor,Observation"' in {v.formula1 for v in findings.data_validations.dataValidation}


# --------------------------------------------------------------------------------------------- a returned form

def filled(folder, evidence, results=None, verdict="Pass", findings=(), refs=None, changed=None, when="2026-10-24", auditor="A. Engineer"):
    """The form of the grips package as an auditor returns it. D1 is set to Pass so that a clean form can pass: on this coarse
    2 by 8 mesh the centre element is about 3 % from laminate theory, which the 0.5 % proposal fails."""
    rubric = load_rubric()
    scored = tuple(dataclasses.replace(s, result="Pass") if s.item.id == "D1" else s for s in score(rubric, evidence))
    path = write_form(folder / "audit.xlsx", rubric, scored, [("Coupon", "IM7-UNT-L9"), ("Attempt", "3")], UNITS)
    book = load_workbook(path)
    sheet = book[RUBRIC_SHEET]
    rows = {sheet.cell(r, 1).value: r for r in range(2, sheet.max_row + 1)}
    column = {name: RUBRIC_COLUMNS.index(name) + 1 for name in RUBRIC_COLUMNS}
    for s in scored:
        if s.result is None:
            sheet.cell(rows[s.item.id], column["Result"]).value = (results or {}).get(s.item.id, "Pass")
    for item_id, value in (changed or {}).items():
        sheet.cell(rows[item_id], column["Result"]).value = value
    for item_id, value in (refs or {}).items():
        sheet.cell(rows[item_id], column["Findings"]).value = value
    cover = book[COVER]
    labels = {cover.cell(r, 1).value: r for r in range(1, cover.max_row + 1)}
    for label, value in (("Auditor", auditor), ("Audit date", when), ("Verdict", verdict)):
        cover.cell(labels[label], 2).value = value
    for n, finding in enumerate(findings, start=2):
        for k, value in enumerate(finding, start=2):
            book[FINDINGS].cell(n, k).value = value
    book.save(path)
    return path


def test_a_clean_form_reads_back(grips, tmp_path):
    form = read_form(filled(tmp_path, grips, when=datetime(2026, 10, 24, 9, 30)))
    assert form.verdict == "Pass" and form.auditor == "A. Engineer" and form.date == "2026-10-24" and form.counts() == "none open"
    assert form.cover["Attempt"] == "3" and {r.id: r.result for r in form.rows}["B6"] == "Pass"


def test_the_verdict_follows_the_rule(grips, tmp_path):
    minor = ("B3", "Minor", "documentation", "the layup table omits the ply thickness", "us", "Open")
    major = ("C2", "Major", "engine", "S22 differs at the hole", "us", "Open")
    closed = ("B3", "Major", "our input", "a wrong angle, fixed in attempt 4", "us", "Closed")
    form = read_form(filled(tmp_path, grips, verdict="Pass with observations", findings=[minor, closed], refs={"B3": "F1, F2"}))
    assert form.verdict == "Pass with observations" and form.counts() == "1 open (1 Minor), 1 closed"
    assert read_form(filled(tmp_path, grips, verdict="Fail", findings=[major])).verdict == "Fail"
    assert read_form(filled(tmp_path, grips, verdict="Fail", results={"B6": "Fail"})).verdict == "Fail"  # a required row fails


def test_the_rule_on_its_own():
    row = lambda item, required, result: Row(item, "auditor", required, result, "", ())  # noqa: E731
    finding = lambda severity, status="Open": Finding("F1", "A1", severity, "engine", "x", "", status)  # noqa: E731
    assert verdict_of((row("A1", True, "Pass"), row("C1", False, "Not checked")), ()) == "Pass"  # an optional row may stay unchecked
    assert verdict_of((row("A1", True, "Pass"), row("E2", False, "Fail")), ()) == "Pass with observations"  # an optional row fails
    assert verdict_of((row("A1", True, "N/A"),), (finding("Observation"),)) == "Pass with observations"
    assert verdict_of((row("A1", True, "Pass"),), (finding("Blocker"),)) == "Fail"
    assert verdict_of((row("A1", True, "Pass"),), (finding("Blocker", "Closed"),)) == "Pass"
    with pytest.raises(AuditError, match="required rows A1"):
        verdict_of((row("A1", True, "Not checked"),), ())


@pytest.mark.parametrize("kwargs, message", [
    (dict(verdict="Pass", findings=[("B3", "Minor", "documentation", "a missing table", "us", "Open")]), "the rule gives 'Pass with observations'"),
    (dict(changed={"C2": "Fail"}), "a result our tools gave was changed"),
    (dict(results={"B6": ""}), "row B6 has no result"),
    (dict(results={"B6": "Not checked"}), "required rows B6 have no result other than Not checked"),
    (dict(findings=[("B3", "Huge", "documentation", "x", "us", "Open")], refs={"C3": "F9"}),
     "finding F1: the severity 'Huge' is not one of"),
    (dict(refs={"C3": "F9"}), "row C3 names finding F9"),
    (dict(auditor=""), "the cover's Auditor is empty"),
    (dict(when="last Tuesday"), "is not a date"),
    (dict(verdict="Approved"), "the verdict 'Approved' is not one of"),
])
def test_an_incomplete_or_inconsistent_form_is_refused_by_name(grips, tmp_path, kwargs, message):
    with pytest.raises(AuditError, match=re.escape(message)):
        read_form(filled(tmp_path, grips, **kwargs))


def test_a_file_that_is_not_a_form_is_refused(tmp_path):
    (tmp_path / "notes.xlsx").write_text("not a workbook", encoding="utf-8")
    with pytest.raises(AuditError, match="not an audit form"):
        read_form(tmp_path / "notes.xlsx")


# --------------------------------------------------------------------------------------------- filing a returned form

CASE_PAGE = """# IM7-UNT-L9, unnotched tension

**Case.** Category: team test | Status: in progress | Accepted attempt: 03

<!-- generated: result -->
<!-- end generated -->

## Attempt log

| NN | Date | Tried | Result | Outcome | Evidence |
| --- | --- | --- | --- | --- | --- |
| 01 | 2026-10-20 | a | b | c | d |
| 02 | 2026-10-21 | a | b | c | d |
| 03 | 2026-10-22 | a | b | c | d |

## Where to look
"""


@pytest.fixture
def coupon_folders(tmp_path, monkeypatch):
    """A model folder with a case page, and an empty local folder for the coupon, in place of paths.MODELS and paths.LOCAL."""
    models, local = tmp_path / "models", tmp_path / "local"
    (models / "IM7-UNT-L9").mkdir(parents=True)
    (models / "IM7-UNT-L9" / "README.md").write_text(CASE_PAGE, encoding="utf-8")
    (local / "IM7-UNT-L9").mkdir(parents=True)
    monkeypatch.setattr(paths, "MODELS", models)
    monkeypatch.setattr(paths, "LOCAL", local)
    monkeypatch.setattr(case_pages, "result_block", lambda folder: "the result\n")  # the CalculiX record is not what this test is about
    return models / "IM7-UNT-L9", local / "IM7-UNT-L9"


def returned(tmp_path, grips, coupon="IM7-UNT-L9", **kwargs):
    folder = tmp_path / "came-back"
    folder.mkdir(exist_ok=True)
    path = filled(folder, grips, **kwargs)
    book = load_workbook(path)
    cover = book[COVER]
    labels = {cover.cell(r, 1).value: r for r in range(1, cover.max_row + 1)}
    cover.cell(labels["Coupon"], 2).value = coupon
    cover.insert_rows(labels["Attempt"])  # a Package row, as the coupon document writes one
    cover.cell(labels["Attempt"], 1).value, cover.cell(labels["Attempt"], 2).value = "Package", "2026-10-23_IM7-UNT-L9"
    book.save(path)
    return path


def test_a_returned_form_is_kept_and_listed_on_the_case_page(grips, tmp_path, coupon_folders):
    model, local = coupon_folders
    form, kept, case = case_pages.file_audit("IM7-UNT-L9", returned(tmp_path, grips), "2026-10-24")
    assert kept == local / paths.TEAM_FILES / "2026-10-24" / "2026-10-23_IM7-UNT-L9-audit.xlsx" and kept.is_file()
    assert form.verdict == "Pass" and case.status == "in progress"
    page = (model / "README.md").read_text(encoding="utf-8")
    assert page.index("## Audits") < page.index("## Attempt log") and "| 2026-10-24 | 2026-10-23_IM7-UNT-L9 | 3 | A. Engineer | 2026-10-24 | **Pass** |" in page
    assert case_pages.fill(page, case_pages.page_blocks(model, page), model / "README.md") == page  # the block is current
    assert case_pages.file_audit("IM7-UNT-L9", kept, "2026-10-25")[1] == kept  # a form already kept stays where it is


@pytest.mark.parametrize("kwargs, message", [
    (dict(coupon="IM7-UNC-L9"), "the form is for 'IM7-UNC-L9', not IM7-UNT-L9"),
    (dict(attempt="9"), "attempt '9' is not a row of the case page's attempt log (01 to 03)"),
])
def test_a_form_that_is_not_the_coupons_is_refused(grips, tmp_path, coupon_folders, kwargs, message):
    path = returned(tmp_path, grips, **{k: v for k, v in kwargs.items() if k == "coupon"})
    if "attempt" in kwargs:
        book = load_workbook(path)
        cover = book[COVER]
        row = next(r for r in range(1, cover.max_row + 1) if cover.cell(r, 1).value == "Attempt")
        cover.cell(row, 2).value = kwargs["attempt"]
        book.save(path)
    with pytest.raises(case_pages.CasePageError, match=re.escape(message)):
        case_pages.file_audit("IM7-UNT-L9", path, "2026-10-24")
    assert not (coupon_folders[1] / paths.TEAM_FILES).exists()


def test_a_form_for_another_team_deck_is_refused(grips, tmp_path, coupon_folders):
    verification = coupon_folders[1] / paths.OURS / paths.VERIFICATION
    verification.mkdir(parents=True)
    (verification / paths.MANIFEST).write_text(f'[team]\ndeck = "{GRIPS_FIXTURE.as_posix()}"\n', encoding="utf-8")
    with pytest.raises(case_pages.CasePageError, match="the form's team deck is not coupon-2x8-grips-im7-8552.inp"):
        case_pages.file_audit("IM7-UNT-L9", returned(tmp_path, grips), "2026-10-24")
