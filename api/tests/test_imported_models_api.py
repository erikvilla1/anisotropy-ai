"""A model brought in as an Abaqus deck, through the API (ADR-0105): POST /v1/imported-models passes the deck to the studio tool and
its answer on as written, keeps nothing of the deck, records its name, size and digest, and is offered where every test is. A stand-in
for fea/tools/studio_tool.py plays `import` and `serve` here, so these tests need neither the fea environment nor the engine;
fea/tests/test_imported.py runs the reader and the kernel themselves."""

import hashlib
import json
import sys

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.live import LiveSolver
from anisotropy_api.main import IMPORTED_MODELS, app
from anisotropy_api.settings import DATABASE_VARIABLE, LIVE_WORKERS_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

STAND_IN = r'''
"""A stand-in for fea/tools/studio_tool.py import and serve: the deck's first line chooses what it does."""
import argparse, json, os, pathlib, sys, time

def read(deck_path, units, name, out):
    text = pathlib.Path(deck_path).read_text(encoding="utf-8")
    first = text.splitlines()[0] if text else ""
    if first == "SLOW":
        time.sleep(5)
    if first == "ERROR":
        raise ValueError("this deck breaks the tool")
    out = pathlib.Path(out)
    out.mkdir(parents=True)
    head = {"state": "solved", "name": name, "units": units, "problem": None,
            "reading": {"elements": 16, "layup": "[0/90]s", "skipped": ["line 8: *preprint"], "warnings": [], "seen_at": str(deck_path)}}
    if first == "*Solid":
        head.update(state="refused", reading=None, problem={"message": "line 15: this version does not read solid elements (C3D8R)", "line": 15,
                                                                 "unread": [{"what": "solid elements", "keyword": "C3D8R", "lines": [15]}]})
    if first == "*Loose":
        head.update(state="read", problem={"message": "the stiffness matrix is singular", "line": None})
    (out / "import.json").write_text(json.dumps(head), encoding="utf-8")
    (out / "timings.json").write_text(json.dumps({"model": 0.02, "total": 0.03}), encoding="utf-8")
    if head["state"] == "refused":
        return "refused"
    (out / "preview.json").write_text(json.dumps({"mesh": {"nodes": [[0, 0]]}}), encoding="utf-8")
    if head["state"] == "read":
        return "read"
    summary = {"verdict": {"basis": "whole", "earliest": "tsai_wu", "factor": 0.93, "fails": True, "outside_earlier": None}, "pid": os.getpid()}
    (out / "fields.json").write_text(json.dumps({"summary": summary, "element": {"big": list(range(5000))}}, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    (out / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (out / "explanation.json").write_text(json.dumps({"writer": "template", "sentences": ["fails"]}), encoding="utf-8")
    return "solved"

parser = argparse.ArgumentParser()
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("import"); p.add_argument("deck"); p.add_argument("--units", required=True); p.add_argument("--name"); p.add_argument("--out", required=True)
commands.add_parser("serve")
args = parser.parse_args()
if args.command == "import":
    try:
        read(args.deck, args.units, args.name, args.out)
    except ValueError as exc:
        sys.exit(f"studio_tool: {exc}")
else:
    print(json.dumps({"ready": True, "imports": 0.0}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            answer = {"state": read(request["deck"], request["units"], request.get("name"), request["out"])}
        except Exception as exc:
            answer = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(answer), flush=True)
'''

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here
DECK = b"*Heading\n** a deck the stand-in solves\n"
ASKED = {"params": {"units": "mm-MPa"}, "headers": {"X-Anisotropy-Model-Name": "plate.inp"}}


def solver(tmp_path, workers: int, **kwargs) -> LiveSolver:
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    return LiveSolver([sys.executable, str(stand_in)], tmp_path / "live", workers, **kwargs)


@pytest.fixture
def offered(monkeypatch):
    monkeypatch.setattr("anisotropy_api.main._every_test", lambda request: True)


