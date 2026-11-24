"""The QA record (ADR-0137): a done job's checks are written once into `qa_checks` from the QA file its tool wrote, never edited or
deleted, and served with the run's verdict to the job's owner alone, in the same 404 as for no job (ADR-0104). A stand-in here plays
the tool; its `--run-by` chooses what it writes, so these tests need neither CalculiX nor the fea environment."""

import json
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from anisotropy_api import access
from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import app, job_recorder
from anisotropy_api.records import QARecordError, fetch_qa_checks, insert_qa_checks, qa_counts, qa_rows, qa_verdict
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from test_coupon_jobs_api import form_request

OTHER = "other.engineer@example.com"
GONE = "These results are no longer available. Run the analysis again from your project."
CHECKS = [
    {"layer": "data", "check": "DATA-UNITS", "version": 1, "verdict": "pass", "label": "Units consistent", "message": "every value in mm-MPa",
     "evidence": {"state": "pass", "rows": []}, "basis": "ADR-0002"},
    {"layer": "fea", "check": "FEA-SECOND-SOLVER", "version": 1, "verdict": "warn", "label": "Second solver agrees",
     "message": "52 of 57 compared values agree with the second solver within 3 %", "evidence": {"agree": 52, "compared": 57}, "basis": "ADR-0030"},
]
STAND_IN = r'''
"""A stand-in for fea/tools/run_coupon.py: --run-by chooses what it writes."""
import argparse, json, pathlib, sys
parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--run-by", required=True)
parser.add_argument("--result", required=True)
parser.add_argument("--progress", required=True)
args, _ = parser.parse_known_args()
result = pathlib.Path(args.result)
attempt = ".local/fea/IM7-UNT-L1/ours/runs/attempt-02_2026-10-27"
pathlib.Path(args.progress).write_text(json.dumps({"stage": "the result", "done": [], "stages": [], "outputs": {}, "coupon": "IM7-UNT-L1",
                                                   "attempt": attempt}), encoding="utf-8")
if args.run_by == "STOPS":
    result.write_text(json.dumps({"status": "stopped", "message": "stopped at the second solver", "coupon": "IM7-UNT-L1", "attempt": attempt,
                                  "outputs": {}}), encoding="utf-8")
    sys.exit(1)
checks = json.loads(%(checks)r)
if args.run_by == "BADQA":
    checks[0]["verdict"] = "fine"
qa = result.parent / "qa.json"
if args.run_by == "ELSEWHERE":  # a file outside the job's folder and its owner's coupons: never read
    import tempfile
    qa = pathlib.Path(tempfile.gettempdir()) / "anisotropy-qa-elsewhere.json"
qa.write_text(json.dumps({"version": 1, "verdict": "ready", "checks": checks}), encoding="utf-8")  # the file's own verdict is never read
result.write_text(json.dumps({"status": "done", "coupon": "IM7-UNT-L1", "attempt": attempt, "message": "done", "outputs": {"qa": str(qa)}}),
                  encoding="utf-8")
''' % {"checks": json.dumps(CHECKS)}


def registry(tmp_path, table=None, folder: str = "jobs") -> CouponJobs:
    stand_in = tmp_path / "qa_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    return CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / folder, table=table, local_root=tmp_path / "coupons")


def ended(client: TestClient, job_id: str, headers: dict | None = None) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        body = client.get(f"/v1/coupon-jobs/{job_id}", headers=headers or {}).json()
        if body["state"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError(f"coupon job {job_id} still running after 30 s")


def run(client: TestClient, run_by: str, headers: dict | None = None) -> dict:
    started = client.post("/v1/coupon-jobs", json=form_request(run_by=run_by), headers=headers or {})
    assert started.status_code == 202, started.text
    return ended(client, started.json()["job_id"], headers)


# --------------------------------------------------------------------------------------------------- what the record keeps

def test_a_qa_file_is_kept_only_as_checks_the_record_knows():
    rows = qa_rows({"checks": CHECKS})
    assert [r["check_id"] for r in rows] == ["DATA-UNITS", "FEA-SECOND-SOLVER"] and [r["position"] for r in rows] == [0, 1]
    assert qa_verdict(rows) == "needs engineer" and qa_counts(rows) == {"pass": 1, "warn": 1, "block": 0}
    assert qa_verdict([]) == "unchecked" and qa_verdict(rows[:1]) == "ready" and qa_verdict([*rows, {**rows[0], "verdict": "block"}]) == "blocked"
    bad = [{"checks": []}, {"checks": "all fine"}, {"checks": [{**CHECKS[0], "layer": "vibes"}]}, {"checks": [{**CHECKS[0], "verdict": "fine"}]},
           {"checks": [{**CHECKS[0], "check": "drop table; --"}]}, {"checks": [{**CHECKS[0], "version": 0}]}, {"checks": [{**CHECKS[0], "version": True}]},
           {"checks": [{**CHECKS[0], "message": 7}]}, {"checks": [{**CHECKS[0], "evidence": {"x": "y" * 5000}}]}, {"checks": [CHECKS[0]] * 201}, [],
           {"checks": [{**CHECKS[0], "evidence": {"x": float("nan")}}]}]  # JSONB holds no NaN
    for qa in bad:
        with pytest.raises(QARecordError):
            qa_rows(qa)


# --------------------------------------------------------------------------------------------------- without the jobs table

def test_without_the_table_the_checks_are_the_runs_own_file(tmp_path, monkeypatch):
    client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})  # no lifespan: nothing is recorded
    monkeypatch.setattr(app.state, "coupon_jobs", registry(tmp_path), raising=False)
    done = run(client, "QA")
    qa = client.get(f"/v1/coupon-jobs/{done['job_id']}/qa").json()
    assert qa["verdict"] == "needs engineer" and qa["counts"] == {"pass": 1, "warn": 1, "block": 0}  # from the checks, not the file's "ready"
    assert [c["check"] for c in qa["checks"]] == ["DATA-UNITS", "FEA-SECOND-SOLVER"] and qa["checks"][1]["evidence"] == {"agree": 52, "compared": 57}
    for run_by in ("BADQA", "STOPS", "ELSEWHERE"):  # a file the record cannot keep, a run that stopped, a file from elsewhere: unchecked
        other = run(client, run_by)
        assert client.get(f"/v1/coupon-jobs/{other['job_id']}/qa").json() == {"job_id": other["job_id"], "verdict": "unchecked",
                                                                              "counts": {"pass": 0, "warn": 0, "block": 0}, "checks": []}
    missing = client.get(f"/v1/coupon-jobs/{uuid.uuid4()}/qa")
    assert missing.status_code == 404 and missing.json()["detail"] == GONE


