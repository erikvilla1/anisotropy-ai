"""The repair page's endpoints (ADR-0135): a stepped patch repair, as a JSON object or as a repair file's text, worked by the engine's
hand calculation (ADR-0130, ADR-0131), its slice solved by the fea package's tool in a process (ADR-0132), and its solids built as a
STEP file. The engine's and the fea package's own tests check the numbers; these check that the API reads the description by the
engine's rules, passes the results on unchanged, refuses what the engine and the tools refuse in their words, says nothing of a tool
that fails, and records a summary rather than the drawings or the file."""

import importlib.util
import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_engine.repair import repair_from_dict, repair_report, repair_views
from anisotropy_api.main import SLICE_NOT_NOW, app
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

ROOT = Path(__file__).resolve().parents[2]
ENDPOINT, SOLVE, SHAPE = "/v1/repairs/analyze", "/v1/repairs/solve", "/v1/repairs/shape"
EXAMPLE = ROOT / "engine" / "examples" / "example-patch-repair.toml"
EXTERNAL = ROOT / "engine" / "examples" / "example-external-patch-repair.toml"
FIXTURES = ROOT / "tests" / "fixtures" / "repair"
client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here


def example(path: Path = EXAMPLE, **changes) -> dict:
    """An example's table; `table__key=value` changes one value, and `None` takes it out."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for where, value in changes.items():
        table, key = where.split("__")
        if value is None:
            data[table].pop(key)
        else:
            data[table][key] = value
    return data


def close(a, b, rel=1e-9) -> bool:
    """The same JSON value, numbers within `rel` of each other: a computed float may differ in its last digits from machine to machine."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], rel) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return a == pytest.approx(b, rel=rel, abs=1e-9)
    return a == b


@pytest.mark.parametrize("path", [EXAMPLE, EXTERNAL], ids=lambda path: path.stem)
def test_a_repair_file_is_worked_and_its_results_are_the_engines(path):
    answer = client.post(ENDPOINT, json={"toml": path.read_text(encoding="utf-8")})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["repair"] == example(path), "the description as the engine read it, so the page can fill its steps from a file"
    repair, load = repair_from_dict(example(path))
    assert close(body["report"], json.loads(json.dumps(repair_report(repair, "mm-MPa", load))))
    assert close(body["views"], json.loads(json.dumps(repair_views(repair, "mm-MPa", load))))
    assert body["needs"] == [] and body["engine_version"]
    assert close(client.post(ENDPOINT, json={"repair": example(path)}).json()["report"], body["report"]), "the JSON form gives the same answer"


def test_a_repair_with_no_load_is_described_and_drawn_and_says_what_a_solve_needs():
    stated = example(adhesive__poisson=None, parent__nu23=None)
    stated.pop("applied")
    body = client.post(ENDPOINT, json={"repair": stated}).json()
    assert "answer" not in body["report"]["lap"] and "lap" not in body["views"] and len(body["report"]["regions"]) > 10
    assert [need["path"] for need in body["needs"]] == ["parent.nu23", "adhesive.poisson", "applied.load"]
    refused = client.post(SOLVE, json={"repair": stated})
    assert refused.status_code == 422
    assert refused.json()["detail"] == ("The solve of the slice needs: the laminate ply's constants through the thickness: nu23 for a unidirectional ply, or all of "
                                        "E3, G13, G23, nu13, nu23; the adhesive's Poisson's ratio; a load per unit width that is not zero.")


