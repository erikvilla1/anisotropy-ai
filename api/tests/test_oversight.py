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

from anisotropy_api import access, oversight, planner
from anisotropy_api.main import app
from anisotropy_api.records import AgentPlanRow, JobRow, ModelVersionRow, ProjectRow, Run, add_plan, record_model_calls
from anisotropy_api.settings import (ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, FOUNDER_EMAILS_VARIABLE,
                                     RECORDING_VARIABLE, AccessSettings)

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from test_model_costs import _call
from test_planner import ASK, GOOD, PLATE, plan, project, scripted, step, with_args

FOUNDER = "founder@example.com"
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "oversight"
BAD = with_args(GOOD, 2, value="2000", unit="N")  # a number the sentence does not write: turned back once


# ------------------------------------------------------------------------------------------------------------ the readings alone

def test_a_customer_is_a_tag_that_names_nobody_and_a_founder_or_a_robot_is_shown():
    founders = frozenset({FOUNDER})
    tag, open_ = oversight.who(EMAIL, founders, local=False)
    assert tag.startswith("customer ") and "engineer" not in tag and not open_
    assert len(tag) == len("customer ") + 10 and tag == oversight.tag_of(f" {EMAIL.title()} ")  # ten hex digits; a pseudonym, as the email gives it
    assert oversight.who(EMAIL.upper(), founders, local=False) == (tag, False)  # the same person, the same tag
    assert oversight.who("someone@example.com", founders, local=False)[0] != tag
    assert oversight.who(FOUNDER, founders, local=False) == (FOUNDER, True)
    assert oversight.who(None, founders, local=False) == ("robot", True)
    assert oversight.who(None, founders, local=True) == ("this machine", True)


def test_a_reason_loses_the_words_it_quotes_for_a_customer():
    # the review of 2026-11-27: taking out what stands between curly quotes let words through (a quote that holds curly quotes, a
    # value outside them, the model's own sentence), so a customer's reason is now one of the fixed lines and holds none of its words
    reason = "the sentence asks for changes the plan leaves out (“make it 3 mm thick”, “use carbon”): ask for them rather than run without them"
    assert oversight.reason_kind(reason) == "the sentence asks for a change the plan leaves out"
    nested = "the sentence asks for a change the plan leaves out (“pull it like the “north bracket” of the Acme job”): ask for it rather than run without it"
    assert oversight.reason_kind(nested) == "the sentence asks for a change the plan leaves out"
    assert oversight.reason_kind("step 2: the sentence writes 2 kN, and the step gives it in N") == "step 2: a value given in another unit than the sentence writes"
    assert oversight.reason_kind("step 1: Edge-Middle is not a region of this model; it has Edge-Bottom, Edge-Top") == "step 1: a region the model does not have"
    assert oversight.reason_kind("You want the bottom edge clamped for the north site bracket") == oversight.REASON_HIDDEN
    assert oversight.reason_kind("step 3: 30 mm is thinner than the plies of the Acme bracket") == oversight.REASON_HIDDEN  # a tool's own refusal
    assert oversight.reason_shown(None, None, False) is None and oversight.reason_shown(nested, None, True) == nested


def _refusals() -> list[str]:
    """Reasons the planner's own checks give, made by the checks themselves on plans that fail them."""
    bad = [with_args(GOOD, 2, value="2000", unit="N"), with_args(GOOD, 2, unit="N"), with_args(GOOD, 2, unit="lbf"), with_args(GOOD, 2, unit=None),
           with_args(GOOD, 1, region="Edge-Middle"), with_args(GOOD, 4, question="Does it hold at 9 kN?"), with_args(GOOD, 4, question="It holds"),
           with_args(GOOD, 4, question=None), plan(), plan(question="which edge do you mean"), plan(question="Is it 7 mm?"),
           plan(step("fly", "clamp the bottom edge")), plan(step("run", "tell me if it holds"), step("run", "tell me if it holds")),
           plan(step("run", "words that are not there")), plan(step("answer", "tell me if it holds", question="Does it hold?")),
           plan(step("row", "clamp the bottom edge", key="colour", value="red")), plan("not a step"),
           plan(step("run", "tell me if it holds"), step("hold", "clamp the bottom edge", region="Edge-Bottom", dofs=[1])),
           plan(step("run", "tell me if it holds"), unread=[{"quote": "clamp the bottom edge", "reason": "no_value"}]),
           plan(step("run", "tell me if it holds"), unread=[{"quote": "clamp the bottom edge", "reason": "not_offered"}]),
           plan(unread=[{"quote": "clamp the bottom edge", "reason": "not_offered"}])]
    return [reason for raw in bad for reason in planner.check_plan(raw, ASK, PLATE).reasons]


