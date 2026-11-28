"""The workspace's tools over a model's setup (ADR-0143): the plate read with its ends and sides, typed changes made every one or none,
the values the fea package takes, the routes that preview and apply them, and a project's versions kept by the server. What the page
writes for the same plates and sentences is `tests/fixtures/setup-tools/plate-setup.json`, and the tools must agree with it."""

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import setup_tools as tools
from anisotropy_api.main import app
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

FIXTURE = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "setup-tools" / "plate-setup.json").read_text(encoding="utf-8"))
PLATE = {"form": {"test": "plate", "units": "mm-MPa", "length": "250", "width": "25", "library": "im7-8552", "ply_1": "45", "ply_2": "0",
                  "ply_3": "-45", "ply_4": "90", "symmetric": "yes", "element_size": "", "date": "2026-11-26"},
         "plate": {"supports": [], "loads": [], "regions": []}}
COUPON = {"form": {"test": "unnotched tension", "length": "250", "width": "25", "library": "im7-8552", "ply_1": "0", "control": "displacement", "value": "1"},
          "plate": {"supports": [], "loads": [], "regions": []}}
PULLED = [{"action": "hold", "region": "Edge-Bottom", "dofs": [1, 2, 3, 4, 5, 6]},
          {"action": "force", "region": "Edge-Top", "sense": "tension", "value": "10", "unit": "kN"}]


def with_form(content: dict, **rows: str) -> dict:
    return {**content, "form": {**content["form"], **rows}}


# ------------------------------------------------------------------------------------------- the page and the tools agree

@pytest.mark.parametrize("case", FIXTURE["values"], ids=lambda c: c["name"])
def test_a_plates_values_are_the_pages(case):
    assert tools.plate_values({"form": case["form"], "plate": case["plate"]}) == case["values"]


@pytest.mark.parametrize("case", FIXTURE["edits"]["cases"], ids=lambda c: c["text"])
def test_a_typed_change_does_what_the_pages_sentence_does(case):
    start = {"form": FIXTURE["edits"]["form"], "plate": FIXTURE["edits"]["start"]}
    changed = tools.change_setup(start, case["changes"])
    assert changed.ok, changed.refused
    assert changed.content["plate"] == case["after"]
    assert changed.done == case["done"]
    assert start["plate"] == FIXTURE["edits"]["start"]  # the setup given is never changed in place


def test_a_force_on_a_held_direction_is_refused_as_the_page_notes_it():
    """A force along a direction its region is held in would go into the support, so it is refused, in the page's words (ADR-0143 am. 1);
    a force or a set move of a direction taking the other's place is in the fixture's cases above."""
    start = {"form": FIXTURE["edits"]["form"], "plate": FIXTURE["edits"]["start"]}
    changed = tools.change_setup(start, [{"action": "force", "region": "Edge-Bottom", "sense": "compression", "value": "1", "unit": "kN"}])
    assert not changed.ok and changed.content == start
    assert changed.refused == [{"change": 1, "reason": "Edge-Bottom is held along y, so a force along y there would go into the support: "
                                                      "free Edge-Bottom or hold it along other directions first"}]


def test_a_coupons_value_takes_its_unit_by_the_loading_type():
    """Value is a travel under displacement and a force under force; a unit of the other quantity asks for the Loading type first."""
    pulled = tools.change_setup(COUPON, [{"action": "row", "key": "control", "value": "force"},
                                         {"action": "row", "key": "value", "value": "2", "unit": "kN"}])
    assert pulled.ok and pulled.content["form"]["value"] == "2000"
    assert pulled.done == ["Loading type: displacement → force", "Value (mm or N): 1 → 2000"]
    moved = tools.change_setup(COUPON, [{"action": "row", "key": "value", "value": "0.5", "unit": "mm"}])
    assert moved.ok and moved.content["form"]["value"] == "0.5"
    wrong = tools.change_setup(COUPON, [{"action": "row", "key": "value", "value": "2", "unit": "kN"}])
    assert wrong.refused == [{"change": 1, "reason": "Value (mm or N) is a travel under displacement loading, and kN is not: set the Loading type "
                                                    "to force first, or give the value in mm"}]
    inches = tools.change_setup(COUPON, [{"action": "row", "key": "value", "value": "0.02", "unit": "in"}])
    assert not inches.ok and "US units" in inches.refused[0]["reason"]


