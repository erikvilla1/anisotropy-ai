"""Test standards as profiles (ADR-0072): the registry holds what a reader needs of every requirement; ASTM D3039 and ASTM C1869 judge the
public coupons as their clauses ask; a deviation warns and never blocks; the form refuses a standard of another test, a missing specimen,
and the rows that belong elsewhere; the spec keeps the standard, the strain measurement and the tabs, and gives them back to the form; an
older form still reads. Nothing here touches .local/."""

import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from anisotropy_engine.library import load_library
from anisotropy_engine.units import INCH
from anisotropy_fea import paths
from anisotropy_fea.checks import setup_checklist
from anisotropy_fea.femodel import build_model
from anisotropy_fea.intake import (FIELDS, FORM_VERSION, RECORD, IntakeError, ROWS_ADDED, check_form, designation_for, read_form, read_values,
                                   spec_from_values, values_of_spec, write_blank_form, fill_form)
from anisotropy_fea.spec import SpecError, parse_spec
from anisotropy_fea.standards import BY_DESIGNATION, LEVELS, NONE, PROFILES, STANDARD_WORDS, profile_of_word, profiles_for
from anisotropy_fea.standards.astm_c1869 import SPECIMEN_A, SPECIMEN_B
from anisotropy_fea.standards.astm_d3039 import BALANCED, NINETY_UD, ZERO_UD, classify
from anisotropy_fea.standards.conformance import conformance, subject_of
from anisotropy_fea.standards.profile import OTHER_FAMILIES, POLYMER_FAMILIES, is_balanced, is_symmetric

from public_coupon import PUBLIC_COUPON
from test_intake import PUBLIC_FILL

D3039, C1869, D638 = "ASTM D3039/D3039M-17", "ASTM C1869-18(2023)", "ASTM D638-22"
TOOLS = dict(ccx=lambda: Path("ccx"), tectonic=lambda: "tectonic", gmsh=lambda: "4.15")
STRIP = {**PUBLIC_FILL, "mesh_nx": None, "mesh_partitions": None, "mesh_seeds": None, "element_size": 5.0}  # the public coupon, coarsely meshed
D3039_STRIP = {**STRIP, "standard": D3039, "strain_device": "extensometer", "strain_length": 25.0}
B_STRIP = {**STRIP, "test": "open-hole tension", "standard": C1869, "specimen": "B", "length": 60.0, "width": 10.0, "tab_length": 15.0,
           "hole_diameter": 3.0, "element_size": 1.0}


@pytest.fixture(scope="module", autouse=True)
def local_untouched():
    before = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    yield
    after = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    assert before == after, "the standards tests must not write under .local/"


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22" if ccx is not None else None)


def values_path(folder: Path, values: dict, version: str = FORM_VERSION) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": version, **{k: v for k, v in values.items() if v is not None}}), encoding="utf-8")
    return path


def checked(folder: Path, values: dict, version: str = FORM_VERSION):
    checklist, model, _ = setup_checklist(read_values(values_path(folder, values, version)), folder / "none", **TOOLS)
    return checklist, {item.id: item for item in checklist.items}, model


def spec_of(folder: Path, values: dict):
    form = read_values(values_path(folder, values))
    typed = check_form(form)
    return spec_from_values(typed, designation_for(typed, folder / "none"), form.path.name)


def judged(spec) -> dict:
    return {j.requirement.id: j for j in conformance(spec).judged}


# --------------------------------------------------------------------------------------------- the registry

def test_every_requirement_names_its_clause_level_and_rule():
    assert STANDARD_WORDS == (NONE, *BY_DESIGNATION) and set(BY_DESIGNATION) == {D3039, D638, C1869}
    for profile in PROFILES.values():
        ids = [r.id for r in profile.requirements]
        assert len(ids) == len(set(ids)), f"{profile.id}: requirement ids repeat"
        assert profile.catalog_url.startswith("https://store.astm.org/") and profile.rights == "licensed-reference" and profile.edition_note
        for r in profile.requirements:
            assert r.clause and r.text.endswith(".") and r.level in LEVELS, r.id
            assert (r.rule is None) == (r.level == "lab"), r.id
            assert all(row in FIELDS for row in r.rows), f"{profile.id}.{r.id}: a row the form does not have"
        for preset in (*profile.variants, *profile.classes):
            assert all(row in FIELDS for row in preset.si), f"{profile.id}.{preset.key}: a row the form does not have"
    assert profiles_for("unnotched_tension") == [PROFILES["astm-d3039"], PROFILES["astm-d638"]] and profiles_for("open_hole_tension") == [PROFILES["astm-c1869"]]
    assert profiles_for("three_point_bending") == [] and profile_of_word("none") is None and profile_of_word("astm d3039/d3039m-17") is PROFILES["astm-d3039"]


