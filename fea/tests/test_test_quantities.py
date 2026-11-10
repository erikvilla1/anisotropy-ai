"""The quantities of a test standard (ADR-0072, part 3): the standards' formulas reproduce hand values; on the public IM7/8552 coupon under
ASTM D3039 the virtual extensometer's chord modulus and Poisson's ratio meet laminate theory; the open hole's net section follows its
geometry; the stated units convert the area and the modulus; every number the sentences print is a fact; CalculiX's chord modulus is
read from the record through the same functions. Nothing here touches .local/."""

import json
from pathlib import Path

import pytest

from anisotropy_engine.units import INCH, PSI
from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.calculix_summary import calculix_test_method
from anisotropy_fea.explain import fact_sheet, numbers_in, result_sentences
from anisotropy_fea.femodel import build_model
from anisotropy_fea.fields import field_data
from anisotropy_fea.intake import check_form, designation_for, read_values, spec_from_values
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.report import ComparisonRow
from anisotropy_fea.test_quantities import (CHORD_RANGE, chord_modulus, engineering_stress, extensometer_strain, gross_area, method_inputs, net_area,
                                            poisson_ratio)
from anisotropy_fea.units import deck_units_of
from anisotropy_fea.write_abaqus import write_abaqus

VALUES = json.loads((paths.ROOT / "tests/fixtures/studio-standards/values.json").read_text(encoding="utf-8"))
D3039 = {**VALUES, "grips": "nodal", "element_size": 2.0}
B = {**VALUES, "test": "open-hole tension", "standard": "ASTM C1869-18(2023)", "specimen": "B", "length": 60.0, "width": 10.0, "tab_length": 15.0,
     "hole_diameter": 3.0, "element_size": 1.0, "strain_length": 10.0, "tab_thickness": None, "tab_bevel": None, "tab_material": None}


@pytest.fixture(scope="module", autouse=True)
def local_untouched():
    before = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    yield
    after = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    assert before == after, "the test-quantity tests must not write under .local/"


def solved(folder: Path, values: dict):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({k: v for k, v in values.items() if v is not None}), encoding="utf-8")
    typed = check_form(read_values(path))
    spec = spec_from_values(typed, designation_for(typed, folder / "none"), path.name)
    deck_path = folder / "deck.inp"
    deck_path.write_text(write_abaqus(build_model(spec)), encoding="utf-8")
    deck = read_deck(deck_path, deck_units_of(spec.units))
    return spec, field_data(deck, solve_deck(deck), spec.units, criteria=tuple(spec.output.fpf_criteria), method=method_inputs(spec),
                            coupon={"designation": "IM7-UNT-L1", "test": spec.kind.replace("_", " "), "layup": "[45/0/-45/90]s"})


@pytest.fixture(scope="module")
def d3039(tmp_path_factory):
    return solved(tmp_path_factory.mktemp("d3039"), D3039)


@pytest.fixture(scope="module")
def specimen_b(tmp_path_factory):
    return solved(tmp_path_factory.mktemp("b"), B)


def test_the_formulas_are_the_standards():
    assert gross_area(0.025, 0.002) == pytest.approx(5e-5) and net_area(0.036, 0.003, 0.006) == pytest.approx(9e-5)
    assert engineering_stress(10000.0, 5e-5) == pytest.approx(2e8) and extensometer_strain(0.0001, 0.00015, 0.1, 0.125) == pytest.approx(0.002)
    low, high, modulus = chord_modulus(1.2e8, 0.002)  # 60 GPa: 60 MPa at 1000 microstrain, 180 MPa at 3000
    assert (low, high, modulus) == pytest.approx((6e7, 1.8e8, 6e10)) and CHORD_RANGE == (1e-3, 3e-3)
    assert poisson_ratio(-0.0006, 0.002) == pytest.approx(0.3)


def test_the_extensometer_reads_laminate_theory_on_the_d3039_coupon(d3039):
    spec, data = d3039
    tm = data["summary"]["test_method"]
    assert tm["designation"] == "ASTM D3039/D3039M-17" and tm["units"]["area"] == "mm²" and tm["units"]["modulus"] == "GPa"
    assert tm["area"] == pytest.approx(25.0 * 8 * 0.18288) and tm["stress"] == pytest.approx(tm["force"] / tm["area"])
    s, lt = tm["strain"], tm["laminate_theory"]
    assert s["modelled_length"] == pytest.approx(25.0) and s["x"] == pytest.approx([12.5, 12.5])  # node rows at the ends, a column on the centre line
    assert s["chord"]["modulus"] == pytest.approx(lt["modulus"], rel=1e-4) and s["poisson"] == pytest.approx(lt["poisson"], rel=1e-4)
    assert s["chord"]["stress_from"] == pytest.approx(s["chord"]["modulus"] * 1e3 * 1e-3, rel=1e-9)  # GPa x 1000 microstrain, in MPa
    assert s["chord"]["force_to"] == pytest.approx(s["chord"]["stress_to"] * tm["area"])
    first = tm["fpf"][tm["earliest"]]
    assert tm["fpf_basis"] == "the gauge section" and first["stress"] == pytest.approx(first["factor"] * tm["stress"])
    assert first["strain"] == pytest.approx(first["factor"] * s["value"]) and tm["note_b"] is False and tm["hole"] is None
    words = tm["reduction"]  # D3039's own words: a chord between Table 3's strains, over the gross area (ADR-0075 gives D638 its own)
    assert (words["modulus"], words["area"], words["modulus_clause"]) == ("chord modulus", "gross area", "D3039 Table 3, Eq 8")
    assert (s["chord"]["from"], s["chord"]["to"]) == CHORD_RANGE and lt["isotropic"] is False
    assert spec.mesh.y_partitions == pytest.approx([0.056, 0.1125, 0.1375, 0.194]) and spec.mesh.y_seeds[2] % 2 == 0 and spec.mesh.nx % 2 == 0


