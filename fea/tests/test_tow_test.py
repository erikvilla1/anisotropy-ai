"""The fibre tow test of ASTM D4018 (ADR-0073): the studio's tow record read, refused by row, judged clause by clause, and reduced by the
engine; a deviation warns and never blocks; the coupon form and the coupon check refuse the tow and say where it goes.

The record is a constructed 12K carbon tow with round numbers, not a published test: 0.800 g/m, 1.80 g/cm^3, five specimens.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from anisotropy_fea.intake import FORM_VERSION, IntakeError, check_form, read_values
from anisotropy_fea.standards.astm_d4018 import failure_words
from anisotropy_fea.tow_test import (ITEM_OF_ROW, SPECIMEN_FIELDS, TOW_BLOCKS, TOW_ITEMS, TowRefused, check_tow, read_tow, tow_answer,
                                     tow_conformance, tow_numbers, tow_subject)

from test_intake import PUBLIC_FILL

FEA = Path(__file__).parents[1]
SPECIMENS = [
    {"id": "1", "max_force": 2150, "force_lower": 101.5, "force_upper": 610.2, "failure_code": "LGM", "status": "valid"},
    {"id": "2", "max_force": 2210, "force_lower": 102.8, "force_upper": 616.0, "failure_code": "SGV", "status": "valid"},
    {"id": "3", "max_force": 2080, "force_lower": 100.9, "force_upper": 607.5, "failure_code": "XGM", "status": "valid"},
    {"id": "4", "max_force": 2195, "force_lower": 103.1, "force_upper": 618.4, "failure_code": "GAT", "status": "valid"},
    {"id": "5", "max_force": 1650, "status": "rejected", "note": "slipped in the top grip"},
]
RECORD = {
    "form_version": FORM_VERSION, "test": "fibre tow tension", "standard": "ASTM D4018-23", "filled_by": "A. Tester", "date": "2026-11-09",
    "fibre": "constructed 12K carbon tow", "fibre_type": "carbon", "filaments": 12000, "bundles": 1, "mul": 0.800, "density_sample": "desized",
    "fibre_density": 1.80, "resin_strain": 50000, "mul_impregnated": 1.400, "tow_gauge_length": 150, "tow_tabs": "paper or card", "speed": 10,
    "failure_strain": 21000, "datasheet_strength": 4900, "datasheet_modulus": 230, "specimens": SPECIMENS,
}
AREA_MM2 = 0.800 / 1.80  # MUL / rho in the standard's units: g/m over g/cm^3 is mm^2


def write(tmp_path: Path, data: dict, name: str = "tow.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def record(**changes) -> dict:
    data = {**RECORD, **changes}
    return {k: v for k, v in data.items() if v is not None}


def judged(tmp_path: Path, **changes) -> dict:
    values = check_tow(read_tow(write(tmp_path, record(**changes))))
    found = tow_conformance(tow_subject(values, tow_numbers(values)))
    return {j.requirement.id: j for j in found.judged}


# --------------------------------------------------------------------------------------------- the numbers

def test_the_record_reduces_to_the_engines_strength_modulus_and_statistics(tmp_path):
    answer = tow_answer(write(tmp_path, RECORD))
    assert answer["checklist"]["state"] == "ready" and [i["id"] for i in answer["checklist"]["items"]] == [i for i, _ in TOW_ITEMS]
    result = answer["result"]
    assert result["fibre_properties"]["area"] == pytest.approx(AREA_MM2, rel=1e-12)
    assert result["fibre_properties"]["resin_content"] == pytest.approx(100 * (1 - 0.8 / 1.4), rel=1e-12)  # Eq 3
    by_id = {s["id"]: s for s in result["specimens"]}
    assert by_id["1"]["strength"] == pytest.approx(2150 * 1.80 / 0.800, rel=1e-12)  # Eq 4 in MPa: 4837.5
    assert by_id["1"]["modulus"] == pytest.approx((610.2 - 101.5) * 1.80 / (0.005 * 0.800) / 1000, rel=1e-12)  # Eq 5 in GPa, absolute strains
    strengths = [p * 1.80 / 0.800 for p in (2150, 2210, 2080, 2195)]  # the rejected specimen is listed, not counted
    mean = sum(strengths) / 4
    assert result["strength"]["n"] == 4 and result["strength"]["mean"] == pytest.approx(mean, rel=1e-12)
    sd = (sum((x - mean) ** 2 for x in strengths) / 3) ** 0.5
    assert result["strength"]["sd"] == pytest.approx(sd, rel=1e-12) and result["strength"]["cv"] == pytest.approx(100 * sd / mean, rel=1e-12)
    assert by_id["5"]["strength"] == pytest.approx(1650 * 1.80 / 0.800, rel=1e-12) and by_id["5"]["status"] == "rejected"
    assert result["counts"] == {"specimens": 5, "valid": 4, "strength": 4, "modulus": 4}
    assert result["strains"]["chord"] == pytest.approx([1000, 6000]) and result["strains"]["chord_from"] == "Table 2"
    assert result["strains"]["preload"] == pytest.approx(200)
    planning = result["planning"]  # P = eps E A and sigma A, from the datasheet, in N
    assert planning["preload_force"] == pytest.approx(200e-6 * 230e3 * AREA_MM2, rel=1e-12)
    assert planning["force_upper"] == pytest.approx(6000e-6 * 230e3 * AREA_MM2, rel=1e-12)
    assert planning["failure_force"] == pytest.approx(4900 * AREA_MM2, rel=1e-12)
    assert by_id["4"]["failure_words"] == "grip or tab, at the grip or tab, top"


def test_eq_1_eq_2_and_bundles_feed_the_area(tmp_path):
    values = check_tow(read_tow(write(tmp_path, record(mul=None, mul_mass=1.6, mul_length=2.0, density_sample="sized", fibre_density=1.82,
                                                       density_correction=0.02, filaments=1000, bundles=3, mul_impregnated=4.0))))
    numbers = tow_numbers(values)
    assert numbers.mul == pytest.approx(0.8e-3, rel=1e-12)  # Eq 1: 1.6 g over 2.0 m
    assert numbers.density == pytest.approx(1800.0, rel=1e-12)  # Eq 2: 1.82 - 0.02 g/cm^3
    assert numbers.specimen_mul == pytest.approx(2.4e-3, rel=1e-12)  # three bundles combined (our reading of §8.3)
    assert numbers.strengths["1"] == pytest.approx(2150 / (2.4e-3 / 1800.0), rel=1e-12)
    assert numbers.resin_content == pytest.approx(100 * (1 - 2.4 / 4.0), rel=1e-12)


def test_given_chord_strains_are_used_and_judged(tmp_path):
    values = check_tow(read_tow(write(tmp_path, record(chord_lower=1000, chord_upper=3000))))
    numbers = tow_numbers(values)
    assert numbers.chord_used == pytest.approx((1000e-6, 3000e-6))
    assert numbers.moduli["1"] == pytest.approx((610.2 - 101.5) / (2000e-6 * 0.8e-3 / 1800.0), rel=1e-12)
    found = judged(tmp_path, chord_lower=1000, chord_upper=3000)
    assert found["chord"].state == "deviation" and "6000" in found["chord"].limit


# --------------------------------------------------------------------------------------------- the judgement

def test_the_constructed_record_meets_every_requirement_the_record_shows(tmp_path):
    found = judged(tmp_path)
    assert {k: j.state for k, j in found.items() if j.state in ("deviation", "advisory")} == {}
    assert found["grip-failures"].state == "note" and found["grip-failures"].value.startswith("1 of 4")
    assert found["mul-length"].state == "na" and found["bundles"].state == "na"
    assert sum(1 for j in found.values() if j.state == "lab") == 10


@pytest.mark.parametrize("changes, requirement, state", [
    ({"tow_gauge_length": 160}, "gauge", "deviation"),
    ({"tow_gauge_length": 145}, "gauge", "met"),
    ({"specimens": SPECIMENS[:3]}, "strength-count", "deviation"),
    ({"specimens": [{**s, "force_lower": None, "force_upper": None} for s in SPECIMENS]}, "modulus-count", "deviation"),
    ({"resin_strain": 40000}, "resin-strain", "deviation"),
    ({"resin_strain": 42000}, "resin-strain", "met"),
    ({"speed": 300}, "speed", "deviation"),
    ({"speed": 250}, "speed", "met"),
    ({"bundles": 2, "mul_impregnated": 2.4}, "bundles", "deviation"),
    ({"filaments": 3000, "bundles": 2, "mul_impregnated": 2.4}, "bundles", "met"),
    ({"mul": None, "mul_mass": 0.4, "mul_length": 0.5}, "mul-length", "deviation"),
    ({"fibre_type": "other"}, "scope-fibre", "deviation"),
    ({"mul_impregnated": None, "resin_content": 30}, "resin-content", "advisory"),
    ({"density_sample": "sized"}, "density-sample", "advisory"),
    ({"density_sample": "sized"}, "density-correction", "note"),
    ({"specimens": [{**s, "failure_code": None} for s in SPECIMENS]}, "failure-codes", "advisory"),
])
def test_each_requirement_is_judged_by_its_clause(tmp_path, changes, requirement, state):
    assert judged(tmp_path, **changes)[requirement].state == state


def test_a_deviation_warns_and_never_blocks(tmp_path):
    answer = tow_answer(write(tmp_path, record(tow_gauge_length=200, specimens=SPECIMENS[:2])))
    standard = next(i for i in answer["checklist"]["items"] if i["id"] == "standard")
    assert answer["checklist"]["state"] == "ready" and standard["state"] == "warn" and answer["result"] is not None
    assert "3 deviations to report" in standard["message"] and "conforms" not in json.dumps(answer)
    assert {r["id"] for r in standard["requirements"] if r["state"] == "deviation"} == {"gauge", "strength-count", "modulus-count"}
    assert answer["result"]["strength"]["n"] == 2


def test_no_standard_still_reduces_the_record(tmp_path):
    answer = tow_answer(write(tmp_path, record(standard="none")))
    assert answer["checklist"]["state"] == "ready" and answer["result"]["conformance"] is None and answer["result"]["designation"] is None
    assert answer["result"]["strength"]["n"] == 4


# --------------------------------------------------------------------------------------------- refusals, by row

@pytest.mark.parametrize("changes, words", [
    ({"fibre": None}, "Fibre: required"),
    ({"fibre_density": None}, "Measured density (g/cm³): required"),
    ({"mul": None}, "Mass per unit length (g/m): required, or the MUL specimen's mass and length"),
    ({"mul_mass": 0.8}, "not both"),
    ({"mul": None, "mul_mass": 0.8}, "MUL specimen length (m): required with the other"),
    ({"density_correction": 0.01}, "belongs to a density measured on sized fibre"),
    ({"resin_content": 40}, "not both"),
    ({"mul_impregnated": 0.7}, "the strand carries the resin"),
    ({"chord_lower": 1000}, "give both chord strains"),
    ({"chord_lower": 3000, "chord_upper": 1000}, "must be greater than the lower strain"),
    ({"standard": "ASTM D3039/D3039M-17"}, "covers unnotched tension, not fibre tow tension"),
    ({"fibre_type": "glass"}, "'glass' is not one of carbon, graphite, other"),
    ({"tow_gauge_length": -1}, "Gauge length (mm): must be greater than 0"),
    ({"bundles": 1.5}, "a whole number is needed"),
    ({"date": "9 Nov"}, "is not a date"),
    ({"specimens": []}, "Specimens: required"),
    ({"specimens": [*SPECIMENS, {"id": "1", "max_force": 2000, "status": "valid"}]}, "'1' names two specimens"),
    ({"specimens": [{"id": "9", "max_force": 2000, "failure_code": "ZZZ", "status": "valid"}]}, "'ZZZ' is not a code of Fig. 1"),
    ({"specimens": [{"id": "9", "max_force": 2000, "status": "rejected"}]}, "required for a rejected specimen"),
    ({"specimens": [{"id": "9", "force_lower": 100, "status": "valid"}]}, "give both chord forces"),
    ({"specimens": [{"id": "9", "force_lower": 500, "force_upper": 100, "status": "valid"}]}, "must be greater than the force at the lower strain"),
    ({"specimens": [{"id": "9", "status": "valid"}]}, "required for a valid specimen"),
])
def test_every_problem_is_named_by_its_row(tmp_path, changes, words):
    with pytest.raises(TowRefused) as refused:
        check_tow(read_tow(write(tmp_path, record(**changes))))
    assert words in str(refused.value)
    assert all(p.row in ITEM_OF_ROW for p in refused.value.problems)


def test_problems_come_back_on_the_checklist_by_item(tmp_path):
    answer = tow_answer(write(tmp_path, record(fibre=None, tow_gauge_length="long", specimens=[])))
    states = {i["id"]: (i["state"], i["rows"]) for i in answer["checklist"]["items"]}
    assert answer["checklist"]["state"] == "blocked" and answer["result"] is None
    assert states["identity"] == ("missing", ["Fibre"]) and states["test"] == ("fail", ["Gauge length (mm)"])
    assert states["specimens"] == ("missing", ["Specimens"]) and states["fibre"][0] == "pass" and states["standard"][0] == "pending"


@pytest.mark.parametrize("data, words", [
    ({**RECORD, "form_version": "0.7"}, "is not the current form's"),
    ({**RECORD, "units": "mm-MPa"}, "unknown keys units"),
    ({**RECORD, "specimens": [{"id": "1", "max_force": 1, "load": 2}]}, "specimen 1: unknown keys load"),
    ({**RECORD, "test": "unnotched tension"}, "is not fibre tow tension"),
])
def test_a_file_that_is_no_tow_record_is_refused(tmp_path, data, words):
    with pytest.raises(IntakeError, match=words):
        read_tow(write(tmp_path, data))


def test_the_coupon_form_and_the_coupon_check_send_the_tow_elsewhere(tmp_path):
    with pytest.raises(IntakeError, match="studio_tool.py tow"):
        read_values(write(tmp_path, RECORD))
    from anisotropy_fea.intake import FormInput
    with pytest.raises(IntakeError, match="stated and calculated from the studio's tow panels"):
        check_form(FormInput(tmp_path / "form.xlsx", FORM_VERSION, {**PUBLIC_FILL, "test": "fibre tow tension"}))


def test_the_rows_of_the_record_are_each_in_one_item():
    keys = [f.key for _, fields in TOW_BLOCKS for f in fields]
    assert len(keys) == len(set(keys)) and set(ITEM_OF_ROW) == {*keys, "test", "standard", "filled_by", "date", "notes", "specimens"}
    assert [f.key for f in SPECIMEN_FIELDS] == ["id", "max_force", "force_lower", "force_upper", "failure_code", "status", "note"]
    assert failure_words("lgm") == "lateral, gauge, middle" and failure_words("LG") is None and failure_words("QGM") is None


def test_the_studio_tool_writes_the_answer(tmp_path):
    source = write(tmp_path, RECORD, "values.json")
    done = subprocess.run([sys.executable, str(FEA / "tools" / "studio_tool.py"), "tow", str(source), "--out", str(tmp_path / "out")],
                          capture_output=True, text=True, encoding="utf-8", cwd=FEA, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("ready: fibre tow record, 4 valid specimens")
    answer = json.loads((tmp_path / "out" / "tow.json").read_text(encoding="utf-8"))
    assert answer["result"]["designation"] == "ASTM D4018-23"


def test_the_browser_fixture_is_what_the_package_answers_today():
    """tests/fixtures/studio-tow/tow.json is what the studio's browser tests show; it must be the package's answer to values.json today
    (rewrite it with `uv run python tools/studio_tool.py tow ../tests/fixtures/studio-tow/values.json --out ../tests/fixtures/studio-tow`)."""
    fixtures = FEA.parent / "tests" / "fixtures" / "studio-tow"
    today = json.loads(json.dumps(tow_answer(fixtures / "values.json"), ensure_ascii=False))
    assert today == json.loads((fixtures / "tow.json").read_text(encoding="utf-8"))
