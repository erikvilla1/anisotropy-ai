"""Invalid inputs must stop a calculation instead of looking like a safe result."""

import math

import numpy as np
import pytest
from pydantic import ValidationError

from anisotropy_engine.failure import margin_of_safety, max_stress_ratio, tsai_wu_ratio
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads, ply_surfaces

# Daniel & Ishai (2006), Table A.4, AS4/3501-6; SI units.
STRENGTHS = Strengths(F1t=2280e6, F1c=1725e6, F2t=57e6, F2c=228e6, F6=76e6)
MATERIAL = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27, strengths=STRENGTHS)
PLY = Ply(material=MATERIAL, angle_deg=0, thickness_m=0.25e-3)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("component", range(3))
def test_failure_checks_reject_nonfinite_stress(bad, component):
    stress = np.zeros(3)
    stress[component] = bad
    with pytest.raises(ValueError, match="stress_12.*finite"):
        max_stress_ratio(stress, STRENGTHS)
    with pytest.raises(ValueError, match="stress_12.*finite"):
        tsai_wu_ratio(stress, STRENGTHS, -0.5)


@pytest.mark.parametrize("stress", [1.0, [1, 2], [1, 2, 3, 4], [[1], [2], [3]]])
def test_failure_checks_require_a_three_component_vector(stress):
    with pytest.raises(ValueError, match="stress_12.*3 components"):
        max_stress_ratio(stress, STRENGTHS)
    with pytest.raises(ValueError, match="stress_12.*3 components"):
        tsai_wu_ratio(stress, STRENGTHS, -0.5)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("name", ["eps0", "kappa"])
def test_ply_recovery_rejects_nonfinite_deformation(name, bad):
    values = {"eps0": np.zeros(3), "kappa": np.zeros(3)}
    values[name][1] = bad
    with pytest.raises(ValueError, match=f"{name}.*finite"):
        ply_surfaces([PLY], **values)


@pytest.mark.parametrize("model, values, typo", [
    (Loads, {"Ny": 100}, {"Nxx": 1000}),
    (Lamina, MATERIAL.model_dump(), {"nu_12": 0.3}),
    (Strengths, STRENGTHS.model_dump(), {"F6t": 80e6}),
    (Ply, PLY.model_dump(), {"angle": 45}),
])
def test_unknown_fields_are_rejected_even_with_other_valid_inputs(model, values, typo):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model(**values, **typo)


@pytest.mark.parametrize("factor", [float("nan"), float("inf"), -float("inf"), 0.9])
def test_safety_factor_must_be_finite_and_at_least_one(factor):
    with pytest.raises(ValueError, match="Factor of safety"):
        margin_of_safety(2.0, factor)


@pytest.mark.parametrize("ratio", [float("nan"), -float("inf"), -1.0])
def test_margin_rejects_invalid_strength_ratios(ratio):
    with pytest.raises(ValueError, match="Strength ratio"):
        margin_of_safety(ratio, 1.5)


def test_zero_stress_retains_an_unbounded_ratio_and_margin():
    assert max_stress_ratio([0, 0, 0], STRENGTHS) == (math.inf, "none")
    assert tsai_wu_ratio([0, 0, 0], STRENGTHS, -0.5) == math.inf
    assert margin_of_safety(math.inf, 1.5) == math.inf
    assert margin_of_safety(0.0, 1.5) == -1.0
