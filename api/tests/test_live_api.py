"""The live solve through the API (ADR-0086): POST /v1/coupon-jobs/live answers the rows as they stand with the setup check and, when
nothing blocks, the kernel's fields and explanation as the studio tool wrote them. A stand-in for fea/tools/studio_tool.py plays both of
its modes here (`live` once, `serve` warm), so these tests need neither the fea environment nor the engine; fea/tests/test_studio_tool.py
runs the tool itself."""

import hashlib
import json
import sys
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.live import LiveSolver
from anisotropy_api.main import app
from anisotropy_api.settings import DATABASE_VARIABLE, LIVE_WORKERS_VARIABLE, RECORDING_VARIABLE, live_workers

from conftest import TEST_URL, needs_test_database

STAND_IN = r'''
"""A stand-in for fea/tools/studio_tool.py live and serve: the values' notes choose what it does."""
import argparse, json, os, pathlib, sys, time

def solve(values_path, out):
    values = json.loads(pathlib.Path(values_path).read_text(encoding="utf-8"))
    notes = values.get("notes", "")
    if notes == "SLOW":
        time.sleep(5)
    if notes == "DIES":
        os._exit(3)
    if notes == "ERROR":
        raise ValueError("these rows break the kernel")
    out = pathlib.Path(out)
    out.mkdir(parents=True)
    blocked = "length" not in values
    checklist = {"items": [{"id": "geometry", "label": "Geometry", "state": "missing" if blocked else "pass", "message": "Length: required" if blocked else "",
                            "rows": ["Length (mm)"] if blocked else []}], "designation": None if blocked else "IM78552-UNT-L1",
                 "coupon_exists": False, "attempts": 0, "state": "blocked" if blocked else "ready", "problems": []}
    (out / "checklist.json").write_text(json.dumps(checklist), encoding="utf-8")
    if blocked:
        (out / "timings.json").write_text(json.dumps({"check": 0.1}), encoding="utf-8")
        return "blocked"
    summary = {"verdict": {"basis": "gauge", "earliest": "tsai_hill", "factor": 1.032, "fails": False, "outside_earlier": None}, "pid": os.getpid()}
    fields = {"summary": summary, "element": {"big": list(range(5000))}}
    (out / "preview.json").write_text(json.dumps({"mesh": {"nodes": [[0, 0]]}}), encoding="utf-8")
    (out / "fields.json").write_text(json.dumps(fields, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")  # as the tool writes it
    (out / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (out / "explanation.json").write_text(json.dumps({"writer": "template", "sentences": ["holds"]}), encoding="utf-8")
    (out / "timings.json").write_text(json.dumps({"check": 0.1, "solve": 0.01, "total": 0.2}), encoding="utf-8")
    return "ready"

parser = argparse.ArgumentParser()
parser.add_argument("--root")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("live"); p.add_argument("values"); p.add_argument("--out", required=True)
commands.add_parser("serve")
args = parser.parse_args()
if args.command == "live":
    try:
        solve(args.values, args.out)
    except ValueError as exc:
        sys.exit(f"studio_tool: {exc}")
else:
    print(json.dumps({"ready": True, "imports": 0.0, "pid": os.getpid()}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            answer = {"state": solve(request["values"], request["out"])}
        except Exception as exc:
            answer = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(answer), flush=True)
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here
VALUES = {"form_version": "0.9", "test": "unnotched tension", "filled_by": "A. Tester", "length": 250, "width": 25}


def solver(tmp_path, workers: int, **kwargs) -> LiveSolver:
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    return LiveSolver([sys.executable, str(stand_in)], tmp_path / "live", workers, **kwargs)


@pytest.fixture
def warm(tmp_path, monkeypatch):
    live = solver(tmp_path, 1, timeout_s=2.0, wait_s=10.0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    yield live
    live.close()


def test_a_ready_setup_answers_with_the_kernels_fields_as_the_tool_wrote_them(warm):
    answer = client.post("/v1/coupon-jobs/live", json={"values": VALUES})
    assert answer.status_code == 200
    body = answer.json()
    assert body["state"] == "ready" and body["designation"] == "IM78552-UNT-L1" and body["solver"] == "kernel" and body["warm"] is True
    assert body["fields"]["summary"]["verdict"]["earliest"] == "tsai_hill" and len(body["fields"]["element"]["big"]) == 5000
    assert body["explanation"]["sentences"] == ["holds"] and body["preview"]["mesh"]["nodes"] == [[0, 0]]
    assert body["timings"]["solve"] == 0.01 and body["seconds"] > 0 and body["run_id"] is None  # nothing is recorded without the lifespan
    assert answer.headers.get("content-encoding") == "gzip", "a live solve's fields are compressed for a browser that asks"


def test_a_blocked_setup_answers_with_its_checklist_and_nothing_solved(warm):
    body = client.post("/v1/coupon-jobs/live", json={"values": {k: v for k, v in VALUES.items() if k != "length"}}).json()
    assert body["state"] == "blocked" and body["fields"] is None and body["explanation"] is None and body["preview"] is None
    assert body["checklist"]["items"][0]["rows"] == ["Length (mm)"]


def test_the_same_warm_worker_answers_one_request_after_another(warm):
    first = client.post("/v1/coupon-jobs/live", json={"values": VALUES}).json()["fields"]["summary"]["pid"]
    second = client.post("/v1/coupon-jobs/live", json={"values": VALUES}).json()["fields"]["summary"]["pid"]
    assert first == second, "the package stays imported in one warm worker"


def test_a_worker_that_errs_stays_and_one_that_stops_is_replaced(warm):
    err = client.post("/v1/coupon-jobs/live", json={"values": {**VALUES, "notes": "ERROR"}})
    assert err.status_code == 503 and "these rows break the kernel" in err.json()["detail"]
    kept = client.post("/v1/coupon-jobs/live", json={"values": VALUES}).json()["fields"]["summary"]["pid"]
    died = client.post("/v1/coupon-jobs/live", json={"values": {**VALUES, "notes": "DIES"}})
    assert died.status_code == 503 and "stopped" in died.json()["detail"]
    after = client.post("/v1/coupon-jobs/live", json={"values": VALUES})
    assert after.status_code == 200 and after.json()["fields"]["summary"]["pid"] != kept, "a new worker took the stopped one's place"


def test_a_slow_worker_is_a_504_and_is_replaced(warm):
    slow = client.post("/v1/coupon-jobs/live", json={"values": {**VALUES, "notes": "SLOW"}})
    assert slow.status_code == 504 and "did not answer in 2 s" in slow.json()["detail"]
    assert client.post("/v1/coupon-jobs/live", json={"values": VALUES}).status_code == 200


def test_every_worker_busy_is_a_429(tmp_path, monkeypatch):
    live = solver(tmp_path, 1, timeout_s=10.0, wait_s=10.0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    try:
        assert client.post("/v1/coupon-jobs/live", json={"values": VALUES}).status_code == 200  # the worker is warm
        live.wait_s = 0.5
        holding = threading.Thread(target=lambda: live.solve(json.dumps({**VALUES, "notes": "SLOW"}).encode()), daemon=True)
        holding.start()
        time.sleep(0.3)
        busy = client.post("/v1/coupon-jobs/live", json={"values": VALUES})
        assert busy.status_code == 429 and "busy" in busy.json()["detail"]
    finally:
        live.close()


def test_without_warm_workers_each_request_starts_the_tool(tmp_path, monkeypatch):
    live = solver(tmp_path, 0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    body = client.post("/v1/coupon-jobs/live", json={"values": VALUES}).json()
    assert body["state"] == "ready" and body["warm"] is False and body["fields"]["summary"]["verdict"]["basis"] == "gauge"
    broken = client.post("/v1/coupon-jobs/live", json={"values": {**VALUES, "notes": "ERROR"}})
    assert broken.status_code == 503 and "these rows break the kernel" in broken.json()["detail"]


def test_no_uv_is_a_503(tmp_path, monkeypatch):
    monkeypatch.setattr(app.state, "live", LiveSolver(None, tmp_path / "live", 1), raising=False)
    refused = client.post("/v1/coupon-jobs/live", json={"values": VALUES})
    assert refused.status_code == 503 and "uv is not on PATH" in refused.json()["detail"]


@pytest.mark.parametrize("raw, refused", [("", None), ("0", None), ("3", None), ("9", "from 0 to 8"), ("two", "whole number")])
def test_the_worker_count_is_a_whole_number_from_0_to_8(raw, refused):
    if refused is None:
        assert live_workers({LIVE_WORKERS_VARIABLE: raw}) == (int(raw) if raw else 1)
    else:
        with pytest.raises(RuntimeError, match=refused):
            live_workers({LIVE_WORKERS_VARIABLE: raw})


@pytest.fixture
def recording(empty_runs, monkeypatch, tmp_path):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(LIVE_WORKERS_VARIABLE, "0")  # the lifespan's own solver starts no worker; the test's replaces it
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        app.state.live = solver(tmp_path, 1, timeout_s=5.0, wait_s=10.0)
        yield recorded
        app.state.live.close()


@needs_test_database
def test_a_live_solve_is_recorded_by_its_summary_and_the_fields_digest(recording):
    answer = recording.post("/v1/coupon-jobs/live", json={"values": VALUES, "project_id": str(uuid.uuid4())})
    assert answer.status_code == 200 and answer.json()["run_id"]
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    assert run["actor"] == "studio" and run["endpoint"] == "/v1/coupon-jobs/live" and run["status"] == "solved"
    digest = hashlib.sha256(json.dumps(VALUES, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")).hexdigest()
    assert run["inputs"]["values"]["sha256"] == digest  # never the rows
    response = run["response"]
    assert response["summary"]["verdict"]["earliest"] == "tsai_hill" and response["solver"] == "kernel" and response["state"] == "ready"
    fields = json.dumps(answer.json()["fields"], separators=(",", ":"))
    assert response["fields_sha256"] == hashlib.sha256((fields + "\n").encode("utf-8")).hexdigest(), "the digest of the file the tool wrote"
    assert "element" not in json.dumps(response), "never the arrays"
