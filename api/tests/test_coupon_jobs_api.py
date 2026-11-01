"""Coupon jobs (ADR-0050): a form or a coupon starts fea/tools/run_coupon.py in the background, one job at a time; its status shows
the end of its console and, once done, its files; its package comes as a zip; an ended job has one run record. A stand-in for the
tool plays each outcome here, so these tests need neither CalculiX nor the fea environment; fea/tests/test_run_coupon.py runs the
tool itself."""

import base64
import hashlib
import io
import json
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
import argparse, json, pathlib, sys, tempfile, time
parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--run-by", required=True)
parser.add_argument("--result", required=True)
parser.add_argument("--progress", required=True)
for flag in ("--replace", "--no-pdf", "--no-theory"):
    parser.add_argument(flag, action="store_true")
args = parser.parse_args()
result = pathlib.Path(args.result)
print("== the input form", flush=True)
fields = result.parent / "fields.json"
fields.write_text('{"summary": {"reaction": {"value": 1.0}}}', encoding="utf-8")
outside = pathlib.Path(tempfile.gettempdir()) / "anisotropy-outside.txt"
outside.write_text("not for the API", encoding="utf-8")
progress = {"stage": "our engine", "done": ["the setup check", "the input", "the decks", "the attempt"], "stages": ["the setup check", "the input"],
            "outputs": {"fields": str(fields), "outside": str(outside)}, "coupon": "IM7-UNT-L1", "attempt": ".local/fea/IM7-UNT-L1/ours/runs/attempt-02_2026-10-27"}
pathlib.Path(args.progress).write_text(json.dumps(progress), encoding="utf-8")
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
                              "message": f"form {size} bytes; run by {args.run_by}; no-pdf {args.no_pdf}", "outputs": {"package": str(package), "fields": str(fields), "outside": str(outside)},
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
    (form_request(coupon="IM7-UNT-L1"), "one of the three"),
    ({"run_by": "A. Engineer"}, "one of the three"),
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


# --------------------------------------------------------------------------------------------- the studio's way in (ADR-0051)

VALUES = {"form_version": "0.3", "filled_by": "A. Engineer", "test": "unnotched tension", "length": 250.0, "angles": [45, 0, -45, 90]}


def test_the_values_run_as_a_file_the_tool_reads(jobs):
    started = client.post("/v1/coupon-jobs", json={"values": VALUES, "run_by": "A. Engineer", "pdf": False})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    body = ended(job_id)
    [written] = [p for p in (jobs.root / job_id).iterdir() if p.name.startswith("values-") and p.suffix == ".json"]
    assert written.name == f"values-{job_id.replace('-', '')[:8]}.json" and json.loads(written.read_text(encoding="utf-8")) == VALUES
    assert list(json.loads(written.read_text(encoding="utf-8"))) == sorted(VALUES)  # written with sorted keys: one digest for one object
    assert body["state"] == "done" and body["message"].startswith(f"form {written.stat().st_size} bytes")


