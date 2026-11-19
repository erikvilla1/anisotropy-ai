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


def test_the_wing_file_the_page_saves_reads_back_as_the_example():
    """tests/fixtures/wing/example-saved.toml is what the page's writer (lib/wingToml) makes of the example, checked by
    tests/wing.test.ts; the engine reads it as the same description, so a saved wing opens as it was."""
    saved = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wing" / "example-saved.toml"
    assert tomllib.loads(saved.read_text(encoding="utf-8")) == example()
    assert client.post(ENDPOINT, json={"toml": saved.read_text(encoding="utf-8")}).status_code == 200
