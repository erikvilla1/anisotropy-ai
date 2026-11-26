"""The day's cap on calls to the model per person, and the weekly counts of what the guards set aside (ADR-0139), against the test
database. A stub plays the model, as test_model_costs.py does; nothing here calls one."""

import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from anisotropy_api import access
from anisotropy_api.assistant import CHECKED_MODELS, DAILY_LIMIT_REASON, ClaudeAssistant, LimitedAssistant
from anisotropy_api.main import app
from anisotropy_api.planner import PLAN_LIMIT_REASON
from anisotropy_api.records import model_calls_since, record_model_calls
from anisotropy_api.settings import (ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, MODEL_CALLS_PER_DAY_VARIABLE,
                                     RECORDING_VARIABLE, AccessSettings)

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, alembic_config, needs_test_database
from test_laminate_problems import homework
from test_model_costs import Billing, _call, answer

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("guards_migration", ROOT / "api" / "alembic" / "versions" / "0015_assistant_guards.py")
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)

OTHER = "colleague@example.com"
WORDS = "The laminate is symmetric and balanced."  # no number and no verdict: the guards keep it


# --------------------------------------------------------------------------------------------- the writer past the cap

def test_past_the_cap_nothing_is_asked_and_every_answer_carries_the_reason_the_page_reads():
    limited = LimitedAssistant(100)
    template = ["The template's sentence."]
    for draft in (limited.explain_setup({}, template), limited.explain_result({}, template), limited.explain_laminate({}, template)):
        assert draft.prose == tuple(template) and draft.writer == "template" and draft.model is None and draft.call is None
        assert draft.reason == DAILY_LIMIT_REASON and not draft.withheld
    for reading in (limited.propose({}), limited.read_question({}, {}), limited.answer_question({}, {}), limited.answer_general({}, {}),
                    limited.choose_tools({})):
        assert reading.raw is None and reading.model is None and reading.reason == DAILY_LIMIT_REASON


def test_the_reason_is_one_sentence_in_the_api_the_page_and_the_view():
    page = (ROOT / "lib" / "studio-api.ts").read_text(encoding="utf-8")
    assert f'export const DAILY_LIMIT_REASON = "{DAILY_LIMIT_REASON}";' in page
    assert migration.CAPPED == DAILY_LIMIT_REASON


# --------------------------------------------------------------------------------------------- the count and the cap on the API

@needs_test_database
def test_the_count_is_by_email_whatever_the_client_since_the_time_given(empty_runs):
    with empty_runs.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))
    today = dt.datetime(2026, 11, 24, 9, tzinfo=dt.timezone.utc)
    midnight = today.replace(hour=0)
    record_model_calls(empty_runs, [_call(answered_at=today), _call(answered_at=midnight - dt.timedelta(minutes=1))],
                       actor="browser", user_email=EMAIL, run_id=None)
    record_model_calls(empty_runs, [_call(answered_at=today)], actor="assistant", user_email=EMAIL, run_id=None)  # the MCP server, signed in
    record_model_calls(empty_runs, [_call(answered_at=today)], actor="assistant", user_email=None, run_id=None)
    try:
        assert model_calls_since(empty_runs, EMAIL, midnight) == 2  # yesterday's call is not today's, and a call with no email is no one's
        assert model_calls_since(empty_runs, OTHER, midnight) == 0
    finally:
        with empty_runs.begin() as connection:
            connection.execute(text("TRUNCATE model_calls"))


