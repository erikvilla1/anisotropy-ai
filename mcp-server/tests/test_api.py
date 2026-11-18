"""How the server reaches the API (ADR-0107): where, as whom, and what a refusal says."""

import httpx
import pytest

from anisotropy_mcp.api import ACTOR, ACTOR_HEADER, API_URL, LOCAL_API, Api, ApiRefused, api_url


def test_the_address_is_this_machines_api_unless_the_environment_names_another():
    assert api_url({}) == LOCAL_API == "http://127.0.0.1:8000" and api_url({API_URL: "  "}) == LOCAL_API
    assert api_url({API_URL: "http://localhost:8123/"}) == "http://localhost:8123"
    assert api_url({API_URL: "https://api.example.test"}) == "https://api.example.test"


@pytest.mark.parametrize("given, why", [
    ("ftp://127.0.0.1", "http or https"), ("127.0.0.1:8000", "http or https"), ("http://", "http or https"),
    ("http://api.example.test", "plain http only for this machine"),  # a setup never crosses a network unencrypted
    ("https://someone:secret@api.example.test", "no user, password"), ("https://api.example.test/?token=abc", "no user, password"),
])
def test_an_address_that_is_not_one_or_would_leak_is_refused(given, why):
    with pytest.raises(ValueError, match=why):
        api_url({API_URL: given})


def test_every_request_names_the_assistant_as_its_actor():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers.get(ACTOR_HEADER)))
        return httpx.Response(200, json={"ok": True})

    api = Api(LOCAL_API, transport=httpx.MockTransport(handler))
    assert api.get("/v1/materials") == {"ok": True} and api.post("/v1/coupon-jobs/check", {"values": {}}) == {"ok": True}
    assert seen == [("GET", "/v1/materials", "assistant"), ("POST", "/v1/coupon-jobs/check", "assistant")] and ACTOR == "assistant"


@pytest.mark.parametrize("status, body, said", [
    (503, {"detail": "The live solver could not start: uv was not found"}, "The live solver could not start: uv was not found"),
    (422, {"detail": [{"loc": ["body", "values"], "msg": "Field required"}, {"loc": ["body", "extra"], "msg": "Extra inputs are not permitted"}]},
     "values: Field required; extra: Extra inputs are not permitted"),
    (500, {}, "the API answered 500 with no reason"),
])
def test_a_refusal_is_passed_on_in_the_apis_own_words(status, body, said):
    api = Api(LOCAL_API, transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)))
    with pytest.raises(ApiRefused) as refused:
        api.get("/v1/materials")
    assert str(refused.value) == said and refused.value.status == status


def test_an_api_that_is_not_there_a_sign_in_page_and_an_answer_that_is_not_json_each_say_so():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ApiRefused, match="does not answer. Start it on this machine"):
        Api(LOCAL_API, transport=httpx.MockTransport(down)).get("/v1/materials")
    signed = Api("https://api.example.test", transport=httpx.MockTransport(lambda request: httpx.Response(302, headers={"Location": "https://login.example.test"})))
    with pytest.raises(ApiRefused, match="redirect \\(302\\), as a site behind a sign-in does"):
        signed.get("/v1/materials")
    with pytest.raises(ApiRefused, match="not JSON"):
        Api(LOCAL_API, transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>"))).get("/v1/materials")
