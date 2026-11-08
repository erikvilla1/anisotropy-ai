"""The job queue (ADR-0056 stage 3, amendment 3): the API's container files a job as `queued` with its input in the store; a solver
container claims it, names its coupon under the naming lock, claims the coupon at the tool's gate and runs; many jobs run at once,
one per coupon; a job whose coupon another job holds goes back to the queue and later numbers the next attempt; a running job's
files are read through the API's container from the store; a lost job is swept. A stand-in plays the tool with its gate, so these
tests need neither CalculiX nor the fea environment; fea/tests/test_run_coupon.py tests the tool's gate itself."""

import datetime as dt
import json
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import coupon_jobs
from anisotropy_api.coupon_jobs import CouponJobs, JobRefused
from anisotropy_api.main import ENQUEUE_HEADER, app, job_recorder
from anisotropy_api.records import fetch_job, update_job
from anisotropy_api.storage import input_key

from conftest import needs_test_database
from memory_store import MemoryStore

pytestmark = needs_test_database

STAND_IN = r'''
"""A stand-in for fea/tools/run_coupon.py with its gate: the coupon is the source's name or the values' "coupon"; it writes the
spec, holds at the gate, numbers the next attempt from the coupon's folder, reports the fields, and waits for a release file when
the coupon's name starts with WAIT."""
import argparse, json, os, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("source")
for option in ("--run-by", "--result", "--progress", "--gate"):
    parser.add_argument(option, required=True)
for flag in ("--replace", "--no-pdf", "--no-theory"):
    parser.add_argument(flag, action="store_true")
args = parser.parse_args()
root = pathlib.Path(os.environ["STAND_IN_ROOT"])
result, progress = pathlib.Path(args.result), pathlib.Path(args.progress)
source = pathlib.Path(args.source)
coupon = json.loads(source.read_text(encoding="utf-8"))["coupon"] if source.suffix == ".json" else args.source
ours = root / coupon / "ours"
ours.mkdir(parents=True, exist_ok=True)
(ours / f"{coupon}.toml").write_text("the spec", encoding="utf-8")

def write(stage, held, attempt=None, outputs=None):
    progress.write_text(json.dumps({"stage": stage, "done": [], "stages": ["the input", "CalculiX"], "coupon": coupon, "held": held,
                                    "attempt": None if attempt is None else str(attempt), "outputs": outputs or {}}), encoding="utf-8")

print("== the input", flush=True)
write("the input", True)
gate = pathlib.Path(args.gate)
while not gate.is_file():
    time.sleep(0.02)
word = gate.read_text(encoding="utf-8")
if word != "go":
    result.write_text(json.dumps({"status": "refused", "message": word, "coupon": None, "attempt": None, "outputs": {}}), encoding="utf-8")
    sys.exit(1)
runs = ours / "runs"
runs.mkdir(exist_ok=True)
number = max([int(d.name[8:10]) for d in runs.iterdir()] or [1]) + 1
attempt = runs / f"attempt-{number:02d}_2026-11-07"
(attempt / "run").mkdir(parents=True)
fields = attempt / "run" / "fields.json"
fields.write_text(json.dumps({"attempt": number}), encoding="utf-8")
write("CalculiX", False, attempt, {"fields": str(fields)})
print(f"== CalculiX, attempt {number:02d}", flush=True)
if coupon.startswith("WAIT"):
    while not (root.parent / f"release-{coupon}").exists():
        time.sleep(0.02)
package = attempt / "package"
package.mkdir()
(package / "doc.pdf").write_bytes(b"%PDF")
result.write_text(json.dumps({"status": "done", "message": f"attempt {number:02d}", "coupon": coupon, "attempt": str(attempt),
                              "outputs": {"fields": str(fields), "package": str(package)}}), encoding="utf-8")
'''


@pytest.fixture
def queue(tmp_path, monkeypatch, empty_runs):
    """The API's container (`queue`) and two solver containers sharing one store and the test database, the stand-in as their tool."""
    monkeypatch.setattr(coupon_jobs, "REPO", tmp_path)  # the stand-in's files lie under tmp_path; the rule of what may be served holds
    monkeypatch.setattr(coupon_jobs, "HEARTBEAT_S", 0.05)
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    store = MemoryStore()
    recorder = job_recorder(app)

    def solver(name):
        root = tmp_path / name / "coupons"
        return CouponJobs([sys.executable, str(stand_in)], recorder, tmp_path / name / "jobs", store=store, table=empty_runs, local_root=root,
                          role="solver")

    front = CouponJobs([sys.executable, str(stand_in)], recorder, tmp_path / "api" / "jobs", store=store, table=empty_runs,
                       local_root=tmp_path / "api" / "coupons", role="queue")
    monkeypatch.setattr(app.state, "coupon_jobs", front, raising=False)
    first, second = solver("solver-1"), solver("solver-2")
    return front, first, second, store, empty_runs, tmp_path


