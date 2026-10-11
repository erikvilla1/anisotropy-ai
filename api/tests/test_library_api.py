"""Library materials over HTTP: listing, detail, and analysis by dataset id with provenance."""

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from anisotropy_engine.library import library_material
from anisotropy_api.main import app

client = TestClient(app)
EXAMPLE = json.loads((Path(__file__).parents[1] / "examples/zero-degree-tension.json").read_text())


def test_the_library_lists_every_dataset_and_whether_it_can_be_analyzed():
    response = client.get("/v1/materials")
    assert response.status_code == 200
    rows = response.json()
    assert len({r["material_id"] for r in rows}) == 25
    im7 = [r for r in rows if r["material_id"] == "im7-8552"]
    assert [r["dataset_id"] for r in im7] == ["ncamp-im7-8552-2019-rtd-measured-v1", "nasa-tm-20230001560-im7-8552-rt-measured-v1"]
    assert im7[0]["primary"] and not im7[1]["primary"] and all(r["elastic_inputs"] for r in im7)
    assert not next(r for r in rows if r["material_id"] == "t650-35-976")["elastic_inputs"]


def test_material_detail_returns_si_values_with_their_pages():
    response = client.get("/v1/materials/im7-8552")
    assert response.status_code == 200
    detail = response.json()
    expected = library_material("im7-8552")
    assert detail["dataset_id"] == expected.dataset_id
    assert detail["E1_pa"] == expected.lamina.E1 and detail["ply_thickness_m"] == expected.ply_thickness_m
    e1 = next(v for v in detail["values"] if v["role"] == "E1")
    assert e1 == {"role": "E1", "key": "E1t", "value": expected.lamina.E1, "unit": "Pa", "source_value": 23.51,
                  "source_unit": "Msi", "basis": "Measured mean", "page": 30, "printed_page": None,
                  "reference_url": expected.value("E1").reference_url}
    nasa = client.get("/v1/materials/im7-8552", params={"dataset": "nasa-tm-20230001560-im7-8552-rt-measured-v1"}).json()
    assert nasa["citation"].startswith("Experimental Tests to Characterize")
    assert client.get("/v1/materials/nothing").status_code == 404
    refused = client.get("/v1/materials/t650-35-976")
    assert refused.status_code == 422 and "no elastic input set" in refused.json()["detail"]


def test_analysis_by_library_id_matches_explicit_constants_and_reports_provenance():
    material = library_material("im7-8552")
    by_library = {**EXAMPLE, "material": {"library_id": "im7-8552"}}
    explicit = {**EXAMPLE, "material": {"E1_pa": material.lamina.E1, "E2_pa": material.lamina.E2,
                                        "G12_pa": material.lamina.G12, "nu12": material.lamina.nu12,
                                        "source_reference": "typed"}}
    a, b = client.post("/v1/laminates/response", json=by_library), client.post("/v1/laminates/response", json=explicit)
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    ra, rb = a.json(), b.json()
    for key in ("A_N_per_m", "B_N", "D_N_m", "midplane_strain", "curvature_per_m"):
        np.testing.assert_array_equal(ra[key], rb[key])
    assert ra["inputs"]["material"] == {"library_id": "im7-8552", "dataset_id": None}
    assert rb["material_provenance"] is None
    provenance = ra["material_provenance"]
    assert provenance["dataset_id"] == "ncamp-im7-8552-2019-rtd-measured-v1"
    assert provenance["record_revision"] == "2026-10-10.1"
    assert "CAM-RP-2009-015" in provenance["citation"]
    assert {v["role"] for v in provenance["values"]} >= {"E1", "E2", "G12", "nu12", "F1t", "F6", "tply"}


def test_library_errors_are_reported_as_validation_errors_on_the_material_field():
    unknown = client.post("/v1/laminates/response", json={**EXAMPLE, "material": {"library_id": "im7"}})
    assert unknown.status_code == 422
    assert unknown.json()["detail"][0]["loc"][-1] in ("material", "library", "library_id") and "unknown library material" in unknown.json()["detail"][0]["msg"]
    refused = client.post("/v1/laminates/response", json={**EXAMPLE, "material": {"library_id": "t650-35-976"}})
    assert refused.status_code == 422 and "no elastic input set" in refused.json()["detail"][0]["msg"]
    mixed = client.post("/v1/laminates/response", json={**EXAMPLE, "material": {"library_id": "im7-8552", "E1_pa": 1e9}})
    assert mixed.status_code == 422


def test_prescribed_curvature_accepts_a_library_material_too():
    problem = json.loads((Path(__file__).parents[1] / "examples/flat-cross-ply.json").read_text())
    response = client.post("/v1/laminates/prescribed-curvature", json={**problem, "material": {"library_id": "as4-3501"}})
    assert response.status_code == 200, response.text
    assert response.json()["material_provenance"]["dataset_id"] == "daniel-ishai-2006-as4-3501-v2"
