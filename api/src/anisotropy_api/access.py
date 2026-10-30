"""Cloudflare Access in front of the API (ADR-0056): when the settings name the team domain and the application's audience tag,
every request except GET /healthz and a CORS preflight must carry the token Access adds to each request it lets through, the
`Cf-Access-Jwt-Assertion` header: signed by one of the team's published keys, issued by that team, for this application, not
expired. The signed-in email the token carries goes with the request to the run records (ADR-0026 amendment 1). Without the
settings nothing here runs, and the API is the local one with no sign-in (ADR-0011).

The keys are read from https://<team>.cloudflareaccess.com/cdn-cgi/access/certs and cached. Access rotates them every six weeks
and keeps the old one valid for seven days, so a token whose key id is not in the cached set makes the client fetch the set again.
A service token carries no email; its request passes with no email recorded.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .settings import AccessSettings

HEADER = "Cf-Access-Jwt-Assertion"
ALGORITHMS = ["RS256"]  # what Access signs with; nothing else is accepted
EXEMPT_PATHS = frozenset({"/healthz"})  # what a platform polls before any user has signed in


class TeamKeysUnavailable(RuntimeError):
    """The team's keys could not be fetched, so no token can be checked."""


def verifier(settings: AccessSettings, key_for: Callable[[str], Any] | None = None) -> Callable[[str], dict]:
    """A function that checks one token and returns its claims, or raises jwt's error for what is wrong with it. The key comes
    from the team's published set by the token's key id; `key_for` replaces that lookup in tests."""
    client = None if key_for is not None else PyJWKClient(settings.certs_url, cache_keys=True)

    def verify(token: str) -> dict:
        if key_for is not None:
            key = key_for(token)
        else:
            try:
                key = client.get_signing_key_from_jwt(token).key
            except PyJWKClientConnectionError as exc:
                raise TeamKeysUnavailable(f"the team's keys at {settings.certs_url} could not be fetched: {exc}") from exc
        return jwt.decode(token, key, algorithms=ALGORITHMS, audience=settings.audience, issuer=settings.issuer,
                          options={"require": ["exp", "iat", "aud", "iss"]})

    return verify


def signed_in_email(claims: dict) -> str | None:
    """The email Access verified with the identity provider, as the token states it; None for a service token, which has none."""
    email = claims.get("email")
    return email.strip() if isinstance(email, str) and email.strip() else None


def _refused(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


class AccessMiddleware:
    """Refuses, with 401, any request that lacks a valid Access token while Access is on, and sets `request.state.user_email`
    for the handlers. `app.state.access_verifier` is the check, set by the lifespan from the settings; None means Access is off."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state.setdefault("user_email", None)
        verify = getattr(scope["app"].state, "access_verifier", None)
        if verify is None or scope["path"] in EXEMPT_PATHS or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        wanted = HEADER.lower().encode("latin-1")
        token = next((value.decode("latin-1").strip() for name, value in scope["headers"] if name == wanted), "")
        if not token:
            await _refused(401, f"This API is behind Cloudflare Access and the request did not come through it: no {HEADER} header. "
                                "Sign in at the site's address")(scope, receive, send)
            return
        try:
            claims = verify(token)
        except jwt.ExpiredSignatureError:
            await _refused(401, "The Cloudflare Access token has expired; sign in again")(scope, receive, send)
            return
        except jwt.InvalidAudienceError:
            await _refused(401, "The Cloudflare Access token is for another application, not this API")(scope, receive, send)
            return
        except jwt.InvalidIssuerError:
            await _refused(401, "The Cloudflare Access token was issued by another team, not this API's")(scope, receive, send)
            return
        except TeamKeysUnavailable as exc:
            await _refused(503, f"The Cloudflare Access token could not be checked: {exc}")(scope, receive, send)
            return
        except PyJWTError as exc:
            await _refused(401, f"The Cloudflare Access token is not valid: {exc}")(scope, receive, send)
            return
        state["user_email"] = signed_in_email(claims)
        await self.app(scope, receive, send)