def test_the_status_shows_the_stage_and_the_files_so_far(jobs):
    job_id = client.post("/v1/coupon-jobs", json={"coupon": "WAITS", "run_by": "A. Engineer"}).json()["job_id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and client.get(f"/v1/coupon-jobs/{job_id}").json()["stage"] is None:
        time.sleep(0.05)
    running = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert running["state"] == "running" and running["stage"] == "our engine" and running["stages_done"] == ["the setup check", "the input", "the decks", "the attempt"]
    assert running["stages"] == ["the setup check", "the input"] and set(running["outputs"]) == {"fields", "outside"} and running["coupon"] == "IM7-UNT-L1"
    fields = client.get(f"/v1/coupon-jobs/{job_id}/files/fields")
    assert fields.status_code == 200 and fields.headers["content-type"].startswith("application/json") and fields.json()["summary"]["reaction"]["value"] == 1.0
    no_package = client.get(f"/v1/coupon-jobs/{job_id}/files/package")
    assert no_package.status_code == 404 and "it has: fields, outside" in no_package.json()["detail"]
    outside = client.get(f"/v1/coupon-jobs/{job_id}/files/outside")
    assert outside.status_code == 404 and "lies outside the repository and the job's folder" in outside.json()["detail"]
    (jobs.root / "release").touch()
    done = ended(job_id)
    assert done["stage"] == "our engine" and set(done["outputs"]) == {"package", "fields", "outside"}  # the outcome's files once done
    package = client.get(f"/v1/coupon-jobs/{job_id}/files/package")
    assert package.status_code == 200 and package.headers["content-type"] == "application/zip"
    assert client.get(f"/v1/coupon-jobs/{job_id}/files/fields").status_code == 200


def test_jobs_are_listed_newest_first(jobs):
    assert client.get("/v1/coupon-jobs").json() == []
    first = ended(client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}).json()["job_id"])
    second = ended(client.post("/v1/coupon-jobs", json={"coupon": "STOPS", "run_by": "A. Engineer"}).json()["job_id"])
    listed = client.get("/v1/coupon-jobs").json()
    assert [job["job_id"] for job in listed] == [second["job_id"], first["job_id"]] and [job["state"] for job in listed] == ["stopped", "done"]


