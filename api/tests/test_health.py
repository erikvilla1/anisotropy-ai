"""GET /healthz answers without the database (ADR-0056): what a platform polls to know the container is up."""

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.main import app


def test_healthz_answers_with_the_lifespan_and_records_off(monkeypatch):
    monkeypatch.setenv("ANISOTROPY_RUN_RECORDS", "off")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:  # the lifespan runs: no database is connected
        response = client.get("/healthz")  # no actor header: the check is not a run
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert "X-Anisotropy-Run-Id" not in response.headers


def test_healthz_answers_without_the_lifespan():
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/v1/healthz", "/health"])
def test_only_the_one_path_answers(path):
    assert TestClient(app).get(path).status_code == 404


def test_version_names_the_commit_the_container_was_started_with(monkeypatch):
    """The check after a deploy (ADR-0113) compares this commit with the one it deployed."""
    commit = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("ANISOTROPY_RUN_RECORDS", "off")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("anisotropy_api.main.git_commit", lambda: commit)  # as in the image, where no checkout is
    with TestClient(app) as client:
        response = client.get("/version")  # no actor header: not a run
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["git_commit"] == commit and body["api_version"] and body["engine_version"]
    assert "X-Anisotropy-Run-Id" not in response.headers
