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
from anisotropy_api.main import BOND_NOT_NOW, SLICE_NOT_NOW, app
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

ROOT = Path(__file__).resolve().parents[2]
ENDPOINT, SOLVE, SHAPE, BOND = "/v1/repairs/analyze", "/v1/repairs/solve", "/v1/repairs/shape", "/v1/repairs/bond"
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
    assert body["needs"] == [] and body["bond_needs"] == [] and body["engine_version"]
    assert close(client.post(ENDPOINT, json={"repair": example(path)}).json()["report"], body["report"]), "the JSON form gives the same answer"


def test_a_repair_with_no_load_is_described_and_drawn_and_says_what_a_solve_needs():
    stated = example(adhesive__poisson=None, parent__nu23=None)
    stated.pop("applied")
    body = client.post(ENDPOINT, json={"repair": stated}).json()
    assert "answer" not in body["report"]["lap"] and "lap" not in body["views"] and len(body["report"]["regions"]) > 10
    assert [need["path"] for need in body["needs"]] == ["parent.nu23", "adhesive.poisson", "applied.load"]
    assert [need["path"] for need in body["bond_needs"]] == ["parent.nu23", "adhesive.poisson"], "following the bond needs no load: the load is what it finds"
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
        keys = ("repair", "report", "views", "needs", "bond_needs")
        assert close({key: sent[key] for key in keys}, {key: kept[key] for key in keys}), "the browser test's answer is the API's"


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
if "--out" in sys.argv and "--cut-faces" not in sys.argv:  # the bond followed until it lets go: no choice of the cut faces
    from pathlib import Path
    out = Path(sys.argv[sys.argv.index("--out") + 1]); out.mkdir(parents=True)
    report = {"headline": "The bond first softens at 184 N/mm; in this model it lets go at 1340 N/mm", "units": {"length": "mm", "stress": "MPa", "force": "N/mm"},
              "model": {"elements": 3045, "pairs": 319}, "checks": {"equilibrium": 1e-11, "far_field": 2e-10}, "ended": "let_go",
              "onset": {"part": "Adhesive on the ledge of step 2", "step": 2, "r": 37.4, "load": 184.0, "shear": 30.0, "peel": -14.0, "lines": [{"r": [0.0, 1.0]}]},
              "let_go": {"load": 1340.0, "end_movement": 2.2, "spent": 0.005, "softening_length": 18.7, "parted_length": 0.0, "lines": [{"r": [0.0, 1.0]}]},
              "largest": {"load": 1340.0}, "curve": {"end_movement": [0.0, 2.2], "load": [0.0, 1340.0]}}
    if mode == "held":
        report["let_go"], report["ended"] = None, "steps"
    if mode == "empty":
        report = ["not", "a", "report"]
    if mode == "nan":
        report["let_go"]["load"] = float("nan")
    (out / "repair-bond.json").write_text(json.dumps(report), encoding="utf-8")
