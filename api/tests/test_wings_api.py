"""The wing workspace's endpoint (ADR-0118): a wing description, as a JSON object or as a wing file's text, worked by the engine's
hand calculation (ADR-0115), the results in the file's units and what the page draws. The engine's own tests check the numbers;
these check that the API reads the description by the engine's rules, passes the engine's results on unchanged, refuses what the
engine refuses, and records a summary rather than the drawings."""

import json
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_engine.wing.analysis import analyze_wing
from anisotropy_engine.wing.wing_file import wing_from_dict, wing_report
from anisotropy_api.main import app
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

ENDPOINT = "/v1/wings/analyze"
EXAMPLE = Path(__file__).resolve().parents[2] / "engine" / "examples" / "example-wing.toml"
client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing is recorded here


def example() -> dict:
    return tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_the_example_wing_file_is_worked_and_its_results_are_the_engines():
    answer = client.post(ENDPOINT, json={"toml": EXAMPLE.read_text(encoding="utf-8")})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["wing"] == example(), "the description as the engine read it, so the page can fill its tabs from a file"
    wing, envelope = wing_from_dict(example())
    expected = wing_report(analyze_wing(wing, envelope), "SI", "m/s")
    report = body["report"]
    assert report["governing"] == expected["governing"] and report["passes"] == expected["passes"]
    assert report["design"] == pytest.approx(expected["design"])
    assert len(report["cases"]) == len(expected["cases"]) == 34 and report["not_run"] == []
    assert report["cases"][5]["checks"]["skin plies"] == pytest.approx(expected["cases"][5]["checks"]["skin plies"])


def test_the_page_gets_the_section_the_ribs_and_every_cases_margins_along_the_span():
    views = client.post(ENDPOINT, json={"wing": example()}).json()["views"]
    assert views["half_span"] == 2.0 and views["chord"] == 0.45 and views["ribs"] == pytest.approx([0.0, 0.5, 1.0, 1.5, 2.0])
    assert [w["name"] for w in views["walls"]] == ["upper skin", "lower skin", "front web", "rear web"]
    assert views["spars"] == pytest.approx([0.1125, 0.2925])
    assert views["airfoil"]["x"][0] == 0.0 and views["airfoil"]["x"][-1] == pytest.approx(0.45)
    assert len(views["cases"]) == 34 and len(views["stations"]) == 51
    case = views["cases"][0]
    assert set(case["margins"]) == {"skin plies", "spar plies", "skin buckling", "web buckling"}
    assert all(len(values) == 51 for values in case["margins"].values())
    assert [len(w["shear_flow"]) for w in case["root"]] == [len(w["x"]) for w in views["walls"]]


def test_the_json_form_and_the_file_text_give_the_same_answer():
    from_text = client.post(ENDPOINT, json={"toml": EXAMPLE.read_text(encoding="utf-8")}).json()
    from_json = client.post(ENDPOINT, json={"wing": example()}).json()
    assert from_text["report"]["governing"] == from_json["report"]["governing"]
    assert from_text["views"] == from_json["views"]


def test_a_wing_with_missing_speeds_runs_the_cases_it_can_and_lists_what_the_others_need():
    wing = example()
    del wing["envelope"]["speeds"]["cruise"], wing["envelope"]["gust"]
    report = client.post(ENDPOINT, json={"wing": wing}).json()["report"]
    needs = {(n["number"], n["needs"]) for n in report["not_run"]}
    assert any(number == 3 and "cruise" in need for number, need in needs)
    assert 0 < len(report["cases"]) < 34


@pytest.mark.parametrize(("change", "says"), [
    (lambda w: w["geometry"].update(sweep=5.0), "unknown keys sweep"),
    (lambda w: w["geometry"].pop("chord"), "missing chord"),
    (lambda w: w["geometry"].update(front_spar=0.7), "0 < front < rear < 1"),
    (lambda w: w["material"].update(library="no-such-material"), "no-such-material"),
    (lambda w: w["skin"].update(half_stack="0/45"), "half_stack"),
    (lambda w: w.update(units="imperial"), "units must be one of"),
])
def test_the_engine_refuses_a_wrong_description_by_name(change, says):
    wing = example()
    change(wing)
    answer = client.post(ENDPOINT, json={"wing": wing})
    assert answer.status_code == 422 and says in answer.json()["detail"], answer.text