@pytest.fixture
def capped(empty_runs, monkeypatch):
    """The API behind Cloudflare Access with run records on and a cap of two calls a day, as the hosted site runs with its own number."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    monkeypatch.setenv(MODEL_CALLS_PER_DAY_VARIABLE, "2")
    with empty_runs.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        yield client
    with empty_runs.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))


@needs_test_database
def test_past_the_day_s_cap_a_person_gets_the_template_and_the_reason_and_no_call_is_made(capped, empty_runs):
    before = app.state.assistant
    client = Billing(answer(WORDS), answer(WORDS), answer(WORDS))  # three answers: two for the engineer, one for a colleague
    app.state.assistant = ClaudeAssistant("claude-opus-5-5", client=client)
    try:
        bodies = [capped.post("/v1/laminates/solve", json=homework(), headers={access.HEADER: token(email=EMAIL)}) for _ in range(3)]
        colleague = capped.post("/v1/laminates/solve", json=homework(), headers={access.HEADER: token(email=OTHER)})
    finally:
        app.state.assistant = before
    assert all(body.status_code == 200 for body in bodies + [colleague]), [body.text for body in bodies]
    assert [body.json()["writer"] for body in bodies] == ["anthropic", "anthropic", "template"]
    third = bodies[2].json()
    assert third["reason"] == DAILY_LIMIT_REASON and third["model"] is None and third["prose"]  # the engine's sentences still answer
    assert colleague.json()["writer"] == "anthropic"  # a cap is per person
    assert client.responses == []  # the capped request asked nothing
    with empty_runs.connect() as connection:
        calls = dict(connection.execute(text("SELECT user_email, count(*) FROM model_calls GROUP BY user_email")).all())
        recorded = connection.execute(text("SELECT response->>'reason' FROM runs WHERE user_email = :e ORDER BY created_at"), {"e": EMAIL}).scalars().all()
    assert calls == {EMAIL: 2, OTHER: 1}
    assert recorded == [None, None, DAILY_LIMIT_REASON]  # the run record says why no model wrote, and the view counts it


@needs_test_database
def test_a_request_with_no_email_a_service_token_of_ours_is_never_capped(capped, empty_runs):
    before = app.state.assistant
    app.state.assistant = ClaudeAssistant("claude-opus-5-5", client=Billing(*[answer(WORDS) for _ in range(3)]))
    try:
        writers = [capped.post("/v1/laminates/solve", json=homework(), headers={access.HEADER: service_token()}).json()["writer"] for _ in range(3)]
    finally:
        app.state.assistant = before
    assert writers == ["anthropic"] * 3  # the site check keeps a budget of its own (ADR-0138)


@needs_test_database
def test_with_no_cap_set_the_model_is_asked_every_time(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.delenv(MODEL_CALLS_PER_DAY_VARIABLE, raising=False)
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        before = app.state.assistant
        app.state.assistant = ClaudeAssistant("claude-opus-5-5", client=Billing(*[answer(WORDS) for _ in range(3)]))
        try:
            writers = [client.post("/v1/laminates/solve", json=homework()).json()["writer"] for _ in range(3)]
        finally:
            app.state.assistant = before
    with empty_runs.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))
    assert writers == ["anthropic"] * 3


# --------------------------------------------------------------------------------------------- the checked models (ADR-0121 amendment 8)

def test_the_page_is_told_whether_the_model_is_one_the_assistant_check_was_run_with(monkeypatch):
    client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=Billing()), raising=False)
    assert client.get("/v1/workspace/assistant").json()["checked"] is True and "claude-opus-5-5" in CHECKED_MODELS
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-unchecked-0", client=Billing()), raising=False)
    assert client.get("/v1/workspace/assistant").json() == {"proposes": True, "provider": "anthropic", "model": "claude-unchecked-0", "checked": False}


# --------------------------------------------------------------------------------------------- the guards' weekly view

def _run(connection, endpoint: str, at: dt.datetime, response: dict) -> None:
    connection.execute(text("INSERT INTO runs (id, created_at, actor, endpoint, status, inputs, inputs_sha256, engine_version, api_version, response) "
                            "VALUES (gen_random_uuid(), :at, 'browser', :endpoint, 'solved', '{}', :digest, '0', '0', CAST(:response AS jsonb))"),
                       {"at": at, "endpoint": endpoint, "digest": "0" * 64, "response": json.dumps(response)})


KEPT = {"writer": "anthropic", "model": "claude-opus-5-5", "withheld": False, "reason": None}
SET_ASIDE = {"writer": "template", "model": None, "withheld": True, "reason": "the model's answer said “laminate fails”, against the engine's verdict"}
NO_ANSWER = {"writer": "template", "model": None, "withheld": False, "reason": "the model could not be reached; the template's prose stands"}
CAPPED = {"writer": "template", "model": None, "withheld": False, "reason": DAILY_LIMIT_REASON}
NO_MODEL = {"writer": "template", "model": None, "withheld": False, "reason": None}  # no model set: nothing was asked


@needs_test_database
def test_the_view_counts_each_week_and_route_and_flags_a_jump_in_answers_set_aside(empty_runs):
    monday = dt.datetime(2026, 11, 16, 9, tzinfo=dt.timezone.utc)
    answers = "/v1/workspace/result-answers"
    with empty_runs.begin() as connection:
        for weeks in (1, 2, 3, 4):  # the four weeks before: every answer kept
            for _ in range(2):
                _run(connection, answers, monday - dt.timedelta(weeks=weeks), KEPT)
        for response in (KEPT, SET_ASIDE, SET_ASIDE, NO_ANSWER, CAPPED, NO_MODEL):
            _run(connection, answers, monday, response)
        _run(connection, "/v1/coupon-jobs/3f0c/explain", monday, KEPT)
        _run(connection, "/v1/workspace/proposals", monday, {**KEPT, "dropped": [{"field": "width", "reason": "not_offered"}]})
        _run(connection, "/v1/workspace/result-questions", monday, {**KEPT, "dropped": []})
        _run(connection, "/v1/coupons/check", monday, {"items": []})  # no writer: not the model's
    with empty_runs.connect() as connection:
        rows = connection.execute(text("SELECT feature, asked, kept, set_aside, with_dropped, no_answer, capped, set_aside_pct, usual_set_aside_pct, flag "
                                       "FROM assistant_guards_by_feature WHERE week_of = '2026-11-16' ORDER BY feature")).all()
        first = connection.execute(text("SELECT flag FROM assistant_guards_by_feature WHERE week_of = '2026-10-19'")).scalar_one()
        comment = connection.execute(text("SELECT obj_description('assistant_guards_by_feature'::regclass)")).scalar_one()
    by_feature = {row[0]: tuple(row[1:]) for row in rows}
    assert set(by_feature) == {"explain", "workspace/proposals", "workspace/result-answers", "workspace/result-questions"}
    asked, kept, set_aside, with_dropped, no_answer, capped, pct, usual, flag = by_feature["workspace/result-answers"]
    assert (asked, kept, set_aside, with_dropped, no_answer, capped) == (4, 1, 2, 0, 1, 1)  # the capped one asked no model
    assert (float(pct), float(usual), flag) == (50.0, 0.0, "look: more answers set aside than usual")
    assert by_feature["workspace/proposals"][:4] == (1, 1, 0, 1) and by_feature["workspace/result-questions"][3] == 0
    assert by_feature["explain"][-1] == "no earlier week to compare with" and first == "no earlier week to compare with"
    assert "ADR-0139" in comment


@needs_test_database
def test_a_request_past_the_days_planned_requests_is_counted_capped(empty_runs):
    """A sentence past the day's planned requests (ADR-0144) asked no model, as one past the day's calls: the view counts it capped
    (migration 0017), not as a request the model did not answer."""
    monday = dt.datetime(2026, 11, 16, 9, tzinfo=dt.timezone.utc)
    plans = "/v1/projects/{project_id}/plans"
    with empty_runs.begin() as connection:
        for response in (KEPT, {"writer": "template", "model": None, "withheld": False, "reason": PLAN_LIMIT_REASON}):
            _run(connection, plans, monday, response)
    with empty_runs.connect() as connection:
        row = connection.execute(text("SELECT asked, kept, no_answer, capped FROM assistant_guards_by_feature WHERE feature = 'projects/{project_id}/plans'")).one()
        comment = connection.execute(text("SELECT obj_description('assistant_guards_by_feature'::regclass)")).scalar_one()
    assert tuple(row) == (1, 1, 0, 1) and "ADR-0139" in comment


@needs_test_database
def test_the_migration_adds_the_view_and_takes_it_away(empty_runs):
    config = alembic_config(TEST_URL)
    assert "assistant_guards_by_feature" in inspect(empty_runs).get_view_names()
    command.downgrade(config, "0014")
    assert "assistant_guards_by_feature" not in inspect(empty_runs).get_view_names()
    command.upgrade(config, "head")
    assert "assistant_guards_by_feature" in inspect(empty_runs).get_view_names()