def _fixed(line: str) -> bool:
    """Whether a line is one of the fixed ones, after a step's number at most."""
    head, colon, rest = line.partition(": ")
    if colon and head.startswith("step ") and head[5:].isdigit():
        line = rest
    return line in oversight.REASON_LINES


def test_every_reason_of_the_planners_checks_has_a_fixed_line_and_no_reason_gives_anything_else():
    reasons = _refusals()
    assert len(set(reasons)) >= 18  # the checks above fail in as many ways
    for reason in reasons:
        line = oversight.reason_kind(reason)
        assert line != oversight.REASON_HIDDEN and _fixed(line), reason  # a reason of planner.py with no line: add it to REASON_KINDS
    assert oversight.reason_kind(planner.PLAN_LIMIT_REASON) == planner.PLAN_LIMIT_REASON
    # whatever the words, the answer is a fixed line, after a step's number at most: nothing of the reason is in it
    for words in ("", "x", "step 1: ", "step 12: “a” is not a row on offer", "step 7: Acme's secret is not a tool on offer here; the tools are x",
                  "the sentence names Acme, not Zenith", "Acme takes only words the sentence writes", "step 99999: x is not a row on offer", *reasons):
        line = oversight.reason_kind(words)
        assert _fixed(line) and "Acme" not in line, words
    joined = planner.reason_of(reasons)  # more than a refusal's answer names: the first five, and "more like them"
    shown = oversight.reason_shown(joined, reasons, False)
    assert shown.endswith("; and more like them") and all(_fixed(part) for part in shown.removesuffix("; and more like them").split("; "))
    assert _fixed(oversight.reason_shown(joined, None, False))  # with nothing to read the joined reasons by, still a fixed line


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


def test_a_call_whose_answer_the_checks_turned_back_says_so_and_never_reads_as_the_plan():
    # the review of 2026-11-27: every call of a plan read as the plan's state, so a call turned back read "proposed" or "done"
    assert oversight.call_outcome("end_turn", None, "proposed", True) == "turned back"
    assert oversight.call_outcome("end_turn", None, "done", True) == "turned back"
    assert oversight.call_outcome("end_turn", None, "done", False) == "done"
    assert oversight.call_outcome("end_turn", None, "done", None) == "plan done"  # the records do not say which call it was
    assert oversight.call_outcome("refusal", None, "refused", True) == "declined" and oversight.call_outcome("max_tokens", None, "refused", None) == "cut short"
    a, b, c = (uuid.UUID(int=n) for n in (1, 2, 3))
    told = oversight.turned_back_calls
    assert told("proposed", 0, [a]) == {a: False} and told("proposed", 1, [a, b]) == {a: True, b: False}
    assert told("done", 1, [a, b]) == {a: True, b: False} and told("unavailable", 0, [a]) == {a: False}
    assert told("refused", 2, [a, b]) == {a: True, b: True} and told("refused", 1, [a]) == {a: True}
    assert told("refused", 1, [a, b]) == {a: True, b: False}  # the second call gave no answer to check
    # a call's row is missing, or the plan is older than the record of what was turned back: no call is said to be either
    assert told("proposed", 1, [a]) == {a: None} and told("proposed", 0, [a, b]) == {a: None, b: None}
    assert told("refused", 2, [a]) == {a: None} and told("refused", 0, [a]) == {a: None} and told("refused", 1, [a, b, c]) == {a: None, b: None, c: None}
    assert told("capped", 0, []) == {}


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
    assert [c["outcome"] for c in their_calls] == ["proposed", "turned back"] and all(c["cost_usd"] is not None and c["run"] for c in their_calls)
    assert [c["outcome"] for c in events if c["kind"] == "call" and c["plan"] == ours["id"]] == ["proposed"]
    fixture = json.loads((FIXTURES / "activity.json").read_text(encoding="utf-8"))
    assert set(fixture["events"][0]) == set(events[0]) and len({e["key"] for e in events}) == len(events)
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
    assert [t["plan"] for t in story["turned_back"]] == [None]
    assert story["turned_back"][0]["reasons"] == ["step 2: a value that is not a number the sentence writes"] and "2000" not in json.dumps(story)
    assert [c["outcome"] for c in story["calls"]] == ["turned back", "proposed"] == [c["outcome"] for c in mine["calls"]]
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
    # a call of now, not of the stand-in's fixed day: the week's window moves, and this test passed only until 2027-01-11
    now = dt.datetime.now(dt.timezone.utc)
    record_model_calls(overseeing.engine, [_call(model="claude-stand-in-1", answered_at=now)], actor="test", user_email=None, run_id=None,
                       checked_models={"claude-opus-5-5"})
    week = overseeing.client.get("/v1/oversight/weekly", headers=overseeing.founder).json()
    after = dt.datetime.now(dt.timezone.utc)
    fixture = json.loads((FIXTURES / "weekly.json").read_text(encoding="utf-8"))
    assert set(fixture) <= set(week) and dt.date.fromisoformat(fixture["since"]).weekday() == 0
    assert {(p["kind"], p["state"], p["plans"]) for p in week["plans"]} == {("plate", "refused", 1)}
    assert refused["reason"].startswith("step 2: 2000 is not a number the sentence writes")  # what the customer was told, in full
    assert week["refused"] == [{"reason": "step 2: a value that is not a number the sentence writes", "plans": 1}]  # and what a founder reads
    assert [(u["model"], u["calls"]) for u in week["unchecked"]] == [("claude-stand-in-1", 1)]
    assert {c["feature"] for c in week["costs"]} >= {"plan_steps", "explain_result"}
    assert any(g["feature"].endswith("/plans") or "plans" in g["feature"] for g in week["guards"])
    since = dt.date.fromisoformat(week["since"])  # a Monday: this week and the seven before (either clock's week, should one turn between them)
    assert since.weekday() == 0 and since in {day.date() - dt.timedelta(days=day.weekday(), weeks=7) for day in (now, after)}
    assert _views(overseeing.engine) == ["/v1/oversight/weekly"]