def test_a_coupons_values_are_not_a_plates():
    with pytest.raises(ValueError, match="a plate's values"):
        tools.plate_values(COUPON)


# ------------------------------------------------------------------------------------------- reading the model

def test_the_plate_is_read_with_its_ends_and_sides():
    setup = tools.read_setup(PLATE)
    assert setup["is_plate"] and setup["units"] == {"system": "mm-MPa", "length": "mm", "force": "N", "stress": "MPa"}
    assert setup["size"] == {"length": "250", "width": "25", "tab_length": None, "hole_diameter": None}
    assert setup["layup"] == {"plies_bottom_first": ["45", "0", "-45", "90"], "symmetric": "yes"}
    roles = {r["name"]: r["role"] for r in setup["regions"]}
    assert roles == {"Edge-Bottom": "end", "Edge-Top": "end", "Edge-Left": "side", "Edge-Right": "side", "Face": "area"}
    where = {r["name"]: r["where"] for r in setup["regions"]}
    assert where["Edge-Top"] == "the top end, at y = 250, across the width (25 mm)"
    assert where["Edge-Left"] == "the left side, at x = 0, along the length (250 mm)"
    assert "Edge-Left and Edge-Right are its long sides" in setup["note"]
    assert setup["held"] == [] and setup["loaded"] == []
    assert setup["digest"] == tools.content_digest(PLATE)


def test_the_tabs_the_hole_and_a_box_are_regions_too():
    content = {"form": {**PLATE["form"], "tab_length": "50", "hole_diameter": "6"},
               "plate": {"supports": [], "loads": [], "regions": [{"name": "Patch", "x0": "5", "x1": "20", "y0": "100", "y1": "150"}]}}
    ends = tools.regions(content, "ends")
    assert [r["name"] for r in ends] == ["Edge-Bottom", "Edge-Top", "Tab-Bottom", "Tab-Top"]
    assert ends[2]["where"] == "the tab at the bottom end, 50 mm long" and ends[2]["kind"] == "area"
    assert [r["name"] for r in tools.regions(content, "sides")] == ["Edge-Left", "Edge-Right"]
    assert [r["name"] for r in tools.regions(content, "edges")] == ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Hole"]
    assert [r["name"] for r in tools.regions(content, "areas")] == ["Face", "Tab-Bottom", "Tab-Top", "Patch"]
    assert tools.regions(content, "areas")[-1]["where"] == "a box drawn on the face: x 5 to 20, y 100 to 150 mm"
    with pytest.raises(ValueError, match="role must be one of"):
        tools.regions(content, "middle")


def test_what_is_held_and_loaded_is_read_in_lines():
    changed = tools.change_setup(PLATE, [*PULLED, {"action": "pressure", "region": "Face", "value": "-0.02"},
                                         {"action": "move", "region": "Edge-Left", "dof": 3, "value": "0.5"}])
    setup = tools.read_setup(changed.content)
    assert setup["held"] == ["Edge-Bottom: fixed (encastre)", "Edge-Left: moved 0.5 mm along z"]
    assert setup["loaded"] == ["Edge-Top: force of 10000 N along y", "Face: pressure of -0.02 MPa, lifting the plate"]


def test_a_coupon_is_read_as_held_by_its_test():
    setup = tools.read_setup(COUPON)
    assert not setup["is_plate"] and "regions" not in setup
    assert "held and loaded by its test's grips" in setup["note"]
    assert "hole_diameter" not in setup["size"]  # an unnotched coupon has no hole row


# ------------------------------------------------------------------------------------------- changes: every one or none