elif "--out" in sys.argv:
    from pathlib import Path
    out = Path(sys.argv[sys.argv.index("--out") + 1]); out.mkdir(parents=True)
    report = {"headline": "Under 100 N/mm: largest bondline shear 11.5 MPa", "units": {"length": "mm", "stress": "MPa", "force": "N/mm"}, "load": 100.0,
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
    monkeypatch.setattr(main_module, "repair_bond_command", lambda: [sys.executable, str(script)])
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
    monkeypatch.setattr(main_module, "repair_bond_command", lambda: None)
    assert client.post(SOLVE, json={"repair": example()}).status_code == 503
    assert client.post(SHAPE, json={"repair": example()}).status_code == 503
    assert client.post(BOND, json={"repair": example()}).status_code == 503


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


# ---- the bond followed until it lets go (ADR-0140), with the stand-in: the report passed on, every way the run can end

def test_the_bond_followed_comes_back_as_the_tools_report_with_its_headline_apart(fake_tools):
    answer = client.post(BOND, json={"repair": example()})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["headline"] == "The bond first softens at 184 N/mm; in this model it lets go at 1340 N/mm" and "headline" not in body["report"]
    assert body["report"]["let_go"]["load"] == 1340.0 and body["report"]["onset"]["load"] == 184.0 and body["report"]["model"]["pairs"] == 319
    assert client.post(BOND, json={"toml": EXAMPLE.read_text(encoding="utf-8")}).status_code == 200, "a repair file's text is followed too"
    unloaded = example()
    unloaded.pop("applied")
    assert client.post(BOND, json={"repair": unloaded}).status_code == 200, "no load is needed: the load is what the run finds"
    held = client.post(BOND, json={"repair": example() | {"title": "held"}})
    assert held.status_code == 200 and held.json()["report"]["let_go"] is None, "a run that ends before the bond lets go says so, and names no load"


def test_a_bond_that_lacks_its_strengths_or_its_energies_is_refused_with_the_list(fake_tools):
    refused = client.post(BOND, json={"repair": example(adhesive__peel_energy=None, adhesive__shear_energy=None, adhesive__peel_strength=None)})
    assert refused.status_code == 422
    assert refused.json()["detail"] == ("To follow the bond until it lets go the repair needs: the bond's peel strength; the bond's fracture energy in peel; "
                                        "the bond's fracture energy in shear.")
    wrong = client.post(BOND, json={"repair": example(adhesive__shear_energy=0)})
    assert wrong.status_code == 422 and wrong.json()["detail"] == "[adhesive]: The bond's shear energy must be a positive, finite number, got 0.0"


def test_the_bond_tools_refusal_is_passed_on_and_one_that_fails_or_runs_on_says_nothing_of_itself(fake_tools, monkeypatch, capsys):
    refused = client.post(BOND, json={"repair": example() | {"title": "refuse"}})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "The forces along the load do not add up to the load at every station (off by 2.00e-02 of it)"
    for mode in ("stop", "crash", "empty", "nan"):
        failed = client.post(BOND, json={"repair": example() | {"title": mode}})
        assert failed.status_code == 503 and failed.json()["detail"] == BOND_NOT_NOW, (mode, failed.text)
    assert "ccx at /secret/path ended with status 1" in capsys.readouterr().out, "the cause is in the log"
    monkeypatch.setattr(fake_tools, "REPAIR_BOND_TIMEOUT_S", 0.5)
    late = client.post(BOND, json={"repair": example() | {"title": "slow"}})
    assert late.status_code == 504 and late.json()["detail"] == "Following the bond took too long"


@needs_test_database
def test_a_bond_followed_is_recorded_by_its_loads_never_its_curves(recording, fake_tools):
    followed = recording.post(BOND, json={"repair": example()})
    run = recording.get(f"/v1/runs/{followed.json()['run_id']}").json()
    response = run["response"]
    assert run["endpoint"] == BOND and run["status"] == "solved" and response["headline"] == followed.json()["headline"]
    assert response["onset"] == {"load": 184.0, "r": 37.4, "part": "Adhesive on the ledge of step 2"}
    assert response["let_go"] == {"load": 1340.0, "softening_length": 18.7, "parted_length": 0.0} and response["largest_load"] == 1340.0
    assert response["ended"] == "let_go" and "curve" not in response and "lines" not in json.dumps(response)
    refused = recording.post(BOND, json={"repair": example(adhesive__peel_energy=None)})
    run = recording.get(f"/v1/runs/{refused.headers['X-Anisotropy-Run-Id']}").json()
    assert run["status"] == "rejected" and run["error"] == "To follow the bond until it lets go the repair needs: the bond's fracture energy in peel."


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


@pytest.mark.skipif(not FEA_VENV.is_dir(), reason="the fea environment is not installed here")
def test_the_examples_bond_is_followed_by_the_fea_package_and_is_the_pages_tests_answer():
    """The real run, about ten seconds. The path's steps may differ from machine to machine, so the loads are held to a part in a
    thousand, and the lists' lengths are not compared."""
    answer = client.post(BOND, json={"toml": EXAMPLE.read_text(encoding="utf-8")})
    assert answer.status_code == 200, answer.text
    body, kept = answer.json(), json.loads((FIXTURES / "example-bond.json").read_text(encoding="utf-8"))
    assert body["report"].keys() == kept["report"].keys() and body["report"]["model"]["pairs"] == kept["report"]["model"]["pairs"]
    assert body["report"]["onset"]["load"] == pytest.approx(kept["report"]["onset"]["load"], rel=1e-6)
    assert body["report"]["let_go"]["load"] == pytest.approx(kept["report"]["let_go"]["load"], rel=1e-3)
    assert body["report"]["let_go"]["softening_length"] == pytest.approx(kept["report"]["let_go"]["softening_length"], rel=0.02)
    assert body["headline"].split(";")[0] == kept["headline"].split(";")[0]


# ---- a change previewed and a quantity swept (ADR-0136): the engine's answers passed on, the pick held to a solved slice

CHANGES, SWEEPS = "/v1/repairs/changes", "/v1/repairs/sweeps"


def test_a_change_is_previewed_on_a_copy_and_is_the_engines():
    from anisotropy_engine.repair import RepairChange, preview_change
    change = {"action": "set", "quantity": "step_length", "value": 0.5, "unit": "in"}
    answer = client.post(CHANGES, json={"repair": example(), "change": change})
    assert answer.status_code == 200, answer.text
    body, direct = answer.json(), preview_change(example(), RepairChange(**change))
    assert body["words"] == direct["words"] == "The step length goes from 12.5 mm to 12.7 mm (0.5 in as written)."
    assert body["repair"] == direct["repair"] and body["repair"]["steps"]["length"] == 12.7
    assert close(body["before"], direct["before"]) and close(body["after"], direct["after"]) and body["units"] == direct["units"]
    assert body["before"]["repair_diameter"] == pytest.approx(125.0) and body["after"]["repair_diameter"] == pytest.approx(126.2)
    again = client.post(ENDPOINT, json={"repair": body["repair"]}).json()["report"]["lap"]["answer"]
    assert body["after"]["elastic_limit_load"] == pytest.approx(again["elastic_limit_load"]), "the preview is the hand calculation of the changed file"
    steps = client.post(CHANGES, json={"toml": EXAMPLE.read_text(encoding="utf-8"), "change": {"action": "add_steps", "count": 1}})
    assert steps.status_code == 200 and steps.json()["after"]["steps"] == steps.json()["before"]["steps"] + 1


def test_a_change_the_repair_cannot_take_and_a_change_that_is_none_are_refused_in_words():
    refused = client.post(CHANGES, json={"repair": example(), "change": {"action": "set", "quantity": "patch_overlap", "value": 20}})
    assert refused.status_code == 422 and "flush" in refused.json()["detail"], refused.text
    thick = client.post(CHANGES, json={"repair": example(), "change": {"action": "set", "quantity": "bondline", "value": 0.2}})
    assert thick.status_code == 422 and thick.json()["detail"].startswith("The bondline"), thick.text
    unit = client.post(CHANGES, json={"repair": example(), "change": {"action": "set", "quantity": "step_length", "value": 5, "unit": "psi"}})
    assert unit.status_code == 422 and "psi is not a length unit" in unit.json()["detail"]
    assert client.post(CHANGES, json={"repair": example(), "change": {"action": "set", "quantity": "step_length"}}).status_code == 422
    assert client.post(CHANGES, json={"repair": example(), "change": {"action": "paint", "count": 1}}).status_code == 422
    assert client.post(CHANGES, json={"repair": example()}).status_code == 422, "a change is asked for"


def test_a_sweep_without_a_load_is_the_engines_table_and_solves_nothing(monkeypatch):
    import anisotropy_api.main as main_module
    from anisotropy_engine.repair import RepairSweep, sweep_repair
    monkeypatch.setattr(main_module, "repair_model_command", lambda: pytest.fail("no pick, so no slice is solved"))
    sweep = {"quantity": "step_length", "start": 3, "end": 25}
    answer = client.post(SWEEPS, json={"repair": example(), "sweep": sweep})
    assert answer.status_code == 200, answer.text
    body, direct = answer.json(), sweep_repair(example(), RepairSweep(**sweep))
    assert body["words"] == direct["words"] and body["pick"] is None and body["picked"] is None and body["check"] is None and body["target"] is None
    assert close(body["rows"], direct["rows"]) and len(body["rows"]) == 24 and body["flat_from"]["value"] == 6.0
    assert body["rows"][-1]["refused"].startswith("The repair is"), "a value the panel cannot hold is a row, in the engine's words"


def test_a_sweep_to_a_load_picks_the_smallest_and_holds_it_to_a_solved_slice(fake_tools):
    answer = client.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "step_length", "start": 3, "end": 25, "load": 230}})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    pick = body["rows"][body["pick"]]
    assert pick["value"] == 4.0 and pick["elastic"] is True and body["picked"]["steps"]["length"] == 4.0 and body["target"] == 230.0
    assert [row["elastic"] for row in body["rows"][:2]] == [False, True] and body["rows"][-1]["elastic"] is None
    check = body["check"]
    assert check["state"] == "solved" and check["holds"] is True and check["first"] == {"what": "adhesive", "load": 260.8}
    assert check["headline"] == "Under 100 N/mm: largest bondline shear 11.5 MPa" and check["peak_peel"]["value"] == 4.1
    assert check["words"][-1] == "That is at or above the 230 N/mm named: the slice holds the pick."
    assert not any(word in " ".join(body["words"] + check["words"]).lower() for word in ("strength of the repair", "margin", "carries", "design"))
    unchecked = client.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "step_length", "start": 3, "end": 25, "load": 230}, "confirm": False})
    assert unchecked.json()["pick"] == body["pick"] and unchecked.json()["check"] is None
    none = client.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "step_length", "load": 300}})
    assert none.status_code == 200 and none.json()["pick"] is None and none.json()["check"] is None and none.json()["words"][-2].startswith("None of these keeps")


