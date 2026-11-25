"""A repair carried until its plies and its bond cannot hold the load, from the repair's page (ADR-0141 amendment 1): a job as a
wing's check is one (ADR-0119), since the run takes minutes. The engine reads the description first and refuses a bad one, or one
that lacks what the run needs, at once; the run then goes on in the background, one at a time here and through the job queue on
the hosted tier, and once done its report comes back with its status. A stand-in plays the run's tool; fea/tests/test_repair_plies.py
runs the tool itself, as a job too."""

import json
import sys
import time
import tomllib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import coupon_jobs
from anisotropy_api.coupon_jobs import REPAIR_PLIES_OPTIONS, CouponJobs
from anisotropy_api.main import ENQUEUE_HEADER, PLIES_STOPPED, app, job_recorder
from anisotropy_api.records import fetch_job, fetch_run
from anisotropy_api.storage import job_output_key

from conftest import needs_test_database
from memory_store import MemoryStore

RUNS, ANALYZE = "/v1/repairs/plies", "/v1/repairs/analyze"
EXAMPLE = Path(__file__).resolve().parents[2] / "engine" / "examples" / "example-patch-repair.toml"
EXTERNAL = Path(__file__).resolve().parents[2] / "engine" / "examples" / "example-external-patch-repair.toml"
client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: the jobs are the test's own
HEADLINE = "The slice carries 1208 N/mm in this model and not 1213; the first softening is at 184.4 N/mm (the bond)."

STAND_IN = r'''
"""A stand-in for anisotropy_fea.repair_plies as a job: the repair's title chooses what it does."""
import argparse, json, os, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("repair")
for option in ("--out", "--result", "--progress", "--seconds", "--most", "--finer"):
    parser.add_argument(option, required=True)
args = parser.parse_args()
repair = json.loads(pathlib.Path(args.repair).read_text(encoding="utf-8"))
title, out, result, progress = repair["title"], pathlib.Path(args.out), pathlib.Path(args.result), pathlib.Path(args.progress)
out.mkdir(parents=True, exist_ok=True)
stages = ["build", "soften", "raise", "close"]
for done, stage in (([], "build"), (["build"], "soften"), (["build", "soften"], "raise")):
    progress.write_text(json.dumps({"stage": stage, "done": done, "stages": stages, "outputs": {}, "coupon": None, "attempt": None}))
if title.startswith("WAIT"):
    while not (pathlib.Path(os.environ["STAND_IN_RELEASE"])).exists():
        time.sleep(0.02)
if title.startswith("CRASH"):
    print("Traceback: SuperLU ran out of memory", flush=True)
    sys.exit(1)
if title.startswith("REFUSE"):
    result.write_text(json.dumps({"status": "refused", "message": "The slice would have 48,000 elements, and this run takes at most 40,000.",
                                  "coupon": None, "attempt": None, "outputs": {}}))
    sys.exit(2)
headline = "The slice carries 1208 N/mm in this model and not 1213; the first softening is at 184.4 N/mm (the bond)."
report = out / "repair-plies.json"
report.write_text(json.dumps({"units": {"system": "mm-MPa", "length": "mm", "force": "N/mm", "stress": "MPa"}, "ended": "closed",
                              "model": {"elements": 6322, "given": [args.seconds, args.most, args.finer]},
                              "onset": {"load": 184.4, "what": "the bond"}, "load": {"held": 1207.5, "not_held": 1212.8}, "headline": headline}))
progress.write_text(json.dumps({"stage": None, "done": stages, "stages": stages, "outputs": {}}))
result.write_text(json.dumps({"status": "done", "message": headline, "coupon": None, "attempt": None, "outputs": {"repair_plies": str(report)}}))
'''


def example(title: str | None = None, **changes) -> dict:
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    if title is not None:
        data["title"] = title
    for where, value in changes.items():
        table, key = where.split("__")
        if value is None:
            data[table].pop(key)
        else:
            data[table][key] = value
    return data


@pytest.fixture
def stand_in(tmp_path) -> list[str]:
    script = tmp_path / "repair_plies_stand_in.py"
    script.write_text(STAND_IN, encoding="utf-8")
    return [sys.executable, str(script)]


@pytest.fixture
def here(tmp_path, monkeypatch, stand_in):
    """The local API: this process runs each job itself, one at a time, with no table and no store."""
    monkeypatch.setattr(coupon_jobs, "REPO", tmp_path)
    monkeypatch.setenv("STAND_IN_RELEASE", str(tmp_path / "release"))
    jobs = CouponJobs(None, lambda job, state, outcome: None, tmp_path / "jobs", plies=stand_in)
    monkeypatch.setattr(app.state, "coupon_jobs", jobs, raising=False)
    return jobs, tmp_path


