"""The material loader: cited library datasets become engine inputs in SI with their pages."""

from pathlib import Path

import pytest

from anisotropy_engine.cases import load_case, solve_case
from anisotropy_engine.library import find_dataset, library_material, list_datasets, load_library
from anisotropy_engine.units import DEG_F, INCH, PSI

CASES = Path(__file__).parents[1] / "validation" / "cases"


def test_library_file_is_a_schema_1_export_with_the_26_public_materials():
    data = load_library()
    assert data["schemaVersion"] == 1
    ids = {d["materialId"] for d in data["datasets"]}
    assert len(ids) == 26
    assert len({d["datasetId"] for d in data["datasets"]}) == len(data["datasets"])
    summaries = list_datasets()
    assert {s["material_id"] for s in summaries} == ids
    assert sum(s["primary"] for s in summaries) == 26


def test_im7_8552_defaults_to_the_ncamp_dataset_and_converts_printed_units_to_si():
    m = library_material("im7-8552")
    assert m.dataset_id == "ncamp-im7-8552-2019-rtd-measured-v1"
    assert m.lamina.E1 == pytest.approx(23.51e6 * PSI, rel=1e-12)
    assert m.lamina.E2 == pytest.approx(1.30e6 * PSI, rel=1e-12)
    assert m.lamina.G12 == pytest.approx(0.68e6 * PSI, rel=1e-12)
    assert m.lamina.nu12 == 0.316
    assert m.value("E1").source_value == 23.51 and m.value("E1").source_unit == "Msi"
    assert m.value("E1").page == 30 and m.value("E1").reference_url.endswith("#page=30")
    # Strengths: the direct values, the cross-ply back-out for F1c, and the 5%-strain shear for F6.
    assert m.lamina.strengths is not None
    assert m.lamina.strengths.F1t == pytest.approx(371.08e3 * PSI, rel=1e-12)
    assert m.value("F1c").key == "F1c-derived" and m.value("F1c").basis == "Derived lamina mean"
    assert m.lamina.strengths.F1c == pytest.approx(251.13e3 * PSI, rel=1e-12)
    assert m.value("F6").key == "F12-5pct"
    assert m.lamina.strengths.F6 == pytest.approx(13.22e3 * PSI, rel=1e-12)
    assert m.ply_thickness_m == pytest.approx(0.0072 * INCH, rel=1e-12)
    assert m.lamina.thermal_expansion is None
    assert any(item.startswith("thermal expansion") for item in m.not_provided)
    assert "CAM-RP-2009-015" in m.citation and m.rights == "open-publisher"


def test_a_book_or_a_search_link_is_cited_by_printed_page_and_a_document_link_opens_at_its_page():
    # ADR-0018 amendment 2: the textbook links to its publisher and the dissertation to a search, so neither link is the
    # document; both are cited by printed page only, with no #page= anchor and no PDF page in the export.
    book = library_material("as4-3501")
    assert book.value("E1").page == 377 and book.value("E1").printed_page == 377
    assert "#page=" not in book.value("E1").reference_url
    assert find_dataset("as4-3501")["source"]["page"] == 377
    dissertation = library_material("x840-z60-pw")
    assert dissertation.value("E1").page == 79 and dissertation.value("E1").printed_page == 79
    assert "#page=" not in dissertation.value("E1").reference_url
    record = find_dataset("x840-z60-pw")
    assert record["source"]["page"] == 79 and record["source"]["linkKind"] == "search"
    assert {p["sourcePage"] for p in record["properties"]} == {79}
    # The NASA report's link is the public PDF itself: its value opens at the PDF page and also names the printed one.
    nasa = library_material("im7-8552", "nasa-tm-20230001560-im7-8552-rt-measured-v1")
    assert nasa.value("E1").page == 18 and nasa.value("E1").printed_page == 12
    assert nasa.value("E1").reference_url.endswith("TM-20230001560.pdf#page=18")


def test_the_nasa_dataset_of_the_same_material_is_a_separate_choice_with_direct_compression():
    m = library_material("im7-8552", "nasa-tm-20230001560-im7-8552-rt-measured-v1")
    assert m.lamina.E1 == pytest.approx(23.105148e6 * PSI, rel=1e-12)
    assert m.value("F1c").key == "F1c" and m.lamina.strengths.F1c == pytest.approx(116.744e3 * PSI, rel=1e-12)
    assert m.value("F6").key == "F12-5pct"
    assert m.ply_thickness_m == pytest.approx(0.18e-3, rel=1e-12)


def test_textbook_values_in_si_convert_without_change_and_carry_thermal_expansion():
    m = library_material("as4-3501")
    assert m.lamina.E1 == 147e9 and m.lamina.E2 == 10.3e9 and m.lamina.G12 == 7e9 and m.lamina.nu12 == 0.27
    assert m.value("F6").key == "F12" and m.lamina.strengths.F6 == 76e6
    assert m.lamina.strengths.F1c == 1725e6
    assert m.lamina.thermal_expansion.alpha1 == pytest.approx(-0.9e-6)
    assert m.lamina.thermal_expansion.alpha2 == pytest.approx(27e-6)
    assert m.ply_thickness_m is None and any(item.startswith("ply thickness") for item in m.not_provided)


