"""The Anisotropy API as this server reaches it (ADR-0107): plain HTTP to the address the environment names, the API on this machine
unless told otherwise, with the actor named on every request (ADR-0026). A refusal comes back in the API's own words, so the client's
model can say what the engineer has to change."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx

API_URL = "ANISOTROPY_API_URL"
LOCAL_API = "http://127.0.0.1:8000"
ACTOR = "assistant"  # one of the actors the API knows (ADR-0026): an assistant working for the engineer; unused until this server
ACTOR_HEADER = "X-Anisotropy-Actor"
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
TIMEOUT_S = 150.0  # the API gives its own setup check two minutes before it answers 504


class ApiRefused(Exception):
    """The API did not give an answer: it refused the request, or it could not be reached. The message is for the engineer."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def api_url(environ: dict[str, str] | None = None) -> str:
    """The API's address: `ANISOTROPY_API_URL`, or the API on this machine. Plain http only to this machine itself, so a setup never
    crosses a network unencrypted, and no sign-in written into the address."""
    given = ((os.environ if environ is None else environ).get(API_URL) or "").strip() or LOCAL_API
    parts = urlsplit(given)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"{API_URL} must be an http or https address such as {LOCAL_API}; got {given!r}")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError(f"{API_URL} is an address alone: no user, password, query or fragment in it")
    if parts.scheme == "http" and parts.hostname not in LOOPBACK:
        raise ValueError(f"{API_URL} may use plain http only for this machine ({', '.join(sorted(LOOPBACK))}); use https for {parts.hostname}")
    return given.rstrip("/")


def detail_of(response: httpx.Response) -> str:
    """What the API said of a refusal: its `detail`, a sentence or the list of rows a 422 names."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, list) and detail:
        return "; ".join(f"{'.'.join(str(part) for part in item.get('loc', ()) if part != 'body')}: {item.get('msg', '')}".strip(": ")
                         if isinstance(item, dict) else str(item) for item in detail)
    return f"the API answered {response.status_code} with no reason"


class Api:
    """One HTTP client for the server's life. `transport` stands in for the network in tests."""

    def __init__(self, base_url: str | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = api_url() if base_url is None else api_url({API_URL: base_url})
        local = urlsplit(self.base_url).hostname in LOOPBACK
        # a proxy named in the environment is for the internet, never for this machine's own API
        self.http = httpx.Client(base_url=self.base_url, headers={ACTOR_HEADER: ACTOR}, timeout=TIMEOUT_S, transport=transport,
                                 trust_env=not local, follow_redirects=False)

    def get(self, path: str) -> Any:
        return self._send("GET", path)

    def post(self, path: str, body: dict) -> Any:
        return self._send("POST", path, json=body)

    def close(self) -> None:
        self.http.close()

    def _send(self, method: str, path: str, **sent: Any) -> Any:
        try:
            response = self.http.request(method, path, **sent)
        except httpx.ConnectError as exc:
            raise ApiRefused(f"The Anisotropy API at {self.base_url} does not answer. Start it on this machine (docs/components/mcp.md) "
                             f"and ask again.") from exc
        except httpx.TimeoutException as exc:
            raise ApiRefused(f"The Anisotropy API at {self.base_url} did not answer within {TIMEOUT_S:g} s.") from exc
        except httpx.HTTPError as exc:
            raise ApiRefused(f"The request to the Anisotropy API at {self.base_url} failed: {exc}") from exc
        if 300 <= response.status_code < 400:
            raise ApiRefused(f"The API at {self.base_url} answered with a redirect ({response.status_code}), as a site behind a sign-in "
                             f"does. This server reaches an API that needs no sign-in: the one on this machine.", response.status_code)
        if response.status_code >= 400:
            raise ApiRefused(detail_of(response), response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiRefused(f"The API at {self.base_url} answered {method} {path} with something that is not JSON.") from exc