def test_the_open_hole_reports_its_net_section(specimen_b):
    _, data = specimen_b
    tm = data["summary"]["test_method"]
    h = tm["hole"]
    assert h["net_area"] == pytest.approx((10.0 - 3.0) * tm["thickness"]) and h["width_to_hole"] == pytest.approx(10 / 3)
    assert h["hole_to_thickness"] == pytest.approx(3.0 / tm["thickness"]) and h["net_stress"] == pytest.approx(tm["force"] / h["net_area"])
    assert tm["strain"]["poisson"] is None  # mid-length is the hole's section
    first = tm["fpf"][tm["earliest"]]
    assert first["net_stress"] == pytest.approx(first["factor"] * h["net_stress"]) and first["place"] == "beside the hole"


def test_a_coupon_without_a_standard_or_a_strain_measurement_has_no_block(tmp_path):
    plain = {**D3039, "standard": "none", "strain_device": None, "strain_length": None, "tab_thickness": None, "tab_bevel": None, "tab_material": None,
             "size_from": "ours"}
    _, data = solved(tmp_path, plain)
    assert "test_method" not in data["summary"]


def test_the_stated_units_carry_the_area_and_the_modulus(tmp_path, d3039):
    inches = {**D3039, "units": "in-psi", "length": 10.0, "width": 1.0, "tab_length": 2.2, "strain_length": 1.0, "element_size": 0.08,
              "tab_thickness": 0.062, "G13": 680000.0, "G23": 435000.0}
    _, data = solved(tmp_path, inches)
    tm = data["summary"]["test_method"]
    assert tm["units"]["area"] == "in²" and tm["units"]["modulus"] == "Msi" and tm["area"] == pytest.approx(1.0 * 8 * 0.18288e-3 / INCH)
    _, metric = d3039
    gpa = metric["summary"]["test_method"]["laminate_theory"]["modulus"]
    assert tm["laminate_theory"]["modulus"] == pytest.approx(gpa * 1e9 / (1e6 * PSI))  # the same laminate in Msi


@pytest.mark.parametrize("which", ["d3039", "specimen_b"])
def test_every_number_the_method_sentences_print_is_a_fact(which, request):
    _, data = request.getfixturevalue(which)
    facts = fact_sheet(data["summary"], data["coupon"], data["units"], data["labels"])
    sentences = result_sentences(facts)
    printed = set()
    for value in facts.values():
        for v in (value if isinstance(value, list) else [value]):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                printed.update({f"{v:.4g}", str(v), f"{v:g}"})
            elif isinstance(v, str):
                printed.add(v)
    method = [s for s in sentences if s.startswith(("As ASTM", "Through the hole", "The extensometer", "By "))]
    assert len(method) == (4 if which == "specimen_b" else 3)
    for sentence in sentences:
        for token in numbers_in(sentence):
            assert token in printed or token.lstrip("-+") in printed or any(token in v for v in printed if isinstance(v, str)), (token, sentence)
    assert any("not the ultimate strength" in s for s in method)
    for key, value in facts.items():
        if isinstance(value, float):
            assert value == float(f"{value:.4g}"), key


def test_calculix_chord_modulus_comes_from_the_record_through_the_same_functions():
    rows = [ComparisonRow("rf", "rf", "Grip-Top", None, 1, 10000.0, 10010.0, 300.0),
            ComparisonRow("u", "u", "Coupon-1.10", None, 1, 0.20, 0.2002, 0.01), ComparisonRow("u", "u", "Coupon-1.20", None, 1, 0.25, 0.2502, 0.01)]
    out = calculix_test_method(rows, "mm-MPa", "mm-MPa", ("Coupon-1.10", "Coupon-1.20"), (0.1, 0.125), 5e-5)
    assert out["calculix"]["strain"] == pytest.approx(0.002) and out["calculix"]["modulus"] == pytest.approx(10000.0 / 5e-5 / 0.002 / 1e9)
    assert out["ours"]["modulus"] == pytest.approx(10010.0 / 5e-5 / 0.002 / 1e9) and out["agrees"] is True
    assert out["difference"] == "+0.10 %"  # ours against CalculiX, as the record words every difference
    assert calculix_test_method(rows[:1], "mm-MPa", "mm-MPa", ("Coupon-1.10", "Coupon-1.20"), (0.1, 0.125), 5e-5) is None