def test_the_ten_kilonewton_pull_of_the_mockup():
    changed = tools.change_setup(PLATE, [*PULLED, {"action": "row", "key": "element_size", "value": "2.1"}])
    assert changed.ok
    assert changed.done == ["Edge-Bottom: fixed (encastre)", "Edge-Top: force of 10000 N along y (tension)", "Element size (mm): blank → 2.1"]
    values = tools.plate_values(changed.content)
    assert values["supports"] == [{"region": "Edge-Bottom", "dofs": [1, 2, 3, 4, 5, 6]}]
    assert values["loads"] == [{"region": "Edge-Top", "dof": 2, "total": 10000}]
    assert values["element_size"] == 2.1 and values["input"] == "plate"


def test_one_refused_change_makes_none():
    changed = tools.change_setup(PLATE, [*PULLED, {"action": "pressure", "region": "Edge-Top", "value": "1"}])
    assert not changed.ok and changed.done == []
    assert changed.content == PLATE
    assert changed.refused == [{"change": 3, "reason": "a pressure acts on an area, and Edge-Top is an edge"}]


@pytest.mark.parametrize(("change", "reason"), [
    ({"action": "hold", "region": "Edge-Middle", "dofs": [1]}, "Edge-Middle is not a region of this plate; it has Edge-Bottom, Edge-Top, Edge-Left, Edge-Right, Face"),
    ({"action": "hold", "region": "Hole", "dofs": [1]}, "Hole is not a region of this plate"),
    ({"action": "hold", "region": "Edge-Left", "dofs": [1, 1]}, "a hold names the directions it holds, each once"),
    ({"action": "hold", "region": "Edge-Left", "dofs": [7]}, "a hold names the directions it holds"),
    ({"action": "hold", "region": "Edge-Left", "dofs": [True]}, "a hold names the directions it holds"),
    ({"action": "force", "region": "Face", "sense": "tension", "value": "5"}, "tension has no one direction on Face"),
    ({"action": "force", "region": "Edge-Top", "dof": 4, "value": "5"}, "a force acts along a direction: 1, 2 or 3"),
    ({"action": "force", "region": "Edge-Top", "dof": 2, "sense": "tension", "value": "5"}, "a direction or a sense"),
    ({"action": "force", "region": "Edge-Top", "sense": "tension", "value": "5", "unit": "kip"}, "kip belongs to US units"),
    ({"action": "force", "region": "Edge-Top", "sense": "tension", "value": "5", "unit": "MPa"}, "MPa is not a unit of this value, which the model states in N"),
    ({"action": "force", "region": "Edge-Top", "sense": "tension", "value": "0"}, "a value of zero changes nothing"),
    ({"action": "force", "region": "Edge-Top", "sense": "tension", "value": "ten"}, "ten is not a number"),
    ({"action": "move", "region": "Edge-Top", "dof": 2, "value": "1", "unit": "in"}, "in belongs to US units"),
    ({"action": "move", "region": "Edge-Top", "dof": 6, "value": "1", "unit": "mm"}, "mm is not an angle's unit"),
    ({"action": "free", "region": "Edge-Top"}, "nothing is held on Edge-Top"),
    ({"action": "unload", "region": "Edge-Top"}, "no load is on Edge-Top"),
    ({"action": "turn", "region": "Edge-Top"}, "the action must be one of"),
    ({"action": "row", "key": "test", "value": "unnotched tension"}, "Test is set on the page"),
    ({"action": "row", "key": "filled_by", "value": "someone"}, "is set on the page"),
    ({"action": "row", "key": "control", "value": "force"}, "Loading type is not a row of a plate"),
    ({"action": "row", "key": "ply_1", "value": "120"}, "120 is not an angle from -90 to 90 degrees"),
    ({"action": "row", "key": "hole_circumferential", "value": "32.5"}, "takes a whole number"),
    ({"action": "row", "key": "criteria", "value": "hashin"}, "'hashin' is not one of Failure criterion's choices"),
    ({"action": "row", "key": "length", "value": ""}, "Length (mm) is required"),
    ({"action": "row", "key": "length", "value": "250"}, "Length (mm) is already 250"),
    ({"action": "row", "key": "own_nu12", "value": "0.3", "unit": "mm"}, "is a pure number and carries no unit"),
    ({"action": "row", "key": "bogus", "value": "1"}, "bogus is not a row of the form"),
])
def test_a_change_the_plate_cannot_take_is_refused_in_words(change, reason):
    changed = tools.change_setup(PLATE, [change])
    assert not changed.ok and changed.content == PLATE
    assert reason in changed.refused[0]["reason"]


