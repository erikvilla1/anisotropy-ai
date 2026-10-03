"""The same case format drives homework checks and the interactive calculator."""

from pathlib import Path
import subprocess
import sys

import pytest

from anisotropy_engine.cases import engine_results, load_case

ENGINE = Path(__file__).parents[1]
REFERENCE = ENGINE / "validation/cases/daniel-ishai-problem-7-11.toml"
PRACTICE = ENGINE / "validation/cases/as4-zero-degree-axial-check.toml"


def calculator(*args):
    return subprocess.run([sys.executable, str(ENGINE / "examples/laminate_calculator.py"), *map(str, args)],
                          cwd=ENGINE, capture_output=True, text=True)


def test_default_calculator_keeps_the_reference_problem():
    run = calculator()
    assert run.returncode == 0, run.stderr
    assert "daniel-ishai-problem-7-11.toml" in run.stdout
    assert "Moduli: GPa; stress: MPa; thickness: mm" in run.stdout
    assert "60.2447" in run.stdout


def test_calculator_reads_a_practice_file_without_assuming_tsai_wu():
    run = calculator(PRACTICE)
    assert run.returncode == 0, run.stderr
    assert "R = 22.8" in run.stdout
    assert "Tsai-Wu skipped" in run.stdout


@pytest.mark.parametrize("applied", [
    "local_stress = [100.0, 0.0, 0.0]",
    "local_strain = [0.001, 0.0, 0.0]",
    "strains = [0.001, 0.0, 0.0, 0.0, 0.0, 0.0]",
])
def test_calculator_accepts_other_explicit_loading_modes(tmp_path, applied):
    path = tmp_path / "applied.toml"
    path.write_text(PRACTICE.read_text().replace("stress = [100.0, 0.0, 0.0]", applied))
    run = calculator(path)
    assert run.returncode == 0, run.stderr
    assert "First-ply failure, max_stress" in run.stdout


def test_calculator_runs_tsai_wu_when_the_case_records_its_assumption(tmp_path):
    path = tmp_path / "interaction.toml"
    path.write_text(PRACTICE.read_text().replace('units = "SI"', 'units = "SI"\nf12_star = -0.5'))
    run = calculator(path)
    assert run.returncode == 0, run.stderr
    assert "First-ply failure, tsai_wu: R = 22.8" in run.stdout


def test_calculator_requires_unit_review_for_unusual_moduli(tmp_path):
    path = tmp_path / "unit-mistake.toml"
    path.write_text(REFERENCE.read_text().replace("E1 = 145.0", "E1 = 140e9"))
    run = calculator(path)
    assert run.returncode != 0
    assert "enter moduli in GPa" in run.stderr
    assert "Mid-plane strains" not in run.stdout
    reviewed = calculator(path, "--allow-unusual-moduli")
    assert reviewed.returncode == 0, reviewed.stderr
    assert "WARNING" in reviewed.stdout


@pytest.mark.parametrize("kind, values", [
    ("loads", [1, 0, 0]), ("loads", [1, 0, 0, 0, 0, 0, 999]),
    ("strains", [0, 0, 0, 0, 0]), ("stress", [1, 0]),
    ("local_stress", [float("nan"), 0, 0]), ("local_strain", [0, float("inf"), 0]),
    ("forces_curvature", [1, 0, 0]), ("forces_curvature", [1, 0, 0, 0, 0, float("inf")]),
])
def test_case_vectors_cannot_be_truncated_or_defaulted(kind, values):
    case = load_case(REFERENCE)
    case["applied"] = {kind: values}
    with pytest.raises(ValueError, match=f"applied.{kind}"):
        engine_results(case)


@pytest.mark.parametrize("section, field", [("material", "E11"), ("laminate", "thickness"), ("applied", "load")])
def test_case_unknown_fields_are_rejected(section, field):
    case = load_case(REFERENCE)
    case[section][field] = 1
    with pytest.raises(ValueError, match="unknown fields"):
        engine_results(case)