# ------------------------------------------------------------------------- the review of 2026-11-27: what it found, held fixed

def _story(o, plan_id: str) -> dict:
    answered = o.client.get(f"/v1/oversight/plans/{plan_id}", headers=o.founder)
    assert answered.status_code == 200, answered.text
    return answered.json()


def _read_by_a_founder(o, plan_id: str) -> tuple[dict, dict, str]:
    """A plan's story, the week and all three readings as text, as a founder's browser gets them."""
    story = _story(o, plan_id)
    week = o.client.get("/v1/oversight/weekly", headers=o.founder).json()
    feed = o.client.get("/v1/oversight/activity", headers=o.founder).json()
    return story, week, json.dumps([story, week, feed], ensure_ascii=False)


@needs_test_database
def test_the_models_own_sentence_as_a_customers_reason_is_one_fixed_line_and_a_founders_or_a_robots_is_whole(overseeing, monkeypatch):
    # words the model writes back that are no question become the refusal's reason as they are (planner: `checked.said`): they repeat
    # the customer's sentence and hold no curly quote, so taking out what stood between quotes let all of them through
    echo = plan(question="You want the bottom edge clamped and the top edge pulled for the north site bracket, which needs a region first")
    scripted(monkeypatch, *[echo] * 6)
    theirs = _planned(overseeing.client, overseeing.customer)
    assert theirs["state"] == "refused" and "north site bracket" in theirs["reason"]  # what the customer is told, in full
    story, week, sent = _read_by_a_founder(overseeing, theirs["id"])
    assert not story["words_shown"] and story["reason"] == oversight.REASON_HIDDEN
    assert story["turned_back"] == [{"plan": None, "reasons": [planner.NOT_A_QUESTION]}] * 2  # the checks' own line, and it holds no word
    assert week["refused"] == [{"reason": oversight.REASON_HIDDEN, "plans": 1}]
    assert "north site bracket" not in sent and "clamped" not in sent
    ours = _planned(overseeing.client, overseeing.founder)
    robots = _planned(overseeing.client, overseeing.robot)
    for whose, name in ((ours, FOUNDER), (robots, "robot")):  # a founder's own rows and a robot's stay whole
        story = _story(overseeing, whose["id"])
        assert story["who"] == name and story["words_shown"] and story["ask"] == ASK and story["reason"] == whose["reason"]
        assert story["turned_back"] == [{"plan": echo, "reasons": [planner.NOT_A_QUESTION]}] * 2
    week = overseeing.client.get("/v1/oversight/weekly", headers=overseeing.founder).json()
    assert week["refused"] == [{"reason": ours["reason"], "plans": 2}, {"reason": oversight.REASON_HIDDEN, "plans": 1}]