def test_every_library_family_is_known_by_its_matrix():
    families = {d["family"] for d in load_library()["datasets"]}
    assert families <= set(POLYMER_FAMILIES) | set(OTHER_FAMILIES), f"a family the standards do not place: {families - set(POLYMER_FAMILIES) - set(OTHER_FAMILIES)}"


@pytest.mark.parametrize("angles, balanced, symmetric", [
    ((45, 0, -45, 90, 90, -45, 0, 45), True, True), ((0, 45), False, False), ((45, -45), True, False), ((45, 45), False, True),
    ((0, 90, 90, 0), True, True), ((30, -30, -30, 30), True, True),
])
def test_balanced_and_symmetric_follow_the_definitions(angles, balanced, symmetric):
    assert is_balanced(tuple(float(a) for a in angles)) is balanced and is_symmetric(tuple(float(a) for a in angles)) is symmetric


def test_the_presets_keep_the_standards_own_inch_values():
    assert ZERO_UD.values_in("in-psi") == pytest.approx({"width": 0.5, "length": 10.0, "tab_length": 2.25, "tab_thickness": 0.062, "tab_bevel": 7.0})
    assert ZERO_UD.values_in("mm-MPa") == pytest.approx({"width": 15.0, "length": 250.0, "tab_length": 56.0, "tab_thickness": 1.5, "tab_bevel": 7.0})
    assert NINETY_UD.values_in("m-Pa") == pytest.approx({"width": 0.025, "length": 0.175, "tab_length": 0.025, "tab_thickness": 0.0015, "tab_bevel": 90.0})
    assert BALANCED.thickness_si("in-ksi") == pytest.approx(0.100 * INCH) and BALANCED.thickness_si("mm-MPa") == pytest.approx(2.5e-3)
    assert SPECIMEN_A.values_in("in-psi")["width"] == pytest.approx(36 / 25.4)  # C1869 is SI only: converted exactly
    assert SPECIMEN_B.values_in("mm-MPa") == pytest.approx({"width": 10.0, "hole_diameter": 3.0, "length": 60.0, "tab_length": 15.0})


# --------------------------------------------------------------------------------------------- ASTM D3039

def test_d3039_holds_the_public_coupon_and_names_what_it_does_not_follow(tmp_path):
    checklist, items, model = checked(tmp_path, D3039_STRIP)
    assert checklist.state == "ready" and model is not None and items["standard"].state == "pass"
    assert items["standard"].message.startswith(f"specimen checked against {D3039}, balanced and symmetric class (Table 2): 4 of 4 requirements")
    states = {r["id"]: r["state"] for r in items["standard"].requirements}
    assert all(states[k] == "met" for k in ("scope-matrix", "scope-laminate", "section", "min-length", "t2-width", "t2-length", "extensometer"))
    assert states["t2-thickness"] == "advisory" and states["edge-effects"] == "note" and states["tab-bevel"] == "na"
    assert sum(1 for r in items["standard"].requirements if r["state"] == "lab") == 12
    row = next(r for r in items["standard"].requirements if r["id"] == "min-length")
    assert row["value"] == "250 mm" and row["limit"] == "at least 187 mm (2 × 56 mm gripped + 2 × 25 mm wide + 25 mm gauge)" and row["clause"] == "Table 1"


@pytest.mark.parametrize("changes, deviation", [
    (dict(angles=[0, 45], symmetric="no"), "scope-laminate"),
    (dict(length=150.0, mesh_partitions=None), "min-length"),
    (dict(tab_thickness=1.5, tab_bevel=3.0), "tab-bevel"),
])
def test_a_d3039_deviation_warns_and_still_runs(tmp_path, changes, deviation):
    checklist, items, model = checked(tmp_path, {**D3039_STRIP, **changes})
    assert checklist.state == "ready" and model is not None and items["standard"].state == "warn"
    states = {r["id"]: r["state"] for r in items["standard"].requirements}
    assert states[deviation] == "deviation" and "deviation" in items["standard"].message and "conform" not in items["standard"].message


@pytest.mark.parametrize("changes, preset", [
    (dict(angles=[0, 0, 0, 0]), ZERO_UD), (dict(angles=[90, 90]), NINETY_UD), (dict(angles=[45, 0, -45, 90]), BALANCED),
    (dict(angles=[0, 0], library="as4-8552s-pw"), BALANCED), (dict(angles=[0, 45], symmetric="no"), None),
])
def test_the_table_2_class_follows_the_layup_and_the_material(tmp_path, changes, preset):
    assert classify(subject_of(spec_of(tmp_path, {**D3039_STRIP, **changes}))) is preset


