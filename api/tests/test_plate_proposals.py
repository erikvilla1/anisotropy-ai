"""A plate's supports and loads from a message and the place clicked (ADR-0101): the guard, the schema, what the model is shown, and the
endpoint with a stub in the model's place."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.assistant import PROPOSAL_SCHEMA, ClaudeAssistant
from anisotropy_api.main import app
from anisotropy_api.plate_proposals import DIRECTIONS, EDGE_NORMAL, PLATE_SYSTEM, REGION_KINDS, plate_guard, plate_schema, plate_view
from anisotropy_api.schemas import PLATE_REGION_KINDS

from test_proposals import COUPON_ROWS, StubClient

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded
REGIONS = [{"name": name, "kind": kind} for name, kind in REGION_KINDS.items() if not name.startswith("Tab-")]


def offer(here=(), **more):
    return {"regions": REGIONS, "here": list(here), "force_unit": "N", "stress_unit": "MPa", "held": [], "loaded": [], **more}


def support(region, directions, quote):
    return {"region": region, "directions": list(directions), "quote": quote}


def load(region, kind, value, unit, quote, direction=None, sense="as_signed"):
    return {"region": region, "kind": kind, "direction": direction, "sense": sense, "value": value, "unit": unit, "quote": quote}


def test_the_regions_and_their_kinds_are_the_forms_own():
    plate = json.loads((Path(__file__).parents[2] / "lib" / "coupon-form-definition.json").read_text())["plate"]
    edges, areas = [*plate["edges"], *plate["with_hole"]], [*plate["areas"], *plate["with_tabs"]]
    assert {**dict.fromkeys(edges, "edge"), **dict.fromkeys(areas, "area")} == REGION_KINDS == PLATE_REGION_KINDS
    assert {str(number): name for name, number in DIRECTIONS.items()}.keys() == plate["dofs"].keys()
    assert set(EDGE_NORMAL) == set(plate["edges"])


def test_the_founders_sentences_are_kept_from_the_click_and_the_words():
    """2026-11-16: "pick a face and say add a 10 kN load in tension here"; here the click is on the top edge."""
    message = "hold this edge and add a 10 kN load in tension here"
    kept = plate_guard({"supports": [support("Edge-Top", ["x", "y", "z"], "hold this edge")],
                        "loads": [load("Edge-Top", "force", "10", "kN", "a 10 kN load in tension here", sense="tension")]},
                       message, offer(here=["Face", "Edge-Top"]))
    assert kept.dropped == []
    assert kept.supports == [{"region": "Edge-Top", "dofs": [1, 2, 3], "quote": "hold this edge"}]
    assert kept.loads == [{"region": "Edge-Top", "kind": "force", "dof": 2, "value": "10000", "unit": "N", "written_value": "10",
                           "written_unit": "kN", "sense": "tension", "quote": "a 10 kN load in tension here"}]


@pytest.mark.parametrize("region, sense, dof, value", [
    ("Edge-Right", "tension", 1, "500"), ("Edge-Left", "tension", 1, "-500"), ("Edge-Top", "tension", 2, "500"), ("Edge-Bottom", "tension", 2, "-500"),
    ("Edge-Right", "compression", 1, "-500"), ("Edge-Left", "compression", 1, "500"), ("Edge-Top", "compression", 2, "-500"),
    ("Edge-Bottom", "compression", 2, "500"),
])
def test_tension_pulls_along_the_edges_outward_normal_whatever_sign_the_model_wrote(region, sense, dof, value):
    side = region[5:].lower()
    message = f"put 500 N in {sense} on the {side} edge"
    for written in ("500", "-500"):
        kept = plate_guard({"loads": [load(region, "force", written, "N", message, direction="z", sense=sense)]}, message, offer())
        assert [(entry["dof"], entry["value"]) for entry in kept.loads] == [(dof, value)] and kept.dropped == []


def test_a_named_region_needs_no_click_and_a_pointed_one_needs_the_click():
    message = "clamp the left edge, simply support the right side, press on the face with 0.01 MPa, and 200 N down at the hole"
    raw = {"supports": [support("Edge-Left", list(DIRECTIONS), "clamp the left edge"), support("Edge-Right", ["z"], "simply support the right side")],
           "loads": [load("Face", "pressure", "0.01", "MPa", "press on the face with 0.01 MPa"),
                     load("Hole", "force", "-200", "N", "200 N down at the hole", direction="z")]}
    kept = plate_guard(raw, message, offer())
    assert kept.dropped == []
    assert [(s["region"], s["dofs"]) for s in kept.supports] == [("Edge-Left", [1, 2, 3, 4, 5, 6]), ("Edge-Right", [3])]
    assert [(entry["region"], entry["kind"], entry["dof"], entry["value"], entry["unit"], entry["sense"]) for entry in kept.loads] == [
        ("Face", "pressure", None, "0.01", "MPa", None), ("Hole", "force", 3, "-200", "N", "as_signed")]
    pointed = {"supports": [support("Edge-Top", ["x", "y", "z"], "hold this")]}
    assert plate_guard(pointed, "hold this", offer(here=["Face", "Edge-Top"])).supports[0]["region"] == "Edge-Top"
    assert plate_guard(pointed, "hold this", offer()).dropped == [
        {"key": "support on Edge-Top", "reason": "the quoted words do not name Edge-Top, and it is not where you clicked"}]


@pytest.mark.parametrize("raw, reason", [
    ({"supports": [support("Box-1", ["z"], "hold the left edge")]}, "not a region on offer"),
    ({"supports": [support("Edge-Left", ["z"], "hold the left side")]}, "the quoted words are not in the message"),
    ({"supports": [support("Edge-Right", ["z"], "hold the left edge")]}, "the quoted words do not name Edge-Right, and it is not where you clicked"),
    ({"supports": [support("Tab-Bottom", ["z"], "hold the left edge")]}, "not a region on offer"),
    ({"supports": [support("Edge-Left", [], "hold the left edge")]}, "it names no direction a plate holds"),
    ({"supports": [support("Edge-Left", ["x", "up"], "hold the left edge")]}, "it names no direction a plate holds"),
    ({"loads": [load("Edge-Left", "pressure", "5", "MPa", "5 MPa on the left edge")]}, "a pressure acts on an area, and Edge-Left is an edge"),
    ({"loads": [load("Face", "force", "20", "N", "20 N on the face in tension", sense="tension")]},
     "tension has no one direction on Face: name the direction, x, y or z"),
    ({"loads": [load("Edge-Left", "force", "20", "N", "20 N on the left edge")]}, "a force needs a direction: x, y or z"),
    ({"loads": [load("Edge-Left", "force", "25", "N", "20 N on the left edge", direction="x")]}, "25 is not a number the quoted words write"),
    ({"loads": [load("Edge-Left", "force", "5", "MPa", "5 MPa on the left edge", direction="x")]}, "MPa is not a unit of the row, which is stated in N"),
    ({"loads": [load("Edge-Left", "force", "3", "kip", "3 kip on the left edge", direction="x")]},
     "kip belongs to US units (in, lbf, psi), and this coupon is stated in SI units (mm, N, MPa): give it in N, or switch the coupon's units"),
    ({"loads": [load("Edge-Left", "force", "0", "N", "0 N on the left edge", direction="x")]}, "a load of zero is no load"),
    ({"loads": [load("Edge-Left", "moment", "20", "N", "20 N on the left edge", direction="x")]}, "neither a force nor a pressure"),
])
def test_a_support_or_load_the_words_and_the_click_do_not_hold_is_dropped_with_its_reason(raw, reason):
    message = "hold the left edge; 20 N on the left edge; 5 MPa on the left edge; 3 kip on the left edge; 0 N on the left edge; 20 N on the face in tension"
    kept = plate_guard(raw, message, offer())
    assert kept.supports == [] and kept.loads == [] and [d["reason"] for d in kept.dropped] == [reason]


def test_a_region_held_twice_keeps_the_first_and_words_a_kept_entry_quotes_are_not_unread():
    message = "hold the left edge, fix the left edge in z, and the rest like before"
    kept = plate_guard({"supports": [support("Edge-Left", ["x", "y", "z"], "hold the left edge"), support("Edge-Left", ["z"], "fix the left edge in z")]},
                       message, offer())
    assert [s["dofs"] for s in kept.supports] == [[1, 2, 3]]
    assert kept.dropped == [{"key": "support on Edge-Left", "reason": "held twice; the first stands"}]
    unread = [{"quote": "Hold the left edge", "reason": "no_value"}, {"quote": "like before", "reason": "refers_back"}]
    assert kept.not_taken(unread) == [{"quote": "like before", "reason": "refers_back"}]


def test_the_schema_names_only_the_regions_on_offer_and_the_model_sees_no_value():
    schema = plate_schema(PROPOSAL_SCHEMA, ["Edge-Left", "Face"])
    assert "supports" not in PROPOSAL_SCHEMA["properties"] and schema["required"][-2:] == ["supports", "loads"]
    assert schema["properties"]["supports"]["items"]["properties"]["region"]["enum"] == ["Edge-Left", "Face"]
    assert schema["properties"]["loads"]["items"]["properties"]["region"]["enum"] == ["Edge-Left", "Face"]
    assert schema["properties"]["loads"]["items"]["properties"]["sense"]["enum"] == ["tension", "compression", "as_signed"]
    view = plate_view(offer(here=["Face"], held=["Edge-Left"], loaded=["Face"]))
    assert view == {"regions": REGIONS, "here": ["Face"], "force_unit": "N", "pressure_unit": "MPa", "held": ["Edge-Left"], "loaded": ["Face"]}
    assert "worked out from the edge" in PLATE_SYSTEM


REQUEST = {"product": "coupon", "message": "hold this edge and add a 10 kN load in tension here", "rows": COUPON_ROWS, "form": {"test": "plate"},
           "plate": offer(here=["Face", "Edge-Top"])}


def test_the_endpoint_offers_the_plate_to_the_model_and_returns_what_the_guard_keeps(monkeypatch):
    answer = {"proposals": [], "conditions": [], "question": None, "unread": [{"quote": "hold this edge", "reason": "no_value"}],
              "supports": [support("Edge-Top", ["x", "y", "z"], "hold this edge"), support("Edge-Left", ["z"], "hold this edge")],
              "loads": [load("Edge-Top", "force", "10", "kN", "a 10 kN load in tension here", sense="tension")]}
    stub = StubClient(json.dumps(answer))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = client.post("/v1/workspace/proposals", json=REQUEST).json()
    assert body["supports"] == [{"region": "Edge-Top", "dofs": [1, 2, 3], "quote": "hold this edge"}]
    assert [(entry["region"], entry["dof"], entry["value"], entry["unit"]) for entry in body["loads"]] == [("Edge-Top", 2, "10000", "N")]
    assert body["dropped"] == [{"key": "support on Edge-Left", "reason": "the quoted words do not name Edge-Left, and it is not where you clicked"}]
    assert body["unread"] == [] and body["proposals"] == []
    [call] = stub.calls
    seen = json.loads(call["messages"][0]["content"])
    assert seen["plate"]["here"] == ["Face", "Edge-Top"] and [r["name"] for r in seen["plate"]["regions"]] == [r["name"] for r in REGIONS]
    assert call["output_config"]["format"]["schema"]["properties"]["loads"]["items"]["properties"]["region"]["enum"] == [r["name"] for r in REGIONS]
    assert call["system"].endswith(PLATE_SYSTEM)
    # a message with no plate is read as before: the rows' schema, no plate in the view, no supports or loads in the answer
    plain = StubClient(json.dumps({"proposals": [], "conditions": [], "question": None, "unread": []}))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=plain), raising=False)
    rows_only = client.post("/v1/workspace/proposals", json={k: v for k, v in REQUEST.items() if k != "plate"}).json()
    assert rows_only["supports"] == [] and rows_only["loads"] == []
    assert plain.calls[0]["output_config"]["format"]["schema"] == PROPOSAL_SCHEMA and "plate" not in json.loads(plain.calls[0]["messages"][0]["content"])


@pytest.mark.parametrize("change, where", [
    ({"regions": [{"name": "Box-1", "kind": "area"}]}, "regions"),
    ({"regions": [{"name": "Edge-Left", "kind": "area"}]}, "Edge-Left is an edge"),
    ({"regions": [*REGIONS, REGIONS[0]]}, "offered once"),
    ({"here": ["Tab-Top"]}, "clicked and not offered"),
    ({"stress_unit": "psi"}, "one system"),
    ({"supports": [{"region": "Edge-Left", "dofs": [1]}]}, "supports"),
])
def test_a_malformed_plate_offer_is_refused(change, where):
    answer = client.post("/v1/workspace/proposals", json={**REQUEST, "plate": {**REQUEST["plate"], **change}})
    assert answer.status_code == 422 and where in answer.text
    wrong_product = client.post("/v1/workspace/proposals", json={**REQUEST, "product": "laminate"})
    assert wrong_product.status_code == 422 and "only a coupon" in wrong_product.text


@pytest.mark.parametrize("message, quote, model_wrote, dofs", [
    ("encastre the left edge", "encastre the left edge", ["x"], [1, 2, 3, 4, 5, 6]),
    ("pinned support on the right edge", "pinned support on the right edge", ["z"], [1, 2, 3]),
    ("XSYMM on the left edge", "XSYMM on the left edge", ["x", "y", "z"], [1, 5, 6]),
    ("apply a ysymm bc to the bottom edge", "ysymm bc to the bottom edge", ["y"], [2, 4, 6]),
    ("ZSYMM on the face", "ZSYMM on the face", ["z"], [3, 4, 5]),
    ("hold U1 and UR3 on the top edge", "hold U1 and UR3 on the top edge", ["x", "y", "z"], [1, 6]),
    ("BC on the bottom edge: U2 = 0", "BC on the bottom edge: U2", ["x"], [2]),
])
def test_abaqus_names_and_codes_fix_the_directions_whatever_the_model_wrote(message, quote, model_wrote, dofs):
    """ADR-0110: a named boundary condition or a direction code has one meaning, so the quoted words, not the model, set the directions."""
    region = {"left": "Edge-Left", "right": "Edge-Right", "bottom": "Edge-Bottom", "top": "Edge-Top", "face": "Face"}[
        next(side for side in ("left", "right", "bottom", "top", "face") if side in message.lower())]
    kept = plate_guard({"supports": [support(region, model_wrote, quote)]}, message, offer())
    assert kept.dropped == [] and kept.supports == [{"region": region, "dofs": dofs, "quote": quote}]


@pytest.mark.parametrize("message, region", [("fix the lefft edge", "Edge-Left"), ("hold the rigth edge", "Edge-Right"), ("clamp the botom edge", "Edge-Bottom"),
                                             ("fix the tpo edge", "Edge-Top")])
def test_a_side_typed_with_one_slip_still_names_its_edge(message, region):
    """ADR-0101 amendment 3: the first real-model run (2026-11-20) found "fix the lefft edge" read by the model and dropped by the guard."""
    kept = plate_guard({"supports": [support(region, ["x", "y", "z"], message)]}, message, offer())
    assert kept.dropped == [] and kept.supports[0]["region"] == region


@pytest.mark.parametrize("message, region", [("fix the lift edge", "Edge-Right"), ("fix the tip edge", "Edge-Top"), ("hold the bottom edge", "Edge-Top")])
def test_a_word_that_is_not_a_slip_of_the_side_names_no_edge(message, region):
    kept = plate_guard({"supports": [support(region, ["x", "y", "z"], message)]}, message, offer())
    assert kept.supports == [] and kept.dropped[0]["reason"].startswith("the quoted words do not name")


def test_pin_is_pinned():
    kept = plate_guard({"supports": [support("Hole", [], "pin the hole")]}, "pin the hole", offer())
    assert kept.dropped == [] and kept.supports == [{"region": "Hole", "dofs": [1, 2, 3], "quote": "pin the hole"}]


def test_a_named_condition_stands_even_when_the_model_names_no_direction():
    kept = plate_guard({"supports": [support("Edge-Left", [], "encastre the left edge")]}, "encastre the left edge", offer())
    assert kept.supports[0]["dofs"] == [1, 2, 3, 4, 5, 6] and kept.dropped == []


def test_a_roller_with_no_direction_written_is_dropped_and_one_with_a_direction_stands():
    dropped = plate_guard({"supports": [support("Edge-Right", ["z"], "a roller on the right edge")]}, "a roller on the right edge", offer())
    assert dropped.supports == [] and dropped.dropped == [{"key": "support on Edge-Right", "reason": "a roller holds one direction: say which, x, y or z"}]
    kept = plate_guard({"supports": [support("Edge-Right", ["z"], "a roller on the right edge in z")]}, "a roller on the right edge in z", offer())
    assert kept.supports == [{"region": "Edge-Right", "dofs": [3], "quote": "a roller on the right edge in z"}]


@pytest.mark.parametrize("code, dof", [("CF1", 1), ("CF2", 2), ("cf3", 3)])
def test_cf1_to_cf3_point_a_force_along_x_y_z_whatever_the_model_wrote(code, dof):
    message = f"{code} = -500 N on the top edge"
    for direction, sense in (("z", "as_signed"), (None, "tension")):
        kept = plate_guard({"loads": [load("Edge-Top", "force", "-500", "N", message, direction=direction, sense=sense)]}, message, offer())
        assert kept.dropped == [] and [(entry["dof"], entry["value"], entry["sense"]) for entry in kept.loads] == [(dof, "-500", "as_signed")]


def test_the_plate_prompt_says_abaqus_words_with_the_meanings_the_guard_holds():
    for words in ("boundary condition (BC) is a support", "encastre is all six", "pinned (or pin) is x, y and z", "XSYMM is x, tilt_y and turn_z",
                  "YSYMM is y, tilt_x and turn_z", "ZSYMM is z, tilt_x and tilt_y", "CF1, CF2 and CF3 are a force along x, y and z"):
        assert words in PLATE_SYSTEM