@needs_test_database
def test_a_customers_quote_that_holds_curly_quotes_leaves_no_word_in_a_reason(overseeing, monkeypatch):
    ask = "clamp the bottom edge, pull the top edge like the “north bracket” of the Acme job and run it"
    raw = plan(step("hold", "clamp the bottom edge", region="Edge-Bottom", dofs=[1, 2, 3, 4, 5, 6]), step("run", "run it"),
               unread=[{"quote": "pull the top edge like the “north bracket” of the Acme job", "reason": "refers_back"}])
    scripted(monkeypatch, raw, raw)
    theirs = _planned(overseeing.client, overseeing.customer, ask=ask)
    assert theirs["state"] == "refused" and "“north bracket” of the Acme job”" in theirs["reason"]
    story, week, sent = _read_by_a_founder(overseeing, theirs["id"])
    line = "the sentence asks for a change the plan leaves out"
    assert story["reason"] == line and [t["reasons"] for t in story["turned_back"]] == [[line], [line]]
    assert week["refused"] == [{"reason": line, "plans": 1}]
    assert "Acme" not in sent and "north bracket" not in sent and "pull the top edge" not in sent


@needs_test_database
def test_a_value_a_unit_or_a_region_outside_any_quote_leaves_a_customers_reason(overseeing, monkeypatch):
    scripted(monkeypatch, with_args(GOOD, 2, unit="N"), with_args(GOOD, 1, region="Edge-Middle"))  # the sentence writes 2 kN, and no such edge
    theirs = _planned(overseeing.client, overseeing.customer)
    assert theirs["state"] == "refused" and "Edge-Middle is not a region of this model; it has Edge-" in theirs["reason"]
    story, week, sent = _read_by_a_founder(overseeing, theirs["id"])
    assert [t["reasons"] for t in story["turned_back"]] == [["step 2: a value given in another unit than the sentence writes"],
                                                            ["step 1: a region the model does not have"]]
    assert story["reason"] == "step 1: a region the model does not have" and week["refused"] == [{"reason": story["reason"], "plans": 1}]
    assert "Edge-" not in sent and "2 kN" not in sent and "kN" not in sent
    for reasons in ([story["reason"]], *[t["reasons"] for t in story["turned_back"]], [r["reason"] for r in week["refused"]]):
        assert all(_fixed(reason) for reason in reasons)


@needs_test_database
def test_an_approved_customers_plan_shows_what_happened_and_none_of_its_words(overseeing):
    now = dt.datetime.now(dt.timezone.utc)
    pid, plan_id, job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with Session(overseeing.engine) as session:
        session.add(ProjectRow(id=pid, kind="fea", name="SECRET bracket", actor="studio", user_email=EMAIL, content={}, created_at=now, updated_at=now))
        session.flush()
        session.add(ModelVersionRow(project_id=pid, n=2, made_by="assistant", why="SECRET sentence", changes=["Width: 25 mm to 30 mm SECRET"],
                                    content={}, digest="0" * 64, job_id=str(job_id), created_at=now))
        session.add(JobRow(id=job_id, actor="studio", user_email=EMAIL, state="stopped", stage="SECRET stage", stages_done=["a"], stages=["a", "b"],
                           message="SECRET message of the tool", inputs={}, started_at=now, process="p", project_id=pid))
        session.add(AgentPlanRow(
            id=plan_id, project_id=pid, kind="coupon", user_email=EMAIL, actor="studio", ask="SECRET sentence", state="stopped",
            steps=[{"n": 1, "role": "Geometry", "tool": "row", "line": "SECRET line", "quote": "SECRET quote", "regions": ["SECRET region"],
                    "change": {"action": "row", "key": "width", "value": "SECRET"}, "question": "SECRET?", "state": "done", "note": "SECRET note"}],
            base="0" * 64, question="SECRET question", unread=[{"quote": "SECRET", "reason": "no_value"}], reason="step 1: SECRET is too thin",
            writer="anthropic", model="m", job_id=str(job_id), version_n=2, attempts=None, created_at=now,
            approved_at=now + dt.timedelta(seconds=1), updated_at=now))
        session.commit()
    story, week, sent = _read_by_a_founder(overseeing, str(plan_id))
    assert "SECRET" not in sent and EMAIL not in sent
    assert story["state"] == "stopped" and story["reason"] == oversight.REASON_HIDDEN and story["turned_back"] == []  # a plan older than `attempts`
    assert story["steps"][0] == {"n": 1, "role": "Geometry", "tool": "row", "state": "done", "line": None, "note": None}
    assert story["version"] == {"n": 2, "made_by": "assistant", "why": None, "changes": 1, "change_lines": [], "at": story["version"]["at"]}
    assert story["job"]["state"] == "stopped" and story["job"]["stage"] is None and story["job"]["message"] is None and story["job"]["stages"] == 2


