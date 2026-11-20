"""A question asked in the FEA section before anything is set up (ADR-0124): what the model is shown, the schema it answers in, the guard
on its answer and on the kind of work it names, the Claude writer behind a stand-in client, and the endpoint on our own theory pages.
Nothing here calls a model."""

import json

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.assistant import GENERAL_SYSTEM, ClaudeAssistant, TemplateAssistant
from anisotropy_api.general_answers import NONE, general_guard, general_schema, general_view
from anisotropy_api.main import app
from anisotropy_api.result_answers import MAX_ANSWER, SECTIONS_SHOWN
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE
from anisotropy_api.theory import Section, find

from conftest import TEST_URL, needs_test_database
from test_result_answers import StubClient

SHELL = Section("fea:8-shell", "fea", "Finite element theory", "8. The flat shell", "A shell element carries bending.\n\n<!-- code: shell_stiffness -->\n\nIt has four nodes.")
FAILURE = Section("engine:5-failure", "engine", "Laminate theory", "5. Failure", "Tsai-Hill combines the stresses.")
FOUND = [SHELL, FAILURE]
QUESTION = "what is a shell element?"
GOOD = "A shell element is a flat piece of the model that carries bending as well as stretching, with its stiffness from the laminate."


def raw(answer=GOOD, sections=("fea:8-shell",), covered=True, start=NONE):
    return {"answer": answer, "sections": list(sections), "covered": covered, "start": start}


# --------------------------------------------------------------------------------------------- what the model sees and answers in

def test_the_model_is_shown_the_question_the_sections_and_the_kinds_offered_and_nothing_else():
    view = general_view(QUESTION, FOUND, ["coupon"])
    assert set(view) == {"question", "sections", "kinds"} and view["question"] == QUESTION
    assert view["sections"][0] == {"id": "fea:8-shell", "from": "Finite element theory, 8. The flat shell",
                                   "text": "A shell element carries bending.\n\nIt has four nodes."}  # no code marker
    assert [k["id"] for k in view["kinds"]] == ["coupon"] and "coupon" in view["kinds"][0]["is"]


def test_the_schema_holds_the_answer_the_sections_shown_and_a_kind_offered_or_none():
    schema = general_schema(["a", "b"], ["coupon"])
    assert schema["additionalProperties"] is False and schema["required"] == ["answer", "covered", "sections", "start"]
    assert schema["properties"]["sections"]["items"]["enum"] == ["a", "b"] and schema["properties"]["start"]["enum"] == ["coupon", NONE]
    bare = general_schema([], [])
    assert "sections" not in bare["properties"] and "start" not in bare["properties"]  # nothing found, nothing offered: neither is named


# --------------------------------------------------------------------------------------------- the guard

def test_an_answer_with_no_number_of_its_own_stands_with_the_sections_it_names():
    kept = general_guard(raw(), QUESTION, FOUND, ["coupon"])
    assert kept.prose == (GOOD,) and kept.sources == (SHELL,) and kept.covered and not kept.withheld and kept.start is None
    asked = general_guard(raw("A mesh of 4 elements across is coarse for a hole."), "is 4 elements across enough?", FOUND, [])
    assert asked.prose and not asked.withheld  # a number the engineer wrote may be said back


@pytest.mark.parametrize("answer", [
    "In a tension coupon the 90-degree ply usually cracks first, across its fibres.",
    "The 0° plies carry most of the load and the ±45° plies the shear.",
    "A -45 degree ply mirrors a 45 degree one.",
])
def test_a_ply_named_by_its_angle_stands_in_an_answer_with_no_result(answer):
    # "explain first ply failure" was set aside on the fourth real run (2026-11-20) for naming the 90-degree ply: no value, a kind of ply
    kept = general_guard(raw(answer), "explain first ply failure", FOUND, [])
    assert kept.prose and not kept.withheld


@pytest.mark.parametrize("answer, offending", [
    ("A shell element has 4 nodes and 5 degrees of freedom at each.", "4"),  # a number of the theory pages is said in words, never copied
    ("Refine until the answer moves by less than 2 %.", "2"),
    ("The 90-degree ply fails at 60 MPa across its fibres.", "60"),  # the ply's angle is read past, a value is not
    ("Turn the fibres 37 degrees off the load.", "37"),  # only the angles a layup is written in
])
def test_an_answer_with_a_number_not_in_the_question_is_set_aside(answer, offending):
    kept = general_guard(raw(answer), QUESTION, FOUND, ["coupon"])
    assert kept.prose == () and kept.withheld and kept.sources == () and offending in kept.reason and "not in the question" in kept.reason


def test_the_kind_named_stands_only_when_offered_and_whatever_becomes_of_the_text():
    assert general_guard(raw(start="coupon"), "how do I test a coupon?", FOUND, ["coupon"]).start == "coupon"
    assert general_guard(raw(start="wing"), "start a wing", FOUND, ["coupon"]).start is None  # not offered
    assert general_guard(raw(start=NONE), QUESTION, FOUND, ["coupon"]).start is None
    withheld = general_guard(raw("Test 3 coupons at 2 mm/min.", start="coupon"), "how do I test a coupon?", FOUND, ["coupon"])
    assert withheld.withheld and withheld.prose == () and withheld.start == "coupon"