def ended(job_id: str, until=("done", "stopped", "refused")) -> dict:
    deadline = time.monotonic() + 30
    while True:
        status = client.get(f"{RUNS}/{job_id}").json()
        if status["state"] in until:
            return status
        assert time.monotonic() < deadline, f"the run {job_id} is still {status['state']} after 30 s"
        time.sleep(0.02)


def test_the_hand_answer_says_what_the_ply_run_still_needs():
    whole = client.post(ANALYZE, json={"repair": example()}).json()
    assert whole["ply_needs"] == [] and whole["bond_needs"] == []
    without = client.post(ANALYZE, json={"repair": example(**{key: None for key in (
        "parent__fibre_tension_energy", "parent__fibre_compression_energy", "parent__matrix_tension_energy", "parent__matrix_shear_energy")})}).json()
    assert [need["path"] for need in without["ply_needs"]] == ["parent.fibre_tension_energy"] and without["bond_needs"] == []
    external = client.post(ANALYZE, json={"toml": EXTERNAL.read_text(encoding="utf-8")}).json()
    assert [need["path"].split(".")[1] for need in external["ply_needs"]] == ["fibre_tension_energy"] * len(external["ply_needs"]) != []


def test_a_run_goes_on_in_the_background_and_its_report_comes_back_with_its_status(here):
    answer = client.post(RUNS, json={"repair": example()})
    assert answer.status_code == 202 and answer.headers["Location"] == f"{RUNS}/{answer.json()['job_id']}"
    first = answer.json()
    assert first["state"] == "running" and first["repair"] == "Example stepped patch repair" and first["report"] is None and first["finer"] == 0
    status = ended(first["job_id"])
    assert status["state"] == "done" and status["stages_done"] == ["build", "soften", "raise", "close"] and status["message"] is None
    assert status["headline"] == HEADLINE and "headline" not in status["report"]
    assert status["report"]["load"] == {"held": 1207.5, "not_held": 1212.8}
    # the run is given less time than the queue's limit, a limit on its elements, and the mesh asked for
    assert status["report"]["model"]["given"] == [REPAIR_PLIES_OPTIONS[1], REPAIR_PLIES_OPTIONS[3], "0"] == ["540", "40000", "0"]
    jobs, _ = here
    description = json.loads((jobs.root / first["job_id"] / "repair.json").read_text(encoding="utf-8"))
    assert description == example(), "the tool reads the description the engine read"


def test_a_second_run_on_a_finer_mesh_and_a_repair_file_as_text(here):
    finer = client.post(RUNS, json={"toml": EXAMPLE.read_text(encoding="utf-8"), "finer": 1})
    assert finer.status_code == 202 and finer.json()["finer"] == 1
    assert ended(finer.json()["job_id"])["report"]["model"]["given"][2] == "1"
    assert client.post(RUNS, json={"repair": example(), "finer": 5}).status_code == 422


def test_the_engine_refuses_a_bad_description_and_one_that_lacks_what_the_run_needs_before_any_run_starts(here):
    jobs, _ = here
    refused = client.post(RUNS, json={"repair": {**example(), "units": "imperial"}})
    assert refused.status_code == 422 and "units must be one of" in refused.json()["detail"]
    lacking = client.post(RUNS, json={"toml": EXTERNAL.read_text(encoding="utf-8")})
    assert lacking.status_code == 422
    assert lacking.json()["detail"].startswith("To carry the repair until its plies and its bond cannot hold the load it needs: ")
    assert "fracture energies" in lacking.json()["detail"]
    assert jobs.jobs == {}, "nothing started"


def test_one_run_at_a_time_here_and_another_jobs_id_is_not_a_ply_run(here):
    jobs, tmp_path = here
    first = client.post(RUNS, json={"repair": example("WAIT")})
    assert first.status_code == 202
    second = client.post(RUNS, json={"repair": example()})
    assert second.status_code == 409 and second.json()["detail"] == "Another analysis is running. Wait for it to finish, then run this one."
    deadline = time.monotonic() + 30
    while (running := client.get(f"{RUNS}/{first.json()['job_id']}").json())["stage"] != "raise":  # the tool is starting
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert running["state"] == "running" and running["stages_done"] == ["build", "soften"] and running["stages"] == ["build", "soften", "raise", "close"]
    (tmp_path / "release").write_text("go", encoding="utf-8")
    assert ended(first.json()["job_id"])["state"] == "done"
    assert client.get(f"{RUNS}/{uuid.uuid4()}").status_code == 404
    other = next(iter(jobs.jobs.values()))
    other.inputs = {"kind": "wing", "wing": "Example straight wing", "description": {}}  # a wing's check of this process: not a ply run
    assert client.get(f"{RUNS}/{other.id}").status_code == 404
    assert client.get(f"/v1/wings/checks/{first.json()['job_id']}").status_code == 200, "and it reads as the wing's check it now is"


