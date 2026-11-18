"""The laminate flat shell kernel: four-node Reissner-Mindlin plate elements with mixed-interpolated transverse shear (MITC4) on
the laminate's A, B, D and transverse shear stiffness (ADR-0053). Theory and the function that computes each step:
`fea/docs/theory.md`, Section 8.

Every node has five degrees of freedom: u, v, w and the rotations theta_x, theta_y about the x and y axes (Abaqus dofs 1 to 5). The
drilling rotation, dof 6, has no stiffness in a flat plate and is not carried. In-plane displacement through the thickness follows
the rotations, u = u_0 + z theta_y, v = v_0 - z theta_x, so the curvatures are kappa_x = theta_y,x, kappa_y = -theta_x,y and
kappa_xy = theta_y,y - theta_x,x, and the transverse shear strains gamma_xz = w,x + theta_y and gamma_yz = w,y - theta_x. Membrane
and bending strains come from the bilinear interpolation; the transverse shear strains are interpolated from the element's edge
midpoints (Bathe and Dvorkin's MITC4 tying), which is what keeps a thin plate from locking. Section forces follow the engine's
laminate law, N = A eps_0 + B kappa, M = B eps_0 + D kappa, and Q = H gamma with H the shear-corrected transverse stiffness.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import splu

from .membrane import GAUSS_POINTS, GAUSS_WEIGHTS, SINGULAR_PIVOT_RATIO, jacobian, shape_derivatives, shape_functions
from .mesh import KernelError, Mesh, is_symmetric_layup, mesh_from_deck
from .model import Deck, all_boundaries, coupled_nodes, node_name, reference_node, resolve_elements, resolve_nodes, section_plies
from .results import ShellSolution

DOFS = 5  # u, v, w, theta_x, theta_y per node: Abaqus dofs 1 to 5
PLATE_DOFS = (3, 4, 5)
TYING = {"A": (0.0, 1.0), "B": (-1.0, 0.0), "C": (0.0, -1.0), "D": (1.0, 0.0)}  # edge midpoints, in natural coordinates
# How SuperLU factors the plate's stiffness (ADR-0073 amendment 2). The three belong together: the ordering is the one for a symmetric
# pattern, and the pivot stays on the diagonal so that ordering holds. The ordering without the diagonal pivot fills the factor in
# (ten times the entries on a 20 by 20 plate) and is far slower than SuperLU's defaults; `test_shell_solve.py` holds the fill.
SYMMETRIC_FACTOR = {"permc_spec": "MMD_AT_PLUS_A", "diag_pivot_thresh": 0.0, "options": {"SymmetricMode": True}}


def membrane_rows(dN: np.ndarray) -> np.ndarray:
    """B_m (3 by 20): eps_x, eps_y, gamma_xy from u and v, for the dof order u, v, w, theta_x, theta_y per node; dN holds dN/dx, dN/dy."""
    B = np.zeros((3, 4 * DOFS))
    for i in range(4):
        B[0, DOFS * i] = dN[0, i]
        B[1, DOFS * i + 1] = dN[1, i]
        B[2, DOFS * i] = dN[1, i]
        B[2, DOFS * i + 1] = dN[0, i]
    return B


def bending_rows(dN: np.ndarray) -> np.ndarray:
    """B_b (3 by 20): kappa_x = theta_y,x, kappa_y = -theta_x,y, kappa_xy = theta_y,y - theta_x,x."""
    B = np.zeros((3, 4 * DOFS))
    for i in range(4):
        B[0, DOFS * i + 4] = dN[0, i]
        B[1, DOFS * i + 3] = -dN[1, i]
        B[2, DOFS * i + 4] = dN[1, i]
        B[2, DOFS * i + 3] = -dN[0, i]
    return B


def covariant_shear_rows(xy: np.ndarray, xi: float, eta: float) -> np.ndarray:
    """The covariant transverse shear strains at one point from the bilinear fields, rows gamma_xi and gamma_eta (2 by 20):
    gamma_xi = w,xi + x,xi theta_y - y,xi theta_x, and the same with eta."""
    N = shape_functions(xi, eta)
    dN = shape_derivatives(xi, eta)
    J = jacobian(xy, xi, eta)
    rows = np.zeros((2, 4 * DOFS))
    for i in range(4):
        for r in range(2):
            rows[r, DOFS * i + 2] = dN[r, i]
            rows[r, DOFS * i + 4] = J[r, 0] * N[i]
            rows[r, DOFS * i + 3] = -J[r, 1] * N[i]
    return rows


def shear_rows(xy: np.ndarray, xi: float, eta: float) -> np.ndarray:
    """B_s (2 by 20): gamma_xz, gamma_yz at a point by the MITC4 tying. gamma_xi is interpolated linearly in eta between its values
    at the edge midpoints A (0, 1) and C (0, -1), gamma_eta linearly in xi between D (1, 0) and B (-1, 0); the Cartesian strains follow
    from [gamma_xi, gamma_eta]^T = J [gamma_xz, gamma_yz]^T."""
    a = covariant_shear_rows(xy, *TYING["A"])[0]
    c = covariant_shear_rows(xy, *TYING["C"])[0]
    d = covariant_shear_rows(xy, *TYING["D"])[1]
    b = covariant_shear_rows(xy, *TYING["B"])[1]
    covariant = np.vstack([0.5 * (1.0 + eta) * a + 0.5 * (1.0 - eta) * c, 0.5 * (1.0 + xi) * d + 0.5 * (1.0 - xi) * b])
    return np.linalg.solve(jacobian(xy, xi, eta), covariant)


def physical_derivatives(xy: np.ndarray, xi: float, eta: float) -> tuple[np.ndarray, float]:
    """dN/dx and dN/dy (2 by 4) and det J at a point; a non-positive det J is refused as in the membrane element."""
    J = jacobian(xy, xi, eta)
    det = float(np.linalg.det(J))
    if det <= 0.0:
        raise KernelError(f"element has det J = {det:.3g} <= 0 at (xi, eta) = ({xi:.3g}, {eta:.3g}): its nodes are listed clockwise or it is degenerate")
    return np.linalg.solve(J, shape_derivatives(xi, eta)), det


def element_stiffness_shell(xy: np.ndarray, A: np.ndarray, B: np.ndarray, D: np.ndarray, H: np.ndarray) -> np.ndarray:
    """k (20 by 20) = sum over the 2 by 2 Gauss points of w det J (B_m^T A B_m + B_m^T B B_b + B_b^T B B_m + B_b^T D B_b + B_s^T H B_s)."""
    k = np.zeros((4 * DOFS, 4 * DOFS))
    for (xi, eta), weight in zip(GAUSS_POINTS, GAUSS_WEIGHTS):
        dN, det = physical_derivatives(xy, xi, eta)
        Bm, Bb, Bs = membrane_rows(dN), bending_rows(dN), shear_rows(xy, xi, eta)
        k += weight * det * (Bm.T @ A @ Bm + Bm.T @ B @ Bb + Bb.T @ B @ Bm + Bb.T @ D @ Bb + Bs.T @ H @ Bs)
    return k


def pressure_loads(xy: np.ndarray, pressure: float) -> np.ndarray:
    """Consistent nodal forces on w (20 entries) of a uniform pressure p on the element: f_i = -p sum_g w_g N_i det J. A positive
    pressure pushes against the element's normal (+z for counterclockwise nodes): it presses on the top face, as a spec states a
    pressure and as Abaqus's *Dsload P on the SPOS face acts (ADR-0053). The P label of *Dload on a shell element is the other way in
    Abaqus and in CalculiX alike, positive along the normal: seen on Abaqus 2025 on 2026-11-17 (ADR-0053 amendment 1) and on CalculiX by
    a run on 2026-10-28 (fea/checks/calculix-conventions.toml, pressure_direction). The reader and the writers change the sign."""
    f = np.zeros(4 * DOFS)
    for (xi, eta), weight in zip(GAUSS_POINTS, GAUSS_WEIGHTS):
        _, det = physical_derivatives(xy, xi, eta)
        N = shape_functions(xi, eta)
        for i in range(4):
            f[DOFS * i + 2] += -pressure * weight * det * N[i]
    return f


def element_xy(mesh: Mesh, elements: np.ndarray | None = None) -> np.ndarray:
    """The corner coordinates of every element (ne, 4, 2), or of the elements listed."""
    connectivity = mesh.connectivity if elements is None else mesh.connectivity[elements]
    return mesh.xy[connectivity].reshape(len(connectivity), 4, 2)


def jacobians_all(xy: np.ndarray, points) -> tuple[np.ndarray, np.ndarray]:
    """J (points, ne, 2, 2) and det J (points, ne) of every element at each natural point, the operations of `jacobian` and
    `physical_derivatives` on a stack (ADR-0073 amendment 2)."""
    J = np.array([shape_derivatives(xi, eta) @ xy for xi, eta in points]).reshape(len(points), len(xy), 2, 2)
    det = np.linalg.det(J) if len(xy) else np.zeros((len(points), 0))
    return J, det


def first_inverted(det: np.ndarray) -> tuple[int, int] | None:
    """The first element, and in it the first point, with det J <= 0: the one a call per element would refuse. None when every
    element is sound."""
    bad = det <= 0.0
    if not bad.any():
        return None
    e = int(np.flatnonzero(bad.any(axis=0))[0])
    return e, int(np.flatnonzero(bad[:, e])[0])


def inverted_message(det: np.ndarray, points, e: int, g: int) -> str:
    xi, eta = points[g]
    return (f"element has det J = {float(det[g, e]):.3g} <= 0 at (xi, eta) = ({float(xi):.3g}, {float(eta):.3g}): "
            "its nodes are listed clockwise or it is degenerate")


def covariant_shear_rows_all(xy: np.ndarray, xi: float, eta: float) -> np.ndarray:
    """`covariant_shear_rows` for every element at one point: (ne, 2, 20)."""
    N = shape_functions(xi, eta)
    dN = shape_derivatives(xi, eta)
    J = dN @ xy
    rows = np.zeros((len(xy), 2, 4 * DOFS))
    rows[:, :, 2::DOFS] = dN
    rows[:, :, 4::DOFS] = J[:, :, 0:1] * N
    rows[:, :, 3::DOFS] = -J[:, :, 1:2] * N
    return rows


def shell_rows_all(xy: np.ndarray, points, J: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """B_m, B_b (points, ne, 3, 20) and B_s (points, ne, 2, 20) of every element at each natural point: `membrane_rows`,
    `bending_rows` and `shear_rows` on a stack, the same operations in the same order, so the same numbers to the last bit
    (ADR-0073 amendment 2). The elements are sound: det J > 0 at every point (`first_inverted`)."""
    ne = len(xy)
    Bm, Bb, Bs = (np.zeros((len(points), ne, rows, 4 * DOFS)) for rows in (3, 3, 2))
    if not ne:
        return Bm, Bb, Bs
    a = covariant_shear_rows_all(xy, *TYING["A"])[:, 0]
    c = covariant_shear_rows_all(xy, *TYING["C"])[:, 0]
    d = covariant_shear_rows_all(xy, *TYING["D"])[:, 1]
    b = covariant_shear_rows_all(xy, *TYING["B"])[:, 1]
    for g, (xi, eta) in enumerate(points):
        dN = np.linalg.solve(J[g], np.broadcast_to(shape_derivatives(xi, eta), (ne, 2, 4)))  # rows dN/dx, dN/dy
        Bm[g, :, 0, 0::DOFS] = dN[:, 0]
        Bm[g, :, 1, 1::DOFS] = dN[:, 1]
        Bm[g, :, 2, 0::DOFS] = dN[:, 1]
        Bm[g, :, 2, 1::DOFS] = dN[:, 0]
        Bb[g, :, 0, 4::DOFS] = dN[:, 0]
        Bb[g, :, 1, 3::DOFS] = -dN[:, 1]
        Bb[g, :, 2, 4::DOFS] = dN[:, 1]
        Bb[g, :, 2, 3::DOFS] = -dN[:, 0]
        covariant = np.stack([0.5 * (1.0 + eta) * a + 0.5 * (1.0 - eta) * c, 0.5 * (1.0 + xi) * d + 0.5 * (1.0 - xi) * b], axis=1)
        Bs[g] = np.linalg.solve(J[g], covariant)
    return Bm, Bb, Bs


def element_sections(mesh: Mesh) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Every element's A, B, D (ne, 3, 3) and H (ne, 2, 2), from its section."""
    of = np.asarray(mesh.element_section, dtype=int)
    return tuple(np.array([getattr(section, name) for section in mesh.sections], dtype=float).reshape(len(mesh.sections), size, size)[of]
                 for name, size in (("A", 3), ("B", 3), ("D", 3), ("H", 2)))