def test_a_slice_that_does_not_hold_the_pick_says_so(fake_tools):
    # the stand-in's slice reaches its first limit at 260.8 N/mm whatever the repair: a sweep to more than that, over the bondline, is not held
    answer = client.post(SWEEPS, json={"repair": example(adhesive__shear_strength=40.0), "sweep": {"quantity": "bondline", "load": 280}})
    assert answer.status_code == 200, answer.text
    check = answer.json()["check"]
    assert answer.json()["pick"] is not None and check["state"] == "solved" and check["holds"] is False
    assert check["words"][-1] == "That is below the 280 N/mm named: the slice does not hold the pick."
    # a first limit within 2 % of the load named is neither held nor not: a finer mesh may move it that far (ADR-0132)
    near = client.post(SWEEPS, json={"repair": example(adhesive__shear_strength=40.0), "sweep": {"quantity": "bondline", "load": 262}}).json()["check"]
    assert near["state"] == "solved" and near["holds"] is None and near["close"] is True
    assert near["words"][-1] == ("That is within 2 % of the 262 N/mm named, as far as a finer mesh may move a slice's number: "
                                 "too close to say whether the slice holds the pick.")


def test_a_pick_whose_slice_cannot_be_solved_leaves_the_sweep_whole_and_says_it_is_not_checked(fake_tools, monkeypatch, capsys):
    from anisotropy_api.main import PICK_NOT_CHECKED
    sweep = {"quantity": "step_length", "start": 3, "end": 25, "load": 230}
    whole = client.post(SWEEPS, json={"repair": example(), "sweep": sweep, "confirm": False}).json()
    for mode in ("stop", "crash", "empty", "nan"):
        body = client.post(SWEEPS, json={"repair": example() | {"title": mode}, "sweep": sweep}).json()
        assert body["check"] == {"state": "failed", "holds": None, "words": [PICK_NOT_CHECKED]}, mode
        assert body["rows"] == whole["rows"] and body["pick"] == whole["pick"] and body["words"] == whole["words"], mode
    assert "ccx at /secret/path" in capsys.readouterr().out, "the cause is in the log"
    refused = client.post(SWEEPS, json={"repair": example() | {"title": "refuse"}, "sweep": sweep}).json()["check"]
    assert refused["state"] == "refused" and refused["words"][0].startswith("The pick's slice was not solved: The forces along the load do not add up")
    monkeypatch.setattr(fake_tools, "REPAIR_SOLVE_TIMEOUT_S", 0.5)
    assert client.post(SWEEPS, json={"repair": example() | {"title": "slow"}, "sweep": sweep}).json()["check"]["state"] == "failed"
    monkeypatch.setattr(fake_tools, "repair_model_command", lambda: None)
    assert client.post(SWEEPS, json={"repair": example(), "sweep": sweep}).json()["check"]["state"] == "failed"
    needs = client.post(SWEEPS, json={"repair": example(adhesive__poisson=None), "sweep": sweep}).json()["check"]
    assert needs["state"] == "needs" and needs["words"][0].startswith("The pick is not checked by a solved slice, which needs: the adhesive's Poisson's ratio")