def test_a_request_gives_exactly_one_form_and_bad_text_is_refused():
    assert client.post(ENDPOINT, json={}).status_code == 422
    assert client.post(ENDPOINT, json={"wing": example(), "toml": "title = 'x'"}).status_code == 422
    answer = client.post(ENDPOINT, json={"toml": "title = "})
    assert answer.status_code == 422 and answer.json()["detail"]


@pytest.fixture
def recording(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        yield recorded


@needs_test_database
def test_a_wing_is_recorded_by_its_description_and_summary_never_the_drawings(recording):
    answer = recording.post(ENDPOINT, json={"wing": example()})
    assert answer.status_code == 200 and answer.json()["run_id"]
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    assert run["actor"] == "studio" and run["endpoint"] == ENDPOINT and run["status"] == "solved"
    assert run["inputs"]["wing"] == example()
    response = run["response"]
    assert response["governing"] == answer.json()["report"]["governing"] and response["cases_run"] == 34 and response["cases_not_run"] == 0
    assert "walls" not in json.dumps(response) and "cases" not in response, "never the drawings or the per-case tables"
    refused = recording.post(ENDPOINT, json={"wing": {**example(), "units": "imperial"}})
    run = recording.get(f"/v1/runs/{refused.headers['X-Anisotropy-Run-Id']}").json()
    assert run["status"] == "rejected" and "units must be one of" in run["error"]


def close(a, b, rel=1e-3) -> bool:
    """The same JSON value, numbers within `rel` of each other: a computed float may differ in its last digits from machine to
    machine, and a value drawn to four digits may round the other way."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], rel) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return a == pytest.approx(b, rel=rel, abs=1e-9)
    return a == b


def test_the_pages_wing_choices_and_the_browser_tests_answer_are_what_the_script_writes():
    import importlib.util
    script = Path(__file__).resolve().parents[2] / "scripts" / "wing-choices.py"
    spec = importlib.util.spec_from_file_location("wing_choices", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hint = "run: uv run --project engine python scripts/wing-choices.py"
    assert module.OUT.read_text(encoding="utf-8") == module.text(), hint
    assert module.choices()["example"] == example()
    kept = json.loads(module.ANSWER.read_text(encoding="utf-8"))
    assert close(kept, module.answer()), hint
    sent = client.post(ENDPOINT, json={"wing": example()}).json()
    sent["report"]["seconds"] = kept["report"]["seconds"]
    assert close({key: sent[key] for key in ("wing", "report", "views")}, {key: kept[key] for key in ("wing", "report", "views")}), \
        "the browser test's answer is the API's"
    caps = json.loads(module.CAPS_ANSWER.read_text(encoding="utf-8"))  # the example with spar caps and a cap zone (ADR-0125)
    assert close(caps, module.answer(caps=True)), hint
    sent = client.post(ENDPOINT, json={"wing": module.with_caps(example())}).json()
    sent["report"]["seconds"] = caps["report"]["seconds"]
    assert close({key: sent[key] for key in ("wing", "report", "views")}, {key: caps[key] for key in ("wing", "report", "views")}), \
        "the browser test's answer with caps is the API's"
    previewed = json.loads(module.CAPS_PREVIEW.read_text(encoding="utf-8"))  # the founder's change on those caps (ADR-0128)
    assert close(previewed, module.preview()), hint
    sent = client.post("/v1/wings/changes", json={"wing": module.without_zones(example()), "change": module.FOUNDERS.model_dump()}).json()
    assert close({key: sent[key] for key in previewed if key != "run_id"}, {key: previewed[key] for key in previewed if key != "run_id"}), \
        "the browser test's preview is the API's"
    assert close(previewed["wing"], caps["wing"]), "the change previewed gives the zone the caps answer holds"
    skin = json.loads(module.SKIN_PREVIEW.read_text(encoding="utf-8"))  # the MCP server's stand-in answer
    assert close(skin, module.preview(skin=True)), hint


def test_the_wing_file_the_page_saves_reads_back_as_the_example():
    """tests/fixtures/wing/example-saved.toml is what the page's writer (lib/wingToml) makes of the example, checked by
    tests/wing.test.ts; the engine reads it as the same description, so a saved wing opens as it was."""
    saved = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wing" / "example-saved.toml"
    assert tomllib.loads(saved.read_text(encoding="utf-8")) == example()
    assert client.post(ENDPOINT, json={"toml": saved.read_text(encoding="utf-8")}).status_code == 200


# ---- the shape for a CAD program (ADR-0116, ADR-0118)

SHAPE = "/v1/wings/shape"
FAKE_SHAPE = '''
import json, sys
wing, step, parts = sys.argv[1], sys.argv[2], sys.argv[4]
data = json.load(open(wing, encoding="utf-8"))
mode = data["title"]
if mode == "refuse":
    print("warning: a uv line first", file=sys.stderr)
    print("The front spar web has no height", file=sys.stderr)
    sys.exit(2)
if mode == "crash":
    print("Traceback (most recent call last): secret/path.py", file=sys.stderr)
    sys.exit(1)
open(step, "w", encoding="ascii").write("ISO-10303-21;\\nEND-ISO-10303-21;\\n")
json.dump({"wing": mode, "units": {"thickness": "mm", "area": "m^2", "mass": "kg", "step": "mm"},
           "parts": [{"name": "Upper skin", "layup": "skin", "thickness": 7.46, "area": 0.87, "mass": 2.2}], "mass": 2.2},
          open(parts, "w", encoding="utf-8"))
'''


def fake_shape(monkeypatch, tmp_path):
    import sys
    import anisotropy_api.main as main_module
    script = tmp_path / "fake_shape.py"
    script.write_text(FAKE_SHAPE, encoding="utf-8")
    monkeypatch.setattr(main_module, "wing_shape_command", lambda: [sys.executable, str(script)])


def test_the_shape_comes_back_as_the_step_files_text_and_the_part_table(monkeypatch, tmp_path):
    fake_shape(monkeypatch, tmp_path)
    answer = client.post(SHAPE, json={"wing": example()})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["step"].startswith("ISO-10303-21;")
    assert body["parts"]["parts"][0]["name"] == "Upper skin" and body["parts"]["units"]["step"] == "mm"


def test_a_wing_the_engine_refuses_is_refused_before_the_shape_is_built(monkeypatch, tmp_path):
    fake_shape(monkeypatch, tmp_path)
    wing = example()
    wing["geometry"]["chord"] = -1
    answer = client.post(SHAPE, json={"wing": wing})
    assert answer.status_code == 422
    assert answer.json()["detail"] == client.post(ENDPOINT, json={"wing": wing}).json()["detail"]  # the same words as the calculation's


def test_the_shapes_own_refusal_is_its_last_line_and_a_crash_says_nothing_of_the_tool(monkeypatch, tmp_path):
    fake_shape(monkeypatch, tmp_path)
    refused = client.post(SHAPE, json={"wing": example() | {"title": "refuse"}})
    assert refused.status_code == 422 and refused.json()["detail"] == "The front spar web has no height"
    crashed = client.post(SHAPE, json={"wing": example() | {"title": "crash"}})
    assert crashed.status_code == 503 and crashed.json()["detail"] == "The shape could not be built"


def test_without_the_shape_builder_the_answer_is_unavailable(monkeypatch):
    import anisotropy_api.main as main_module
    monkeypatch.setattr(main_module, "wing_shape_command", lambda: None)
    assert client.post(SHAPE, json={"wing": example()}).status_code == 503


FEA_GMSH = list((Path(__file__).resolve().parents[2] / "fea" / ".venv").glob("lib/python*/site-packages/gmsh*"))


@pytest.mark.skipif(not FEA_GMSH, reason="the fea environment with Gmsh is not installed here (uv sync --project fea --extra mesh)")
def test_the_example_wings_shape_is_built_by_the_fea_package():
    answer = client.post(SHAPE, json={"toml": EXAMPLE.read_text(encoding="utf-8")})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["step"].startswith("ISO-10303-21;") and "PRODUCT('Front spar'" in body["step"]
    assert [p["name"] for p in body["parts"]["parts"]][:4] == ["Upper skin", "Lower skin", "Front spar", "Rear spar"]
    assert body["parts"]["wing"] == "Example straight wing" and body["parts"]["mass"] > 0


# A change of plies previewed (ADR-0128): the engine's preview passed on, the wing sent never kept, a change the wing cannot take refused in
# the engine's words, and the record holding the change and both summaries, not the wing.
CHANGES = "/v1/wings/changes"
FOUNDERS = {"action": "add_plies", "part": "spar_caps", "angle": 0, "count": 2, "start": 0, "end": 0.4}  # "Add 2 0 plies to the spar caps from the root to 40% span"


def capped() -> dict:
    return {**example(), "spar_caps": {"front_width": 0.045, "rear_width": 0.045, "half_stack": [0, 0, 45, -45, 0]}}


def test_a_change_is_previewed_as_the_engine_previews_it_and_the_wing_sent_is_unchanged():
    from anisotropy_engine.wing.changes import PlyChange, preview_change
    sent = capped()
    answer = client.post(CHANGES, json={"wing": sent, "change": FOUNDERS})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    expected = preview_change(capped(), PlyChange(**FOUNDERS))
    assert body["words"] == expected["words"] and body["wing"] == expected["wing"] and body["rules"] == expected["rules"]
    assert close(body["before"], expected["before"]) and close(body["after"], expected["after"])
    assert body["wing"]["spar_caps"]["zones"] == [{"start": 0.0, "end": 0.4, "half_stack": [0.0, 0.0, 0.0, 45.0, -45.0, 0.0]}]
    assert sent == capped(), "the wing sent is never changed"
    assert body["after"]["lowest"]["skin plies"] > body["before"]["lowest"]["skin plies"] and body["after"]["mass"] > body["before"]["mass"]
    from_text = client.post(CHANGES, json={"toml": EXAMPLE.read_text(encoding="utf-8"), "change": {**FOUNDERS, "part": "skin", "end": 1}})
    assert from_text.status_code == 200 and from_text.json()["wing"]["skin"]["half_stack"] == [0.0, 0.0, 45.0, -45.0, 0.0]


@pytest.mark.parametrize(("wing", "change", "says"), [
    (example, FOUNDERS, "The wing has no spar caps: add them on the Layup step first"),
    (capped, {**FOUNDERS, "action": "remove_plies", "angle": 90}, "has 0 plies at 90°"),
])
def test_a_change_the_wing_cannot_take_is_refused_in_the_engines_words(wing, change, says):
    refused = client.post(CHANGES, json={"wing": wing(), "change": change})
    assert refused.status_code == 422 and says in refused.json()["detail"]


@pytest.mark.parametrize("change", [
    {**FOUNDERS, "count": 3}, {**FOUNDERS, "start": 0.5, "end": 0.4}, {**FOUNDERS, "part": "rib"}, {**FOUNDERS, "count": "2"},
    {**FOUNDERS, "where": "both caps"}, {k: v for k, v in FOUNDERS.items() if k != "angle"},
])
def test_a_change_out_of_its_shape_is_refused_before_the_engine_works(change):
    assert client.post(CHANGES, json={"wing": capped(), "change": change}).status_code == 422


@needs_test_database
def test_a_change_is_recorded_by_the_change_and_its_summaries_never_the_wing_it_gives(recording):
    answer = recording.post(CHANGES, json={"wing": capped(), "change": FOUNDERS})
    assert answer.status_code == 200 and answer.json()["run_id"]
    run = recording.get(f"/v1/runs/{answer.json()['run_id']}").json()
    assert run["endpoint"] == CHANGES and run["status"] == "solved" and run["inputs"]["change"] == FOUNDERS
    assert set(run["response"]) == {"change", "words", "before", "after"} and run["response"]["words"] == answer.json()["words"]


def test_a_wings_question_searches_its_theory_and_the_reference_pages_and_a_coupons_does_not():
    asked = "what ply drop ratio should I use?"
    wing = client.post("/v1/workspace/theory-sections", json={"question": asked, "about": "wing"}).json()["sections"]
    assert wing[0]["id"] == "rules:ply-drops-how-long-the-run-out-is" and "<!-- also" not in wing[0]["text"]
    coupon = client.post("/v1/workspace/theory-sections", json={"question": asked}).json()["sections"]
    assert not any(s["id"].startswith(("rules:", "tests:", "allowables:")) for s in coupon)
    assert client.post("/v1/workspace/theory-sections", json={"question": asked, "about": "plate"}).status_code == 422
