"""Lamina constants from fiber and matrix: the models' limits and identities, the refusals, and the case format.

The constituent values are Daniel and Ishai (2006) Tables A.2 and A.3 (pp. 375-376): IM7 carbon fiber and 977-3 epoxy.
The checks here are algebraic (limits, bounds, hand values); the course key is a validation case.
"""

import math

import pytest
from pydantic import ValidationError

from anisotropy_engine.cases import engine_results, load_case, solve_case
from anisotropy_engine.micromechanics import (
    Fiber, Matrix, combination_square_array, constrained_matrix_modulus, halpin_tsai, lamina_from_constituents, rule_of_mixtures, series_model,
)

IM7 = Fiber(E1=290e9, E2=21e9, G12=14e9, nu12=0.20)
EPOXY = Matrix(E=3.7e9, nu=0.35)
VF = 0.65


def test_rule_of_mixtures_and_series_model_are_the_voigt_and_reuss_bounds_of_every_other_model():
    for Vf in (0.3, 0.5, 0.65, 0.8):
        upper, lower = rule_of_mixtures(IM7.E2, EPOXY.E, Vf), series_model(IM7.E2, EPOXY.E, Vf)
        assert lower < upper
        for value in (halpin_tsai(IM7.E2, EPOXY.E, Vf, 1.0), halpin_tsai(IM7.E2, EPOXY.E, Vf, 2.0), combination_square_array(IM7.E2, EPOXY.E, Vf),
                      series_model(IM7.E2, constrained_matrix_modulus(EPOXY), Vf)):
            assert lower <= value <= upper


def test_halpin_tsai_limits_are_the_series_and_parallel_models():
    assert halpin_tsai(IM7.E2, EPOXY.E, VF, 0.0) == pytest.approx(series_model(IM7.E2, EPOXY.E, VF), rel=1e-12)
    assert halpin_tsai(IM7.E2, EPOXY.E, VF, 1e9) == pytest.approx(rule_of_mixtures(IM7.E2, EPOXY.E, VF), rel=1e-6)
    # Daniel and Ishai Eq. 3.37: for xi = 1 the transverse modulus is Em [(1 + Vf) E2f + Vm Em] / [Vm E2f + (1 + Vf) Em]
    Vm = 1 - VF
    closed = EPOXY.E * ((1 + VF) * IM7.E2 + Vm * EPOXY.E) / (Vm * IM7.E2 + (1 + VF) * EPOXY.E)
    assert halpin_tsai(IM7.E2, EPOXY.E, VF, 1.0) == pytest.approx(closed, rel=1e-12)


def test_every_model_returns_the_constituent_at_the_ends_of_the_volume_ratio():
    for model in (lambda f, m, v: rule_of_mixtures(f, m, v), series_model, lambda f, m, v: halpin_tsai(f, m, v, 1.5), combination_square_array):
        assert model(IM7.E2, EPOXY.E, 1 - 1e-9) == pytest.approx(IM7.E2, rel=1e-6)
        assert model(IM7.E2, EPOXY.E, 1e-9) == pytest.approx(EPOXY.E, rel=1e-6)


def test_combination_model_matches_its_derivation_by_hand():
    side = math.sqrt(VF)
    series_column = IM7.E2 * EPOXY.E / (EPOXY.E * side + IM7.E2 * (1 - side))
    assert combination_square_array(IM7.E2, EPOXY.E, VF) == pytest.approx(EPOXY.E * (1 - side) + side * series_column, rel=1e-12)
    assert combination_square_array(IM7.E2, EPOXY.E, VF) == pytest.approx(9.600e9, rel=1e-3)  # by hand: 3.7 (1 - 0.80623) + 0.80623 * 11.018 GPa


def test_the_constrained_matrix_modulus_is_em_over_one_minus_nu_squared():
    assert constrained_matrix_modulus(EPOXY) == pytest.approx(3.7e9 / (1 - 0.35**2))
    assert EPOXY.G == pytest.approx(3.7e9 / (2 * 1.35))  # Table A.3 lists 1.37 GPa for 977-3


def test_lamina_from_constituents_uses_the_stated_models_and_builds_a_valid_lamina():
    result = lamina_from_constituents(IM7, EPOXY, VF, "series_constrained", "series")
    assert result.E1 == pytest.approx(0.65 * 290e9 + 0.35 * 3.7e9)
    assert result.nu12 == pytest.approx(0.65 * 0.20 + 0.35 * 0.35)
    assert result.E2 == pytest.approx(series_model(21e9, 3.7e9 / (1 - 0.35**2), VF))
    assert result.G12 == pytest.approx(series_model(14e9, EPOXY.G, VF))
    assert result.lamina.E1 == result.E1 and result.lamina.nu21 == pytest.approx(result.nu12 * result.E2 / result.E1)
    assert result.Vm == pytest.approx(0.35) and result.xi_E2 is None
    with_xi = lamina_from_constituents(IM7, EPOXY, VF, "halpin_tsai", "halpin_tsai", xi_E2=2.0, xi_G12=1.0)
    assert with_xi.E2 == pytest.approx(halpin_tsai(21e9, 3.7e9, VF, 2.0)) and with_xi.G12 == pytest.approx(halpin_tsai(14e9, EPOXY.G, VF, 1.0))