def element_stiffness_shell_all(mesh: Mesh) -> np.ndarray:
    """`element_stiffness_shell` for every element at once (ne, 20, 20): the same sum over the Gauss points (ADR-0073 amendment 2).
    The first element a call per element would refuse is refused with the same words: a section without bending stiffness, or
    det J <= 0, named as `assemble_shell` names it."""
    without = np.array([section.D is None or section.H is None or section.B is None for section in mesh.sections], dtype=bool)
    missing = without[np.asarray(mesh.element_section, dtype=int)] if mesh.element_count else np.zeros(0, dtype=bool)
    xy = element_xy(mesh)
    points = [(float(xi), float(eta)) for xi, eta in GAUSS_POINTS]
    J, det = jacobians_all(xy, points)
    inverted = first_inverted(det)
    if missing.any() and (inverted is None or int(np.flatnonzero(missing)[0]) <= inverted[0]):
        section = mesh.sections[mesh.element_section[int(np.flatnonzero(missing)[0])]]
        raise KernelError(f"section {section.name!r} carries no bending stiffness; build the mesh with mesh_from_deck(deck, shell=True)")
    if inverted is not None:
        instance, label = mesh.element_keys[inverted[0]]
        raise KernelError(f"element {instance}.{label}: {inverted_message(det, points, *inverted)}")
    A, B, D, H = element_sections(mesh)
    Bm, Bb, Bs = shell_rows_all(xy, points, J)
    k = np.zeros((mesh.element_count, 4 * DOFS, 4 * DOFS))
    for g, weight in enumerate(GAUSS_WEIGHTS):
        m, b, s = Bm[g], Bb[g], Bs[g]
        mT, bT, sT = m.transpose(0, 2, 1), b.transpose(0, 2, 1), s.transpose(0, 2, 1)
        k += (weight * det[g])[:, None, None] * (mT @ A @ m + mT @ B @ b + bT @ B @ m + bT @ D @ b + sT @ H @ s)
    return k