def test_density_and_fiber_volume_fraction_are_cited_when_the_record_states_one_value():
    textbook = library_material("as4-3501")  # Table A.4: 1.6 g/cm^3 recorded in kg/m^3, Vf 63 %
    assert textbook.density_kg_per_m3 == 1600.0 and textbook.fiber_volume_fraction == pytest.approx(0.63)
    assert textbook.value("density").source_value == 1.6 and textbook.value("density").source_unit == "g/cm³"
    assert textbook.value("Vf").unit == "—" and textbook.value("Vf").key == "Vf"
    ncamp = library_material("im7-8552")  # the panel summary: density-LT 1.58 g/cm^3, Vf-LT 57.3 %
    assert ncamp.density_kg_per_m3 == pytest.approx(1580.0) and ncamp.fiber_volume_fraction == pytest.approx(0.573)
    assert ncamp.value("density").key == "density-LT" and ncamp.value("Vf").key == "Vf-LT"
    # Beside the values the analysis used, not among them: a deck header lists `values` and stays as it was.
    assert [v.role for v in ncamp.extra_values] == ["density", "Vf"]
    assert all(v.role not in ("density", "Vf") for v in ncamp.values)
    assert not any(item.startswith(("density", "fiber volume")) for item in ncamp.not_provided)


def test_a_record_without_a_density_or_a_fraction_says_so_instead_of_guessing():
    m = library_material("x840-z60-pw")  # a density, no fiber volume fraction
    assert m.density_kg_per_m3 == pytest.approx(1610.0) and m.fiber_volume_fraction is None
    assert any(item == "fiber volume fraction: none of Vf, Vf-LT, Vf-WT, Vf-nominal" for item in m.not_provided)
    nasa = library_material("im7-8552", "nasa-tm-20230001560-im7-8552-rt-measured-v1")  # neither
    assert nasa.density_kg_per_m3 is None and nasa.fiber_volume_fraction is None
    assert any(item.startswith("density: none of") for item in nasa.not_provided)
    assert nasa.extra_values == () and all(v.role not in ("density", "Vf") for v in nasa.values)


def test_fahrenheit_expansion_coefficients_convert_to_per_kelvin():
    assert (1e-6 / DEG_F) == pytest.approx(1.8e-6)


def test_the_offset_shear_strength_never_stands_in_for_f6():
    m = library_material("as4-8552s-pw")  # Reports only the 0.2% offset shear strength at RTD.
    assert m.lamina.strengths is None
    assert any("F6" in item for item in m.not_provided)
    assert all(v.key != "F12-offset" for v in m.values)


def test_datasets_without_an_elastic_input_set_are_refused_with_the_reason():
    with pytest.raises(ValueError, match="no elastic input set.*no Poisson ratio"):
        library_material("t650-35-976")
    with pytest.raises(ValueError, match="no elastic input set"):
        library_material("7781-e765", "ncamp-e765-2025-rtd-measured-v2")


def test_unknown_ids_name_what_exists():
    with pytest.raises(ValueError, match="unknown library material 'im7'.*'im7-8552'"):
        library_material("im7")
    with pytest.raises(ValueError, match="has no dataset 'nope'.*ncamp-im7-8552"):
        library_material("im7-8552", "nope")
    assert find_dataset("7781-e765")["datasetId"] == "agate-e765-2001-rtd-measured-v2"


def test_a_case_can_name_a_library_dataset_and_take_its_ply_thickness():
    case = load_case(CASES / "library-im7-8552-axial-check.toml")
    solution = solve_case(case)
    item = solution.library["material"]
    assert item.dataset_id == "ncamp-im7-8552-2019-rtd-measured-v1"
    assert solution.plies[0].thickness_m == pytest.approx(0.0072 * INCH, rel=1e-12)
    assert solution.plies[0].material.E1 == pytest.approx(23.51e6 * PSI, rel=1e-12)


def test_library_tables_cannot_mix_typed_values_and_need_a_thickness_when_the_dataset_has_none():
    case = load_case(CASES / "library-im7-8552-axial-check.toml")
    mixed = {**case, "material": {"library": "im7-8552", "E1": 150.0}}
    with pytest.raises(ValueError, match="unknown fields \\['E1'\\]"):
        solve_case(mixed)
    no_thickness = {**case, "material": {"library": "as4-3501"}}
    with pytest.raises(ValueError, match="has no ply thickness; give laminate.ply_thickness"):
        solve_case(no_thickness)
    typed = {**case, "material": {"E1": 150.0, "E2": 10.0, "G12": 5.0, "nu12": 0.3}}
    with pytest.raises(ValueError, match="laminate.ply_thickness is required"):
        solve_case(typed)


def test_a_temperature_change_needs_a_dataset_with_expansion_coefficients():
    case = load_case(CASES / "library-im7-8552-axial-check.toml")
    thermal = {**case, "applied": {**case["applied"], "delta_T": -100.0}}
    with pytest.raises(ValueError, match="delta_T needs alpha1 and alpha2"):
        solve_case(thermal)
    ok = {**thermal, "material": {"library": "as4-3501"}, "laminate": {"layup": [0], "ply_thickness": 0.25}}
    assert solve_case(ok).delta_T == -100.0
