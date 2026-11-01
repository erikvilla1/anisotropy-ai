"""The runs table against a real PostgreSQL (ADR-0025, ADR-0026). Fixtures and the skip rule are in conftest.py."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
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
        actor="test", endpoint="/v1/cases/solve", status="solved", inputs={"case": {"units": "SI", "title": "t"}}, inputs_sha256="0" * 64,
        engine_version="0.1.0", api_version="0.1.0", response={"results": {"A": [[1.0]]}, "problems": []},
    )
    fields.update(overrides)
    return Run(**fields)


def test_migration_creates_the_table_with_every_column(engine):
    columns = {column["name"] for column in inspect(engine).get_columns("runs")}
    assert columns == {
        "id", "created_at", "actor", "endpoint", "status", "inputs", "inputs_sha256", "engine_version", "api_version",
        "git_commit", "response", "error", "supersedes_run_id", "llm_provider", "llm_model_version", "user_email",
    }
    assert {index["name"] for index in inspect(engine).get_indexes("runs")} == {
        "runs_created_at_idx", "runs_actor_idx", "runs_endpoint_idx",
    }


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


def test_migration_0003_renames_hermes_rows_and_keeps_the_trigger(engine):
    """A row written under the old actor name reads back under the new one; the old name is refused; rows stay immutable."""
    config = alembic_config(TEST_URL)
    command.downgrade(config, "0002")
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO runs (id, actor, endpoint, status, inputs, inputs_sha256, engine_version, api_version, response) "
                "VALUES (:id, 'hermes', '/v1/cases/solve', 'solved', '{}'::jsonb, :sha, '0.1.0', '0.1.0', '{}'::jsonb)"
            ), {"id": uuid.uuid4(), "sha": "0" * 64})
        command.upgrade(config, "head")
        with Session(engine) as session:
            stored = session.scalars(select(Run)).one()
            assert stored.actor == "founder-agent"
            session.add(solved_row(actor="hermes"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            stored = session.scalars(select(Run)).one()
            stored.actor = "test"
            with pytest.raises(DBAPIError, match="never edited or deleted"):
                session.commit()
            session.rollback()
    finally:
        command.upgrade(config, "head")


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


def test_migration_0005_undoes_cleanly_when_empty_and_refuses_over_an_email_or_the_browser_actor(engine):
    """The signed-in email and the actor `browser` (ADR-0026 amendment 1): the column goes and comes back on an empty table; with a
    row that carries either, the downgrade refuses, since rows are never rewritten."""
    config = alembic_config(TEST_URL)
    command.downgrade(config, "0004")
    assert "user_email" not in {column["name"] for column in inspect(engine).get_columns("runs")}
    command.upgrade(config, "head")
    assert "user_email" in {column["name"] for column in inspect(engine).get_columns("runs")}
    with Session(engine) as session:
        session.add(solved_row(user_email="engineer@example.com"))
        session.commit()
    with pytest.raises(RuntimeError, match="signed-in email"):
        command.downgrade(config, "0004")
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE runs CASCADE"))
    with Session(engine) as session:
        session.add(solved_row(actor="browser"))
        session.commit()
    with pytest.raises(RuntimeError, match="browser"):
        command.downgrade(config, "0004")
    assert "user_email" in {column["name"] for column in inspect(engine).get_columns("runs")}  # nothing was dropped
    with Session(engine) as session:
        assert session.scalar(select(Run.actor)) == "browser"  # and the row is as inserted


# ------------------------------------------------------------------------------------------ the jobs table (ADR-0050 amendment 2)

import datetime as _dt

from anisotropy_api.records import fetch_job, insert_job, list_jobs, stop_orphans, update_job


def _started(engine, job_id, process="p1", **fields):
    insert_job(engine, job_id=job_id, actor="test", user_email=fields.get("user_email"), inputs={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"},
               started_at=_dt.datetime.now(_dt.timezone.utc), process=process)


def test_migration_0006_creates_the_jobs_table_and_refuses_to_drop_it_over_rows(engine):
    assert {column["name"] for column in inspect(engine).get_columns("jobs")} == {
        "id", "actor", "user_email", "state", "stage", "stages_done", "stages", "coupon", "attempt", "message", "inputs", "outputs", "stored",
        "started_at", "finished_at", "run_id", "log_tail", "process",
    }
    assert {index["name"] for index in inspect(engine).get_indexes("jobs")} == {"jobs_started_at_idx", "jobs_state_idx"}
    config = alembic_config(TEST_URL)
    command.downgrade(config, "0005")
    assert not inspect(engine).has_table("jobs")
    command.upgrade(config, "head")
    _started(engine, uuid.uuid4())
    with pytest.raises(RuntimeError, match="holds 1 job"):
        command.downgrade(config, "0005")
    assert inspect(engine).has_table("jobs")


def test_the_jobs_table_keeps_each_status_and_a_new_process_marks_the_jobs_a_stopped_one_left(engine):
    first, second = uuid.uuid4(), uuid.uuid4()
    _started(engine, first, user_email="engineer@example.com")
    _started(engine, second)
    assert fetch_job(engine, first).state == "running" and fetch_job(engine, first).user_email == "engineer@example.com"
    update_job(engine, first, state="done", stage="the outputs", stages_done=["the setup check"], stages=["the setup check", "the outputs"],
               coupon="IM7-UNT-L1", attempt=".local/fea/IM7-UNT-L1/ours/runs/attempt-02_2026-10-30", message="57 of 57", outputs={"fields": "x.json"},
               stored={"fields": "coupons/IM7-UNT-L1/attempt-02_2026-10-30/files/fields/x.json"}, finished_at=_dt.datetime.now(_dt.timezone.utc), log_tail=["Done"])
    assert stop_orphans(engine, "the API stopped while this job ran") == 1  # only the one still running
    done, stopped = fetch_job(engine, first), fetch_job(engine, second)
    assert done.state == "done" and done.stored["fields"].startswith("coupons/") and done.log_tail == ["Done"] and done.finished_at is not None
    assert stopped.state == "stopped" and stopped.message == "the API stopped while this job ran" and stopped.finished_at is not None
    assert [row.id for row in list_jobs(engine)] == [second, first]  # newest first
    with pytest.raises(LookupError):
        update_job(engine, uuid.uuid4(), state="done")
    with pytest.raises(DBAPIError):
        update_job(engine, first, state="weird")
    assert fetch_job(engine, uuid.uuid4()) is None


def test_the_api_marks_a_stopped_processs_job_at_startup_and_serves_it_from_the_table(engine, monkeypatch):
    orphan = uuid.uuid4()
    _started(engine, orphan, process="an earlier process")
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "test"}) as client:
        status = client.get(f"/v1/coupon-jobs/{orphan}").json()
        assert status["state"] == "stopped" and "stopped while this job ran" in status["message"] and status["outputs"] == {}
        assert status["actor"] == "test" and status["log_tail"] == [] and status["finished_at"] is not None
        assert [job["job_id"] for job in client.get("/v1/coupon-jobs").json()] == [str(orphan)]
        assert client.get(f"/v1/coupon-jobs/{orphan}/package").status_code == 409
        assert client.get(f"/v1/coupon-jobs/{uuid.uuid4()}").status_code == 404
