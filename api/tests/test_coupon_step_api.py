"""The model's shape as a STEP file through the API (ADR-0146): POST /v1/coupon-jobs/model?program=step answers the rows with the file
the fea package drew, under the rules of the other two downloads (ADR-0129). A stand-in for fea/tools/studio_tool.py plays `model` in
most of these tests, once and warm, so they need neither the fea environment nor Gmsh; fea/tests/test_coupon_shape.py draws the shapes
themselves and runs the tool. The tests at the end run the real tool behind the route, where the fea environment holds Gmsh. Some
answers are read over a real HTTP server on this machine, because the test client refuses nothing a browser or Node refuses."""

import json
import math
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from anisotropy_api.coupon_jobs import FEA, STUDIO
from anisotropy_api.live import LiveSolver
from anisotropy_api.main import MODEL_NOT_WRITTEN, MODEL_PARTS_LIMIT, app

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
    if values.get("notes") == "STOPS":  # what the real tool did with a name too long for a file: an error that names its folder
        raise OSError(36, "File name too long", str(out / ("A" * 300 + ".step")))
    if values.get("notes") == "SLEEPS":
        import time
        time.sleep(30)
    name = NAMES[values["test"]] + ".step"
    data = ("ISO-10303-21;\n" + ("every\n" if every else "") + (f"root {pathlib.Path(root).name}\n" if root else "")).encode("utf-8")
    (out / name).write_bytes(data)
    parts = {"title": NAMES[values["test"]], "units": {"length": "mm", "volume": "mm³", "step": "mm"},
             "parts": [{"name": "Laminate", "kind": "laminate", "layup": "[45/0/-45/90]s", "plies": 8, "ply_thickness": 0.18288,
                        "thickness": 1.46304, "material": "IM7-8552", "volume": values["length"] * values["width"] * 1.46304, "in_model": True}]}
    for end in ("Bottom", "Top") if "tab_material" in values else ():
        for face in ("top", "bottom"):
            parts["parts"].append({"name": f"{end} tab, {face} face", "kind": "tab", "layup": None, "plies": None, "ply_thickness": None,
                                   "thickness": 1.5, "material": values["tab_material"], "volume": 2100.0, "in_model": False})
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


# --------------------------------------------------------------------------------------------- what an answer may never hold

def nothing_of_this_machine(answer, tmp_path) -> bool:
    """No folder of this machine, no file of the tool and none of the tool's own error words, in the body or in a header."""
    said = answer.text + " ".join(f"{name}: {value}" for name, value in answer.headers.items())
    return not any(word in said for word in (str(tmp_path), "/tmp", "/home", "Traceback", "Error", "Errno", ".py", "stand-in", "uv run"))


@pytest.mark.parametrize("program", ["step", "abaqus", "ansys"])
def test_a_tool_that_stops_is_a_503_that_says_so_and_names_no_folder_of_this_machine(tool, tmp_path, capfd, monkeypatch, program):
    """The tool stops on an error that names its folder under the system's temporary one (as a real name too long for a file did), or,
    for the other two programs, on this stand-in's own refusal to write them. The answer says what happened; the cause is in the log."""
    monkeypatch.setattr("anisotropy_api.main._ansys_model", lambda request: True)
    answer = client.post(ADDRESS, params={"program": program}, json={"values": {**VALUES, "notes": "STOPS"}})
    assert answer.status_code == 503 and answer.json() == {"detail": MODEL_NOT_WRITTEN} == {"detail": "The model file could not be written here"}
    assert nothing_of_this_machine(answer, tmp_path)
    logged = capfd.readouterr().out
    assert "the model file was not written: the live solver" in logged
    assert ("File name too long" in logged and str(tmp_path) in logged) if program == "step" else "this stand-in draws a STEP file" in logged


def test_without_uv_the_answer_is_the_same_503_and_how_the_tool_is_run_stays_in_the_log(tmp_path, capfd, monkeypatch):
    monkeypatch.setattr(app.state, "live", LiveSolver(None, tmp_path / "live", 0), raising=False)
    monkeypatch.setattr(app.state, "settings", None, raising=False)
    answer = client.post(ADDRESS, params=STEP, json={"values": VALUES})
    assert answer.status_code == 503 and answer.json() == {"detail": MODEL_NOT_WRITTEN} and nothing_of_this_machine(answer, tmp_path)
    assert "uv is not on PATH" in capfd.readouterr().out