def test_units_of_the_models_own_system_are_converted_exactly():
    changed = tools.change_setup(PLATE, [{"action": "pressure", "region": "Face", "value": "20", "unit": "kPa"},
                                         {"action": "move", "region": "Edge-Top", "dof": 2, "value": "0.1", "unit": "cm"},
                                         {"action": "row", "key": "width", "value": "0.036", "unit": "m"},
                                         {"action": "move", "region": "Edge-Bottom", "dof": 6, "value": 2, "unit": "degrees"}])
    assert changed.ok, changed.refused
    assert changed.done == ["Face: pressure of 0.02 MPa, pressing down on the plate", "Edge-Top: moved 1 mm along y", "Width (mm): 25 → 36",
                            "Edge-Bottom: turned 0.0349065850399 rad about z"]
    in_psi = tools.change_setup(with_form(PLATE, units="in-psi", length="10", width="1"),
                                [{"action": "force", "region": "Edge-Top", "sense": "compression", "value": "2", "unit": "kip"}])
    assert in_psi.done == ["Edge-Top: force of -2000 lbf along y (compression)"]


def test_a_coupon_takes_rows_but_no_supports_or_loads():
    assert tools.change_setup(COUPON, [{"action": "row", "key": "value", "value": "2"}]).done == ["Value (mm or N): 1 → 2"]
    refused = tools.change_setup(COUPON, PULLED[:1])
    assert "supports and loads on named regions are a plate's" in refused.refused[0]["reason"]


def test_no_changes_or_too_many_are_refused():
    assert tools.change_setup(PLATE, []).refused == [{"change": 0, "reason": "no change was given"}]
    assert "at most 24 changes" in tools.change_setup(PLATE, [PULLED[0]] * 25).refused[0]["reason"]


def test_a_version_counts_the_setup_not_the_date_or_blank_rows():
    key = tools.setup_key(PLATE)
    assert tools.setup_key(with_form(PLATE, date="2027-01-01", notes="")) == key
    assert tools.setup_key(with_form(PLATE, element_size="2")) != key
    assert tools.setup_key(tools.change_setup(PLATE, PULLED[:1]).content) != key


def test_the_setups_a_version_counts_as_one_are_the_pages_too():
    """`tests/fixtures/setup-tools/setup-keys.json` is held by the page's `setupKey` too (`tests/model-versions.test.ts`): a setup the
    server counts as its last must be one the page does not send again."""
    held = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "setup-tools" / "setup-keys.json").read_text(encoding="utf-8"))
    for group in held["same"]:
        assert len({tools.setup_key(setup) for setup in group["setups"]}) == 1, group["name"]
    for group in held["different"]:
        assert len({tools.setup_key(setup) for setup in group["setups"]}) == len(group["setups"]), group["name"]
    assert len(held["same"]) == 5 and len(held["different"]) == 3


# ------------------------------------------------------------------------------------------- the routes

