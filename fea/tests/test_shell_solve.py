"""Whole shell solves: engine equality under pure bending, the membrane reproduced, the dispatch, couplings and refusals (theory, Section 8)."""

import numpy as np
import pytest

from anisotropy_engine.failure import first_ply_failure
from anisotropy_engine.laminate import abd_matrices
from anisotropy_engine.response import Loads, ply_surfaces
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.kernel import is_shell, solve_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.model import section_plies
from anisotropy_fea.recovery import FACES, deck_f12_star, element_ply_states, ply_ratio_per_ply, strength_ratios
from anisotropy_fea.results import ShellSolution
from anisotropy_fea.shell import needs_shell, solve_shell
from _decks import gripped_coupon
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECKS = paths.CHECK_DECKS
ONE = DECKS / "coupon-1x1-im7-8552.inp"
BEND = DECKS / "coupon-1x1-bend-im7-8552.inp"
GRIPS = DECKS / "coupon-2x8-grips-im7-8552.inp"
KAPPA = 1.0  # 1/m: the bend deck prescribes kappa_x = 1e-3 per mm


def test_the_bend_deck_goes_to_the_shell_and_the_in_plane_decks_stay_with_the_membrane():
    assert needs_shell(read_deck(BEND, "mm-MPa")) and not needs_shell(read_deck(ONE, "mm-MPa")) and not needs_shell(read_deck(GRIPS, "mm-MPa"))
    assert is_shell(solve_deck(read_deck(BEND, "mm-MPa"))) and not is_shell(solve_deck(read_deck(ONE, "mm-MPa")))


def test_pure_bending_of_an_unsymmetric_element_reproduces_the_engine_to_1e_12():
    deck = read_deck(BEND, "mm-MPa")
    plies = section_plies(deck.parts["Coupon"].sections[0], deck.materials)
    A, B, D = abd_matrices(plies)
    assert np.linalg.norm(B) > 1e-3 * np.linalg.norm(A) * sum(p.thickness_m for p in plies)  # the layup is unsymmetric on purpose
    kappa = np.array([KAPPA, 0.0, 0.0])
    solution = solve_deck(deck)
    assert isinstance(solution, ShellSolution)
    assert solution.curvature[0] == pytest.approx(kappa, rel=1e-12, abs=1e-14)
    assert solution.strain[0] == pytest.approx([0.0, 0.0, 0.0], abs=1e-14)
    assert solution.shear_strain[0] == pytest.approx([0.0, 0.0], abs=1e-14)
    assert solution.section_force[0] == pytest.approx(B @ kappa, rel=1e-12, abs=1e-9 * np.abs(B @ kappa).max())
    assert solution.moment[0] == pytest.approx(D @ kappa, rel=1e-12, abs=1e-9 * np.abs(D @ kappa).max())
    assert solution.free_residual < 1e-9 * np.abs(D @ kappa).max()
    # both faces of every ply equal the engine's ply surfaces on (0, kappa)
    field = element_ply_states(solution)
    assert field.faces == FACES and field.stress_12[0].shape == (4, 2, 3)
    surfaces = ply_surfaces(plies, np.zeros(3), kappa)
    for k in range(4):
        for f in range(2):
            s = surfaces[2 * k + f]
            assert field.stress_12[0][k, f] == pytest.approx(s.stress_12, rel=1e-12, abs=1e-3)
            assert field.strain_12[0][k, f] == pytest.approx(s.strain_12, rel=1e-12, abs=1e-16)
    assert not np.allclose(field.stress_12[0][0, 0], field.stress_12[0][0, 1])  # the two faces of a ply differ under bending