def pressure_loads_all(xy: np.ndarray, pressure: float) -> np.ndarray:
    """`pressure_loads` for a stack of elements (ne, 20); an element with det J <= 0 is refused as one call would refuse it."""
    points = [(float(xi), float(eta)) for xi, eta in GAUSS_POINTS]
    _, det = jacobians_all(xy, points)
    inverted = first_inverted(det)
    if inverted is not None:
        raise KernelError(inverted_message(det, points, *inverted))
    f = np.zeros((len(xy), 4 * DOFS))
    for g, ((xi, eta), weight) in enumerate(zip(points, GAUSS_WEIGHTS)):
        N = shape_functions(xi, eta)
        for i in range(4):
            f[:, DOFS * i + 2] += -pressure * weight * det[g] * N[i]
    return f


@dataclass(frozen=True)
class ShellDofMap:
    """How the full dofs (5 per mesh node) map to the reduced system the kernel solves."""

    representative: np.ndarray
    reduced: np.ndarray
    representative_of_reduced: np.ndarray
    size: int
    prescribed: dict[int, float]
    loads: np.ndarray
    notes: tuple[str, ...]  # what was accepted without effect: a boundary on the drilling dof


def constraint_map_shell(deck: Deck, mesh: Mesh) -> ShellDofMap:
    """Alias coupled nodes to their reference node in every coupled dof, collect prescribed dofs 1 to 5, concentrated loads on dofs 1 to 5
    and the consistent nodal forces of distributed pressures; a boundary on dof 6 is noted and dropped, a load on dof 6 refused."""
    n = mesh.node_count
    representative = np.arange(DOFS * n)
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
            for dof in sorted(coupling.dofs):
                if dof <= DOFS:
                    representative[DOFS * slave + dof - 1] = DOFS * master + dof - 1
    for master in masters:
        if master in coupled_by:
            raise KernelError(f"reference node {node_name(mesh.node_keys[master])} is itself coupled to another reference node; chained couplings are not supported")
    attached = np.zeros(n, dtype=bool)
    attached[mesh.connectivity.ravel()] = True
    for master in masters:
        attached[master] = True
    for i in np.flatnonzero(~attached).tolist():
        if i not in coupled_by:
            raise KernelError(f"node {node_name(mesh.node_keys[i])} belongs to no element and drives no coupling; its dofs would be free")
    representative_of_reduced, reduced = np.unique(representative, return_inverse=True)
    size = int(representative_of_reduced.size)
    prescribed: dict[int, float] = {}
    origin: dict[int, str] = {}
    notes: list[str] = []
    for boundary in all_boundaries(deck):
        for dof in range(boundary.dof_first, boundary.dof_last + 1):
            if dof == 6:
                if not notes:
                    notes.append(f"line {boundary.line}: a boundary on dof 6 (the drilling rotation) has no effect in a flat plate and is dropped")
                continue
            for key in resolve_nodes(deck, boundary.target, boundary.line):
                r = int(reduced[DOFS * mesh.node(key) + (dof - 1)])
                if r in prescribed and prescribed[r] != boundary.value:
                    raise KernelError(f"line {boundary.line}: {node_name(key)} dof {dof} = {boundary.value:g} conflicts with {origin[r]}, which shares the same "
                                      "degree of freedom through a coupling")
                prescribed[r] = boundary.value
                origin[r] = f"{node_name(key)} dof {dof} = {boundary.value:g} (line {boundary.line})"
    loads = np.zeros(size)
    for step in deck.steps:
        for load in step.cloads:
            if load.dof == 6:
                raise KernelError(f"line {load.line}: a load on dof 6 (the drilling rotation) has nothing to act on in a flat plate")
            for key in resolve_nodes(deck, load.target, load.line):
                loads[reduced[DOFS * mesh.node(key) + (load.dof - 1)]] += load.value
        for dload in step.dloads:  # every element of a pressure at once, added in the elements' order (ADR-0073 amendment 2)
            pressed = np.array([mesh.element(key) for key in resolve_elements(deck, dload.target, dload.line)], dtype=int)
            if pressed.size:
                f = pressure_loads_all(element_xy(mesh, pressed), dload.value)
                np.add.at(loads, reduced[element_dofs(mesh.connectivity[pressed])], f)
    return ShellDofMap(representative=representative, reduced=reduced, representative_of_reduced=representative_of_reduced, size=size,
                       prescribed=prescribed, loads=loads, notes=tuple(notes))


