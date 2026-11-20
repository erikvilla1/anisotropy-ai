"""The read-only login for the model-cost views (scripts/create-cost-reader.py, ADR-0120 amendment 1), against the test database: it
reads the three views and nothing else, writes nothing, and a second run gives it a new password that replaces the old one."""

import datetime as dt
import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError

from anisotropy_api.model_costs import PRICES_AS_OF, ModelCall
from anisotropy_api.records import record_model_calls
from conftest import TEST_URL, needs_test_database

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "create-cost-reader.py"
_spec = importlib.util.spec_from_file_location("create_cost_reader", SCRIPT)
reader_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reader_script)

ROLE = "cost_reader_test"  # not the hosted name, so a test never touches a real reader on a shared server


def _engine(address: str):
    return create_engine(make_url(address).set(drivername="postgresql+psycopg"))


@pytest.fixture
def database(empty_runs):
    yield empty_runs
    with empty_runs.begin() as connection:
        if connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": ROLE}).first():
            connection.execute(text(f"DROP OWNED BY {ROLE}"))  # its grants, here and on the database
            connection.execute(text(f"DROP ROLE {ROLE}"))
        connection.execute(text("TRUNCATE model_calls"))


@needs_test_database
def test_the_reader_reads_the_three_views_and_nothing_else(database):
    call = ModelCall(feature="explain_result", answered_at=dt.datetime(2026, 11, 19, 18, tzinfo=dt.timezone.utc), model="claude-opus-5-5",
                     effort="low", input_tokens=3000, output_tokens=900, thinking_tokens=700, cache_read_tokens=0, cache_write_tokens=0,
                     answer_characters=720, stop_reason="end_turn", seconds=8.0, cost_usd=Decimal("0.030000"), prices_as_of=PRICES_AS_OF)
    record_model_calls(database, [call], actor="browser", user_email="engineer@example.com", run_id=None)
    address = reader_script.reader_address(TEST_URL, ROLE, reader_script.grant_reader(database, ROLE))
    assert address.startswith(f"postgresql://{ROLE}:")
    reader = _engine(address)
    try:
        with reader.connect() as connection:
            assert connection.execute(text("SELECT person, calls, cost_usd FROM model_costs_by_person")).all() == [
                ("engineer@example.com", 1, Decimal("0.030000"))]
            assert connection.execute(text("SELECT count(*) FROM model_costs_by_feature")).scalar_one() == 1
            assert connection.execute(text("SELECT cost_usd FROM model_costs_by_day")).scalar_one() == Decimal("0.030000")
        for table in ("model_calls", "runs", "jobs", "projects"):
            with reader.connect() as connection, pytest.raises(DBAPIError, match="permission denied"):
                connection.execute(text(f"SELECT * FROM {table}"))
        for statement in ("CREATE TABLE reader_was_here (a int)", "DELETE FROM model_calls", "REFRESH MATERIALIZED VIEW model_costs_by_day"):
            with reader.connect() as connection, pytest.raises(DBAPIError, match="read-only transaction|permission denied|is not a"):
                connection.execute(text(statement))
    finally:
        reader.dispose()


@needs_test_database
def test_a_second_run_gives_a_new_password_and_the_old_one_stops_working(database):
    first = reader_script.reader_address(TEST_URL, ROLE, reader_script.grant_reader(database, ROLE))
    second = reader_script.reader_address(TEST_URL, ROLE, reader_script.grant_reader(database, ROLE))
    assert first != second
    old, new = _engine(first), _engine(second)
    try:
        with pytest.raises(OperationalError, match="password authentication failed"):
            old.connect()
        with new.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM model_costs_by_person")).scalar_one() == 0
    finally:
        old.dispose()
        new.dispose()


def test_a_role_name_that_is_not_a_plain_name_is_refused():
    with pytest.raises(ValueError, match="lowercase letters"):
        reader_script.grant_reader(None, "x; DROP TABLE runs")  # refused before any connection
