"""The plate kernel forms every element at once (ADR-0073 amendment 2): the stiffness, the pressure loads, the strains, curvatures and
section forces come out exactly as one call per element gives them, to the last bit, an element that cannot be formed is still named,
and the factors of the stiffness are SuperLU's in its symmetric mode."""

import dataclasses

import numpy as np
import pytest
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.mesh import KernelError, mesh_from_deck
from anisotropy_fea.model import resolve_elements, resolve_nodes
from anisotropy_fea.shell import (DOFS, SYMMETRIC_FACTOR, assemble_shell, bending_rows, constraint_map_shell, element_dofs, element_states,
                                  element_stiffness_shell, factor_stiffness, membrane_rows, physical_derivatives, pressure_loads, shear_rows,
                                  solve_shell)

DECKS = {"quasi-isotropic 10 by 5": paths.CHECK_DECKS / "plate-10x5-cae-layout-im7-8552.inp",
         "cross-ply 32 by 32": paths.CHECK_DECKS / "plate-ss-32x32-cross-ply-im7-8552.inp"}  # the second couples stretching and bending (B is not zero)


@pytest.fixture(scope="module", params=list(DECKS), ids=list(DECKS))
def deck(request):
    return read_deck(DECKS[request.param], "mm-MPa")


@pytest.fixture(scope="module")
def skewed(deck):
    """The plate's mesh with every node moved a little, so no two elements share a Jacobian."""
    mesh = mesh_from_deck(deck, shell=True)
    rng = np.random.default_rng(5)
    span = mesh.xy.max(axis=0) - mesh.xy.min(axis=0)
    return dataclasses.replace(mesh, xy=mesh.xy + rng.uniform(-0.02, 0.02, size=mesh.xy.shape) * span / 40)


def dofs_of(nodes: np.ndarray) -> np.ndarray:
    return np.repeat(DOFS * nodes, DOFS) + np.tile(np.arange(DOFS), 4)


def test_the_assembled_stiffness_is_the_per_element_sum_to_the_last_bit(deck, skewed):
    dofmap = constraint_map_shell(deck, skewed)
    rows, cols, values = [], [], []
    for e in range(skewed.element_count):
        nodes = skewed.connectivity[e]
        section = skewed.sections[skewed.element_section[e]]
        k = element_stiffness_shell(skewed.xy[nodes], section.A, section.B, section.D, section.H)
        r = dofmap.reduced[dofs_of(nodes)]
        rows.append(np.repeat(r, 4 * DOFS))
        cols.append(np.tile(r, 4 * DOFS))
        values.append(k.ravel())
    by_element = coo_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))), shape=(dofmap.size, dofmap.size)).tocsr()
    assert (assemble_shell(skewed, dofmap) != by_element).nnz == 0
    assert np.array_equal(element_dofs(skewed.connectivity), np.array([dofs_of(nodes) for nodes in skewed.connectivity]))


def test_the_pressure_loads_are_the_per_element_sums_to_the_last_bit(deck, skewed):
    dofmap = constraint_map_shell(deck, skewed)
    loads = np.zeros(dofmap.size)
    pressed = 0
    for step in deck.steps:  # the loads in the order the kernel adds them: a step's concentrated loads, then its pressures
        for load in step.cloads:
            for key in resolve_nodes(deck, load.target, load.line):
                loads[dofmap.reduced[DOFS * skewed.node(key) + (load.dof - 1)]] += load.value
        for dload in step.dloads:
            for key in resolve_elements(deck, dload.target, dload.line):
                nodes = skewed.connectivity[skewed.element(key)]
                np.add.at(loads, dofmap.reduced[dofs_of(nodes)], pressure_loads(skewed.xy[nodes], dload.value))
                pressed += 1
    assert pressed == skewed.element_count and np.any(loads != 0.0)
    assert np.array_equal(dofmap.loads, loads)


