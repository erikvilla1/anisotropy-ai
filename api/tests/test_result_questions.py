"""A model reads a loose question about a result into a fixed request (ADR-0100): what the model is shown, the schema it answers in, the
guard on each way a reading can go wrong, the Claude writer behind a stand-in client, and the endpoint. Nothing here calls a model, and
nothing here holds a value of a result."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.assistant import QUESTION_SYSTEM, ClaudeAssistant, TemplateAssistant
from anisotropy_api.main import app
from anisotropy_api.result_questions import QUANTITIES, model_view, question_guard, question_schema
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

ANGLES = [45, 0, -45, 90, 90, -45, 0, 45]
PLIES = [{"ply": i + 1, "angle": float(a)} for i, a in enumerate(ANGLES)]
OFFERED = list(QUANTITIES)


def view_of(message, gauge=True, picked=False):
    return model_view(message, OFFERED, PLIES, gauge, picked)


def answer(kind="extreme", quantities=("S12",), plies=(), element=None, here=False, sense="magnitude", region="default", question=None):
    return {"kind": kind, "quantities": list(quantities), "plies": list(plies), "element": element, "here": here, "sense": sense, "region": region,
            "question": question}


def kept(message, raw, **offer):
    return question_guard(raw, message, view_of(message, **offer))


# --------------------------------------------------------------------------------------------- what the model sees and answers in

def test_the_model_is_shown_the_message_and_the_offer_and_no_result():
    view = view_of("where is the shear highest?", picked=True)
    assert set(view) == {"message", "quantities", "plies", "regions", "element_clicked"}
    assert [q["key"] for q in view["quantities"]] == OFFERED and all(q["words"] for q in view["quantities"])
    assert view["plies"][1] == {"ply": 2, "angle": 0.0} and view["element_clicked"] is True
    assert [r["key"] for r in view["regions"]] == ["default", "gauge", "whole"]
    assert [r["key"] for r in view_of("x", gauge=False)["regions"]] == ["default", "whole"]  # no gauge section, none on offer


def test_the_schema_holds_names_on_offer_and_whole_numbers_only():
    schema = question_schema(["S11", "E22"], ["default", "whole"])
    properties = schema["properties"]
    assert schema["additionalProperties"] is False and sorted(schema["required"]) == sorted(properties)
    assert properties["quantities"]["items"]["enum"] == ["S11", "E22"] and properties["region"]["enum"] == ["default", "whole"]
    assert properties["plies"]["items"] == {"type": "integer"} and properties["kind"]["enum"] == ["values", "extreme", "failure", "none"]
    # nowhere a decimal number or free text but the question back, which the guard reads
    assert [name for name, p in properties.items() if p.get("type") == "number"] == []
    assert [name for name, p in properties.items() if p.get("type") == "string" and "enum" not in p] == []


# --------------------------------------------------------------------------------------------- the guard

def test_a_reading_inside_the_offer_is_kept_in_the_offers_order():
    read = kept("wher is teh shear highest in the gage?", answer(quantities=("S12",), region="gauge"))
    assert read.request == {"kind": "extreme", "quantities": ["S12"], "plies": [], "element": None, "here": False, "sense": "magnitude", "region": "gauge"}
    assert read.dropped == [] and read.question is None
    load = kept("which ply carries the most load?", answer(quantities=("S11",)))
    assert load.request["quantities"] == ["S11"] and load.request["region"] == "default"
    compare = kept("compare the 0° and 90° plies", answer(quantities=("S12", "S11", "S22"), plies=(7, 2, 4, 5, 2), sense="magnitude"))
    assert compare.request["quantities"] == ["S11", "S22", "S12"] and compare.request["plies"] == [2, 4, 5, 7]
    outer = kept("how stressed are the outer plies along the fibres?", answer(quantities=("S11",), plies=(1, 8)))
    assert outer.request["plies"] == [1, 8], "a ply named by its position needs no number in the message"


def test_an_element_is_kept_only_when_the_message_writes_it_and_here_only_without_one():
    at = kept("transvers strain in layer 3 at elem 40 please", answer(kind="values", quantities=("E22",), plies=(3,), element=40, sense=None))
    assert at.request == {"kind": "values", "quantities": ["E22"], "plies": [3], "element": 40, "here": False, "sense": None, "region": "default"}
    here = kept("and the fibre stress right here?", answer(kind="values", quantities=("S11",), here=True, sense=None), picked=True)
    assert here.request["here"] is True and here.request["element"] is None
    both = kept("stress at element 12 here", answer(kind="values", quantities=("S11",), element=12, here=True, sense=None))
    assert both.request["element"] == 12 and both.request["here"] is False
    invented = kept("stress at the middle of the coupon", answer(kind="values", quantities=("S11",), element=125, sense=None))
    assert invented.request is None and invented.dropped == ["the element named is not a number the message writes"]


@pytest.mark.parametrize("raw, reason", [
    (answer(kind="summary"), "not a kind of request"),
    (answer(quantities=()), "no quantity on offer is named"),
    (answer(quantities=("S12", "S33")), "not on offer"),
    (answer(plies=(9,)), "plies do not hold"),
    (answer(plies=(0,)), "plies do not hold"),
    (answer(plies=(2.5,)), "plies do not hold"),
    (answer(plies=(True,)), "plies do not hold"),
    (answer(kind="values", element=-3, sense=None), "not a number the message writes"),
    (answer(kind="values", element="12", sense=None), "not a number the message writes"),
    (answer(sense=None), "names no end"),
    (answer(sense="average"), "names no end"),
    (answer(region="Tab-Top"), "not a region on offer"),
])
def test_a_reading_outside_the_offer_is_dropped_with_its_reason(raw, reason):
    read = kept("where is the shear highest?", raw)
    assert read.request is None and len(read.dropped) == 1 and reason in read.dropped[0]


def test_the_gauge_section_is_a_region_only_where_the_model_has_one():
    assert kept("largest shear in the gauge", answer(region="gauge"), gauge=False).request is None
    assert kept("largest shear in the gauge", answer(region="gauge"), gauge=True).request["region"] == "gauge"


def test_none_is_no_request_and_a_question_back_may_hold_only_the_messages_numbers():
    setup = kept("make it [0/90]2s", answer(kind="none", quantities=(), sense=None))
    assert setup.request is None and setup.dropped == [] and setup.question is None
    unclear = kept("what about ply 4?", answer(kind="none", quantities=(), sense=None, question="Which quantity in ply 4: stress or strain?"))
    assert unclear.request is None and unclear.question == "Which quantity in ply 4: stress or strain?"
    stray = kept("what about ply 4?", answer(kind="none", quantities=(), sense=None, question="Do you mean the 1182 MPa in ply 2?"))
    assert stray.question is None and "numbers the message does not" in stray.dropped[0] and "1182" in stray.dropped[0]
    assert kept("x", answer(kind="none", quantities=(), sense=None, question="why " * 200)).dropped == ["the question back is too long"]


def test_a_question_of_failure_is_kept_as_its_kind_alone_whatever_else_the_model_wrote():
    """ADR-0100 amendment 1: which ply fails first is the package's own answer, so the request names nothing; a quantity, a ply, an
    element or a region the model wrote beside it does not go with it."""
    bare = {"kind": "failure", "quantities": [], "plies": [], "element": None, "here": False, "sense": None, "region": "default"}
    asked = kept("what is the the ply that fails", answer(kind="failure", quantities=(), sense=None))
    assert asked.request == bare and asked.dropped == [] and asked.question is None
    loaded = kept("which layer goes first", answer(kind="failure", quantities=("S11", "S22"), plies=(4, 99), element=120, here=True, sense="magnitude", region="whole"))
    assert loaded.request == bare and loaded.dropped == []
    assert "'failure'" in QUESTION_SYSTEM and "never an 'extreme'" in QUESTION_SYSTEM


def test_the_endpoint_returns_a_question_of_failure(monkeypatch):
    stub = StubClient(json.dumps(answer(kind="failure", quantities=(), sense=None)))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = client.post("/v1/workspace/result-questions", json={**REQUEST, "message": "which layer goes first"}).json()
    assert body["request"] == {"kind": "failure", "quantities": [], "plies": [], "element": None, "here": False, "sense": None, "region": "default"}
    assert body["dropped"] == [] and body["writer"] == "anthropic"


# --------------------------------------------------------------------------------------------- the writers

class StubClient:
    """What the Claude writer calls: `client.beta.messages.create(...)`; answers with the text given, or with a stop reason."""

    def __init__(self, text="", stop_reason="end_turn"):
        self.calls = []
        reply = SimpleNamespace(stop_reason=stop_reason, model="claude-stub", content=[SimpleNamespace(type="text", text=text)])
        outer = self

        class Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return reply

        self.beta = SimpleNamespace(messages=Messages())


def test_the_claude_writer_asks_in_the_schema_and_returns_its_answer_unjudged():
    raw = answer(quantities=("S12",))
    stub = StubClient(json.dumps(raw))
    view = view_of("where is the shear highest?")
    schema = question_schema(OFFERED, ["default", "gauge", "whole"])
    reading = ClaudeAssistant("claude-opus-5-5", client=stub).read_question(view, schema)
    assert reading.raw == raw and reading.writer == "anthropic" and reading.model == "claude-opus-5-5" and reading.reason is None
    [call] = stub.calls
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
    assert call["system"] == QUESTION_SYSTEM and "never write a value of a result" in call["system"] and call["max_tokens"] == 1000
    assert json.loads(call["messages"][0]["content"]) == view


@pytest.mark.parametrize("stub, reason", [
    (StubClient("", stop_reason="refusal"), "declined"),
    (StubClient('{"kind": ', stop_reason="max_tokens"), "cut short"),
    (StubClient("The shear is highest in ply 1."), "not the JSON asked for"),
])
def test_a_model_that_does_not_answer_in_the_schema_reads_nothing(stub, reason):
    reading = ClaudeAssistant("m", client=stub).read_question(view_of("x"), question_schema(OFFERED, ["default"]))
    assert reading.raw is None and reading.writer == "template" and reason in reading.reason and "stands" not in reading.reason


def test_the_template_reads_nothing():
    assert TemplateAssistant().read_question(view_of("max s11"), {}).raw is None


# --------------------------------------------------------------------------------------------- the endpoint

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded
REQUEST = {"message": "which ply carries the most load?", "quantities": OFFERED, "plies": PLIES, "gauge": True, "picked": False}


def test_with_no_model_nothing_is_read(monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    body = client.post("/v1/workspace/result-questions", json=REQUEST).json()
    assert body == {"run_id": None, "writer": "template", "model": None, "request": None, "question": None, "dropped": [], "reason": None}


def test_the_endpoint_returns_the_request_the_guard_keeps_and_the_model_saw_the_offer_alone(monkeypatch):
    stub = StubClient(json.dumps(answer(quantities=("S11",), sense="magnitude")))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = client.post("/v1/workspace/result-questions", json=REQUEST).json()
    assert body["writer"] == "anthropic" and body["model"] == "claude-opus-5-5" and body["dropped"] == [] and body["question"] is None
    assert body["request"] == {"kind": "extreme", "quantities": ["S11"], "plies": [], "element": None, "here": False, "sense": "magnitude", "region": "default"}
    seen = json.loads(stub.calls[0]["messages"][0]["content"])
    assert seen == view_of(REQUEST["message"])
    assert stub.calls[0]["output_config"]["format"]["schema"]["properties"]["region"]["enum"] == ["default", "gauge", "whole"]


def test_a_reading_the_guard_drops_comes_back_with_its_reason_and_no_request(monkeypatch):
    stub = StubClient(json.dumps(answer(kind="values", quantities=("S11",), element=125, sense=None)))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("m", client=stub), raising=False)
    body = client.post("/v1/workspace/result-questions", json={**REQUEST, "message": "stress in the middle?"}).json()
    assert body["request"] is None and body["dropped"] == ["the element named is not a number the message writes"]
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("m", client=StubClient("", stop_reason="refusal")), raising=False)
    declined = client.post("/v1/workspace/result-questions", json=REQUEST).json()
    assert declined["writer"] == "template" and declined["request"] is None and "declined" in declined["reason"]


@pytest.mark.parametrize("change, where", [
    ({"message": ""}, "message"),
    ({"quantities": ["S11", "S33"]}, "quantities"),
    ({"quantities": ["S11", "S11"]}, "offered once"),
    ({"quantities": []}, "quantities"),
    ({"plies": [{"ply": 2, "angle": 0.0}]}, "numbered from 1"),
    ({"plies": []}, "plies"),
    ({"picked": "yes"}, "picked"),
    ({"results": {"S11": [1182.0]}}, "results"),
])
def test_a_malformed_offer_is_refused_and_a_result_cannot_be_sent(change, where, monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    refused = client.post("/v1/workspace/result-questions", json={**REQUEST, **change})
    assert refused.status_code == 422 and where in json.dumps(refused.json())
    assert TestClient(app).post("/v1/workspace/result-questions", json=REQUEST).status_code == 422  # the actor is required


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        yield recorded


@needs_test_database
def test_a_reading_is_recorded_with_the_model_that_read_it(recording, monkeypatch):
    stub = StubClient(json.dumps(answer(quantities=("S11",))))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = recording.post("/v1/workspace/result-questions", json=REQUEST).json()
    run = recording.get(f"/v1/runs/{body['run_id']}").json()
    assert run["endpoint"] == "/v1/workspace/result-questions" and run["inputs"]["message"] == REQUEST["message"]
    assert run["llm_provider"] == "anthropic" and run["llm_model_version"] == "claude-opus-5-5"
    assert run["response"]["request"]["quantities"] == ["S11"]
