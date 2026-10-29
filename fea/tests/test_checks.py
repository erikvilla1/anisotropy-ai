"""The setup check (ADR-0051): every item judged from the tools' own refusals and the model, a failed row named under its item, a
warning that does not block, and what is installed. Mesh quality and the preview are checked here too. Nothing touches .local/."""

import json
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.checks import ITEM_OF_KEY, ITEMS, coupon_attempts, setup_checklist, split_problems
from anisotropy_fea.femodel import build_model
from anisotropy_fea.intake import FIELDS, FORM_VERSION, convert, read_values
from anisotropy_fea.mesher import structured_rectangle
from anisotropy_fea.preview import preview_data
from anisotropy_fea.quality import THRESHOLDS, element_quality, quality_summary, quality_words
from anisotropy_fea.spec import load_spec

from public_coupon import DESIGNATION
from test_intake import OHT_FILL, PUBLIC_FILL, own_constants

CCX = lambda: Path("ccx")  # noqa: E731
TOOLS = dict(ccx=CCX, tectonic=lambda: "tectonic", gmsh=lambda: "4.15")


@pytest.fixture(scope="module", autouse=True)
def local_untouched():
    before = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    yield
    after = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    assert before == after, "the check tests must not write under .local/"


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22" if ccx is not None else None)


def values_file(folder: Path, values: dict, **changes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **values, **changes}), encoding="utf-8")
    return path


def checklist(folder: Path, values: dict, root: Path | None = None, **changes):
    return setup_checklist(read_values(values_file(folder, values, **changes)), root or folder / "none", **TOOLS)


def by_id(checked) -> dict:
    return {item.id: item for item in checked.items}


# --------------------------------------------------------------------------------------------- a good setup

def test_a_complete_setup_passes_every_item(tmp_path):
    checked, model, quality = checklist(tmp_path, PUBLIC_FILL)
    items = by_id(checked)
    assert [item.id for item in checked.items] == [item_id for item_id, _ in ITEMS] and checked.state == "ready" and checked.problems == ()
    assert {item.state for item in checked.items} == {"pass"} and checked.designation == DESIGNATION and not checked.coupon_exists and checked.attempts == 0
    assert "a new coupon" in items["identity"].message and "mm, MPa and N" in items["units"].message
    assert "250 by 25 mm, 56 mm tabs with a node row on each tab line" in items["geometry"].message
    assert "library im7-8552" in items["material"].message and "strengths given" in items["material"].message
    assert "8 plies [45/0/-45/90]s" in items["laminate"].message and "B = 0" in items["laminate"].message
    assert "through a reference point at each end" in items["constraints"].message and "no rigid-body motion is left" in items["constraints"].message
    assert items["load"].message == "displacement of 1 mm on the top grip along the coupon, a pull"
    assert items["mesh"].message.startswith("1200 elements, 1331 nodes (structured mesh, order 1); aspect ratio")
    assert items["criterion"].message == "first-ply failure by max_stress, tsai_hill"
    assert "node centre at (12.5, 125)" in items["probes"].message and "element centre, element near_grip" in items["probes"].message
    assert items["solver"].message.startswith("CalculiX 2.22 at ccx") and items["document"].message.startswith("Tectonic at tectonic")
    assert model is not None and model.mesh.element_count == 1200 and quality is not None and quality.element_count == 1200
    as_dict = checked.as_dict()
    assert as_dict["state"] == "ready" and as_dict["items"][0] == {"id": "identity", "label": "Who and which coupon", "state": "pass",
                                                                   "message": items["identity"].message, "rows": []}
    json.dumps(as_dict)


def test_an_existing_coupon_counts_its_attempts(tmp_path):
    root = tmp_path / "root"
    convert(values_file(tmp_path / "first", PUBLIC_FILL), root=root, day="2026-10-28")
    checked, _, _ = checklist(tmp_path / "second", PUBLIC_FILL, root=root)
    assert checked.coupon_exists and checked.attempts == 1 and "this run is attempt 2" in by_id(checked)["identity"].message
    assert coupon_attempts(root, DESIGNATION) == (True, 1) and coupon_attempts(root, "NONE-UNT-L9") == (False, 0)