def test_partial_strength_inputs_are_not_silently_discarded():
    case = load_case(REFERENCE)
    case["material"]["F1t"] = 2280
    with pytest.raises(ValueError, match="all five strengths"):
        engine_results(case)


def test_empty_layup_is_rejected():
    case = load_case(REFERENCE)
    case["laminate"]["layup"] = []
    with pytest.raises(ValueError, match="nonempty"):
        engine_results(case)


def test_calculator_prints_required_moments_and_forward_verification():
    run = calculator(ENGINE / "validation/cases/constructed-flat-cross-ply.toml")
    assert run.returncode == 0, run.stderr
    assert "required applied moments calculated; forward verification passed" in run.stdout
    moment_line = next(line for line in run.stdout.splitlines() if line.startswith("Moments M"))
    assert "[N*m/m]" in moment_line
    assert [float(v) for v in moment_line.split(":")[1].split()] == pytest.approx([-0.36, -0.18, 0], abs=1e-12)


def test_prescribed_curvature_case_converts_us_force_and_curvature_units():
    from anisotropy_engine.units import UNIT_SYSTEMS

    case = load_case(ENGINE / "validation/cases/constructed-prescribed-curvature.toml")
    base = engine_results(case)
    si, us = UNIT_SYSTEMS["SI"], UNIT_SYSTEMS["US"]
    case["units"] = "US"
    for key in ("E1", "E2", "G12"):
        case["material"][key] *= si["modulus"][0] / us["modulus"][0]
    case["laminate"]["ply_thickness"] *= si["length"][0] / us["length"][0]
    case["applied"]["forces_curvature"] = [
        value / us["N" if i < 3 else "kappa"][0]
        for i, value in enumerate(case["applied"]["forces_curvature"])
    ]
    converted = engine_results(case)
    for key, kind in (("moments", "M"), ("curvature", "kappa")):
        assert converted[key][0] * us[kind][0] == pytest.approx(base[key][0], rel=1e-10, abs=1e-12)
    assert converted["strain_global"][0] == pytest.approx(base["strain_global"][0], rel=1e-10)


THERMAL = ENGINE / "validation/cases/course-reader-5-9-as4-curing.toml"


def test_calculator_prints_thermal_resultants_and_residual_stresses():
    run = calculator(THERMAL)
    assert run.returncode == 0, run.stderr
    assert "Temperature change delta_T = -150 degC" in run.stdout
    n_line = next(line for line in run.stdout.splitlines() if line.startswith("Thermal forces N_T"))
    assert [float(v) for v in n_line.split(":")[1].split()] == pytest.approx([-7477.57, -7477.57, 0], abs=0.01)
    stress_rows = [line for line in run.stdout.splitlines() if line.strip().startswith("ply") and "|" in line][-8:]
    for row in stress_rows:  # every ply face: sigma_1 = -36.346 MPa, sigma_2 = +36.346 MPa
        assert [float(v) for v in row.split("|")[1].split()] == pytest.approx([-36.346, 36.346, 0], abs=1e-3)


def test_calculator_states_when_no_temperature_change_is_given():
    run = calculator(REFERENCE)
    assert "Temperature change: none given" in run.stdout
    assert "Thermal forces" not in run.stdout


def test_calculator_skips_failure_ratios_with_a_temperature_change(tmp_path):
    path = tmp_path / "thermal-with-strengths.toml"
    strengths = "alpha2 = 26.0e-6\nF1t = 2280.0\nF1c = 1725.0\nF2t = 57.0\nF2c = 228.0\nF6 = 76.0"
    path.write_text(THERMAL.read_text().replace("alpha2 = 26.0e-6", strengths)
                    .replace("loads = [0, 0, 0, 0, 0, 0]", "loads = [1000, 0, 0, 0, 0, 0]"))
    run = calculator(path)
    assert run.returncode == 0, run.stderr
    assert "strength ratios with residual thermal stresses are not implemented yet" in run.stdout
    assert "First-ply failure" not in run.stdout
