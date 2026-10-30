"""The plate kind (ADR-0054): supports and loads over named regions. A plate stated as the unnotched coupon reproduces it exactly; the
pressure plate reproduces the Navier case; the spec refuses what it must by name; the values file carries the lists; the checklist judges
the rigid-body motions."""

import json
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.cases import load_case
from anisotropy_fea.checks import rigid_modes_left, setup_checklist
from anisotropy_fea.femodel import build_model, consistent_area_loads
from anisotropy_fea.intake import FORM_VERSION, IntakeError, check_form, read_values, spec_from_values, values_of_spec
from anisotropy_fea.intake import designation_for
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesher import structured_rectangle
from anisotropy_fea.results import ShellSolution
from anisotropy_fea.spec import SpecError, load_spec, parse_spec, plate_regions, to_si
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea.write_calculix import write_calculix

UNT = (paths.CHECKS / "unnotched-im7-8552" / "unnotched-im7-8552-nodal.toml").read_text(encoding="utf-8")
PRESSURE = paths.CHECKS / "plate-pressure-isotropic" / "plate-pressure-isotropic.toml"
PLATE_VALUES = paths.ROOT / "tests" / "fixtures" / "studio-plate" / "values.json"


def unt_as_plate() -> str:
    text = UNT.replace('kind = "unnotched_tension"', 'kind = "plate"').replace('designation = "IM7-UNT-L1"', 'designation = "IM7-PLT-L1"')
    text = text.replace("IM7-UNT-L1, unnotched tension:", "IM7-PLT-L1, plate:")
    text = text.replace('[grips]\nkind = "nodal"\nregion = "tabs"     # the whole tab is gripped, as in the team\'s decks\n', "")
    return text.replace('[loading]\ncontrol = "displacement"\nvalue = 1.0\n',
                        '[[supports]]\nregion = "Tab-Bottom"\ndofs = [1, 2, 3, 4, 5, 6]\n[[supports]]\nregion = "Tab-Top"\ndofs = [1, 3, 4, 5, 6]\n'
                        '[[supports]]\nregion = "Tab-Top"\ndofs = [2]\nvalue = 1.0\n')


def test_the_unnotched_coupon_stated_as_a_plate_reproduces_it_exactly(tmp_path):
    spec = to_si(parse_spec(unt_as_plate(), "plate-unt.toml"))
    model = build_model(spec)
    assert model.plate and not model.bending and model.support_sets == ("Tab-Bottom", "Tab-Top") and not model.loads and not model.pressures
    assert {b.target for b in model.boundaries} == {"Tab-Bottom", "Tab-Top"} and any(b.value == pytest.approx(1e-3) and b.dof_first == 2 for b in model.boundaries)
    deck_path = tmp_path / "plate.inp"
    deck_path.write_text(write_abaqus(model), encoding="utf-8")
    ours = solve_deck(read_deck(deck_path, spec.units))
    reference_deck = read_deck(paths.CHECKS / "unnotched-im7-8552" / "decks" / "unnotched-im7-8552-nodal-abaqus.inp", "mm-MPa")
    reference = solve_membrane(reference_deck)
    assert not isinstance(ours, ShellSolution)  # nothing acts out of the plane: the membrane kernel, as for the coupon
    assert ours.displacement == pytest.approx(reference.displacement, rel=1e-12, abs=1e-15)
    assert ours.section_force == pytest.approx(reference.section_force, rel=1e-12, abs=1e-6)
    assert ours.reaction_of(read_deck(deck_path, spec.units).nsets["Tab-Top"]) == pytest.approx(reference.reaction_of(reference_deck.nsets["Grip-Top"]), rel=1e-12)
    # the CalculiX twin writes without couplings to replace
    twin = build_model(spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})}))
    assert "*NODE PRINT, NSET=Tab-Top, TOTALS=YES" in write_calculix(twin)


