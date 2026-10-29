"""Meshes we generate ourselves (ADR-0030): a structured rectangle, and an open-hole plate meshed by Gmsh as a transfinite O-grid.

`Mesh2D` is the solver-neutral mesh: node coordinates in metres, four corner nodes per element listed
counterclockwise, optional midside nodes for 8-node elements, and named node and element sets. Its
invariants are checked on construction, so a deck written from it is a valid S4R or S8R mesh by construction.

Both meshers share the same code for midside nodes and for the named sets, which are found from coordinates
(end rows, side edges, tab lines, tab bands, the hole circle) rather than from mesher bookkeeping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DUPLICATE_TOLERANCE = 1e-9  # relative to the characteristic size
MIDSIDE_TOLERANCE = 1e-9
COORDINATE_DECIMALS = 12  # Gmsh coordinates are rounded to 1 pm so a generated deck's text is the same on every platform


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


# --- shared by both meshers ------------------------------------------------------------------------


def with_midside_nodes(xy: list[tuple[float, float]], corners: np.ndarray) -> tuple[list[tuple[float, float]], np.ndarray]:
    """One new node at the midpoint of every element edge, shared between neighbours; appended after the corner nodes."""
    xy = list(xy)
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
    return xy, mids


def sets_by_coordinates(points: np.ndarray, corners: np.ndarray, width: float, length: float,
                        node_rows: dict[str, float] | None, element_bands: dict[str, tuple[float, float]] | None,
                        node_bands: dict[str, tuple[float, float]] | None, tolerance: float,
                        boxes: dict[str, tuple[float, float, float, float]] | None = None) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """The named sets of a plate [0, width] x [0, length] with loading axis y, found from coordinates.

    Node sets: Grip-Bottom (y = 0), Grip-Top (y = length), Edge-Left (x = 0), Edge-Right (x = width), one
    per entry of `node_rows` (name -> y) which must coincide with a node row, and one per entry of `node_bands` (name -> (y0, y1))
    holding every node in the band; a band set replaces a default set of the same name. Midside nodes on a line belong
    to its set. Element sets: one per entry of `element_bands` (name -> (y0, y1)) holding the elements whose centroid lies in the band.
    A box (name -> (x0, x1, y0, y1), ADR-0054) gives both a node set of the nodes inside it and an element set of the elements whose
    centroid lies inside it.
    """

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
        if found.size == 0:
            raise MeshError(f"no node row lies on {name!r} at y = {y_line:g}; choose the mesh so that a node row falls on {y_line:g}")
        node_sets[name] = found
    for name, (y0, y1) in (node_bands or {}).items():
        node_sets[name] = nodes_on(lambda x, y, y0=y0, y1=y1: y0 - tol_y <= y <= y1 + tol_y)
    centroid_y = points[corners].mean(axis=1)[:, 1]
    element_sets = {name: np.flatnonzero((centroid_y >= y0) & (centroid_y <= y1)) for name, (y0, y1) in (element_bands or {}).items()}
    centroids = points[corners].mean(axis=1)
    for name, (x0, x1, y0, y1) in (boxes or {}).items():
        node_sets[name] = nodes_on(lambda x, y, x0=x0, x1=x1, y0=y0, y1=y1: x0 - tol_x <= x <= x1 + tol_x and y0 - tol_y <= y <= y1 + tol_y)
        element_sets[name] = np.flatnonzero((centroids[:, 0] >= x0) & (centroids[:, 0] <= x1) & (centroids[:, 1] >= y0) & (centroids[:, 1] <= y1))
    return node_sets, element_sets


# --- structured rectangle --------------------------------------------------------------------------


def structured_rectangle(width: float, length: float, nx: int, ny: int, order: int = 1,
                         node_rows: dict[str, float] | None = None, element_bands: dict[str, tuple[float, float]] | None = None,
                         node_bands: dict[str, tuple[float, float]] | None = None, tolerance: float = 1e-9,
                         ys: list[float] | None = None, boxes: dict[str, tuple[float, float, float, float]] | None = None) -> Mesh2D:
    """A rectangle [0, width] x [0, length] with nx by ny elements, loading axis y; sets as in `sets_by_coordinates`.

    The node rows are evenly spaced unless `ys` gives all ny + 1 of them (bottom first, from 0 to the length, increasing):
    a mesh seeded by segment, as `spec.row_coordinates` computes from partition lines and seed counts.
    """
    if nx < 1 or ny < 1:
        raise MeshError("nx and ny must be at least 1")
    if order not in (1, 2):
        raise MeshError("order must be 1 or 2")
    label = lambda i, j: i + (nx + 1) * j  # noqa: E731
    xs = np.linspace(0.0, width, nx + 1)
    if ys is None:
        ys = np.linspace(0.0, length, ny + 1)
    else:
        ys = np.asarray(ys, dtype=float)
        if ys.shape != (ny + 1,):
            raise MeshError(f"ys must give ny + 1 = {ny + 1} node rows; it gives {ys.size}")
        if abs(ys[0]) > tolerance * length or abs(ys[-1] - length) > tolerance * length or np.any(np.diff(ys) <= 0):
            raise MeshError("ys must start at 0, end at the length and increase strictly")
        ys[0], ys[-1] = 0.0, length
    xy = [(float(x), float(y)) for y in ys for x in xs]
    corners = np.array([[label(i, j), label(i + 1, j), label(i + 1, j + 1), label(i, j + 1)] for j in range(ny) for i in range(nx)], dtype=int)
    midside = None
    if order == 2:
        xy, midside = with_midside_nodes(xy, corners)
    points = np.asarray(xy, dtype=float)
    for name, y_line in (node_rows or {}).items():
        if not any(abs(float(y) - y_line) <= tolerance * length for y in ys):
            raise MeshError(f"no node row lies on {name!r} at y = {y_line:g}; choose ny so that {y_line:g} / ({length:g} / ny) is an integer")
    node_sets, element_sets = sets_by_coordinates(points, corners, width, length, node_rows, element_bands, node_bands, tolerance, boxes)
    return Mesh2D(xy=points, corners=corners, midside=midside, node_sets=node_sets, element_sets=element_sets, order=order, mesher="structured")


# --- Gmsh: open-hole plate as a transfinite O-grid -------------------------------------------------


def gmsh_available() -> str | None:
    """The installed Gmsh version, or None. Gmsh is the optional extra `mesh`: from fea/, `uv sync --extra mesh`."""
    try:
        import gmsh
    except (ImportError, OSError):  # OSError: the wheel's shared library needs libGLU on Linux (apt install libglu1-mesa)
        return None
    return str(gmsh.__version__)


def gmsh_open_hole_plate(width: float, length: float, hole_diameter: float, element_size: float, circumferential: int, radial_layers: int,
                         ring_ratio: float, growth: float, order: int = 1, tab_length: float = 0.0,
                         node_rows: dict[str, float] | None = None, element_bands: dict[str, tuple[float, float]] | None = None,
                         node_bands: dict[str, tuple[float, float]] | None = None, tolerance: float = 1e-9,
                         boxes: dict[str, tuple[float, float, float, float]] | None = None) -> Mesh2D:
    """A plate [0, width] x [0, length] with a central circular hole, meshed by Gmsh as a transfinite butterfly O-grid.

    Blocks: four annular blocks between the hole and an inner square of half-side `ring_ratio` times the hole radius
    (`circumferential` / 4 elements along each quarter arc, `radial_layers` layers growing outwards by `growth`), and
    the rectangular blocks that fill the plate around that square, split at the tab lines when `tab_length` > 0 so the
    tab lines are node rows. Every block is transfinite and recombined, so the mesh is quadrilaterals only. Gmsh
    makes the corner nodes; midside nodes (order 2) and the named sets come from the same code as the structured
    mesher, and the extra set `Hole` holds the nodes on the circle (with the midside nodes of its edges at order 2).
    Nodes are ordered by (y, x) and elements by centroid, so the result does not depend on Gmsh's internal numbering.
    """
    try:
        import gmsh
    except (ImportError, OSError) as exc:
        raise MeshError("Gmsh is not available; from fea/ run `uv sync --extra mesh` (the optional extra declared in pyproject.toml); "
                        f"on Linux the wheel also needs the system library libGLU (apt install libglu1-mesa). Python said: {exc}") from None
    if order not in (1, 2):
        raise MeshError("order must be 1 or 2")
    if circumferential < 8 or circumferential % 4:
        raise MeshError("circumferential must be a multiple of 4, at least 8")
    if radial_layers < 1 or growth < 1.0:
        raise MeshError("radial_layers must be at least 1 and growth at least 1")
    if element_size <= 0:
        raise MeshError("element_size must be positive")
    radius = hole_diameter / 2
    half = ring_ratio * radius
    cx, cy = width / 2, length / 2
    if not radius < half < min(cx, cy):
        raise MeshError(f"the inner square (half-side {half:g}) must enclose the hole (radius {radius:g}) and lie inside the plate ({cx:g} by {cy:g} half-sizes)")
    if tab_length < 0 or (tab_length and tab_length >= cy - half):
        raise MeshError(f"tab_length {tab_length:g} must be zero or end before the inner square at y = {cy - half:g}")
    n_quarter = circumferential // 4
    xs = [0.0, cx - half, cx + half, width]
    ys = [0.0] + ([tab_length] if tab_length else []) + [cy - half, cy + half] + ([length - tab_length] if tab_length else []) + [length]
    jc = ys.index(cy - half)  # the band holding the inner square
    count = lambda span: max(1, math.ceil(span / element_size - 1e-9))  # noqa: E731
    col_nodes = [count(xs[1] - xs[0]) + 1, n_quarter + 1, count(xs[3] - xs[2]) + 1]
    band_nodes = [n_quarter + 1 if j == jc else count(ys[j + 1] - ys[j]) + 1 for j in range(len(ys) - 1)]

    owned = not gmsh.isInitialized()
    if owned:
        gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("open-hole-plate")
        geo = gmsh.model.geo
        P = [[geo.addPoint(x, y, 0.0) for y in ys] for x in xs]
        H = [[geo.addLine(P[i][j], P[i + 1][j]) for j in range(len(ys))] for i in range(3)]
        V = [[geo.addLine(P[i][j], P[i][j + 1]) for j in range(len(ys) - 1)] for i in range(4)]
        for i in range(3):
            for j in range(len(ys)):
                geo.mesh.setTransfiniteCurve(H[i][j], col_nodes[i])
        for i in range(4):
            for j in range(len(ys) - 1):
                geo.mesh.setTransfiniteCurve(V[i][j], band_nodes[j])
        surfaces = []
        for i in range(3):
            for j in range(len(ys) - 1):
                if i == 1 and j == jc:
                    continue
                surfaces.append(geo.addPlaneSurface([geo.addCurveLoop([H[i][j], V[i + 1][j], -H[i][j + 1], -V[i][j]])]))
        centre = geo.addPoint(cx, cy, 0.0)
        C = [geo.addPoint(cx + radius * math.cos(a), cy + radius * math.sin(a), 0.0) for a in (math.pi / 4 + k * math.pi / 2 for k in range(4))]
        square = [P[2][jc + 1], P[1][jc + 1], P[1][jc], P[2][jc]]  # NE, NW, SW, SE, matching the circle points at 45, 135, 225, 315 degrees
        A = [geo.addCircleArc(C[k], centre, C[(k + 1) % 4]) for k in range(4)]
        D = [geo.addLine(C[k], square[k]) for k in range(4)]  # from the hole outwards, so the progression grows away from the hole
        sides = [H[1][jc + 1], V[1][jc], -H[1][jc], -V[2][jc]]  # square side from corner k+1 to corner k
        for arc in A:
            geo.mesh.setTransfiniteCurve(arc, n_quarter + 1)
        for diagonal in D:
            geo.mesh.setTransfiniteCurve(diagonal, radial_layers + 1, "Progression", growth)
        for k in range(4):
            surfaces.append(geo.addPlaneSurface([geo.addCurveLoop([A[k], D[(k + 1) % 4], sides[k], -D[k]])]))
        for surface in surfaces:
            geo.mesh.setTransfiniteSurface(surface)
            geo.mesh.setRecombine(2, surface)
        geo.synchronize()
        gmsh.model.mesh.generate(2)
        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        types, _, element_nodes = gmsh.model.mesh.getElements(2)
    finally:
        if owned:
            gmsh.finalize()
        else:
            gmsh.model.remove()

    if [int(t) for t in types] != [3]:
        raise MeshError(f"Gmsh produced element types {[int(t) for t in types]}; the transfinite blocks must give 4-node quadrilaterals (type 3) only")
    quads = np.asarray(element_nodes[0], dtype=np.int64).reshape(-1, 4)
    node_tags = np.asarray(node_tags, dtype=np.int64)
    coords = np.asarray(coords, dtype=float).reshape(-1, 3)[:, :2]
    used = np.unique(quads)  # the hole's centre point is meshed as a node but belongs to no element
    position = np.searchsorted(node_tags[np.argsort(node_tags)], used)
    xy = np.round(coords[np.argsort(node_tags)][position], COORDINATE_DECIMALS)
    corners = np.searchsorted(used, quads)
    # counterclockwise corners, whatever the orientation Gmsh gave each block
    p = xy[corners]
    area2 = np.zeros(len(corners))
    for i in range(4):
        area2 += p[:, i, 0] * p[:, (i + 1) % 4, 1] - p[:, (i + 1) % 4, 0] * p[:, i, 1]
    clockwise = area2 < 0
    corners[clockwise] = corners[clockwise][:, [0, 3, 2, 1]]
    # a numbering that does not depend on Gmsh: nodes by (y, x), elements by centroid (y, x), each element starting at its lowest node
    node_order = np.lexsort((xy[:, 0], xy[:, 1]))
    new_index = np.empty_like(node_order)
    new_index[node_order] = np.arange(node_order.size)
    xy = xy[node_order]
    corners = new_index[corners]
    corners = np.array([np.roll(c, -int(np.argmin(c))) for c in corners], dtype=int)
    centroid = xy[corners].mean(axis=1)
    corners = corners[np.lexsort((centroid[:, 0], centroid[:, 1]))]

    points_list = [(float(x), float(y)) for x, y in xy]
    midside = None
    if order == 2:
        points_list, midside = with_midside_nodes(points_list, corners)
    points = np.asarray(points_list, dtype=float)
    node_sets, element_sets = sets_by_coordinates(points, corners, width, length, node_rows, element_bands, node_bands, tolerance, boxes)
    size = max(width, length)
    on_circle = np.abs(np.hypot(points[:, 0] - cx, points[:, 1] - cy) - radius) <= tolerance * size
    hole = set(np.flatnonzero(on_circle).tolist())
    if midside is not None:
        for nodes, mids in zip(corners, midside):
            for k in range(4):
                if int(nodes[k]) in hole and int(nodes[(k + 1) % 4]) in hole:
                    hole.add(int(mids[k]))
    node_sets["Hole"] = np.array(sorted(hole), dtype=int)
    return Mesh2D(xy=points, corners=corners, midside=midside, node_sets=node_sets, element_sets=element_sets, order=order, mesher="gmsh")
