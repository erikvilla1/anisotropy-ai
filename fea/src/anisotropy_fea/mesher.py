"""Meshes we generate ourselves (ADR-0030): a structured rectangle now, Gmsh geometries in a later chunk.

`Mesh2D` is the solver-neutral mesh: node coordinates in metres, four corner nodes per element listed
counterclockwise, optional midside nodes for 8-node elements, and named node and element sets. Its
invariants are checked on construction, so a deck written from it is a valid S4R or S8R mesh by construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DUPLICATE_TOLERANCE = 1e-9  # relative to the characteristic size
MIDSIDE_TOLERANCE = 1e-9


class MeshError(ValueError):
    """The mesh would not be a valid finite element mesh."""


@dataclass(frozen=True)
class Mesh2D:
    xy: np.ndarray  # (n, 2) metres: corner nodes first, then midside nodes when order == 2
    corners: np.ndarray  # (ne, 4) node indices, counterclockwise viewed from +z
    midside: np.ndarray | None  # (ne, 4) midside node indices of edges 1-2, 2-3, 3-4, 4-1; None for order 1
    node_sets: dict[str, np.ndarray] = field(default_factory=dict)  # sorted indices; edge sets include midside nodes at order 2
    element_sets: dict[str, np.ndarray] = field(default_factory=dict)
    order: int = 1
    mesher: str = "structured"

    def __post_init__(self) -> None:
        xy, corners = np.asarray(self.xy, dtype=float), np.asarray(self.corners, dtype=int)
        object.__setattr__(self, "xy", xy)
        object.__setattr__(self, "corners", corners)
        if xy.ndim != 2 or xy.shape[1] != 2 or corners.ndim != 2 or corners.shape[1] != 4:
            raise MeshError("xy must be (n, 2) and corners (ne, 4)")
        if (self.midside is None) != (self.order == 1):
            raise MeshError("order 2 needs midside nodes and order 1 must not have them")
        n = xy.shape[0]
        if corners.size and (corners.min() < 0 or corners.max() >= n):
            raise MeshError("an element names a node outside the mesh")
        size = float(np.max(np.ptp(xy, axis=0))) if n > 1 else 1.0
        for e, nodes in enumerate(corners):
            if len(set(nodes.tolist())) != 4:
                raise MeshError(f"element {e + 1}: repeated corner node")
            p = xy[nodes]
            # twice the signed area by the shoelace formula; counterclockwise is positive
            area2 = sum(p[i, 0] * p[(i + 1) % 4, 1] - p[(i + 1) % 4, 0] * p[i, 1] for i in range(4))
            if area2 <= 0:
                raise MeshError(f"element {e + 1}: corner nodes are clockwise or the element is degenerate")
        if self.midside is not None:
            midside = np.asarray(self.midside, dtype=int)
            object.__setattr__(self, "midside", midside)
            if midside.shape != corners.shape:
                raise MeshError("midside must be (ne, 4)")
            for e, (nodes, mids) in enumerate(zip(corners, midside)):
                for k in range(4):
                    expected = 0.5 * (xy[nodes[k]] + xy[nodes[(k + 1) % 4]])
                    if np.linalg.norm(xy[mids[k]] - expected) > MIDSIDE_TOLERANCE * size:
                        raise MeshError(f"element {e + 1}: midside node {mids[k] + 1} is not at the midpoint of edge {k + 1}")
        if n > 1:
            rounded = np.round(xy / (DUPLICATE_TOLERANCE * size)).astype(np.int64)
            if np.unique(rounded, axis=0).shape[0] != n:
                raise MeshError("two nodes share the same coordinates")
        for name, indices in self.node_sets.items():
            if indices.size and (indices.min() < 0 or indices.max() >= n):
                raise MeshError(f"node set {name!r} names a node outside the mesh")
        for name, indices in self.element_sets.items():
            if indices.size and (indices.min() < 0 or indices.max() >= corners.shape[0]):
                raise MeshError(f"element set {name!r} names an element outside the mesh")

    @property
    def node_count(self) -> int:
        return int(self.xy.shape[0])

    @property
    def element_count(self) -> int:
        return int(self.corners.shape[0])

    def connectivity(self) -> np.ndarray:
        """(ne, 4) for order 1; (ne, 8) corners then midsides for order 2: the S4R and S8R node orders."""
        return self.corners if self.midside is None else np.hstack([self.corners, self.midside])

    def corner_mesh(self) -> "Mesh2D":
        """The order-1 mesh on the same corner nodes: the S4R twin of an S8R mesh."""
        if self.order == 1:
            return self
        used = np.unique(self.corners)
        new_index = -np.ones(self.node_count, dtype=int)
        new_index[used] = np.arange(used.size)
        node_sets = {name: np.sort(new_index[idx[new_index[idx] >= 0]]) for name, idx in self.node_sets.items()}
        return Mesh2D(xy=self.xy[used], corners=new_index[self.corners], midside=None, node_sets=node_sets,
                      element_sets=dict(self.element_sets), order=1, mesher=self.mesher)

    def centroids(self) -> np.ndarray:
        return self.xy[self.corners].mean(axis=1)

    def nearest_node(self, point: tuple[float, float]) -> int:
        """The nearest corner node (midside nodes are skipped, so a probe names the same node at order 1 and 2)."""
        candidates = np.unique(self.corners)
        distances = np.linalg.norm(self.xy[candidates] - np.asarray(point, dtype=float), axis=1)
        return int(candidates[int(np.argmin(distances))])

    def nearest_element(self, point: tuple[float, float]) -> int:
        return int(np.argmin(np.linalg.norm(self.centroids() - np.asarray(point, dtype=float), axis=1)))


def counts_from_size(width: float, length: float, element_size: float) -> tuple[int, int]:
    return max(1, math.ceil(width / element_size - 1e-9)), max(1, math.ceil(length / element_size - 1e-9))


def structured_rectangle(width: float, length: float, nx: int, ny: int, order: int = 1,
                         node_rows: dict[str, float] | None = None, element_bands: dict[str, tuple[float, float]] | None = None,
                         node_bands: dict[str, tuple[float, float]] | None = None, tolerance: float = 1e-9) -> Mesh2D:
    """A rectangle [0, width] x [0, length] with nx by ny elements, loading axis y.

    Node sets: Grip-Bottom (y = 0), Grip-Top (y = length), Edge-Left (x = 0), Edge-Right (x = width), one set per
    entry of `node_rows` (name -> y) which must coincide with a node row, and one per entry of `node_bands`
    (name -> (y0, y1)) holding every node in the band; a band set replaces a default set of the same name.
    Element sets: one per entry of `element_bands` (name -> (y0, y1)) holding the elements whose centroid lies in the band.
    """
    if nx < 1 or ny < 1:
        raise MeshError("nx and ny must be at least 1")
    if order not in (1, 2):
        raise MeshError("order must be 1 or 2")
    label = lambda i, j: i + (nx + 1) * j  # noqa: E731
    xs, ys = np.linspace(0.0, width, nx + 1), np.linspace(0.0, length, ny + 1)
    xy = [(float(x), float(y)) for y in ys for x in xs]
    corners = np.array([[label(i, j), label(i + 1, j), label(i + 1, j + 1), label(i, j + 1)] for j in range(ny) for i in range(nx)], dtype=int)
    midside = None
    if order == 2:
        edge_node: dict[tuple[int, int], int] = {}
        mids = np.zeros_like(corners)
        for e, nodes in enumerate(corners):
            for k in range(4):
                a, b = int(nodes[k]), int(nodes[(k + 1) % 4])
                key = (min(a, b), max(a, b))
                if key not in edge_node:
                    edge_node[key] = len(xy)
                    xy.append(((xy[a][0] + xy[b][0]) / 2, (xy[a][1] + xy[b][1]) / 2))
                mids[e, k] = edge_node[key]
        midside = mids
    points = np.asarray(xy, dtype=float)

    def nodes_on(predicate) -> np.ndarray:
        return np.flatnonzero(np.array([predicate(x, y) for x, y in points]))

    tol_x, tol_y = tolerance * width, tolerance * length
    node_sets = {
        "Grip-Bottom": nodes_on(lambda x, y: abs(y) <= tol_y),
        "Grip-Top": nodes_on(lambda x, y: abs(y - length) <= tol_y),
        "Edge-Left": nodes_on(lambda x, y: abs(x) <= tol_x),
        "Edge-Right": nodes_on(lambda x, y: abs(x - width) <= tol_x),
    }
    for name, y_line in (node_rows or {}).items():
        found = nodes_on(lambda x, y, y_line=y_line: abs(y - y_line) <= tol_y)
        if found.size < nx + 1:
            raise MeshError(f"no node row lies on {name!r} at y = {y_line:g}; choose ny so that {y_line:g} / ({length:g} / ny) is an integer")
        node_sets[name] = found
    for name, (y0, y1) in (node_bands or {}).items():
        node_sets[name] = nodes_on(lambda x, y, y0=y0, y1=y1: y0 - tol_y <= y <= y1 + tol_y)
    centroid_y = points[corners].mean(axis=1)[:, 1]
    element_sets = {name: np.flatnonzero((centroid_y >= y0) & (centroid_y <= y1)) for name, (y0, y1) in (element_bands or {}).items()}
    return Mesh2D(xy=points, corners=corners, midside=midside, node_sets=node_sets, element_sets=element_sets, order=order, mesher="structured")