def test_a_sweep_the_engine_refuses_is_refused_in_its_words():
    unloaded = example()
    unloaded.pop("applied")
    no_load = client.post(SWEEPS, json={"repair": unloaded, "sweep": {"quantity": "step_length"}})
    assert no_load.status_code == 422 and no_load.json()["detail"].startswith("A sweep needs a load per unit width")
    no_strength = client.post(SWEEPS, json={"repair": example(adhesive__shear_strength=None), "sweep": {"quantity": "step_length", "load": 200}})
    assert no_strength.status_code == 422 and no_strength.json()["detail"].startswith("A sweep to a load needs the adhesive's shear strength")
    flush = client.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "patch_overlap"}})
    assert flush.status_code == 422 and "a flush patch fills its cut" in flush.json()["detail"]
    assert client.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "step_length", "start": 5}}).status_code == 422
    assert client.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "colour"}}).status_code == 422


@needs_test_database
def test_a_change_and_a_sweep_are_recorded_by_their_words_and_the_pick_never_every_row(recording, fake_tools):
    previewed = recording.post(CHANGES, json={"repair": example(), "change": {"action": "set", "quantity": "bondline", "value": 0.15}})
    run = recording.get(f"/v1/runs/{previewed.json()['run_id']}").json()
    assert run["endpoint"] == CHANGES and run["status"] == "solved" and run["response"]["words"] == previewed.json()["words"]
    assert set(run["response"]) == {"change", "words", "before", "after"}
    swept = recording.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "step_length", "start": 3, "end": 25, "load": 230}})
    run = recording.get(f"/v1/runs/{swept.json()['run_id']}").json()
    assert run["endpoint"] == SWEEPS and run["response"]["rows"] == 24 and run["response"]["pick"]["value"] == 4.0
    assert run["response"]["check"]["holds"] is True and run["response"]["words"] == swept.json()["words"]
    refused = recording.post(SWEEPS, json={"repair": example(), "sweep": {"quantity": "patch_overlap"}})
    assert recording.get(f"/v1/runs/{refused.headers['X-Anisotropy-Run-Id']}").json()["status"] == "rejected"