# --------------------------------------------------------------------------------------------------- with the jobs table

@pytest.fixture
def recording(empty_runs, monkeypatch, tmp_path):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "test"}) as client:
        app.state.coupon_jobs = registry(tmp_path, app.state.records)
        yield client


@needs_test_database
def test_a_done_jobs_checks_are_written_once_and_never_changed(recording, tmp_path):
    engine = app.state.records
    done = run(recording, "QA")
    job_id = uuid.UUID(done["job_id"])
    rows = fetch_qa_checks(engine, job_id)
    assert [(r.position, r.check_id, r.verdict, r.layer) for r in rows] == [(0, "DATA-UNITS", "pass", "data"), (1, "FEA-SECOND-SOLVER", "warn", "fea")]
    assert rows[1].evidence == {"agree": 52, "compared": 57} and rows[1].basis == "ADR-0030" and rows[0].recorded_at is not None

    app.state.coupon_jobs = registry(tmp_path, engine, folder="later")  # a later process, without the run's files: the record answers
    qa = recording.get(f"/v1/coupon-jobs/{job_id}/qa").json()
    assert qa["verdict"] == "needs engineer" and [c["check"] for c in qa["checks"]] == ["DATA-UNITS", "FEA-SECOND-SOLVER"]

    with pytest.raises(QARecordError, match="written already"):  # the record is never rewritten
        insert_qa_checks(engine, job_id, qa_rows({"checks": CHECKS}), rows[0].recorded_at)
    for statement in ("UPDATE qa_checks SET verdict = 'pass'", "DELETE FROM qa_checks"):  # nor edited or deleted, whoever asks
        with pytest.raises(DBAPIError, match="never edited or deleted"), engine.begin() as connection:
            connection.execute(text(statement))
    with pytest.raises(DBAPIError, match="written once"), engine.begin() as connection:  # nor added to: the database refuses it too
        connection.execute(text("INSERT INTO qa_checks (id, job_id, position, recorded_at, layer, check_id, version, verdict, label, message, "
                                "evidence, basis) VALUES (:id, :job, 9, now(), 'data', 'DATA-LATE', 1, 'block', 'Late', 'added later', '{}', 'x')"),
                           {"id": uuid.uuid4(), "job": job_id})
    assert len(fetch_qa_checks(engine, job_id)) == 2


@needs_test_database
def test_a_qa_file_the_record_cannot_keep_leaves_the_job_done_and_unchecked(recording):
    done = run(recording, "BADQA")
    assert done["state"] == "done" and fetch_qa_checks(app.state.records, uuid.UUID(done["job_id"])) == []
    assert recording.get(f"/v1/coupon-jobs/{done['job_id']}/qa").json()["verdict"] == "unchecked"


# --------------------------------------------------------------------------------------------------- behind Cloudflare Access

def signed(email: str = EMAIL) -> dict:
    return {access.HEADER: token(email=email)}


@pytest.fixture(params=["with the jobs table", "without it"])
def hosted(request, empty_runs, monkeypatch, tmp_path):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        app.state.coupon_jobs = registry(tmp_path, app.state.records if request.param == "with the jobs table" else None)
        yield client


@needs_test_database
def test_a_runs_checks_are_its_owners_alone(hosted):
    client = hosted
    done = run(client, "QA", signed())
    path = f"/v1/coupon-jobs/{done['job_id']}/qa"
    mine = client.get(path, headers=signed())
    assert mine.status_code == 200 and mine.json()["verdict"] == "needs engineer" and len(mine.json()["checks"]) == 2
    unknown = client.get(f"/v1/coupon-jobs/{uuid.uuid4()}/qa", headers=signed(OTHER))
    assert unknown.status_code == 404 and unknown.json()["detail"] == GONE
    for stranger in (signed(OTHER), {access.HEADER: service_token()}, signed(EMAIL.upper())):  # another person, a machine, the email not to the letter
        answer = client.get(path, headers=stranger)
        assert answer.status_code == 404 and answer.json() == unknown.json()  # the same words as for a job there is none of
    assert client.get(path).status_code == 401  # and no one at all without Access's token
