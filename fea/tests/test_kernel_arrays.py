"""The kernel forms every element at once (ADR-0073): the stiffness, the strains, the section forces and every ply's strength ratio come out
exactly as one call per element and ply gives them, to the last bit, and a clockwise element is still named."""

import dataclasses

import numpy as np
import pytest
from scipy.sparse import coo_matrix

from anisotropy_engine.failure import CRITERIA, face_strength_ratio
from anisotropy_engine.response import PlySurface
from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.membrane import (GAUSS_POINTS, assemble, constraint_map, element_stiffness, element_strains, section_forces, solve_membrane,
                                    strain_displacement)
from anisotropy_fea.mesh import KernelError, mesh_from_deck
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios

DECK = paths.CHECK_DECKS / "coupon-2x8-grips-im7-8552.inp"
ZERO = np.zeros(3)


@pytest.fixture(scope="module")
def deck():
    return read_deck(DECK, "mm-MPa")


@pytest.fixture(scope="module")
def skewed(deck):
    """The coupon's mesh with every node moved a little, so no two elements share a Jacobian."""
    mesh = mesh_from_deck(deck)
    rng = np.random.default_rng(5)
    span = mesh.xy.max(axis=0) - mesh.xy.min(axis=0)
    return dataclasses.replace(mesh, xy=mesh.xy + rng.uniform(-0.02, 0.02, size=mesh.xy.shape) * span / 16)


def test_the_assembled_stiffness_is_the_per_element_sum_to_the_last_bit(deck, skewed):
    dofmap = constraint_map(deck, skewed)
    rows, cols, values = [], [], []
    for e in range(skewed.element_count):
        nodes = skewed.connectivity[e]
        k = element_stiffness(skewed.xy[nodes], skewed.sections[skewed.element_section[e]].A)
        r = dofmap.reduced[np.repeat(2 * nodes, 2) + np.tile([0, 1], 4)]
        rows.append(np.repeat(r, 8))
        cols.append(np.tile(r, 8))
        values.append(k.ravel())
    by_element = coo_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))), shape=(dofmap.size, dofmap.size)).tocsr()
    assert (assemble(skewed, dofmap) != by_element).nnz == 0


def test_strains_and_section_forces_are_the_per_element_products_to_the_last_bit(skewed):
    u = np.random.default_rng(6).normal(size=(skewed.node_count, 2)) * 1e-4
    centroid, gauss = element_strains(skewed, u)
    forces = section_forces(skewed, centroid)
    for e in range(skewed.element_count):
        nodes = skewed.connectivity[e]
        u_e = u[nodes].ravel()
        assert np.array_equal(centroid[e], strain_displacement(skewed.xy[nodes], 0.0, 0.0)[0] @ u_e)
        for g, (xi, eta) in enumerate(GAUSS_POINTS):
            assert np.array_equal(gauss[e, g], strain_displacement(skewed.xy[nodes], xi, eta)[0] @ u_e)
        assert np.array_equal(forces[e], skewed.sections[skewed.element_section[e]].A @ centroid[e])


def test_the_first_clockwise_element_is_named(deck, skewed):
    connectivity = skewed.connectivity.copy()
    connectivity[5] = connectivity[5][::-1]
    connectivity[9] = connectivity[9][::-1]
    flipped = dataclasses.replace(skewed, connectivity=connectivity)
    instance, label = skewed.element_keys[5]
    with pytest.raises(KernelError, match=rf"^element {instance}\.{label}: element has det J = .* <= 0 at \(xi, eta\) = .*clockwise or it is degenerate"):
        assemble(flipped, constraint_map(deck, flipped))


@pytest.mark.parametrize("criterion", [c for c in CRITERIA if c != "max_strain"])  # the deck's material states no strain limits
def test_every_ply_ratio_and_mode_is_the_engine_per_ply_answer(deck, criterion):
    solution = solve_membrane(deck)
    f12 = deck_f12_star(deck)  # the deck states the Tsai-Wu f* (*Fail Stress)
    field = strength_ratios(solution, criterion, f12)
    mesh = solution.mesh
    states = element_ply_states(solution)
    for e in range(mesh.element_count):
        for k, ply in enumerate(mesh.sections[mesh.element_section[e]].plies):
            loaded = PlySurface(k, ply.angle_deg, 0.0, states.strain_xy[e][k], states.stress_xy[e][k], states.strain_12[e][k], states.stress_12[e][k])
            ratio, mode = face_strength_ratio(criterion, ply.material, PlySurface(k, ply.angle_deg, 0.0, ZERO, ZERO, ZERO, ZERO), loaded, f12)
            assert field.ratio[e][k] == ratio and field.mode[e][k] == mode