def test_the_chats_tests_answers_are_what_the_script_writes_and_what_the_api_answers():
    spec = importlib.util.spec_from_file_location("repair_choices", ROOT / "scripts" / "repair-choices.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hint = "run: uv run --project fea python scripts/repair-choices.py --solve"
    for name, change in module.CHANGES.items():
        kept = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert close(kept, json.loads(json.dumps(module.change(name)))), hint
        sent = client.post(CHANGES, json={"repair": example(), "change": change}).json()
        assert close({key: sent[key] for key in kept if key != "run_id"}, {key: kept[key] for key in kept if key != "run_id"}), "the browser test's preview is the API's"
    kept = json.loads((FIXTURES / "example-sweep.json").read_text(encoding="utf-8"))
    assert close(kept, json.loads(json.dumps(module.sweep()))), hint
    sent = client.post(SWEEPS, json={"repair": example(), "sweep": module.SWEEP, "confirm": False}).json()
    assert sent["check"] is None and close({key: sent[key] for key in kept if key != "run_id"}, {key: kept[key] for key in kept if key != "run_id"}), \
        "the browser test's sweep is the API's"
    checked = json.loads((FIXTURES / "example-sweep-check.json").read_text(encoding="utf-8"))
    assert checked["state"] == "solved" and checked["holds"] is True and kept["rows"][kept["pick"]]["value"] == 4.0


@pytest.mark.skipif(not FEA_VENV.is_dir() or shutil.which("ccx") is None, reason="the fea environment or CalculiX (ccx) is not installed here")
def test_the_examples_pick_is_solved_by_the_fea_package_and_held_by_its_slice():
    answer = client.post(SWEEPS, json={"toml": EXAMPLE.read_text(encoding="utf-8"), "sweep": {"quantity": "step_length", "start": 3, "end": 25, "load": 230}})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    check = body["check"]
    assert body["rows"][body["pick"]]["value"] == 4.0 and check["state"] == "solved" and check["first"]["what"] == "adhesive"
    assert check["holds"] is (check["first"]["load"] >= 230.0) and check["elastic_limit_load"] == pytest.approx(check["first"]["load"])
    solved = client.post(SOLVE, json={"repair": body["picked"]}).json()["report"]
    assert check["peak_shear"]["value"] == pytest.approx(solved["bond"]["peak_shear"]["value"], rel=1e-9), "the check is the pick's own solve"