def test_strains_curvatures_and_section_forces_are_the_per_element_products_to_the_last_bit(deck, skewed):
    u = np.random.default_rng(6).normal(size=(skewed.node_count, DOFS)) * 1e-4
    strain, curvature, shear = element_states(skewed, u)
    for e in range(skewed.element_count):
        nodes = skewed.connectivity[e]
        xy, u_e = skewed.xy[nodes], u[nodes].ravel()
        dN, _ = physical_derivatives(xy, 0.0, 0.0)
        assert np.array_equal(strain[e], membrane_rows(dN) @ u_e)
        assert np.array_equal(curvature[e], bending_rows(dN) @ u_e)
        assert np.array_equal(shear[e], shear_rows(xy, 0.0, 0.0) @ u_e)
    solution = solve_shell(deck, skewed)
    for e in range(skewed.element_count):
        s = skewed.sections[skewed.element_section[e]]
        assert np.array_equal(solution.section_force[e], s.A @ solution.strain[e] + s.B @ solution.curvature[e])
        assert np.array_equal(solution.moment[e], s.B @ solution.strain[e] + s.D @ solution.curvature[e])
        assert np.array_equal(solution.shear_force[e], s.H @ solution.shear_strain[e])


def test_every_held_dof_carries_its_reaction_and_no_other_dof_does(deck, skewed):
    solution = solve_shell(deck, skewed)
    dofmap = constraint_map_shell(deck, skewed)
    held = np.zeros((skewed.node_count, DOFS), dtype=bool)
    for r in dofmap.prescribed:
        full = int(dofmap.representative_of_reduced[r])
        held[full // DOFS, full % DOFS] = True
    assert held.any() and np.all(solution.reaction[~held] == 0.0) and np.any(solution.reaction[held] != 0.0)


def test_the_first_element_that_cannot_be_formed_is_named(deck, skewed):
    connectivity = skewed.connectivity.copy()
    connectivity[5] = connectivity[5][::-1]
    connectivity[9] = connectivity[9][::-1]
    flipped = dataclasses.replace(skewed, connectivity=connectivity)
    instance, label = skewed.element_keys[5]
    with pytest.raises(KernelError, match=rf"^element {instance}\.{label}: element has det J = .* <= 0 at \(xi, eta\) = .*clockwise or it is degenerate"):
        assemble_shell(flipped, constraint_map_shell(deck, skewed))
    membrane_only = mesh_from_deck(deck)  # without shell=True a section carries A alone
    with pytest.raises(KernelError, match="carries no bending stiffness; build the mesh with mesh_from_deck"):
        assemble_shell(membrane_only, constraint_map_shell(deck, skewed))


def free_stiffness(deck, mesh):
    dofmap = constraint_map_shell(deck, mesh)
    K = assemble_shell(mesh, dofmap)
    free = np.setdiff1d(np.arange(dofmap.size), np.array(sorted(dofmap.prescribed), dtype=int))
    return K[free][:, free].tocsc(), dofmap.loads[free]


def test_the_factors_are_the_symmetric_ones_and_fill_less_than_the_default(deck):
    """The three settings belong together. The ordering for a symmetric pattern with SuperLU's own pivoting (the slow case: 46 s
    against 0.5 s on a 50 by 50 plate, measured 2026-11-17) fills the factors several times over; with the pivot kept on the diagonal
    it fills them less than SuperLU's defaults do."""
    assert SYMMETRIC_FACTOR == {"permc_spec": "MMD_AT_PLUS_A", "diag_pivot_thresh": 0.0, "options": {"SymmetricMode": True}}
    K, f = free_stiffness(deck, mesh_from_deck(deck, shell=True))
    assert abs(K - K.T).max() <= 1e-9 * abs(K).max()  # the mode is for a symmetric matrix, which the stiffness is
    fill = lambda factor: factor.L.nnz + factor.U.nnz  # noqa: E731
    ours, default, slow = factor_stiffness(K), splu(K), splu(K, permc_spec="MMD_AT_PLUS_A")
    assert fill(ours) < fill(default) < fill(slow)
    pivots = np.abs(ours.U.diagonal())
    assert pivots.min() > 1e-9 * pivots.max()  # a held plate: no pivot vanishes without row exchanges
    u, reference = ours.solve(f), default.solve(f)
    assert np.abs(u - reference).max() <= 1e-8 * np.abs(reference).max()
