"""The array forms a finite element kernel calls once per section (ADR-0069) give exactly what the per-ply functions give, row by row:
the same ratio to the last bit and the same governing mode."""

import math

import numpy as np
import pytest

from anisotropy_engine.failure import CRITERIA, face_strength_ratio, scaled_strength_ratios
from anisotropy_engine.lamina import Lamina, StrainLimits, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import PlySurface, ply_surface_arrays, ply_surfaces

MATERIAL = Lamina(E1=162e9, E2=9e9, G12=4.7e9, nu12=0.316, strengths=Strengths(F1t=2558e6, F1c=1731e6, F2t=64e6, F2c=286e6, F6=91e6),
                  strain_limits=StrainLimits(eps1t=0.016, eps1c=0.011, eps2t=0.0071, eps2c=0.032, gamma12=0.019))
ZERO = np.zeros(3)


def surface(stress_12):
    return PlySurface(0, 0.0, 0.0, ZERO, ZERO, ZERO, np.asarray(stress_12, dtype=float))


def states() -> np.ndarray:
    """Random states over twelve decades, with zero components, unloaded rows, a negative zero and limits that overflow."""
    rng = np.random.default_rng(7)
    v = rng.normal(size=(3000, 3)) * 10 ** rng.uniform(-3, 9, size=(3000, 3))
    v[rng.random((3000, 3)) < 0.2] = 0.0
    v[:20] = 0.0
    v[20:30] = [1e-320, 0.0, 0.0]
    v[30:40] = [-1e-320, 0.0, -1e-320]
    v[40:50, 0] = -0.0
    return v


@pytest.mark.parametrize("criterion", CRITERIA)
def test_every_row_gives_the_per_ply_ratio_to_the_last_bit_and_its_mode(criterion):
    v = states()
    ratios, modes = scaled_strength_ratios(criterion, MATERIAL, v, -0.5)
    assert ratios.shape == (len(v),) and len(modes) == len(v)
    for i, row in enumerate(v):
        with np.errstate(over="ignore"):
            ratio, mode = face_strength_ratio(criterion, MATERIAL, surface(ZERO), surface(row), -0.5)
        assert (ratio == ratios[i]) or (math.isinf(ratio) and math.isinf(ratios[i])), (i, row, ratio, ratios[i])
        assert mode == modes[i], (i, row, mode, modes[i])


def test_an_unloaded_row_has_no_failure_and_mode_none():
    ratios, modes = scaled_strength_ratios("max_stress", MATERIAL, np.zeros((2, 3)), None)
    assert np.all(np.isinf(ratios)) and modes == ["none", "none"]


def test_the_array_forms_refuse_what_the_per_ply_functions_refuse():
    with pytest.raises(ValueError, match="only finite numbers"):
        scaled_strength_ratios("max_stress", MATERIAL, [[1.0, math.nan, 0.0]], None)
    with pytest.raises(ValueError, match="shape"):
        scaled_strength_ratios("max_stress", MATERIAL, [1.0, 2.0, 3.0], None)
    with pytest.raises(ValueError, match="between -1 and 1"):
        scaled_strength_ratios("tsai_wu", MATERIAL, [[1.0, 2.0, 3.0]], 1.0)
    with pytest.raises(ValueError, match="Unknown criterion"):
        scaled_strength_ratios("hashin", MATERIAL, [[1.0, 2.0, 3.0]], None)


def test_ply_surface_arrays_equal_ply_surfaces_for_every_state():
    plies = [Ply(material=MATERIAL, angle_deg=a, thickness_m=1.3e-4) for a in (0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0)]
    rng = np.random.default_rng(3)
    eps0 = rng.normal(size=(200, 3)) * 1e-3
    kappa = rng.normal(size=(200, 3)) * 1e-1
    kappa[:100] = 0.0  # membrane states too
    arrays = ply_surface_arrays(plies, eps0, kappa)
    assert all(a.shape == (200, len(plies), 2, 3) for a in arrays)
    for n in range(len(eps0)):
        for i, s in enumerate(ply_surfaces(plies, eps0[n], kappa[n])):  # bottom then top face of every ply
            for array, value in zip(arrays, (s.strain_xy, s.stress_xy, s.strain_12, s.stress_12)):
                assert np.array_equal(array[n, i // 2, i % 2], value)


def test_ply_surface_arrays_refuse_bad_states():
    plies = [Ply(material=MATERIAL, angle_deg=0.0, thickness_m=1e-4)]
    with pytest.raises(ValueError, match="shape"):
        ply_surface_arrays(plies, np.zeros(3), np.zeros(3))
    with pytest.raises(ValueError, match="only finite numbers"):
        ply_surface_arrays(plies, [[math.inf, 0.0, 0.0]], np.zeros((1, 3)))
    with pytest.raises(ValueError, match="same shape"):
        ply_surface_arrays(plies, np.zeros((2, 3)), np.zeros((1, 3)))