def test_the_pressure_plate_reproduces_the_navier_case_and_flips_the_sign_for_calculix(tmp_path):
    spec = load_spec(PRESSURE)
    model = build_model(spec)
    assert model.plate and model.bending and model.pressures[0].elset == "Face" and model.pressures[0].value == pytest.approx(-0.01e6)
    assert set(model.node_sets) >= {"Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Corner-Origin", "Corner-X", "Face"}
    assert model.node_sets["Corner-Origin"].size == 1 and model.element_sets["Corner-Origin"].size == 0  # a corner box holds one node and no centroid
    assert model.element_sets["Face"].size == 256 and model.node_sets["Face"].size == 289
    deck_text = write_abaqus(model)
    assert "*Dload\nFace, P, -0.01" in deck_text
    deck_path = tmp_path / "plate.inp"
    deck_path.write_text(deck_text, encoding="utf-8")
    deck = read_deck(deck_path, spec.units)
    solution = solve_deck(deck)
    assert isinstance(solution, ShellSolution)
    case = load_case(paths.CASES / "plate-ss-isotropic-uniform-pressure-navier.toml")
    centre = model.probe_nodes["centre"]
    assert solution.displacement[centre, 2] * 1e3 == pytest.approx(0.633254568, rel=1e-6)  # the case's own kernel value on this mesh
    assert solution.displacement[centre, 2] * 1e3 == pytest.approx(case["expected"]["w"]["Plate-1.145"][0], rel=case["expected"]["tolerance"])
    assert solution.total_reaction[2] == pytest.approx(-100.0, rel=1e-10)  # the 100 N of pressure toward +z are carried by the supports
    ccx = write_calculix(build_model(spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})))
    assert "*DLOAD\nFace, P, 0.01" in ccx and "sign is flipped" in ccx  # the CalculiX pressure pushes along the normal (the conventions file)


def test_consistent_area_loads_sum_to_the_total_and_follow_the_area():
    mesh = structured_rectangle(10.0, 20.0, 2, 4)
    loads = consistent_area_loads(mesh, np.arange(mesh.element_count), 3, 80.0, instance="I")
    assert sum(load.value for load in loads) == pytest.approx(80.0)
    by_node = {load.target: load.value for load in loads}
    assert by_node["I.1"] == pytest.approx(80.0 / 32) and by_node["I.8"] == pytest.approx(80.0 / 8)  # a corner node: one quarter; an interior node: four quarters
    eight = structured_rectangle(10.0, 20.0, 2, 4, order=2)
    loads8 = consistent_area_loads(eight, np.arange(eight.element_count), 3, 80.0, instance="I")
    assert sum(load.value for load in loads8) == pytest.approx(80.0) and any(load.value < 0 for load in loads8)  # serendipity corners pull


@pytest.mark.parametrize("old, new, message", [
    ('region = "Edge-Left"\ndofs = [3, 4]', 'region = "Edge-Nowhere"\ndofs = [3, 4]', "region 'Edge-Nowhere' is not one of"),
    ('region = "Face"\npressure = -0.01', 'region = "Edge-Left"\npressure = -0.01', "a pressure acts on an area region"),
    ('region = "Face"\npressure = -0.01', 'region = "Face"\npressure = -0.01\ndof = 3\ntotal = 5.0', "not both and not neither"),
    ('dofs = [1, 2]', 'dofs = [1, 2]\nvalue = 0.5', "a nonzero value needs exactly one dof"),
    ('name = "Corner-X"', 'name = "Edge-Top"', "not a name a region may take"),
    ("[[loads]]\n", "[loading]\ncontrol = \"force\"\nvalue = 1.0\n[[loads]]\n", "takes no \\[grips\\] or \\[loading\\] table"),
    ('x1 = 0.1\ny0 = 0.0\ny1 = 0.1\n[[regions]]', 'x1 = 0.1\ny0 = 0.0\ny1 = 0.1\n[[regions]]\nname = "Corner-Origin"\nx0 = 1.0\nx1 = 2.0\ny0 = 1.0\ny1 = 2.0\n[[regions]]', "every name must be unique"),
])
def test_a_plate_is_refused_by_name(old, new, message):
    text = PRESSURE.read_text(encoding="utf-8")
    assert old in text
    with pytest.raises(SpecError, match=message):
        parse_spec(text.replace(old, new, 1))


def test_a_coupon_kind_refuses_the_plate_lists_and_a_plate_names_its_regions():
    with pytest.raises(SpecError, match="belong to the plate kind only"):
        parse_spec(UNT.replace("[probes]", '[[supports]]\nregion = "Edge-Left"\ndofs = [1]\n[probes]', 1))
    spec = parse_spec(PRESSURE.read_text(encoding="utf-8"))
    assert plate_regions(spec) == ("Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Face", "Corner-Origin", "Corner-X")
    tabs = parse_spec(unt_as_plate())
    assert "Tab-Bottom" in plate_regions(tabs) and "Hole" not in plate_regions(tabs)


