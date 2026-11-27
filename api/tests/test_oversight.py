"""The founders' AI activity page's readings (ADR-0145): who may read them, what a customer's row hides, how a call ended, one plan's
story from its records, the week's numbers, and that each view of the page is kept. No model is called: the writer is scripted."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from anisotropy_api import access, oversight
from anisotropy_api.main import app
from anisotropy_api.records import Run
from anisotropy_api.settings import (ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, FOUNDER_EMAILS_VARIABLE,
                                     RECORDING_VARIABLE, AccessSettings)

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from test_planner import ASK, GOOD, PLATE, project, scripted, with_args

FOUNDER = "founder@example.com"
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "oversight"
BAD = with_args(GOOD, 2, value="2000", unit="N")  # a number the sentence does not write: turned back once


# ------------------------------------------------------------------------------------------------------------ the readings alone

def test_a_customer_is_a_tag_that_names_nobody_and_a_founder_or_a_robot_is_shown():
    founders = frozenset({FOUNDER})
    tag, open_ = oversight.who(EMAIL, founders, local=False)
    assert tag.startswith("customer ") and "engineer" not in tag and not open_
    assert oversight.who(EMAIL.upper(), founders, local=False) == (tag, False)  # the same person, the same tag
    assert oversight.who("someone@example.com", founders, local=False)[0] != tag
    assert oversight.who(FOUNDER, founders, local=False) == (FOUNDER, True)
    assert oversight.who(None, founders, local=False) == ("robot", True)
    assert oversight.who(None, founders, local=True) == ("this machine", True)


def test_a_reason_loses_the_words_it_quotes_for_a_customer():
    reason = "the sentence asks for changes the plan leaves out (“make it 3 mm thick”, “use carbon”): ask for them"
    assert oversight.unquoted(reason) == "the sentence asks for changes the plan leaves out (“…”, “…”): ask for them"
    assert oversight.unquoted(None) is None


@pytest.mark.parametrize(("stop", "response", "plan_state", "outcome"), [
    ("refusal", {"model": "m"}, "proposed", "declined"),
    ("max_tokens", None, None, "cut short"),
    ("end_turn", {"withheld": True}, "refused", "refused"),
    ("end_turn", {"withheld": True}, None, "set aside"),
    ("end_turn", {"dropped": [{"line": "x"}], "model": "m"}, None, "partly dropped"),
    ("end_turn", {"model": "m"}, None, "kept"),
    ("end_turn", {"reason": "the day's limit"}, None, "not used"),
    ("end_turn", None, None, "not used"),
])
def test_how_a_call_ended(stop, response, plan_state, outcome):
    assert oversight.call_outcome(stop, response, plan_state) == outcome


# ---------------------------------------------------------------------------------------------------------- through the API

@pytest.fixture
def overseeing(empty_runs, monkeypatch):
    """The API behind Cloudflare Access with run records on and one founder; the customer is EMAIL."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    monkeypatch.setenv(FOUNDER_EMAILS_VARIABLE, FOUNDER)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        yield SimpleNamespace(client=client, engine=empty_runs, customer={access.HEADER: token()},
                              founder={access.HEADER: token(email=FOUNDER)}, robot={access.HEADER: service_token()})


def _planned(client, headers: dict, ask: str = ASK) -> dict:
    pid = project(client, PLATE, headers=headers)
    asked = client.post(f"/v1/projects/{pid}/plans", json={"ask": ask}, headers=headers)
    assert asked.status_code == 200, asked.text
    return asked.json()


def _views(engine) -> list[str]:
    with Session(engine) as session:
        return [r.endpoint for r in session.scalars(select(Run).where(Run.endpoint.like("/v1/oversight/%")).order_by(Run.created_at))]


@needs_test_database
def test_only_a_founder_may_read_the_page_and_anyone_else_finds_nothing_there(overseeing):
    paths = ["/v1/oversight/activity", f"/v1/oversight/plans/{uuid.uuid4()}", "/v1/oversight/weekly"]
    for headers in (overseeing.customer, overseeing.robot, {access.HEADER: token(email="Founder@example.com.evil.test")}):
        for path in paths:
            answered = overseeing.client.get(path, headers=headers)
            assert answered.status_code == 404 and answered.json() == {"detail": "Not Found"}, path
    assert overseeing.client.get("/v1/oversight/activity", headers={access.HEADER: token(email=FOUNDER.upper())}).status_code == 200
    assert overseeing.client.get(paths[1], headers=overseeing.founder).json() == {"detail": "There is no such plan."}
    assert _views(overseeing.engine) == ["/v1/oversight/activity"]  # a refusal reads nothing, so keeps nothing


