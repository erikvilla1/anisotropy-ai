"""The array forms a finite element kernel calls once per section (ADR-0073) give exactly what the per-ply functions give, row by row:
the same ratio to the last bit and the same governing mode."""

import math

import numpy as np
import pytest

from anisotropy_engine.failure import CRITERIA, combined_strength_ratios, face_strength_ratio, first_ply_failure_combined, scaled_strength_ratios
from anisotropy_engine.lamina import Lamina, StrainLimits, Strengths, ThermalExpansion
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads, PlySurface, midplane_response, ply_surface_arrays, ply_surfaces
from anisotropy_engine.thermal import thermal_ply_surface_arrays, thermal_ply_surfaces, thermomechanical_response

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


def held_states(n: int) -> np.ndarray:
    """Held stresses within, at and past every limit of MATERIAL, with zero components and unloaded rows."""
    st = MATERIAL.strengths
    rng = np.random.default_rng(11)
    held = rng.uniform(-1.6, 1.6, size=(n, 3)) * np.array([st.F1t, st.F2t, st.F6])
    held[rng.random((n, 3)) < 0.2] = 0.0
    held[:20] = 0.0
    edges = [[st.F1t, 0, 0], [-st.F1c, 0, 0], [0, st.F2t, 0], [0, -st.F2c, 0], [0, 0, st.F6], [0, 0, -st.F6], [0.99 * st.F1t, 0.5 * st.F2t, 0]]
    held[20:20 + len(edges)] = edges
    return held


@pytest.mark.parametrize("criterion", CRITERIA)
def test_a_held_and_a_scaled_stress_give_the_per_ply_ratio_to_the_last_bit_and_its_mode(criterion):
    """`combined_strength_ratios` is `face_strength_ratio` with a held face, row by row (ADR-0073 amendment 1): R = 0 where the held
    stress alone reaches the criterion, as the per-ply functions say, which `_tsai_hill_ratios` with nothing held never needed."""
    v = states()
    s = held_states(len(v))
    ratios, modes = combined_strength_ratios(criterion, MATERIAL, s, v, -0.5)
    assert ratios.shape == (len(v),) and len(modes) == len(v)
    for i, (held, row) in enumerate(zip(s, v)):
        with np.errstate(over="ignore"):
            ratio, mode = face_strength_ratio(criterion, MATERIAL, surface(held), surface(row), -0.5)
        assert (ratio == ratios[i]) or (math.isinf(ratio) and math.isinf(ratios[i])), (i, held, row, ratio, ratios[i])
        assert mode == modes[i], (i, held, row, mode, modes[i])
    assert np.any(ratios == 0.0) and np.any((ratios > 0) & np.isfinite(ratios)), "the states reach both branches"


def test_a_held_stress_past_a_limit_fails_at_once_and_names_its_mode():
    st = MATERIAL.strengths
    held = np.array([[st.F1t, 0.0, 0.0], [0.0, -1.2 * st.F2c, 0.0], [0.0, 0.0, -st.F6], [0.0, 0.5 * st.F2t, 0.0]])
    ratios, modes = combined_strength_ratios("max_stress", MATERIAL, held, np.zeros((4, 3)), None)
    assert ratios.tolist()[:3] == [0.0, 0.0, 0.0] and math.isinf(ratios[3])
    assert modes == ["longitudinal tension", "transverse compression", "in-plane shear", "none"]
    for criterion in ("tsai_hill", "tsai_wu"):
        assert combined_strength_ratios(criterion, MATERIAL, held, np.zeros((4, 3)), -0.5)[0].tolist()[:3] == [0.0, 0.0, 0.0]


def test_nothing_held_is_the_scaled_form():
    v = states()
    for criterion in CRITERIA:
        held_none = combined_strength_ratios(criterion, MATERIAL, np.zeros_like(v), v, -0.5)
        scaled = scaled_strength_ratios(criterion, MATERIAL, v, -0.5)
        assert np.array_equal(held_none[0], scaled[0]) and held_none[1] == scaled[1]


def test_the_combined_form_refuses_what_the_per_ply_functions_refuse():
    with pytest.raises(ValueError, match="same shape"):
        combined_strength_ratios("max_stress", MATERIAL, np.zeros((2, 3)), np.zeros((3, 3)), None)
    with pytest.raises(ValueError, match="fixed_12 must contain only finite numbers"):
        combined_strength_ratios("max_stress", MATERIAL, [[math.inf, 0.0, 0.0]], [[1.0, 0.0, 0.0]], None)
    with pytest.raises(ValueError, match="between -1 and 1"):
        combined_strength_ratios("tsai_wu", MATERIAL, [[0.0, 0.0, 0.0]], [[1.0, 2.0, 3.0]], -1.0)


