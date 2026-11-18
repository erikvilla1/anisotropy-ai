"""The model built from a spec: boundary tables, grips, loads, probes, headers (ADR-0030)."""


import numpy as np
import pytest

from anisotropy_fea.femodel import BoundaryDefinition, build_model, consistent_edge_loads, mesh_for_spec
from anisotropy_fea.mesher import structured_rectangle
from anisotropy_fea.spec import SpecError, load_spec, parse_spec, to_si
from anisotropy_fea import paths  # where the files live (ADR-0036)

NODAL = (paths.spec_path("unnotched-im7-8552-nodal")).read_text(encoding="utf-8")


def spec_from(text: str):
    return to_si(parse_spec(text))


def test_nodal_grips_on_the_tabs():
    model = build_model(load_spec(paths.spec_path("unnotched-im7-8552-nodal")))
    mesh = model.mesh
    assert mesh.element_count == 1250 and mesh.node_count == 1386
    assert mesh.node_sets["Grip-Bottom"].size == 11 * 29 and mesh.node_sets["Grip-Top"].size == 11 * 29  # 56 mm of 2 mm rows plus the end row
    assert mesh.element_sets["Tab-Bottom"].size == 280 and mesh.element_sets["Gauge"].size == 690 and mesh.element_sets["Tab-Top"].size == 280
    assert model.boundaries == (BoundaryDefinition("Grip-Bottom", 1, 6), BoundaryDefinition("Grip-Top", 1, 1), BoundaryDefinition("Grip-Top", 3, 6),
                                BoundaryDefinition("Grip-Top", 2, 2, pytest.approx(1e-3)))
    assert model.loads == () and model.reference_points == () and model.couplings == ()
    assert [p.angle_deg for p in model.section.plies] == [45, 0, -45, 90, 90, -45, 0, 45] and len(model.section.listed) == 4
    assert [p.fibre_deg for p in model.section.plies] == [-45, 90, 45, 0, 0, 45, 90, -45]  # the stated angles plus 90, from x (ADR-0065)
    assert model.orientation_angles == (-45.0, 0.0, 45.0, 90.0) and model.orientation_fibres == (45.0, 90.0, -45.0, 0.0)
    assert any("from the length axis (fibres from x: [-45.0, 90.0, 45.0, 0.0, 0.0, 45.0, 90.0, -45.0])" in line for line in model.heading)
    assert model.probe_nodes["centre"] == mesh.nearest_node((0.0125, 0.125)) and "Probe-centre" in model.node_sets and "Probe-near_grip" in model.element_sets
    assert any("rights class open-publisher" in line for line in model.heading) and any("page 30" in line for line in model.heading)


def test_coupling_grips_add_reference_points_and_couplings():
    model = build_model(load_spec(paths.spec_path("unnotched-im7-8552-coupling")))
    assert [p.set_name for p in model.reference_points] == ["RF-Bottom", "RF-Top"]
    assert model.reference_points[1].xy == pytest.approx((0.0125, 0.250))
    assert [(c.reference_set, c.node_set) for c in model.couplings] == [("RF-Bottom", "Grip-Bottom"), ("RF-Top", "Grip-Top")]
    assert model.boundaries[0] == BoundaryDefinition("RF-Bottom", 1, 6) and model.boundaries[-1].target == "RF-Top"


def test_line_grips_use_the_end_rows_only():
    model = build_model(spec_from(NODAL.replace('region = "tabs"', 'region = "line"')))
    assert model.mesh.node_sets["Grip-Bottom"].size == 11 and model.mesh.node_sets["Grip-Top"].size == 11


def test_force_control_with_nodal_grips_gives_consistent_edge_loads():
    text = NODAL.replace('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0').replace('region = "tabs"', 'region = "line"')
    model = build_model(spec_from(text))
    assert model.boundaries == (BoundaryDefinition("Grip-Bottom", 1, 6), BoundaryDefinition("Grip-Top", 1, 1), BoundaryDefinition("Grip-Top", 3, 6))
    assert len(model.loads) == 11 and sum(load.value for load in model.loads) == pytest.approx(5000.0)
    values = [load.value for load in model.loads]
    assert values[0] == pytest.approx(values[1] / 2) and values[-1] == pytest.approx(values[1] / 2)  # corners carry half shares
    assert model.loads[0].target == "Coupon-1.1376"
    coupling = build_model(spec_from(text.replace('kind = "nodal"', 'kind = "coupling"')))
    assert coupling.loads[0].target == "RF-Top" and coupling.loads[0].value == pytest.approx(5000.0)