@needs_test_database
def test_a_call_that_is_no_plans_reads_what_became_of_its_words_from_its_run(overseeing):
    at = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
    answers = {"read_question": {"withheld": True, "reason": "x" * 5000}, "answer_question": {"model": "m", "dropped": [], "answer": "y" * 5000},
               "explain_result": {"model": "m", "dropped": [{"line": "it will hold"}]}, "explain_laminate": {"reason": "the day's limit"}}
    with Session(overseeing.engine) as session:
        runs = {feature: Run(actor="studio", endpoint="/v1/workspace/assistant", status="solved", inputs={}, inputs_sha256="0" * 64,
                             engine_version="0", api_version="0", response=response) for feature, response in answers.items()}
        session.add_all(runs.values())
        session.commit()
        ids = {feature: run.id for feature, run in runs.items()}
    for n, feature in enumerate(answers):
        record_model_calls(overseeing.engine, [_call(feature=feature, answered_at=at + dt.timedelta(seconds=n))], actor="studio", user_email=EMAIL,
                           run_id=ids[feature])
    record_model_calls(overseeing.engine, [_call(feature="propose_changes", answered_at=at - dt.timedelta(seconds=1))], actor="studio", user_email=None,
                       run_id=None)
    events = overseeing.client.get("/v1/oversight/activity", headers=overseeing.founder).json()["events"]
    assert [(e["what"], e["outcome"]) for e in events] == [("explain_laminate", "not used"), ("explain_result", "partly dropped"),
                                                          ("answer_question", "kept"), ("read_question", "set aside"), ("propose_changes", "not used")]


# The page's feed as lib/oversight.ts reads it (firstPage, refreshed), asked of the routes themselves.

EPOCH = "1970-01-01T00:00:00+00:00"


def _feed(o, **params) -> list[dict]:
    answered = o.client.get("/v1/oversight/activity", params=params, headers=o.founder)
    assert answered.status_code == 200, answered.text
    return answered.json()["events"]


def _first(o, size: int) -> tuple[list[dict], str | None]:
    """The first page and its floor: the key of its oldest event, or None when the page is the whole feed."""
    events = _feed(o, limit=size)
    return events, (events[-1]["key"] if len(events) == size else None)


def _refreshed(o, floor: str | None, size: int) -> list[dict]:
    """Everything from the floor on (from the beginning with no floor), page by page until a page is short: the page's refresh."""
    start = {"from": floor} if floor else {"since": EPOCH}
    events: list[dict] = []
    while True:
        page = _feed(o, limit=size, **start, **({"before": events[-1]["key"]} if events else {}))
        events += page
        if len(page) < size:
            return events


def _recorded(o, at: dt.datetime, n: int = 1, **changes) -> None:
    record_model_calls(o.engine, [_call(answered_at=at + dt.timedelta(seconds=i), **changes) for i in range(n)], actor="studio", user_email=None,
                       run_id=None)


@needs_test_database
def test_a_refresh_shows_a_call_recorded_after_newer_ones(overseeing, monkeypatch):
    # a plan's first call is answered, the second takes a while, and both rows are written when the request ends. Meanwhile somebody
    # else's call is recorded and the page reads: a refresh that asked only for what is newer than its newest never saw the first call
    hour_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    _recorded(overseeing, hour_ago, 3)
    writer = scripted(monkeypatch, BAD, GOOD)
    create, seen = writer.beta.messages.create, {}

    def between(**kwargs):
        if len(writer.asked) == 1:  # the first answer is in and the second is being asked
            _recorded(overseeing, dt.datetime.now(dt.timezone.utc), feature="read_question")
            seen["page"], seen["floor"] = _first(overseeing, 2)
        return create(**kwargs)

    monkeypatch.setattr(writer.beta.messages, "create", between, raising=False)
    theirs = _planned(overseeing.client, overseeing.customer)
    page, floor = seen["page"], seen["floor"]
    assert [e["what"] for e in page] == ["read_question", "explain_result"] and floor == page[-1]["key"]
    newer = _feed(overseeing, since=page[0]["key"])
    assert [(e["kind"], e["outcome"]) for e in newer] == [("plan", "proposed"), ("call", "proposed")]  # the first call is not newer
    fresh = _refreshed(overseeing, floor, 2)
    everything = _feed(overseeing, limit=200)
    assert len(everything) == 7 and fresh == everything[:5] and fresh[-1]["key"] == floor
    assert [(e["kind"], e["what"], e["outcome"]) for e in fresh[:4]] == [
        ("plan", "plan on a plate", "proposed"), ("call", "plan_steps", "proposed"), ("call", "read_question", "not used"),
        ("call", "plan_steps", "turned back")]
    assert fresh[3]["plan"] == theirs["id"] and fresh[3]["at"] < page[0]["at"]  # recorded later, and it happened earlier


