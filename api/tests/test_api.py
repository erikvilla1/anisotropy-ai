"""Exercise the actual HTTP contract and compare results to independent checks and the engine."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.response import Loads, midplane_response
from anisotropy_api.main import app


client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})  # no lifespan: nothing is recorded here
ENDPOINT = "/v1/laminates/response"


@pytest.fixture
def problem():
    return json.loads((Path(__file__).parents[1] / "examples/zero-degree-tension.json").read_text())


def test_zero_degree_example_matches_uniaxial_compliance(problem):
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 200, response.text
    result = response.json()
    # Independent analytical relation: sigma = Nx/h, eps_x = sigma/E1, eps_y = -nu12*eps_x.
    eps_x = 100e6 / 147e9
    np.testing.assert_allclose(result["midplane_strain"], [eps_x, -0.27 * eps_x, 0], atol=1e-15)
    np.testing.assert_allclose(result["curvature_per_m"], [0, 0, 0], atol=1e-12)
    assert result["inputs"] == problem
    assert result["engine_version"] == "0.1.0"


def test_unsymmetric_stack_and_mixed_loads_match_direct_engine_calls(problem):
    # Constructed inputs exercise coupling, shear and all six nonzero load components.
    problem["plies"] = [{"angle_deg": angle, "thickness_m": 0.00025} for angle in [0, 35, -20]]
    problem["loads"] = dict(Nx=25000, Ny=-2000, Nxy=800, Mx=2, My=-1, Mxy=0.5)
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 200, response.text
    result = response.json()
    material = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27)
    plies = [Ply(material=material, **ply) for ply in problem["plies"]]
    for key, expected in zip(["A_N_per_m", "B_N", "D_N_m"], abd_matrices(plies)):
        np.testing.assert_array_equal(result[key], expected)
    eps0, kappa = midplane_response(plies, Loads(**problem["loads"]))
    np.testing.assert_array_equal(result["midplane_strain"], eps0)
    np.testing.assert_array_equal(result["curvature_per_m"], kappa)


@pytest.mark.parametrize("component", ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"])
def test_each_load_component_is_required(problem, component):
    del problem["loads"][component]
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "loads", component]


@pytest.mark.parametrize("path,value", [
    (("unit_system",), "SI"),
    (("unit_system",), "US"),
    (("plies",), []),
    (("plies", 0, "thickness_m"), 0),
    (("plies", 0, "thickness_m"), -0.001),
    (("plies", 0, "angle_deg"), True),
    (("material", "E1_pa"), -1),
    (("material", "E1_pa"), "147e9"),
    (("material", "nu12"), 10),
    (("material", "nu12"), 1e200),
    (("material", "source_reference"), "   "),
    (("material", "extra_property"), 1),
    (("plies", 0, "hole_diameter_m"), 0.01),
    (("loads", "Nxx"), 100),
    (("loads", "Nx"), False),
    (("extra_option",), "ignored?"),
])
def test_invalid_or_unsupported_inputs_get_actionable_errors(problem, path, value):
    target = problem
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"][0] == "body"


@pytest.mark.parametrize("section,key", [(None, "unit_system"), ("material", "source_reference")])
def test_units_and_source_are_required(problem, section, key):
    del (problem[section] if section else problem)[key]
    assert client.post(ENDPOINT, json=problem).status_code == 422


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_input_is_rejected_without_breaking_error_serialization(problem, value):
    problem["loads"]["Nx"] = value
    response = client.post(ENDPOINT, content=json.dumps(problem), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "loads", "Nx"]


@pytest.mark.parametrize("thickness", [1e-200, 1e200])
def test_numerically_unsolvable_inputs_return_an_error(problem, thickness):
    problem["plies"][0]["thickness_m"] = thickness
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 422
    assert "solvable" in response.json()["detail"]


def test_openapi_describes_required_fields_and_response():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert ENDPOINT in schema["paths"]
    assert set(schema["components"]["schemas"]["LoadInput"]["required"]) == {"Nx", "Ny", "Nxy", "Mx", "My", "Mxy"}
    assert "AnalysisResponse" in schema["components"]["schemas"]
    assert client.get("/docs").status_code == 200


def test_explicit_zero_loads_produce_zero_deformation(problem):
    problem["loads"] = dict.fromkeys(problem["loads"], 0)
    response = client.post(ENDPOINT, json=problem)
    assert response.status_code == 200
    np.testing.assert_array_equal(response.json()["midplane_strain"], [0, 0, 0])
    np.testing.assert_array_equal(response.json()["curvature_per_m"], [0, 0, 0])


def test_malformed_json_gets_a_client_error():
    response = client.post(ENDPOINT, content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"])
def test_local_website_can_preflight_and_read_a_calculation(problem, origin):
    headers = {"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    preflight = client.options(ENDPOINT, headers=headers)
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    response = client.post(ENDPOINT, json=problem, headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers


def test_unapproved_browser_origin_fails_preflight():
    response = client.options(ENDPOINT, headers={"Origin": "https://unapproved.example", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
