"""Coupon jobs (ADR-0050): a form or a coupon starts fea/tools/run_coupon.py in the background, one job at a time; its status shows
the end of its console and, once done, its files; its package comes as a zip; an ended job has one run record. A stand-in for the
tool plays each outcome here, so these tests need neither CalculiX nor the fea environment; fea/tests/test_run_coupon.py runs the
tool itself."""

import base64
import hashlib
import io
import sys
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import coupon_jobs
from anisotropy_api.coupon_jobs import CouponJobs, RecordingFailed, runner_command
from anisotropy_api.main import app, job_recorder
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

FORM = b"PK\x03\x04" + bytes(200)  # starts as an .xlsx file does; only the stand-in reads it
STAND_IN = r'''
"""A stand-in for fea/tools/run_coupon.py: the source argument chooses what it does."""
import argparse, json, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--run-by", required=True)
parser.add_argument("--result", required=True)
for flag in ("--replace", "--no-pdf", "--no-theory"):
    parser.add_argument(flag, action="store_true")
args = parser.parse_args()
result = pathlib.Path(args.result)
print("== the input form", flush=True)
if args.source == "STOPS":
    result.write_text(json.dumps({"status": "stopped", "message": "stopped at CalculiX: run_calculix.py exited with code 1",
                                  "coupon": "STOPS", "attempt": ".local/fea/STOPS/ours/runs/attempt-02_2026-10-27", "outputs": {}}))
    sys.exit(1)
if args.source == "CRASHES":
    print("Traceback: something broke", flush=True)
    sys.exit(2)
if args.source == "WAITS":
    while not (result.parent.parent / "release").exists():
        time.sleep(0.05)
package = result.parent / "2026-10-27_IM7-UNT-L1"
package.mkdir()
(package / "IM7-UNT-L1.pdf").write_bytes(b"%PDF")
source = pathlib.Path(args.source)
size = source.stat().st_size if source.is_file() else 0
result.write_text(json.dumps({"status": "done", "coupon": "IM7-UNT-L1", "attempt": ".local/fea/IM7-UNT-L1/ours/runs/attempt-02_2026-10-27",
                              "message": f"form {size} bytes; run by {args.run_by}; no-pdf {args.no_pdf}", "outputs": {"package": str(package)},
                              "fea_version": "stand-in"}), encoding="utf-8")
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})  # no lifespan: nothing is recorded here


def form_request(**changes) -> dict:
    return {"form_name": "filled.xlsx", "form_base64": base64.b64encode(FORM).decode(), "run_by": "A. Engineer", **changes}


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    """The API's coupon jobs, running the stand-in."""
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    registry = CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / "jobs")
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    return registry


def ended(job_id: str, through: TestClient = client) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        body = through.get(f"/v1/coupon-jobs/{job_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError(f"coupon job {job_id} still running after 30 s")


def test_a_form_runs_in_the_background_to_its_package(jobs):
    started = client.post("/v1/coupon-jobs", json=form_request(pdf=False))
    assert started.status_code == 202 and started.json()["state"] in ("running", "done")
    job_id = started.json()["job_id"]
    assert started.headers["location"] == f"/v1/coupon-jobs/{job_id}"
    body = ended(job_id)
    assert body["state"] == "done" and body["coupon"] == "IM7-UNT-L1" and body["attempt"].endswith("attempt-02_2026-10-27")
    assert body["message"] == f"form {len(FORM)} bytes; run by A. Engineer; no-pdf True"  # the form as sent, and the options
    assert "== the input form" in body["log_tail"] and body["run_id"] is None and body["finished_at"] is not None
    assert (jobs.root / job_id / "filled.xlsx").read_bytes() == FORM
    package = client.get(f"/v1/coupon-jobs/{job_id}/package")
    assert package.status_code == 200 and package.headers["content-type"] == "application/zip"
    assert zipfile.ZipFile(io.BytesIO(package.content)).namelist() == ["2026-10-27_IM7-UNT-L1/", "2026-10-27_IM7-UNT-L1/IM7-UNT-L1.pdf"]


def test_one_job_runs_at_a_time(jobs):
    first = client.post("/v1/coupon-jobs", json={"coupon": "WAITS", "run_by": "A. Engineer"}).json()["job_id"]
    second = client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"})
    assert second.status_code == 409 and first in second.json()["detail"]
    assert client.get(f"/v1/coupon-jobs/{first}/package").status_code == 409  # running: no package yet
    (jobs.root / "release").touch()
    assert ended(first)["state"] == "done"
    assert client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}).status_code == 202


def test_a_stopped_run_says_where_and_has_no_package(jobs):
    job_id = client.post("/v1/coupon-jobs", json={"coupon": "STOPS", "run_by": "A. Engineer"}).json()["job_id"]
    body = ended(job_id)
    assert body["state"] == "stopped" and body["message"] == "stopped at CalculiX: run_calculix.py exited with code 1" and body["outputs"] == {}
    package = client.get(f"/v1/coupon-jobs/{job_id}/package")
    assert package.status_code == 409 and "stopped at CalculiX" in package.json()["detail"]


def test_a_tool_that_writes_no_outcome_is_stopped_with_its_console(jobs):
    body = ended(client.post("/v1/coupon-jobs", json={"coupon": "CRASHES", "run_by": "A. Engineer"}).json()["job_id"])
    assert body["state"] == "stopped" and "exited with code 2 and wrote no outcome" in body["message"]
    assert "Traceback: something broke" in body["log_tail"]


@pytest.mark.parametrize("body, reason", [
    (form_request(coupon="IM7-UNT-L1"), "not both"),
    ({"run_by": "A. Engineer"}, "not neither"),
    (form_request(form_base64=None), "needs both"),
    (form_request(form_base64="not base64!"), "not base64"),
    (form_request(form_base64=base64.b64encode(b"hello").decode()), "not an .xlsx"),
    (form_request(form_name="team/filled.xlsx"), "pattern"),
    (form_request(form_name="filled.txt"), "pattern"),
    ({"coupon": "../IM7-UNT-L1", "run_by": "A. Engineer"}, "pattern"),
    ({"coupon": "IM7-UNT-L1", "run_by": "A. Engineer", "replace": True}, "needs a form"),
    ({"coupon": "IM7-UNT-L1", "run_by": "--replace"}, "pattern"),
    ({"coupon": "IM7-UNT-L1"}, "Field required"),
    ({"coupon": "IM7-UNT-L1", "run_by": "A. Engineer", "pdf": "no"}, "boolean"),
    ({"coupon": "IM7-UNT-L1", "run_by": "A. Engineer", "dry_run": True}, "Extra inputs"),
])
def test_a_request_outside_the_contract_starts_nothing(jobs, body, reason):
    refused = client.post("/v1/coupon-jobs", json=body)
    assert refused.status_code == 422 and reason in str(refused.json()["detail"])
    assert jobs.jobs == {}


def test_the_actor_is_required_and_an_unknown_job_is_not_found(jobs):
    assert TestClient(app).post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}).status_code == 422
    missing = client.get("/v1/coupon-jobs/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404 and "GET /v1/runs?endpoint=/v1/coupon-jobs" in missing.json()["detail"]
    assert jobs.jobs == {}


def test_without_uv_no_job_starts(tmp_path, monkeypatch):
    monkeypatch.setattr(coupon_jobs.shutil, "which", lambda name: None)
    assert runner_command() is None
    monkeypatch.setattr(app.state, "coupon_jobs", CouponJobs(runner_command(), job_recorder(app), tmp_path), raising=False)
    refused = client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"})
    assert refused.status_code == 503 and "uv is not on PATH" in refused.json()["detail"]


def test_the_command_is_the_fea_tool_in_its_own_environment(monkeypatch):
    monkeypatch.setattr(coupon_jobs.shutil, "which", lambda name: f"/bin/{name}")
    command = runner_command()
    assert command == ["/bin/uv", "run", "--project", str(coupon_jobs.FEA), "python", str(coupon_jobs.RUNNER)]
    assert coupon_jobs.RUNNER.is_file()


def test_a_job_whose_receipt_cannot_be_written_withholds_its_result(tmp_path):
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")

    def broken(job, state, outcome):
        raise RecordingFailed("connection refused")

    registry = CouponJobs([sys.executable, str(stand_in)], broken, tmp_path / "jobs")
    job = registry.start("test", {"coupon": "IM7-UNT-L1"}, ["--run-by", "A. Engineer"], coupon="IM7-UNT-L1")
    deadline = time.monotonic() + 30
    while job.state == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert job.state == "stopped" and "could not be written: connection refused" in job.outcome["message"] and job.outcome["outputs"] == {}


@pytest.fixture
def recording(empty_runs, monkeypatch, tmp_path):
    """The API with run records on, its coupon jobs running the stand-in."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    with TestClient(app, headers={"X-Anisotropy-Actor": "test"}) as recorded:
        app.state.coupon_jobs = CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / "jobs")
        yield recorded


@needs_test_database
def test_an_ended_job_has_its_receipt(recording):
    done = ended(recording.post("/v1/coupon-jobs", json=form_request()).json()["job_id"], recording)
    run = recording.get(f"/v1/runs/{done['run_id']}").json()
    assert run["status"] == "solved" and run["endpoint"] == "/v1/coupon-jobs" and run["actor"] == "test"
    assert run["inputs"] == {"form": {"name": "filled.xlsx", "sha256": hashlib.sha256(FORM).hexdigest()}, "run_by": "A. Engineer",
                             "replace": False, "pdf": True, "theory": True}  # the form's digest, not the form
    assert run["response"]["job_id"] == done["job_id"] and run["response"]["coupon"] == "IM7-UNT-L1"
    stopped = ended(recording.post("/v1/coupon-jobs", json={"coupon": "STOPS", "run_by": "A. Engineer"}).json()["job_id"], recording)
    run = recording.get(f"/v1/runs/{stopped['run_id']}").json()
    assert run["status"] == "rejected" and run["error"] == "stopped at CalculiX: run_calculix.py exited with code 1" and run["response"] is None