def solving(solver: CouponJobs, job_id: uuid.UUID, monkeypatch, *, until=("done", "stopped", "refused", "queued")):
    """Take the job in the solver (its stand-in reads its own coupons root) and wait until it reaches a state in `until`, both in
    the solver and on its row: the solver sets the job's state a moment before it writes the row, so the row can lag behind."""
    monkeypatch.setenv("STAND_IN_ROOT", str(solver.local_root))
    job = solver.take(job_id)
    assert job is not None, f"the solver did not take {job_id}"
    deadline = time.monotonic() + 30
    while job.state not in until or fetch_job(solver.table, job_id).state != job.state:
        assert time.monotonic() < deadline, f"coupon job {job_id} is {job.state}, its row {fetch_job(solver.table, job_id).state}, after 30 s"
        time.sleep(0.02)
    return job


def held_until(job, condition, what):
    deadline = time.monotonic() + 30
    while not condition():
        assert time.monotonic() < deadline, f"coupon job {job.id}: never {what}"
        time.sleep(0.02)


client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})


def queued(coupon: str | None = None, values: dict | None = None) -> str:
    body = {"coupon": coupon} if coupon is not None else {"values": values}
    answer = client.post("/v1/coupon-jobs", json={**body, "run_by": "A. Engineer", "pdf": False})
    assert answer.status_code == 202, answer.text
    assert answer.json()["state"] == "queued" and answer.headers[ENQUEUE_HEADER] == answer.json()["job_id"]
    return answer.json()["job_id"]


def test_the_api_container_files_a_job_for_the_queue_and_runs_nothing(queue):
    front, _, _, store, table, _ = queue
    job_id = queued(values={"coupon": "IM7-UNT-L1", "form_version": "0.7"})
    row = fetch_job(table, uuid.UUID(job_id))
    assert row.state == "queued" and row.source == input_key(job_id, f"values-{uuid.UUID(job_id).hex[:8]}.json") and row.source in store.objects
    assert json.loads(store.objects[row.source][0]) == {"coupon": "IM7-UNT-L1", "form_version": "0.7"}  # the values as the tool reads them
    assert row.options == ["--run-by", "A. Engineer", "--no-pdf"] and front.jobs == {}  # nothing runs in the API's container
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "queued" and status["message"] == "waiting for a free solver"
    second = client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"})
    assert second.status_code == 202 and ENQUEUE_HEADER in second.headers  # no one-at-a-time 409 any more
    assert client.get(f"/v1/coupon-jobs/{second.json()['job_id']}").json()["message"] == "waiting for a free solver; 1 job(s) ahead of this one"


def test_a_solver_runs_the_queued_job_and_the_api_reads_it_back_from_the_row_and_the_store(queue, monkeypatch):
    front, solver, _, store, table, _ = queue
    job_id = queued("IM7-UNT-L1")
    job = solving(solver, uuid.UUID(job_id), monkeypatch)
    assert job.state == "done" and job.outcome["message"] == "attempt 02"
    row = fetch_job(table, uuid.UUID(job_id))
    assert row.state == "done" and row.coupon == "IM7-UNT-L1" and set(row.stored) == {"fields", "package"} and row.heartbeat_at is not None
    assert row.peak_memory_bytes is None or row.peak_memory_bytes > 0  # cgroup v2's memory.peak where this runs in a container
    assert "coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml" in store.objects  # the coupon's folder, for the next container
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "done" and status["message"] == "attempt 02"
    fields = client.get(f"/v1/coupon-jobs/{job_id}/files/fields", follow_redirects=False)
    assert fields.status_code == 307 and fields.headers["location"].startswith("https://store.test/coupons/IM7-UNT-L1/attempt-02_2026-11-07/files/fields/")
    assert solver.take(uuid.UUID(job_id)).state == "done"  # the job as this solver ran it; a new delivery claims nothing (below)
    assert CouponJobs(solver.command, solver.recorder, solver.root, store=store, table=table, role="solver").take(uuid.UUID(job_id)) is None


def test_jobs_on_two_coupons_run_at_once_in_two_solvers(queue, monkeypatch):
    _, first, second, _, table, tmp_path = queue
    a, b = uuid.UUID(queued("WAIT-A")), uuid.UUID(queued("WAIT-B"))
    job_a = solving(first, a, monkeypatch, until=("running",))
    held_until(job_a, lambda: (job_a.progress() or {}).get("stage") == "CalculiX", "past the gate")
    job_b = solving(second, b, monkeypatch, until=("running",))
    held_until(job_b, lambda: (job_b.progress() or {}).get("stage") == "CalculiX", "past the gate")
    assert {fetch_job(table, a).state, fetch_job(table, b).state} == {"running"}  # both at once
    assert (fetch_job(table, a).coupon, fetch_job(table, b).coupon) == ("WAIT-A", "WAIT-B")
    for coupon, job in (("WAIT-A", job_a), ("WAIT-B", job_b)):
        (tmp_path / first.local_root.parent.name / f"release-{coupon}").touch()
        (tmp_path / second.local_root.parent.name / f"release-{coupon}").touch()
        held_until(job, lambda job=job: job.state == "done", "done")


