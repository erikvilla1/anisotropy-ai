"""What each call to the language model cost, and who asked (ADR-0120): the price of a call from the usage block its response carries,
the writers carrying their call whatever became of the answer, the row each call leaves with its run and the signed-in email, the
three views and the report. A stub plays the model, as api/tests/test_assistant.py does; nothing here calls one."""

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from anisotropy_api import access
from anisotropy_api.assistant import ClaudeAssistant
from anisotropy_api.cost_report import report, table
from anisotropy_api.main import MODEL_COST_HEADER, app
from anisotropy_api.model_costs import FEATURES, PRICES_AS_OF, measure
from anisotropy_api.records import ModelCallRow, record_model_calls
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, alembic_config, needs_test_database
from test_assistant import FACTS, TEMPLATE
from test_laminate_problems import homework


def usage(input_tokens=3000, output_tokens=900, thinking=700, **more):
    details = SimpleNamespace(thinking_tokens=thinking) if thinking is not None else None
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, output_tokens_details=details, cache_read_input_tokens=0,
                           cache_creation_input_tokens=0, cache_creation=None, iterations=None, inference_geo=None, speed=None, **more)


def answer(text="The top grip carries 16211 N.", model="claude-opus-5-5", stop_reason="end_turn", used=None):
    return SimpleNamespace(model=model, stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)] if text else [],
                           usage=usage() if used is None else used)


class Billing:
    """The client the Claude writer calls, answering with the responses given, in turn."""

    def __init__(self, *responses):
        self.responses = list(responses)
        outer = self

        class Messages:
            def create(self, **kwargs):
                return outer.responses.pop(0)

        self.beta = SimpleNamespace(messages=Messages())


# --------------------------------------------------------------------------------------------- the price of one call

def test_a_call_is_priced_from_the_tokens_its_response_reports():
    call = measure("explain_result", "claude-opus-5-5", "low", answer(), "The top grip carries 16211 N.", 1.23456)
    # 3000 input tokens at 4 USD and 900 output tokens at 20 USD per million: 0.012 + 0.018
    assert call.cost_usd == Decimal("0.030000") and call.prices_as_of == PRICES_AS_OF
    assert (call.feature, call.model, call.effort, call.input_tokens, call.output_tokens, call.thinking_tokens) == \
        ("explain_result", "claude-opus-5-5", "low", 3000, 900, 700)
    assert call.answer_characters == len("The top grip carries 16211 N.") and call.stop_reason == "end_turn" and call.seconds == 1.235
    assert call.attempts is None and call.answered_at.tzinfo is not None


def test_cache_tokens_are_priced_by_how_long_they_are_kept():
    used = usage(input_tokens=100, output_tokens=10, thinking=None)
    used.cache_read_input_tokens, used.cache_creation_input_tokens = 2000, 1000
    used.cache_creation = SimpleNamespace(ephemeral_5m_input_tokens=600, ephemeral_1h_input_tokens=400)
    call = measure("propose_changes", "claude-opus-5-5", "low", answer(used=used), "{}", 0.5)
    # 100 x 4 + 600 x 5 + 400 x 8 + 2000 x 0.20 + 10 x 20 = 400 + 3000 + 3200 + 400 + 200 = 7200 per million
    assert call.cost_usd == Decimal("0.007200") and call.cache_write_tokens == 1000 and call.cache_read_tokens == 2000 and call.thinking_tokens is None


def test_a_refusal_then_a_fallback_counts_each_attempt_at_its_own_models_prices():
    used = usage(input_tokens=412, output_tokens=264, thinking=100)
    used.iterations = [SimpleNamespace(type="message", model=None, input_tokens=535, output_tokens=0, cache_read_input_tokens=0, cache_creation_input_tokens=0),
                       SimpleNamespace(type="fallback_message", model="claude-opus-5", input_tokens=412, output_tokens=264, cache_read_input_tokens=0,
                                       cache_creation_input_tokens=0)]
    call = measure("answer_question", "claude-opus-5-5", "low", answer(model="claude-opus-5", used=used), "{}", 2.0)
    # the declined attempt: 535 x 4; the fallback that answered: 412 x 5 + 264 x 25; the top-level block is the fallback's, not added again
    assert call.cost_usd == Decimal("0.010800") and call.input_tokens == 947 and call.output_tokens == 264 and call.model == "claude-opus-5"
    assert [a["model"] for a in call.attempts] == ["claude-opus-5-5", "claude-opus-5"] and call.attempts[0]["type"] == "message"