@needs_test_database
def test_the_feed_shows_what_happened_and_hides_what_a_customer_wrote(overseeing, monkeypatch):
    scripted(monkeypatch, BAD, GOOD, GOOD)
    theirs = _planned(overseeing.client, overseeing.customer)
    ours = _planned(overseeing.client, overseeing.founder, ask=ASK)
    events = overseeing.client.get("/v1/oversight/activity", headers=overseeing.founder).json()["events"]
    assert [e["kind"] for e in events] == ["plan", "call", "plan", "call", "call"]  # newest first; a plan is kept after its calls
    assert all(set(e) == set(events[0]) for e in events)
    mine, their_plan = events[0], events[2]
    assert mine["who"] == FOUNDER and mine["ask"] == ASK and mine["plan"] == ours["id"] and mine["outcome"] == "proposed"
    assert their_plan["who"].startswith("customer ") and their_plan["ask"] == oversight.HIDDEN and not their_plan["words_shown"]
    assert EMAIL not in json.dumps(events)
    their_calls = [e for e in events if e["kind"] == "call" and e["plan"] == theirs["id"]]
    assert len(their_calls) == 2 and all(c["model"] == "claude-opus-5-5" and c["checked"] is True and c["what"] == "plan_steps" for c in their_calls)
    assert all(c["outcome"] == "proposed" and c["cost_usd"] is not None and c["run"] for c in their_calls)
    newer = overseeing.client.get("/v1/oversight/activity", params={"since": events[0]["at"]}, headers=overseeing.founder).json()["events"]
    assert newer == []
    one = overseeing.client.get("/v1/oversight/activity", params={"limit": 1, "before": events[0]["at"]}, headers=overseeing.founder).json()
    assert [e["kind"] for e in one["events"]] == ["call"]
    assert overseeing.client.get("/v1/oversight/activity", params={"since": "yesterday"}, headers=overseeing.founder).status_code == 422
    assert _views(overseeing.engine) == ["/v1/oversight/activity", "/v1/oversight/activity"]  # the refresh (since) is not kept


@needs_test_database
def test_a_plans_story_comes_from_its_records_and_a_customers_keeps_their_words_out(overseeing, monkeypatch):
    scripted(monkeypatch, BAD, GOOD, BAD, GOOD)
    theirs = _planned(overseeing.client, overseeing.customer)
    ours = _planned(overseeing.client, overseeing.founder)
    mine = overseeing.client.get(f"/v1/oversight/plans/{ours['id']}", headers=overseeing.founder).json()
    assert mine["ask"] == ASK and mine["state"] == "proposed" and mine["words_shown"]
    assert [t["plan"] for t in mine["turned_back"]] == [BAD] and mine["turned_back"][0]["reasons"][0].startswith("step 2: 2000")
    assert [c["what"] for c in mine["calls"]] == ["plan_steps", "plan_steps"] and all(len(c["sent"]) == 12 and c["checked"] for c in mine["calls"])
    assert [s["tool"] for s in mine["steps"]] == [s["tool"] for s in ours["steps"]] and all(s["line"] for s in mine["steps"])
    assert mine["version"] is None and mine["job"] is None  # not approved
    story = overseeing.client.get(f"/v1/oversight/plans/{theirs['id']}", headers=overseeing.founder).json()
    assert story["ask"] == oversight.HIDDEN and story["who"].startswith("customer ") and not story["words_shown"]
    assert [t["plan"] for t in story["turned_back"]] == [None] and story["turned_back"][0]["reasons"][0].startswith("step 2: 2000")
    assert all(s["line"] is None and s["note"] is None and s["tool"] for s in story["steps"])
    assert "clamp the bottom edge" not in json.dumps(story) and EMAIL not in json.dumps(story)
    fixture = json.loads((FIXTURES / "plan-story.json").read_text(encoding="utf-8"))
    assert set(fixture) <= set(story) and set(fixture["calls"][0]) <= set(story["calls"][0])
    assert set(fixture["steps"][0]) <= set(story["steps"][0])
    assert _views(overseeing.engine) == ["/v1/oversight/plans/{plan_id}", "/v1/oversight/plans/{plan_id}"]


@needs_test_database
def test_the_week_reads_the_views_the_plans_and_the_unchecked_answers(overseeing, monkeypatch):
    scripted(monkeypatch, BAD, BAD)
    refused = _planned(overseeing.client, overseeing.customer)
    assert refused["state"] == "refused"
    from anisotropy_api.records import record_model_calls
    from test_model_costs import _call
    record_model_calls(overseeing.engine, [_call(model="claude-stand-in-1")], actor="test", user_email=None, run_id=None,
                       checked_models={"claude-opus-5-5"})
    week = overseeing.client.get("/v1/oversight/weekly", headers=overseeing.founder).json()
    fixture = json.loads((FIXTURES / "weekly.json").read_text(encoding="utf-8"))
    assert set(fixture) <= set(week)
    assert {(p["kind"], p["state"], p["plans"]) for p in week["plans"]} == {("plate", "refused", 1)}
    assert week["refused"] == [{"reason": refused["reason"], "plans": 1}]  # this reason quotes no words of the sentence
    assert [(u["model"], u["calls"]) for u in week["unchecked"]] == [("claude-stand-in-1", 1)]
    assert {c["feature"] for c in week["costs"]} >= {"plan_steps", "explain_result"}
    assert any(g["feature"].endswith("/plans") or "plans" in g["feature"] for g in week["guards"])
    assert dt.date.fromisoformat(week["since"]) < dt.date.today()
    assert _views(overseeing.engine) == ["/v1/oversight/weekly"]


@needs_test_database
def test_on_a_machine_with_no_sign_in_its_one_user_reads_the_page(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.delenv(ACCESS_TEAM_DOMAIN_VARIABLE, raising=False)
    monkeypatch.delenv(ACCESS_AUDIENCE_VARIABLE, raising=False)
    monkeypatch.delenv(FOUNDER_EMAILS_VARIABLE, raising=False)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        app.state.access_verifier = None
        assert client.get("/v1/oversight/activity").json() == {"events": []}
        assert client.get("/v1/oversight/weekly").status_code == 200
