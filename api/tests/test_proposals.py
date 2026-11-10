"""The model proposes, the engineer confirms (ADR-0088): the unit reader, the source guard on each way a proposal can go wrong, the Claude
writer behind a stand-in client (the schema it asks for, what it sees, a refusal, a cut answer, text that is not JSON), and the endpoints.
Nothing here calls a model."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.assistant import PROPOSAL_SCHEMA, ClaudeAssistant, TemplateAssistant
from anisotropy_api.main import app
from anisotropy_api.proposals import model_view_of_form, source_guard, unit_named
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

COUPON_ROWS = [
    {"key": "test", "label": "Test", "kind": "choice", "choices": [{"value": "unnotched tension", "label": "Unnotched tension"},
                                                                  {"value": "open-hole tension", "label": "Open-hole tension"}]},
    {"key": "layup", "label": "Layup", "kind": "notation"},
    {"key": "length", "label": "Length (mm)", "kind": "number", "unit": "mm"},
    {"key": "width", "label": "Width (mm)", "kind": "number", "unit": "mm"},
    {"key": "force", "label": "Force (N)", "kind": "number", "unit": "N"},
    {"key": "own_E1", "label": "E1 (MPa)", "kind": "number", "unit": "MPa"},
    {"key": "own_nu12", "label": "nu12", "kind": "number"},
]
LAMINATE_ROWS = [
    {"key": "delta_T", "label": "Temperature change", "kind": "number", "dimension": "temperature_change"},
    {"key": "alpha1", "label": "alpha1", "kind": "number", "dimension": "expansion"},
    {"key": "alpha2", "label": "alpha2", "kind": "number", "dimension": "expansion"},
    {"key": "Nx", "label": "Nx", "kind": "number", "dimension": "force_per_length"},
    {"key": "Ny", "label": "Ny", "kind": "number", "dimension": "force_per_length"},
    {"key": "E2", "label": "E2", "kind": "number", "dimension": "pressure"},
]
TEMPERATURE = [{"id": "temperature", "title": "Temperature change", "detail": "a uniform change of temperature"}]


def proposal(key, value, unit, quote):
    return {"key": key, "value": value, "unit": unit, "quote": quote}


def kept(message, proposals, rows=COUPON_ROWS, conditions=(), question=None, offered_conditions=()):
    return source_guard({"proposals": list(proposals), "conditions": list(conditions), "question": question}, message, rows, list(offered_conditions))


# --------------------------------------------------------------------------------------------- the unit reader

@pytest.mark.parametrize("typed, unit", [
    ("°C", "degC"), ("deg C", "degC"), ("C", "degC"), ("K", "K"), ("°F", "degF"), ("fahrenheit", "degF"),
    ("/°C", "1/degC"), ("1/K", "1/K"), ("x10^-6 /°C", "1e-6/degC"), ("x 10^-6 per °F", "1e-6/degF"), ("e-6/°C", "1e-6/degC"), ("µ/°C", "1e-6/degC"),
    ("GPa", "GPa"), ("ksi", "ksi"), ("kN", "kN"), ("kips", "kip"), ("lbs", "lbf"), ("inches", "in"), ('"', "in"), ("N/mm", "N/mm"),
    ("lbf/in", "lb/in"), ("N·mm/mm", "N*mm/mm"), ("deg", None), ("furlongs", None), ("", None),
])
def test_a_typed_unit_is_read_as_the_engines_table_names_it(typed, unit):
    assert unit_named(typed) == unit


# --------------------------------------------------------------------------------------------- the source guard

def test_values_the_message_writes_are_kept_and_a_coupons_decimal_units_are_converted_to_its_rows():
    message = "Open-hole tension, 250 x 25 mm, [45/0/-45/90]s, pulled to 10 kN, E1 = 161 GPa, nu12 0.32"
    out = kept(message, [proposal("test", "open-hole tension", None, "Open-hole tension"), proposal("length", "250", "mm", "250 x 25 mm"),
                         proposal("width", "25", "mm", "250 x 25 mm"), proposal("layup", "[45/0/-45/90]s", None, "[45/0/-45/90]s"),
                         proposal("force", "10", "kN", "pulled to 10 kN"), proposal("own_E1", "161", "GPa", "E1 = 161 GPa"),
                         proposal("own_nu12", "0.32", None, "nu12 0.32")])
    assert out.dropped == []
    taken = {p["key"]: (p["value"], p["unit"]) for p in out.proposals}
    assert taken == {"test": ("open-hole tension", None), "length": ("250", "mm"), "width": ("25", "mm"), "layup": ("[45/0/-45/90]s", None),
                     "force": ("10000", "N"), "own_E1": ("161000", "MPa"), "own_nu12": ("0.32", None)}
    force = next(p for p in out.proposals if p["key"] == "force")
    assert (force["written_value"], force["written_unit"], force["quote"], force["label"]) == ("10", "kN", "pulled to 10 kN", "Force (N)")


def test_a_laminate_value_keeps_the_unit_written_and_a_cooling_reads_negative():
    message = "Cooled by 270 °F after cure; alpha1 = -0.9e-6 /°F, α2 27 x10^-6 per °F; Nx = 100 N/mm, everything else zero"
    out = kept(message, [proposal("delta_T", "-270", "°F", "Cooled by 270 °F"), proposal("alpha1", "-0.9e-6", "/°F", "alpha1 = -0.9e-6 /°F"),
                         proposal("alpha2", "27", "x10^-6 per °F", "α2 27 x10^-6 per °F"), proposal("Nx", "100", "N/mm", "Nx = 100 N/mm"),
                         proposal("Ny", "0", None, "everything else zero")],
               rows=LAMINATE_ROWS, conditions=[{"id": "temperature", "quote": "Cooled by 270 °F after cure"}], offered_conditions=TEMPERATURE)
    assert out.dropped == []
    assert [(p["key"], p["value"], p["unit"]) for p in out.proposals] == [
        ("delta_T", "-270", "degF"), ("alpha1", "-0.9e-6", "1/degF"), ("alpha2", "27", "1e-6/degF"), ("Nx", "100", "N/mm"), ("Ny", "0", None)]
    assert out.conditions == [{"id": "temperature", "title": "Temperature change", "quote": "Cooled by 270 °F after cure"}]


@pytest.mark.parametrize("item, reason", [
    (proposal("length", "250", "mm", "a 250 mm strip"), "the quoted words are not in the message"),
    (proposal("length", "260", "mm", "250 mm long"), "260 is not a number the quoted words write"),
    (proposal("length", "9.84", "in", "250 mm long"), "9.84 is not a number the quoted words write"),
    (proposal("hole_diameter", "6", "mm", "6 mm hole"), "not a row on offer"),
    (proposal("width", "1", "in", "1 in wide"), "in belongs to US units (in, lbf, psi), and this coupon is stated in SI units (mm, N, MPa): give it in mm, or switch the coupon's units"),
    (proposal("length", "250", "cm", "250 mm long"), "the unit 'cm' is not written in the quoted words"),
    (proposal("own_E1", "250", "mm", "250 mm long"), "mm is not a unit of the row, which is stated in MPa"),
    (proposal("own_nu12", "250", "mm", "250 mm long"), "the row is a pure number and carries no unit"),
    (proposal("test", "three-point bending", None, "three-point"), "'three-point bending' is not one of the row's choices"),
    (proposal("layup", "[0/90]2s", None, "250 mm long"), "the notation is not written in the quoted words"),
    (proposal("length", "two hundred", None, "250 mm long"), "'two hundred' is not a number"),
])
def test_a_proposal_the_message_does_not_hold_is_dropped_with_its_reason(item, reason):
    message = "A 250 mm long strip, 1 in wide, three-point, 6 mm hole"
    out = kept(message, [item])
    assert out.proposals == [] and out.dropped == [{"key": item["key"], "reason": reason}]


def test_a_unit_of_another_dimension_is_dropped_on_a_laminate_row():
    out = kept("E2 10.3 mm", [proposal("E2", "10.3", "mm", "E2 10.3 mm")], rows=LAMINATE_ROWS)
    assert out.dropped == [{"key": "E2", "reason": "mm is not a unit of pressure"}]


def test_a_row_proposed_twice_keeps_the_first_that_holds():
    message = "length 250 mm, no wait, 260 mm"
    out = kept(message, [proposal("length", "300", "mm", "length 250 mm"), proposal("length", "250", "mm", "length 250 mm"),
                         proposal("length", "260", "mm", "260 mm")])
    assert [(p["key"], p["value"]) for p in out.proposals] == [("length", "250")]
    assert [d["reason"] for d in out.dropped] == ["300 is not a number the quoted words write", "proposed twice; the first stands"]


def test_a_condition_must_be_offered_and_asked_for_and_a_question_may_hold_only_the_messages_numbers():
    message = "there are residual stresses from the cure at 180 °C"
    out = kept(message, [], rows=LAMINATE_ROWS, offered_conditions=TEMPERATURE,
               conditions=[{"id": "temperature", "quote": "residual stresses from the cure"}, {"id": "moisture", "quote": "the cure"},
                           {"id": "temperature", "quote": "thermal stresses"}],
               question="Is 180 °C the cure temperature, so the change to 20 °C is -160 °C?")
    assert out.conditions == [{"id": "temperature", "title": "Temperature change", "quote": "residual stresses from the cure"}]
    assert out.dropped == [{"key": "moisture", "reason": "not a condition on offer"},
                           {"key": "temperature", "reason": "the quoted words are not in the message"},
                           {"key": "question", "reason": "it holds numbers the message does not: 20, -160"}]
    asked = kept(message, [], rows=LAMINATE_ROWS, question="Is 180 °C the cure temperature or the change?")
    assert asked.question == "Is 180 °C the cure temperature or the change?" and asked.dropped == []


def test_the_model_sees_no_name_note_or_source():
    form = {"test": "unnotched tension", "length": "250", "filled_by": "A. Engineer", "notes": "for the review", "own_name": "X-Lamina",
            "own_source": "the team's datasheet", "size_from": "the drawing", "team_model": "Job-3.inp", "material_code": "X840", "units": "mm-MPa",
            "width": ""}
    assert model_view_of_form(form) == {"test": "unnotched tension", "length": "250", "units": "mm-MPa"}


# --------------------------------------------------------------------------------------------- the writers

class StubClient:
    """What the Claude writer calls: `client.beta.messages.create(...)`; answers with the text given, or with a stop reason."""

    def __init__(self, text="", stop_reason="end_turn"):
        self.calls = []
        answer = SimpleNamespace(stop_reason=stop_reason, model="claude-stub", content=[SimpleNamespace(type="text", text=text)])
        outer = self

        class Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return answer

        self.beta = SimpleNamespace(messages=Messages())


ANSWER = {"proposals": [proposal("length", "250", "mm", "250 mm long")], "conditions": [], "question": None}


def test_the_claude_writer_asks_for_the_schema_and_returns_its_answer_unjudged():
    client = StubClient(json.dumps(ANSWER))
    reading = ClaudeAssistant("claude-opus-5-5", client=client).propose({"message": "a 250 mm long strip", "rows": COUPON_ROWS})
    assert reading.raw == ANSWER and reading.writer == "anthropic" and reading.model == "claude-opus-5-5" and reading.reason is None
    [call] = client.calls
    assert call["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": PROPOSAL_SCHEMA}}
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"] and call["max_tokens"] == 8000
    assert "digit for digit" in call["system"] and "a 250 mm long strip" in call["messages"][0]["content"]
    assert "temperature" not in call and "thinking" not in call


@pytest.mark.parametrize("client, reason", [
    (StubClient("", stop_reason="refusal"), "declined"),
    (StubClient('{"proposals": [', stop_reason="max_tokens"), "cut short"),
    (StubClient("Length: 250 mm"), "not the JSON asked for"),
    (StubClient("[1, 2]"), "not the JSON asked for"),
])
def test_a_model_that_does_not_answer_in_the_schema_proposes_nothing(client, reason):
    reading = ClaudeAssistant("m", client=client).propose({"message": "x"})
    assert reading.raw is None and reading.writer == "template" and reason in reading.reason and "stands" not in reading.reason


def test_the_template_reads_nothing():
    assert TemplateAssistant().propose({"message": "250 mm"}).raw is None


# --------------------------------------------------------------------------------------------- the endpoints

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded
REQUEST = {"product": "coupon", "message": "A 250 mm long strip, pulled to 10 kN, 1 in wide", "rows": COUPON_ROWS,
           "form": {"units": "mm-MPa", "filled_by": "A. Engineer", "own_source": "the team's datasheet"}}


def test_with_no_model_the_page_is_told_and_a_proposal_request_reads_nothing(monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    assert client.get("/v1/workspace/assistant").json() == {"proposes": False, "provider": None, "model": None}
    body = client.post("/v1/workspace/proposals", json=REQUEST).json()
    assert body["writer"] == "template" and body["proposals"] == [] and body["model"] is None and body["reason"] is None


def test_the_endpoint_returns_what_the_guard_keeps_and_the_model_saw_no_name_or_source(monkeypatch):
    answer = {"proposals": [proposal("length", "250", "mm", "250 mm long"), proposal("force", "10", "kN", "pulled to 10 kN"),
                            proposal("width", "1", "in", "1 in wide"), proposal("width", "25", "mm", "25 mm wide")], "conditions": [], "question": None}
    stub = StubClient(json.dumps(answer))
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=stub), raising=False)
    assert client.get("/v1/workspace/assistant").json() == {"proposes": True, "provider": "anthropic", "model": "claude-opus-5-5"}
    body = client.post("/v1/workspace/proposals", json=REQUEST).json()
    assert body["writer"] == "anthropic" and body["model"] == "claude-opus-5-5"
    assert [(p["key"], p["value"], p["unit"]) for p in body["proposals"]] == [("length", "250", "mm"), ("force", "10000", "N")]
    assert [d["key"] for d in body["dropped"]] == ["width", "width"]
    seen = json.loads(stub.calls[0]["messages"][0]["content"])
    assert seen["form"] == {"units": "mm-MPa"} and seen["message"] == REQUEST["message"] and [r["key"] for r in seen["rows"]] == [r["key"] for r in COUPON_ROWS]
    assert "A. Engineer" not in stub.calls[0]["messages"][0]["content"] and "datasheet" not in stub.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("change, where", [
    ({"rows": [{"key": "length", "label": "Length", "kind": "number", "unit": "furlong"}]}, "unit"),
    ({"rows": [{"key": "test", "label": "Test", "kind": "choice"}]}, "lists its choices"),
    ({"rows": [{"key": "length", "label": "Length", "kind": "number", "unit": "mm", "dimension": "length"}]}, "not both"),
    ({"rows": COUPON_ROWS + [COUPON_ROWS[0]]}, "offered once"),
    ({"message": ""}, "message"),
    ({"product": "plate"}, "product"),
])
def test_a_malformed_offer_is_refused(change, where, monkeypatch):
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    answer = client.post("/v1/workspace/proposals", json={**REQUEST, **change})
    assert answer.status_code == 422 and where in json.dumps(answer.json())
    assert TestClient(app).post("/v1/workspace/proposals", json=REQUEST).status_code == 422  # the actor is required


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        yield recorded


@needs_test_database
def test_a_reading_is_recorded_with_the_model_that_read_it(recording, monkeypatch):
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=StubClient(json.dumps(ANSWER))), raising=False)
    body = recording.post("/v1/workspace/proposals", json={**REQUEST, "message": "a 250 mm long strip"}).json()
    run = recording.get(f"/v1/runs/{body['run_id']}").json()
    assert run["endpoint"] == "/v1/workspace/proposals" and run["inputs"]["message"] == "a 250 mm long strip"
    assert run["llm_provider"] == "anthropic" and run["llm_model_version"] == "claude-opus-5-5"
    assert run["response"]["proposals"][0]["value"] == "250"