@needs_test_database
def test_a_refresh_shows_every_new_event_however_many_there_are(overseeing):
    base = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    _recorded(overseeing, base)
    page, floor = _first(overseeing, 50)
    assert len(page) == 1 and floor is None  # the whole feed: the refresh reads from the beginning
    _recorded(overseeing, base + dt.timedelta(seconds=1), 120)
    assert len(_feed(overseeing, limit=50, since=page[0]["key"])) == 50  # one read holds a page, and 70 would be left behind it
    fresh = _refreshed(overseeing, floor, 50)
    assert len(fresh) == 121 and len({e["key"] for e in fresh}) == 121 and fresh == _feed(overseeing, limit=200)
    assert [e["at"] for e in fresh] == sorted((e["at"] for e in fresh), reverse=True) and fresh[-1] == page[0]
    # and with a floor: a page that was full, then more than a page of new events
    page, floor = _first(overseeing, 50)
    _recorded(overseeing, base + dt.timedelta(seconds=200), 130)
    fresh = _refreshed(overseeing, floor, 50)
    assert len(fresh) == 180 and fresh[-1]["key"] == floor and fresh[130:] == page and len({e["key"] for e in fresh}) == 180


@needs_test_database
def test_events_of_one_instant_are_each_read_once_on_either_side_of_any_of_them(overseeing):
    at = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
    record_model_calls(overseeing.engine, [_call(feature=f, answered_at=at) for f in ("read_question", "answer_question", "explain_result",
                                                                                      "propose_changes", "explain_laminate")],
                       actor="studio", user_email=None, run_id=None)
    add_plan(overseeing.engine, kind="repair", project_id=None, user_email=None, actor="studio", ask="x", state="done", steps=[], base="0" * 64,
             question=None, unread=[], reason=None, writer="template", model=None, created_at=at, approved_at=at, updated_at=at)
    everything = _feed(overseeing, limit=200)
    assert len(everything) == 7 and len({e["at"] for e in everything}) == 1 and len({e["key"] for e in everything}) == 7
    assert [e["kind"] for e in everything] == ["plan", *["call"] * 5, "approval"]
    assert [e["key"] for e in everything] == sorted((e["key"] for e in everything), key=_place, reverse=True)
    walked, page = [], _feed(overseeing, limit=2)
    while page:  # "Show older", a page of two at a time: the page's boundary falls inside the instant three times
        walked += page
        page = _feed(overseeing, limit=2, before=walked[-1]["key"])
    assert walked == everything
    for i, event in enumerate(everything):  # around every event: what is from it on, what is after it and what is before it
        assert _refreshed(overseeing, event["key"], 2) == everything[:i + 1]
        assert _feed(overseeing, limit=200, since=event["key"]) == everything[:i]
        assert _feed(overseeing, limit=200, before=event["key"]) == everything[i + 1:]
    stamp = everything[0]["at"]  # an instant alone: nothing of that instant is before or after it, and all of it is from it on
    assert _feed(overseeing, before=stamp) == [] and _feed(overseeing, since=stamp) == [] and _feed(overseeing, **{"from": stamp}) == everything


def _place(key: str) -> tuple[str, str, uuid.UUID]:
    at, kind, row = key.split("|")
    return at, kind, uuid.UUID(row)


