"""The runs table against a real PostgreSQL (ADR-0025, ADR-0026). Fixtures and the skip rule are in conftest.py."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from anisotropy_api.main import app
from anisotropy_api.records import ACTORS, Run, check_ready, connect
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE
from conftest import TEST_URL, alembic_config, needs_test_database

pytestmark = needs_test_database


@pytest.fixture
def engine(empty_runs):
    return empty_runs


def solved_row(**overrides) -> Run:
    fields = dict(
        actor="test", status="solved", inputs={"case": {"units": "SI", "title": "t"}}, inputs_sha256="0" * 64,
        engine_version="0.1.0", api_version="0.1.0", response={"results": {"A": [[1.0]]}, "problems": []},
    )
    fields.update(overrides)
    return Run(**fields)


def test_migration_creates_the_table_with_every_column(engine):
    columns = {column["name"] for column in inspect(engine).get_columns("runs")}
    assert columns == {
        "id", "created_at", "actor", "status", "inputs", "inputs_sha256", "engine_version", "api_version",
        "git_commit", "response", "error", "supersedes_run_id", "llm_provider", "llm_model_version",
    }
    assert {index["name"] for index in inspect(engine).get_indexes("runs")} == {"runs_created_at_idx", "runs_actor_idx"}


def test_a_solved_run_round_trips(engine):
    with Session(engine) as session:
        run = solved_row()
        session.add(run)
        session.commit()
        run_id = run.id
    with Session(engine) as session:
        stored = session.get(Run, run_id)
        assert stored.created_at.tzinfo is not None
        assert stored.inputs == {"case": {"units": "SI", "title": "t"}}
        assert stored.response == {"results": {"A": [[1.0]]}, "problems": []}
        assert stored.error is None and stored.llm_provider is None


def test_a_rejected_run_stores_the_error_and_no_response(engine):
    with Session(engine) as session:
        session.add(solved_row(status="rejected", response=None, error="laminate: plies must not be empty"))
        session.commit()
        stored = session.scalars(select(Run)).one()
        assert stored.status == "rejected" and stored.response is None


@pytest.mark.parametrize("bad", [
    dict(actor="somebody"),
    dict(status="pending"),
    dict(status="solved", response=None),
    dict(status="rejected", error=None),
    dict(status="rejected", error="x"),  # a rejected run must not carry a response
])
def test_constraints_reject_inconsistent_rows(engine, bad):
    with Session(engine) as session:
        session.add(solved_row(**bad))
        with pytest.raises(IntegrityError):
            session.commit()


def test_rows_are_never_edited_or_deleted(engine):
    with Session(engine) as session:
        run = solved_row()
        session.add(run)
        session.commit()
        run.actor = ACTORS[0]
        with pytest.raises(DBAPIError, match="never edited or deleted"):
            session.commit()
        session.rollback()
        session.delete(session.get(Run, run.id))
        with pytest.raises(DBAPIError, match="never edited or deleted"):
            session.commit()
        session.rollback()
        assert session.scalars(select(Run)).one().actor == "test"


def test_a_correction_is_a_new_run_naming_the_old_one(engine):
    with Session(engine) as session:
        first = solved_row()
        session.add(first)
        session.commit()
        session.add(solved_row(supersedes_run_id=first.id))
        session.commit()
        session.add(solved_row(supersedes_run_id=uuid.uuid4()))
        with pytest.raises(IntegrityError):
            session.commit()


def test_check_ready_needs_the_table(engine):
    check_ready(engine)
    command.downgrade(alembic_config(TEST_URL), "base")
    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            check_ready(engine)
    finally:
        command.upgrade(alembic_config(TEST_URL), "head")


def test_check_ready_names_an_unreachable_server_without_the_password():
    engine = connect("postgresql+psycopg://anisotropy:secret-word@127.0.0.1:1/anisotropy")
    with pytest.raises(RuntimeError, match="Cannot reach") as excinfo:
        check_ready(engine)
    assert "secret-word" not in str(excinfo.value)


def test_api_starts_with_records_on_and_a_migrated_database(engine, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app) as client:
        assert client.get("/v1/materials").status_code == 200
        assert app.state.settings.run_records is True
        assert app.state.records is not None
    assert app.state.records is None  # released at shutdown


def test_api_starts_with_records_explicitly_off(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    with TestClient(app) as client:
        assert client.get("/v1/materials").status_code == 200
        assert app.state.records is None


def test_api_refuses_to_start_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, "postgresql+psycopg://anisotropy:x@127.0.0.1:1/anisotropy")
    with pytest.raises(RuntimeError, match="Cannot reach"):
        with TestClient(app):
            pass
