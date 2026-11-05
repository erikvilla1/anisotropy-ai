"""Who is asking, in the hosted tier. Two ways in, each switched on by its settings, and either may be on during a switch:

- Our own sign-in (ADR-0058): the Worker signs a short-lived token for the signed-in user, the `X-Anisotropy-Identity` header,
  an HS256 JWT made with a key derived from the session secret both share (worker/sign-in.ts). Checked first when present.
- Cloudflare Access (ADR-0056), below.

Cloudflare Access in front of the API (ADR-0056): when the settings name the team domain and the application's audience tag,
every request except GET /healthz and a CORS preflight must carry the token Access adds to each request it lets through, the
`Cf-Access-Jwt-Assertion` header: signed by one of the team's published keys, issued by that team, for this application, not
expired. The signed-in email the token carries goes with the request to the run records (ADR-0026 amendment 1). Without the
settings nothing here runs, and the API is the local one with no sign-in (ADR-0011).

The keys are read from https://<team>.cloudflareaccess.com/cdn-cgi/access/certs and cached. Access rotates them every six weeks
and keeps the old one valid for seven days, so a token whose key id is not in the cached set makes the client fetch the set again.
A service token carries no email; its request passes with no email recorded.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .settings import AccessSettings, IdentitySettings

HEADER = "Cf-Access-Jwt-Assertion"
IDENTITY_HEADER = "X-Anisotropy-Identity"
IDENTITY_AUDIENCE = "anisotropy-api"  # what worker/sign-in.ts writes; both sides must agree
IDENTITY_ISSUER = "anisotropy-sign-in"
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


def identity_key(secret: str) -> bytes:
    """The identity token's key: HMAC-SHA256(secret, "anisotropy identity v1"), as the Worker derives it (worker/sign-in.ts)."""
    return hmac.new(secret.encode("utf-8"), b"anisotropy identity v1", hashlib.sha256).digest()


def identity_verifier(settings: IdentitySettings) -> Callable[[str], dict]:
    """A function that checks one identity token from the Worker and returns its claims, or raises jwt's error."""
    key = identity_key(settings.secret)

    def verify(token: str) -> dict:
        return jwt.decode(token, key, algorithms=["HS256"], audience=IDENTITY_AUDIENCE, issuer=IDENTITY_ISSUER, leeway=30,
                          options={"require": ["exp", "iat", "aud", "iss", "email"]})  # leeway: the Worker's and the container's clocks

    return verify


def signed_in_email(claims: dict) -> str | None:
    """The email Access verified with the identity provider, as the token states it; None for a service token, which has none."""
    email = claims.get("email")
    return email.strip() if isinstance(email, str) and email.strip() else None


def _refused(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


def _header(scope: Scope, name: str) -> str:
    wanted = name.lower().encode("latin-1")
    return next((value.decode("latin-1").strip() for key, value in scope["headers"] if key == wanted), "")


class AccessMiddleware:
    """Refuses, with 401, any request that lacks a valid token while a sign-in is on, and sets `request.state.user_email` for the
    handlers. `app.state.identity_verifier` (our sign-in) and `app.state.access_verifier` (Cloudflare Access) are the checks, set
    by the lifespan from the settings; None means that one is off, and both None means the local API with no sign-in."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state.setdefault("user_email", None)
        verify = getattr(scope["app"].state, "access_verifier", None)
        verify_identity = getattr(scope["app"].state, "identity_verifier", None)
        if (verify is None and verify_identity is None) or scope["path"] in EXEMPT_PATHS or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        identity = _header(scope, IDENTITY_HEADER) if verify_identity is not None else ""
        if identity:
            try:
                claims = verify_identity(identity)
            except jwt.ExpiredSignatureError:
                await _refused(401, "The sign-in token has expired; reload the page")(scope, receive, send)
                return
            except PyJWTError as exc:
                await _refused(401, f"The sign-in token is not valid: {exc}")(scope, receive, send)
                return
            state["user_email"] = signed_in_email(claims)
            await self.app(scope, receive, send)
            return
        if verify is None:
            await _refused(401, f"Not signed in: no {IDENTITY_HEADER} header. Sign in at the site's address")(scope, receive, send)
            return
        token = _header(scope, HEADER)
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
