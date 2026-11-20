"""The model as a file for Abaqus or Ansys through the API (ADR-0129): POST /v1/coupon-jobs/model answers the rows with the file the fea
package wrote, the Abaqus file to everyone and the Ansys file where the import is offered. A stand-in for fea/tools/studio_tool.py plays
`model` here, once and warm, so these tests need neither the fea environment nor the engine; fea/tests/test_studio_tool.py runs the tool
itself and fea/tests/test_write_ansys.py the writer."""

import hashlib
import sys

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.live import LiveSolver
from anisotropy_api.main import MODEL_NAME_HEADER, app

STAND_IN = r'''
"""A stand-in for fea/tools/studio_tool.py model and serve: the values choose what it does."""
import argparse, hashlib, json, pathlib, sys

def model(values_path, program, out, every=False):
    values = json.loads(pathlib.Path(values_path).read_text(encoding="utf-8"))
    if program not in ("abaqus", "ansys"):
        raise ValueError(f"a model is written for abaqus or ansys; got {program!r}")
    out = pathlib.Path(out)
    out.mkdir(parents=True)
    blocked = "length" not in values
    checklist = {"items": [{"id": "geometry", "label": "Geometry", "state": "missing" if blocked else "pass", "message": "Length: required" if blocked else "",
                            "rows": ["Length (mm)"] if blocked else []}], "designation": None if blocked else "IM78552-UNT-L1",
                 "coupon_exists": False, "attempts": 0, "state": "blocked" if blocked else "ready", "problems": []}
    (out / "checklist.json").write_text(json.dumps(checklist), encoding="utf-8")
    if blocked:
        return "blocked"
    if values.get("notes") == "TURNS":
        (out / "model.json").write_text(json.dumps({"state": "refused", "program": program, "problem": "the reference point RF-Top of the grip Grip-Top may turn"}), encoding="utf-8")
        return "refused"
    name = "IM78552-UNT-L1" + ("-abaqus.inp" if program == "abaqus" else "-ansys.cdb")
    data = (("*Heading\n" if program == "abaqus" else "! Generated\n/PREP7\n") + ("every\n" if every else "")).encode("utf-8")
    (out / name).write_bytes(data)
    (out / "model.json").write_text(json.dumps({"state": "written", "program": program, "name": name, "units": "mm-MPa", "bytes": len(data),
                                                "sha256": hashlib.sha256(data).hexdigest(), "nodes": 1386, "elements": 1250}), encoding="utf-8")
    return "written"

parser = argparse.ArgumentParser()
parser.add_argument("--root")
parser.add_argument("--every-test", action="store_true")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("model"); p.add_argument("values"); p.add_argument("--program", required=True); p.add_argument("--out", required=True)
commands.add_parser("serve")
args = parser.parse_args()
if args.command == "model":
    model(args.values, args.program, args.out, args.every_test)
else:
    print(json.dumps({"ready": True, "imports": 0.0}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            answer = {"state": model(request["values"], request["model"], request["out"], request.get("every") is True)}
        except Exception as exc:
            answer = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(answer), flush=True)
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here
VALUES = {"form_version": "0.9", "test": "unnotched tension", "filled_by": "A. Tester", "length": 250, "width": 25}
ADDRESS = "/v1/coupon-jobs/model"


@pytest.fixture(params=[0, 1], ids=["a fresh tool", "a warm worker"])
def tool(tmp_path, monkeypatch, request):
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    live = LiveSolver([sys.executable, str(stand_in)], tmp_path / "live", request.param, timeout_s=20.0, wait_s=20.0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    monkeypatch.setattr(app.state, "settings", None, raising=False)
    yield live
    live.close()


def test_the_abaqus_file_is_everyones_and_comes_as_a_named_download(tool, tmp_path):
    answer = client.post(ADDRESS, params={"program": "abaqus"}, json={"values": VALUES})
    assert answer.status_code == 200, answer.text
    assert answer.text == "*Heading\n" and answer.headers["content-type"].startswith("text/plain")
    assert answer.headers["content-disposition"] == 'attachment; filename="IM78552-UNT-L1-abaqus.inp"'
    assert answer.headers[MODEL_NAME_HEADER] == "IM78552-UNT-L1-abaqus.inp"
    assert not any((tmp_path / "live").iterdir()), "nothing of the model is kept once it is answered"


def test_the_ansys_file_is_everyones_and_refused_only_if_it_is_closed_again(tool, monkeypatch):
    answer = client.post(ADDRESS, params={"program": "ansys"}, json={"values": VALUES})  # no sign-in and no switch (ADR-0129 amendment 3)
    assert answer.status_code == 200 and answer.text.startswith("! Generated\n/PREP7\n")
    assert answer.headers["content-disposition"] == 'attachment; filename="IM78552-UNT-L1-ansys.cdb"'
    assert client.get("/v1/coupon-tests").json()["ansys_model"] is True
    monkeypatch.setattr("anisotropy_api.main._ansys_model", lambda request: False)
    refused = client.post(ADDRESS, params={"program": "ansys"}, json={"values": VALUES})
    assert refused.status_code == 403 and refused.json()["detail"] == "The Ansys model is not offered yet."
    assert client.get("/v1/coupon-tests").json()["ansys_model"] is False


def test_a_setup_the_check_stops_is_a_422_with_its_first_reason(tool):
    answer = client.post(ADDRESS, params={"program": "abaqus"}, json={"values": {k: v for k, v in VALUES.items() if k != "length"}})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "The setup is not complete, so there is no model to write yet. Geometry: Length: required"


def test_a_model_the_writer_cannot_state_is_a_422_that_says_why(tool, monkeypatch):
    answer = client.post(ADDRESS, params={"program": "ansys"}, json={"values": {**VALUES, "notes": "TURNS"}})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "This model cannot be written for Ansys yet: the reference point RF-Top of the grip Grip-Top may turn"


def test_a_program_we_do_not_write_for_and_a_request_without_one_are_refused_before_the_tool(tool):
    assert client.post(ADDRESS, params={"program": "nastran"}, json={"values": VALUES}).status_code == 422
    assert client.post(ADDRESS, json={"values": VALUES}).status_code == 422
    assert client.post(ADDRESS, params={"program": "abaqus"}, json={"values": {}}).status_code == 422


def test_a_plate_set_up_by_a_founder_reaches_the_tool_with_the_option(tool, monkeypatch):
    monkeypatch.setattr("anisotropy_api.main._imports", lambda request: True)
    plate = client.post(ADDRESS, params={"program": "ansys"}, json={"values": {**VALUES, "test": "plate"}})
    assert plate.status_code == 200 and plate.text.endswith("every\n")  # as the check and the live solve pass it (ADR-0089 amendment 7)
    coupon = client.post(ADDRESS, params={"program": "ansys"}, json={"values": VALUES})
    assert coupon.status_code == 200 and not coupon.text.endswith("every\n")


def test_the_file_is_the_tools_bytes(tool):
    answer = client.post(ADDRESS, params={"program": "abaqus"}, json={"values": VALUES})
    assert hashlib.sha256(answer.content).hexdigest() == hashlib.sha256(b"*Heading\n").hexdigest()