def test_the_tools_refusal_is_shown_and_a_stop_says_what_to_do_never_the_cause(here):
    refused = ended(client.post(RUNS, json={"repair": example("REFUSE")}).json()["job_id"])
    assert refused["state"] == "refused" and refused["message"] == "The slice would have 48,000 elements, and this run takes at most 40,000."
    stopped = ended(client.post(RUNS, json={"repair": example("CRASH")}).json()["job_id"])
    assert stopped["state"] == "stopped" and stopped["message"] == PLIES_STOPPED and stopped["report"] is None
    assert "SuperLU" not in json.dumps(stopped)


def test_without_the_tool_the_run_is_unavailable_and_a_wings_check_is_not_a_ply_run(tmp_path, monkeypatch):
    monkeypatch.setattr(app.state, "coupon_jobs", CouponJobs(None, lambda *a: None, tmp_path / "jobs", plies=None), raising=False)
    answer = client.post(RUNS, json={"repair": example()})
    assert answer.status_code == 503 and answer.json()["detail"] == "The run could not be started right now. Try again in a minute."


# ------------------------------------------------------------------------------------------- through the job queue (ADR-0056)

@pytest.fixture
def queue(tmp_path, monkeypatch, empty_runs, stand_in):
    """The API's container (`queue`) and one solver container sharing one store and the test database, the stand-in as the run's tool."""
    monkeypatch.setattr(coupon_jobs, "REPO", tmp_path)
    monkeypatch.setattr(coupon_jobs, "HEARTBEAT_S", 0.05)
    monkeypatch.setenv("STAND_IN_RELEASE", str(tmp_path / "release"))
    store = MemoryStore()
    monkeypatch.setattr(app.state, "records", empty_runs, raising=False)  # the receipts go to the test database
    recorder = job_recorder(app)
    front = CouponJobs([sys.executable, "-c", "pass"], recorder, tmp_path / "api" / "jobs", store=store, table=empty_runs, role="queue", plies=stand_in)
    solver = CouponJobs([sys.executable, "-c", "pass"], recorder, tmp_path / "solver" / "jobs", store=store, table=empty_runs, role="solver", plies=stand_in)
    monkeypatch.setattr(app.state, "coupon_jobs", front, raising=False)
    return front, solver, store, empty_runs


@needs_test_database
def test_through_the_queue_a_solver_makes_the_run_and_the_api_reads_its_report_back_from_the_store(queue):
    front, solver, store, table = queue
    answer = client.post(RUNS, json={"repair": example(), "finer": 1})
    assert answer.status_code == 202 and answer.headers[ENQUEUE_HEADER] == answer.json()["job_id"] and answer.json()["state"] == "queued"
    job_id = uuid.UUID(answer.json()["job_id"])
    row = fetch_job(table, job_id)
    assert row.state == "queued" and front.jobs == {}
    assert row.inputs == {"kind": "repair_plies", "repair": "Example stepped patch repair", "description": example(), "finer": 1}, "the description travels in the row"
    assert store.objects == {}, "nothing is filed before a solver takes it"
    job = solver.take(job_id)
    deadline = time.monotonic() + 30
    while job.state != "done" or fetch_job(table, job_id).state != "done":
        assert time.monotonic() < deadline, f"the run is {job.state} after 30 s"
        time.sleep(0.02)
    row = fetch_job(table, job_id)
    assert row.stored == {"repair_plies": job_output_key(str(job_id), "repair-plies.json")} and row.stored["repair_plies"] in store.objects
    status = client.get(f"{RUNS}/{job_id}").json()
    assert status["state"] == "done" and status["headline"] == HEADLINE and status["report"]["model"]["given"] == ["540", "40000", "1"]
    run = fetch_run(table, uuid.UUID(status["run_id"]))
    assert run.endpoint == RUNS and run.status == "solved" and run.inputs["description"] == example() and run.response["job_id"] == str(job_id)
    assert client.get(f"/v1/coupon-jobs/{job_id}").json()["coupon"] is None, "the list of past analyses keeps coupon runs only (lib/run-history.ts)"


@needs_test_database
def test_through_the_queue_the_per_job_timeout_stops_the_run(queue):
    front, solver, store, table = queue
    job_id = uuid.UUID(client.post(RUNS, json={"repair": example("WAIT")}).json()["job_id"])
    job = solver.take(job_id)
    deadline = time.monotonic() + 30
    while job.process is None:
        assert time.monotonic() < deadline
        time.sleep(0.02)
    solver.stop(job_id, "the job ran longer than the 12 minutes allowed")
    while fetch_job(table, job_id).state != "stopped":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    status = client.get(f"{RUNS}/{job_id}").json()
    assert status["state"] == "stopped" and status["message"] == PLIES_STOPPED and store.objects == {}