def test_a_long_prompt_a_us_only_call_fast_mode_and_an_unknown_model():
    long = measure("read_question", "claude-haiku-5-5", "low", answer(model="claude-haiku-5-5", used=usage(150_000, 1000, None)), "{}", 1.0)
    assert long.cost_usd == Decimal("0.077500")  # over 100,000 prompt tokens: 150,000 x 0.50 + 1000 x 2.50 per million
    short = measure("read_question", "claude-haiku-5-5", "low", answer(model="claude-haiku-5-5", used=usage(90_000, 1000, None)), "{}", 1.0)
    assert short.cost_usd == Decimal("0.009500")  # 90,000 x 0.10 + 1000 x 0.50
    us = usage()
    us.inference_geo = "us"
    assert measure("explain_result", "claude-opus-5-5", "low", answer(used=us), "", 1.0).cost_usd == Decimal("0.033000")
    fast = usage()
    fast.speed = "fast"
    unpriced = measure("explain_result", "claude-opus-5-5", "low", answer(used=fast), "", 1.0)
    assert unpriced.cost_usd is None and unpriced.prices_as_of is None and unpriced.output_tokens == 900
    other = measure("explain_result", "claude-unlisted-9", "low", answer(model="claude-unlisted-9"), "", 1.0)
    assert other.cost_usd is None and other.model == "claude-unlisted-9"


def test_no_usage_block_is_no_call_and_an_unknown_feature_is_refused():
    assert measure("explain_result", "m", "low", SimpleNamespace(model="m", stop_reason="end_turn", content=[]), "", 0.1) is None
    with pytest.raises(ValueError, match="unknown feature"):
        measure("translate", "m", "low", answer(), "", 0.1)


# --------------------------------------------------------------------------------------------- the writers carry their call

def test_every_writer_carries_its_call_whatever_became_of_the_answer():
    kept = ClaudeAssistant("claude-opus-5-5", client=Billing(answer("The top grip carries 16211 N."))).explain_result(FACTS, TEMPLATE)
    assert kept.writer == "anthropic" and kept.call.feature == "explain_result" and kept.call.cost_usd == Decimal("0.030000")
    withheld = ClaudeAssistant("claude-opus-5-5", client=Billing(answer("A 10.4 % margin."))).explain_result(FACTS, TEMPLATE)
    assert withheld.withheld and withheld.call is not None  # set aside by the guard, and still billed
    refused = ClaudeAssistant("claude-opus-5-5", client=Billing(answer("", stop_reason="refusal"))).read_question({"message": "?"}, {})
    assert refused.raw is None and refused.call.feature == "read_question" and refused.call.answer_characters == 0
    cut = ClaudeAssistant("claude-opus-5-5", client=Billing(answer('{"a"', stop_reason="max_tokens"))).propose({"message": "x"})
    assert cut.raw is None and cut.call.stop_reason == "max_tokens" and cut.call.feature == "propose_changes"
    words = ClaudeAssistant("claude-opus-5-5", client=Billing(answer('{"prose": "x"}'))).answer_question({"question": "why"}, {})
    assert words.call.feature == "answer_question"


