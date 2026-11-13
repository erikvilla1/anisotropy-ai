"""A laminate problem stated with each value's own unit (ADR-0060): the conversion with the engine's table, the case the engine solves,
the results in the units asked for, the template's sentences from the engine's numbers, and the model behind the setting with the
number guard. Nothing here calls a model: a stub plays it, as api/tests/test_assistant.py does."""

import pytest
from fastapi.testclient import TestClient

from anisotropy_engine.cases import engine_results, validate_case_inputs
from anisotropy_engine.library import load_library
from anisotropy_engine.units import INCH, LBF, PSI, UNIT_SYSTEMS
from anisotropy_api.assistant import ClaudeAssistant, TemplateAssistant, number_guard
from anisotropy_api.laminate_problems import _words, case_of, sentences_of
from anisotropy_api.main import app
from anisotropy_api.schemas import LaminateProblem

from test_assistant import StubClient

client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})  # no lifespan: nothing is recorded here, the template writes
ENDPOINT = "/v1/laminates/solve"
MSI = 1e6 * PSI
KSI = 1e3 * PSI


def quantity(value: float, unit: str) -> dict:
    return {"value": value, "unit": unit}


def zero_loads(**given: dict) -> dict:
    loads = {name: quantity(0.0, "N/m" if name.startswith("N") else "N*m/m") for name in ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")}
    return {**loads, **given}


# The homework problem of the chat's mock-up: AS4/3501-6 typed from Daniel & Ishai's Table A.4, [0/45/-45/90]s of 0.125 mm plies,
# Nx = 100 N/mm. E2 is typed in MPa and the strengths in MPa while E1 is in GPa, as a student mixes them.
def homework(report_units: str = "SI", **changes) -> dict:
    problem = {
        "title": "Homework: [0/45/-45/90]s under Nx = 100 N/mm",
        "material": {"name": "AS4/3501-6", "E1": quantity(147.0, "GPa"), "E2": quantity(10300.0, "MPa"), "G12": quantity(7.0, "GPa"), "nu12": 0.27,
                     "F1t": quantity(2280.0, "MPa"), "F1c": quantity(1725.0, "MPa"), "F2t": quantity(57.0, "MPa"), "F2c": quantity(228.0, "MPa"),
                     "F6": quantity(76.0, "MPa"), "source": "Daniel & Ishai (2006) Table A.4"},
        "layup": [0, 45, -45, 90, 90, -45, 45, 0], "layup_notation": "[0/45/-45/90]s",
        "ply_thickness": quantity(0.125, "mm"),
        "loads": zero_loads(Nx=quantity(100.0, "N/mm")),
        "f12_star": -0.5,
        "report_units": report_units,
    }
    problem.update(changes)
    return problem


# The same problem as a case file in SI, the format the validation cases use: what the chat's answer must equal.
SI_CASE = {
    "title": "the same problem as a case", "units": "SI", "f12_star": -0.5,
    "material": {"E1": 147.0, "E2": 10.3, "G12": 7.0, "nu12": 0.27, "F1t": 2280.0, "F1c": 1725.0, "F2t": 57.0, "F2c": 228.0, "F6": 76.0},
    "laminate": {"layup": [0, 45, -45, 90, 90, -45, 45, 0], "ply_thickness": 0.125},
    "applied": {"loads": [100e3, 0, 0, 0, 0, 0]},
}


def solve(problem: dict) -> dict:
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------------------------------------ the conversion and the case

def test_every_typed_value_lands_in_the_case_in_the_reporting_units():
    case = case_of(LaminateProblem.model_validate(homework()))
    validate_case_inputs(case)
    assert case["units"] == "SI" and case["material"]["E1"] == 147.0 and case["material"]["E2"] == pytest.approx(10.3, rel=1e-12)
    assert case["material"]["F2t"] == 57.0 and case["laminate"]["ply_thickness"] == 0.125 and case["applied"]["loads"] == [100e3, 0, 0, 0, 0, 0]
    assert case["f12_star"] == -0.5 and case["laminate"]["layup"] == [0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0]
    us = case_of(LaminateProblem.model_validate(homework("US")))
    assert us["units"] == "US" and us["material"]["E1"] == pytest.approx(147e9 / MSI) and us["material"]["F6"] == pytest.approx(76e6 / KSI)
    assert us["laminate"]["ply_thickness"] == pytest.approx(0.125e-3 / INCH) and us["applied"]["loads"][0] == pytest.approx(100e3 * INCH / LBF)


def test_the_answer_equals_the_case_runner_on_the_same_problem_in_si():
    expected = engine_results(SI_CASE)
    answer = solve(homework())
    assert answer["report_units"] == "SI" and answer["units"] == {"modulus": "GPa", "stress": "MPa", "length": "mm", "N": "N/m", "M": "N*m/m",
                                                                    "kappa": "1/m", "A": "MN/m", "B": "kN", "D": "N*m", "areal_mass": "kg/m^2", "delta_T": "degC"}
    for key in ("A11", "A12", "A66", "D11", "D16", "Ex", "nu_xy", "total_thickness", "fpf_ratio_max_stress", "fpf_ratio_tsai_hill", "fpf_ratio_tsai_wu"):
        assert answer["results"][key] == pytest.approx(float(expected[key][0]), rel=1e-12), key
    assert answer["results"]["strain_global"] == pytest.approx([float(v) for v in expected["strain_global"][0]], rel=1e-12)
    for row, expected_row in zip(answer["results"]["ply_stress_local"], expected["ply_stress_local"][0], strict=True):
        assert row == pytest.approx([float(v) for v in expected_row], rel=1e-12, abs=1e-9)
    assert answer["criteria"] == ["max_stress", "tsai_hill", "tsai_wu"]  # no strain limits: maximum strain is not evaluated (ADR-0021)
    assert answer["results"]["fpf_ply_tsai_wu"] == 4.0 and answer["results"]["fpf_forces_max_stress"][0] == pytest.approx(347449.9858, rel=1e-9)
    assert answer["summary"]["kind"] == "quasi-isotropic" and answer["summary"]["symmetric"] and answer["summary"]["balanced"]
    assert answer["summary"]["areal_mass_kg_per_m2"] is None and "no density" in answer["summary"]["areal_mass_missing"]
    assert answer["material"] is None and answer["case"]["material"]["E2"] == pytest.approx(10.3)
    assert "areal_mass" not in answer["results"]
    assert answer["run_id"] is None  # nothing is recorded without the lifespan


def test_the_same_problem_reported_in_each_system_is_the_same_answer_converted():
    si = solve(homework())["results"]
    for system, scale in (("mm-MPa", {"modulus": 1e3, "stress": 1.0, "N": 1e-3, "A": 1e3, "D": 1e3}),
                          ("US", {"modulus": 1e9 / MSI, "stress": 1e6 / KSI, "N": INCH / LBF, "A": 1e6 * INCH / (1e6 * LBF), "D": 1 / (LBF * INCH)}),
                          ("psi", {"modulus": 1e9 / PSI, "stress": 1e6 / PSI, "N": INCH / LBF, "A": 1e6 * INCH / LBF, "D": 1 / (LBF * INCH)})):
        answer = solve(homework(system))
        results = answer["results"]
        assert answer["units"]["modulus"] == UNIT_SYSTEMS[system]["modulus"][1]
        assert results["Ex"] == pytest.approx(si["Ex"] * scale["modulus"], rel=1e-12)
        assert results["A11"] == pytest.approx(si["A11"] * scale["A"], rel=1e-12)
        assert results["D11"] == pytest.approx(si["D11"] * scale["D"], rel=1e-12)
        assert results["ply_stress_local"][3][1] == pytest.approx(si["ply_stress_local"][3][1] * scale["stress"], rel=1e-12)
        assert results["fpf_forces_max_stress"][0] == pytest.approx(si["fpf_forces_max_stress"][0] * scale["N"], rel=1e-12)
        assert results["strain_global"] == pytest.approx(si["strain_global"], rel=1e-12)  # strain has no unit
        assert results["fpf_ratio_tsai_wu"] == pytest.approx(si["fpf_ratio_tsai_wu"], rel=1e-12)  # nor has a ratio
    mm = solve(homework("mm-MPa"))
    assert mm["case"]["material"]["E1"] == pytest.approx(147e3) and mm["case"]["applied"]["loads"][0] == pytest.approx(100.0)
    assert mm["units"] == {"modulus": "MPa", "stress": "MPa", "length": "mm", "N": "N/mm", "M": "N*mm/mm", "kappa": "1/mm", "A": "N/mm", "B": "N",
                           "D": "N*mm", "areal_mass": "kg/m^2", "delta_T": "degC"}


def test_maximum_strain_is_evaluated_only_when_limits_from_the_strengths_are_asked_for():
    # The choice is stated on the material, as the case format states it (ADR-0021); the engine derives the five limits.
    typed = solve(homework(material={**homework()["material"], "strain_limits": "from-strengths"}))
    assert typed["criteria"] == ["max_stress", "max_strain", "tsai_hill", "tsai_wu"]
    assert typed["case"]["material"]["strain_limits"] == "from-strengths"
    expected = engine_results({**SI_CASE, "material": {**SI_CASE["material"], "strain_limits": "from-strengths"}})
    for key in ("fpf_ratio_max_strain", "fpf_ply_max_strain", "fpf_ratio_tsai_wu"):
        assert typed["results"][key] == pytest.approx(float(expected[key][0]), rel=1e-12), key
    assert typed["facts"]["max_strain_mode"].endswith("strain") and "maximum strain R = " in typed["prose"][-1]
    assert number_guard(" ".join(typed["prose"]), typed["facts"]).ok
    library = solve({**homework(material={"library": "im7-8552", "strain_limits": "from-strengths"}), "ply_thickness": None})
    assert library["criteria"] == ["max_stress", "max_strain", "tsai_hill", "tsai_wu"] and library["case"]["material"]["strain_limits"] == "from-strengths"
    without = {k: v for k, v in homework()["material"].items() if not k.startswith("F")}
    refused = client.post(ENDPOINT, json=homework(material={**without, "strain_limits": "from-strengths"}))
    assert refused.status_code == 422 and "needs all five strengths" in refused.text
    assert client.post(ENDPOINT, json=homework(material={**homework()["material"], "strain_limits": "measured"})).status_code == 422


def test_a_library_material_brings_its_ply_thickness_strengths_density_and_citation():
    problem = homework(material={"library": "im7-8552"})
    del problem["ply_thickness"]
    answer = solve(problem)
    assert answer["material"]["material_id"] == "im7-8552" and answer["material"]["ply_thickness_m"] is not None
    assert answer["case"]["material"] == {"library": "im7-8552"} and "ply_thickness" not in answer["case"]["laminate"]
    assert answer["results"]["total_thickness"] == pytest.approx(8 * answer["material"]["ply_thickness_m"] * 1e3, rel=1e-12)
    assert answer["summary"]["areal_mass_kg_per_m2"] == pytest.approx(answer["results"]["areal_mass"], rel=1e-12)
    assert answer["criteria"] == ["max_stress", "tsai_hill", "tsai_wu"]
    assert "F1t" in answer["facts"] and answer["facts"]["F1t"] > 0


def test_typed_constants_without_strengths_give_no_failure_and_say_so():
    material = {k: v for k, v in homework()["material"].items() if not k.startswith("F")}
    answer = solve(homework(material=material))
    assert answer["criteria"] == [] and "fpf_ratio_max_stress" not in answer["results"]
    assert answer["facts"]["earliest"] is None and "F1t" not in answer["facts"]
    assert answer["prose"][-1] == "No first-ply failure is predicted: the material has no strengths."


# ------------------------------------------------------------------------------------------------ refusals (ADR-0003)

@pytest.mark.parametrize("changes, where, words", [
    ({"material": {**homework()["material"], "E1": quantity(147.0, "mm")}}, "material.E1", "mm is not a modulus unit"),
    ({"material": {**homework()["material"], "F6": quantity(76.0, "bar")}}, "material.F6", "unknown unit 'bar' for stress"),
    ({"ply_thickness": quantity(0.125, "MPa")}, "ply_thickness", "MPa is not a length unit"),
    ({"loads": zero_loads(Nx=quantity(100.0, "N"))}, "loads.Nx", "unknown unit 'N' for N"),
    ({"loads": zero_loads(Mx=quantity(1.0, "N/mm"))}, "loads.Mx", "N/mm is not a M unit"),
])
def test_a_unit_of_the_wrong_dimension_or_an_unknown_one_is_refused_by_field(changes, where, words):
    response = client.post(ENDPOINT, json=homework(**changes))
    assert response.status_code == 422, response.text
    assert response.json()["detail"].startswith(where + ": ") and words in response.json()["detail"]


def test_the_request_contract_refuses_half_a_material_a_missing_load_and_a_unit_system_the_engine_lacks():
    four = {k: v for k, v in homework()["material"].items() if k != "F6"}
    response = client.post(ENDPOINT, json=homework(material=four))
    assert response.status_code == 422 and "all five strengths" in response.text
    loads = homework()["loads"]
    del loads["Mxy"]
    response = client.post(ENDPOINT, json=homework(loads=loads))
    assert response.status_code == 422 and any(e["loc"][-1] == "Mxy" for e in response.json()["detail"])
    response = client.post(ENDPOINT, json=homework("cgs"))
    assert response.status_code == 422 and any("report_units" in e["loc"] for e in response.json()["detail"])
    response = client.post(ENDPOINT, json=homework(ply_thickness=quantity(-0.125, "mm")))
    assert response.status_code == 422, response.text  # the engine refuses it; the message is the engine's


def test_a_problem_without_a_ply_thickness_needs_a_dataset_that_records_one():
    problem = homework()
    del problem["ply_thickness"]
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422 and "ply_thickness is required" in response.json()["detail"]


def test_every_dataset_the_material_list_offers_is_solved_and_the_rest_are_refused_for_a_range():
    """The one material list of the calculator and the laminate workspace (lib/material-library-options.ts, ADR-0060 amendment 2) offers
    every dataset with an elastic input set whose elastic inputs and ply thickness are single values. Each one solves here, picked by its
    dataset; every dataset the list leaves out is refused for a range or a bound, the reason it is left out."""
    offered, left_out = [], []
    for d in load_library()["datasets"]:
        if not d["elasticInputs"]:
            continue
        props = {p["key"]: p for p in d["properties"]}
        keys = [*d["elasticInputs"].values(), next((k for k in ("tply", "tply-WT") if k in props), None)]
        single = all("valueEnd" not in props[k] and "valueQualifier" not in props[k] for k in keys if k)
        problem = homework(material={"library": d["materialId"], "dataset": d["datasetId"]})
        response = client.post(ENDPOINT, json=problem)
        if single:
            assert response.status_code == 200, (d["datasetId"], response.text)
            offered.append(d["datasetId"])
        else:
            assert response.status_code == 422 and "is a range or a bound" in response.json()["detail"], (d["datasetId"], response.text)
            left_out.append(d["datasetId"])
    assert offered and "agate-e765-2001-rtd-measured-v2" in left_out


# ------------------------------------------------------------------------------------------------ the words

def test_the_templates_sentences_quote_only_the_engines_numbers():
    answer = solve(homework())
    assert answer["writer"] == "template" and answer["model"] is None and not answer["withheld"] and answer["reason"] is None
    prose = answer["prose"]
    assert prose[0].startswith("The stack [0/45/-45/90/90/-45/45/0] of 8 plies is 1 mm thick, quasi-isotropic, symmetric and balanced, so no in-plane load bends it")
    assert prose[1] == ("Under Nx = 100000 N/m the mid-plane strain is eps_x = 1719 microstrain (it stretches along x), eps_y = -497 microstrain "
                        "(it shortens along y), gamma_xy = 0 (no shear strain), and it does not curve.")
    assert prose[2] == "Its in-plane moduli are Ex = 58.18 GPa, Ey = 58.18 GPa, Gxy = 22.56 GPa and nu_xy = 0.2892."
    assert prose[3] == "By Tsai-Wu, ply 4 (90°) fails first, by the interaction of its stresses, when every load reaches 3.207 times its value: Nx = 320700 N/m."
    assert prose[4] == "By maximum stress that ply fails in transverse tension, when its sigma2 reaches F2t = 57 MPa."
    assert prose[5] == "The other criteria give maximum stress R = 3.474 (ply 4), Tsai-Hill R = 3.434 (ply 4)."
    guard = number_guard(" ".join(prose), answer["facts"])
    assert guard.ok, guard.offending
    assert answer["facts"]["eps_x_microstrain"] == 1719.0 and answer["facts"]["F2t"] == 57.0
    assert answer["facts"]["max_stress_sigma2_at_failure"] == 57.0  # the failing face's stress at failure is the strength it reaches
    assert answer["results"]["ply_stress_local"][3][1] == pytest.approx(16.405, abs=5e-4)  # and at the applied load, in the table


def test_in_mm_mpa_the_lowest_ratio_governs_and_the_maximum_stress_mode_names_the_stress_against_its_strength():
    problem = homework("mm-MPa")
    del problem["f12_star"]  # no Tsai-Wu: Tsai-Hill's R is the lowest, and the maximum-stress mode says which stress limits the ply
    answer = solve(problem)
    assert answer["criteria"] == ["max_stress", "tsai_hill"]
    prose = answer["prose"]
    assert prose[1].startswith("Under Nx = 100 N/mm the mid-plane strain is eps_x = 1719 microstrain (it stretches along x)")
    assert prose[3] == "By Tsai-Hill, ply 4 (90°) fails first, by the interaction of its stresses, when every load reaches 3.434 times its value: Nx = 343.4 N/mm."
    assert prose[4] == "By maximum stress that ply fails in transverse tension, when its sigma2 reaches F2t = 57 MPa."
    assert prose[5] == "The other criteria give maximum stress R = 3.474 (ply 4)."
    assert number_guard(" ".join(prose), answer["facts"]).ok
    assert sentences_of(answer["facts"]) == prose


@pytest.mark.parametrize(("value", "written"), [
    (100000.0, "100000"), (320700.0, "320700"), (1719.0, "1719"), (-497.0, "-497"), (0.2892, "0.2892"), (3.22, "3.22"), (0.001, "0.001"),
    (1.5e6, "1.5e+06"), (1.234e-5, "1.234e-05"), (999999.7, "1e+06"), (0.0, "0"), (None, "unbounded"),
])
def test_a_sentence_writes_the_sites_one_number_rule_in_ascii(value, written):
    """Plain digits from 0.001 up to a million and an exponent outside, four figures, as lib/number-format.ts prints them; the page
    turns the exponent into "x 10^n" and the sign into a minus (ADR-0091 amendment 1). The guard reads every form back."""
    assert _words(value) == written
    if value is not None:
        assert number_guard(f"It is {written}.", {"v": value}).ok


def test_an_unsymmetric_stack_is_said_to_bend_and_curve():
    answer = solve(homework(layup=[0, 90], layup_notation="[0/90]"))
    assert answer["summary"]["symmetric"] is False and answer["summary"]["coupling"]["extension_bending"] is True
    assert "its B matrix is not zero, so an in-plane load also bends it" in answer["prose"][0]
    assert "it curves: kappa_x = " in answer["prose"][1] and " per m" in answer["prose"][1]
    guard = number_guard(" ".join(answer["prose"]), answer["facts"])
    assert guard.ok, guard.offending
    assert answer["facts"]["kappa_x"] != 0 and answer["facts"]["kappa_xy"] == 0


def test_the_model_behind_the_setting_rewrites_the_answer_and_the_guard_withholds_an_invented_number():
    answer = solve(homework())
    facts, template = answer["facts"], answer["prose"]
    draft = ClaudeAssistant("claude-opus-5-5", client=StubClient("Ply 4 (90 degrees) fails first by Tsai-Wu at 3.207 times the load, Nx = 3.207e+05 N/m.")).explain_laminate(facts, template)
    assert draft.writer == "anthropic" and draft.model == "claude-opus-5-5" and not draft.withheld
    assert draft.prose == ("Ply 4 (90 degrees) fails first by Tsai-Wu at 3.207 times the load, Nx = 3.207e+05 N/m.",)
    invented = ClaudeAssistant("m", client=StubClient("Ply 4 fails first at 3.2 times the load, about 320 N/mm.")).explain_laminate(facts, template)
    assert invented.withheld and invented.writer == "template" and tuple(invented.prose) == tuple(template) and "320" in invented.offending
    assert TemplateAssistant().explain_laminate(facts, template).prose == tuple(template)


def test_the_app_uses_the_assistant_the_settings_name():
    stub = ClaudeAssistant("claude-opus-5-5", client=StubClient("The stack of 8 plies is quasi-isotropic and 1 mm thick."))
    app.state.assistant = stub
    try:
        answer = solve(homework())
    finally:
        del app.state.assistant
    assert answer["writer"] == "anthropic" and answer["model"] == "claude-opus-5-5" and answer["prose"] == ["The stack of 8 plies is quasi-isotropic and 1 mm thick."]


# ------------------------------------------------------------------------------------------------ a temperature change (ADR-0017)

# The constructed cooling case of engine/validation/cases/constructed-cross-ply-cooling-alone-first-ply-failure.toml, typed as the chat
# types it: alpha in 1e-6 per degree, the change in degC or degF, no load.
def cooled(delta_T: dict, **changes) -> dict:
    problem = homework(layup=[0, 90, 90, 0], layup_notation="[0/90]s", ply_thickness=quantity(0.25, "mm"), loads=zero_loads(), delta_T=delta_T)
    problem["material"] = {**problem["material"], "alpha1": quantity(-1.0, "1e-6/degC"), "alpha2": quantity(25.0, "1e-6/degC")}
    problem.update(changes)
    return problem


def test_a_temperature_change_alone_fails_its_first_ply_at_r_times_the_change_as_the_case_runner_says():
    answer = solve(cooled(quantity(-120.0, "degC")))
    case = {"title": "the cooling case", "units": "SI", "f12_star": -0.5, "laminate": {"layup": [0, 90, 90, 0], "ply_thickness": 0.25},
            "material": {"E1": 147.0, "E2": 10.3, "G12": 7.0, "nu12": 0.27, "F1t": 2280.0, "F1c": 1725.0, "F2t": 57.0, "F2c": 228.0, "F6": 76.0,
                         "alpha1": -1.0e-6, "alpha2": 25.0e-6},
            "applied": {"loads": [0, 0, 0, 0, 0, 0], "delta_T": -120.0}}
    validate_case_inputs(case)
    expected = engine_results(case)
    assert answer["results"]["fpf_delta_T_max_stress"] == pytest.approx(expected["fpf_delta_T_max_stress"][0], rel=1e-12)
    assert answer["results"]["fpf_delta_T_max_stress"] == pytest.approx(-235.8124400, rel=1e-8)  # the constructed case's closed form
    facts = answer["facts"]
    assert facts["thermal_only"] is True and facts["delta_T"] == -120.0 and facts["max_stress_delta_T_at_failure"] == -235.8
    assert answer["units"]["delta_T"] == "degC"
    assert answer["prose"][1].startswith("Under no load and a temperature change of -120 degC the mid-plane strain is eps_x = -130.6 microstrain")
    assert "when the temperature change reaches 1.93 times its value: -231.5 degC." in answer["prose"][3]  # Tsai-Wu governs
    guard = number_guard(" ".join(answer["prose"]), facts)
    assert guard.ok, guard.offending


def test_a_change_in_fahrenheit_is_the_same_change_and_reports_in_its_system():
    celsius = solve(cooled(quantity(-120.0, "degC")))
    fahrenheit = solve(cooled(quantity(-216.0, "degF")))
    assert fahrenheit["results"]["fpf_delta_T_max_stress"] == pytest.approx(celsius["results"]["fpf_delta_T_max_stress"], rel=1e-12)
    in_us = solve(cooled(quantity(-120.0, "degC"), report_units="US"))
    assert in_us["units"]["delta_T"] == "degF" and in_us["results"]["fpf_delta_T_max_stress"] == pytest.approx(-235.8124400 * 9 / 5, rel=1e-8)


def test_with_a_load_the_temperature_change_is_held_while_the_loads_grow():
    answer = solve(cooled(quantity(-120.0, "degC"), loads=zero_loads(Nx=quantity(100.0, "kN/m"))))
    assert answer["facts"]["thermal_only"] is False and not any("delta_T" in key for key in answer["results"] if key.startswith("fpf"))
    assert answer["prose"][3].endswith("The temperature change of -120 degC is held at its value while the loads grow.")


@pytest.mark.parametrize("material, delta_T, words", [
    ({"alpha2": None}, quantity(-120.0, "degC"), "give alpha1 and alpha2 together"),
    ({"alpha1": quantity(-1.0, "1e-6/degC"), "alpha2": quantity(25.0, "MPa")}, quantity(-120.0, "degC"), "material.alpha2"),
])
def test_half_an_expansion_or_one_of_the_wrong_dimension_is_refused(material, delta_T, words):
    problem = cooled(delta_T)
    problem["material"] = {k: v for k, v in {**problem["material"], **material}.items() if v is not None}
    refused = client.post(ENDPOINT, json=problem)
    assert refused.status_code == 422 and words in str(refused.json()["detail"])


def test_a_temperature_change_needs_the_materials_expansion():
    refused = client.post(ENDPOINT, json=homework(delta_T=quantity(-120.0, "degC")))  # typed constants without alpha
    assert refused.status_code == 422 and "needs alpha1 and alpha2" in str(refused.json()["detail"])
    wrong = client.post(ENDPOINT, json=cooled(quantity(-120.0, "MPa")))
    assert wrong.status_code == 422 and "delta_T" in str(wrong.json()["detail"])