THERMAL = MATERIAL.model_copy(update={"thermal_expansion": ThermalExpansion(alpha1=-0.5e-6, alpha2=30e-6)})  # constructed, for the test


def test_thermal_ply_surface_arrays_equal_thermal_ply_surfaces_for_every_state():
    plies = [Ply(material=THERMAL, angle_deg=a, thickness_m=1.3e-4) for a in (0.0, 45.0, -45.0, 90.0, 0.0, 30.0)]  # unsymmetric: it bends
    rng = np.random.default_rng(5)
    eps0 = rng.normal(size=(200, 3)) * 1e-3
    kappa = rng.normal(size=(200, 3)) * 1e-1
    kappa[:100] = 0.0
    for delta_T in (-150.0, 0.0, 37.5):
        arrays = thermal_ply_surface_arrays(plies, eps0, kappa, delta_T)
        assert all(a.shape == (200, len(plies), 2, 3) for a in arrays)
        for n in range(len(eps0)):
            for i, s in enumerate(thermal_ply_surfaces(plies, eps0[n], kappa[n], delta_T)):
                for array, value in zip(arrays, (s.strain_xy, s.stress_xy, s.strain_12, s.stress_12)):
                    assert np.array_equal(array[n, i // 2, i % 2], value)


def test_thermal_ply_surface_arrays_refuse_what_thermal_ply_surfaces_refuses():
    with pytest.raises(ValueError, match="no thermal expansion"):
        thermal_ply_surface_arrays([Ply(material=MATERIAL, angle_deg=0.0, thickness_m=1e-4)], np.zeros((1, 3)), np.zeros((1, 3)), -100.0)
    with pytest.raises(ValueError, match="finite"):
        thermal_ply_surface_arrays([Ply(material=THERMAL, angle_deg=0.0, thickness_m=1e-4)], np.zeros((1, 3)), np.zeros((1, 3)), math.nan)


@pytest.mark.parametrize("criterion", CRITERIA)
def test_the_array_forms_give_first_ply_failure_combined_under_a_held_temperature_change(criterion):
    """A cooled laminate held under a transverse load while a pull, a shear and a moment grow: the held faces from
    `thermal_ply_surface_arrays`, the scaled ones from `ply_surface_arrays`, and `combined_strength_ratios` give every check of
    `first_ply_failure_combined`, ratio and mode, to the last bit."""
    plies = [Ply(material=THERMAL, angle_deg=a, thickness_m=1.3e-4) for a in (0.0, 90.0, 90.0, 0.0, 45.0)]
    fixed = Loads(Nx=0.0, Ny=2e4, Nxy=0.0, Mx=0.0, My=0.0, Mxy=0.0)
    variable = Loads(Nx=1e5, Ny=0.0, Nxy=5e3, Mx=1.0, My=0.0, Mxy=0.0)
    delta_T = -150.0
    expected = first_ply_failure_combined(plies, fixed, variable, delta_T, criterion, -0.5)
    eps0, kappa = thermomechanical_response(plies, fixed, delta_T)
    held = thermal_ply_surface_arrays(plies, eps0[None], kappa[None], delta_T)[3][0].reshape(-1, 3)
    eps0, kappa = midplane_response(plies, variable)
    scaled = ply_surface_arrays(plies, eps0[None], kappa[None])[3][0].reshape(-1, 3)
    ratios, modes = combined_strength_ratios(criterion, THERMAL, held, scaled, -0.5)
    assert ratios.tolist() == [c.strength_ratio for c in expected.checks]
    assert modes == [c.mode for c in expected.checks]


def test_ply_surface_arrays_refuse_bad_states():
    plies = [Ply(material=MATERIAL, angle_deg=0.0, thickness_m=1e-4)]
    with pytest.raises(ValueError, match="shape"):
        ply_surface_arrays(plies, np.zeros(3), np.zeros(3))
    with pytest.raises(ValueError, match="only finite numbers"):
        ply_surface_arrays(plies, [[math.inf, 0.0, 0.0]], np.zeros((1, 3)))
    with pytest.raises(ValueError, match="same shape"):
        ply_surface_arrays(plies, np.zeros((2, 3)), np.zeros((1, 3)))
