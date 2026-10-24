"""Ply stresses in material axes and first-ply failure per element equal the engine's on the uniform cases (theory, Section 5)."""

from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.failure import first_ply_failure
from anisotropy_engine.mixed import mixed_response
from anisotropy_engine.response import Loads, ply_surfaces
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.model import section_plies
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios
from _decks import gripped_coupon
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECKS = paths.CHECK_DECKS
ONE = DECKS / "coupon-1x1-im7-8552.inp"
TWO = DECKS / "coupon-2x2-im7-8552.inp"


def uniform_case():
    deck = read_deck(ONE, "mm-MPa")
    plies = section_plies(deck.parts["Coupon"].sections[0], deck.materials)
    mixed = mixed_response(plies, {"Nx": 0.0, "eps_y": 0.008, "Nxy": 0.0, "Mx": 0.0, "My": 0.0, "Mxy": 0.0}, None)  # 0.8 mm over 100 mm
    return deck, plies, mixed


def test_ply_states_equal_the_engine_ply_surfaces_with_zero_curvature():
    deck, plies, mixed = uniform_case()
    field = element_ply_states(solve_membrane(deck))
    surfaces = ply_surfaces(plies, mixed.midplane_strain, np.zeros(3))
    assert field.stress_12[0].shape == (10, 3)
    for k in range(10):
        bottom, top = surfaces[2 * k], surfaces[2 * k + 1]
        assert bottom.stress_12 == pytest.approx(top.stress_12)  # a membrane state: both faces equal
        assert field.stress_12[0][k] == pytest.approx(bottom.stress_12, rel=1e-12, abs=1e-3)
        assert field.strain_12[0][k] == pytest.approx(bottom.strain_12, rel=1e-12, abs=1e-16)
        assert field.stress_xy[0][k] == pytest.approx(bottom.stress_xy, rel=1e-12, abs=1e-3)
        assert field.angles_deg[0][k] == bottom.angle_deg
    # the 30 and -30 plies see the same fiber stress magnitude pattern only if the state were pure axial; here gamma_xy != 0, so they differ
    assert not np.allclose(field.stress_12[0][1], field.stress_12[0][2])


@pytest.mark.parametrize("criterion", ["max_stress", "tsai_hill", "tsai_wu"])
def test_first_ply_failure_equals_the_engine(criterion):
    deck, plies, mixed = uniform_case()
    f12_star = deck_f12_star(deck)
    engine = first_ply_failure(plies, Loads(Ny=mixed.loads.Ny), criterion=criterion, f12_star=f12_star)
    failure = strength_ratios(solve_membrane(deck), criterion, f12_star)
    assert failure.factor == pytest.approx(engine.strength_ratio, rel=1e-12)
    engine_ratios = [check.strength_ratio for check in engine.checks[0::2]]
    assert failure.ratio[0] == pytest.approx(engine_ratios, rel=1e-12)
    # identical plies tie in a uniform state; the kernel reports the bottom-most tied ply, the engine's choice is roundoff
    tied = [k for k, ratio in enumerate(engine_ratios) if ratio <= engine.strength_ratio * (1 + 1e-9)]
    assert failure.ply - 1 in tied and failure.ply - 1 == tied[0]
    assert failure.governing_mode == engine.checks[2 * (failure.ply - 1)].mode
    assert failure.element == ("Coupon-1", 1)


def test_every_element_of_a_refined_mesh_has_the_same_ratios():
    deck = read_deck(TWO, "mm-MPa")
    failure = strength_ratios(solve_membrane(deck), "max_stress")
    for element_ratios in failure.ratio[1:]:
        assert element_ratios == pytest.approx(failure.ratio[0], rel=1e-10)


def test_the_factor_is_inverse_to_the_applied_displacement(tmp_path):
    deck = read_deck(ONE, "mm-MPa")
    one = strength_ratios(solve_membrane(deck), "tsai_hill").factor
    path = tmp_path / "double.inp"
    path.write_text(ONE.read_text(encoding="utf-8").replace("Top, 2, 2, 0.8", "Top, 2, 2, 1.6"), encoding="utf-8")
    two = strength_ratios(solve_membrane(read_deck(path, "mm-MPa")), "tsai_hill").factor
    assert two == pytest.approx(one / 2, rel=1e-12)


def test_isotropic_homogeneous_section_gives_the_plane_stress_stress():
    solution = solve_membrane(read_deck(DECKS / "plate-1x1-isotropic.inp", "mm-MPa"))
    field = element_ply_states(solution)
    assert field.stress_12[0].shape == (1, 3)
    assert field.stress_12[0][0] == pytest.approx([0.0, 70000e6 * 0.01, 0.0], rel=1e-12, abs=1e-3)


def test_the_gripped_coupon_fails_first_near_a_grip():
    deck = read_deck(DECKS / "coupon-2x8-grips-im7-8552.inp", "mm-MPa")
    failure = strength_ratios(solve_membrane(deck), "max_stress")
    assert 0 < failure.factor < np.inf
    label = failure.element[1]
    # 2 by 8 mesh, element labels row by row from the bottom: the two rows nearest each grip are 1..4 and 13..16
    assert label in (1, 2, 3, 4, 13, 14, 15, 16), "the first ply to fail should sit within two element rows of a grip"
    assert all(r.shape == (10,) for r in failure.ratio)
    # the factor is the minimum over every ply of every element
    assert failure.factor == pytest.approx(min(r.min() for r in failure.ratio))


def test_refusals_name_what_is_missing(tmp_path):
    deck = read_deck(ONE, "mm-MPa")
    solution = solve_membrane(deck)
    with pytest.raises(KernelError, match="no strain limits"):
        strength_ratios(solution, "max_strain")
    with pytest.raises(KernelError, match="unknown failure criterion"):
        strength_ratios(solution, "hashin")
    with pytest.raises(KernelError, match="needs an explicit f12_star"):
        strength_ratios(solution, "tsai_wu", None)
    no_strengths = tmp_path / "plain.inp"
    text = ONE.read_text(encoding="utf-8")
    start = text.index("*Fail Stress\n")  # the keyword, not the header comment that mentions it
    end = text.index("*Step,")
    no_strengths.write_text(text[:start] + text[end:], encoding="utf-8")
    with pytest.raises(KernelError, match="have no strengths"):
        strength_ratios(solve_membrane(read_deck(no_strengths, "mm-MPa")), "max_stress")


def test_deck_f12_star_reads_the_sixth_fail_stress_value(tmp_path):
    assert deck_f12_star(read_deck(ONE, "mm-MPa")) == 0.0
    assert deck_f12_star(read_deck(DECKS / "plate-1x1-isotropic.inp", "mm-MPa")) is None
    path = tmp_path / "two-materials.inp"
    path.write_text(gripped_coupon(2, 2).replace("91.15, 0.", "91.15, -0.5"), encoding="utf-8")
    assert deck_f12_star(read_deck(path, "mm-MPa")) == -0.5
