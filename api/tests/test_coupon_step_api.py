"""The model's shape as a STEP file through the API (ADR-0146): POST /v1/coupon-jobs/model?program=step answers the rows with the file
the fea package drew, under the rules of the other two downloads (ADR-0129). A stand-in for fea/tools/studio_tool.py plays `model` here,
once and warm, so these tests need neither the fea environment nor Gmsh; fea/tests/test_coupon_shape.py draws the shapes themselves and
runs the tool."""

import json
import sys

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.live import LiveSolver
from anisotropy_api.main import app

STAND_IN = r'''
"""A stand-in for fea/tools/studio_tool.py model and serve, for a STEP file: the values choose what it does."""
import argparse, hashlib, json, pathlib, sys

NAMES = {"unnotched tension": "IM78552-UNT-L1", "open-hole tension": "IM78552-OHT-L1", "compression": "IM78552-UNC-L1",
         "in-plane shear": "IM78552-IPS-L1", "three-point bending": "IM78552-3PB-L1", "four-point bending": "IM78552-4PB-L1",
         "plate": "IM78552-PLT-L1"}

def model(values_path, program, out, every=False, root=None):
    values = json.loads(pathlib.Path(values_path).read_text(encoding="utf-8"))
    if program != "step":
        raise ValueError(f"this stand-in draws a STEP file; got {program!r}")
    out = pathlib.Path(out)
    out.mkdir(parents=True)
    blocked = "length" not in values or (values["test"] != "unnotched tension" and not every)
    message = "Length: required" if "length" not in values else "This test is not offered"
    checklist = {"items": [{"id": "geometry", "label": "Geometry", "state": "missing" if blocked else "pass", "message": message if blocked else "",
                            "rows": ["Length (mm)"] if blocked else []}], "designation": None if blocked else NAMES[values["test"]],
                 "coupon_exists": False, "attempts": 0, "state": "blocked" if blocked else "ready", "problems": []}
    (out / "checklist.json").write_text(json.dumps(checklist), encoding="utf-8")
    if blocked:
        return "blocked"
    if values.get("notes") == "NO GMSH":
        (out / "model.json").write_text(json.dumps({"state": "unavailable", "program": program,
                                                    "problem": "Gmsh is not available; from fea/ run `uv sync --extra mesh`"}), encoding="utf-8")
        return "unavailable"
    if values.get("notes") == "FILLET":
        (out / "model.json").write_text(json.dumps({"state": "refused", "program": program,
                                                    "problem": "the tabs reach the dog-bone's fillet, which is not drawn"}), encoding="utf-8")
        return "refused"
    name = NAMES[values["test"]] + ".step"
    data = ("ISO-10303-21;\n" + ("every\n" if every else "") + (f"root {pathlib.Path(root).name}\n" if root else "")).encode("utf-8")
    (out / name).write_bytes(data)
    parts = {"title": NAMES[values["test"]], "units": {"length": "mm", "volume": "mm³", "step": "mm"},
             "parts": [{"name": "Laminate", "kind": "laminate", "layup": "[45/0/-45/90]s", "plies": 8, "ply_thickness": 0.18288,
                        "thickness": 1.46304, "material": "IM7-8552", "volume": values["length"] * values["width"] * 1.46304, "in_model": True}]}
    (out / "model.json").write_text(json.dumps({"state": "written", "program": program, "name": name, "units": "mm", "bytes": len(data),
                                                "sha256": hashlib.sha256(data).hexdigest(), "solids": 1, "parts": parts}), encoding="utf-8")
    return "written"

parser = argparse.ArgumentParser()
parser.add_argument("--root")
parser.add_argument("--every-test", action="store_true")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("model"); p.add_argument("values"); p.add_argument("--program", required=True); p.add_argument("--out", required=True)
commands.add_parser("serve")
args = parser.parse_args()
if args.command == "model":
    model(args.values, args.program, args.out, args.every_test, args.root)
else:
    print(json.dumps({"ready": True, "imports": 0.0}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            answer = {"state": model(request["values"], request["model"], request["out"], request.get("every") is True, request.get("root"))}
        except Exception as exc:
            answer = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(answer), flush=True)
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here
VALUES = {"form_version": "0.9", "test": "unnotched tension", "filled_by": "A. Tester", "length": 250, "width": 25}
ADDRESS = "/v1/coupon-jobs/model"
STEP = {"program": "step"}
EVERY_KIND = {"unnotched tension": "IM78552-UNT-L1", "open-hole tension": "IM78552-OHT-L1", "compression": "IM78552-UNC-L1",
              "in-plane shear": "IM78552-IPS-L1", "three-point bending": "IM78552-3PB-L1", "four-point bending": "IM78552-4PB-L1",
              "plate": "IM78552-PLT-L1"}


@pytest.fixture(params=[0, 1], ids=["a fresh tool", "a warm worker"])
def tool(tmp_path, monkeypatch, request):
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    live = LiveSolver([sys.executable, str(stand_in)], tmp_path / "live", request.param, timeout_s=20.0, wait_s=20.0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    monkeypatch.setattr(app.state, "settings", None, raising=False)
    yield live
    live.close()


def test_the_step_file_is_everyones_and_comes_named_after_the_coupon(tool, tmp_path):
    answer = client.post(ADDRESS, params=STEP, json={"values": VALUES})  # no sign-in: the rule of the other two files (ADR-0129)
    assert answer.status_code == 200, answer.text
    assert answer.content == b"ISO-10303-21;\n" and answer.headers["content-type"] == "model/step"
    assert answer.headers["content-disposition"] == 'attachment; filename="IM78552-UNT-L1.step"'
    assert answer.headers["X-Anisotropy-Model-File"] == "IM78552-UNT-L1.step"
    assert not any((tmp_path / "live").iterdir()), "nothing of the shape is kept once it is answered"


def test_the_part_table_comes_with_the_file_because_a_step_file_holds_no_plies(tool):
    answer = client.post(ADDRESS, params=STEP, json={"values": VALUES})
    raw = answer.headers["X-Anisotropy-Model-Parts"]
    assert raw.isascii() and "\\u00b3" in raw, "a header is ASCII: the cubed sign travels escaped"
    table = json.loads(raw)
    assert table["title"] == "IM78552-UNT-L1" and table["units"] == {"length": "mm", "volume": "mm³", "step": "mm"}
    assert table["parts"] == [{"name": "Laminate", "kind": "laminate", "layup": "[45/0/-45/90]s", "plies": 8, "ply_thickness": 0.18288,
                               "thickness": 1.46304, "material": "IM7-8552", "volume": 250 * 25 * 1.46304, "in_model": True}]


def test_a_page_on_another_origin_may_read_the_name_and_the_part_table(tool):
    answer = client.post(ADDRESS, params=STEP, json={"values": VALUES}, headers={"Origin": "http://localhost:3000"})
    exposed = {name.strip() for name in answer.headers["access-control-expose-headers"].split(",")}
    assert {"X-Anisotropy-Model-File", "X-Anisotropy-Model-Parts"} <= exposed


def test_the_header_and_the_media_type_are_the_ones_the_page_reads():
    """By their own words, as the name header is checked in test_coupon_model_api.py: lib/studio-api.ts reads these two."""
    from anisotropy_api.main import MODEL_PARTS_HEADER, STEP_MEDIA_TYPE
    assert MODEL_PARTS_HEADER == "X-Anisotropy-Model-Parts" and STEP_MEDIA_TYPE == "model/step"


@pytest.mark.parametrize("test", sorted(EVERY_KIND))
def test_every_kind_a_founder_sets_up_leaves_as_a_step_file(tool, monkeypatch, test):
    monkeypatch.setattr("anisotropy_api.main._every_test", lambda request: True)
    answer = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "test": test}})
    assert answer.status_code == 200, answer.text
    assert answer.headers["X-Anisotropy-Model-File"] == EVERY_KIND[test] + ".step"
    assert answer.content == b"ISO-10303-21;\nevery\n"
    assert json.loads(answer.headers["X-Anisotropy-Model-Parts"])["title"] == EVERY_KIND[test]


@pytest.mark.parametrize("test", sorted(set(EVERY_KIND) - {"unnotched tension", "plate"}))
def test_a_test_that_is_not_offered_to_this_person_gives_no_step_file(tool, test):
    """The access rule is the other downloads' rule (ADR-0089): the setup check judges the rows with the tests this person is offered
    (the tension coupon and, since amendment 8, the plate), and what it stops is a 422 with its reason, for a STEP file as for an
    Abaqus one."""
    answer = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "test": test}})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "The setup is not complete, so there is no model to write yet. Geometry: This test is not offered"
    assert "X-Anisotropy-Model-File" not in answer.headers and "X-Anisotropy-Model-Parts" not in answer.headers


def test_a_plate_reaches_the_tool_with_the_option_and_is_refused_if_plates_are_closed_again(tool, monkeypatch):
    plate = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "test": "plate"}})  # everyone's (ADR-0089 amendment 8)
    assert plate.status_code == 200 and plate.content.endswith(b"every\n")  # as the check and the live solve pass it
    assert plate.headers["X-Anisotropy-Model-File"] == "IM78552-PLT-L1.step"
    coupon = client.post(ADDRESS, params=STEP, json={"values": VALUES})
    assert coupon.status_code == 200 and not coupon.content.endswith(b"every\n")
    monkeypatch.setattr("anisotropy_api.main._plates", lambda request: False)
    closed = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "test": "plate"}})
    assert closed.status_code == 422 and "X-Anisotropy-Model-File" not in closed.headers


def test_a_signed_in_person_is_answered_from_their_own_folder_and_no_other(tool, tmp_path, monkeypatch):
    """The route holds no stored model to ask for by name: it draws the rows this request sends. What differs by person is the folder
    the setup check reads the designation's attempts in (ADR-0106), and that is the requester's own, as for the other downloads."""
    class Jobs:
        def root_of(self, email):
            return tmp_path / "owners" / email.split("@")[0]

    monkeypatch.setattr(app.state, "coupon_jobs", Jobs(), raising=False)
    asked = []
    monkeypatch.setattr("anisotropy_api.main._email", lambda request: asked[-1])
    for person in ("first@example.com", "second@example.com"):
        asked.append(person)
        answer = client.post(ADDRESS, params=STEP, json={"values": VALUES})
        assert answer.status_code == 200 and answer.content == f"ISO-10303-21;\nroot {person.split('@')[0]}\n".encode()
    monkeypatch.setattr("anisotropy_api.main._email", lambda request: None)
    assert client.post(ADDRESS, params=STEP, json={"values": VALUES}).content == b"ISO-10303-21;\n"  # no sign-in: the shared folder


def test_a_setup_the_check_stops_is_a_422_with_its_first_reason(tool):
    answer = client.post(ADDRESS, params=STEP, json={"values": {k: v for k, v in VALUES.items() if k != "length"}})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "The setup is not complete, so there is no model to write yet. Geometry: Length: required"


def test_a_shape_that_cannot_be_drawn_is_a_422_that_says_why(tool):
    answer = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "notes": "FILLET"}})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "This model cannot be drawn as a STEP file yet: the tabs reach the dog-bone's fillet, which is not drawn."
    assert "X-Anisotropy-Model-Parts" not in answer.headers


def test_where_gmsh_is_not_installed_the_answer_says_so_and_sends_no_file(tool, capfd):
    answer = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "notes": "NO GMSH"}})
    assert answer.status_code == 503
    assert answer.json() == {"detail": "The shape builder is not installed here"}  # the words of the wing's and the repair's shape routes
    assert "content-disposition" not in answer.headers and "X-Anisotropy-Model-File" not in answer.headers
    assert "uv sync --extra mesh" in capfd.readouterr().out, "how to install it stays in the log, not in the answer"


def test_the_file_is_the_tools_bytes_and_the_other_programs_are_untouched(tool):
    answer = client.post(ADDRESS, params=STEP, json={"values": VALUES})
    assert answer.content == b"ISO-10303-21;\n"
    assert client.post(ADDRESS, params={"program": "stp"}, json={"values": VALUES}).status_code == 422
    assert client.post(ADDRESS, params={"program": "iges"}, json={"values": VALUES}).status_code == 422