def element_dofs(connectivity: np.ndarray) -> np.ndarray:
    """The full dofs of each element (ne, 20): u, v, w, theta_x, theta_y of its first node, then of the next."""
    return (np.repeat(DOFS * np.asarray(connectivity, dtype=int), DOFS, axis=1) + np.tile(np.arange(DOFS), 4)).astype(int)


def assemble_shell(mesh: Mesh, dofmap: ShellDofMap) -> csr_matrix:
    """The reduced global stiffness: every element's k scattered through the dof map. Every element's k is formed at once
    (`element_stiffness_shell_all`), in the elements' order, so the sums are the ones a loop over the elements makes."""
    k = element_stiffness_shell_all(mesh)
    r = dofmap.reduced[element_dofs(mesh.connectivity)]
    rows = np.repeat(r, 4 * DOFS, axis=1).ravel()
    cols = np.tile(r, (1, 4 * DOFS)).ravel()
    K = coo_matrix((k.reshape(mesh.element_count, (4 * DOFS) ** 2).ravel(), (rows, cols)), shape=(dofmap.size, dofmap.size))
    return K.tocsr()


def factor_stiffness(K_ff):
    """The sparse LU factors of the free part of the stiffness, which is symmetric and positive definite once the plate is held:
    SuperLU in its symmetric mode (`SYMMETRIC_FACTOR`). A matrix that is not held shows as a zero or a vanishing pivot, which
    `solve_shell` refuses."""
    return splu(K_ff, **SYMMETRIC_FACTOR)


