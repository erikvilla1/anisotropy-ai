"""A wing's finite element check (ADR-0119): started from the wing workspace like a coupon run, as a job of the same kind. The engine
reads the description first and refuses a bad one at once; the check then runs in the background, one at a time here and through
the job queue on the hosted tier, and once done its report comes back with its status. A stand-in plays the check's tool, so these
tests need neither CalculiX nor Gmsh; fea/tests/test_wing_check.py runs the tool itself, and one test here runs it whole where both
are installed."""

import json
import sys
import time
import tomllib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import coupon_jobs
from anisotropy_api.coupon_jobs import CouponJobs, wing_check_command
from anisotropy_api.main import CHECK_STOPPED, ENQUEUE_HEADER, app, job_recorder
from anisotropy_api.records import fetch_job, fetch_run
from anisotropy_api.storage import job_output_key

from conftest import needs_test_database
from memory_store import MemoryStore

CHECKS = "/v1/wings/checks"
EXAMPLE = Path(__file__).resolve().parents[2] / "engine" / "examples" / "example-wing.toml"
client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: the jobs are the test's own

STAND_IN = r'''
"""A stand-in for anisotropy_fea.wing_check: the wing's title chooses what it does."""
import argparse, json, os, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("wing")
for option in ("--out", "--result", "--progress"):
    parser.add_argument(option, required=True)
args = parser.parse_args()
wing = json.loads(pathlib.Path(args.wing).read_text(encoding="utf-8"))
title, out, result, progress = wing["title"], pathlib.Path(args.out), pathlib.Path(args.result), pathlib.Path(args.progress)
out.mkdir(parents=True, exist_ok=True)
for done, stage in (([], "build"), (["build"], "solve")):
    progress.write_text(json.dumps({"stage": stage, "done": done, "stages": ["build", "solve", "modes"], "outputs": {}, "coupon": None, "attempt": None}))
if title.startswith("WAIT"):
    while not (pathlib.Path(os.environ["STAND_IN_RELEASE"])).exists():
        time.sleep(0.02)
if title.startswith("CRASH"):
    print("Traceback: CalculiX failed on wing (exit 1)", flush=True)
    sys.exit(1)
if title.startswith("REFUSE"):
    result.write_text(json.dumps({"status": "refused", "message": "The wing has ribs but no rib layup: add a [rib] table with its half_stack",
                                  "coupon": None, "attempt": None, "outputs": {}}))
    sys.exit(2)
report = out / "wing-check.json"
report.write_text(json.dumps({"wing": title, "lowest": {"case": 6, "margin_ultimate": 0.146}, "lowest_hand": {"case": 6, "margin_ultimate": 0.154}}))
progress.write_text(json.dumps({"stage": None, "done": ["build", "solve", "modes"], "stages": ["build", "solve", "modes"], "outputs": {}}))
result.write_text(json.dumps({"status": "done", "message": "Lowest margin outboard of the root +0.146", "coupon": None, "attempt": None,
                              "outputs": {"wing_check": str(report)}}))
'''


def example(title: str | None = None) -> dict:
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    if title is not None:
        data["title"] = title
    return data


@pytest.fixture
def stand_in(tmp_path) -> list[str]:
    script = tmp_path / "wing_check_stand_in.py"
    script.write_text(STAND_IN, encoding="utf-8")
    return [sys.executable, str(script)]


@pytest.fixture
def here(tmp_path, monkeypatch, stand_in):
    """The local API: this process runs each check itself, one at a time, with no table and no store."""
    monkeypatch.setattr(coupon_jobs, "REPO", tmp_path)
    monkeypatch.setenv("STAND_IN_RELEASE", str(tmp_path / "release"))
    jobs = CouponJobs(None, lambda job, state, outcome: None, tmp_path / "jobs", wing=stand_in)
    monkeypatch.setattr(app.state, "coupon_jobs", jobs, raising=False)
    return jobs, tmp_path


def ended(job_id: str, until=("done", "stopped", "refused")) -> dict:
    deadline = time.monotonic() + 30
    while True:
        status = client.get(f"{CHECKS}/{job_id}").json()
        if status["state"] in until:
            return status
        assert time.monotonic() < deadline, f"the check {job_id} is still {status['state']} after 30 s"
        time.sleep(0.02)


def test_a_check_runs_in_the_background_and_its_report_comes_back_with_its_status(here):
    answer = client.post(CHECKS, json={"wing": example()})
    assert answer.status_code == 202 and answer.headers["Location"] == f"{CHECKS}/{answer.json()['job_id']}"
    assert answer.json()["state"] == "running" and answer.json()["wing"] == "Example straight wing" and answer.json()["report"] is None
    status = ended(answer.json()["job_id"])
    assert status["state"] == "done" and status["stages_done"] == ["build", "solve", "modes"] and status["message"] is None
    assert status["report"] == {"wing": "Example straight wing", "lowest": {"case": 6, "margin_ultimate": 0.146},
                                "lowest_hand": {"case": 6, "margin_ultimate": 0.154}}
    jobs, _ = here
    description = json.loads((jobs.root / answer.json()["job_id"] / "wing.json").read_text(encoding="utf-8"))
    assert description == example(), "the tool reads the description the engine read"