def test_no_answer_of_this_address_names_a_folder_of_this_machine(tool, tmp_path, monkeypatch):
    """Every way this address answers a STEP request with a stand-in behind it: the file, a stopped setup, a refusal, no Gmsh, a tool
    that stops, a tool that does not answer in time, and a request the schema refuses."""
    monkeypatch.setattr(tool, "timeout_s", 20.0)
    asked = {"the file": ({"values": {**VALUES, "tab_material": "E-glass/epoxy"}}, 200), "stopped": ({"values": {"form_version": "0.9", "test": "plate"}}, 422),
             "refused": ({"values": {**VALUES, "notes": "FILLET"}}, 422), "no Gmsh": ({"values": {**VALUES, "notes": "NO GMSH"}}, 503),
             "a tool that stops": ({"values": {**VALUES, "notes": "STOPS"}}, 503), "no rows": ({"values": {}}, 422), "not rows": ({"values": [1]}, 422)}
    for name, (body, status) in asked.items():
        answer = client.post(ADDRESS, params=STEP, json=body)
        assert answer.status_code == status and nothing_of_this_machine(answer, tmp_path), name
    monkeypatch.setattr(tool, "timeout_s", 0.5)
    late = client.post(ADDRESS, params=STEP, json={"values": {**VALUES, "notes": "SLEEPS"}})
    assert late.status_code == 504 and late.json() == {"detail": "the live solver did not answer in 0.5 s"} and nothing_of_this_machine(late, tmp_path)


# --------------------------------------------------------------------------------------------- the part table's size, over a real server

