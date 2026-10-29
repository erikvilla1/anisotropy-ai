"""The laminate membrane kernel: four-node plane-stress elements whose stiffness is the laminate's
membrane matrix `A` (ADR-0029). Theory and the function that computes each step: `fea/docs/theory.md`.

The element is the isoparametric bilinear quadrilateral with 2 by 2 Gauss integration. Kinematic
couplings become dof aliasing: every coupled node's in-plane displacement is the reference node's,
so the reference node's reaction is the sum over the coupled region. Prescribed displacements are
handled by partitioning the reduced system; the free part is solved with a sparse LU factorization.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import splu

from .mesh import KernelError, Mesh, mesh_from_deck
from .model import Deck, all_boundaries, coupled_nodes, membrane_limits, node_name, reference_node, resolve_nodes
from .results import MembraneSolution

# Natural coordinates of the four nodes, counterclockwise, and the 2 by 2 Gauss rule.
NATURAL = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])
_G = 1.0 / np.sqrt(3.0)
GAUSS_POINTS = np.array([[-_G, -_G], [_G, -_G], [_G, _G], [-_G, _G]])
GAUSS_WEIGHTS = np.ones(4)
IN_PLANE = (0, 1)  # dof components: 0 is u (Abaqus dof 1), 1 is v (Abaqus dof 2)
SINGULAR_PIVOT_RATIO = 1e-12  # an LU pivot this small relative to the largest means a free rigid-body mode


def shape_functions(xi: float, eta: float) -> np.ndarray:
    """N_i = (1 + xi_i xi)(1 + eta_i eta) / 4 for the four nodes."""
    return 0.25 * (1.0 + NATURAL[:, 0] * xi) * (1.0 + NATURAL[:, 1] * eta)


def shape_derivatives(xi: float, eta: float) -> np.ndarray:
    """Rows dN/dxi and dN/deta, shape (2, 4)."""
    return 0.25 * np.array([NATURAL[:, 0] * (1.0 + NATURAL[:, 1] * eta), NATURAL[:, 1] * (1.0 + NATURAL[:, 0] * xi)])


def jacobian(xy: np.ndarray, xi: float, eta: float) -> np.ndarray:
    """J = [[dx/dxi, dy/dxi], [dx/deta, dy/deta]] for node coordinates xy of shape (4, 2)."""
    return shape_derivatives(xi, eta) @ xy


def strain_displacement(xy: np.ndarray, xi: float, eta: float) -> tuple[np.ndarray, float]:
    """B (3 by 8) with rows eps_x, eps_y, gamma_xy for the dof order u1, v1, ..., u4, v4, and det J."""
    J = jacobian(xy, xi, eta)
    det = float(np.linalg.det(J))
    if det <= 0.0:
        raise KernelError(f"element has det J = {det:.3g} <= 0 at (xi, eta) = ({xi:.3g}, {eta:.3g}): "
                          "its nodes are listed clockwise or it is degenerate")
    dN = np.linalg.solve(J, shape_derivatives(xi, eta))  # rows dN/dx, dN/dy
    B = np.zeros((3, 8))
    B[0, 0::2] = dN[0]
    B[1, 1::2] = dN[1]
    B[2, 0::2] = dN[1]
    B[2, 1::2] = dN[0]
    return B, det


def element_stiffness(xy: np.ndarray, A: np.ndarray) -> np.ndarray:
    """k = sum over Gauss points of w B^T A B det J (8 by 8, N/m). A carries the thickness, so no thickness factor appears."""
    k = np.zeros((8, 8))
    for (xi, eta), weight in zip(GAUSS_POINTS, GAUSS_WEIGHTS):
        B, det = strain_displacement(xy, xi, eta)
        k += weight * det * (B.T @ A @ B)
    return k


@dataclass(frozen=True)
class DofMap:
    """How the full dofs (2 per mesh node) map to the reduced system the kernel solves."""

    representative: np.ndarray  # (ndof,) full dof -> the full dof it is aliased to (itself when not coupled)
    reduced: np.ndarray  # (ndof,) full dof -> reduced dof index
    representative_of_reduced: np.ndarray  # (nred,) reduced dof -> its representative full dof
    size: int
    prescribed: dict[int, float]  # reduced dof -> prescribed displacement, m
    loads: np.ndarray  # (nred,) concentrated loads, N


def constraint_map(deck: Deck, mesh: Mesh) -> DofMap:
    """Alias coupled nodes to their reference node, collect prescribed dofs and loads on the reduced system."""
    n = mesh.node_count
    representative = np.arange(2 * n)
    masters: set[int] = set()
    coupled_by: dict[int, str] = {}
    for coupling in deck.couplings:
        master = mesh.node(reference_node(deck, coupling))
        masters.add(master)
        for key in coupled_nodes(deck, coupling):
            slave = mesh.node(key)
            if slave in coupled_by:
                raise KernelError(f"node {node_name(key)} is driven by two couplings ({coupled_by[slave]!r} and {coupling.name!r})")
            coupled_by[slave] = coupling.name
            representative[2 * slave] = 2 * master
            representative[2 * slave + 1] = 2 * master + 1
    for master in masters:
        if master in coupled_by:
            raise KernelError(f"reference node {node_name(mesh.node_keys[master])} is itself coupled to another reference node; "
                              "chained couplings are not supported")
    attached = np.zeros(n, dtype=bool)
    attached[mesh.connectivity.ravel()] = True
    for master in masters:
        attached[master] = True
    for i, key in enumerate(mesh.node_keys):
        if not attached[i] and i not in coupled_by:
            raise KernelError(f"node {node_name(key)} belongs to no element and drives no coupling; its dofs would be free")
    representative_of_reduced, reduced = np.unique(representative, return_inverse=True)
    size = int(representative_of_reduced.size)

    prescribed: dict[int, float] = {}
    origin: dict[int, str] = {}
    for boundary in all_boundaries(deck):
        for dof in range(boundary.dof_first, boundary.dof_last + 1):
            if dof not in (1, 2):
                continue
            for key in resolve_nodes(deck, boundary.target, boundary.line):
                r = int(reduced[2 * mesh.node(key) + (dof - 1)])
                if r in prescribed and prescribed[r] != boundary.value:
                    raise KernelError(f"line {boundary.line}: {node_name(key)} dof {dof} = {boundary.value:g} conflicts with "
                                      f"{origin[r]}, which shares the same degree of freedom through a coupling")
                prescribed[r] = boundary.value
                origin[r] = f"{node_name(key)} dof {dof} = {boundary.value:g} (line {boundary.line})"
    loads = np.zeros(size)
    for step in deck.steps:
        for load in step.cloads:
            for key in resolve_nodes(deck, load.target, load.line):
                loads[reduced[2 * mesh.node(key) + (load.dof - 1)]] += load.value
    return DofMap(representative=representative, reduced=reduced, representative_of_reduced=representative_of_reduced,
                  size=size, prescribed=prescribed, loads=loads)


def assemble(mesh: Mesh, dofmap: DofMap) -> csr_matrix:
    """The reduced global stiffness: every element's k scattered through the dof map."""
    rows, cols, values = [], [], []
    for e in range(mesh.element_count):
        nodes = mesh.connectivity[e]
        try:
            k = element_stiffness(mesh.xy[nodes], mesh.sections[mesh.element_section[e]].A)
        except KernelError as exc:
            instance, label = mesh.element_keys[e]
            raise KernelError(f"element {instance}.{label}: {exc}") from None
        full = np.repeat(2 * nodes, 2) + np.tile([0, 1], 4)
        r = dofmap.reduced[full]
        rows.append(np.repeat(r, 8))
        cols.append(np.tile(r, 8))
        values.append(k.ravel())
    K = coo_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))), shape=(dofmap.size, dofmap.size))
    return K.tocsr()


