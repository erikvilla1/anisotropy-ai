"""The API behind our own sign-in (ADR-0058): with the session secret named, every request but GET /healthz and a CORS preflight
needs the identity token the Worker signs, and its email reaches the run records; with Cloudflare Access on as well, either
token is accepted, which is how the switch from one to the other happens without a gap."""

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from anisotropy_api import access
from anisotropy_api.main import app
from anisotropy_api.settings import (ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE,
                                     SESSION_SECRET_VARIABLE, AccessSettings, IdentitySettings, load_settings)
from access_tokens import AUDIENCE, TEAM, key_for, token

SECRET = "test-session-secret-0123456789abcdefghij"
EMAIL = "engineer@example.com"
ACTOR = {"X-Anisotropy-Actor": "test"}
# The token tests/worker-sign-in.test.ts makes with this secret at 1 800 000 000 s: the Worker and the API agree on the key, the
# claims and the encoding.
VECTOR_SECRET = "vector-secret-0123456789abcdefghijklmnop"
VECTOR = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhbmlzb3Ryb3B5LWFwaSIsImVtYWlsIjoiZW5naW5lZXJAZXhhbXBsZS5jb20iLCJleHAiOjE4MDAwMDAxMjAs"
          "ImlhdCI6MTgwMDAwMDAwMCwiaXNzIjoiYW5pc290cm9weS1zaWduLWluIn0.Bn_cPjz92xeREhCaBmB3uAU2lKqvKot12nxWZ3RlFO4")


def identity(secret: str = SECRET, **overrides) -> str:
    now = int(time.time())
    claims = {"aud": access.IDENTITY_AUDIENCE, "email": EMAIL, "exp": now + 120, "iat": now, "iss": access.IDENTITY_ISSUER, **overrides}
    return jwt.encode(claims, access.identity_key(secret), algorithm="HS256")


@pytest.fixture
def behind_sign_in(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    monkeypatch.delenv(ACCESS_TEAM_DOMAIN_VARIABLE, raising=False)
    monkeypatch.delenv(ACCESS_AUDIENCE_VARIABLE, raising=False)
    monkeypatch.setenv(SESSION_SECRET_VARIABLE, SECRET)
    with TestClient(app) as client:
        assert app.state.identity_verifier is not None and app.state.access_verifier is None
        yield client


def test_the_settings_read_the_secret_and_refuse_a_short_one():
    assert load_settings({RECORDING_VARIABLE: "off"}).identity == IdentitySettings(None)
    assert load_settings({RECORDING_VARIABLE: "off", SESSION_SECRET_VARIABLE: f" {SECRET} "}).identity == IdentitySettings(SECRET)
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        load_settings({RECORDING_VARIABLE: "off", SESSION_SECRET_VARIABLE: "short"})


def test_the_workers_token_verifies_here():
    claims = jwt.decode(VECTOR, access.identity_key(VECTOR_SECRET), algorithms=["HS256"], audience=access.IDENTITY_AUDIENCE,
                        issuer=access.IDENTITY_ISSUER, options={"verify_exp": False, "verify_iat": False})
    assert claims == {"aud": "anisotropy-api", "email": EMAIL, "exp": 1800000120, "iat": 1800000000, "iss": "anisotropy-sign-in"}


def test_a_valid_token_passes_and_healthz_needs_none(behind_sign_in):
    assert behind_sign_in.get("/v1/materials", headers={**ACTOR, access.IDENTITY_HEADER: identity()}).status_code == 200
    assert behind_sign_in.get("/healthz").status_code == 200


@pytest.mark.parametrize("bad, reason", [
    (None, "no X-Anisotropy-Identity header"),
    (identity(secret="another-secret-0123456789abcdefghijklmn"), "not valid"),
    (identity(exp=int(time.time()) - 60), "expired"),
    (identity(aud="someone-else"), "not valid"),
    (identity(iss="someone-else"), "not valid"),
    (jwt.encode({"aud": access.IDENTITY_AUDIENCE, "exp": int(time.time()) + 60, "iat": int(time.time()), "iss": access.IDENTITY_ISSUER},
                access.identity_key(SECRET), algorithm="HS256"), "not valid"),  # no email
    ("not-a-token", "not valid"),
])
def test_a_missing_or_bad_token_is_refused(behind_sign_in, bad, reason):
    headers = ACTOR if bad is None else {**ACTOR, access.IDENTITY_HEADER: bad}
    refused = behind_sign_in.get("/v1/materials", headers=headers)
    assert refused.status_code == 401 and reason in refused.json()["detail"]


def test_an_access_token_alone_does_not_pass_when_only_our_sign_in_is_on(behind_sign_in):
    refused = behind_sign_in.get("/v1/materials", headers={**ACTOR, access.HEADER: token()})
    assert refused.status_code == 401


def test_during_the_switch_either_token_passes(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    monkeypatch.setenv(SESSION_SECRET_VARIABLE, SECRET)
    with TestClient(app) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        assert client.get("/v1/materials", headers={**ACTOR, access.IDENTITY_HEADER: identity()}).status_code == 200
        assert client.get("/v1/materials", headers={**ACTOR, access.HEADER: token()}).status_code == 200
        assert client.get("/v1/materials", headers=ACTOR).status_code == 401
        # a bad identity token is refused even with a good Access token beside it: the identity header is checked first
        both = {**ACTOR, access.IDENTITY_HEADER: identity(secret="another-secret-0123456789abcdefghijklmn"), access.HEADER: token()}
        assert client.get("/v1/materials", headers=both).status_code == 401


def test_the_signed_in_email_rides_with_the_request():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    seen: list[str | None] = []

    async def handler(request):
        seen.append(request.state.user_email)
        return JSONResponse({"ok": True})

    small = Starlette(routes=[Route("/thing", handler)])
    small.add_middleware(access.AccessMiddleware)
    small.state.identity_verifier = access.identity_verifier(IdentitySettings(SECRET))
    small.state.access_verifier = None
    assert TestClient(small).get("/thing", headers={access.IDENTITY_HEADER: identity()}).status_code == 200 and seen == [EMAIL]
