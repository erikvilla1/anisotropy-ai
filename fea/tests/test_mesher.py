"""The structured mesher and the Mesh2D invariants (ADR-0030)."""

import numpy as np
import pytest

from anisotropy_fea.mesher import Mesh2D, MeshError, counts_from_size, structured_rectangle


def test_structured_rectangle_counts_coordinates_and_default_sets():
    mesh = structured_rectangle(10.0, 80.0, 2, 8)
    assert mesh.node_count == 27 and mesh.element_count == 16 and mesh.order == 1 and mesh.midside is None
    assert mesh.xy[26].tolist() == [10.0, 80.0] and mesh.corners[0].tolist() == [0, 1, 4, 3]
    assert mesh.node_sets["Grip-Bottom"].tolist() == [0, 1, 2] and mesh.node_sets["Grip-Top"].tolist() == [24, 25, 26]
    assert mesh.node_sets["Edge-Left"].tolist() == [0, 3, 6, 9, 12, 15, 18, 21, 24]
    assert mesh.connectivity().shape == (16, 4) and mesh.corner_mesh() is mesh


def test_rows_bands_and_counts():
    mesh = structured_rectangle(10.0, 80.0, 2, 8, node_rows={"Tab-Bottom-Line": 20.0}, element_bands={"Tab-Bottom": (0.0, 20.0), "Gauge": (20.0, 60.0)},
                                node_bands={"Grip-Bottom": (0.0, 20.0)})
    assert mesh.node_sets["Tab-Bottom-Line"].tolist() == [6, 7, 8]
    assert mesh.element_sets["Tab-Bottom"].tolist() == [0, 1, 2, 3] and mesh.element_sets["Gauge"].tolist() == list(range(4, 12))
    assert mesh.node_sets["Grip-Bottom"].tolist() == list(range(9))  # the band replaced the end row
    with pytest.raises(MeshError, match="no node row lies on 'Odd'"):
        structured_rectangle(10.0, 80.0, 2, 8, node_rows={"Odd": 15.0})
    assert counts_from_size(25.0, 250.0, 2.5) == (10, 100) and counts_from_size(10.0, 80.0, 3.0) == (4, 27)


def test_rows_given_explicitly_seed_the_mesh_by_segment():
    ys = [0.0, 10.0, 15.0, 20.0, 40.0, 60.0, 65.0, 70.0, 80.0]  # spacing changes at 10, 20, 60 and 70
    mesh = structured_rectangle(10.0, 80.0, 2, 8, ys=ys, node_rows={"Tab-Bottom-Line": 15.0})
    assert sorted(set(mesh.xy[:, 1].tolist())) == ys and mesh.node_sets["Tab-Bottom-Line"].tolist() == [6, 7, 8]
    with pytest.raises(MeshError, match="ny \\+ 1 = 9 node rows"):
        structured_rectangle(10.0, 80.0, 2, 8, ys=ys[:-1])
    with pytest.raises(MeshError, match="increase strictly"):
        structured_rectangle(10.0, 80.0, 2, 8, ys=[0.0, 10.0, 10.0, 20.0, 40.0, 60.0, 65.0, 70.0, 80.0])
    with pytest.raises(MeshError, match="end at the length"):
        structured_rectangle(10.0, 80.0, 2, 8, ys=ys[:-1] + [79.0])


def test_order_two_adds_one_midside_node_per_edge_in_the_s8r_order():
    mesh = structured_rectangle(10.0, 20.0, 2, 2, order=2)
    assert mesh.node_count == 9 + 12 and mesh.midside.shape == (4, 4)
    conn = mesh.connectivity()
    assert conn.shape == (4, 8)
    for e in range(4):
        for k in range(4):
            a, b, m = conn[e, k], conn[e, (k + 1) % 4], conn[e, 4 + k]
            assert mesh.xy[m] == pytest.approx((mesh.xy[a] + mesh.xy[b]) / 2)
    assert len(np.unique(mesh.midside)) == 12  # shared edges share their midside node
    assert mesh.node_sets["Grip-Bottom"].size == 5  # three corners and two midsides on the bottom edge
    corner = mesh.corner_mesh()
    assert corner.order == 1 and corner.node_count == 9 and corner.node_sets["Grip-Bottom"].tolist() == [0, 1, 2]
    assert corner.xy[corner.corners[3]].tolist() == mesh.xy[mesh.corners[3]].tolist()


def test_invariants_refuse_bad_meshes():
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    with pytest.raises(MeshError, match="clockwise or the element is degenerate"):
        Mesh2D(xy=xy, corners=np.array([[0, 3, 2, 1]]), midside=None)
    with pytest.raises(MeshError, match="repeated corner node"):
        Mesh2D(xy=xy, corners=np.array([[0, 1, 1, 3]]), midside=None)
    with pytest.raises(MeshError, match="outside the mesh"):
        Mesh2D(xy=xy, corners=np.array([[0, 1, 2, 7]]), midside=None)
    with pytest.raises(MeshError, match="share the same coordinates"):
        Mesh2D(xy=np.vstack([xy, [[1.0, 1.0]]]), corners=np.array([[0, 1, 2, 3]]), midside=None)
    with pytest.raises(MeshError, match="not at the midpoint of edge 1"):
        Mesh2D(xy=np.vstack([xy, [[0.5, 0.2], [1.0, 0.5], [0.5, 1.0], [0.0, 0.5]]]), corners=np.array([[0, 1, 2, 3]]), midside=np.array([[4, 5, 6, 7]]), order=2)
    with pytest.raises(MeshError, match="order 2 needs midside nodes"):
        Mesh2D(xy=xy, corners=np.array([[0, 1, 2, 3]]), midside=None, order=2)
    with pytest.raises(MeshError, match="node set 'x' names a node outside"):
        Mesh2D(xy=xy, corners=np.array([[0, 1, 2, 3]]), midside=None, node_sets={"x": np.array([9])})


def test_nearest_node_and_element():
    mesh = structured_rectangle(10.0, 80.0, 2, 8)
    assert mesh.nearest_node((5.1, 39.0)) == 13 and mesh.nearest_element((2.0, 5.0)) == 0