def test_a_second_job_on_a_coupon_goes_back_to_the_queue_and_later_numbers_the_next_attempt(queue, monkeypatch):
    _, first, second, _, table, tmp_path = queue
    a, b = uuid.UUID(queued("WAIT-C")), uuid.UUID(queued("WAIT-C"))
    job_a = solving(first, a, monkeypatch, until=("running",))
    held_until(job_a, lambda: fetch_job(table, a).coupon == "WAIT-C", "holding its coupon")
    job_b = solving(second, b, monkeypatch, until=("queued",))  # the gate refused it: another job holds the coupon
    row = fetch_job(table, b)
    assert row.state == "queued" and row.coupon is None and f"another job ({a}) is solving the coupon WAIT-C" in row.message
    status = client.get(f"/v1/coupon-jobs/{b}").json()
    assert status["state"] == "queued" and "is solving the coupon WAIT-C" in status["message"]
    (tmp_path / "solver-1" / "release-WAIT-C").touch()
    held_until(job_a, lambda: job_a.state == "done", "done")
    (tmp_path / "solver-2" / "release-WAIT-C").touch()
    job_b = solving(second, b, monkeypatch)  # delivered again: now it runs, on the coupon as the first job left it in the store
    assert job_a.outcome["message"] == "attempt 02" and job_b.state == "done" and job_b.outcome["message"] == "attempt 03"


def test_a_running_jobs_fields_are_read_through_the_api_from_the_store(queue, monkeypatch):
    _, solver, _, _, table, tmp_path = queue
    job_id = uuid.UUID(queued("WAIT-D"))
    job = solving(solver, job_id, monkeypatch, until=("running",))
    held_until(job, lambda: "fields" in (fetch_job(table, job_id).stored or {}), "filing its fields while it runs")
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "running" and status["stage"] == "CalculiX" and "fields" in status["outputs"] and "== the input" in status["log_tail"]
    fields = client.get(f"/v1/coupon-jobs/{job_id}/files/fields", follow_redirects=False)
    assert fields.status_code == 307 and "/files/fields/fields.json" in fields.headers["location"]
    (tmp_path / "solver-1" / "release-WAIT-D").touch()
    held_until(job, lambda: job.state == "done", "done")


def test_the_per_job_timeout_stops_the_tool(queue, monkeypatch):
    _, solver, _, _, table, _ = queue
    job_id = uuid.UUID(queued("WAIT-E"))
    job = solving(solver, job_id, monkeypatch, until=("running",))
    held_until(job, lambda: (job.progress() or {}).get("stage") == "CalculiX", "past the gate")
    solver.stop(job_id, "the job ran longer than 12 minutes, the per-job limit")
    held_until(job, lambda: job.state == "stopped" and fetch_job(table, job_id).state == "stopped", "stopped, here and on its row")
    row = fetch_job(table, job_id)
    assert row.state == "stopped" and row.message == "the job ran longer than 12 minutes, the per-job limit" and row.coupon is None


class SlowFolderStore(MemoryStore):
    """A store whose uploads of the coupon's folder take a while, as the hosted bucket's can once the folder has grown."""

    def __init__(self):
        super().__init__()
        self.slow_since: float | None = None

    def put(self, key, path, content_type, disposition=None):
        if "/folder/" in key:
            self.slow_since = self.slow_since or time.monotonic()
            time.sleep(0.3)
        super().put(key, path, content_type, disposition)


class RefusingLiveStore(MemoryStore):
    """A store that refuses a running job's files while `refusing`, as a bucket that is slow or gone for a while would."""

    def __init__(self):
        super().__init__()
        self.refusing = True
        self.refused = 0

    def put(self, key, path, content_type, disposition=None):
        if self.refusing and "/files/" in key:
            self.refused += 1
            raise OSError("the bucket did not answer")
        super().put(key, path, content_type, disposition)