def test_isotropic_fiber_has_equal_moduli_and_the_isotropic_shear_modulus():
    glass = Fiber.isotropic(73e9, 0.23)
    assert glass.E1 == glass.E2 == 73e9 and glass.G12 == pytest.approx(73e9 / (2 * 1.23))


@pytest.mark.parametrize("kwargs, message", [
    (dict(Vf=0.0), "strictly between 0 and 1"),
    (dict(Vf=1.0), "strictly between 0 and 1"),
    (dict(E2_model="halpin_tsai"), "xi_E2 is required"),
    (dict(G12_model="halpin_tsai"), "xi_G12 is required"),
    (dict(xi_E2=1.0), "belongs to the halpin_tsai model only"),
    (dict(E2_model="voigt"), "E2_model must be one of"),
    (dict(G12_model="series_constrained"), "G12_model must be one of"),
    (dict(E2_model="halpin_tsai", xi_E2=-1.0), "zero or positive"),
])
def test_unstated_or_impossible_choices_are_refused_by_name(kwargs, message):
    arguments = dict(fiber=IM7, matrix=EPOXY, Vf=VF, E2_model="series", G12_model="series")
    arguments.update(kwargs)
    with pytest.raises(ValueError, match=message):
        lamina_from_constituents(**arguments)


def test_constituent_models_reject_impossible_constants():
    with pytest.raises(ValidationError):
        Fiber(E1=-1.0, E2=21e9, G12=14e9, nu12=0.2)
    with pytest.raises(ValidationError, match="between -1 and 0.5"):
        Matrix(E=3.7e9, nu=0.6)
    with pytest.raises(ValidationError):
        Matrix(E=3.7e9, nu=0.35, G=1.37e9)  # the shear modulus follows from E and nu; it is not an input


# --- the case format --------------------------------------------------------------------------------------------

CASE = """
title = "constituents test"
units = "SI"
[material]
fiber = {{E1 = 290.0, E2 = 21.0, G12 = 14.0, nu12 = 0.20}}
matrix = {{E = 3.7, nu = 0.35}}
Vf = 0.65
E2_model = "{e2}"
G12_model = "{g12}"
{extra}
[laminate]
layup = [0]
ply_thickness = 0.125
[applied]
loads = [0, 0, 0, 0, 0, 0]
[expected]
tolerance = 0.001
"""


def case_text(e2="series_constrained", g12="series", extra=""):
    import tomllib

    from anisotropy_engine.cases import validate_case_inputs

    case = tomllib.loads(CASE.format(e2=e2, g12=g12, extra=extra))
    validate_case_inputs(case)
    return case


def test_a_case_may_state_its_material_by_constituents_and_reports_the_lamina_constants():
    case = case_text()
    solution = solve_case(case)
    assert set(solution.constituents) == {"material"}
    results = engine_results(case)
    assert results["E1"][0] == pytest.approx(189.795, rel=1e-6)  # GPa
    assert results["E2"][0] == pytest.approx(series_model(21.0, 3.7 / (1 - 0.35**2), 0.65), rel=1e-9)
    assert results["G12"][0] == pytest.approx(series_model(14.0, 3.7 / 2.7, 0.65), rel=1e-9)
    assert results["nu12"][0] == pytest.approx(0.2525) and results["nu21"][0] == pytest.approx(0.2525 * results["E2"][0] / results["E1"][0])
    assert results["Q11"][0] > 0 and results["A11"][0] > 0  # the laminate path runs on the derived lamina


def test_a_constituent_material_may_carry_measured_strengths_and_expansion_coefficients():
    case = case_text(extra="F1t = 2000.0\nF1c = 1500.0\nF2t = 50.0\nF2c = 200.0\nF6 = 80.0\nalpha1 = -0.5e-6\nalpha2 = 30e-6")
    lamina = solve_case(case).materials["material"]
    assert lamina.strengths is not None and lamina.strengths.F1t == pytest.approx(2000e6) and lamina.thermal_expansion.alpha2 == pytest.approx(30e-6)


@pytest.mark.parametrize("e2, g12, extra, message", [
    ("halpin_tsai", "series", "", "xi_E2 is required"),
    ("series", "series", "xi_G12 = 1.0", "belongs to the halpin_tsai model only"),
    ("series", "series", "E1 = 190.0", "unknown fields"),
    ("series", "series", "library = \"im7-8552\"", "unknown fields"),
])
def test_constituent_case_tables_are_checked_by_name(e2, g12, extra, message):
    with pytest.raises(ValueError, match=message):
        case_text(e2, g12, extra)


def test_the_homework_case_file_loads_and_states_its_sources():
    from pathlib import Path

    case = load_case(Path(__file__).parents[1] / "validation" / "cases" / "se142-hw5-p2-micromechanics-im7-977-3-vf-0-65.toml")
    assert "Table A.2" in case["source"] and case["material"]["Vf"] == 0.65
