"""The API behind Cloudflare Access (ADR-0056): with the team domain and the audience tag named, every request but GET /healthz and
a CORS preflight needs the token Access adds, and the signed-in email reaches the run records (ADR-0026 amendment 1); without
them, today's API with no sign-in. The team's keys are stood in for; no network."""

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from anisotropy_api import access
from anisotropy_api.main import RUN_ID_HEADER, app
from anisotropy_api.settings import (ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE,
                                     AccessSettings)
from access_tokens import AUDIENCE, EMAIL, OTHER_PRIVATE_PEM, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database

SETTINGS = AccessSettings(TEAM, AUDIENCE)
HEADER = access.HEADER
ACTOR = {"X-Anisotropy-Actor": "test"}


def with_token(value: str) -> dict[str, str]:
    return {**ACTOR, HEADER: value}


@pytest.fixture
def behind_access(monkeypatch):
    """The API started with Access on and recording off; the team's keys replaced by the test key."""
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with TestClient(app) as client:
        assert app.state.access_verifier is not None  # the lifespan built the real check from the settings
        app.state.access_verifier = access.verifier(SETTINGS, key_for=key_for)
        yield client


def test_the_lifespan_reads_the_settings_and_the_check_needs_no_network(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with TestClient(app) as client:
        assert app.state.settings.access == SETTINGS and app.state.settings.access.certs_url == f"https://{TEAM}/cdn-cgi/access/certs"
        assert client.get("/healthz").status_code == 200  # no token, no keys fetched
    assert app.state.access_verifier is None  # cleared at shutdown, so the next start decides again


def test_a_valid_token_passes(behind_access):
    assert behind_access.get("/v1/materials", headers=with_token(token())).status_code == 200


def test_without_a_token_the_request_is_refused_and_names_the_header(behind_access):
    refused = behind_access.get("/v1/materials", headers=ACTOR)
    assert refused.status_code == 401 and HEADER in refused.json()["detail"]
    assert behind_access.post("/v1/cases/solve", headers=ACTOR, json={"case": {}}).status_code == 401  # before the contract, before the engine


@pytest.mark.parametrize("bad, reason", [
    (token(exp=1, iat=0, nbf=0), "expired"),
    (token(aud=["another-application"]), "another application"),
    (token(iss="https://other.cloudflareaccess.com"), "another team"),
    (token(OTHER_PRIVATE_PEM), "not valid"),
    ("not.a.token", "not valid"),
    (token(exp=None), "not valid"),
])
def test_a_bad_token_is_refused_with_its_reason(behind_access, bad, reason):
    refused = behind_access.get("/v1/materials", headers=with_token(bad))
    assert refused.status_code == 401 and reason in refused.json()["detail"]


def test_healthz_and_a_preflight_need_no_token(behind_access):
    assert behind_access.get("/healthz").json() == {"status": "ok"}
    preflight = behind_access.options("/v1/cases/solve", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                                                                  "Access-Control-Request-Headers": "content-type,x-anisotropy-actor"})
    assert preflight.status_code == 200 and preflight.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_a_refusal_carries_the_cors_headers_the_browser_needs(behind_access):
    refused = behind_access.get("/v1/materials", headers={**ACTOR, "Origin": "http://localhost:3000"})
    assert refused.status_code == 401 and refused.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unreachable_team_keys_are_a_503(behind_access):
    def no_keys(_token: str):
        raise access.TeamKeysUnavailable("the team's keys at https://team.cloudflareaccess.com/cdn-cgi/access/certs could not be fetched")

    app.state.access_verifier = access.verifier(SETTINGS, key_for=no_keys)
    refused = behind_access.get("/v1/materials", headers=with_token(token()))
    assert refused.status_code == 503 and "could not be fetched" in refused.json()["detail"]


def test_with_access_off_nothing_changes(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    monkeypatch.delenv(ACCESS_TEAM_DOMAIN_VARIABLE, raising=False)
    monkeypatch.delenv(ACCESS_AUDIENCE_VARIABLE, raising=False)
    with TestClient(app) as client:
        assert app.state.access_verifier is None
        assert client.get("/v1/materials", headers=ACTOR).status_code == 200  # no token asked for
    assert TestClient(app).get("/v1/materials", headers=ACTOR).status_code == 200  # and without the lifespan, as the other tests run


# ----------------------------------------------------------------------------------------- the middleware on its own: the email

def seen_email(headers: dict[str, str], verify=None) -> tuple[int, str | None]:
    """What a handler behind the middleware sees as `request.state.user_email` for a request with these headers."""
    seen: list[str | None] = []

    async def handler(request):
        seen.append(request.state.user_email)
        return JSONResponse({"ok": True})

    small = Starlette(routes=[Route("/thing", handler)])
    small.add_middleware(access.AccessMiddleware)
    small.state.access_verifier = verify if verify is not None else access.verifier(SETTINGS, key_for=key_for)
    status = TestClient(small).get("/thing", headers=headers).status_code
    return status, seen[0] if seen else None


def test_the_signed_in_email_rides_with_the_request():
    assert seen_email({HEADER: token()}) == (200, EMAIL)
    assert seen_email({HEADER: token(email="  Other.Person@example.com ")}) == (200, "Other.Person@example.com")  # as Access states it


def test_a_service_token_passes_with_no_email():
    assert seen_email({HEADER: service_token()}) == (200, None)


def test_with_access_off_the_email_is_none_not_missing():
    seen: list[str | None] = []

    async def handler(request):
        seen.append(request.state.user_email)
        return JSONResponse({"ok": True})

    small = Starlette(routes=[Route("/thing", handler)])
    small.add_middleware(access.AccessMiddleware)
    assert TestClient(small).get("/thing").status_code == 200 and seen == [None]


# ------------------------------------------------------------------------------------------------ the records (test database)

@pytest.fixture
def recording_behind_access(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with TestClient(app) as client:
        app.state.access_verifier = access.verifier(SETTINGS, key_for=key_for)
        yield client


@needs_test_database
def test_the_email_is_on_the_run_record(recording_behind_access):
    client = recording_behind_access
    solved = client.post("/v1/cases/solve", headers=with_token(token()), json={"case": {}})  # rejected by the engine, still a run
    assert solved.status_code == 422
    record = client.get(f"/v1/runs/{solved.headers[RUN_ID_HEADER]}", headers=with_token(token())).json()
    assert record["user_email"] == EMAIL and record["status"] == "rejected"
    listed = client.get("/v1/runs", headers=with_token(token())).json()
    assert listed[0]["run_id"] == record["run_id"] and listed[0]["user_email"] == EMAIL
    machine = client.post("/v1/cases/solve", headers=with_token(service_token()), json={"case": {}})
    assert client.get(f"/v1/runs/{machine.headers[RUN_ID_HEADER]}", headers=with_token(token())).json()["user_email"] is None