def test_the_heartbeat_goes_on_through_the_finishs_uploads(queue, monkeypatch):
    """The sweep stops a running job silent for two minutes; the uploads at a job's end must not be such a silence (ADR-0056 amendment 5)."""
    front, _, _, _, table, tmp_path = queue
    store = SlowFolderStore()
    solver = CouponJobs(front.command, front.recorder, tmp_path / "slow" / "jobs", store=store, table=table, local_root=tmp_path / "slow" / "coupons",
                        role="solver")
    beats: list[float] = []
    real = coupon_jobs.update_job

    def spied(engine, job_id, **fields):
        if "state" not in fields:  # a heartbeat; the end writes the state
            beats.append(time.monotonic())
        return real(engine, job_id, **fields)

    monkeypatch.setattr(coupon_jobs, "update_job", spied)
    job = solving(solver, uuid.UUID(queued("IM7-UNT-L1")), monkeypatch)
    assert job.state == "done" and store.slow_since is not None
    assert any(t > store.slow_since + 0.3 for t in beats), "no beat landed while the coupon's folder was uploading"
    assert fetch_job(table, job.id).heartbeat_at >= fetch_job(table, job.id).finished_at - dt.timedelta(seconds=1)  # the last sign of life goes with the end


def test_a_bucket_that_refuses_the_running_files_does_not_silence_the_heartbeat(queue, monkeypatch):
    front, _, _, _, table, tmp_path = queue
    store = RefusingLiveStore()
    solver = CouponJobs(front.command, front.recorder, tmp_path / "refusing" / "jobs", store=store, table=table,
                        local_root=tmp_path / "refusing" / "coupons", role="solver")
    job_id = uuid.UUID(queued("WAIT-F"))
    job = solving(solver, job_id, monkeypatch, until=("running",))
    held_until(job, lambda: store.refused >= 2, "asked the bucket twice for the fields")
    first = fetch_job(table, job_id).heartbeat_at
    held_until(job, lambda: fetch_job(table, job_id).heartbeat_at > first, "a later beat while the bucket refuses")
    assert fetch_job(table, job_id).stored == {} and fetch_job(table, job_id).stage == "CalculiX"
    store.refusing = False
    held_until(job, lambda: "fields" in (fetch_job(table, job_id).stored or {}), "the fields filed once the bucket answered")
    (tmp_path / "refusing" / "release-WAIT-F").touch()
    held_until(job, lambda: job.state == "done", "done")


def test_a_job_whose_solver_went_silent_is_swept_and_its_coupon_freed(queue, monkeypatch):
    front, solver, _, _, table, _ = queue
    lost, after = uuid.UUID(queued("IM7-OHT-L1")), uuid.UUID(queued("IM7-OHT-L1"))
    update_job(table, lost, state="running", coupon="IM7-OHT-L1", heartbeat_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))
    job = solving(solver, after, monkeypatch)  # the gate finds the coupon held by a silent job, sweeps it, and runs
    assert job.state == "done" and fetch_job(table, lost).state == "stopped" and "stopped answering" in fetch_job(table, lost).message


def test_the_roles_keep_to_their_own_routes(queue, monkeypatch):
    front, solver, _, _, _, _ = queue
    job_id = queued("IM7-UNT-L1")
    assert client.post(f"/v1/solver/jobs/{job_id}").status_code == 404  # the API's container has no solver routes
    with pytest.raises(JobRefused, match="does not run queued jobs"):
        front.take(uuid.UUID(job_id))
    with pytest.raises(JobRefused, match="runs the queued jobs it is given"):
        solver.start("test", {}, [], coupon="IM7-UNT-L1")
    monkeypatch.setattr(app.state, "coupon_jobs", solver)
    monkeypatch.setenv("STAND_IN_ROOT", str(solver.local_root))
    taken = client.post(f"/v1/solver/jobs/{job_id}")
    assert taken.status_code == 202 and taken.json()["state"] == "running"
    deadline = time.monotonic() + 30
    while (state := client.get(f"/v1/solver/jobs/{job_id}").json()["state"]) == "running":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert state == "done"
    assert client.post(f"/v1/solver/jobs/{job_id}").status_code == 200  # this solver's job as it stands, not run twice
    assert client.post(f"/v1/solver/jobs/{uuid.uuid4()}").status_code == 409  # not queued: the consumer lets the message go
    assert client.get(f"/v1/solver/jobs/{uuid.uuid4()}").status_code == 404


def test_peak_memory_reads_cgroup_v2_then_v1_and_is_none_outside_a_container(tmp_path):
    v2, v1 = tmp_path / "memory.peak", tmp_path / "memory.max_usage_in_bytes"
    assert coupon_jobs.peak_memory((v2, v1)) is None  # neither file: not a container
    v1.write_text("432361472\n", encoding="ascii")
    assert coupon_jobs.peak_memory((v2, v1)) == 432361472  # a Docker host still on cgroup v1
    v2.write_text("299454464\n", encoding="ascii")
    assert coupon_jobs.peak_memory((v2, v1)) == 299454464  # cgroup v2 first