@pytest.fixture
def stateless(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    with TestClient(app, headers={"X-Anisotropy-Actor": "assistant"}) as client:
        yield client


def test_the_setup_is_read_and_changes_previewed_without_a_project(stateless):
    read = stateless.post("/v1/workspace/setup", json={"content": PLATE})
    assert read.status_code == 200 and read.json()["regions"][0]["name"] == "Edge-Bottom"
    preview = stateless.post("/v1/workspace/setup-changes", json={"content": PLATE, "changes": PULLED})
    body = preview.json()
    assert preview.status_code == 200 and body["ok"] and body["refused"] == []
    assert body["done"] == ["Edge-Bottom: fixed (encastre)", "Edge-Top: force of 10000 N along y (tension)"]
    assert body["setup"]["loaded"] == ["Edge-Top: force of 10000 N along y"] and body["digest"] == tools.content_digest(PLATE)
    assert body["project"] is None and body["version"] is None
    assert body["values"] == tools.plate_values(body["content"]) and body["values"]["loads"] == [{"region": "Edge-Top", "dof": 2, "total": 10000}]
    coupon = stateless.post("/v1/workspace/setup-changes", json={"content": COUPON, "changes": [{"action": "row", "key": "value", "value": 2}]}).json()
    assert coupon["ok"] and coupon["values"] is None  # a coupon's values are the tension screen's own
    refused = stateless.post("/v1/workspace/setup-changes", json={"content": PLATE, "changes": [{"action": "free", "region": "Edge-Top"}]}).json()
    assert not refused["ok"] and refused["content"] == PLATE


def test_the_mcp_servers_stand_in_holds_the_apis_own_answers(stateless):
    """`mcp-server/tests/fixtures/plate-setup.json` is what the MCP server's tests are answered with; it must be what the API answers."""
    held = json.loads((Path(__file__).resolve().parents[2] / "mcp-server" / "tests" / "fixtures" / "plate-setup.json").read_text(encoding="utf-8"))
    assert stateless.post("/v1/workspace/setup", json={"content": held["setup"]}).json() == held["read"]
    assert stateless.post("/v1/workspace/setup-changes", json={"content": held["setup"], "changes": held["changes"]}).json() == held["preview"]
    assert stateless.post("/v1/workspace/setup-changes", json={"content": held["setup"], "changes": held["refused_changes"]}).json() == held["refused"]


def test_the_routes_refuse_a_malformed_change(stateless):
    for change in ({"action": "hold", "region": "Edge-Top", "dofs": ["x"]}, {"action": "lift"}, {"action": "hold", "colour": "red"}):
        assert stateless.post("/v1/workspace/setup-changes", json={"content": PLATE, "changes": [change]}).status_code == 422
    assert stateless.post("/v1/workspace/setup-changes", json={"content": PLATE, "changes": []}).status_code == 422
    assert TestClient(app).post("/v1/workspace/setup", json={"content": PLATE}).status_code == 422  # no actor


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        yield client


def project(client, content: dict | None = None, kind: str = "fea") -> str:
    pid = str(uuid.uuid4())
    made = client.put(f"/v1/projects/{pid}", json={"kind": kind, "name": "Pulled plate", "content": PLATE if content is None else content})
    assert made.status_code == 201, made.text
    return pid


@needs_test_database
def test_a_change_is_previewed_then_applied_and_kept_as_a_version(recording):
    pid = project(recording)
    preview = recording.post(f"/v1/projects/{pid}/setup-changes", json={"changes": PULLED}).json()
    assert preview["ok"] and preview["version"] is None
    assert recording.get(f"/v1/projects/{pid}").json()["content"] == PLATE  # a preview keeps nothing
    applied = recording.post(f"/v1/projects/{pid}/setup-changes",
                             json={"changes": PULLED, "apply": True, "base": preview["digest"], "why": "fix the bottom and pull the top with 10 kN"})
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["project"]["content"]["plate"]["loads"] == [{"region": "Edge-Top", "kind": "force", "dof": 2, "total": "10000"}]
    assert body["version"] == {"n": 1, "at": body["version"]["at"], "by": "assistant", "why": "fix the bottom and pull the top with 10 kN",
                               "changes": body["done"], "form": PLATE["form"], "plate": body["project"]["content"]["plate"], "run": None}
    assert recording.get(f"/v1/projects/{pid}").json()["content"] == body["project"]["content"]
    again = recording.post(f"/v1/projects/{pid}/setup-changes", json={"changes": PULLED, "apply": True, "base": preview["digest"]})
    assert again.status_code == 409 and "changed since" in again.json()["detail"]  # the setup it was worked out on is gone


@needs_test_database
def test_an_applied_change_is_refused_with_its_reasons_or_without_a_base(recording):
    pid = project(recording)
    refused = recording.post(f"/v1/projects/{pid}/setup-changes", json={"changes": [{"action": "free", "region": "Edge-Top"}], "apply": True,
                                                                      "base": tools.content_digest(PLATE)})
    assert refused.status_code == 422 and refused.json()["detail"] == "change 1: nothing is held on Edge-Top"
    assert recording.post(f"/v1/projects/{pid}/setup-changes", json={"changes": PULLED, "apply": True}).status_code == 422
    assert recording.get(f"/v1/projects/{pid}/versions").json() == []
    laminate = project(recording, {"draft": {"system": "SI"}}, kind="laminate")
    assert recording.post(f"/v1/projects/{laminate}/setup-changes", json={"changes": PULLED}).status_code == 422


@needs_test_database
def test_versions_are_kept_per_project_numbered_and_marked_with_their_run(recording):
    pid = project(recording)
    first = recording.post(f"/v1/projects/{pid}/versions", json={"changes": ["The setup as it started"], **PLATE})
    assert first.status_code == 201 and first.json()["n"] == 1 and first.json()["by"] == "you" and first.json()["run"] is None
    same = recording.post(f"/v1/projects/{pid}/versions", json={"changes": ["nothing"], **with_form(PLATE, date="2027-01-01")})
    assert same.status_code == 200 and same.json()["n"] == 1  # the same setup is no new version
    second = recording.post(f"/v1/projects/{pid}/versions", json={"by": "assistant", "why": "use 1 mm elements",
                                                                  "changes": ["Element size (mm): blank → 1"], **with_form(PLATE, element_size="1")})
    assert second.status_code == 201 and second.json()["n"] == 2
    job = str(uuid.uuid4())
    marked = recording.put(f"/v1/projects/{pid}/versions/2/run", json={"job": job})
    assert marked.json()["run"] == {"job": job, "result": None}
    result = {"reaction": "10000 N", "displacement": "1.83 mm", "failure": "Holds, R = 1.709"}
    assert recording.put(f"/v1/projects/{pid}/versions/2/run", json={"job": job, "result": result}).json()["run"]["result"] == result
    assert recording.put(f"/v1/projects/{pid}/versions/9/run", json={"job": job}).status_code == 404
    listed = recording.get(f"/v1/projects/{pid}/versions").json()
    assert [(v["n"], v["by"], v["why"]) for v in listed] == [(1, "you", None), (2, "assistant", "use 1 mm elements")]
    assert [v["n"] for v in recording.get(f"/v1/projects/{pid}/versions", params={"limit": 1}).json()] == [2]
    other = {"X-Anisotropy-Actor": "test"}  # locally, a project is its actor's: another's versions are not found
    assert recording.get(f"/v1/projects/{pid}/versions", headers=other).status_code == 404
    assert recording.post(f"/v1/projects/{pid}/versions", json={"changes": [], **PLATE}, headers=other).status_code == 404
    assert recording.put(f"/v1/projects/{pid}/versions/1/run", json={"job": job}, headers=other).status_code == 404
    assert recording.post(f"/v1/projects/{pid}/setup-changes", json={"changes": PULLED}, headers=other).status_code == 404


@needs_test_database
def test_an_applied_change_follows_the_pages_versions(recording):
    pid = project(recording)
    recording.post(f"/v1/projects/{pid}/versions", json={"changes": ["The setup as it started"], **PLATE})
    applied = recording.post(f"/v1/projects/{pid}/setup-changes", json={"changes": PULLED, "apply": True, "base": tools.content_digest(PLATE)}).json()
    assert applied["version"]["n"] == 2
    page = recording.post(f"/v1/projects/{pid}/versions", json={"changes": ["Added: ..."], "form": applied["content"]["form"],
                                                                "plate": applied["content"]["plate"]})
    assert page.status_code == 200 and page.json()["n"] == 2  # the page settling the same setup adds nothing