def test_a_section_not_shown_is_dropped_and_covered_needs_one_that_was():
    stray = general_guard(raw(sections=("engine:9-micromechanics",)), QUESTION, FOUND, [])
    assert stray.prose == (GOOD,) and stray.sources == () and stray.covered is False
    assert general_guard({"answer": GOOD, "covered": True}, QUESTION, [], []).covered is False  # no section found, none named


@pytest.mark.parametrize("answer, reason", [("", "no text"), (None, "no text"), ("word " * (MAX_ANSWER // 5 + 1), "longer")])
def test_an_empty_or_overlong_answer_is_no_answer(answer, reason):
    kept = general_guard(raw(answer), QUESTION, FOUND, [])
    assert kept.prose == () and reason in kept.reason


# --------------------------------------------------------------------------------------------- the Claude writer, behind a stand-in

def test_the_claude_writer_asks_in_the_schema_with_its_own_instructions_and_returns_the_answer_unjudged():
    stub = StubClient(json.dumps(raw()))
    view, schema = general_view(QUESTION, FOUND, ["coupon"]), general_schema([s.id for s in FOUND], ["coupon"])
    reading = ClaudeAssistant("claude-opus-5-5", client=stub).answer_general(view, schema)
    assert reading.raw == raw() and reading.writer == "anthropic" and reading.model == "claude-opus-5-5"
    [call] = stub.calls
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
    assert call["system"] == GENERAL_SYSTEM and "before any model is set up" in call["system"] and "never mention a language model" in call["system"]
    assert json.loads(call["messages"][0]["content"]) == view
    assert reading.call is None or reading.call.feature == "answer_question"  # billed as the one feature of questions from the theory pages


def test_the_template_writes_no_answer():
    assert TemplateAssistant().answer_general({}, {}).raw is None


# --------------------------------------------------------------------------------------------- the endpoint, on our own theory pages

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded
ASKED = {"question": "what is a shell element?", "kinds": ["coupon"]}
PAGES = [section for section, _ in find(ASKED["question"], limit=SECTIONS_SHOWN)]


def test_the_question_finds_the_shell_sections_of_our_own_pages():
    assert len(PAGES) == SECTIONS_SHOWN and all(section.id.startswith("fea:8-") for section in PAGES)


def test_with_no_model_no_answer_is_written_and_the_sections_found_are_named(monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    body = client.post("/v1/workspace/questions", json=ASKED).json()
    assert body["writer"] == "template" and body["model"] is None and body["prose"] == [] and body["covered"] is False and body["start"] is None
    assert [s["id"] for s in body["sources"]] == [s.id for s in PAGES] and body["run_id"] is None


def test_the_endpoint_returns_the_answer_the_guard_keeps_and_the_kind_named(monkeypatch):
    first = PAGES[0].id
    stub = StubClient(json.dumps(raw(sections=(first,), start="coupon")))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = client.post("/v1/workspace/questions", json={**ASKED, "kinds": ["coupon", "coupon"]}).json()
    assert body["writer"] == "anthropic" and body["prose"] == [GOOD] and body["covered"] is True and body["start"] == "coupon"
    assert [s["id"] for s in body["sources"]] == [first]
    assert json.loads(stub.calls[0]["messages"][0]["content"]) == general_view(ASKED["question"], PAGES, ["coupon"])  # each kind once
    assert stub.calls[0]["output_config"]["format"]["schema"]["properties"]["start"]["enum"] == ["coupon", NONE]


def test_an_answer_the_guard_sets_aside_comes_back_as_the_sections_found(monkeypatch):
    stub = StubClient(json.dumps(raw("A shell has 4 nodes.", start="coupon")))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("m", client=stub), raising=False)
    body = client.post("/v1/workspace/questions", json=ASKED).json()
    assert body["prose"] == [] and body["withheld"] is True and body["writer"] == "template" and body["start"] == "coupon"
    assert [s["id"] for s in body["sources"]] == [s.id for s in PAGES]


@pytest.mark.parametrize("change, where", [
    ({"question": ""}, "question"),
    ({"question": "x" * 2001}, "question"),
    ({"kinds": ["laminate"]}, "kinds"),
    ({"facts": {"a": 1}}, "facts"),
])
def test_a_malformed_request_is_refused(change, where, monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    refused = client.post("/v1/workspace/questions", json={**ASKED, **change})
    assert refused.status_code == 422 and where in json.dumps(refused.json())
    assert TestClient(app).post("/v1/workspace/questions", json=ASKED).status_code == 422  # the actor is required


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        yield recorded


@needs_test_database
def test_a_question_is_recorded_with_the_kinds_offered_and_the_model(recording, monkeypatch):
    stub = StubClient(json.dumps(raw(sections=(PAGES[0].id,))))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = recording.post("/v1/workspace/questions", json=ASKED).json()
    run = recording.get(f"/v1/runs/{body['run_id']}").json()
    assert run["endpoint"] == "/v1/workspace/questions" and run["inputs"] == ASKED
    assert run["llm_provider"] == "anthropic" and run["llm_model_version"] == "claude-opus-5-5" and run["response"]["prose"] == [GOOD]