def solve_membrane(deck: Deck, mesh: Mesh | None = None) -> MembraneSolution:
    """Displacements, reactions, element strains and section forces for a deck in SI. What the membrane cannot represent is refused by
    `membrane_limits` first; `kernel.solve_deck` sends such a deck to the flat shell instead."""
    membrane_limits(deck)
    mesh = mesh if mesh is not None else mesh_from_deck(deck)
    dofmap = constraint_map(deck, mesh)
    K = assemble(mesh, dofmap)
    f = dofmap.loads.copy()
    u = np.zeros(dofmap.size)
    fixed = np.array(sorted(dofmap.prescribed), dtype=int)
    values = np.array([dofmap.prescribed[r] for r in fixed], dtype=float)
    u[fixed] = values
    free = np.setdiff1d(np.arange(dofmap.size), fixed)
    if free.size:
        K_ff = K[free][:, free].tocsc()
        rhs = f[free] - (K[free][:, fixed] @ values if fixed.size else 0.0)
        try:
            factor = splu(K_ff)
        except RuntimeError as exc:
            raise KernelError(f"the stiffness matrix is singular ({exc}); a region can move as a rigid body or is disconnected. "
                              "Check the boundary conditions and couplings") from None
        pivots = np.abs(factor.U.diagonal())
        if pivots.min() <= SINGULAR_PIVOT_RATIO * pivots.max():
            raise KernelError(f"the stiffness matrix is singular to working precision (smallest pivot {pivots.min():.2g} against "
                              f"{pivots.max():.2g}); a region can move as a rigid body or is disconnected. Check the boundary conditions")
        u_free = factor.solve(rhs)
        if not np.all(np.isfinite(u_free)):
            raise KernelError("the solve produced non-finite displacements; the stiffness matrix is singular or badly scaled")
        u[free] = u_free
    residual = K @ u - f  # reactions at prescribed dofs; roundoff at free dofs
    displacement = u[dofmap.reduced].reshape(mesh.node_count, 2)
    reaction = np.zeros((mesh.node_count, 2))
    for r in fixed.tolist():
        full = int(dofmap.representative_of_reduced[r])
        reaction[full // 2, full % 2] = residual[r]
    free_residual = float(np.max(np.abs(residual[free]))) if free.size else 0.0
    strain, gauss_strain = element_strains(mesh, displacement)
    return MembraneSolution(mesh=mesh, displacement=displacement, reaction=reaction, strain=strain, gauss_strain=gauss_strain,
                            section_force=section_forces(mesh, strain), free_residual=free_residual)


def element_strains(mesh: Mesh, displacement: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Membrane strain eps = B u_e at each element's centroid (ne, 3) and at its four Gauss points (ne, 4, 3)."""
    centroid = np.zeros((mesh.element_count, 3))
    gauss = np.zeros((mesh.element_count, 4, 3))
    for e in range(mesh.element_count):
        nodes = mesh.connectivity[e]
        xy = mesh.xy[nodes]
        u_e = displacement[nodes].ravel()
        centroid[e] = strain_displacement(xy, 0.0, 0.0)[0] @ u_e
        for g, (xi, eta) in enumerate(GAUSS_POINTS):
            gauss[e, g] = strain_displacement(xy, xi, eta)[0] @ u_e
    return centroid, gauss


def section_forces(mesh: Mesh, strain: np.ndarray) -> np.ndarray:
    """N = A eps per element (ne, 3), N/m: the membrane resultants Abaqus reports as SF."""
    forces = np.zeros_like(strain)
    for e in range(mesh.element_count):
        forces[e] = mesh.sections[mesh.element_section[e]].A @ strain[e]
    return forces
