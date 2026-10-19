"""The Gmsh open-hole O-grid: counts, sets, invariants, determinism, order 2, and the refusals (ADR-0030, chunk A2).

Every test here skips with a reason when Gmsh is not installed (`uv sync --extra mesh`), except the availability test.
"""

import math

import numpy as np
import pytest

from anisotropy_fea.mesher import MeshError, gmsh_available, gmsh_open_hole_plate

pytestmark = pytest.mark.skipif(gmsh_available() is None,
                                reason="Gmsh is not available: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")

W, L, D, H = 0.120, 0.360, 0.006, 0.003  # the Kirsch plate, metres


def plate(**overrides):
    args = dict(width=W, length=L, hole_diameter=D, element_size=H, circumferential=36, radial_layers=6, ring_ratio=2.0, growth=1.2)
    args.update(overrides)
    return gmsh_open_hole_plate(**args)


def test_gmsh_is_reported_available_with_its_version():
    import gmsh

    assert gmsh_available() == gmsh.__version__


def test_counts_follow_the_block_layout():
    mesh = plate()
    n_quarter, layers = 9, 6
    side = math.ceil((W / 2 - 2 * D / 2) / H)  # 18 elements across each side column
    band = math.ceil((L / 2 - 2 * D / 2) / H)  # 58 rows in each outer band
    rectangular = 2 * (2 * side * band) + 2 * (n_quarter * band) + 2 * (side * n_quarter)
    assert mesh.element_count == rectangular + 4 * n_quarter * layers == 5760
    assert mesh.mesher == "gmsh" and mesh.order == 1 and mesh.midside is None
    assert mesh.node_count == 5948
    assert mesh.node_sets["Hole"].size == 36 and mesh.node_sets["Grip-Bottom"].size == mesh.node_sets["Grip-Top"].size == 2 * side + n_quarter + 1
    assert mesh.node_sets["Edge-Left"].size == mesh.node_sets["Edge-Right"].size == 2 * band + n_quarter + 1


def test_hole_nodes_lie_on_the_circle_and_the_plate_fills_its_rectangle():
    mesh = plate()
    hole = mesh.xy[mesh.node_sets["Hole"]]
    assert np.allclose(np.hypot(hole[:, 0] - W / 2, hole[:, 1] - L / 2), D / 2, atol=1e-11)
    assert mesh.xy.min(axis=0).tolist() == [0.0, 0.0] and mesh.xy.max(axis=0).tolist() == [W, L]
    # no node inside the hole
    assert np.all(np.hypot(mesh.xy[:, 0] - W / 2, mesh.xy[:, 1] - L / 2) >= D / 2 - 1e-11)
    # the first radial layer is the thinnest: elements grow away from the hole
    centroids = mesh.centroids()
    r = np.hypot(centroids[:, 0] - W / 2, centroids[:, 1] - L / 2)
    side = mesh.nearest_element((W / 2 + D / 2, L / 2))
    assert r[side] < D / 2 + 0.2e-3 and abs(centroids[side, 1] - L / 2) < 1e-10  # odd quarter count: an element sits on the axis (coordinates rounded to 1 pm)


def test_the_same_inputs_give_the_same_mesh_twice():
    a, b = plate(), plate()
    assert np.array_equal(a.xy, b.xy) and np.array_equal(a.corners, b.corners)
    assert all(int(c[0]) == int(c.min()) for c in a.corners)  # each element starts at its lowest node: a numbering Gmsh's internals cannot change


def test_order_two_shares_midside_nodes_and_the_hole_set_includes_them():
    one, two = plate(), plate(order=2)
    assert two.order == 2 and two.element_count == one.element_count
    distinct_edges = (4 * one.element_count + _boundary_edges(one)) // 2  # interior edges are shared by two elements
    assert two.node_count == one.node_count + distinct_edges
    assert two.node_sets["Hole"].size == 72  # 36 corner nodes and 36 chord midpoints
    assert two.corner_mesh().node_count == one.node_count
    assert two.node_sets["Edge-Left"].size == 2 * one.node_sets["Edge-Left"].size - 1


def _boundary_edges(mesh) -> int:
    """Edges used by one element only (outer boundary and hole), so that interior edges = (4 ne - boundary) / 2."""
    seen: dict[tuple[int, int], int] = {}
    for nodes in mesh.corners:
        for k in range(4):
            a, b = int(nodes[k]), int(nodes[(k + 1) % 4])
            seen[(min(a, b), max(a, b))] = seen.get((min(a, b), max(a, b)), 0) + 1
    return sum(1 for count in seen.values() if count == 1)


def test_tabs_split_the_outer_bands_into_node_rows_and_element_bands():
    tab = 0.050
    mesh = gmsh_open_hole_plate(0.036, 0.300, 0.006, 0.0015, 32, 6, 2.0, 1.2, tab_length=tab,
                                node_rows={"Tab-Bottom-Line": tab, "Tab-Top-Line": 0.300 - tab},
                                element_bands={"Tab-Bottom": (0.0, tab), "Gauge": (tab, 0.300 - tab), "Tab-Top": (0.300 - tab, 0.300)},
                                node_bands={"Grip-Bottom": (0.0, tab), "Grip-Top": (0.300 - tab, 0.300)})
    assert np.allclose(mesh.xy[mesh.node_sets["Tab-Bottom-Line"], 1], tab) and np.allclose(mesh.xy[mesh.node_sets["Tab-Top-Line"], 1], 0.300 - tab)
    bands = mesh.element_sets
    assert bands["Tab-Bottom"].size == bands["Tab-Top"].size and bands["Tab-Bottom"].size + bands["Gauge"].size + bands["Tab-Top"].size == mesh.element_count
    assert mesh.node_sets["Grip-Bottom"].size > mesh.node_sets["Edge-Left"].size // 6  # the whole tab, not one row


@pytest.mark.parametrize("overrides, message", [
    ({"circumferential": 10}, "multiple of 4"),
    ({"radial_layers": 0}, "radial_layers"),
    ({"growth": 0.9}, "growth at least 1"),
    ({"ring_ratio": 25.0}, "inside the plate"),
    ({"ring_ratio": 0.5}, "enclose the hole"),
    ({"tab_length": 0.175}, "end before the inner square"),
    ({"order": 3}, "order must be 1 or 2"),
])
def test_impossible_layouts_are_refused_by_name(overrides, message):
    with pytest.raises(MeshError, match=message):
        plate(**overrides)