def test_a_coupon_stated_in_inches_is_held_to_the_inch_values(tmp_path):
    inches = {**D3039_STRIP, "units": "in-psi", "length": 10.0, "width": 1.0, "tab_length": 2.0, "strain_length": 1.0, "element_size": 0.2,
              "G13": 680000.0, "G23": 435000.0}
    found = judged(spec_of(tmp_path, inches))
    assert found["t2-width"].state == "met" and found["t2-width"].value == "1 in" and found["t2-length"].state == "met"
    assert found["extensometer"].state == "met" and found["extensometer"].limit == "0.5 in to 2 in"
    metric_width = judged(spec_of(tmp_path / "metric", {**inches, "width": 25.0 / 25.4}))  # 25 mm is not D3039's 1.0 in (§1.2)
    assert metric_width["t2-width"].state == "advisory"


# --------------------------------------------------------------------------------------------- ASTM C1869

def test_c1869_b_is_judged_on_its_table_and_a_polymer_is_outside_its_scope(tmp_path):
    checklist, items, model = checked(tmp_path, B_STRIP)
    assert checklist.state == "ready" and model is not None and items["standard"].state == "warn"
    states = {r["id"]: r for r in items["standard"].requirements}
    assert states["scope-matrix"]["state"] == "deviation" and "ASTM D5766/D5766M" in states["scope-matrix"]["value"]
    assert all(states[k]["state"] == "met" for k in ("hole", "width", "width-to-hole", "length", "gauge-length", "grip-length", "hole-centred"))
    assert states["width-to-hole"]["value"] == "3.33" and states["thickness"]["state"] == "deviation"  # 1.46 mm, under C1869's 2 mm
    assert items["standard"].message.startswith(f"specimen checked against {C1869}, Specimen B: 7 of 9 requirements")


def test_c1869_a_at_its_least_lengths_meets_its_table(tmp_path):
    a = {**B_STRIP, "specimen": "A", "length": 120.0, "width": 36.0, "tab_length": 30.0, "hole_diameter": 6.0, "element_size": 2.0,
         "angles": [45, 0, -45, 90, 45, 0, -45, 90, 45, 0, -45, 90]}  # 24 plies of 0.183 mm: 4.4 mm, inside 2 to 10 mm
    found = judged(spec_of(tmp_path, a))
    assert all(found[k].state == "met" for k in ("hole", "width", "width-to-hole", "length", "gauge-length", "grip-length", "thickness"))
    assert found["gauge-to-hole"].state == "met" and found["variation"].state == "na"


def test_c1869_other_is_a_variation_judged_by_its_annex(tmp_path):
    other = {**B_STRIP, "specimen": "other", "length": 200.0, "width": 40.0, "tab_length": 40.0, "hole_diameter": 8.0, "element_size": 2.0}
    found = judged(spec_of(tmp_path, other))
    assert found["variation"].state == "note" and found["hole"].state == "na" and found["width"].state == "na"
    assert found["larger-hole"].state == "advisory" and found["larger-hole"].limit == "at least 6 for a hole above 5 mm (X1.3)"  # w/D = 5


# --------------------------------------------------------------------------------------------- the form refuses by row

@pytest.mark.parametrize("values, row, words", [
    ({**STRIP, "standard": C1869, "specimen": "A"}, "standard", "covers open-hole tension, not unnotched tension"),
    ({**B_STRIP, "specimen": None}, "specimen", "required for ASTM C1869-18(2023); one of A, B, other"),
    ({**STRIP, "specimen": "A"}, "specimen", "belongs to a standard that names its specimens"),
    ({**STRIP, "standard": "ASTM D3039"}, "standard", "is not one of none, ASTM D3039/D3039M-17, ASTM D638-22, ASTM C1869-18(2023)"),
    ({**STRIP, "standard": D3039}, "strain_device", "required for ASTM D3039/D3039M-17, whose minimum length counts the gauge length"),
    ({**STRIP, "tab_thickness": 1.5}, "tab_thickness", "give both for bonded tabs"),
    ({**STRIP, "tab_thickness": 1.5, "tab_bevel": 95.0}, "tab_bevel", "at most 90"),
    ({**STRIP, "strain_length": 25.0}, "strain_device", "give both, or neither"),
])
def test_the_form_refuses_a_standard_row_by_its_label(tmp_path, values, row, words):
    with pytest.raises(IntakeError) as caught:
        check_form(read_values(values_path(tmp_path, values)))
    assert f"{FIELDS[row].label}" in str(caught.value) and words in str(caught.value)


def test_bending_takes_no_tab_or_strain_rows(tmp_path):
    bending = json.loads((paths.ROOT / "tests/fixtures/studio-bending/values.json").read_text(encoding="utf-8"))
    bending.pop("form_version")
    for extra in ({"tab_thickness": 1.5, "tab_bevel": 7.0}, {"strain_device": "extensometer", "strain_length": 10.0}):
        with pytest.raises(IntakeError, match="belong to the pulled and pushed tests"):
            check_form(read_values(values_path(tmp_path, {**bending, **extra})))