@needs_test_database
def test_a_page_left_open_keeps_one_view_however_often_it_refreshes(overseeing):
    # the review of 2026-11-27: on an empty feed the refresh had no `since` to send, so each one, every ten seconds, was kept as a view
    page, floor = _first(overseeing, 50)
    assert page == [] and floor is None
    for _ in range(3):
        assert _refreshed(overseeing, floor, 200) == []
    assert _views(overseeing.engine) == ["/v1/oversight/activity"]
    _recorded(overseeing, dt.datetime.now(dt.timezone.utc))
    fresh = _refreshed(overseeing, floor, 200)
    assert len(fresh) == 1 and _refreshed(overseeing, fresh[0]["key"], 200) == fresh
    assert _views(overseeing.engine) == ["/v1/oversight/activity"]  # neither a read `since` a place nor one `from` a place is a view
    assert _feed(overseeing, before=fresh[0]["key"]) == []
    assert _views(overseeing.engine) == ["/v1/oversight/activity"] * 2  # "Show older" is one


@needs_test_database
def test_anyone_but_a_founder_is_answered_the_same_whatever_they_send(overseeing):
    # the review of 2026-11-27: the actor header and the parameters were read before the founder check, so a customer was answered
    # 422 where a founder's route would be and 404 elsewhere, which told them the page exists
    client = overseeing.client
    tries = [("/v1/oversight/activity", {}, {"X-Anisotropy-Actor": "nobody"}), ("/v1/oversight/weekly", {}, {"X-Anisotropy-Actor": "nobody"}),
             ("/v1/oversight/plans/not-a-uuid", {}, {}), (f"/v1/oversight/plans/{uuid.uuid4()}", {}, {"X-Anisotropy-Actor": "nobody"}),
             ("/v1/oversight/activity", {"limit": "abc"}, {}), ("/v1/oversight/activity", {"since": "yesterday"}, {}),
             ("/v1/oversight/activity", {"before": "x", "from": "y"}, {}), ("/v1/oversight/nothing-here", {}, {})]
    for who in (overseeing.customer, overseeing.robot):
        for path, params, headers in tries:
            answered = client.get(path, params=params, headers={**who, **headers})
            assert answered.status_code == 404 and answered.json() == {"detail": "Not Found"}, (path, params, headers)
    actor = client.headers.pop("X-Anisotropy-Actor")
    try:  # with no actor header at all
        for path in ("/v1/oversight/activity", "/v1/oversight/weekly", f"/v1/oversight/plans/{uuid.uuid4()}"):
            answered = client.get(path, headers=overseeing.customer)
            assert answered.status_code == 404 and answered.json() == {"detail": "Not Found"}, path
        assert client.get("/v1/oversight/activity", headers=overseeing.founder).status_code == 422  # a founder is still told what is missing
    finally:
        client.headers["X-Anisotropy-Actor"] = actor
    for path, params, headers in tries[:-1]:  # and a founder is told what is wrong with each
        assert client.get(path, params=params, headers={**overseeing.founder, **headers}).status_code == 422, (path, params, headers)
    # with no sign-in at all the sign-in answers, as it does on every route, before any route is looked for
    unsigned, elsewhere = client.get("/v1/oversight/activity"), client.get(f"/v1/projects/{uuid.uuid4()}")
    assert unsigned.status_code == elsewhere.status_code == 401 and unsigned.json() == elsewhere.json()
    assert _views(overseeing.engine) == []


@needs_test_database
def test_a_time_with_no_offset_is_refused_and_one_with_its_offset_is_read(overseeing):
    # the review of 2026-11-27: a time with no offset was read as UTC, whatever clock wrote it
    _recorded(overseeing, dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc))
    for name in ("since", "before", "from"):
        for value in ("2026-11-20T12:00:00", "2026-11-20", "2026-11-20T12:00:00|call", "2026-11-20T12:00:00+00:00|step|" + str(uuid.uuid4()),
                      "2026-11-20T12:00:00+00:00|call|not-a-uuid"):
            answered = overseeing.client.get("/v1/oversight/activity", params={name: value}, headers=overseeing.founder)
            assert answered.status_code == 422 and name in answered.json()["detail"] and "offset" in answered.json()["detail"], (name, value)
    assert len(_feed(overseeing, since="2026-11-20T11:59:59Z")) == 1 and _feed(overseeing, since="2026-11-20T13:00:00+01:00") == []
    assert len(_feed(overseeing, before="2026-11-20T14:00:00+01:00")) == 1 and _feed(overseeing, before="2026-11-20T04:00:00-08:00") == []
    with pytest.raises(ValueError, match="no offset"):
        oversight.cursor("2026-11-20T12:00:00")


@needs_test_database
@pytest.mark.parametrize(("sent", "kept"), [("x\u0000y", "x�y"), ("x\ud800y", "x�y"), (float("nan"), "nan")],
                         ids=["a NUL", "half a surrogate pair", "a number that is none"])