@pytest.fixture
def served(tool):
    """The API on a real HTTP server of this machine, with the stand-in tool behind it: (host, port)."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "the server did not start"
    yield "127.0.0.1", port
    server.should_exit = True
    thread.join(timeout=10.0)


def over_http(address: tuple[str, int], values: dict) -> tuple[int, dict[str, str], bytes, bytes]:
    """One POST to the model's address as bytes on a socket: the status, the headers, the header block as it was sent, and the body."""
    body = json.dumps({"values": values}).encode("utf-8")
    request = (f"POST {ADDRESS}?program=step HTTP/1.1\r\nHost: {address[0]}:{address[1]}\r\nContent-Type: application/json\r\n"
               f"X-Anisotropy-Actor: studio\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode("ascii") + body
    with socket.create_connection(address, timeout=30.0) as connection:
        connection.sendall(request)
        received = bytearray()
        while chunk := connection.recv(65536):
            received += chunk
    block, _, content = bytes(received).partition(b"\r\n\r\n")
    lines = block.decode("latin-1").split("\r\n")
    headers = {name.strip().lower(): value.strip() for name, _, value in (line.partition(":") for line in lines[1:])}
    return int(lines[0].split()[1]), headers, block, content


HEADERS_A_FETCH_TAKES = 8192  # half of what Node's fetch takes in all (16 KiB): what an answer's whole header block stays under
LONG_NAME = "glass fabric in epoxy, 45 degrees " * 124  # 4.2 kB: what a tab material's row held when Node's fetch refused the answer


def test_an_ordinary_part_table_comes_in_the_header_over_a_real_server(served):
    status, headers, block, content = over_http(served, {**VALUES, "tab_material": "E-glass/epoxy at 45 degrees"})
    assert status == 200 and content == b"ISO-10303-21;\n" and headers["content-type"] == "model/step"
    table = json.loads(headers["x-anisotropy-model-parts"])
    assert [part["material"] for part in table["parts"]] == ["IM7-8552"] + ["E-glass/epoxy at 45 degrees"] * 4
    assert len(headers["x-anisotropy-model-parts"]) < MODEL_PARTS_LIMIT / 2 and len(block) < HEADERS_A_FETCH_TAKES / 4


@pytest.mark.parametrize("material", [LONG_NAME, "\U0001f9f5" * 80, "glass " * 20000],
                         ids=["4.2 kB of words", "80 characters outside the basic plane", "120 kB"])
def test_a_part_table_too_large_for_a_header_is_left_out_and_the_file_still_comes(served, material):
    """The table repeats a tab's material four times, and a header is ASCII, so one character may travel as twelve. Past the limit the
    table is left out whole (the page then says where the layup is, lib/model-shape.ts): half a table would be no JSON at all."""
    status, headers, block, content = over_http(served, {**VALUES, "tab_material": material})
    assert status == 200 and content == b"ISO-10303-21;\n" and headers["x-anisotropy-model-file"] == "IM78552-UNT-L1.step"
    assert "x-anisotropy-model-parts" not in headers
    assert len(block) < HEADERS_A_FETCH_TAKES / 8, f"the header block is {len(block)} bytes"


def test_the_largest_part_table_sent_fits_the_limit_and_one_byte_more_is_left_out(served):
    def table_bytes(material: str) -> int:
        return len(json.dumps(json.loads(STAND_IN_TABLE.replace("MATERIAL", material)), ensure_ascii=True, separators=(",", ":")))

    longest = next(n for n in range(4000, 0, -1) if table_bytes("g" * n) <= MODEL_PARTS_LIMIT)  # four tabs: four bytes a character
    assert table_bytes("g" * longest) > MODEL_PARTS_LIMIT - 4
    status, headers, block, _ = over_http(served, {**VALUES, "tab_material": "g" * longest})
    assert status == 200 and len(headers["x-anisotropy-model-parts"]) == table_bytes("g" * longest) <= MODEL_PARTS_LIMIT == 4096
    assert len(block) < HEADERS_A_FETCH_TAKES
    status, headers, _, _ = over_http(served, {**VALUES, "tab_material": "g" * (longest + 1)})
    assert status == 200 and "x-anisotropy-model-parts" not in headers


STAND_IN_TABLE = json.dumps({"title": "IM78552-UNT-L1", "units": {"length": "mm", "volume": "mm³", "step": "mm"}, "parts": [
    {"name": "Laminate", "kind": "laminate", "layup": "[45/0/-45/90]s", "plies": 8, "ply_thickness": 0.18288, "thickness": 1.46304,
     "material": "IM7-8552", "volume": 250 * 25 * 1.46304, "in_model": True},
    *({"name": f"{end} tab, {face} face", "kind": "tab", "layup": None, "plies": None, "ply_thickness": None, "thickness": 1.5,
       "material": "MATERIAL", "volume": 2100.0, "in_model": False} for end in ("Bottom", "Top") for face in ("top", "bottom"))]})

NODE_FETCH = """
const [address, material] = [process.argv[2], process.argv[3].repeat(Number(process.argv[4]))];
const values = { form_version: "0.9", test: "unnotched tension", filled_by: "A. Tester", length: 250, width: 25, tab_material: material };
try {
  const answer = await fetch(address, { method: "POST", headers: { "Content-Type": "application/json", "X-Anisotropy-Actor": "studio" }, body: JSON.stringify({ values }) });
  console.log(JSON.stringify({ status: answer.status, parts: answer.headers.get("x-anisotropy-model-parts"), bytes: (await answer.arrayBuffer()).byteLength }));
} catch (error) {
  console.log(JSON.stringify({ failed: String(error.cause?.code ?? error.cause?.message ?? error.message) }));
}
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH: this test asks the server with Node's own fetch")
def test_nodes_fetch_takes_the_answer_whatever_a_tab_materials_row_holds(served, tmp_path):
    """Node's fetch refused the answer (UND_ERR_HEADERS_OVERFLOW) when a material of 4.2 kB made 18 kB of headers."""
    script = tmp_path / "fetch.mjs"
    script.write_text(NODE_FETCH, encoding="utf-8")
    address = f"http://{served[0]}:{served[1]}{ADDRESS}?program=step"
    for words, times, table in (("E-glass/epoxy", 1, True), ("glass fabric in epoxy, 45 degrees ", 124, False), ("glass ", 20000, False)):
        done = subprocess.run([shutil.which("node"), str(script), address, words, str(times)], capture_output=True, text=True, timeout=60, check=False)
        answer = json.loads(done.stdout)
        assert answer.get("status") == 200 and answer["bytes"] == len(b"ISO-10303-21;\n"), (words, times, answer, done.stderr[-300:])
        assert (answer["parts"] is not None) == table, (words, times)


# --------------------------------------------------------------------------------------------- the real tool behind the route

def gmsh_in_the_fea_environment() -> bool:
    """Whether the fea package's own environment, as it stands, holds Gmsh: asked without changing it (--no-sync)."""
    uv = shutil.which("uv")
    if uv is None:
        return False
    asked = subprocess.run([uv, "run", "--project", str(FEA), "--no-sync", "python", "-c",
                            "from anisotropy_fea.mesher import gmsh_available; raise SystemExit(0 if gmsh_available() else 3)"],
                           capture_output=True, text=True, timeout=120, check=False)
    return asked.returncode == 0


needs_gmsh = pytest.mark.skipif(not gmsh_in_the_fea_environment(),
                                reason="Gmsh is not in the fea environment: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")
ROWS = {"form_version": "0.9", "filled_by": "A. Tester", "date": "2026-11-27", "material_code": "IM7", "layup_code": "L1", "standard": "none",
        "size_from": "own", "team_model": "not built yet", "test_data": "none", "symmetric": "yes", "library": "im7-8552", "G13": 4688.43,
        "G23": 3000.0, "control": "displacement", "value": 1.0, "element_size": 2.0, "angles": [45, 0, -45, 90], "test": "unnotched tension",
        "length": 237.3, "width": 19.7, "tab_length": 41.9}
TABBED = {**ROWS, "tab_thickness": 1.7, "tab_bevel": 11.3, "tab_material": "E-glass ±45°"}


@pytest.fixture(scope="module")
def real_tool(tmp_path_factory):
    """fea/tools/studio_tool.py itself, warm, in the fea environment as it stands, with a folder of coupons of its own."""
    folder = tmp_path_factory.mktemp("real-tool")
    live = LiveSolver([shutil.which("uv"), "run", "--project", str(FEA), "--no-sync", "python", str(STUDIO), "--root", str(folder / "coupons")],
                      folder / "live", 1, timeout_s=60.0, wait_s=60.0)
    yield live, folder
    live.close()


@pytest.fixture
def real(real_tool, monkeypatch):
    monkeypatch.setattr(app.state, "live", real_tool[0], raising=False)
    monkeypatch.setattr(app.state, "settings", None, raising=False)
    return real_tool[1]


def step_text(written: str) -> str:
    """A string of a STEP file as the text it stands for, for the two directives these tests write: `\\X\\hh` and a doubled apostrophe."""
    return re.sub(r"\\X\\([0-9A-F]{2})", lambda found: chr(int(found.group(1), 16)), written).replace("''", "'")


@needs_gmsh
def test_the_real_tool_behind_the_route_draws_a_tabbed_strip_end_to_end(real):
    answer = client.post(ADDRESS, params=STEP, json={"values": TABBED})
    assert answer.status_code == 200, answer.text
    assert answer.headers["content-type"] == "model/step" and answer.headers["X-Anisotropy-Model-File"] == "IM7-UNT-L1.step"
    text = answer.content.decode("ascii")
    assert text.startswith("ISO-10303-21;") and text.rstrip().endswith("END-ISO-10303-21;")
    assert "SI_UNIT(.MILLI.,.METRE.)" in text and text.count("MANIFOLD_SOLID_BREP(") == 5
    described = " ".join(line.strip().strip(",")[1:-1] for line in text.split("FILE_DESCRIPTION((")[1].split("),'2;1');")[0].splitlines())
    assert "\\X\\B145\\X\\B0" in described and "E-glass ±45°" in step_text(described)  # the tab's material, as ISO 10303-21 writes it
    table = json.loads(answer.headers["X-Anisotropy-Model-Parts"])
    assert [part["name"] for part in table["parts"]] == ["Laminate", "Bottom tab, top face", "Bottom tab, bottom face", "Top tab, top face", "Top tab, bottom face"]
    laminate, tab = table["parts"][0], table["parts"][1]
    assert laminate["layup"] == "[45/0/-45/90]s" and laminate["plies"] == 8 and laminate["thickness"] == pytest.approx(8 * laminate["ply_thickness"])
    assert laminate["volume"] == pytest.approx(237.3 * 19.7 * laminate["thickness"], rel=1e-9)
    assert tab["material"] == "E-glass ±45°" and tab["thickness"] == pytest.approx(1.7) and tab["in_model"] is False
    assert not any((real / "live").iterdir())


@needs_gmsh
def test_the_real_tool_draws_a_very_fine_model_as_fast_as_a_coarse_one_because_a_shape_cuts_no_mesh(real):
    """An element size of 0.22 mm is about 97,000 elements of this strip, near the most a setup may state (ADR-0086 amendment 2), which
    the route once meshed before it drew anything."""
    client.post(ADDRESS, params=STEP, json={"values": ROWS})  # the worker is warm after this
    files, seconds = [], []
    for size in (2.0, 0.22):
        started = time.perf_counter()
        answer = client.post(ADDRESS, params=STEP, json={"values": {**ROWS, "element_size": size}})
        seconds.append(time.perf_counter() - started)
        assert answer.status_code == 200, answer.text
        files.append([line for line in answer.content.decode("ascii").splitlines() if not line.startswith("FILE_NAME(")])
    assert files[0] == files[1], "the element size is no part of a shape"
    assert seconds[1] < 5.0, f"the fine model took {seconds[1]:.1f} s (the coarse one {seconds[0]:.1f} s)"


@needs_gmsh
def test_the_real_tool_draws_a_plate_with_a_hole_from_the_rows_the_workspace_sends(real):
    """The workspace's own plate (the browser tests' rows) with a hole's diameter, and no tab length: the form shows a plate none."""
    rows = json.loads((Path(__file__).parents[2] / "tests" / "fixtures" / "studio-plate" / "values.json").read_text(encoding="utf-8"))
    assert rows["test"] == "plate" and "tab_length" not in rows
    rows.update(length=123.4, width=77.7, regions=[], supports=[{"region": "Edge-Left", "dofs": [1, 2, 3, 4, 5, 6]}], hole_diameter=21.7, element_size=5.0)
    answer = client.post(ADDRESS, params=STEP, json={"values": rows})
    assert answer.status_code == 200, answer.text
    text = answer.content.decode("ascii")
    assert text.count("MANIFOLD_SOLID_BREP(") == 1 and "CIRCLE(" in text
    (plate,) = json.loads(answer.headers["X-Anisotropy-Model-Parts"])["parts"]
    assert plate["volume"] == pytest.approx((123.4 * 77.7 - math.pi * 21.7 ** 2 / 4) * plate["thickness"], rel=1e-9)


@needs_gmsh
@pytest.mark.parametrize("changes, said", [
    ({"tab_thickness": 41.9 * math.tan(math.radians(11.3)) * (1 - 1e-9), "tab_bevel": 11.3, "tab_material": "glass"},
     "e-08 mm long, under the 0.001 mm that is the smallest size drawn."),
    ({"tab_thickness": 41.9 * math.tan(math.radians(11.3)) * (1 + 1e-9), "tab_bevel": 11.3, "tab_material": "glass"},
     "runs the tab's whole length, 41.9 mm, so it has no outer face left."),
    ({"tab_thickness": 1e-9, "tab_bevel": 90.0}, "the tabs' thickness is 1e-09 mm, under the 0.001 mm that is the smallest size drawn."),
    ({"tab_thickness": 10.0, "tab_bevel": 7.0}, "a bevel of 7 degrees over a thickness of 10 mm runs 81.4435 mm, and the tab is 41.9 mm long"),
], ids=["a bevel that leaves an outer face too short to draw", "a bevel that runs the tab's whole length", "a tab a nanometre thick",
        "a bevel longer than the tab"])
def test_a_shape_the_real_tool_cannot_draw_is_a_422_with_its_reason(real, changes, said):
    answer = client.post(ADDRESS, params=STEP, json={"values": {**ROWS, **changes}})
    assert answer.status_code == 422, answer.text
    detail = answer.json()["detail"]
    assert detail.startswith("This model cannot be drawn as a STEP file yet: ") and said in detail and detail.endswith(".")
    assert "runs 41.9 mm, and the tab is 41.9 mm long" not in detail  # two numbers that print alike are no reason
    assert nothing_of_this_machine(answer, real)


@needs_gmsh
def test_a_refusal_of_the_real_tool_is_in_the_units_the_rows_are_in(real):
    inches = {**ROWS, "units": "in-psi", "length": 10.0, "width": 1.0, "tab_length": 2.25, "ply_thickness": 0.0072, "G13": 680000.0, "G23": 433000.0,
              "value": 0.04, "element_size": 0.1, "tab_thickness": 0.4, "tab_bevel": 7.0}
    answer = client.post(ADDRESS, params=STEP, json={"values": inches})
    assert answer.status_code == 422
    assert answer.json()["detail"] == ("This model cannot be drawn as a STEP file yet: The tabs cannot be drawn: a bevel of 7 degrees over a thickness "
                                       "of 0.4 in runs 3.25774 in, and the tab is 2.25 in long, so it has no outer face left.")


@needs_gmsh
@pytest.mark.parametrize("program", ["step", "abaqus"])
@pytest.mark.parametrize("raw, said", [
    ('"width": Infinity', "Width (mm): a finite number is needed, not inf"),
    ('"width": 1e999', "Width (mm): a finite number is needed, not inf"),
    ('"length": NaN', "Length (mm): a finite number is needed, not nan"),
    ('"tab_thickness": Infinity, "tab_bevel": 30', "Tab thickness (mm): a finite number is needed, not inf"),
    ('"material_code": "' + "A" * 300 + '"', "the coupon's name would be 307 characters, and a name is at most 80; give shorter codes"),
    ('"layup_code": "L' + "1" * 90 + '"', "the coupon's name would be 99 characters, and a name is at most 80; give shorter codes"),
    ('"tab_thickness": 1.5, "tab_bevel": 30, "tab_material": "' + "g" * 81 + '"',
     "Tab material: at most 80 bytes (a letter outside the basic Latin letters takes 2 to 4), not 81"),
], ids=["Infinity", "1e999", "NaN", "an infinite tab", "a 300-character material code", "a 91-character layup code", "an 81-character tab material"])
def test_a_size_that_is_no_number_or_a_name_too_long_is_stopped_at_the_setup_check_with_its_row(real, program, raw, said):
    """What the JSON of a request may hold and no model may: each was a 503 with the tool's own error, one of them naming its folder."""
    body = json.dumps({"values": ROWS})[:-2] + ", " + raw + "}}"
    answer = client.post(ADDRESS, params={"program": program}, content=body.encode("utf-8"), headers={"Content-Type": "application/json"})
    assert answer.status_code == 422, answer.text
    detail = answer.json()["detail"]
    assert detail.startswith("The setup is not complete, so there is no model to write yet. ") and said in detail
    assert nothing_of_this_machine(answer, real)


@needs_gmsh
def test_a_name_at_its_limit_is_drawn_and_its_part_table_fits_the_header(real):
    """A tab material of 80 bytes, the most the form takes, each letter outside ASCII: the table travels at six bytes a letter."""
    material = "α" * 40
    answer = client.post(ADDRESS, params=STEP, json={"values": {**ROWS, "tab_thickness": 1.5, "tab_bevel": 30, "tab_material": material}})
    assert answer.status_code == 200, answer.text
    raw = answer.headers["X-Anisotropy-Model-Parts"]
    assert len(raw) <= MODEL_PARTS_LIMIT and json.loads(raw)["parts"][1]["material"] == material
    assert max(len(line) for line in answer.content.decode("ascii").split("FILE_DESCRIPTION((")[1].split("),'2;1');")[0].splitlines()) < 80


SEEDS_OF_THE_STRIP = '"element_size": null, "mesh_partitions": "41.9, 195.4", '
PAST_THE_MOST = "elements; a setup holds at most 100,000, whatever is made of it: "
NOT_A_503 = [  # what the review's second round still got a 503 or a 504 for, each with the reason its row now gives
    ('"length": 1' + "0" * 400, "Length (mm): the number is too large"),
    ('"angles": [45, 1' + "0" * 400 + ', -45, 90]', "Ply 2: the number is too large"),
    ('"tab_thickness": 1.5, "tab_bevel": 30, "tab_material": "' + "\U0001F600" * 80 + '"',
     "Tab material: at most 80 bytes (a letter outside the basic Latin letters takes 2 to 4), not 320"),
    ('"size_from": "' + "s" * 5000 + '"', "Where the size comes from: one word of it takes 5000 bytes, and a line of a model file holds a word of at most 200; "
                                          "shorten it or put a space in it"),
    (SEEDS_OF_THE_STRIP + '"mesh_nx": 1000000000000, "mesh_seeds": "20, 80, 20"',
     "the mesh would have more than 1,000,000,000,000 " + PAST_THE_MOST + "give fewer elements across the width or fewer rows per segment"),
    (SEEDS_OF_THE_STRIP + '"mesh_nx": 10, "mesh_seeds": "20, 99999999999, 20"',
     "the mesh would have more than 1,000,000,000,000 " + PAST_THE_MOST + "give fewer elements across the width or fewer rows per segment"),
    ('"element_size": 1e-5', "the mesh would have more than 1,000,000,000,000 " + PAST_THE_MOST + "use an element size of 0.22 mm or more"),
    ('"element_size": 1e-6', "the mesh would have more than 1,000,000,000,000 " + PAST_THE_MOST + "use an element size of 0.22 mm or more"),
    ('"element_size": 5e-324', "the mesh would have more than 1,000,000,000,000 " + PAST_THE_MOST + "use an element size of 0.22 mm or more"),
    ('"element_size": 0.1', "the mesh would have 467,481 " + PAST_THE_MOST + "use an element size of 0.22 mm or more"),
]


@needs_gmsh
@pytest.mark.parametrize("program", ["step", "abaqus", "ansys"])
@pytest.mark.parametrize("around, count", [(39000, "1,113,900"), (190000, "5,417,400")])
def test_a_plate_with_a_hole_and_far_too_many_nodes_around_it_is_a_422_for_every_program_and_soon(real, program, around, count):
    """The third review's plate: a hole with 39,000 or 190,000 nodes around it in one ring. Its STEP file came, and its file for Abaqus
    or Ansys was a 504 at the route's 30 s, because the count the check judged left out the column and the band through the hole
    (ADR-0086 amendment 2). The refusal names the nodes, which no element size takes out of the plate."""
    rows = json.loads((Path(__file__).parents[2] / "tests" / "fixtures" / "studio-plate" / "values.json").read_text(encoding="utf-8"))
    rows.update(length=200.0, width=100.0, element_size=2.0, hole_diameter=20.0, regions=[], supports=[{"region": "Edge-Left", "dofs": [1, 2, 3, 4, 5, 6]}],
                hole_circumferential=around, hole_radial=1)
    started = time.perf_counter()
    answer = client.post(ADDRESS, params={"program": program}, json={"values": rows})
    seconds = time.perf_counter() - started
    assert answer.status_code == 422, answer.text[:400]
    assert answer.json()["detail"] == ("The setup is not complete, so there is no model to write yet. Mesh quality acceptable: the mesh would have "
                                       f"{count} elements; a setup holds at most 100,000, whatever is made of it: give at most 3,424 nodes around the hole")
    assert seconds < 10.0, seconds
    assert nothing_of_this_machine(answer, real)


@needs_gmsh
@pytest.mark.parametrize("program", ["step", "abaqus", "ansys"])
@pytest.mark.parametrize("raw, said", NOT_A_503, ids=["a length of 1 and 400 zeros", "a ply angle of 1 and 400 zeros", "a tab material of 80 emoji",
                                                     "a 5000-character word", "10^12 elements across", "99999999999 rows in a segment",
                                                     "an element size of 1e-5 mm", "an element size of 1e-6 mm", "an element size of 5e-324 mm",
                                                     "an element size of 0.1 mm"])
def test_what_no_file_can_hold_is_a_422_with_its_rows_reason_for_every_program_and_soon(real, program, raw, said):
    """Each of these was a 503 or, past the route's 30 s, a 504, for at least one program: a number no float holds, a name or a word no
    line of a deck holds, and a mesh that took the memory of the machine before anything was refused (ADR-0146, ADR-0086 amendment 2)."""
    body = json.dumps({"values": ROWS})[:-2] + ", " + raw + "}}"
    started = time.perf_counter()
    answer = client.post(ADDRESS, params={"program": program}, content=body.encode("utf-8"), headers={"Content-Type": "application/json"})
    seconds = time.perf_counter() - started
    assert answer.status_code == 422, answer.text[:400]
    detail = answer.json()["detail"]
    assert detail.startswith("The setup is not complete, so there is no model to write yet. ") and said in detail and len(detail) < 700
    assert seconds < 10.0, seconds
    assert nothing_of_this_machine(answer, real)