@pytest.mark.parametrize("criterion", ["max_stress", "tsai_hill", "tsai_wu"])
def test_first_ply_failure_under_bending_names_the_face_the_engine_names(criterion):
    deck = read_deck(BEND, "mm-MPa")
    plies = section_plies(deck.parts["Coupon"].sections[0], deck.materials)
    solution = solve_deck(deck)
    N, M = solution.section_force[0], solution.moment[0]
    engine = first_ply_failure(plies, Loads(Nx=N[0], Ny=N[1], Nxy=N[2], Mx=M[0], My=M[1], Mxy=M[2]), criterion=criterion, f12_star=deck_f12_star(deck))
    failure = strength_ratios(solution, criterion, deck_f12_star(deck))
    assert failure.factor == pytest.approx(engine.strength_ratio, rel=1e-12)
    ratios = [c.strength_ratio for c in engine.checks]
    i = int(np.argmin(ratios))
    assert (failure.ply, failure.face, failure.governing_mode) == (i // 2 + 1, FACES[i % 2], engine.checks[i].mode)
    assert failure.ratio[0].shape == (4, 2)
    ours = failure.ratio[0].ravel()
    # the two faces on the midplane carry no stress: the kernel's ratio there is infinite, the engine's a roundoff-sized stress's huge ratio
    stressed = np.array(ratios) < 1e12
    assert stressed.sum() == 6 and np.all(np.isinf(ours[~stressed]))
    assert ours[stressed] == pytest.approx(np.array(ratios)[stressed], rel=1e-12)
    assert ply_ratio_per_ply(failure.ratio[0]) == pytest.approx(np.minimum(ratios[0::2], ratios[1::2]), rel=1e-12)


def test_the_shell_reproduces_the_membrane_on_a_symmetric_in_plane_deck(tmp_path):
    """The one-element coupon with w and the tilts held: the shell's u, v, strain, N and in-plane reactions are the membrane's to 1e-12."""
    text = ONE.read_text(encoding="utf-8").replace("*Boundary\nBottom, 2, 2", "*Boundary\nBottom, 3, 5\nTop, 3, 5\n*Boundary\nBottom, 2, 2", 1)
    path = tmp_path / "deck.inp"
    path.write_text(text, encoding="utf-8")
    deck = read_deck(path, "mm-MPa")
    assert not needs_shell(deck)
    membrane, shell = solve_membrane(deck), solve_shell(deck)
    scale = np.abs(membrane.displacement).max()
    assert shell.displacement[:, :2] == pytest.approx(membrane.displacement, rel=1e-12, abs=1e-14 * scale)
    assert np.abs(shell.displacement[:, 2:]).max() < 1e-14 * scale
    assert shell.strain == pytest.approx(membrane.strain, rel=1e-12, abs=1e-16)
    assert shell.section_force == pytest.approx(membrane.section_force, rel=1e-12, abs=1e-6)
    assert shell.reaction[:, :2] == pytest.approx(membrane.reaction, rel=1e-12, abs=1e-9 * np.abs(membrane.reaction).max())
    assert np.abs(shell.curvature).max() < 1e-14 and np.abs(shell.moment).max() < 1e-9
    field = element_ply_states(shell)
    assert field.faces == FACES
    assert field.stress_12[0][:, 0] == pytest.approx(element_ply_states(membrane).stress_12[0], rel=1e-12, abs=1e-3)


def test_a_coupled_grip_aliases_all_five_dofs_and_the_shell_matches_the_membrane_through_it():
    deck = read_deck(GRIPS, "mm-MPa")
    membrane, shell = solve_membrane(deck), solve_shell(deck)
    scale = np.abs(membrane.displacement).max()
    assert shell.displacement[:, :2] == pytest.approx(membrane.displacement, rel=1e-10, abs=1e-12 * scale)
    assert np.abs(shell.displacement[:, 2:]).max() < 1e-12 * scale
    top = deck.nsets["RF-Top"]
    assert shell.reaction_of(top)[:2] == pytest.approx(membrane.reaction_of(top), rel=1e-10)
    assert shell.notes and "dof 6" in shell.notes[0]  # the ENCASTRE line holds the drilling rotation, which the plate drops


def test_a_pressure_on_a_plate_is_in_equilibrium_with_the_edge_reactions():
    deck = read_deck(DECKS / "plate-ss-16x16-isotropic.inp", "mm-MPa")
    solution = solve_deck(deck)
    assert isinstance(solution, ShellSolution)
    total = -0.01e6 * 0.1 * 0.1  # the deck writes P = -0.01 MPa (toward +z) on a 100 mm square: the reactions sum to -q a^2
    assert solution.total_reaction[2] == pytest.approx(total, rel=1e-10)
    assert solution.total_reaction[:2] == pytest.approx([0.0, 0.0], abs=1e-9 * abs(total))
    assert solution.displacement[:, 2].max() > 0.0  # the plate deflects toward +z


def test_a_plate_free_to_move_out_of_plane_is_refused(tmp_path):
    text = BEND.read_text(encoding="utf-8").replace("Left, 3, 3\nLeft, 5, 5\n", "", 1).replace("Right, 3, 3, -0.3125\nRight, 5, 5, 0.025\n", "", 1)
    assert "Right, 3, 3" not in text
    path = tmp_path / "deck.inp"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(KernelError, match="translations and its two tilts"):
        solve_shell(read_deck(path, "mm-MPa"))


def test_a_load_on_the_drilling_rotation_is_refused(tmp_path):
    text = BEND.read_text(encoding="utf-8").replace("*Restart", "*Cload\nRight, 6, 1.\n*Restart", 1)
    path = tmp_path / "deck.inp"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(KernelError, match="dof 6"):
        solve_shell(read_deck(path, "mm-MPa"))


def test_an_unsymmetric_layup_in_tension_goes_to_the_shell_and_bends(tmp_path):
    """The gripped coupon with an unsymmetric layup: the membrane refuses it, the shell solves it, and the pull bends it between the grips."""
    text = gripped_coupon(2, 8).replace(", symmetric", "", 1).replace("0.18288, 3, IM7-8552, 0., Ply-5", "0.18288, 3, IM7-8552, 90., Ply-5", 1)  # [0/30/-30/30/90]
    path = tmp_path / "deck.inp"
    path.write_text(text, encoding="utf-8")
    deck = read_deck(path, "mm-MPa")
    assert needs_shell(deck)
    with pytest.raises(KernelError, match="not symmetric"):
        solve_membrane(deck)
    solution = solve_deck(deck)
    assert isinstance(solution, ShellSolution)
    assert np.abs(solution.displacement[:, 2]).max() > 0.0 and np.abs(solution.curvature).max() > 0.0
    assert solution.total_reaction[:3] == pytest.approx([0.0, 0.0, 0.0], abs=1e-9 * np.abs(solution.reaction).max())