def test_a_turned_back_answer_the_database_cannot_hold_is_kept_cleaned_and_the_plan_is_the_same(overseeing, monkeypatch, sent, kept):
    # the review of 2026-11-27: the answers turned back are kept as the model wrote them, and Postgres takes no NUL, no half of a
    # surrogate pair and no NaN in JSON, so one such answer failed the engineer's request though the second answer was good
    told = ("state", "steps", "question", "unread", "reason")
    scripted(monkeypatch, BAD, GOOD)
    usual = _planned(overseeing.client, overseeing.customer)
    scripted(monkeypatch, {**BAD, "unread": [{"quote": sent, "reason": "not_offered"}]}, GOOD)
    theirs = _planned(overseeing.client, overseeing.customer)
    assert theirs["state"] == "proposed" and {key: theirs[key] for key in told} == {key: usual[key] for key in told}
    with Session(overseeing.engine) as session:
        attempts = session.get(AgentPlanRow, uuid.UUID(theirs["id"])).attempts
    assert len(attempts) == 1 and attempts[0]["plan"]["unread"] == [{"quote": kept, "reason": "not_offered"}]
    assert attempts[0]["plan"]["steps"] == BAD["steps"] and attempts[0]["reasons"][0].startswith("step 2: 2000")
    assert [c["outcome"] for c in _story(overseeing, theirs["id"])["calls"]] == ["turned back", "proposed"]


@needs_test_database
@pytest.mark.parametrize("sent", ["\u0000", "\ud800"], ids=["a NUL", "half a surrogate pair"])
def test_a_refusal_in_the_models_own_words_that_the_database_cannot_hold_is_still_answered(overseeing, monkeypatch, sent):
    said = plan(question=f"You want it clamped{sent} now")  # no question, so the model's words are the reason, and the reason is kept as text
    scripted(monkeypatch, said, said)
    theirs = _planned(overseeing.client, overseeing.founder)
    assert theirs["state"] == "refused" and theirs["reason"] == "You want it clamped� now"
    assert _story(overseeing, theirs["id"])["reason"] == theirs["reason"]


@needs_test_database
def test_every_table_of_the_week_starts_on_the_same_monday(overseeing):
    # the review of 2026-11-27: the week began eight weeks before the hour of the reading, so the oldest week of the plans and of the
    # unchecked calls was a part of a week beside the views' whole one
    def kept(month: int, day: int) -> None:
        when = dt.datetime(2026, month, day, 12, tzinfo=dt.timezone.utc)
        add_plan(overseeing.engine, kind="repair", project_id=None, user_email=None, actor="studio", ask="x", state="refused", steps=[], base="0" * 64,
                 question=None, unread=[], reason="r", writer="template", model=None, created_at=when, updated_at=when)
        record_model_calls(overseeing.engine, [_call(answered_at=when, model="claude-stand-in-1")], actor="studio", user_email=None, run_id=None,
                           checked_models={"claude-opus-5-5"})

    for month, day in ((10, 4), (10, 5), (10, 6), (10, 7), (10, 10)):  # a Sunday, then Monday, Tuesday, Wednesday and Saturday of the next week
        kept(month, day)
    for now in (dt.datetime(2026, 11, 27, 15, tzinfo=dt.timezone.utc), dt.datetime(2026, 11, 23, 0, tzinfo=dt.timezone.utc),
                dt.datetime(2026, 11, 29, 23, 59, tzinfo=dt.timezone.utc), dt.datetime(2026, 11, 30, 1, tzinfo=dt.timezone(dt.timedelta(hours=5)))):
        week = oversight.weekly(overseeing.engine, frozenset({FOUNDER}), now=now)  # a Friday, the week's first and last hours, another clock
        assert week["since"] == "2026-10-05", now
        assert week["plans"] == [{"week_of": "2026-10-05", "kind": "repair", "state": "refused", "plans": 4}]
        assert week["unchecked"] == [{"week_of": "2026-10-05", "model": "claude-stand-in-1", "calls": 4}]
        assert [(c["week_of"], c["calls"]) for c in week["costs"]] == [("2026-10-05", 4)] and week["refused"] == [{"reason": "r", "plans": 4}]
    later = oversight.weekly(overseeing.engine, frozenset({FOUNDER}), now=dt.datetime(2026, 11, 30, 0, tzinfo=dt.timezone.utc))
    assert later["since"] == "2026-10-12" and later["plans"] == [] and later["unchecked"] == [] and later["costs"] == []


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