def needs_shell(deck: Deck) -> bool:
    """Whether a deck asks for what the membrane cannot give: a prescribed out-of-plane displacement or rotation with a value, a load on
    dofs 3 to 5, a distributed pressure, or a section whose B does not vanish. Everything else stays with the membrane kernel, whose
    results the committed cases and records pin."""
    for boundary in all_boundaries(deck):
        if boundary.value != 0.0 and any(boundary.dof_first <= d <= boundary.dof_last for d in PLATE_DOFS):
            return True
    for step in deck.steps:
        if any(load.dof in PLATE_DOFS and load.value != 0.0 for load in step.cloads) or step.dloads:
            return True
    for part in deck.parts.values():
        for section in part.sections:
            if not is_symmetric_layup(section_plies(section, deck.materials)):
                return True
    return False


def solve_shell(deck: Deck, mesh: Mesh | None = None) -> ShellSolution:
    """Displacements and rotations, reactions, element strains, curvatures, transverse shear strains and section forces, moments and
    shear forces for a deck in SI."""
    mesh = mesh if mesh is not None else mesh_from_deck(deck, shell=True)
    dofmap = constraint_map_shell(deck, mesh)
    K = assemble_shell(mesh, dofmap)
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
            factor = factor_stiffness(K_ff)
        except RuntimeError as exc:
            raise KernelError(f"the stiffness matrix is singular ({exc}); a region can move as a rigid body or is disconnected. Check the boundary "
                              "conditions: a plate needs its translations and its two tilts held somewhere") from None
        pivots = np.abs(factor.U.diagonal())
        if pivots.min() <= SINGULAR_PIVOT_RATIO * pivots.max():
            raise KernelError(f"the stiffness matrix is singular to working precision (smallest pivot {pivots.min():.2g} against {pivots.max():.2g}); "
                              "a region can move as a rigid body or is disconnected. Check the boundary conditions: a plate needs its translations "
                              "and its two tilts held somewhere")
        u_free = factor.solve(rhs)
        if not np.all(np.isfinite(u_free)):
            raise KernelError("the solve produced non-finite displacements; the stiffness matrix is singular or badly scaled")
        u[free] = u_free
    residual = K @ u - f
    displacement = u[dofmap.reduced].reshape(mesh.node_count, DOFS)
    reaction = np.zeros((mesh.node_count, DOFS))
    held = dofmap.representative_of_reduced[fixed].astype(int)
    reaction[held // DOFS, held % DOFS] = residual[fixed]
    free_residual = float(np.max(np.abs(residual[free]))) if free.size else 0.0
    strain0, curvature, shear = element_states(mesh, displacement)
    A, B, D, H = element_sections(mesh)  # N = A eps + B kappa, M = B eps + D kappa, Q = H gamma, every element at once
    on = lambda stiffness, values: (stiffness @ values[:, :, None])[:, :, 0]  # noqa: E731
    N = on(A, strain0) + on(B, curvature)
    M = on(B, strain0) + on(D, curvature)
    Q = on(H, shear)
    return ShellSolution(mesh=mesh, displacement=displacement, reaction=reaction, strain=strain0, curvature=curvature, shear_strain=shear,
                         section_force=N, moment=M, shear_force=Q, free_residual=free_residual, notes=dofmap.notes)


def element_states(mesh: Mesh, displacement: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Membrane strain, curvature and transverse shear strain at every element's centroid, from the nodal displacements (n, 5),
    every element at once (ADR-0073 amendment 2)."""
    ne = mesh.element_count
    if not ne:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 2))
    xy = element_xy(mesh)
    centroid = [(0.0, 0.0)]
    J, det = jacobians_all(xy, centroid)
    inverted = first_inverted(det)
    if inverted is not None:
        raise KernelError(inverted_message(det, centroid, *inverted))
    Bm, Bb, Bs = shell_rows_all(xy, centroid, J)
    u = np.asarray(displacement)[mesh.connectivity].reshape(ne, 4 * DOFS, 1)
    return (Bm[0] @ u)[:, :, 0], (Bb[0] @ u)[:, :, 0], (Bs[0] @ u)[:, :, 0]