# --------------------------------------------------------------------------------------------- refusals land under their items

def test_blank_and_wrong_rows_block_the_run_under_their_items(tmp_path):
    checked, model, quality = checklist(tmp_path, PUBLIC_FILL, length=None, width="wide", G23=None, value=-1.0, criteria="tsai-wu")
    items = by_id(checked)
    assert checked.state == "blocked" and model is None and quality is None and checked.designation is None
    assert items["geometry"].state == "missing" and items["geometry"].rows == ("Length (mm)", "Width (mm)")
    assert "Length (mm): required" in items["geometry"].message and "Width (mm): a number is needed, not 'wide'" in items["geometry"].message
    assert items["material"].state == "missing" and items["material"].rows == ("G23 (MPa)",)
    assert items["load"].state == "fail" and items["load"].message == "Value (mm or N): must be greater than 0, not -1"
    assert items["criterion"].state == "missing" and items["criterion"].rows == ("Tsai-Wu interaction f12*",)
    assert {items[i].state for i in ("units", "laminate", "constraints", "mesh", "probes")} == {"pending"}
    assert items["solver"].state == "pass"  # what is installed is judged whatever the inputs say
    assert len(checked.problems) == 1 and checked.problems[0].startswith("values.json: ")


def test_a_spec_rule_lands_on_the_rows_it_names(tmp_path):
    checked, _, _ = checklist(tmp_path, PUBLIC_FILL, tab_length=0.0)  # tabs region with no tabs: refused by the spec, not the form
    items = by_id(checked)
    assert checked.state == "blocked" and items["constraints"].state == "fail"
    assert items["constraints"].rows == ("Grip region", "Tab length (mm)") and 'grips.region = "tabs" needs a positive geometry.tab_length' in items["constraints"].message


def test_a_name_clash_lands_on_the_identity(tmp_path):
    root = tmp_path / "root"
    convert(values_file(tmp_path / "first", PUBLIC_FILL), root=root, day="2026-10-28")
    checked, _, _ = checklist(tmp_path / "second", PUBLIC_FILL, root=root, layup_code="L1", angles=[0, 90])
    items = by_id(checked)
    assert checked.state == "blocked" and items["identity"].state == "fail" and "L1 already names another stacking sequence" in items["identity"].message
    assert items["identity"].rows == ("Layup code", "Material code")


def test_a_warning_does_not_block(tmp_path):
    without = {**own_constants(), **{k: None for k in ("own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6")}}
    checked, _, _ = checklist(tmp_path, PUBLIC_FILL, **without)
    items = by_id(checked)
    assert checked.state == "ready" and items["criterion"].state == "warn" and "the material has no strengths" in items["criterion"].message
    assert items["material"].state == "pass" and "no strengths" in items["material"].message


def test_a_modulus_in_the_wrong_unit_warns(tmp_path):
    own = own_constants()
    own = {**own, "own_E1": own["own_E1"] / 1e3, "own_E2": own["own_E2"] / 1e3, "own_G12": own["own_G12"] / 1e3}  # GPa typed on the MPa rows
    checked, _, _ = checklist(tmp_path, PUBLIC_FILL, **own)
    items = by_id(checked)
    assert items["units"].state == "warn" and "E1 = 162.096 MPa" in items["units"].message and "GPa typed as MPa" in items["units"].message
    assert items["units"].rows == ("Own material: E1 (MPa)", "Own material: E2 (MPa)", "Own material: G12 (MPa)") and checked.state == "ready"


def test_constants_the_engine_refuses_fail_the_material(tmp_path):
    checked, model, _ = checklist(tmp_path, PUBLIC_FILL, **{**own_constants(), "own_E1": 162.0})  # E1 alone in GPa: nu12^2 < E1/E2 no longer holds
    items = by_id(checked)
    assert checked.state == "blocked" and model is None and items["material"].state == "fail"
    assert "our engine refuses these constants: Elastic constants violate positive compliance" in items["material"].message
    assert items["material"].rows[0] == "Own material: E1 (MPa)" and checked.problems == ("Elastic constants violate positive compliance: need nu12**2 < E1/E2",)