def test_what_the_engine_refuses_is_refused_in_its_words_by_all_three():
    for stated, words in ((example(steps__count=9), "9 steps of 1 plies remove 9 plies, and the laminate has 8"),
                          (example() | {"units": "imperial"}, "units must be one of SI, mm-MPa, US, psi, got 'imperial'"),
                          (example() | {"wing": {}}, "The repair has tables it does not read: wing"),
                          (example(adhesive__thickness="thin"), "[adhesive]: A length must be a number, got 'thin'")):
        for endpoint in (ENDPOINT, SOLVE, SHAPE):
            answer = client.post(endpoint, json={"repair": stated})
            assert answer.status_code == 422 and answer.json()["detail"] == words, (endpoint, answer.text)
    assert client.post(ENDPOINT, json={}).status_code == 422
    assert client.post(ENDPOINT, json={"repair": example(), "toml": "title = 'x'"}).status_code == 422
    assert client.post(SOLVE, json={"repair": example(), "cut_faces": "glued"}).status_code == 422
    broken = client.post(ENDPOINT, json={"toml": "title = "})
    assert broken.status_code == 422 and broken.json()["detail"]


def test_the_pages_choices_and_its_tests_answers_are_what_the_script_writes():
    spec = importlib.util.spec_from_file_location("repair_choices", ROOT / "scripts" / "repair-choices.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hint = "run: uv run --project fea python scripts/repair-choices.py --solve"
    assert module.OUT.read_text(encoding="utf-8") == module.text(), hint
    choices = module.choices()
    assert choices["example"] == example() and choices["external"] == example(EXTERNAL)
    assert {"id": "im7-8552", "name": "IM7 / 8552", "strengths": True} in choices["materials"]
    for name, path in (("example", EXAMPLE), ("external", EXTERNAL)):
        kept = json.loads((FIXTURES / f"{name}-answer.json").read_text(encoding="utf-8"))
        assert close(kept, json.loads(json.dumps(module.answer(name)))), hint
        sent = client.post(ENDPOINT, json={"repair": example(path)}).json()
        assert close({key: sent[key] for key in ("repair", "report", "views", "needs")}, {key: kept[key] for key in ("repair", "report", "views", "needs")}), \
            "the browser test's answer is the API's"


@pytest.mark.parametrize("name", ["example", "external"])
def test_the_repair_file_the_page_saves_reads_back_as_the_example(name):
    """tests/fixtures/repair/<name>-saved.toml is what the page's writer makes of an example, checked by tests/repair.test.ts; the engine
    reads it as the same description, so a saved repair opens as it was."""
    saved = (FIXTURES / f"{name}-saved.toml").read_text(encoding="utf-8")
    assert tomllib.loads(saved) == example(EXAMPLE if name == "example" else EXTERNAL)
    assert client.post(ENDPOINT, json={"toml": saved}).status_code == 200


# ---- the solve of the slice and the shape, with a stand-in for each tool: what the API does with every way a tool can end

FAKE_TOOL = '''
import json, sys
stated = json.load(open(sys.argv[1], encoding="utf-8"))
mode = stated.get("title")
if mode == "refuse":
    print("Example"); print("refused: The forces along the load do not add up to the load at every station (off by 2.00e-02 of it)")
    print("The shape has no volume", file=sys.stderr)
    sys.exit(2)
if mode == "stop":
    print("stopped: ccx at /secret/path ended with status 1", file=sys.stderr)
    sys.exit(3)
if mode == "crash":
    print("Traceback (most recent call last): secret/path.py", file=sys.stderr)
    sys.exit(1)
if mode == "slow":
    import time
    time.sleep(5)
if "--out" in sys.argv:
    from pathlib import Path
    out = Path(sys.argv[sys.argv.index("--out") + 1]); out.mkdir(parents=True)
    report = {"headline": "Under 100 N/mm: largest bondline shear 11.5 MPa", "units": {"length": "mm", "stress": "MPa", "force": "N/mm"},
              "model": {"cut_faces": sys.argv[sys.argv.index("--cut-faces") + 1], "elements": 6344}, "checks": {"equilibrium": 1e-7, "far_field": 4e-7},
              "bond": {"peak_shear": {"value": -11.5, "r": 37.3, "part": "Adhesive on the ledge of step 2"}, "peak_peel": {"value": 4.1, "r": 62.4, "part": "x"}},
              "first": {"what": "adhesive", "load": 260.8}}
    if mode == "empty":
        report = ["not", "a", "report"]
    if mode == "nan":
        report["bond"]["peak_shear"]["value"] = float("nan")
    (out / "repair-solve.json").write_text(json.dumps(report), encoding="utf-8")
else:
    step, parts = sys.argv[sys.argv.index("--step") + 1], sys.argv[sys.argv.index("--parts") + 1]
    open(step, "w", encoding="ascii").write("ISO-10303-21;\\nEND-ISO-10303-21;\\n")
    json.dump({"title": mode, "units": {"length": "mm", "volume": "mm^3"}, "parts": [{"name": "Laminate ply 1 (45 deg)", "kind": "parent", "angle": 45.0,
               "volume": 10972.8}], "volumes": {"parent": 10972.8, "adhesive": 0.0, "patch": 0.0, "cover": 0.0}}, open(parts, "w", encoding="utf-8"))
'''


@pytest.fixture
def fake_tools(monkeypatch, tmp_path):
    import anisotropy_api.main as main_module
    script = tmp_path / "fake_repair_tool.py"
    script.write_text(FAKE_TOOL, encoding="utf-8")
    monkeypatch.setattr(main_module, "repair_model_command", lambda: [sys.executable, str(script)])
    monkeypatch.setattr(main_module, "repair_shape_command", lambda: [sys.executable, str(script)])
    return main_module


def test_the_solve_comes_back_as_the_tools_report_with_its_headline_apart(fake_tools):
    answer = client.post(SOLVE, json={"repair": example()})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["headline"] == "Under 100 N/mm: largest bondline shear 11.5 MPa" and "headline" not in body["report"]
    assert body["report"]["model"] == {"cut_faces": "open", "elements": 6344} and body["report"]["bond"]["peak_shear"]["value"] == -11.5
    assert client.post(SOLVE, json={"repair": example(), "cut_faces": "bonded"}).json()["report"]["model"]["cut_faces"] == "bonded"
    assert client.post(SOLVE, json={"toml": EXAMPLE.read_text(encoding="utf-8")}).status_code == 200, "a repair file's text is solved too"


def test_the_tools_own_refusal_is_passed_on_and_a_tool_that_fails_says_nothing_of_itself(fake_tools, capsys):
    refused = client.post(SOLVE, json={"repair": example() | {"title": "refuse"}})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "The forces along the load do not add up to the load at every station (off by 2.00e-02 of it)"
    for mode in ("stop", "crash", "empty", "nan"):
        failed = client.post(SOLVE, json={"repair": example() | {"title": mode}})
        assert failed.status_code == 503 and failed.json()["detail"] == SLICE_NOT_NOW, (mode, failed.text)
    assert "ccx at /secret/path ended with status 1" in capsys.readouterr().out, "the cause is in the log"
    shape = client.post(SHAPE, json={"repair": example() | {"title": "refuse"}})
    assert shape.status_code == 422 and shape.json()["detail"] == "The shape has no volume"
    crashed = client.post(SHAPE, json={"repair": example() | {"title": "crash"}})
    assert crashed.status_code == 503 and crashed.json()["detail"] == "The shape could not be built"


def test_a_solve_that_outlasts_its_time_is_ended_and_said_so(fake_tools, monkeypatch):
    monkeypatch.setattr(fake_tools, "REPAIR_SOLVE_TIMEOUT_S", 0.5)
    late = client.post(SOLVE, json={"repair": example() | {"title": "slow"}})
    assert late.status_code == 504 and late.json()["detail"] == "The solve of the slice took too long"


def test_without_the_tools_the_solve_and_the_shape_are_unavailable(monkeypatch):
    import anisotropy_api.main as main_module
    monkeypatch.setattr(main_module, "repair_model_command", lambda: None)
    monkeypatch.setattr(main_module, "repair_shape_command", lambda: None)
    assert client.post(SOLVE, json={"repair": example()}).status_code == 503
    assert client.post(SHAPE, json={"repair": example()}).status_code == 503


def test_the_shape_comes_back_as_the_step_files_text_and_the_table_of_its_solids(fake_tools):
    answer = client.post(SHAPE, json={"repair": example()})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["step"].startswith("ISO-10303-21;") and body["parts"]["parts"][0]["name"] == "Laminate ply 1 (45 deg)"


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        yield recorded


@needs_test_database
def test_each_is_recorded_by_the_description_and_a_summary_never_the_drawings_or_the_file(recording, fake_tools):
    answer = recording.post(ENDPOINT, json={"repair": example()})
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    assert run["actor"] == "studio" and run["endpoint"] == ENDPOINT and run["status"] == "solved" and run["inputs"]["repair"] == example()
    response = run["response"]
    assert response["kind"] == "flush" and response["load"] == 100.0 and response["solve_needs"] == []
    assert response["peak_shear"] == answer.json()["report"]["lap"]["answer"]["peak_shear"]
    assert response["elastic_limit_load"] == pytest.approx(answer.json()["report"]["lap"]["answer"]["elastic_limit_load"])
    assert "regions" not in response and "lap" not in response, "never the rectangles or the curve"
    solved = recording.post(SOLVE, json={"repair": example()})
    run = recording.get(f"/v1/runs/{solved.json()['run_id']}").json()
    assert run["endpoint"] == SOLVE and run["response"]["headline"] == solved.json()["headline"] and run["response"]["first"] == {"what": "adhesive", "load": 260.8}
    shaped = recording.post(SHAPE, json={"repair": example()})
    run = recording.get(f"/v1/runs/{shaped.json()['run_id']}").json()
    assert run["endpoint"] == SHAPE and run["response"]["parts"] == 1 and run["response"]["step_bytes"] > 0 and "ISO-10303" not in json.dumps(run["response"])
    refused = recording.post(SOLVE, json={"repair": example(adhesive__poisson=None)})
    run = recording.get(f"/v1/runs/{refused.headers['X-Anisotropy-Run-Id']}").json()
    assert run["status"] == "rejected" and run["error"].startswith("The solve of the slice needs: the adhesive's Poisson's ratio")


# ---- the real tools, where the fea environment is installed

FEA_VENV = ROOT / "fea" / ".venv"
FEA_GMSH = list(FEA_VENV.glob("lib/python*/site-packages/gmsh*"))


@pytest.mark.skipif(not FEA_VENV.is_dir() or shutil.which("ccx") is None, reason="the fea environment or CalculiX (ccx) is not installed here")
def test_the_examples_slice_is_solved_by_the_fea_package_and_is_the_pages_tests_answer():
    answer = client.post(SOLVE, json={"toml": EXAMPLE.read_text(encoding="utf-8")})
    assert answer.status_code == 200, answer.text
    body, kept = answer.json(), json.loads((FIXTURES / "example-solve.json").read_text(encoding="utf-8"))
    assert body["headline"] == kept["headline"]
    assert body["report"].keys() == kept["report"].keys() and body["report"]["model"]["elements"] == kept["report"]["model"]["elements"]
    assert body["report"]["bond"]["peak_shear"]["value"] == pytest.approx(kept["report"]["bond"]["peak_shear"]["value"], rel=1e-5)


@pytest.mark.skipif(not FEA_GMSH, reason="the fea environment with Gmsh is not installed here (uv sync --project fea --extra mesh)")
def test_the_examples_solids_are_built_by_the_fea_package():
    answer = client.post(SHAPE, json={"toml": EXAMPLE.read_text(encoding="utf-8")})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["step"].startswith("ISO-10303-21;") and "Laminate ply 1 (45 deg)" in body["step"]
    assert body["parts"]["title"] == "Example stepped patch repair" and body["parts"]["volumes"]["patch"] > 0
