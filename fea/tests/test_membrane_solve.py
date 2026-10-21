"""Whole solves: engine equality, closed forms, couplings, equilibrium, refinement and refusals (fea/docs/theory.md, Checks)."""

from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.mixed import mixed_response
from anisotropy_engine.response import Loads, midplane_response
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.model import section_plies
from _decks import edge_coupon, gripped_coupon
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECKS = paths.CHECK_DECKS
ONE = DECKS / "coupon-1x1-im7-8552.inp"
GRIPS = DECKS / "coupon-2x8-grips-im7-8552.inp"
WIDTH_M = 0.010


def engine_strain_for_prescribed_pull(deck):
    plies = section_plies(deck.parts["Coupon"].sections[0], deck.materials)
    mixed = mixed_response(plies, {"Nx": 0.0, "eps_y": 0.01, "Nxy": 0.0, "Mx": 0.0, "My": 0.0, "Mxy": 0.0}, None)
    return mixed.midplane_strain, mixed.loads.Ny


def test_one_element_coupon_reproduces_the_engine_to_1e_12():
    deck = read_deck(ONE, "mm-MPa")
    eps, Ny = engine_strain_for_prescribed_pull(deck)
    solution = solve_membrane(deck)
    assert solution.strain[0] == pytest.approx(eps, rel=1e-12, abs=1e-16)
    assert solution.gauss_strain[0] == pytest.approx(np.tile(eps, (4, 1)), rel=1e-12, abs=1e-16)
    assert solution.section_force[0] == pytest.approx([0.0, Ny, 0.0], rel=1e-12, abs=1e-6 * Ny)
    assert solution.reaction_of(deck.nsets["Top"]) == pytest.approx([0.0, Ny * WIDTH_M], rel=1e-12, abs=1e-9 * Ny * WIDTH_M)
    assert solution.total_reaction == pytest.approx([0.0, 0.0], abs=1e-9 * Ny * WIDTH_M)
    assert solution.free_residual < 1e-9 * Ny * WIDTH_M
    x, y = 0.010, 0.080
    assert solution.displacement_of(("Coupon-1", 3)) == pytest.approx([eps[0] * x + eps[2] * y, eps[1] * y], rel=1e-12)


def test_refined_meshes_carry_the_same_uniform_state(tmp_path):
    reference = read_deck(ONE, "mm-MPa")
    eps, Ny = engine_strain_for_prescribed_pull(reference)
    for nx, ny in ((2, 2), (4, 8), (3, 5)):
        path = tmp_path / f"coupon-{nx}x{ny}.inp"
        path.write_text(edge_coupon(nx, ny), encoding="utf-8")
        solution = solve_membrane(read_deck(path, "mm-MPa"))
        assert solution.strain == pytest.approx(np.tile(eps, (nx * ny, 1)), rel=1e-11, abs=1e-15)
        assert solution.reaction_of(read_deck(path, "mm-MPa").nsets["Top"]) == pytest.approx([0.0, Ny * WIDTH_M], rel=1e-11, abs=1e-8 * Ny * WIDTH_M)


def test_load_control_reproduces_the_engine_forward_solve():
    deck = read_deck(DECKS / "coupon-1x1-cload-im7-8552.inp", "mm-MPa")
    plies = section_plies(deck.parts["Coupon"].sections[0], deck.materials)
    Ny = 1000.0 / WIDTH_M
    eps, kappa = midplane_response(plies, Loads(Ny=Ny))
    assert kappa == pytest.approx(np.zeros(3), abs=1e-12)  # symmetric layup: curvature is roundoff
    solution = solve_membrane(deck)
    assert solution.strain[0] == pytest.approx(eps, rel=1e-12, abs=1e-16)
    assert solution.reaction_of(deck.nsets["Bottom"]) == pytest.approx([0.0, -1000.0], abs=1e-9 * 1000.0)
    assert solution.total_reaction == pytest.approx([0.0, -1000.0], abs=1e-9 * 1000.0)  # equilibrium with the applied load


def test_isotropic_closed_forms():
    E, nu, h, w = 70000e6, 0.33, 2e-3, 0.010
    uniaxial = solve_membrane(read_deck(DECKS / "plate-1x1-isotropic.inp", "mm-MPa"))
    assert uniaxial.strain[0] == pytest.approx([-nu * 0.01, 0.01, 0.0], rel=1e-12, abs=1e-16)
    assert uniaxial.section_force[0] == pytest.approx([0.0, E * h * 0.01, 0.0], rel=1e-12, abs=1e-6)
    shear = solve_membrane(read_deck(DECKS / "plate-1x1-isotropic-shear.inp", "mm-MPa"))
    G = E / (2 * (1 + nu))
    assert shear.strain[0] == pytest.approx([0.0, 0.0, 0.01], rel=1e-12, abs=1e-16)
    assert shear.section_force[0] == pytest.approx([0.0, 0.0, G * h * 0.01], rel=1e-12, abs=1e-6)
    deck = read_deck(DECKS / "plate-1x1-isotropic-shear.inp", "mm-MPa")
    assert shear.reaction_of(deck.nsets["Top"]) == pytest.approx([G * h * 0.01 * w, 0.0], rel=1e-12, abs=1e-6)


