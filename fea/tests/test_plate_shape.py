"""A plate's shape before it is held or loaded (ADR-0101 amendment 1): the mesh and regions shown to be clicked, nothing drawn for a list
that is not stated, the setup still blocked, and nothing shown when the plate is hidden or refused for another reason."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.checks import SHAPE_LOAD, SHAPE_SUPPORT, plate_shape, setup_checklist
from anisotropy_fea.enabled import ALL_TESTS_VARIABLE
from anisotropy_fea.intake import read_values
from anisotropy_fea.preview import preview_data, shape_data

from test_checks import TOOLS, by_id
from test_intake import PUBLIC_FILL

PLATE = json.loads((paths.ROOT / "tests" / "fixtures" / "studio-plate" / "values.json").read_text(encoding="utf-8"))
TOOL = paths.ROOT / "fea" / "tools" / "studio_tool.py"


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22" if ccx is not None else None)  # as tests/test_checks.py


def form_of(folder: Path, **changes):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({**PLATE, **changes}), encoding="utf-8")
    return read_values(path)


def test_a_plate_with_nothing_held_or_loaded_shows_its_mesh_and_regions_and_stays_blocked(tmp_path):
    bare = form_of(tmp_path / "bare", supports=[], loads=[])
    checked, model, _ = setup_checklist(bare, tmp_path / "none", **TOOLS)
    assert checked.state == "blocked" and model is None and by_id(checked)["constraints"].state == "missing"
    shape, stood_in = plate_shape(bare, tmp_path / "none")
    assert stood_in == ("supports", "loads")
    data = shape_data(shape, stood_in)
    assert data["shape"] == ["supports", "loads"] and data["held"] == [] and data["loads"] == [] and data["loaded"] is None
    assert data["regions"]["edges"][:4] == ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right"] and "Face" in data["regions"]["areas"]
    assert data["mesh"]["element_count"] > 0 and set(data["regions"]["edges"]) <= set(data["mesh"]["node_sets"])
    assert '"control"' not in json.dumps(data)  # no load, stated or stood in, is anywhere in what the page is sent


def test_the_shape_is_the_mesh_the_stated_plate_has(tmp_path):
    """Supports and loads do not move a node: the plate clicked before it is held is the plate checked after."""
    stated = form_of(tmp_path / "stated")
    _, model, _ = setup_checklist(stated, tmp_path / "none", **TOOLS)
    assert model is not None and plate_shape(stated, tmp_path / "none") is None  # both lists stated: the setup's own model is shown
    shape, _ = plate_shape(form_of(tmp_path / "bare", supports=[], loads=[]), tmp_path / "none")
    assert np.array_equal(shape.mesh.xy, model.mesh.xy) and np.array_equal(shape.mesh.corners, model.mesh.corners)
    for sets, others in ((shape.node_sets, model.node_sets), (shape.element_sets, model.element_sets)):
        assert set(sets) == set(others) and all(np.array_equal(sets[name], others[name]) for name in sets)
    assert preview_data(model)["mesh"] == shape_data(shape, ("supports", "loads"))["mesh"]


def test_a_stated_list_is_drawn_and_only_the_missing_one_is_stood_in(tmp_path):
    held = form_of(tmp_path / "held", loads=[])
    shape, stood_in = plate_shape(held, tmp_path / "none")
    assert stood_in == ("loads",)
    data = shape_data(shape, stood_in)
    assert data["shape"] == ["loads"] and data["loads"] == [] and data["loaded"] is None
    assert {h["set"] for h in data["held"]} == {s["region"] for s in PLATE["supports"]}
    loaded = form_of(tmp_path / "loaded", supports=[])
    shape, stood_in = plate_shape(loaded, tmp_path / "none")
    assert stood_in == ("supports",)
    data = shape_data(shape, stood_in)
    assert data["held"] == [] and [load["set"] for load in data["loads"]] == [ld["region"] for ld in PLATE["loads"]] and data["loaded"] == data["loads"][0]


def test_no_shape_for_another_test_or_for_a_plate_refused_for_another_reason(tmp_path):
    folder = tmp_path / "tension"
    folder.mkdir()
    (folder / "values.json").write_text(json.dumps({"form_version": PLATE["form_version"], **PUBLIC_FILL}), encoding="utf-8")
    assert plate_shape(read_values(folder / "values.json"), tmp_path / "none") is None
    assert plate_shape(form_of(tmp_path / "no-width", supports=[], loads=[], width=None), tmp_path / "none") is None
    assert plate_shape(form_of(tmp_path / "bad-list", supports=[], loads=[{"region": "Nowhere", "pressure": 1.0}]), tmp_path / "none") is None


def test_a_hidden_plate_shows_no_shape(tmp_path, monkeypatch):
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "off")
    assert plate_shape(form_of(tmp_path, supports=[], loads=[]), tmp_path / "none") is None


def test_the_stand_ins_name_regions_every_plate_has():
    assert SHAPE_SUPPORT["region"] == "Edge-Bottom" and SHAPE_LOAD["region"] == "Face" and set(SHAPE_LOAD) == {"region", "pressure"}


@pytest.mark.parametrize("command", ["check", "live"])
def test_the_studio_tool_writes_the_shape_as_the_preview_and_solves_nothing(tmp_path, command):
    values = tmp_path / "values.json"
    values.write_text(json.dumps({**PLATE, "supports": [], "loads": []}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(TOOL), "--root", str(tmp_path / "none"), command, str(values), "--out", str(tmp_path / "out")],
                          capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stderr
    written = {p.name for p in (tmp_path / "out").iterdir()}
    assert {"checklist.json", "preview.json"} <= written and not written & {"fields.json", "summary.json", "explanation.json"}
    assert json.loads((tmp_path / "out" / "checklist.json").read_text(encoding="utf-8"))["state"] == "blocked"
    preview = json.loads((tmp_path / "out" / "preview.json").read_text(encoding="utf-8"))
    assert preview["shape"] == ["supports", "loads"] and preview["loaded"] is None


def test_the_pages_fixture_of_the_stated_plate_has_the_shapes_mesh_and_keys(tmp_path):
    """The page's tests draw a shape from `tests/fixtures/studio-plate/preview.json` with its lists emptied: the same mesh, regions and keys
    as the shape the tool writes for that plate with nothing held or loaded."""
    fixture = json.loads((paths.ROOT / "tests" / "fixtures" / "studio-plate" / "preview.json").read_text(encoding="utf-8"))
    shape, stood_in = plate_shape(form_of(tmp_path, supports=[], loads=[]), tmp_path / "none")
    data = shape_data(shape, stood_in)
    assert data["regions"] == fixture["regions"] and data["geometry"] == fixture["geometry"]
    assert data["mesh"]["quads"] == fixture["mesh"]["quads"] and data["mesh"]["node_sets"] == fixture["mesh"]["node_sets"]
    assert np.allclose(np.array(data["mesh"]["nodes"]), np.array(fixture["mesh"]["nodes"]))
    assert set(data) - {"shape"} == set(fixture) - {"quality"}
