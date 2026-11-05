"""The stack's description: thickness, symmetry, balance, kind, coupling, areal mass and the failure summary (ADR-0059)."""

import math

import numpy as np
import pytest

from anisotropy_engine.failure import first_ply_failure
from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply, abd_matrices, ply_interfaces
from anisotropy_engine.library import library_material
from anisotropy_engine.response import Loads
from anisotropy_engine.summary import (
    RELATIVE_TOLERANCE, areal_mass, coupling_flags, face_of, first_ply_failure_summary, is_antisymmetric, is_balanced,
    is_symmetric, laminate_kind, laminate_summary, total_thickness,
)

AS4 = library_material("as4-3501")  # Daniel & Ishai Table A.4: strengths, expansion, density 1600 kg/m^3, no ply thickness
TYPED = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27)  # the same constants without strengths or a density
T = 0.125e-3


def stack(angles, material=AS4.lamina, thickness=T):
    return [Ply(material=material, angle_deg=a, thickness_m=thickness) for a in angles]


def test_thickness_is_the_sum_of_the_plies_and_an_empty_stack_is_refused():
    assert total_thickness(stack([0, 45, -45, 90, 90, -45, 45, 0])) == pytest.approx(1.0e-3, rel=1e-15)
    with pytest.raises(ValueError, match="at least one ply"):
        total_thickness([])


@pytest.mark.parametrize("angles,symmetric,antisymmetric,balanced", [
    ([0], True, False, True),
    ([0, 90, 90, 0], True, False, True),
    ([0, 90, 0], True, False, True),
    ([45, -45, -45, 45], True, False, True),
    ([45, -45], False, True, True),
    ([45, -45, 0, 45, -45], False, True, True),  # an antisymmetric stack with a 0 ply in the middle
    ([45, -45, 45, -45], False, True, True),  # the antisymmetric angle-ply of Daniel & Ishai
    ([45, -45, 0, 0], False, False, True),  # balanced but neither symmetric nor antisymmetric
    ([0, 45], False, False, False),
    ([30, 0, 30], True, False, False),  # symmetric but unbalanced: no -30 ply
    ([0, 45, -45, 90, 90, -45, 45, 0], True, False, True),
])
def test_symmetry_antisymmetry_and_balance_follow_the_textbook_definitions(angles, symmetric, antisymmetric, balanced):
    plies = stack(angles)
    assert (is_symmetric(plies), is_antisymmetric(plies), is_balanced(plies)) == (symmetric, antisymmetric, balanced)


def test_symmetry_needs_the_same_material_and_thickness_in_the_mirrored_plies():
    plies = [Ply(material=AS4.lamina, angle_deg=0, thickness_m=T), Ply(material=AS4.lamina, angle_deg=90, thickness_m=T),
             Ply(material=AS4.lamina, angle_deg=90, thickness_m=T), Ply(material=TYPED, angle_deg=0, thickness_m=T)]
    assert not is_symmetric(plies)
    thicker = stack([0, 90, 90]) + [Ply(material=AS4.lamina, angle_deg=0, thickness_m=2 * T)]
    assert not is_symmetric(thicker)
    assert not is_balanced([Ply(material=AS4.lamina, angle_deg=45, thickness_m=T), Ply(material=AS4.lamina, angle_deg=-45, thickness_m=2 * T)])


def test_a_fiber_angle_is_the_same_fiber_angle_plus_180_degrees():
    assert is_symmetric(stack([0, 180]))
    assert is_symmetric(stack([45, -135]))
    assert is_balanced(stack([45, 135]))  # 135 is -45
    assert is_antisymmetric(stack([30, 150]))  # 150 is -30


