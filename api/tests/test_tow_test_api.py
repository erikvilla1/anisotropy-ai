"""The fibre tow record through the API (ADR-0074): POST /v1/tow-tests answers at once with the checklist and the result that
fea/tools/studio_tool.py tow writes. A stand-in for the tool plays the answers here, so these tests need neither the fea environment nor
the engine; fea/tests/test_tow_test.py runs the tool itself."""

import hashlib
import json
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import coupon_jobs
from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import app, job_recorder
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

STUDIO_STAND_IN = r'''
"""A stand-in for fea/tools/studio_tool.py tow: the values choose what it does."""
import argparse, json, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("--root")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("tow"); p.add_argument("values"); p.add_argument("--out", required=True)
args = parser.parse_args()
values = json.loads(pathlib.Path(args.values).read_text(encoding="utf-8"))
if values.get("notes") == "SLOW":
    time.sleep(5)
if values.get("notes") == "FAILS":
    sys.exit("studio_tool: something broke")
out = pathlib.Path(args.out)
out.mkdir(parents=True)
blocked = "fibre" not in values
items = [{"id": "identity", "label": "Who and which fibre", "state": "missing" if blocked else "pass", "message": "Fibre: required" if blocked else "",
          "rows": ["Fibre"] if blocked else [], "requirements": []}]
result = None if blocked else {"test": "fibre tow tension", "designation": "ASTM D4018-23", "strength": {"n": 4, "mean": 4857.0, "sd": 131.3, "cv": 2.7}}
(out / "tow.json").write_text(json.dumps({"checklist": {"items": items, "designation": None, "coupon_exists": False, "attempts": 0,
                                                       "state": "blocked" if blocked else "ready", "problems": ["Fibre: required"] if blocked else []},
                                         "result": result}))
print("blocked" if blocked else "ready")
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here
VALUES = {"form_version": "0.8", "test": "fibre tow tension", "filled_by": "A. Tester", "fibre": "constructed 12K carbon tow",
          "specimens": [{"id": "1", "max_force": 2150, "status": "valid"}]}


@pytest.fixture
def studio(tmp_path, monkeypatch):
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STUDIO_STAND_IN, encoding="utf-8")
    registry = CouponJobs(None, job_recorder(app), tmp_path / "jobs", studio=[sys.executable, str(stand_in)])
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    return registry


def test_a_tow_record_answers_with_its_checklist_and_result(studio):
    answer = client.post("/v1/tow-tests", json={"values": VALUES})
    assert answer.status_code == 200
    body = answer.json()
    assert body["state"] == "ready" and body["result"]["strength"]["mean"] == 4857.0 and body["checklist"]["items"][0]["id"] == "identity"
    assert body["run_id"] is None  # nothing is recorded without the lifespan


def test_a_blocked_record_has_no_result(studio):
    body = client.post("/v1/tow-tests", json={"values": {k: v for k, v in VALUES.items() if k != "fibre"}}).json()
    assert body["state"] == "blocked" and body["result"] is None and body["checklist"]["items"][0]["rows"] == ["Fibre"]


@pytest.mark.parametrize("body, reason", [({"values": {}}, "the object is empty"), ({"values": VALUES, "extra": 1}, "Extra inputs"),
                                          ({"values": VALUES, "project_id": "not-a-uuid"}, "pattern")])
def test_a_record_outside_the_contract_is_refused(studio, body, reason):
    refused = client.post("/v1/tow-tests", json=body)
    assert refused.status_code == 422 and reason in str(refused.json()["detail"])


def test_a_slow_tool_is_a_504_and_a_broken_one_a_503(studio, monkeypatch):
    monkeypatch.setattr(coupon_jobs, "CHECK_TIMEOUT_S", 0.5)
    slow = client.post("/v1/tow-tests", json={"values": {**VALUES, "notes": "SLOW"}})
    assert slow.status_code == 504 and "did not answer in 0.5 s" in slow.json()["detail"]
    broken = client.post("/v1/tow-tests", json={"values": {**VALUES, "notes": "FAILS"}})
    assert broken.status_code == 503 and "something broke" in broken.json()["detail"]


def test_the_actor_is_required(studio):
    assert TestClient(app).post("/v1/tow-tests", json={"values": VALUES}).status_code == 422


@pytest.fixture
def recording(empty_runs, monkeypatch, tmp_path):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STUDIO_STAND_IN, encoding="utf-8")
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        app.state.coupon_jobs = CouponJobs(None, job_recorder(app), tmp_path / "jobs", studio=[sys.executable, str(stand_in)])
        yield recorded


@needs_test_database
def test_a_tow_record_is_recorded_by_its_digest(recording):
    project = str(uuid.uuid4())
    answer = recording.post("/v1/tow-tests", json={"values": VALUES, "project_id": project})
    assert answer.status_code == 200 and answer.json()["run_id"]
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    digest = hashlib.sha256(json.dumps(VALUES, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")).hexdigest()
    assert run["actor"] == "studio" and run["endpoint"] == "/v1/tow-tests" and run["status"] == "solved"
    assert run["inputs"] == {"values": {"sha256": digest, "form_version": "0.8", "rows": len(VALUES)}, "project_id": project}  # never the rows
    assert run["response"]["result"]["designation"] == "ASTM D4018-23"