def test_what_is_not_installed_is_named(tmp_path):
    form = read_values(values_file(tmp_path, PUBLIC_FILL))
    checked, _, _ = setup_checklist(form, tmp_path / "none", ccx=lambda: None, tectonic=lambda: None, gmsh=lambda: None)
    items = by_id(checked)
    assert checked.state == "blocked" and items["solver"].state == "fail" and "CalculiX not found" in items["solver"].message
    assert items["document"].state == "warn" and "without its PDF" in items["document"].message
    checked, _, _ = setup_checklist(read_values(values_file(tmp_path / "oht", OHT_FILL)), tmp_path / "none", ccx=CCX, tectonic=lambda: "t", gmsh=lambda: None)
    items = by_id(checked)
    assert items["mesh"].state == "fail" and "Gmsh is not installed" in items["mesh"].message and items["mesh"].rows == ("Hole diameter (mm)",)


def test_every_form_row_belongs_to_an_item():
    assert set(ITEM_OF_KEY) == set(FIELDS) and set(ITEM_OF_KEY.values()) <= {item_id for item_id, _ in ITEMS}
    assert split_problems("values.json: Length (mm): required; Library material and Own material: give one of the two") == [
        ("Length (mm)", "Length (mm): required"), ("Library material", "Library material and Own material: give one of the two")]


# --------------------------------------------------------------------------------------------- mesh quality

def test_quality_measures_a_square_a_stretched_and_a_skewed_element():
    square = structured_rectangle(1.0, 1.0, 1, 1)
    q = element_quality(square.xy, square.corners)
    assert q.aspect_ratio[0] == pytest.approx(1.0) and q.min_angle_deg[0] == pytest.approx(90.0) and q.max_angle_deg[0] == pytest.approx(90.0)
    assert q.jacobian_ratio[0] == pytest.approx(1.0)
    stretched = structured_rectangle(12.0, 1.0, 1, 1)
    assert element_quality(stretched.xy, stretched.corners).aspect_ratio[0] == pytest.approx(12.0)
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [1.5, 1.0], [0.0, 1.0]])  # a trapezium: angles 90, 90, 63.4, 116.6; Jacobian 0.25 to 0.375
    q = element_quality(xy, np.array([[0, 1, 2, 3]]))
    assert q.min_angle_deg[0] == pytest.approx(63.4349, abs=1e-3) and q.max_angle_deg[0] == pytest.approx(116.5651, abs=1e-3)
    assert q.jacobian_ratio[0] == pytest.approx(0.25 / 0.375)
    summary = quality_summary(q)
    assert summary["acceptable"] and summary["measures"]["aspect_ratio"]["threshold"] == THRESHOLDS["aspect_ratio"]
    over = quality_summary(element_quality(stretched.xy, stretched.corners))
    assert not over["acceptable"] and over["measures"]["aspect_ratio"] == {"word": "aspect ratio", "worst": 12.0, "element": 0, "threshold": 10.0,
                                                                            "warns": "above", "over": 1}
    assert quality_words(over).startswith("aspect ratio 12 at worst (warns above 10): 1 element past it; smallest angle 90° at worst")


def test_the_public_coupon_mesh_is_within_every_threshold(tmp_path):
    _, model, quality = checklist(tmp_path, PUBLIC_FILL)
    summary = quality_summary(quality)
    assert summary["acceptable"] and summary["elements"] == 1200
    assert summary["measures"]["aspect_ratio"]["worst"] == pytest.approx(2.5 / 2.0)  # the tabs' 2 mm rows against the 2.5 mm columns


# --------------------------------------------------------------------------------------------- the preview