@pytest.mark.parametrize("angles,kind", [
    ([0], "unidirectional"),
    ([30, 30, 30], "unidirectional"),
    ([0, 90, 90, 0], "cross-ply"),
    ([0, 90], "cross-ply"),
    ([45, -45, -45, 45], "angle-ply"),
    ([30, -30], "angle-ply"),
    ([0, 45], "general"),
    ([0, 45, -45, 90], "quasi-isotropic"),  # unsymmetric, but A is isotropic: the kind is read from A, not the stacking
    ([0, 60, -60, -60, 60, 0], "quasi-isotropic"),
    ([0, 45, -45, 90, 90, -45, 45, 0], "quasi-isotropic"),
])
def test_the_kind_is_read_from_a_first_and_the_angles_second(angles, kind):
    plies = stack(angles)
    A, _, _ = abd_matrices(plies)
    assert laminate_kind(plies, A) == kind


def test_quasi_isotropic_means_a_is_isotropic_to_the_tolerance():
    plies = stack([0, 60, -60, -60, 60, 0])
    A, _, _ = abd_matrices(plies)
    scale = np.abs(A).max()
    assert abs(A[0, 0] - A[1, 1]) <= RELATIVE_TOLERANCE * scale
    assert abs(A[2, 2] - (A[0, 0] - A[0, 1]) / 2) <= RELATIVE_TOLERANCE * scale
    perturbed = stack([0, 60, -60, -60, 60, 0.001])
    assert laminate_kind(perturbed, abd_matrices(perturbed)[0]) == "general"


@pytest.mark.parametrize("angles,extension_shear,extension_bending,bending_twisting", [
    ([0, 90, 90, 0], False, False, False),
    ([0, 90], False, True, False),
    ([45, -45], False, True, False),  # antisymmetric angle-ply: B16, B26 only
    ([45, -45, -45, 45], False, False, True),  # symmetric angle-ply: D16, D26 only
    ([0, 45], True, True, True),
    ([30, 0, 30], True, False, True),
])
def test_coupling_flags_judge_each_matrix_against_its_own_size(angles, extension_shear, extension_bending, bending_twisting):
    plies = stack(angles)
    A, B, D = abd_matrices(plies)
    flags = coupling_flags(A, B, D, total_thickness(plies))
    assert (flags.extension_shear, flags.extension_bending, flags.bending_twisting) == (extension_shear, extension_bending, bending_twisting)


def test_roundoff_in_a_symmetric_stack_is_not_coupling():
    plies = stack([0, 45, -45, 90, 90, -45, 45, 0])
    A, B, D = abd_matrices(plies)
    assert np.abs(B).max() > 0  # the sum is not exactly zero in floating point
    assert not coupling_flags(A, B, D, total_thickness(plies)).extension_bending


def test_areal_mass_is_density_times_thickness_summed_and_names_the_plies_without_a_density():
    plies = stack([0, 45, -45, 90, 90, -45, 45, 0])
    assert areal_mass(plies, [1600.0] * 8) == pytest.approx(1.6, rel=1e-15)
    two = [Ply(material=AS4.lamina, angle_deg=0, thickness_m=1e-3), Ply(material=TYPED, angle_deg=0, thickness_m=2e-3)]
    assert areal_mass(two, [1000.0, 2000.0]) == pytest.approx(5.0, rel=1e-15)
    with pytest.raises(ValueError, match=r"plies \[2\] have no density"):
        areal_mass(two, [1000.0, None])
    with pytest.raises(ValueError, match="2 plies need 2 densities, got 1"):
        areal_mass(two, [1000.0])
    with pytest.raises(ValueError, match=r"plies \[1\] have a density that is not a finite positive number"):
        areal_mass(two, [0.0, 2000.0])


def test_the_summary_describes_the_quasi_isotropic_library_stack():
    plies = stack([0, 45, -45, 90, 90, -45, 45, 0])
    s = laminate_summary(plies, [AS4.density_kg_per_m3] * 8)
    assert s.ply_count == 8 and s.total_thickness_m == pytest.approx(1.0e-3, rel=1e-15)
    assert s.symmetric and s.balanced and not s.antisymmetric and s.kind == "quasi-isotropic"
    assert not s.coupling.extension_shear and not s.coupling.extension_bending and s.coupling.bending_twisting
    assert s.areal_mass_kg_per_m2 == pytest.approx(1.6, rel=1e-15) and s.areal_mass_missing is None
    assert s.tolerance == RELATIVE_TOLERANCE