# --------------------------------------------------------------------------------------------- the spec and the round trip

def test_the_spec_keeps_the_standard_the_strain_and_the_tabs_and_gives_them_back(tmp_path):
    values = {**D3039_STRIP, "tab_thickness": 1.5, "tab_bevel": 7.0, "tab_material": "E-glass/epoxy"}
    spec = spec_of(tmp_path, values)
    assert spec.coupon.standard == D3039 and spec.test_method.id == "astm-d3039" and spec.test_method.variant is None
    assert spec.strain.device == "extensometer" and spec.strain.gauge_length == pytest.approx(0.025) and spec.tabs.thickness == pytest.approx(1.5e-3)
    back = values_of_spec(spec)
    assert {k: back[k] for k in ("standard", "strain_device", "strain_length", "tab_thickness", "tab_bevel", "tab_material")} == {
        "standard": D3039, "strain_device": "extensometer", "strain_length": pytest.approx(25.0), "tab_thickness": pytest.approx(1.5), "tab_bevel": 7.0,
        "tab_material": "E-glass/epoxy"}
    b = values_of_spec(spec_of(tmp_path / "b", B_STRIP))
    assert b["standard"] == C1869 and b["specimen"] == "B"


def test_the_deck_heading_names_the_standard_only_when_there_is_one(tmp_path):
    heading = "\n".join(build_model(spec_of(tmp_path, {**D3039_STRIP, "tab_thickness": 1.5, "tab_bevel": 7.0})).heading)
    assert f"Standard: {D3039}" in heading and "Strain measurement: extensometer, 25 mm gauge length" in heading
    assert "Tabs: bonded, 1.5 mm thick, 7 deg bevel; drawn and reported, not modelled" in heading
    plain = "\n".join(build_model(spec_of(tmp_path / "plain", STRIP)).heading)
    assert "Standard: none" in plain and "Strain measurement" not in plain and "Tabs:" not in plain and "Specimen" not in plain


@pytest.mark.parametrize("edit, words", [
    (("[geometry]", '[test_method]\nid = "astm-d9999"\n\n[geometry]'), "test_method.id = 'astm-d9999' is not one of"),
    (("[geometry]", '[test_method]\nid = "astm-c1869"\nvariant = "A"\n\n[geometry]'), "covers open-hole tension, not unnotched tension"),
    (('standard = "none"', f'standard = "{D3039}"'), "names a standard we check, so the spec needs [test_method] id = 'astm-d3039'"),
    (("[geometry]", '[test_method]\nid = "astm-d3039"\n\n[geometry]'), f"needs coupon.standard = '{D3039}'"),
    (("[output]", '[strain]\ndevice = "extensometer"\ngauge_length = 200.0\n\n[output]'), "must fit between the grips"),
    (("[output]", '[tabs]\nthickness = 1.5\nbevel = 120.0\n\n[output]'), "tabs.bevel is an angle in degrees above 0 and at most 90"),
])
def test_the_spec_refuses_a_standard_it_cannot_hold(edit, words):
    old, new = edit
    assert old in PUBLIC_COUPON
    with pytest.raises(SpecError) as caught:
        parse_spec(PUBLIC_COUPON.replace(old, new, 1))
    assert words in str(caught.value)


def test_a_spec_that_names_no_standard_is_judged_by_none(tmp_path):
    spec = spec_of(tmp_path, STRIP)
    assert spec.test_method is None and conformance(spec) is None


# --------------------------------------------------------------------------------------------- older forms

def test_a_values_file_of_form_0_7_still_reads(tmp_path):
    checklist, items, _ = checked(tmp_path, STRIP, version="0.7")
    assert checklist.state == "ready" and items["standard"].message.startswith("no standard picked")


def test_an_excel_form_of_0_7_without_the_new_rows_still_reads(tmp_path):
    blank = write_blank_form(tmp_path / "blank.xlsx")
    path = fill_form(blank, {k: v for k, v in STRIP.items() if v is not None}, tmp_path / "filled.xlsx")
    book = load_workbook(path)
    sheet = book["Coupon"]
    new_labels = {FIELDS[key].label for key in ROWS_ADDED["0.8"]}
    for r in range(1, sheet.max_row + 1):  # a 0.7 form has no such rows: their labels gone, the reader does not find them
        if sheet.cell(r, 1).value in new_labels:
            sheet.cell(r, 1).value = None
    record = book[RECORD]
    row = next(r for r in range(1, record.max_row + 1) if record.cell(r, 1).value == "Form version")
    record.cell(row, 2, "0.7")
    book.save(path)
    form = read_form(path)
    assert form.version == "0.7" and check_form(form).standard == NONE
    record.cell(row, 2, FORM_VERSION)
    book.save(path)
    with pytest.raises(IntakeError, match="rows missing from the form: Specimen"):
        read_form(path)
