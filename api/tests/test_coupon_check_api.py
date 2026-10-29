"""The studio's questions through the API (ADR-0051): the setup check of a values object, the list of coupons and a coupon's values,
each answered by fea/tools/studio_tool.py run as a program. A stand-in for the tool plays each answer here, so these tests need
neither the fea environment nor a coupon on the machine; fea/tests/test_studio_tool.py runs the tool itself."""

import hashlib
import json
import sys

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import coupon_jobs
from anisotropy_api.coupon_jobs import CouponJobs, studio_command
from anisotropy_api.main import app, job_recorder
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

STUDIO_STAND_IN = r'''
"""A stand-in for fea/tools/studio_tool.py: the values choose what it does."""
import argparse, json, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("--root")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("check"); p.add_argument("values"); p.add_argument("--out", required=True)
commands.add_parser("coupons")
p = commands.add_parser("values"); p.add_argument("coupon")
args = parser.parse_args()
if args.command == "coupons":
    print(json.dumps([{"name": "IM7-UNT-L1", "designation": "IM7-UNT-L1", "kind": "unnotched_tension", "test": "unnotched tension",
                       "title": "IM7-UNT-L1, unnotched tension: a stand-in", "layup": "[45/0/-45/90]s", "status": "in progress", "accepted": "01",
                       "attempts": 1, "category": "team test"}]))
    sys.exit(0)
if args.command == "values":
    if args.coupon == "NONE-UNT-L9":
        sys.exit("studio_tool: NONE-UNT-L9: no coupon of that name under .local/fea")
    print(json.dumps({"form_version": "0.3", "test": "unnotched tension", "length": 250.0, "angles": [45, 0, -45, 90]}))
    sys.exit(0)
values = json.loads(pathlib.Path(args.values).read_text(encoding="utf-8"))
if values.get("notes") == "SLOW":
    time.sleep(5)
if values.get("notes") == "FAILS":
    sys.exit("studio_tool: something broke")
out = pathlib.Path(args.out)
out.mkdir(parents=True)
blocked = "length" not in values
items = [{"id": "geometry", "label": "Geometry defined", "state": "missing" if blocked else "pass", "message": "Length (mm): required" if blocked else "250 by 25 mm",
          "rows": ["Length (mm)"] if blocked else []}]
(out / "checklist.json").write_text(json.dumps({"items": items, "designation": "IM7-UNT-L1", "coupon_exists": False, "attempts": 0,
                                                "state": "blocked" if blocked else "ready", "problems": ["values.json: Length (mm): required"] if blocked else []}))
if not blocked:
    (out / "preview.json").write_text(json.dumps({"units": "mm-MPa", "mesh": {"element_count": 1200}, "loaded": {"value": values.get("value", 1.0)}}))
print("ready" if not blocked else "blocked")
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here
VALUES = {"form_version": "0.3", "filled_by": "A. Engineer", "test": "unnotched tension", "length": 250.0, "value": 1.0, "angles": [45, 0, -45, 90]}


@pytest.fixture
def studio(tmp_path, monkeypatch):
    """The API's coupon jobs with the studio stand-in."""
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STUDIO_STAND_IN, encoding="utf-8")
    registry = CouponJobs(None, job_recorder(app), tmp_path / "jobs", studio=[sys.executable, str(stand_in)])
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    return registry


def test_the_check_answers_with_the_checklist_and_the_preview(studio):
    answer = client.post("/v1/coupon-jobs/check", json={"values": VALUES})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["state"] == "ready" and body["designation"] == "IM7-UNT-L1" and body["run_id"] is None
    assert body["checklist"]["items"][0]["state"] == "pass" and body["preview"] == {"units": "mm-MPa", "mesh": {"element_count": 1200}, "loaded": {"value": 1.0}}
    assert sorted(p.name for p in (studio.root).iterdir()) == []  # the check's folder is cleaned up


def test_a_blocked_check_has_no_preview(studio):
    body = client.post("/v1/coupon-jobs/check", json={"values": {k: v for k, v in VALUES.items() if k != "length"}}).json()
    assert body["state"] == "blocked" and body["preview"] is None and body["checklist"]["items"][0]["rows"] == ["Length (mm)"]


@pytest.mark.parametrize("body, reason", [({"values": {}}, "the object is empty"), ({"values": [1]}, "dictionary"), ({}, "Field required"),
                                          ({"values": VALUES, "extra": 1}, "Extra inputs")])
def test_a_check_outside_the_contract_is_refused(studio, body, reason):
    refused = client.post("/v1/coupon-jobs/check", json=body)
    assert refused.status_code == 422 and reason in str(refused.json()["detail"])


def test_a_slow_tool_is_a_504_and_a_broken_one_a_503(studio, monkeypatch):
    monkeypatch.setattr(coupon_jobs, "CHECK_TIMEOUT_S", 0.5)
    slow = client.post("/v1/coupon-jobs/check", json={"values": {**VALUES, "notes": "SLOW"}})
    assert slow.status_code == 504 and "did not answer in 0.5 s" in slow.json()["detail"]
    broken = client.post("/v1/coupon-jobs/check", json={"values": {**VALUES, "notes": "FAILS"}})
    assert broken.status_code == 503 and "something broke" in broken.json()["detail"]


def test_without_uv_the_studio_has_no_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(coupon_jobs.shutil, "which", lambda name: None)
    assert studio_command() is None
    monkeypatch.setattr(app.state, "coupon_jobs", CouponJobs(None, job_recorder(app), tmp_path, studio=None), raising=False)
    assert client.post("/v1/coupon-jobs/check", json={"values": VALUES}).status_code == 503
    assert client.get("/v1/coupons").status_code == 503


def test_the_studio_command_is_the_fea_tool(monkeypatch):
    monkeypatch.setattr(coupon_jobs.shutil, "which", lambda name: f"/bin/{name}")
    assert studio_command() == ["/bin/uv", "run", "--project", str(coupon_jobs.FEA), "python", str(coupon_jobs.STUDIO)] and coupon_jobs.STUDIO.is_file()


def test_the_coupons_and_a_coupons_values_are_listed(studio):
    listed = client.get("/v1/coupons")
    assert listed.status_code == 200 and listed.json()[0]["name"] == "IM7-UNT-L1" and listed.json()[0]["status"] == "in progress"
    values = client.get("/v1/coupons/IM7-UNT-L1/values")
    assert values.status_code == 200 and values.json() == {"name": "IM7-UNT-L1", "values": {"form_version": "0.3", "test": "unnotched tension",
                                                                                            "length": 250.0, "angles": [45, 0, -45, 90]}}
    missing = client.get("/v1/coupons/NONE-UNT-L9/values")
    assert missing.status_code == 404 and "no coupon of that name" in missing.json()["detail"]


def test_the_actor_is_required_for_a_check(studio):
    assert TestClient(app).post("/v1/coupon-jobs/check", json={"values": VALUES}).status_code == 422


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
def test_a_check_is_recorded_by_its_digest(recording):
    answer = recording.post("/v1/coupon-jobs/check", json={"values": VALUES})
    assert answer.status_code == 200 and answer.json()["run_id"]
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    digest = hashlib.sha256(json.dumps(VALUES, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")).hexdigest()
    assert run["actor"] == "studio" and run["endpoint"] == "/v1/coupon-jobs/check" and run["status"] == "solved"
    assert run["inputs"] == {"values": {"sha256": digest, "form_version": "0.3", "rows": len(VALUES)}}  # never the rows themselves
    assert run["response"]["state"] == "ready" and run["response"]["preview"]["mesh"]["element_count"] == 1200