def test_a_call_that_never_answered_carries_none():
    import anthropic
    import httpx2

    class Down:
        beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(
            anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")))))

    draft = ClaudeAssistant("claude-opus-5-5", client=Down()).explain_result(FACTS, TEMPLATE)
    assert draft.writer == "template" and draft.call is None


def test_the_features_are_the_ones_the_migration_allows():
    from importlib import util
    from pathlib import Path

    # the last migration to name them: 0013 made the table, 0017 added the planner's `plan_steps` (ADR-0144)
    spec = util.spec_from_file_location("m0017", Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0017_agent_plans.py")
    migration = util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.FEATURES == FEATURES  # a new feature is a new migration (ADR-0120)


def test_the_report_table_aligns_its_columns():
    lines = table(["person", "calls", "cost USD"], [("a@example.com", 3, Decimal("0.012000")), ("b", 12, None)]).splitlines()
    assert lines[0] == "person         calls  cost USD" and lines[2] == "a@example.com      3  0.012000" and lines[3].endswith("12         -")


# --------------------------------------------------------------------------------------------- the table, its views and the API

def _call(feature="explain_result", **changes):
    fields = dict(model="claude-opus-5-5", effort="low", input_tokens=3000, output_tokens=900, thinking_tokens=700, cache_read_tokens=0,
                  cache_write_tokens=0, answer_characters=120, stop_reason="end_turn", seconds=1.0, cost_usd=Decimal("0.030000"),
                  prices_as_of=PRICES_AS_OF, attempts=None, answered_at=dt.datetime(2026, 11, 18, 12, tzinfo=dt.timezone.utc))
    fields.update(changes)
    return SimpleNamespace(feature=feature, **fields)


@needs_test_database
def test_the_migration_makes_the_table_and_its_views_and_refuses_to_drop_them_over_a_row(empty_runs):
    engine = empty_runs
    columns = [column["name"] for column in inspect(engine).get_columns("model_calls")]
    assert columns == ["id", "called_at", "user_email", "actor", "feature", "model", "effort", "input_tokens", "output_tokens", "thinking_tokens",
                       "cache_read_tokens", "cache_write_tokens", "answer_characters", "stop_reason", "seconds", "cost_usd", "prices_as_of",
                       "run_id", "attempts"]
    assert set(inspect(engine).get_view_names()) >= {"model_costs_by_person", "model_costs_by_feature", "model_costs_by_day"}
    config = alembic_config(TEST_URL)
    command.downgrade(config, "0012")
    assert not inspect(engine).has_table("model_calls") and "model_costs_by_day" not in inspect(engine).get_view_names()
    command.upgrade(config, "head")
    record_model_calls(engine, [_call()], actor="test", user_email=None, run_id=None)
    with pytest.raises(RuntimeError, match="holds 1 call"):
        command.downgrade(config, "0012")
    assert inspect(engine).has_table("model_calls")
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))


@needs_test_database
def test_the_views_add_up_by_person_feature_and_day_and_flag_a_jump(empty_runs):
    engine = empty_runs
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))
    week = dt.timedelta(weeks=1)
    monday = dt.datetime(2026, 11, 16, 9, tzinfo=dt.timezone.utc)
    usual = [_call(answered_at=monday - k * week) for k in (1, 2, 3, 4)]  # one call a week at 0.03 USD, 700 of 900 thinking
    this_week = [_call(answered_at=monday, cost_usd=Decimal("0.050000")), _call("answer_question", answered_at=monday, cost_usd=None, prices_as_of=None)]
    record_model_calls(engine, usual + this_week[:1], actor="browser", user_email=EMAIL, run_id=None)
    record_model_calls(engine, this_week[1:], actor="assistant", user_email=None, run_id=None)
    with engine.connect() as connection:
        people = connection.execute(text("SELECT person, calls, cost_usd, unpriced_calls, features FROM model_costs_by_person "
                                         "WHERE month = '2026-11'")).all()
        weekly = connection.execute(text("SELECT feature, calls, cost_per_call_usd, usual_cost_per_call_usd, thinking_share_pct, flag "
                                         "FROM model_costs_by_feature WHERE week_of = '2026-11-16' ORDER BY feature")).all()
        first = connection.execute(text("SELECT flag FROM model_costs_by_feature WHERE week_of = '2026-10-19'")).scalar_one()
        days = connection.execute(text("SELECT day, model, calls, cost_usd FROM model_costs_by_day WHERE day = '2026-11-16'")).all()
    # November holds the weeks of the 2nd, 9th and 16th for Erik's email (three calls), and the MCP server's unpriced one
    # sorted here, not by the database: how "(" sorts against a letter depends on the database's collation (C here, en_US on CI)
    assert sorted(tuple(row) for row in people) == [("(no sign-in: assistant)", 1, None, 1, "answer_question"),
                                              (EMAIL, 3, Decimal("0.110000"), 0, "explain_result")]
    assert [tuple(row) for row in weekly] == [
        ("answer_question", 1, None, None, Decimal("77.8"), "no earlier week to compare with"),
        ("explain_result", 1, Decimal("0.050000"), Decimal("0.030000"), Decimal("77.8"), "look: cost per call more than 30% above the usual"),
    ]
    assert first == "no earlier week to compare with"
    assert [tuple(row) for row in days] == [(dt.date(2026, 11, 16), "claude-opus-5-5", 2, Decimal("0.050000"))]
    text_report = report(engine, "2026-11", 2)
    assert EMAIL in text_report and "(no sign-in: assistant)" in text_report and "look: cost per call" in text_report
    assert "Total: 4 call(s), 0.110000 USD, and 1 call(s) of a model not on the price list." in text_report
    assert "1 week(s) flagged" in text_report
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))
    assert "No calls to the model were recorded this month." in report(engine, "2026-11", 2)