def test_the_preview_says_what_is_drawn_held_and_loaded(tmp_path):
    checked, model, quality = checklist(tmp_path, PUBLIC_FILL)
    data = preview_data(model, quality)
    json.dumps(data)
    assert data["units"] == "mm-MPa" and data["labels"]["force"] == "N" and data["coupon"]["designation"] == DESIGNATION
    assert data["coupon"]["test"] == "unnotched tension" and data["coupon"]["layup"] == "[45/0/-45/90]s" and ("Coupon", DESIGNATION) in map(tuple, data["coupon"]["card"])
    assert data["geometry"] == {"length": 250.0, "width": 25.0, "tab_length": 56.0, "hole_diameter": None, "thickness": pytest.approx(8 * 0.18288),
                                "span": None, "overhang": None, "load_span": None}
    mesh = data["mesh"]
    assert len(mesh["nodes"]) == 1331 and len(mesh["quads"]) == 1200 and mesh["node_count"] == 1331 and mesh["element_count"] == 1200
    assert mesh["nodes"][0] == [0.0, 0.0] and max(max(q) for q in mesh["quads"]) == 1330 and mesh["order"] == 1 and mesh["mesher"] == "structured"
    assert set(mesh["node_sets"]) >= {"Grip-Bottom", "Grip-Top", "Edge-Left", "Edge-Right", "Tab-Bottom-Line", "Probe-centre"}
    assert set(mesh["element_sets"]) >= {"Tab-Bottom", "Gauge", "Tab-Top", "Probe-centre", "Probe-near_grip"}
    assert data["held"] == [{"set": "Grip-Bottom", "through": "RF-Bottom", "dofs": [1, 2, 3, 4, 5, 6],
                             "directions": ["x", "y", "z", "rotation about x", "rotation about y", "rotation about z"], "nodes": len(mesh["node_sets"]["Grip-Bottom"])},
                            {"set": "Grip-Top", "through": "RF-Top", "dofs": [1], "directions": ["x"], "nodes": len(mesh["node_sets"]["Grip-Top"])},
                            {"set": "Grip-Top", "through": "RF-Top", "dofs": [3, 4, 5, 6], "directions": ["z", "rotation about x", "rotation about y", "rotation about z"],
                             "nodes": len(mesh["node_sets"]["Grip-Top"])}]
    assert data["loaded"] == {"set": "Grip-Top", "through": "RF-Top", "control": "displacement", "dof": 2, "direction": "+y", "value": 1.0, "unit": "mm",
                              "nodes": len(mesh["node_sets"]["Grip-Top"])}
    assert [p["angle"] for p in data["plies"]] == [45, 0, -45, 90, 90, -45, 0, 45] and data["plies"][0]["z_bottom"] == pytest.approx(-4 * 0.18288)
    assert data["plies"][-1]["z_top"] == pytest.approx(4 * 0.18288) and data["plies"][0]["material"] == "IM7-8552-Lamina"
    material = data["material"]
    assert material["name"] == "IM7-8552-Lamina" and material["rights"] == "open-publisher" and material["E1"] == pytest.approx(162096.0, rel=1e-3)
    assert material["strengths"]["F1t"] > 0 and material["criteria"] == ["max_stress", "tsai_hill"] and material["plies"] == 8
    assert data["probes"]["nodes"]["centre"]["xy"] == [12.5, 125.0] and data["probes"]["elements"]["near_grip"]["index"] >= 0
    assert data["quality"]["summary"]["acceptable"] and len(data["quality"]["per_element"]["aspect_ratio"]) == 1200


def test_the_preview_of_a_force_controlled_nodal_coupon(tmp_path):
    spec = load_spec(paths.spec_path("patch-1x1-cload-im7-engine-equality")) if False else None  # no such spec; the nodal check with force control instead
    _, model, _ = checklist(tmp_path, PUBLIC_FILL, grips="nodal", control="force", value=10000.0)
    data = preview_data(model, None)
    assert data["held"][0] == {"set": "Grip-Bottom", "through": None, "dofs": [1, 2, 3, 4, 5, 6],
                               "directions": ["x", "y", "z", "rotation about x", "rotation about y", "rotation about z"], "nodes": data["held"][0]["nodes"]}
    assert data["loaded"]["control"] == "force" and data["loaded"]["value"] == pytest.approx(10000.0) and data["loaded"]["unit"] == "N"
    assert data["loaded"]["set"] == "Grip-Top" and data["loaded"]["through"] is None and "quality" not in data
    assert build_model(model.spec).mesh.element_count == model.mesh.element_count