@pytest.fixture
def warm(tmp_path, monkeypatch, offered):
    live = solver(tmp_path, 1, timeout_s=2.0, wait_s=10.0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    yield live
    live.close()


def test_a_deck_is_answered_with_the_reading_and_the_kernels_fields_as_the_tool_wrote_them(warm, tmp_path):
    answer = client.post(IMPORTED_MODELS, **ASKED, content=DECK)
    assert answer.status_code == 200
    body = answer.json()
    assert (body["state"], body["name"], body["units"], body["solver"], body["warm"], body["problem"]) == ("solved", "plate.inp", "mm-MPa", "kernel", True, None)
    assert body["reading"]["elements"] == 16 and body["reading"]["skipped"] == ["line 8: *preprint"]
    assert body["fields"]["summary"]["verdict"]["earliest"] == "tsai_wu" and len(body["fields"]["element"]["big"]) == 5000
    assert body["explanation"]["sentences"] == ["fails"] and body["preview"]["mesh"]["nodes"] == [[0, 0]]
    assert body["timings"]["model"] == 0.02 and body["seconds"] > 0 and body["run_id"] is None  # nothing is recorded without the lifespan
    assert answer.headers.get("content-encoding") == "gzip"


def test_nothing_of_the_deck_is_left_on_the_machine(warm, tmp_path):
    seen_at = client.post(IMPORTED_MODELS, **ASKED, content=DECK).json()["reading"]["seen_at"]
    assert seen_at.endswith("model.inp") and str(tmp_path / "live") in seen_at
    assert list((tmp_path / "live").iterdir()) == [], "the deck's folder is removed once the answer is read"


def test_a_refused_deck_and_one_that_is_read_but_not_solved_answer_with_why(warm):
    refused = client.post(IMPORTED_MODELS, **ASKED, content=b"*Solid\n")
    body = refused.json()
    assert refused.status_code == 200 and body["state"] == "refused" and body["problem"] == {
        "message": "line 15: this version does not read solid elements (C3D8R)", "line": 15,
        "unread": [{"what": "solid elements", "keyword": "C3D8R", "lines": [15]}]}  # everything unread, passed on as the package wrote it (ADR-0105 amendment 1)
    assert body["reading"] is None and body["preview"] is None and body["fields"] is None and body["explanation"] is None
    read = client.post(IMPORTED_MODELS, **ASKED, content=b"*Loose\n").json()
    assert read["state"] == "read" and "singular" in read["problem"]["message"] and read["preview"] is not None and read["fields"] is None


def test_the_name_is_a_files_name_and_the_units_one_of_the_four(warm):
    named = lambda name: client.post(IMPORTED_MODELS, params={"units": "in-psi"}, headers={"X-Anisotropy-Model-Name": name}, content=DECK).json()["name"]  # noqa: E731
    assert named("C%3A%5Cmodels%5C..%5Cwing%20panel.inp") == "wing panel.inp"  # percent-encoded, as the page sends it
    assert named("../../etc/passwd") == "passwd" and named("pl%C3%A4tte.inp") == "plätte.inp"
    assert client.post(IMPORTED_MODELS, params={"units": "in-psi"}, content=DECK).json()["name"] == "model.inp"
    assert client.post(IMPORTED_MODELS, content=DECK).status_code == 422  # a deck carries no units: they are stated
    assert client.post(IMPORTED_MODELS, params={"units": "cm-kPa"}, content=DECK).status_code == 422


def test_no_body_is_a_422_and_a_model_past_the_size_is_a_413(warm, monkeypatch):
    empty = client.post(IMPORTED_MODELS, **ASKED, content=b"")
    assert empty.status_code == 422 and "no body" in empty.json()["detail"]
    monkeypatch.setattr("anisotropy_api.main.MAX_MODEL_BYTES", 16)
    large = client.post(IMPORTED_MODELS, **ASKED, content=DECK)
    assert large.status_code == 413 and "at most 16 bytes" in large.json()["detail"]


def test_where_not_every_test_is_offered_a_model_is_not_imported(tmp_path, monkeypatch):
    monkeypatch.setattr("anisotropy_api.main._every_test", lambda request: False)
    live = solver(tmp_path, 0)
    monkeypatch.setattr(app.state, "live", live, raising=False)
    refused = client.post(IMPORTED_MODELS, **ASKED, content=DECK)
    assert refused.status_code == 403 and refused.json()["detail"] == "Importing a model is not offered yet."
    assert not (tmp_path / "live").exists(), "the deck was not written anywhere"


def test_a_slow_tool_is_refused_in_the_pages_words_and_a_failing_one_is_a_503(warm):
    slow = client.post(IMPORTED_MODELS, **ASKED, content=b"SLOW\n")
    assert slow.status_code == 422 and slow.json()["detail"] == "This model took too long to solve here. Try a coarser mesh."
    assert client.post(IMPORTED_MODELS, **ASKED, content=DECK).status_code == 200  # a new worker took its place
    broken = client.post(IMPORTED_MODELS, **ASKED, content=b"ERROR\n")
    assert broken.status_code == 503 and "this deck breaks the tool" in broken.json()["detail"]


def test_without_warm_workers_each_request_starts_the_tool(tmp_path, monkeypatch, offered):
    monkeypatch.setattr(app.state, "live", solver(tmp_path, 0), raising=False)
    body = client.post(IMPORTED_MODELS, **ASKED, content=DECK).json()
    assert body["state"] == "solved" and body["warm"] is False and body["name"] == "plate.inp"
    assert list((tmp_path / "live").iterdir()) == []
    monkeypatch.setattr(app.state, "live", LiveSolver(None, tmp_path / "live", 1), raising=False)
    assert client.post(IMPORTED_MODELS, **ASKED, content=DECK).status_code == 503


@pytest.fixture
def recording(empty_runs, monkeypatch, tmp_path, offered):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(LIVE_WORKERS_VARIABLE, "0")  # the lifespan's own solver starts no worker; the test's replaces it
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        app.state.live = solver(tmp_path, 1, timeout_s=5.0, wait_s=10.0)
        yield recorded
        app.state.live.close()


@needs_test_database
def test_an_import_is_recorded_by_its_digest_and_summary_and_never_the_deck(recording):
    answer = recording.post(IMPORTED_MODELS, **ASKED, content=DECK)
    assert answer.status_code == 200 and answer.json()["run_id"] == answer.headers["X-Anisotropy-Run-Id"]
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    assert run["actor"] == "studio" and run["endpoint"] == IMPORTED_MODELS and run["status"] == "solved"
    assert run["inputs"] == {"name": "plate.inp", "units": "mm-MPa", "bytes": len(DECK), "sha256": hashlib.sha256(DECK).hexdigest()}
    response = run["response"]
    assert response["state"] == "solved" and response["summary"]["verdict"]["earliest"] == "tsai_wu" and response["reading"]["elements"] == 16
    fields = json.dumps(answer.json()["fields"], separators=(",", ":"))
    assert response["fields_sha256"] == hashlib.sha256((fields + "\n").encode("utf-8")).hexdigest()
    assert "a deck the stand-in solves" not in json.dumps(run) and "big" not in json.dumps(response), "never the deck, never the arrays"

    refused = recording.post(IMPORTED_MODELS, **ASKED, content=b"*Solid\n")
    run = recording.get(f"/v1/runs/{refused.json()['run_id']}").json()
    assert run["status"] == "rejected" and "C3D8R" in run["error"] and run["inputs"]["bytes"] == 7