@needs_test_database
def test_a_cleared_run_leaves_its_calls_with_the_link_empty(empty_runs):
    engine = empty_runs
    with engine.begin() as connection:
        run_id = connection.execute(text("INSERT INTO runs (id, actor, endpoint, status, inputs, inputs_sha256, engine_version, api_version, response) "
                                         "VALUES (gen_random_uuid(), 'test', '/x', 'solved', '{}', :d, '0', '0', '{}') RETURNING id"), {"d": "0" * 64}).scalar_one()
    record_model_calls(engine, [_call()], actor="test", user_email=None, run_id=run_id)
    with engine.begin() as connection:  # the one clearing of trial runs switches the trigger off as ADR-0026 amendment 2 does
        connection.execute(text("ALTER TABLE runs DISABLE TRIGGER runs_immutable"))
        connection.execute(text("DELETE FROM runs"))
        connection.execute(text("ALTER TABLE runs ENABLE TRIGGER runs_immutable"))
    with Session(engine) as session:
        [row] = session.scalars(select(ModelCallRow)).all()
        assert row.run_id is None and row.cost_usd == Decimal("0.030000")
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))


@pytest.fixture
def signed_in(empty_runs, monkeypatch):
    """The API behind Cloudflare Access with run records on, as the hosted site runs."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with empty_runs.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        yield client
    with empty_runs.begin() as connection:
        connection.execute(text("TRUNCATE model_calls"))


@needs_test_database
def test_each_call_is_written_with_the_signed_in_email_the_client_and_the_run(signed_in, empty_runs):
    before = app.state.assistant
    app.state.assistant = ClaudeAssistant("claude-opus-5-5", client=Billing(answer("The laminate holds the load.")))
    try:
        answered = signed_in.post("/v1/laminates/solve", json=homework(), headers={access.HEADER: token(email=EMAIL)})
    finally:
        app.state.assistant = before
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["writer"] == "anthropic" and "cost_usd" not in answered.text and "thinking_tokens" not in answered.text  # ours to read, not the page's
    with Session(empty_runs) as session:
        [row] = session.scalars(select(ModelCallRow)).all()
    assert (row.user_email, row.actor, row.feature, row.model, str(row.run_id)) == (EMAIL, "browser", "explain_laminate", "claude-opus-5-5", body["run_id"])
    assert row.cost_usd == Decimal("0.030000") and row.thinking_tokens == 700 and row.answer_characters == len("The laminate holds the load.")


@needs_test_database
def test_a_request_with_no_model_call_writes_no_row(signed_in, empty_runs):
    answered = signed_in.post("/v1/laminates/solve", json=homework(), headers={access.HEADER: token(email=EMAIL)})
    assert answered.status_code == 200 and answered.json()["writer"] == "template"
    with empty_runs.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM model_calls")).scalar_one() == 0


# ------------------------------------------------------------------- the cost on the answer, to a service token only (ADR-0138)

def _explained(headers: dict[str, str], *, behind_access: bool):
    """A laminate explained by the stub model, behind Access or not, with no records kept: the answer as the client sees it."""
    before = getattr(app.state, "assistant", None), getattr(app.state, "access_verifier", None)
    app.state.assistant = ClaudeAssistant("claude-opus-5-5", client=Billing(answer("The laminate holds the load.")))
    app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for) if behind_access else None
    try:
        return TestClient(app, headers={"X-Anisotropy-Actor": "test"}).post("/v1/laminates/solve", json=homework(), headers=headers)
    finally:
        app.state.assistant, app.state.access_verifier = before


def test_a_service_tokens_answer_carries_what_its_calls_cost():
    answered = _explained({access.HEADER: service_token()}, behind_access=True)
    assert answered.status_code == 200, answered.text
    assert answered.headers[MODEL_COST_HEADER] == "0.030000; calls=1; unpriced=0"  # 3000 in and 900 out at opus's prices


def test_a_signed_in_persons_answer_never_carries_it():
    answered = _explained({access.HEADER: token(email=EMAIL)}, behind_access=True)
    assert answered.status_code == 200, answered.text
    assert MODEL_COST_HEADER not in answered.headers and answered.json()["writer"] == "anthropic"


def test_with_access_off_the_local_answer_carries_it_and_a_request_with_no_call_does_not():
    assert _explained({}, behind_access=False).headers[MODEL_COST_HEADER] == "0.030000; calls=1; unpriced=0"
    plain = TestClient(app, headers={"X-Anisotropy-Actor": "test"}).post("/v1/laminates/solve", json=homework())
    assert plain.status_code == 200 and MODEL_COST_HEADER not in plain.headers
