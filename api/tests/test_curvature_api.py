"""Prescribed-curvature HTTP checks; success cases use the actual engine."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from anisotropy_api.main import app


client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})  # no lifespan: nothing is recorded here
ENDPOINT = "/v1/laminates/prescribed-curvature"


@pytest.fixture
def problem():
    return json.loads((Path(__file__).parents[1] / "examples/flat-cross-ply.json").read_text())


def test_flat_example_has_analytical_moments_and_checkable_verification(problem):
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["inputs"] == problem
    assert result["analysis_type"] == "prescribed_curvature"
    assert result["engine_version"]
    np.testing.assert_allclose(result["moments_N_m_per_m"], [-0.36, -0.18, 0], atol=1e-14)
    np.testing.assert_allclose(result["midplane_strain"], [2e-4, -1e-4, 5e-4], atol=1e-15)
    check = result["verification"]
    assert check["passed"] is True
    assert np.all(np.abs(check["strain_residual"]) <= check["strain_allowed_error"])
    assert np.all(np.abs(check["curvature_residual_per_m"]) <= check["curvature_allowed_error_per_m"])
    # Also traverse the separate, unchanged forward HTTP operation.
    forward = client.post("/v1/laminates/response", json={
        "unit_system": problem["unit_system"], "material": problem["material"], "plies": problem["plies"],
        "loads": {**problem["forces"], **dict(zip(["Mx", "My", "Mxy"], result["moments_N_m_per_m"]))},
    })
    assert forward.status_code == 200, forward.text
    np.testing.assert_allclose(forward.json()["curvature_per_m"], [0, 0, 0], atol=1e-12)


def test_nonzero_curvature_is_supported_with_explicit_units(problem):
    problem["plies"] = problem["plies"][:1]
    problem["prescribed_curvature_per_m"] = [0.2, -0.1, 0.3]
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 200, response.text
    result = response.json()
    np.testing.assert_allclose(result["moments_N_m_per_m"], [0.016, -0.002, 0.0012], atol=1e-15)
    np.testing.assert_allclose(result["verification"]["recovered_curvature_per_m"], [0.2, -0.1, 0.3], atol=1e-12)


@pytest.mark.parametrize("field", ["unit_system", "stacking_order", "material", "plies", "forces", "prescribed_curvature_per_m"])
def test_problem_fields_are_required(problem, field):
    del problem[field]
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]


@pytest.mark.parametrize("component", ["Nx", "Ny", "Nxy"])
def test_force_components_cannot_be_implicitly_zero(problem, component):
    del problem["forces"][component]
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "forces", component]


@pytest.mark.parametrize("path,value", [
    (("unit_system",), "SI"), (("stacking_order",), "top_to_bottom"),
    (("prescribed_curvature_per_m",), [0, 0]), (("prescribed_curvature_per_m",), [0, 0, 0, 0]),
    (("prescribed_curvature_per_m",), [True, 0, 0]), (("prescribed_curvature_per_m",), ["0", 0, 0]),
    (("prescribed_curvature_per_m",), [None, 0, 0]), (("prescribed_curvature_per_m",), None),
    (("forces", "Nx"), "6000"), (("forces", "Nx"), False),
    (("forces", "Mx"), 0), (("forces", "Mx"), None), (("moments",), [0, 0, 0]),
    (("plies",), []), (("plies", 0, "thickness_m"), 0),
    (("material", "nu12"), 10), (("material", "source_reference"), "  "),
])
def test_malformed_inputs_and_overconstraints_are_rejected(problem, path, value):
    target = problem
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"][0] == "body"


@pytest.mark.parametrize("field", ["forces", "prescribed_curvature_per_m"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_produces_serializable_field_errors(problem, field, value):
    problem[field]["Nx" if field == "forces" else 0] = value
    response = client.post(ENDPOINT, content=json.dumps(problem), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][:2] == ["body", field]


@pytest.mark.parametrize("thickness", [1e-200, 1e200])
def test_numerical_failure_is_a_client_error(problem, thickness):
    problem["plies"][0]["thickness_m"] = thickness
    problem["plies"] = problem["plies"][:1]
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422
    assert "verified" in response.json()["detail"]


def test_failed_forward_check_never_returns_success(problem, monkeypatch):
    monkeypatch.setattr("anisotropy_engine.response.midplane_response", lambda *_: (np.ones(3), np.ones(3)))
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422
    assert "verification" not in response.json()  # No successful result envelope.


def test_openapi_exposes_unknown_moments_only_in_output_and_local_cors(problem):
    schema = client.get("/openapi.json").json()
    request = schema["components"]["schemas"]["PrescribedCurvatureRequest"]
    assert request["additionalProperties"] is False
    assert set(request["required"]) == set(problem)
    assert "moments_N_m_per_m" in schema["components"]["schemas"]["PrescribedCurvatureResponse"]["properties"]
    assert ENDPOINT in schema["paths"]
    response = client.post(ENDPOINT, json=problem, headers={"Origin": "http://localhost:3001"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