def test_without_densities_the_areal_mass_is_left_out_with_the_reason():
    s = laminate_summary(stack([0, 90]))
    assert s.areal_mass_kg_per_m2 is None and s.areal_mass_missing == "plies [1, 2] have no density"
    partial = laminate_summary(stack([0, 90]), [1600.0, None])
    assert partial.areal_mass_kg_per_m2 is None and partial.areal_mass_missing == "plies [2] have no density"


def test_face_of_names_the_interface_a_check_sits_on():
    plies = stack([0, 90])
    z = ply_interfaces(plies)
    fpf = first_ply_failure(plies, Loads(Nx=1000.0), "max_stress")
    faces = {(c.ply_index, face_of(plies, c)) for c in fpf.checks}
    assert faces == {(0, "bottom"), (0, "top"), (1, "bottom"), (1, "top")}
    bottom_of_second = next(c for c in fpf.checks if c.ply_index == 1 and c.z_m == z[1])
    assert face_of(plies, bottom_of_second) == "bottom"


def test_the_failure_summary_runs_the_criteria_the_inputs_support_and_names_the_rest():
    plies = stack([0, 45, -45, 90, 90, -45, 45, 0])
    loads = Loads(Nx=1000.0)
    summary = first_ply_failure_summary(plies, loads)
    assert summary.evaluated and summary.reason is None
    assert [r.criterion for r in summary.results] == ["max_stress", "tsai_hill"]
    assert [n.criterion for n in summary.not_computed] == ["max_strain", "tsai_wu"]
    assert "no strain limits" in summary.not_computed[0].reason and "f12_star" in summary.not_computed[1].reason
    for result in summary.results:
        direct = first_ply_failure(plies, loads, result.criterion)
        assert result.strength_ratio == direct.strength_ratio
        assert result.ply_number == direct.governing.ply_index + 1 and result.z_m == direct.governing.z_m
        assert result.mode == direct.governing.mode and result.failure_loads == direct.failure_loads
        assert result.face in ("bottom", "top") and math.isfinite(result.strength_ratio)
    # The 90-degree plies next to the mid-plane crack first in transverse tension under Nx.
    assert summary.results[0].ply_number == 4 and summary.results[0].angle_deg == 90 and summary.results[0].mode == "transverse tension"


def test_the_failure_summary_takes_f12_star_and_strain_limits_when_they_are_given():
    from anisotropy_engine.lamina import strain_limits_from_strengths
    limited = AS4.lamina.model_copy(update={"strain_limits": strain_limits_from_strengths(AS4.lamina)})
    plies = stack([0, 90, 90, 0], material=limited)
    summary = first_ply_failure_summary(plies, Loads(Nx=500.0, Mx=0.5), f12_star=-0.5)
    assert [r.criterion for r in summary.results] == ["max_stress", "max_strain", "tsai_hill", "tsai_wu"]
    assert summary.not_computed == ()


def test_the_failure_summary_says_why_it_did_not_run():
    plies = stack([0, 90, 90, 0])
    nothing = first_ply_failure_summary(plies, Loads())
    assert not nothing.evaluated and nothing.reason == "no loads applied" and nothing.results == ()
    typed = first_ply_failure_summary(stack([0, 90], material=TYPED), Loads(Nx=1000.0))
    assert not typed.evaluated and typed.reason == "plies [1, 2] have no strengths"
    mixed = first_ply_failure_summary([Ply(material=AS4.lamina, angle_deg=0, thickness_m=T), Ply(material=TYPED, angle_deg=90, thickness_m=T)],
                                      Loads(Nx=1000.0))
    assert mixed.reason == "plies [2] have no strengths"
