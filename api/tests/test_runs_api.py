"""The case endpoint records every run it answers, and GET /v1/runs/{id} reads one back (ADR-0026)."""

import datetime as dt
import json
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from anisotropy_api.main import RUN_ID_HEADER, app
from anisotropy_api.records import ACTORS, Run
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE
from conftest import TEST_URL, needs_test_database

pytestmark = needs_test_database
ENDPOINT = "/v1/cases/solve"
HEADERS = {"X-Anisotropy-Actor": "test"}
EXAMPLES = Path(__file__).parents[1] / "examples"
EXAMPLE = json.loads((EXAMPLES / "case-library-axial-check.json").read_text())
FORWARD = json.loads((EXAMPLES / "zero-degree-tension.json").read_text())
CURVATURE = json.loads((EXAMPLES / "flat-cross-ply.json").read_text())
HEX = re.compile(r"^[0-9a-f]+$")


@pytest.fixture
def recording(empty_runs, monkeypatch):
    """A client whose app started with recording on, against the emptied test database."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app) as client:
        yield client


def count_rows(engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Run))


def test_a_solved_case_is_recorded_and_readable(recording):
    response = recording.post(ENDPOINT, headers=HEADERS, json=EXAMPLE)
    assert response.status_code == 200, response.text
    body = response.json()
    run_id = body["run_id"]
    uuid.UUID(run_id)
    assert response.headers[RUN_ID_HEADER] == run_id

    stored = recording.get(f"/v1/runs/{run_id}")
    assert stored.status_code == 200, stored.text
    record = stored.json()
    assert record["run_id"] == run_id and record["actor"] == "test" and record["status"] == "solved"
    assert record["endpoint"] == ENDPOINT and record["inputs"] == EXAMPLE
    assert record["response"]["results"] == body["results"] and record["response"]["materials"] == body["materials"]
    assert "run_id" not in record["response"]
    assert record["engine_version"] == body["engine_version"] == "0.1.0" and record["api_version"] == "0.1.0"
    assert len(record["inputs_sha256"]) == 64 and HEX.match(record["inputs_sha256"])
    assert record["git_commit"] is None or (len(record["git_commit"]) == 40 and HEX.match(record["git_commit"]))
    assert dt.datetime.fromisoformat(record["created_at"]).tzinfo is not None
    assert record["error"] is None and record["supersedes_run_id"] is None and record["llm_provider"] is None


def test_a_rejected_case_is_recorded_with_its_error(recording):
    response = recording.post(ENDPOINT, headers=HEADERS, json={"case": {}})
    assert response.status_code == 422 and "missing fields" in response.json()["detail"]
    record = recording.get(f"/v1/runs/{response.headers[RUN_ID_HEADER]}").json()
    assert record["status"] == "rejected" and record["error"] == response.json()["detail"]
    assert record["response"] is None and record["inputs"] == {"case": {}}


def test_a_toml_parse_error_is_recorded(recording):
    response = recording.post(ENDPOINT, headers=HEADERS, json={"toml": "units = 'SI'\n[material"})
    assert response.status_code == 422 and response.json()["detail"].startswith("toml:")
    record = recording.get(f"/v1/runs/{response.headers[RUN_ID_HEADER]}").json()
    assert record["status"] == "rejected" and record["inputs"] == {"toml": "units = 'SI'\n[material"}


def test_missing_or_unknown_actor_is_refused_and_not_recorded(recording, empty_runs):
    assert recording.post(ENDPOINT, json=EXAMPLE).status_code == 422
    response = recording.post(ENDPOINT, headers={"X-Anisotropy-Actor": "somebody"}, json=EXAMPLE)
    assert response.status_code == 422
    assert "X-Anisotropy-Actor" in response.json()["detail"] and "calculator" in response.json()["detail"]
    assert count_rows(empty_runs) == 0


def test_a_body_that_fails_the_contract_is_not_recorded(recording, empty_runs):
    assert recording.post(ENDPOINT, headers=HEADERS, json={}).status_code == 422
    assert count_rows(empty_runs) == 0


def test_every_actor_is_accepted(recording, empty_runs):
    for actor in ACTORS:
        assert recording.post(ENDPOINT, headers={"X-Anisotropy-Actor": actor}, json=EXAMPLE).status_code == 200
    assert count_rows(empty_runs) == len(ACTORS)


def test_identical_requests_share_a_digest_but_not_an_id(recording):
    first = recording.post(ENDPOINT, headers=HEADERS, json=EXAMPLE).json()["run_id"]
    second = recording.post(ENDPOINT, headers=HEADERS, json=EXAMPLE).json()["run_id"]
    assert first != second
    digests = {recording.get(f"/v1/runs/{run_id}").json()["inputs_sha256"] for run_id in (first, second)}
    assert len(digests) == 1


def test_the_forward_endpoint_is_recorded_for_the_calculator(recording):
    response = recording.post("/v1/laminates/response", headers={"X-Anisotropy-Actor": "calculator"}, json=FORWARD)
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers[RUN_ID_HEADER] == body["run_id"]
    record = recording.get(f"/v1/runs/{body['run_id']}").json()
    assert record["endpoint"] == "/v1/laminates/response" and record["actor"] == "calculator"
    assert record["inputs"] == FORWARD
    assert record["response"]["midplane_strain"] == body["midplane_strain"] and "run_id" not in record["response"]
    assert record["response"]["inputs"]["plies"] == FORWARD["plies"]


def test_the_prescribed_curvature_endpoint_is_recorded(recording):
    response = recording.post("/v1/laminates/prescribed-curvature", headers=HEADERS, json=CURVATURE)
    assert response.status_code == 200, response.text
    record = recording.get(f"/v1/runs/{response.json()['run_id']}").json()
    assert record["endpoint"] == "/v1/laminates/prescribed-curvature" and record["inputs"] == CURVATURE
    assert record["response"]["moments_N_m_per_m"] == response.json()["moments_N_m_per_m"]
    assert record["response"]["verification"]["passed"] is True


def test_the_older_endpoints_need_the_actor_too(recording, empty_runs):
    assert recording.post("/v1/laminates/response", json=FORWARD).status_code == 422
    assert recording.post("/v1/laminates/prescribed-curvature", json=CURVATURE).status_code == 422
    assert count_rows(empty_runs) == 0


def test_an_unknown_run_is_404_and_a_non_uuid_is_422(recording):
    assert recording.get(f"/v1/runs/{uuid.uuid4()}").status_code == 404
    assert recording.get("/v1/runs/not-a-uuid").status_code == 422


def test_switched_off_solves_without_a_run_id_and_has_nothing_to_read(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    with TestClient(app) as client:
        response = client.post(ENDPOINT, headers=HEADERS, json=EXAMPLE)
        assert response.status_code == 200 and response.json()["run_id"] is None
        assert RUN_ID_HEADER not in response.headers
        read = client.get(f"/v1/runs/{uuid.uuid4()}")
        assert read.status_code == 503 and "switched off" in read.json()["detail"]


def test_a_result_is_withheld_when_it_cannot_be_recorded(recording):
    working = app.state.records
    app.state.records = create_engine("postgresql+psycopg://anisotropy:x@127.0.0.1:1/anisotropy",
                                      connect_args={"connect_timeout": 1})
    try:
        response = recording.post(ENDPOINT, headers=HEADERS, json=EXAMPLE)
        assert response.status_code == 503 and "could not be recorded" in response.json()["detail"]
        assert recording.get(f"/v1/runs/{uuid.uuid4()}").status_code == 503
    finally:
        app.state.records.dispose()
        app.state.records = working