@pytest.mark.parametrize("body, reason", [
    ({"values": VALUES, "coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}, "one of the three"),
    ({"values": {}, "run_by": "A. Engineer"}, "the object is empty"),
    ({"values": "length = 250", "run_by": "A. Engineer"}, "dictionary"),
    ({"values": {"big": "x" * 300_000}, "run_by": "A. Engineer"}, "far below"),
])
def test_values_outside_the_contract_start_nothing(jobs, body, reason):
    refused = client.post("/v1/coupon-jobs", json=body)
    assert refused.status_code == 422 and reason in str(refused.json()["detail"])
    assert jobs.jobs == {}


@needs_test_database
def test_a_values_job_and_a_studio_request_have_their_receipts(recording):
    done = ended(recording.post("/v1/coupon-jobs", json={"values": VALUES, "run_by": "A. Engineer"}).json()["job_id"], recording)
    run = recording.get(f"/v1/runs/{done['run_id']}").json()
    digest = hashlib.sha256(json.dumps(VALUES, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")).hexdigest()
    assert run["inputs"] == {"values": {"sha256": digest, "form_version": "0.3"}, "run_by": "A. Engineer", "replace": False, "pdf": True, "theory": True}
    studio = ended(recording.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"},
                                  headers={"X-Anisotropy-Actor": "studio"}).json()["job_id"], recording)
    assert recording.get(f"/v1/runs/{studio['run_id']}").json()["actor"] == "studio"  # the constraint admits the new actor (migration 0004)


# --------------------------------------------------------------------------------- behind Cloudflare Access (ADR-0056)

from anisotropy_api import access
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, AccessSettings
from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, token


@pytest.fixture
def recording_behind_access(empty_runs, monkeypatch, tmp_path):
    """The API with run records on and Access on, its coupon jobs running the stand-in; every request carries a valid token."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    with TestClient(app, headers={"X-Anisotropy-Actor": "test", access.HEADER: token()}) as recorded:
        app.state.coupon_jobs = CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / "jobs")
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        yield recorded


@needs_test_database
def test_a_job_started_behind_access_keeps_the_signed_in_email(recording_behind_access):
    through = recording_behind_access
    started = through.post("/v1/coupon-jobs", json=form_request()).json()
    assert started["user_email"] == EMAIL  # on the status from the start
    done = ended(started["job_id"], through)
    assert done["state"] == "done" and done["user_email"] == EMAIL
    run = through.get(f"/v1/runs/{done['run_id']}").json()
    assert run["user_email"] == EMAIL and run["actor"] == "test" and run["endpoint"] == "/v1/coupon-jobs"  # the receipt names the person
    assert through.get("/v1/coupon-jobs").json()[0]["user_email"] == EMAIL
    assert through.get("/v1/coupon-jobs", headers={access.HEADER: ""}).status_code == 401  # and without the token, nothing


# ---------------------------------------------------------------------------------- durable outputs (ADR-0050 amendment 2)

import uuid as _uuid

from memory_store import FailingStore, MemoryStore


def storing_registry(tmp_path, store, monkeypatch) -> CouponJobs:
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    ours = tmp_path / "fea" / "IM7-UNT-L1" / "ours"
    ours.mkdir(parents=True)
    (ours / "IM7-UNT-L1.toml").write_text("[coupon]\n", encoding="utf-8")  # the coupon's folder, as the tool leaves it
    registry = CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / "jobs", store=store, local_root=tmp_path / "fea")
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    return registry


def test_a_done_jobs_files_go_to_the_store_and_the_api_hands_out_links_there(tmp_path, monkeypatch):
    store = MemoryStore()
    registry = storing_registry(tmp_path, store, monkeypatch)
    done = ended(client.post("/v1/coupon-jobs", json=form_request()).json()["job_id"])
    assert done["state"] == "done"
    attempt = "attempt-02_2026-10-27"
    assert set(store.objects) == {f"coupons/IM7-UNT-L1/{attempt}/files/fields/fields.json", f"coupons/IM7-UNT-L1/{attempt}/package.zip",
                                  "coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml"}  # the file outside the repository and the job's folder is not stored
    job = registry.get(_uuid.UUID(done["job_id"]))
    assert job.stored == {"fields": f"coupons/IM7-UNT-L1/{attempt}/files/fields/fields.json", "package": f"coupons/IM7-UNT-L1/{attempt}/package.zip"}
    assert store.objects[job.stored["package"]][1:] == ("application/zip", 'attachment; filename="2026-10-27_IM7-UNT-L1.zip"')
    fields = client.get(f"/v1/coupon-jobs/{done['job_id']}/files/fields", follow_redirects=False)
    assert fields.status_code == 307 and fields.headers["location"] == f"https://store.test/{job.stored['fields']}?expires=600"
    package = client.get(f"/v1/coupon-jobs/{done['job_id']}/package", follow_redirects=False)
    assert package.status_code == 307 and package.headers["location"].endswith("/package.zip?expires=600")
    outside = client.get(f"/v1/coupon-jobs/{done['job_id']}/files/outside")  # not in the store: the disk rule still refuses it
    assert outside.status_code == 404 and "outside" in outside.json()["detail"]


def test_while_a_job_runs_its_files_come_from_the_disk(tmp_path, monkeypatch):
    registry = storing_registry(tmp_path, MemoryStore(), monkeypatch)
    started = client.post("/v1/coupon-jobs", json={"coupon": "WAITS", "run_by": "A. Engineer"}).json()
    deadline = time.monotonic() + 30
    while "fields" not in client.get(f"/v1/coupon-jobs/{started['job_id']}").json()["outputs"] and time.monotonic() < deadline:
        time.sleep(0.05)
    fields = client.get(f"/v1/coupon-jobs/{started['job_id']}/files/fields", follow_redirects=False)
    assert fields.status_code == 200 and fields.json() == {"summary": {"reaction": {"value": 1.0}}}  # served from the disk, no link yet
    (registry.root / "release").touch()
    assert ended(started["job_id"])["state"] == "done"


def test_a_store_that_fails_stops_the_job_and_withholds_its_result(tmp_path, monkeypatch):
    storing_registry(tmp_path, FailingStore(), monkeypatch)
    stopped = ended(client.post("/v1/coupon-jobs", json=form_request()).json()["job_id"])
    assert stopped["state"] == "stopped" and "could not be copied to storage" in stopped["message"] and "AccessDenied" in stopped["message"]
    assert stopped["outputs"] == {} and client.get(f"/v1/coupon-jobs/{stopped['job_id']}/package").status_code == 409