def test_a_wing_file_as_text_is_checked_as_its_description(here):
    jobs, _ = here
    answer = client.post(CHECKS, json={"toml": EXAMPLE.read_text(encoding="utf-8")})
    assert ended(answer.json()["job_id"])["state"] == "done"
    assert json.loads((jobs.root / answer.json()["job_id"] / "wing.json").read_text(encoding="utf-8")) == example()


def test_the_engine_refuses_a_bad_description_before_any_check_starts(here):
    jobs, _ = here
    refused = client.post(CHECKS, json={"wing": {**example(), "units": "imperial"}})
    assert refused.status_code == 422 and "units must be one of" in refused.json()["detail"]
    assert client.post(CHECKS, json={"toml": "title = "}).status_code == 422
    assert jobs.jobs == {}, "nothing started"


def test_one_check_runs_at_a_time_here_and_a_coupon_jobs_id_is_not_a_check(here):
    jobs, tmp_path = here
    first = client.post(CHECKS, json={"wing": example("WAIT")})
    assert first.status_code == 202
    second = client.post(CHECKS, json={"wing": example()})
    assert second.status_code == 409 and second.json()["detail"] == "Another analysis is running. Wait for it to finish, then run this one."
    (tmp_path / "release").write_text("go", encoding="utf-8")
    assert ended(first.json()["job_id"])["state"] == "done"
    assert client.get(f"{CHECKS}/{uuid.uuid4()}").status_code == 404
    coupon = next(iter(jobs.jobs.values()))
    coupon.inputs = {"coupon": "IM7-UNT-L1"}  # a coupon job of this process: not a wing's check
    assert client.get(f"{CHECKS}/{coupon.id}").status_code == 404


def test_the_tools_refusal_is_shown_and_a_stop_says_what_to_do_never_the_cause(here):
    refused = ended(client.post(CHECKS, json={"wing": example("REFUSE")}).json()["job_id"])
    assert refused["state"] == "refused" and refused["message"] == "The wing has ribs but no rib layup: add a [rib] table with its half_stack"
    stopped = ended(client.post(CHECKS, json={"wing": example("CRASH")}).json()["job_id"])
    assert stopped["state"] == "stopped" and stopped["message"] == CHECK_STOPPED and stopped["report"] is None
    assert "CalculiX" not in json.dumps(stopped)


def test_without_the_check_tool_the_check_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(app.state, "coupon_jobs", CouponJobs(None, lambda *a: None, tmp_path / "jobs", wing=None), raising=False)
    answer = client.post(CHECKS, json={"wing": example()})
    assert answer.status_code == 503 and answer.json()["detail"] == "The check could not be started right now. Try again in a minute."


# ------------------------------------------------------------------------------------------- through the job queue (ADR-0056)

@pytest.fixture
def queue(tmp_path, monkeypatch, empty_runs, stand_in):
    """The API's container (`queue`) and one solver container sharing one store and the test database, the stand-in as the check's tool."""
    monkeypatch.setattr(coupon_jobs, "REPO", tmp_path)
    monkeypatch.setattr(coupon_jobs, "HEARTBEAT_S", 0.05)
    monkeypatch.setenv("STAND_IN_RELEASE", str(tmp_path / "release"))
    store = MemoryStore()
    monkeypatch.setattr(app.state, "records", empty_runs, raising=False)  # the receipts go to the test database
    recorder = job_recorder(app)
    front = CouponJobs([sys.executable, "-c", "pass"], recorder, tmp_path / "api" / "jobs", store=store, table=empty_runs, role="queue", wing=stand_in)
    solver = CouponJobs([sys.executable, "-c", "pass"], recorder, tmp_path / "solver" / "jobs", store=store, table=empty_runs, role="solver", wing=stand_in)
    monkeypatch.setattr(app.state, "coupon_jobs", front, raising=False)
    return front, solver, store, empty_runs