def test_a_rigid_grip_under_a_force_is_held_below_and_tied_to_one_reference_point_above():
    """ADR-0030 amendment 7: the CalculiX twin of a coupon under a force. The bottom grip is held node by node, so its reaction can be
    printed; the top grip moves as one, as a coupled grip does, and our kernel gives it the coupled model's solution."""
    from anisotropy_fea.abaqus_reader import parse_deck, to_si as deck_to_si
    from anisotropy_fea.kernel import solve_deck
    from anisotropy_fea.write_abaqus import write_abaqus

    text = NODAL.replace('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0\nrigid_grip = true')
    model = build_model(spec_from(text))
    assert [(p.set_name, p.xy) for p in model.reference_points] == [("RF-Top", pytest.approx((0.0125, 0.250)))]
    assert [(c.reference_set, c.node_set) for c in model.couplings] == [("RF-Top", "Grip-Top")]
    assert model.boundaries == (BoundaryDefinition("Grip-Bottom", 1, 6), BoundaryDefinition("RF-Top", 1, 1), BoundaryDefinition("RF-Top", 3, 6))
    assert [(load.target, load.dof, load.value) for load in model.loads] == [("RF-Top", 2, 5000.0)]
    assert model.support_sets == ("RF-Top", "Grip-Bottom") and model.reaction_set == "Grip-Bottom"
    assert "the top grip moves as one, its reference point carrying the force" in "\n".join(model.heading)
    coupled = build_model(spec_from(text.replace('kind = "nodal"', 'kind = "coupling"').replace("\nrigid_grip = true", "")))
    assert coupled.support_sets == ("RF-Top", "RF-Bottom") and coupled.reaction_set == "RF-Bottom"
    solved = [solve_deck(deck_to_si(parse_deck(write_abaqus(m, "mm-MPa")), "mm-MPa")) for m in (model, coupled)]
    count = model.mesh.node_count  # the coupon's own nodes come first in both
    assert np.allclose(solved[0].displacement[:count], solved[1].displacement[:count], rtol=0, atol=1e-12)
    moved = build_model(spec_from(NODAL))
    assert moved.support_sets == ("Grip-Top", "Grip-Bottom") and moved.reaction_set == "Grip-Top" and not moved.couplings
    for wrong in (NODAL.replace("value = 1.0", "value = 1.0\nrigid_grip = true"),  # a displacement moves every grip node alike already
                  text.replace('kind = "nodal"', 'kind = "coupling"')):  # a coupled grip is rigid already
        with pytest.raises(SpecError, match="rigid_grip belongs to force control on nodal grips"):
            spec_from(wrong)


def test_consistent_loads_for_eight_node_edges():
    mesh = structured_rectangle(10.0, 20.0, 2, 2, order=2)
    loads = consistent_edge_loads(mesh, "Grip-Top", 2, 300.0, instance="I")
    assert len(loads) == 5 and sum(load.value for load in loads) == pytest.approx(300.0)
    by_node = {load.target: load.value for load in loads}
    corner_end, middle_corner, midside = by_node["I.7"], by_node["I.8"], max(by_node.values())
    assert midside == pytest.approx(100.0) and corner_end == pytest.approx(25.0) and middle_corner == pytest.approx(50.0)


def test_a_bending_coupon_rests_on_its_supports_pinned_in_its_plane_and_is_pushed_by_the_nose():
    """ADR-0053: w held along both support rows, the centre node of each row pins the in-plane motion, the nose row moves along z."""
    model = build_model(load_spec(paths.spec_path("three-point-im7-8552")))
    assert model.bending and model.support_sets == ("Support-Left", "Support-Right", "Nose") and model.nose_sets == ("Nose",)
    sets = model.node_sets
    assert sets["Support-Left"].size == sets["Support-Right"].size == sets["Nose"].size == 7  # nx = 6: seven nodes across
    assert np.allclose(model.mesh.xy[sets["Support-Left"]][:, 1], 0.006) and np.allclose(model.mesh.xy[sets["Nose"]][:, 1], 0.030)
    assert sets["Pin-Left"].size == 1 and model.mesh.xy[sets["Pin-Left"][0]].tolist() == pytest.approx([0.0065, 0.006])
    assert sets["Pin-Right"].size == 1 and model.mesh.xy[sets["Pin-Right"][0]].tolist() == pytest.approx([0.0065, 0.054])
    held = {(b.target, b.dof_first, b.dof_last, b.value) for b in model.boundaries}
    assert held == {("Support-Left", 3, 3, 0.0), ("Support-Right", 3, 3, 0.0), ("Pin-Left", 1, 2, 0.0), ("Pin-Right", 1, 1, 0.0), ("Nose", 3, 3, -1e-3)}
    assert not model.loads and not model.couplings and not model.reference_points
    assert any("supports at y = 0.006 and 0.054 m" in line and "moved -0.001 m along z" in line for line in model.heading)
    four = NODAL.replace('kind = "unnotched_tension"', 'kind = "four_point_bending"').replace("tab_length = 56.0", "span = 230.0\noverhang = 10.0\nload_span = 110.0")
    four = four.replace("[grips]\nkind = \"nodal\"\nregion = \"tabs\"     # the whole tab is gripped, as in the team's decks\n", "")
    four = four.replace("ny = 125", "ny = 250").replace("IM7-UNT-L1, unnotched tension", "IM7-4PB-L1, four-point bending").replace('designation = "IM7-UNT-L1"', 'designation = "IM7-4PB-L1"')
    model = build_model(spec_from(four))
    assert model.nose_sets == ("Nose-1", "Nose-2") and model.support_sets == ("Support-Left", "Support-Right", "Nose-1", "Nose-2")
    assert np.allclose(model.mesh.xy[model.node_sets["Nose-1"]][:, 1], 0.070) and np.allclose(model.mesh.xy[model.node_sets["Nose-2"]][:, 1], 0.180)


def test_unbuildable_specs_are_refused():
    gmsh = NODAL.replace('mesher = "structured"', 'mesher = "gmsh"')
    with pytest.raises(SpecError, match="goes with open_hole_tension"):
        mesh_for_spec(spec_from(gmsh))
    with pytest.raises(SpecError, match="needs the spec in SI"):
        build_model(parse_spec(NODAL))


def test_compression_spec_builds_a_fine_tabbed_mesh():
    model = build_model(load_spec(paths.spec_path("compression-im7-8552")))
    assert model.mesh.element_count == 3360 and model.boundaries[-1].value == pytest.approx(-0.1e-3)
    assert model.mesh.element_sets["Gauge"].size == 26 * 12
    assert np.all(model.mesh.xy[model.mesh.node_sets["Grip-Top"]][:, 1] >= 0.0765 - 1e-12)