def test_the_checklist_judges_the_rigid_body_motions_of_a_plate(tmp_path):
    form = read_values(PLATE_VALUES)
    checklist, model, _ = setup_checklist(form, tmp_path / "root", ccx=lambda: None, tectonic=lambda: None)
    items = {item.id: item for item in checklist.items}
    assert items["constraints"].state == "pass" and "no rigid-body motion is left" in items["constraints"].message
    assert items["load"].state == "pass" and "pressure of -0.01 MPa on Face" in items["load"].message
    assert items["laminate"].state == "pass" and "flat shell kernel" in items["laminate"].message
    assert rigid_modes_left(model) == ("", "")
    # drop the corner pins: the plate can slide and turn in its plane
    data = json.loads(PLATE_VALUES.read_text(encoding="utf-8"))
    data["supports"] = [s for s in data["supports"] if not s["region"].startswith("Corner")]
    loose = tmp_path / "loose.json"
    loose.write_text(json.dumps(data), encoding="utf-8")
    checklist, _, _ = setup_checklist(read_values(loose), tmp_path / "root", ccx=lambda: None, tectonic=lambda: None)
    items = {item.id: item for item in checklist.items}
    assert items["constraints"].state == "fail" and "translate along x, translate along y, turn about z" in items["constraints"].message
    assert items["constraints"].rows == ("Supports",)
    # hold only one edge against z: the plate can still tilt about the other axis
    data["supports"] = [{"region": "Edge-Left", "dofs": [1, 2, 3]}]
    loose.write_text(json.dumps(data), encoding="utf-8")
    checklist, _, _ = setup_checklist(read_values(loose), tmp_path / "root", ccx=lambda: None, tectonic=lambda: None)
    items = {item.id: item for item in checklist.items}
    assert items["constraints"].state == "fail" and "out of its plane" in items["constraints"].message and "tilt about y" in items["constraints"].message


def test_the_values_file_carries_the_lists_and_reads_back(tmp_path):
    form = read_values(PLATE_VALUES)
    assert set(form.lists) == {"supports", "loads", "regions"} and len(form.lists["supports"]) == 6
    values = check_form(form)
    assert values.kind == "plate" and values.control == "" and values.value is None and len(values.supports) == 6 and values.loads == [{"region": "Face", "pressure": -0.01}]
    spec = spec_from_values(values, designation_for(values, tmp_path / "none"), "values.json")
    assert spec.kind == "plate" and len(spec.supports) == 6 and spec.loads[0].pressure == pytest.approx(-0.01e6) and spec.loading is None
    back = values_of_spec(spec)
    assert back["supports"][0] == {"region": "Edge-Left", "dofs": [3, 4], "value": 0.0} and back["loads"] == [{"region": "Face", "pressure": -0.01}]
    assert back["regions"][1] == {"name": "Corner-X", "x0": 99.9, "x1": 100.0, "y0": 0.0, "y1": 0.1} and "control" not in back


@pytest.mark.parametrize("change, message", [
    ({"supports": []}, "Supports: required for a plate"),
    ({"supports": [{"region": "Edge-Nowhere", "dofs": [3]}]}, "Supports: entry 1 names region 'Edge-Nowhere'"),
    ({"supports": [{"region": "Edge-Left", "dofs": [0]}]}, "needs dofs as a list of distinct numbers from 1 to 6"),
    ({"supports": [{"region": "Edge-Left", "dofs": [1, 2], "value": 0.5}]}, "moves, so it needs exactly one dof"),
    ({"loads": [{"region": "Face", "pressure": "ten"}]}, "has a pressure that is not a number"),
    ({"loads": [{"region": "Edge-Left", "dof": 7, "total": 5.0}]}, "needs dof from 1 to 5"),
    ({"loads": [], "supports": [{"region": "Edge-Left", "dofs": [1, 2, 3]}]}, "Loads: a plate needs a load, or a support that moves"),
    ({"regions": [{"name": "B", "x0": 0.0}]}, "Regions: entry 1 needs name, x0, x1, y0, y1"),
    ({"test": "unnotched tension", "tab_length": 0.0, "control": "displacement", "value": 1.0}, "Supports, Loads and Regions: belong to a plate only"),
])
def test_the_plate_lists_are_refused_by_name(tmp_path, change, message):
    data = {**json.loads(PLATE_VALUES.read_text(encoding="utf-8")), **change}
    path = tmp_path / "values.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(IntakeError, match=message):
        check_form(read_values(path))


def test_a_values_file_without_lists_is_still_the_form(tmp_path):
    data = json.loads(PLATE_VALUES.read_text(encoding="utf-8"))
    data["supports"] = "Edge-Left"
    path = tmp_path / "values.json"
    path.write_text(json.dumps({**data, "form_version": FORM_VERSION}), encoding="utf-8")
    with pytest.raises(IntakeError, match="supports must be a list of objects"):
        read_values(path)