@needs_test_database
def test_through_the_queue_a_solver_runs_the_check_and_the_api_reads_its_report_back_from_the_store(queue):
    front, solver, store, table = queue
    answer = client.post(CHECKS, json={"wing": example()})
    assert answer.status_code == 202 and answer.headers[ENQUEUE_HEADER] == answer.json()["job_id"] and answer.json()["state"] == "queued"
    job_id = uuid.UUID(answer.json()["job_id"])
    row = fetch_job(table, job_id)
    assert row.state == "queued" and row.source is None and row.options == [] and front.jobs == {}
    assert row.inputs == {"kind": "wing", "wing": "Example straight wing", "description": example()}, "the description travels in the row"
    assert store.objects == {}, "nothing is filed before a solver takes it"
    assert client.get(f"{CHECKS}/{job_id}").json()["message"] == "queued"
    job = solver.take(job_id)
    deadline = time.monotonic() + 30
    while job.state != "done" or fetch_job(table, job_id).state != "done":
        assert time.monotonic() < deadline, f"the check is {job.state} after 30 s"
        time.sleep(0.02)
    row = fetch_job(table, job_id)
    assert row.stored == {"wing_check": job_output_key(str(job_id), "wing-check.json")} and row.stored["wing_check"] in store.objects
    status = client.get(f"{CHECKS}/{job_id}").json()
    assert status["state"] == "done" and status["report"]["lowest"] == {"case": 6, "margin_ultimate": 0.146}
    run = fetch_run(table, uuid.UUID(status["run_id"]))
    assert run.endpoint == CHECKS and run.status == "solved" and run.inputs["description"] == example() and run.response["job_id"] == str(job_id)
    assert client.get(f"/v1/coupon-jobs/{job_id}").json()["coupon"] is None, "the list of past analyses keeps coupon runs only (lib/run-history.ts)"


@needs_test_database
def test_a_check_started_for_a_wing_project_is_listed_with_it_and_anothers_project_is_ignored(queue):
    """A wing is a project (ADR-0120): the check names it, the project lists the check, even while it waits for a solver; a project id
    that is not the requester's is ignored and the check still runs."""
    front, solver, store, table = queue
    pid = str(uuid.uuid4())
    made = client.put(f"/v1/projects/{pid}", json={"kind": "wing", "name": "Example straight wing", "content": {"wing": example()}})
    assert made.status_code == 201 and made.json()["kind"] == "wing" and made.json()["content"]["wing"] == example()
    mine = client.post(CHECKS, json={"wing": example(), "project_id": pid})
    assert mine.status_code == 202 and fetch_job(table, uuid.UUID(mine.json()["job_id"])).project_id == uuid.UUID(pid)
    listed = client.get(f"/v1/projects/{pid}").json()["jobs"]
    assert [(job["job_id"], job["state"]) for job in listed] == [(mine.json()["job_id"], "queued")]
    theirs = client.post(CHECKS, json={"wing": example(), "project_id": pid}, headers={"X-Anisotropy-Actor": "test"})
    assert theirs.status_code == 202 and fetch_job(table, uuid.UUID(theirs.json()["job_id"])).project_id is None
    assert client.post(CHECKS, json={"wing": example(), "project_id": "not-an-id"}).status_code == 422


@needs_test_database
def test_through_the_queue_the_per_job_timeout_stops_the_check(queue, monkeypatch):
    front, solver, store, table = queue
    job_id = uuid.UUID(client.post(CHECKS, json={"wing": example("WAIT")}).json()["job_id"])
    job = solver.take(job_id)
    deadline = time.monotonic() + 30
    while job.process is None:
        assert time.monotonic() < deadline
        time.sleep(0.02)
    solver.stop(job_id, "the job ran longer than the 12 minutes allowed")
    while fetch_job(table, job_id).state != "stopped":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    status = client.get(f"{CHECKS}/{job_id}").json()
    assert status["state"] == "stopped" and status["message"] == CHECK_STOPPED and store.objects == {}


# ------------------------------------------------------------------------------------------- the tool itself

FEA = Path(__file__).resolve().parents[2] / "fea"
READY = bool(list((FEA / ".venv").glob("lib/python*/site-packages/gmsh*"))) and wing_check_command() is not None and coupon_jobs.shutil.which("ccx")


@pytest.mark.skipif(not READY, reason="the fea environment with Gmsh (uv sync --extra mesh in fea/) and CalculiX are not both installed")
def test_the_example_wing_is_checked_by_its_finite_element_model(tmp_path, monkeypatch):
    """Half a minute: the real tool, run by this API, on the example wing (the numbers are the fea package's tests' to judge)."""
    monkeypatch.setattr(app.state, "coupon_jobs", CouponJobs(None, lambda *a: None, tmp_path / "jobs", wing=wing_check_command()), raising=False)
    status = client.post(CHECKS, json={"toml": EXAMPLE.read_text(encoding="utf-8")}).json()
    deadline = time.monotonic() + 300
    while status["state"] in ("queued", "running"):
        assert time.monotonic() < deadline
        time.sleep(1)
        status = client.get(f"{CHECKS}/{status['job_id']}").json()
    assert status["state"] == "done", status
    report = status["report"]
    assert report["wing"] == "Example straight wing" and report["units"]["deflection"] == "mm" and len(report["cases"]) == 34
    assert abs(report["lowest"]["margin_ultimate"] - report["lowest_hand"]["margin_ultimate"]) < 0.05
