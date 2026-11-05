"""The response endpoint describes the stack and evaluates first-ply failure under the request's loads (ADR-0059)."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from anisotropy_engine.failure import first_ply_failure
from anisotropy_engine.laminate import Ply
from anisotropy_engine.library import library_material
from anisotropy_engine.response import Loads
from anisotropy_api.main import app

client = TestClient(app, headers={"X-Anisotropy-Actor": "test"})  # no lifespan: nothing is recorded here
ENDPOINT = "/v1/laminates/response"
EXAMPLE = json.loads((Path(__file__).parents[1] / "examples/zero-degree-tension.json").read_text())
ZERO_LOADS = dict(Nx=0.0, Ny=0.0, Nxy=0.0, Mx=0.0, My=0.0, Mxy=0.0)


def quasi_isotropic(material: dict, loads: dict | None = None) -> dict:
    return {**EXAMPLE, "material": material, "loads": loads or ZERO_LOADS,
            "plies": [{"angle_deg": a, "thickness_m": 0.125e-3} for a in (0, 45, -45, 90, 90, -45, 45, 0)]}


def test_the_typed_example_is_described_and_its_areal_mass_and_failure_are_left_out_with_the_reasons():
    response = client.post(ENDPOINT, json=EXAMPLE)
    assert response.status_code == 200, response.text
    result = response.json()
    summary = result["summary"]
    assert summary["ply_count"] == 1 and summary["total_thickness_m"] == EXAMPLE["plies"][0]["thickness_m"]
    assert summary["symmetric"] and summary["balanced"] and not summary["antisymmetric"]
    assert summary["kind"] == "unidirectional"
    assert summary["coupling"] == {"extension_shear": False, "extension_bending": False, "bending_twisting": False}
    assert summary["relative_tolerance"] == 1e-9
    assert summary["areal_mass_kg_per_m2"] is None and summary["areal_mass_missing"] == "plies [1] have no density"
    failure = result["first_ply_failure"]
    assert failure == {"evaluated": False, "reason": "plies [1] have no strengths", "criteria": [], "not_computed": []}


def test_a_library_stack_gets_its_areal_mass_from_the_cited_density_and_its_provenance_carries_it():
    material = library_material("as4-3501")  # Table A.4: density 1600 kg/m^3, Vf 63 %
    response = client.post(ENDPOINT, json=quasi_isotropic({"library_id": "as4-3501"}))
    assert response.status_code == 200, response.text
    result = response.json()
    summary = result["summary"]
    assert summary["kind"] == "quasi-isotropic" and summary["symmetric"] and summary["balanced"]
    assert summary["coupling"] == {"extension_shear": False, "extension_bending": False, "bending_twisting": True}
    assert summary["total_thickness_m"] == pytest.approx(1.0e-3, rel=1e-15)
    assert summary["areal_mass_kg_per_m2"] == pytest.approx(material.density_kg_per_m3 * 1.0e-3, rel=1e-15)
    assert summary["areal_mass_missing"] is None
    provenance = result["material_provenance"]
    assert provenance["density_kg_per_m3"] == 1600.0 and provenance["fiber_volume_fraction"] == pytest.approx(0.63)
    roles = {v["role"]: v for v in provenance["values"]}
    assert roles["density"]["source_value"] == 1.6 and roles["density"]["source_unit"] == "g/cm³"
    assert roles["Vf"]["key"] == "Vf" and roles["Vf"]["unit"] == "—"


def test_zero_loads_give_no_failure_and_a_load_gives_the_criteria_the_dataset_supports():
    unloaded = client.post(ENDPOINT, json=quasi_isotropic({"library_id": "im7-8552"})).json()
    assert unloaded["first_ply_failure"] == {"evaluated": False, "reason": "no loads applied", "criteria": [], "not_computed": []}
    loads = {**ZERO_LOADS, "Nx": 25000.0}
    response = client.post(ENDPOINT, json=quasi_isotropic({"library_id": "im7-8552"}, loads))
    assert response.status_code == 200, response.text
    failure = response.json()["first_ply_failure"]
    assert failure["evaluated"] and failure["reason"] is None
    assert [c["criterion"] for c in failure["criteria"]] == ["max_stress", "tsai_hill"]
    assert [n["criterion"] for n in failure["not_computed"]] == ["max_strain", "tsai_wu"]
    assert "no strain limits" in failure["not_computed"][0]["reason"] and "f12_star" in failure["not_computed"][1]["reason"]
    material = library_material("im7-8552")
    plies = [Ply(material=material.lamina, angle_deg=a, thickness_m=0.125e-3) for a in (0, 45, -45, 90, 90, -45, 45, 0)]
    for item in failure["criteria"]:
        direct = first_ply_failure(plies, Loads(**loads), item["criterion"])
        assert item["strength_ratio"] == direct.strength_ratio
        assert item["ply"] == direct.governing.ply_index + 1 and item["angle_deg"] == direct.governing.angle_deg
        assert item["z_m"] == direct.governing.z_m and item["mode"] == direct.governing.mode
        assert item["face"] in ("bottom", "top")
        np.testing.assert_array_equal(list(item["failure_loads"].values()), direct.failure_loads.as_vector())
        assert item["failure_loads"]["Nx"] == pytest.approx(direct.strength_ratio * 25000.0)


def test_symmetry_and_balance_are_judged_from_the_plies_and_the_kind_from_a():
    typed = EXAMPLE["material"]
    angle_ply = {**EXAMPLE, "material": typed, "plies": [{"angle_deg": a, "thickness_m": 0.25e-3} for a in (45, -45, -45, 45)]}
    summary = client.post(ENDPOINT, json=angle_ply).json()["summary"]
    assert summary["symmetric"] and summary["balanced"] and not summary["antisymmetric"] and summary["kind"] == "angle-ply"
    assert summary["coupling"] == {"extension_shear": False, "extension_bending": False, "bending_twisting": True}
    antisymmetric = {**angle_ply, "plies": [{"angle_deg": a, "thickness_m": 0.25e-3} for a in (45, -45)]}
    summary = client.post(ENDPOINT, json=antisymmetric).json()["summary"]
    assert not summary["symmetric"] and summary["antisymmetric"] and summary["balanced"]
    assert summary["coupling"] == {"extension_shear": False, "extension_bending": True, "bending_twisting": False}
    general = {**angle_ply, "plies": [{"angle_deg": a, "thickness_m": 0.25e-3} for a in (0, 30)]}
    summary = client.post(ENDPOINT, json=general).json()["summary"]
    assert summary == {**summary, "symmetric": False, "antisymmetric": False, "balanced": False, "kind": "general",
                       "coupling": {"extension_shear": True, "extension_bending": True, "bending_twisting": True}}


def test_the_older_fields_of_the_response_are_unchanged_by_the_additions():
    response = client.post(ENDPOINT, json=EXAMPLE).json()
    assert set(response) == {"run_id", "engine_version", "inputs", "A_N_per_m", "B_N", "D_N_m", "midplane_strain", "curvature_per_m",
                             "material_provenance", "summary", "first_ply_failure"}
    assert response["inputs"] == EXAMPLE and response["material_provenance"] is None
    detail = client.get("/v1/materials/im7-8552", params={"dataset": "nasa-tm-20230001560-im7-8552-rt-measured-v1"}).json()
    assert detail["density_kg_per_m3"] is None and detail["fiber_volume_fraction"] is None  # the record states neither
    assert any(item.startswith("density: none of") for item in detail["not_provided"])
