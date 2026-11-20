"""A question about a result answered in words (ADR-0102): what the model is shown, the schema it answers in, the guard on its answer,
the Claude writer behind a stand-in client, and the endpoint on the public example coupon's fact sheet with our own theory pages.
Nothing here calls a model."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.assistant import ANSWER_SYSTEM, ClaudeAssistant, TemplateAssistant, model_view_of_facts
from anisotropy_api.main import app
from anisotropy_api.result_answers import MAX_ANSWER, SECTIONS_SHOWN, answer_guard, answer_schema, answer_view
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE
from anisotropy_api.theory import Section, find

from conftest import TEST_URL, needs_test_database

FACTS = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "studio" / "explanation.json").read_text(encoding="utf-8"))["facts"]
SEEN = model_view_of_facts(FACTS)
FAILURE = Section("engine:5-failure", "engine", "Laminate theory", "5. Failure", "Tsai-Hill combines the stresses.\n\n<!-- code: tsai_hill_index -->\n\nThe index reaches one at failure.")
PLIES = Section("fea:6-ply-stresses-in-material-axes", "fea", "Finite element theory", "6. Ply stresses in material axes", "Every ply carries the element's strain.")
FOUND = [FAILURE, PLIES]
QUESTION = "why does ply 4 fail first?"
GOOD = "Ply 4 (90 degrees) fails first because its stress across the fibres, 60.6 MPa, reaches the matrix strength before any fibre does, at 1.032 times the applied loading."


def raw(answer=GOOD, sections=("engine:5-failure",), covered=True):
    return {"answer": answer, "sections": list(sections), "covered": covered}


# --------------------------------------------------------------------------------------------- what the model sees and answers in

def test_the_model_is_shown_the_question_the_fact_sheet_and_the_sections_without_the_codes_markers():
    view = answer_view(QUESTION, SEEN, FOUND)
    assert set(view) == {"question", "facts", "sections"} and view["question"] == QUESTION and view["facts"] == SEEN
    assert "designation" not in view["facts"] and view["facts"]["tsai_hill_factor"] == 1.032  # the record's name stays here (audit fea-run-8)
    assert view["sections"][0] == {"id": "engine:5-failure", "from": "Laminate theory, 5. Failure",
                                   "text": "Tsai-Hill combines the stresses.\n\nThe index reaches one at failure."}
    assert [s["id"] for s in view["sections"]] == ["engine:5-failure", "fea:6-ply-stresses-in-material-axes"]


def test_the_schema_holds_the_answer_whether_it_is_covered_and_sections_from_those_shown():
    schema = answer_schema(["a", "b"])
    assert schema["additionalProperties"] is False and schema["required"] == ["answer", "covered", "sections"]
    assert schema["properties"]["sections"]["items"]["enum"] == ["a", "b"] and schema["properties"]["covered"] == {"type": "boolean"}
    assert "sections" not in answer_schema([])["properties"]  # no section found, none to name


# --------------------------------------------------------------------------------------------- the guard

def test_an_answer_whose_numbers_are_the_results_or_the_questions_stands_with_the_sections_it_names():
    kept = answer_guard(raw(), QUESTION, SEEN, FOUND)
    assert kept.prose == (GOOD,) and kept.sources == (FAILURE,) and kept.covered and not kept.withheld and kept.reason is None
    both = answer_guard(raw(sections=("fea:6-ply-stresses-in-material-axes", "engine:5-failure")), QUESTION, SEEN, FOUND)
    assert both.sources == (FAILURE, PLIES)  # in the order shown
    asked = answer_guard(raw("At 2.5 times the loading the question is a different one."), "what happens at 2.5 times the loading?", SEEN, FOUND)
    assert asked.prose and not asked.withheld  # a number the engineer wrote may be said back


@pytest.mark.parametrize("answer, offending", [
    ("Ply 4 fails first at about 1.03 times the loading, some 3 % above it.", "3"),  # a rounding passes at its precision; a new number does not
    ("The 90 degree ply carries 61 MPa across the fibres, a fifth of 300 MPa.", "300"),
    ("The matrix strength of 73 MPa is reached first.", "73"),
])
def test_an_answer_with_a_number_of_its_own_is_set_aside(answer, offending):
    kept = answer_guard(raw(answer), QUESTION, SEEN, FOUND)
    assert kept.prose == () and kept.withheld and kept.sources == () and offending in kept.reason and "neither the results nor the question" in kept.reason


def test_a_section_that_was_not_shown_is_dropped_and_covered_needs_one_that_was():
    stray = answer_guard(raw(sections=("engine:9-micromechanics",)), QUESTION, SEEN, FOUND)
    assert stray.prose == (GOOD,) and stray.sources == () and stray.covered is False
    uncovered = answer_guard(raw("The results show ply 4 in compression along its fibres. The theory pages do not explain this yet.", covered=False), QUESTION, SEEN, FOUND)
    assert len(uncovered.prose) == 2 and uncovered.covered is False and uncovered.sources == ()  # nothing is cited for a reason not given
    assert answer_guard({"answer": GOOD, "covered": True}, QUESTION, SEEN, []).covered is False  # no section found, none named


@pytest.mark.parametrize("answer, reason", [("", "no text"), ("   ", "no text"), (None, "no text"), ("word " * (MAX_ANSWER // 5 + 1), "longer")])
def test_an_empty_or_overlong_answer_is_no_answer(answer, reason):
    kept = answer_guard(raw(answer), QUESTION, SEEN, FOUND)
    assert kept.prose == () and reason in kept.reason


# --------------------------------------------------------------------------------------------- the Claude writer, behind a stand-in

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
    stub = StubClient(json.dumps(raw()))
    view, schema = answer_view(QUESTION, SEEN, FOUND), answer_schema([s.id for s in FOUND])
    reading = ClaudeAssistant("claude-opus-5-5", client=stub).answer_question(view, schema)
    assert reading.raw == raw() and reading.writer == "anthropic" and reading.model == "claude-opus-5-5" and reading.reason is None
    [call] = stub.calls
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
    assert call["system"] == ANSWER_SYSTEM and "give no reason of your own" in call["system"] and "never mention a language model" in call["system"]
    assert "at most three short, plain sentences of at most 25 words" in call["system"] and "The first sentence is the answer on its own in at most nine words" in call["system"]
    assert json.loads(call["messages"][0]["content"]) == view


def test_a_model_that_does_not_answer_writes_nothing_and_the_template_writes_nothing():
    declined = ClaudeAssistant("m", client=StubClient("", stop_reason="refusal")).answer_question({}, answer_schema([]))
    assert declined.raw is None and declined.writer == "template" and "declined" in declined.reason
    assert ClaudeAssistant("m", client=StubClient("Ply 4 fails first.")).answer_question({}, answer_schema([])).reason == "the model's answer was not the JSON asked for"
    assert TemplateAssistant().answer_question({}, {}).raw is None


# --------------------------------------------------------------------------------------------- the endpoint, on our own theory pages

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded
ASKED = {"question": "what is the Tsai-Hill failure index, and why does ply 4 fail first by it?", "facts": FACTS}
PAGES = [section for section, _ in find(ASKED["question"], limit=SECTIONS_SHOWN)]


def test_the_question_finds_the_failure_section_of_our_own_pages_and_a_reason():
    cited = {section.id: section.cited() for section in PAGES}  # which of the three is first moves as the pages are edited
    assert len(PAGES) == SECTIONS_SHOWN and cited["engine:5-failure"] == "Laminate theory, 5. Failure"
    assert "Reasons behind a result, Why the failure criteria give different factors" in cited.values()


def test_with_no_model_no_answer_is_written_and_the_sections_found_are_named(monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    body = client.post("/v1/workspace/result-answers", json=ASKED).json()
    assert body["writer"] == "template" and body["model"] is None and body["prose"] == [] and body["covered"] is False
    assert body["withheld"] is False and body["reason"] is None and body["run_id"] is None
    assert {"id": "engine:5-failure", "document": "Laminate theory", "title": "5. Failure"} in body["sources"]
    assert [s["id"] for s in body["sources"]] == [s.id for s in PAGES]


def test_the_endpoint_returns_the_answer_the_guard_keeps_with_its_sections_and_the_model_saw_no_name(monkeypatch):
    stub = StubClient(json.dumps(raw(sections=("engine:5-failure",))))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = client.post("/v1/workspace/result-answers", json=ASKED).json()
    assert body["writer"] == "anthropic" and body["model"] == "claude-opus-5-5" and body["prose"] == [GOOD] and body["covered"] is True
    assert body["sources"] == [{"id": "engine:5-failure", "document": "Laminate theory", "title": "5. Failure"}] and body["withheld"] is False
    seen = json.loads(stub.calls[0]["messages"][0]["content"])
    assert seen == answer_view(ASKED["question"], SEEN, PAGES) and "IM7-UNT-L1" not in stub.calls[0]["messages"][0]["content"]
    assert "<!-- code:" not in stub.calls[0]["messages"][0]["content"]
    assert stub.calls[0]["output_config"]["format"]["schema"]["properties"]["sections"]["items"]["enum"] == [s.id for s in PAGES]


def test_an_answer_the_guard_sets_aside_comes_back_as_no_answer_with_the_sections_found(monkeypatch):
    stub = StubClient(json.dumps(raw("Ply 4 fails first because its 73 MPa matrix strength is reached.")))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("m", client=stub), raising=False)
    body = client.post("/v1/workspace/result-answers", json=ASKED).json()
    assert body["prose"] == [] and body["withheld"] is True and "73" in body["reason"] and body["writer"] == "template" and body["model"] is None
    assert [s["id"] for s in body["sources"]] == [s.id for s in PAGES] and body["covered"] is False
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("m", client=StubClient("", stop_reason="refusal")), raising=False)
    declined = client.post("/v1/workspace/result-answers", json=ASKED).json()
    assert declined["prose"] == [] and declined["withheld"] is False and "declined" in declined["reason"]


def test_a_question_no_page_holds_a_word_of_is_answered_from_the_sheet_alone(monkeypatch):
    stub = StubClient(json.dumps({"answer": "This is not about the result. Ask why a ply is loaded as it is.", "covered": False}))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("m", client=stub), raising=False)
    body = client.post("/v1/workspace/result-answers", json={**ASKED, "question": "zzz qqq?"}).json()
    assert len(body["prose"]) == 2 and body["sources"] == [] and body["covered"] is False
    assert "sections" not in stub.calls[0]["output_config"]["format"]["schema"]["properties"]


@pytest.mark.parametrize("change, where", [
    ({"question": ""}, "question"),
    ({"question": "x" * 2001}, "question"),
    ({"facts": {}}, "facts"),
    ({"facts": {"nested": {"a": 1}}}, "facts"),
    ({"facts": {"notes": "x" * 50_000}}, "longer than"),
    ({"job_id": "0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00"}, "job_id"),
])
def test_a_malformed_request_is_refused(change, where, monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    refused = client.post("/v1/workspace/result-answers", json={**ASKED, **change})
    assert refused.status_code == 422 and where in json.dumps(refused.json())
    assert TestClient(app).post("/v1/workspace/result-answers", json=ASKED).status_code == 422  # the actor is required


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        yield recorded


@needs_test_database
def test_an_answer_is_recorded_with_the_question_the_facts_digest_the_sections_and_the_model(recording, monkeypatch):
    stub = StubClient(json.dumps(raw()))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    body = recording.post("/v1/workspace/result-answers", json=ASKED).json()
    run = recording.get(f"/v1/runs/{body['run_id']}").json()
    digest = hashlib.sha256(json.dumps(SEEN, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    assert run["endpoint"] == "/v1/workspace/result-answers"
    assert run["inputs"] == {"question": ASKED["question"], "facts_sha256": digest, "sections": [s.id for s in PAGES]}
    assert run["llm_provider"] == "anthropic" and run["llm_model_version"] == "claude-opus-5-5" and run["response"]["prose"] == [GOOD]


# --------------------------------------------------------------------------- the sections themselves, for a reader whose own model writes

def test_a_question_is_handed_the_sections_it_finds_with_their_text_and_no_code_marker():
    body = client.post("/v1/workspace/theory-sections", json={"question": ASKED["question"]}).json()
    assert [s["id"] for s in body["sections"]] == [s.id for s in PAGES] and body["run_id"] is None
    failure = next(s for s in body["sections"] if s["id"] == "engine:5-failure")
    assert failure["document"] == "Laminate theory" and failure["title"] == "5. Failure"
    assert failure["text"] == next(s for s in PAGES if s.id == "engine:5-failure").shown and "Tsai-Hill" in failure["text"]
    assert all("<!-- code:" not in s["text"] for s in body["sections"])
    one = client.post("/v1/workspace/theory-sections", json={"question": ASKED["question"], "limit": 1}).json()
    assert [s["id"] for s in one["sections"]] == [PAGES[0].id]
    assert client.post("/v1/workspace/theory-sections", json={"question": "zzz qqq?"}).json()["sections"] == []


@pytest.mark.parametrize("change, where", [({"question": ""}, "question"), ({"question": "x" * 2001}, "question"), ({"limit": 0}, "limit"),
                                           ({"limit": 6}, "limit"), ({"facts": {"a": 1}}, "facts")])
def test_a_malformed_request_for_sections_is_refused(change, where):
    refused = client.post("/v1/workspace/theory-sections", json={"question": ASKED["question"], **change})
    assert refused.status_code == 422 and where in json.dumps(refused.json())
    assert TestClient(app).post("/v1/workspace/theory-sections", json={"question": ASKED["question"]}).status_code == 422  # the actor is required


@needs_test_database
def test_the_sections_found_are_recorded_by_their_ids_and_never_their_text(recording):
    body = recording.post("/v1/workspace/theory-sections", json={"question": ASKED["question"]}, headers={"X-Anisotropy-Actor": "assistant"})
    run = recording.get(f"/v1/runs/{body.json()['run_id']}").json()
    assert body.headers["X-Anisotropy-Run-Id"] == body.json()["run_id"] and run["actor"] == "assistant"
    assert run["endpoint"] == "/v1/workspace/theory-sections" and run["inputs"] == {"question": ASKED["question"]}
    assert run["response"] == {"sections": [s.id for s in PAGES]}