def test_a_coupled_edge_equals_the_same_edge_prescribed_node_by_node(tmp_path):
    coupled_path = tmp_path / "coupled.inp"
    coupled_path.write_text(gripped_coupon(2, 4), encoding="utf-8")
    coupled_deck = read_deck(coupled_path, "mm-MPa")
    coupled = solve_membrane(coupled_deck)
    # the same mesh with every top node moved 0.8 mm in y and held in x, every bottom node encastre, no couplings
    direct_text = edge_coupon(2, 4).replace("*Boundary\nBottom, 2, 2\n*Boundary\nCorner, 1, 1\n*Boundary\nTop, 2, 2, 0.8\n",
                                             "*Boundary\nBottom, 1, 2\n*Boundary\nTop, 1, 1\nTop, 2, 2, 0.8\n")
    direct_path = tmp_path / "direct.inp"
    direct_path.write_text(direct_text, encoding="utf-8")
    direct_deck = read_deck(direct_path, "mm-MPa")
    direct = solve_membrane(direct_deck)
    for label in range(1, 16):
        assert coupled.displacement_of(("CFRP-Coupon-1", label)) == pytest.approx(direct.displacement_of(("Coupon-1", label)), abs=1e-15)
    assert coupled.strain == pytest.approx(direct.strain, rel=1e-10, abs=1e-15)
    rf_top = coupled.reaction_of([(None, 1)])
    assert rf_top == pytest.approx(direct.reaction_of(direct_deck.nsets["Top"]), rel=1e-10)
    assert coupled.reaction_of(coupled_deck.nsets["s_Top"]) == pytest.approx([0.0, 0.0])  # coupled nodes carry no reaction of their own
    assert coupled.displacement_of((None, 1)) == pytest.approx([0.0, 0.8e-3])


def test_the_gripped_coupon_is_in_equilibrium_with_antisymmetric_grip_reactions():
    deck = read_deck(GRIPS, "mm-MPa")
    solution = solve_membrane(deck)
    top, bottom = solution.reaction_of([(None, 1)]), solution.reaction_of([(None, 2)])
    assert top[1] > 0
    assert top == pytest.approx(-bottom, abs=1e-10 * top[1])
    assert solution.total_reaction == pytest.approx([0.0, 0.0], abs=1e-9 * top[1])
    assert solution.free_residual < 1e-9 * top[1]
    for label in (25, 26, 27):
        assert solution.displacement_of(("CFRP-Coupon-1", label)) == pytest.approx([0.0, 0.8e-3])
    # the unbalanced layup shears under rigid grips: the strain field is not uniform
    assert np.ptp(solution.strain[:, 2]) > 1e-4


def test_refinement_does_not_stiffen_the_gripped_coupon(tmp_path):
    reactions = []
    for nx, ny in ((2, 8), (4, 16), (8, 32)):
        path = tmp_path / f"grips-{nx}x{ny}.inp"
        path.write_text(gripped_coupon(nx, ny), encoding="utf-8")
        reactions.append(solve_membrane(read_deck(path, "mm-MPa")).reaction_of([(None, 1)])[1])
    assert reactions[0] >= reactions[1] >= reactions[2]
    assert abs(reactions[1] - reactions[2]) / reactions[2] < abs(reactions[0] - reactions[1]) / reactions[1]  # converging
    assert abs(reactions[0] - reactions[2]) / reactions[2] < 0.05


def test_an_unsymmetric_layup_is_refused(tmp_path):
    path = tmp_path / "unsym.inp"
    # [0/45/-45/45/0] mirrors itself, so dropping `symmetric` alone is still symmetric; turn the last ply to 90 as well
    text = ONE.read_text(encoding="utf-8").replace("layup=Layup-1, symmetric", "layup=Layup-1").replace("IM7-8552, 0., Ply-5", "IM7-8552, 90., Ply-5")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(KernelError, match="layup is not symmetric"):
        solve_membrane(read_deck(path, "mm-MPa"))


def test_a_free_rigid_body_motion_is_refused(tmp_path):
    path = tmp_path / "loose.inp"
    path.write_text(ONE.read_text(encoding="utf-8").replace("*Boundary\nCorner, 1, 1\n", ""), encoding="utf-8")
    with pytest.raises(KernelError, match="singular"):
        solve_membrane(read_deck(path, "mm-MPa"))


def test_a_node_in_no_element_is_refused(tmp_path):
    path = tmp_path / "stray.inp"
    path.write_text(ONE.read_text(encoding="utf-8").replace("4, 0., 80., 0.\n", "4, 0., 80., 0.\n5, 5., 40., 0.\n"), encoding="utf-8")
    with pytest.raises(KernelError, match="belongs to no element"):
        solve_membrane(read_deck(path, "mm-MPa"))


def test_a_prescription_that_conflicts_through_a_coupling_is_refused(tmp_path):
    path = tmp_path / "conflict.inp"
    path.write_text(gripped_coupon(2, 8).replace("*Boundary\nSet-TopPull, 2, 2, 0.8\n",
                                                 "*Boundary\nSet-TopPull, 2, 2, 0.8\n*Boundary\nCFRP-Coupon-1.25, 2, 2\n"), encoding="utf-8")
    with pytest.raises(KernelError, match="conflicts with"):
        solve_membrane(read_deck(path, "mm-MPa"))
