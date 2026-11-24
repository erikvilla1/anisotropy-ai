"""The one clearing of the hosted tier's trial records (scripts/clear-hosted-trials.py, ADR-0026 amendment 2), against the test
database and a store in memory: what goes, what stays, and every refusal changing nothing."""

import datetime as dt
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from anisotropy_api.records import (fetch_upload, insert_job, insert_pairing_code, insert_qa_checks, insert_upload, insert_upload_token, record_run,
                                    update_job, update_project, upsert_project)
from conftest import needs_test_database

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "clear-hosted-trials.py"
_spec = importlib.util.spec_from_file_location("clear_hosted_trials", SCRIPT)
clear = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clear)

pytestmark = needs_test_database
NOW = dt.datetime(2026, 11, 18, 21, 0, tzinfo=dt.timezone.utc)
CONFIRM = clear.CONFIRMATION


class MemoryStore:
    def __init__(self, keys):
        self.held = {key: len(key) for key in keys}

    def objects(self, prefix):
        return {key: size for key, size in self.held.items() if key.startswith(prefix)}

    def delete(self, key):
        self.held.pop(key, None)


KEYS = ["coupons/OLD-1/folder/README.md", "owners/" + "a" * 32 + "/coupons/IM7-UNT-L1/001/package.zip", "jobs/x/input/values.json",
        "uploads/u/bundle.zip", "elsewhere/kept.txt"]


def _run(engine, email=None, actor="browser"):
    return record_run(engine, actor=actor, endpoint="/v1/coupon-jobs", inputs={"n": str(uuid.uuid4())}, engine_version="1", api_version="1",
                      git_commit=None, response={"ok": True}, user_email=email)


@pytest.fixture
def filled(empty_runs):
    engine = empty_runs
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM projects"))
    first = _run(engine, "one@example.com")
    _run(engine, "two@example.com")
    _run(engine, None, "test")
    project, _ = upsert_project(engine, project_id=uuid.uuid4(), kind="fea", name="trial", actor="browser", user_email="one@example.com",
                                content={"form": {}}, form_version=None, units=None, now=NOW)
    update_project(engine, project.id, last_check_run_id=first)
    job = uuid.uuid4()
    insert_job(engine, job_id=job, actor="browser", user_email="one@example.com", inputs={}, started_at=NOW, process="p", project_id=project.id)
    update_job(engine, job, state="done", run_id=first, finished_at=NOW)
    insert_qa_checks(engine, job, [{"position": 0, "layer": "fea", "check_id": "FEA-SECOND-SOLVER", "version": 1, "verdict": "warn", "label": "Second solver",
                                    "message": "52 of 57", "evidence": {}, "basis": "ADR-0030"}], NOW)  # the job's QA record (ADR-0137)
    token = insert_upload_token(engine, token_id=uuid.uuid4(), actor="browser", user_email="one@example.com", name="PC", token_sha256="f" * 64,
                                hint="abcd", now=NOW)
    insert_pairing_code(engine, code_id=uuid.uuid4(), actor="browser", user_email="one@example.com", code_sha256="e" * 64, now=NOW,
                        expires_at=NOW + dt.timedelta(minutes=10))
    upload = insert_upload(engine, id=uuid.uuid4(), actor="browser", user_email="one@example.com", token_id=token.id, created_at=NOW,
                           bundle_sha256="d" * 64, bundle_bytes=10, object_key="uploads/u/bundle.zip", units="SI (mm)", job="Job-1",
                           coupon="IM7-UNT-L1", in_scope=True, facts={}, job_id=job, verdict="agrees", comparison={"rows": []}, compared_at=NOW)
    return engine, upload.id


def test_count_gives_counts_only_and_changes_nothing(filled):
    engine, _ = filled
    store = MemoryStore(KEYS)
    report = clear.count(engine, store)
    assert report["rows"] == {"runs": 3, "jobs": 1, "projects": 1, "abaqus_uploads": 1, "upload_tokens": 1, "pairing_codes": 1}
    assert report["people"] == {"runs": 2, "jobs": 1, "projects": 1} and report["no_email"]["runs"] == 1
    assert report["busy_jobs"] == 0 and report["uploads_linked_to_a_job"] == 1
    assert report["objects"]["owners/"]["files"] == 1 and report["objects"]["(whole bucket)"]["files"] == 5
    assert "@" not in repr(report)
    assert clear.count(engine, store)["rows"] == report["rows"] and len(store.held) == 5


def test_delete_clears_runs_jobs_projects_and_their_files_and_keeps_the_uploads_and_the_connector(filled):
    engine, upload_id = filled
    store = MemoryStore(KEYS)
    report = clear.delete(engine, store, {"runs": 3, "jobs": 1, "projects": 1}, CONFIRM)
    assert report["rows_now"] == {"runs": 0, "jobs": 0, "projects": 0, "abaqus_uploads": 1, "upload_tokens": 1, "pairing_codes": 1}
    assert report["uploads_unlinked"] == 1 and report["deleted_files"] == 3
    assert report["files_left"] == {"coupons/": 0, "owners/": 0, "jobs/": 0}
    assert sorted(store.held) == ["elsewhere/kept.txt", "uploads/u/bundle.zip"]
    kept = fetch_upload(engine, upload_id)
    assert kept.job_id is None and kept.verdict == "agrees" and kept.comparison == {"rows": []}
    # The trigger is back on: a run is again never deleted one by one.
    run_id = _run(engine)
    with pytest.raises(Exception, match="never edited or deleted"), engine.begin() as connection:
        connection.execute(text("DELETE FROM runs WHERE id = :id"), {"id": run_id})
    # The jobs' QA checks went with them, and their trigger is back on too (ADR-0137).
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM qa_checks")).scalar_one() == 0
        assert connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgname = 'qa_checks_immutable'")).scalar_one() == "O"


@pytest.mark.parametrize("expected, confirmation, busy, words", [
    ({"runs": 4, "jobs": 1, "projects": 1}, CONFIRM, False, "not the"),
    ({"runs": 3, "jobs": 1, "projects": 1}, "yes", False, "Type the confirmation"),
    ({"runs": 3, "jobs": 2, "projects": 1}, CONFIRM, True, "queued or running"),
])
def test_delete_refuses_and_changes_nothing(filled, expected, confirmation, busy, words):
    engine, _ = filled
    if busy:
        insert_job(engine, job_id=uuid.uuid4(), actor="browser", user_email=None, inputs={}, started_at=NOW, process="p", state="queued")
    before = clear.count(engine, MemoryStore(KEYS))["rows"]
    store = MemoryStore(KEYS)
    with pytest.raises(clear.Refused, match=words):
        clear.delete(engine, store, expected, confirmation)
    assert clear.count(engine, store)["rows"] == before and len(store.held) == 5


def test_expect_names_each_cleared_table_once():
    assert clear.parse_expect("runs=373, jobs=27,projects=40") == {"runs": 373, "jobs": 27, "projects": 40}
    for bad in ("runs=1,jobs=2", "runs=1,jobs=2,projects=x", "runs=1,jobs=2,projects=3,uploads=1"):
        with pytest.raises(Exception, match="--expect"):
            clear.parse_expect(bad)
