"""The case endpoint: whole problems over HTTP, compared with the engine's own case runner."""

import json
import math
import tomllib
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from anisotropy_engine.cases import engine_results, load_case
from anisotropy_api.main import app

client = TestClient(app)  # no lifespan: nothing is recorded here; test_runs_api.py covers recording
ENDPOINT = "/v1/cases/solve"
HEADERS = {"X-Anisotropy-Actor": "test"}
CASES = Path(__file__).parents[2] / "engine" / "validation" / "cases"


def case_text(name: str) -> str:
    return (CASES / f"{name}.toml").read_text(encoding="utf-8")


def flatten(value):
    return np.asarray(value, dtype=float).ravel()


@pytest.mark.parametrize("name", [
    "constructed-cross-ply-cooling-first-ply-failure",  # loads, temperature change, fixed and variable failure, Tsai-Wu
    "constructed-mixed-angle-lamina",  # mixed conditions
    "constructed-two-material-laminate-cooling",  # several materials
    "constructed-cross-ply-plate-buckling",  # plate buckling
    "constructed-max-strain-biaxial-lamina",  # every failure criterion
])
def test_toml_cases_return_the_case_runner_results_and_agree_with_their_keys(name):
    response = client.post(ENDPOINT, headers=HEADERS, json={"toml": case_text(name)})
    assert response.status_code == 200, response.text
    body = response.json()
    case = load_case(CASES / f"{name}.toml")
    expected = engine_results(case)
    assert body["units"] == case["units"] and body["engine_version"] == "0.1.0"
    assert set(body["results"]) == set(expected)
    for key, (value, _scale) in expected.items():
        got = flatten(body["results"][key])
        want = flatten(value)
        finite = np.isfinite(want)
        np.testing.assert_allclose(got[finite], want[finite], rtol=1e-12, atol=0)
    assert body["comparison"] and all(c["agrees"] for c in body["comparison"]) and body["problems"] == []


def test_json_case_with_a_library_material_reports_provenance_and_criteria():
    case = tomllib.loads(case_text("library-im7-8552-axial-check"))
    case["f12_star"] = -0.5
    response = client.post(ENDPOINT, headers=HEADERS, json={"case": case})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["materials"]["material"]["dataset_id"] == "ncamp-im7-8552-2019-rtd-measured-v1"
    assert body["criteria"] == ["max_stress", "tsai_hill", "tsai_wu"]  # no strain limits, so no max_strain
    assert body["results"]["fpf_ratio_max_stress"] == pytest.approx(371.08e3 * 6.894757293168e-3 / 100, rel=1e-6)
    assert body["results"]["Ex"] == pytest.approx(162.09574396238816)


def test_the_example_file_solves():
    example = json.loads((Path(__file__).parents[1] / "examples/case-library-axial-check.json").read_text())
    response = client.post(ENDPOINT, headers=HEADERS, json=example)
    assert response.status_code == 200, response.text
    assert all(c["agrees"] for c in response.json()["comparison"])


def test_engine_validation_messages_come_back_as_422():
    case = tomllib.loads(case_text("constructed-cross-ply-plate-buckling"))
    bad = {**case, "material": {**case["material"], "E9": 1.0}}
    response = client.post(ENDPOINT, headers=HEADERS, json={"case": bad})
    assert response.status_code == 422 and "unknown fields ['E9']" in response.json()["detail"]
    unsymmetric = {**case, "laminate": {"layup": [0, 90], "ply_thickness": 0.25}}
    response = client.post(ENDPOINT, headers=HEADERS, json={"case": unsymmetric})
    assert response.status_code == 422 and "midplane-symmetric" in response.json()["detail"]
    response = client.post(ENDPOINT, headers=HEADERS, json={"toml": "units = 'SI'\\n[material"})
    assert response.status_code == 422 and response.json()["detail"].startswith("toml:")


def test_exactly_one_of_case_or_toml():
    for body in ({}, {"case": {}, "toml": "units = 'SI'"}):
        response = client.post(ENDPOINT, headers=HEADERS, json=body)
        assert response.status_code == 422, body
    response = client.post(ENDPOINT, headers=HEADERS, json={"case": {}})
    assert response.status_code == 422 and "missing fields" in response.json()["detail"]


def test_unbounded_ratios_become_null_not_infinity():
    case = tomllib.loads(case_text("as4-zero-degree-axial-check"))
    body = client.post(ENDPOINT, headers=HEADERS, json={"case": case}).json()
    assert math.isfinite(body["results"]["fpf_ratio_max_stress"])
    assert "null" not in json.dumps(body["results"]["fpf_ratio_max_stress"])
