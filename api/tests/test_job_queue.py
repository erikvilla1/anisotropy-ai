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
from anisotropy_api.storage import input_key, owner_key

from conftest import needs_test_database
from memory_store import MemoryStore
from typesetter_stub import stand_in_typesetter

pytestmark = needs_test_database

STAND_IN = r'''
"""A stand-in for fea/tools/run_coupon.py with its gate: the coupon is the source's name or the values' "coupon"; it writes the
spec, holds at the gate, numbers the next attempt from the coupon's folder, reports the fields, and waits for a release file when
the coupon's name starts with WAIT."""
import argparse, json, os, pathlib, sys, time, zipfile
parser = argparse.ArgumentParser()
parser.add_argument("source")
for option in ("--run-by", "--result", "--progress", "--gate"):
    parser.add_argument(option, required=True)
for flag in ("--replace", "--no-pdf", "--no-theory"):
    parser.add_argument(flag, action="store_true")
args = parser.parse_args()
root = pathlib.Path(os.environ["ANISOTROPY_COUPONS_ROOT"])  # the folder of coupons the solver started the tool with (ADR-0106)
releases = pathlib.Path(os.environ["STAND_IN_ROOT"]).parent  # where a test lets a waiting job go on
result, progress = pathlib.Path(args.result), pathlib.Path(args.progress)
source = pathlib.Path(args.source)
coupon = json.loads(source.read_text(encoding="utf-8"))["coupon"] if source.suffix == ".json" else args.source
ours = root / coupon / "ours"
ours.mkdir(parents=True, exist_ok=True)

def write(stage, held, attempt=None, outputs=None, result=None):
    progress.write_text(json.dumps({"stage": stage, "done": [], "stages": ["the input", "CalculiX"], "coupon": coupon, "held": held,
                                    "attempt": None if attempt is None else str(attempt), "outputs": outputs or {}, "result": result}),
                        encoding="utf-8")

gate = pathlib.Path(args.gate)

def hold(stage, named):
    """The tool's two holds (ADR-0056 amendment 6): before the coupon is named, and once it is; the word is read once each time."""
    progress.write_text(json.dumps({"stage": stage, "done": [], "stages": ["the input", "CalculiX"], "coupon": coupon if named else None, "held": True,
                                    "attempt": None, "outputs": {}, "result": None}), encoding="utf-8")
    while not gate.is_file():
        time.sleep(0.02)
    word = gate.read_text(encoding="utf-8")
    gate.unlink()
    if word != "go":
        result.write_text(json.dumps({"status": "refused", "message": word, "coupon": None, "attempt": None, "outputs": {}}), encoding="utf-8")
        sys.exit(1)

print("== the setup check", flush=True)
hold("the setup check", False)
print("== the input", flush=True)
(ours / f"{coupon}.toml").write_text("the spec", encoding="utf-8")
hold("the input", True)
runs = ours / "runs"
runs.mkdir(exist_ok=True)
number = max([int(d.name[8:10]) for d in runs.iterdir()] or [1]) + 1
attempt = runs / f"attempt-{number:02d}_2026-11-07"
(attempt / "run").mkdir(parents=True)
fields = attempt / "run" / "fields.json"
fields.write_text(json.dumps({"attempt": number}), encoding="utf-8")
write("CalculiX", False, attempt, {"fields": str(fields)})
print(f"== CalculiX, attempt {number:02d}", flush=True)
if coupon.startswith("WAIT-AGAIN"):  # the fields written a second time with what came later, then the result reported (ADR-0056 amendment 11)
    while not (releases / f"again-{coupon}").exists():
        time.sleep(0.02)
    fields.write_text(json.dumps({"attempt": number, "calculix": "beside ours"}), encoding="utf-8")
    write("the result", False, attempt, {"fields": str(fields)}, result=f"attempt {number:02d}")
if coupon.startswith("WAIT-RESULT"):  # the result reported, the package still to build (ADR-0064)
    write("the package", False, attempt, {"fields": str(fields)}, result=f"attempt {number:02d}")
if coupon.startswith("WAIT"):
    while not (releases / f"release-{coupon}").exists():
        time.sleep(0.02)
package = attempt / "package"
package.mkdir()
outputs = {"fields": str(fields), "package": str(package)}
if "--no-pdf" in sys.argv and not coupon.startswith("NO-SOURCE"):  # as the tool without its PDF: the report's LaTeX and figures, this attempt's own (ADR-0064 amendment 3); a coupon NO-SOURCE* stands for a run that could not write them
    source = attempt / "run" / f"{coupon}-report-source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(f"{coupon}.tex", f"the report of {coupon}, attempt {number:02d}")
        archive.writestr("figures/model.png", "a figure")
    outputs["document_source"] = str(source)
if "--no-pdf" not in sys.argv and not coupon.startswith("NO-DOC"):  # as the tool: the PDF by its own key; a coupon NO-DOC* stands for a failed PDF
    (package / "doc.pdf").write_bytes(b"%PDF")
    outputs["document"] = str(package / "doc.pdf")
result.write_text(json.dumps({"status": "done", "message": f"attempt {number:02d}", "coupon": coupon, "attempt": str(attempt),
                              "outputs": outputs}), encoding="utf-8")
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
    """Take the job in the solver (its stand-in waits for its release beside the solver's own coupons) and wait until it reaches a state in `until`, both in
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


def queued(coupon: str | None = None, values: dict | None = None, pdf: bool = False) -> str:
    body = {"coupon": coupon} if coupon is not None else {"values": values}
    answer = client.post("/v1/coupon-jobs", json={**body, "run_by": "A. Engineer", "pdf": pdf})
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
    assert status["state"] == "queued" and status["message"] == "queued"
    second = client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"})
    assert second.status_code == 202 and ENQUEUE_HEADER in second.headers  # no one-at-a-time 409 any more
    assert client.get(f"/v1/coupon-jobs/{second.json()['job_id']}").json()["message"] == "queued; 1 ahead"


def test_a_solver_runs_the_queued_job_and_the_api_reads_it_back_from_the_row_and_the_store(queue, monkeypatch):
    front, solver, _, store, table, _ = queue
    job_id = queued("IM7-UNT-L1")
    job = solving(solver, uuid.UUID(job_id), monkeypatch)
    assert job.state == "done" and job.outcome["message"] == "attempt 02"
    row = fetch_job(table, uuid.UUID(job_id))
    assert row.state == "done" and row.coupon == "IM7-UNT-L1" and set(row.stored) == {"fields", "package", "document_source"} and row.heartbeat_at is not None
    assert row.peak_memory_bytes is None or row.peak_memory_bytes > 0  # cgroup v2's memory.peak where this runs in a container
    assert "coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml" in store.objects  # the coupon's folder, for the next container
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "done" and status["message"] == "attempt 02"
    fields = client.get(f"/v1/coupon-jobs/{job_id}/files/fields", follow_redirects=False)
    assert fields.status_code == 307 and fields.headers["location"].startswith("https://store.test/coupons/IM7-UNT-L1/attempt-02_2026-11-07/files/fields/")
    assert solver.take(uuid.UUID(job_id)).state == "done"  # the job as this solver ran it; a new delivery claims nothing (below)
    assert CouponJobs(solver.command, solver.recorder, solver.root, store=store, table=table, role="solver").take(uuid.UUID(job_id)) is None


def test_a_signed_in_persons_job_keeps_its_coupon_in_their_own_folder_and_under_their_own_prefix(queue, monkeypatch):
    """ADR-0106: the solver starts the tool with the job's owner's folder and files it under their prefix; two people's coupons of
    one name are two coupons, each numbering its own attempts; a job with no email keeps the shared folder and `coupons/`."""
    front, solver, _, store, table, _ = queue
    mine, theirs = "a.engineer@example.com", "other.engineer@example.com"
    values = json.dumps({"coupon": "IM7-UNT-L1", "form_version": "0.7"}).encode()
    ran = {}
    for who in (mine, theirs, mine, None):
        filed = front.start("browser", {"values": "x"}, ["--run-by", "A. Engineer", "--no-pdf"], values=values, user_email=who)
        ran.setdefault(who, []).append(solving(solver, filed.id, monkeypatch))
    assert [job.outcome["message"] for job in ran[mine]] == ["attempt 02", "attempt 03"]  # my second run numbers on from my first
    assert ran[theirs][0].outcome["message"] == "attempt 02" and ran[None][0].outcome["message"] == "attempt 02"  # theirs and the shared one start their own

    for who in (mine, theirs):
        key = owner_key(who)
        assert f"owners/{key}/coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml" in store.objects
        row = fetch_job(table, ran[who][0].id)
        assert row.stored["fields"].startswith(f"owners/{key}/coupons/IM7-UNT-L1/attempt-02_2026-11-07/files/fields/")
        assert row.stored["package"] == f"owners/{key}/coupons/IM7-UNT-L1/attempt-02_2026-11-07/package.zip"
    assert "coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml" in store.objects and fetch_job(table, ran[None][0].id).stored["fields"].startswith("coupons/IM7-UNT-L1/")
    assert not any("@" in key or "example" in key for key in store.objects), "no key holds an address"
    assert sorted(p.name for p in (solver.local_root / "IM7-UNT-L1" / "ours" / "runs").iterdir()) == ["attempt-02_2026-11-07"]
    assert list(solver.owners_root.iterdir()) == []  # a solver's disk keeps no person's coupons past the next person's job: my third attempt came by the store
    again = front.start("browser", {"values": "x"}, ["--run-by", "A. Engineer", "--no-pdf"], values=values, user_email=theirs)
    assert solving(solver, again.id, monkeypatch).outcome["message"] == "attempt 03" and [p.name for p in solver.owners_root.iterdir()] == [owner_key(theirs)]

    # the API's container reads each person's coupons from their own prefix into their own folder, when they ask
    assert not front.owners_root.exists()
    assert front.has_coupon("IM7-UNT-L1", mine) and front.has_coupon("IM7-UNT-L1", theirs) and not front.has_coupon("IM7-UNT-L1", "nobody@example.com")
    assert sorted(p.name for p in front.owners_root.iterdir()) == sorted([owner_key(mine), owner_key(theirs), owner_key("nobody@example.com")])
    assert sorted(p.name for p in (front.root_of(mine) / "IM7-UNT-L1" / "ours" / "runs").iterdir()) == ["attempt-02_2026-11-07", "attempt-03_2026-11-07"]
    assert not front.has_coupon("../IM7-UNT-L1", mine) and not front.has_coupon("", mine)
    assert not front.local_root.exists() and front.has_coupon("IM7-UNT-L1", None) and front.local_root.is_dir()  # the shared folder, level only once asked


def test_a_solver_that_runs_a_job_is_busy_for_the_next_and_its_row_carries_the_timings(queue, monkeypatch):
    _, solver, _, _, table, tmp_path = queue
    a, b = uuid.UUID(queued("WAIT-E")), uuid.UUID(queued("PLAIN-F"))
    job_a = solving(solver, a, monkeypatch, until=("running",))
    held_until(job_a, lambda: (job_a.progress() or {}).get("stage") == "CalculiX", "past the gate")
    with pytest.raises(coupon_jobs.SolverBusy, match=f"this solver runs coupon job {a}"):  # one job at a time on one container's disk
        solver.take(b)
    assert fetch_job(table, b).state == "queued"  # not claimed: the pool's next solver takes it
    (tmp_path / solver.local_root.parent.name / "release-WAIT-E").touch()
    held_until(job_a, lambda: job_a.state == "done", "done")
    row = fetch_job(table, a)
    assert row.claimed_at is not None and row.claimed_at >= row.started_at
    assert {"restore_s", "lock_wait_s", "gate_s", "upload_s"} <= set(row.timings) and all(isinstance(v, (int, float)) for v in row.timings.values())
    assert client.get(f"/v1/coupon-jobs/{a}").json()["timings"] == row.timings
    job_b = solving(solver, b, monkeypatch)  # the solver is free again
    assert job_b.state == "done"


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


def test_a_running_jobs_result_is_read_back_from_its_row_before_the_package(queue, monkeypatch):
    """ADR-0064: the solver's heartbeat writes the result to the row's message as soon as the tool reports it, so the API's container
    shows it while the solver still builds the package; the row's message before then is empty."""
    _, solver, _, _, table, tmp_path = queue
    job_id = uuid.UUID(queued("WAIT-RESULT"))
    job = solving(solver, job_id, monkeypatch, until=("running",))
    held_until(job, lambda: fetch_job(table, job_id).message == "attempt 02", "writing its result to the row")
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "running" and status["stage"] == "the package" and status["result"] == status["message"] == "attempt 02"
    assert status["documents"] == "building"
    (tmp_path / "solver-1" / "release-WAIT-RESULT").touch()
    held_until(job, lambda: fetch_job(table, job_id).state == "done", "done on its row")  # the API's container reads the row
    ended = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert ended["state"] == "done" and ended["result"] == "attempt 02" and ended["documents"] == "written"


def test_the_row_says_the_result_once_the_fields_that_go_with_it_are_filed(queue, monkeypatch):
    """ADR-0056 amendment 11: a running job's fields are filed again when the tool has written them anew (CalculiX's numbers, then the
    mesh study), and the row says the result's line only once that copy is in the store: the page reads the fields when the line shows."""
    _, solver, _, store, table, tmp_path = queue
    job_id = uuid.UUID(queued("WAIT-AGAIN"))
    job = solving(solver, job_id, monkeypatch, until=("running",))
    held_until(job, lambda: "fields" in (fetch_job(table, job_id).stored or {}), "filing its fields while it runs")
    key = fetch_job(table, job_id).stored["fields"]
    assert json.loads(store.objects[key][0]) == {"attempt": 2} and fetch_job(table, job_id).message is None

    seen: list[dict] = []
    real = coupon_jobs.update_job

    def spied(engine, job, **fields):
        if fields.get("message") == "attempt 02" and "state" not in fields:  # the beat that first says the result
            seen.append(json.loads(store.objects[key][0]))
        return real(engine, job, **fields)

    monkeypatch.setattr(coupon_jobs, "update_job", spied)
    (tmp_path / "solver-1" / "again-WAIT-AGAIN").touch()
    held_until(job, lambda: fetch_job(table, job_id).message == "attempt 02", "writing its result to the row")
    assert seen and seen[0] == {"attempt": 2, "calculix": "beside ours"}  # filed before the row said so
    assert fetch_job(table, job_id).stage == "the result" and fetch_job(table, job_id).stored["fields"] == key
    (tmp_path / "solver-1" / "release-WAIT-AGAIN").touch()
    held_until(job, lambda: job.state == "done", "done")


def test_a_new_stage_reaches_the_row_without_waiting_for_the_next_beat(queue, monkeypatch):
    """ADR-0056 amendment 11: the solver looks at its job every LOOK_S and writes the row when the stage or the filed files changed,
    and otherwise only every HEARTBEAT_S."""
    front, _, _, _, table, tmp_path = queue
    monkeypatch.setattr(coupon_jobs, "HEARTBEAT_S", 30.0)
    monkeypatch.setattr(coupon_jobs, "LOOK_S", 0.05)
    solver = CouponJobs(front.command, front.recorder, tmp_path / "looking" / "jobs", store=MemoryStore(), table=table,
                        local_root=tmp_path / "looking" / "coupons", role="solver")
    beats: list[str | None] = []
    real = coupon_jobs.update_job

    def spied(engine, job, **fields):
        if "state" not in fields and "heartbeat_at" in fields:
            beats.append(fields.get("stage"))
        return real(engine, job, **fields)

    monkeypatch.setattr(coupon_jobs, "update_job", spied)
    job_id = uuid.UUID(queued("WAIT-G"))
    job = solving(solver, job_id, monkeypatch, until=("running",))
    held_until(job, lambda: "fields" in (fetch_job(table, job_id).stored or {}), "its fields on the row within the looks, not after a 30 s beat")
    time.sleep(0.5)  # ten looks with nothing new: no further write
    count = len(beats)
    time.sleep(0.5)
    assert len(beats) == count and beats[-1] == "CalculiX" and count <= 8, beats
    (tmp_path / "looking" / "release-WAIT-G").touch()
    held_until(job, lambda: job.state == "done", "done")


def report_asked(job_id) -> dict:
    """Ask for the job's report and wait until it is written or the try has failed; the job as it then stands."""
    asked = client.post(f"/v1/coupon-jobs/{job_id}/document")
    assert asked.status_code == 202 and asked.json()["report"] == "writing", asked.text
    deadline = time.monotonic() + 30
    while (status := client.get(f"/v1/coupon-jobs/{job_id}").json())["report"] == "writing":
        assert time.monotonic() < deadline, "the report is still being written after 30 s"
        time.sleep(0.02)
    return status


def test_a_report_is_written_on_request_from_the_jobs_own_source_and_filed_with_its_files(queue, monkeypatch):
    """ADR-0064 amendment 3: a run without its PDF ends done and keeps the report's LaTeX and figures; the API's container typesets
    them when someone asks, files the PDF beside the job's other files and lists it on the row. The report is the job's own: a later
    run of the same coupon does not change it."""
    _, solver, _, store, table, tmp_path = queue
    stand_in_typesetter(tmp_path, monkeypatch)
    first, second = uuid.UUID(queued("REPORT-A")), uuid.UUID(queued("REPORT-A"))
    solving(solver, first, monkeypatch)
    solving(solver, second, monkeypatch)
    before = client.get(f"/v1/coupon-jobs/{first}").json()
    assert before["state"] == "done" and before["documents"] == "written" and before["report"] is None
    assert "document_source" in before["outputs"] and "document" not in before["outputs"]
    assert client.get(f"/v1/coupon-jobs/{first}/files/document").status_code == 404

    after = report_asked(first)
    assert after["report"] is None and after["outputs"]["document"].endswith("package/REPORT-A.pdf") and after["documents"] == "written"
    row = fetch_job(table, first)
    assert row.stored["document"] == "coupons/REPORT-A/attempt-02_2026-11-07/files/document/REPORT-A.pdf" and row.state == "done"
    assert store.objects[row.stored["document"]][0] == b"%PDF typeset from: the report of REPORT-A, attempt 02"  # its own attempt's, not the later one's
    assert store.objects[row.stored["document"]][1] == "application/pdf"
    link = client.get(f"/v1/coupon-jobs/{first}/files/document", params={"name": "D3039_report.pdf"}, follow_redirects=False)
    assert link.status_code == 307 and link.headers["location"] == f"https://store.test/{row.stored['document']}?expires=600&filename=D3039_report.pdf"
    again = client.post(f"/v1/coupon-jobs/{first}/document")
    assert again.status_code == 200 and again.json()["report"] is None and "document" in again.json()["outputs"]
    assert "document" not in client.get(f"/v1/coupon-jobs/{second}").json()["outputs"]  # nobody asked for the later run's


def test_a_report_under_way_is_not_started_twice_and_a_failed_one_can_be_asked_again(queue, monkeypatch):
    _, solver, _, store, table, tmp_path = queue
    stand_in_typesetter(tmp_path, monkeypatch)
    held = uuid.UUID(queued("REPORT-HOLD"))
    solving(solver, held, monkeypatch)
    starts: list[uuid.UUID] = []
    real = CouponJobs._typeset
    monkeypatch.setattr(CouponJobs, "_typeset", lambda self, job: (starts.append(job.id), real(self, job))[1])
    assert [client.post(f"/v1/coupon-jobs/{held}/document").status_code for _ in range(3)] == [202, 202, 202]
    assert client.get(f"/v1/coupon-jobs/{held}").json()["report"] == "writing"
    assert [job["report"] for job in client.get("/v1/coupon-jobs").json() if job["job_id"] == str(held)] == ["writing"]
    (tmp_path / "release-typesetter").touch()
    deadline = time.monotonic() + 30
    while "document" not in client.get(f"/v1/coupon-jobs/{held}").json()["outputs"]:
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert starts == [held]

    refused = uuid.UUID(queued("REPORT-REFUSE"))
    solving(solver, refused, monkeypatch)
    failed = report_asked(refused)
    assert failed["report"] == "failed" and "document" not in failed["outputs"] and "document" not in fetch_job(table, refused).stored
    assert failed["state"] == "done" and failed["documents"] == "written"  # the run and its files stand; the report is asked for again
    assert report_asked(refused)["report"] == "failed" and starts == [held, refused, refused]


def test_a_report_is_refused_in_the_pages_words_when_it_cannot_be_written(queue, monkeypatch):
    _, solver, _, _, _, tmp_path = queue
    stand_in_typesetter(tmp_path, monkeypatch)
    plain = uuid.UUID(queued("NO-SOURCE-B"))  # a run that kept no source for its report (a run of before this, or one whose package failed)
    waiting = client.post(f"/v1/coupon-jobs/{plain}/document")
    assert waiting.status_code == 409 and waiting.json()["detail"] == "The report is written once the analysis has finished."
    solving(solver, plain, monkeypatch)
    none = client.post(f"/v1/coupon-jobs/{plain}/document")
    assert none.status_code == 409 and none.json()["detail"] == "This analysis kept no report to write. Run the analysis again to get one."
    assert client.post(f"/v1/coupon-jobs/{uuid.uuid4()}/document").status_code == 404
    kept = uuid.UUID(queued("REPORT-B"))
    solving(solver, kept, monkeypatch)
    monkeypatch.setattr(coupon_jobs, "typesetter", lambda: None)
    missing = client.post(f"/v1/coupon-jobs/{kept}/document")
    assert missing.status_code == 503 and "Tectonic" not in missing.json()["detail"] and "Try again" in missing.json()["detail"]
    assert client.get(f"/v1/coupon-jobs/{kept}").json()["report"] is None


def test_the_page_opening_is_answered_with_the_word_that_wakes_a_solver(queue, monkeypatch):
    """ADR-0056 amendment 11: with the queue, the API's container marks the answer for the Worker, which starts the pool's first free
    solver; a process that runs its own jobs, or a solver, has nothing to wake and says so."""
    front, solver, _, _, _, tmp_path = queue
    woken = client.post("/v1/wake")
    assert woken.status_code == 202 and woken.json() == {"waking": True} and woken.headers["X-Anisotropy-Wake"] == "1"
    assert front.jobs == {} and client.get("/v1/coupon-jobs").json() == []  # nothing is filed or run by it
    for other in (solver, CouponJobs(front.command, front.recorder, tmp_path / "alone" / "jobs")):
        monkeypatch.setattr(app.state, "coupon_jobs", other)
        alone = client.post("/v1/wake")
        assert alone.status_code == 202 and alone.json() == {"waking": False} and "X-Anisotropy-Wake" not in alone.headers


def test_a_solver_says_whether_it_runs_a_job(queue, monkeypatch):
    """ADR-0056 amendment 11: what the Worker asks the pool's solvers when the page opens; the API's own container has no such route."""
    _, solver, _, _, _, tmp_path = queue
    assert client.get("/v1/solver/state").status_code == 404
    job_id = uuid.UUID(queued("WAIT-H"))
    monkeypatch.setattr(app.state, "coupon_jobs", solver)
    assert client.get("/v1/solver/state").json() == {"busy": False}
    job = solving(solver, job_id, monkeypatch, until=("running",))
    assert client.get("/v1/solver/state").json() == {"busy": True}
    (tmp_path / "solver-1" / "release-WAIT-H").touch()
    held_until(job, lambda: job.state == "done", "done")
    assert client.get("/v1/solver/state").json() == {"busy": False}


@pytest.mark.parametrize(("coupon", "written"), [("PDF-A", True), ("NO-DOC-A", False)])
def test_report_ready_on_a_row_read_back_needs_the_pdf(queue, monkeypatch, coupon, written):
    """ADR-0064 amendment 2: a job read back from its row has its documents "written" only when the package came with the PDF it asked
    for; a package without it says so, and the page shows the report as not written instead of ticking Report ready."""
    _, solver, _, _, table, _ = queue
    job_id = uuid.UUID(queued(coupon, pdf=True))
    solving(solver, job_id, monkeypatch)
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "done" and "package" in status["outputs"] and ("document" in status["outputs"]) is written
    assert (status["documents"] == "written") is written
    if not written:
        assert status["documents"] == "the package was written without its document"


@pytest.mark.parametrize(("coupon", "written"), [("SOURCE-A", True), ("NO-SOURCE-A", False)])
def test_report_ready_without_a_pdf_needs_the_source_of_the_report(queue, monkeypatch, coupon, written):
    """ADR-0064 amendment 3: a job that asked for no PDF has its documents "written" once the source its report is typeset from is
    filed, since the report can then be had on request; without that source the row says so and Report ready is not ticked."""
    _, solver, _, _, table, _ = queue
    job_id = uuid.UUID(queued(coupon))
    solving(solver, job_id, monkeypatch)
    status = client.get(f"/v1/coupon-jobs/{job_id}").json()
    assert status["state"] == "done" and "document" not in status["outputs"] and ("document_source" in status["outputs"]) is written
    assert status["documents"] == ("written" if written else "the package was written without the source of its report")


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
    outside = coupon_jobs.peak_memory((v2, v1))  # neither file: not a container; on Linux the children's peak resident set stands in
    assert outside is None or (sys.platform.startswith("linux") and isinstance(outside, int))
    v1.write_text("432361472\n", encoding="ascii")
    assert coupon_jobs.peak_memory((v2, v1)) == 432361472  # a Docker host still on cgroup v1
    v2.write_text("299454464\n", encoding="ascii")
    assert coupon_jobs.peak_memory((v2, v1)) == 299454464  # cgroup v2 first
