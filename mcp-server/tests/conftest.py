"""A stand-in for the API (ADR-0107): the answers are the files the browser tests use, which the fea package wrote (`tests/fixtures/`),
so a tool is tried on a real result without a solver. Nothing here reaches a network."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from anisotropy_mcp.api import Api
from anisotropy_mcp.server import build

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "tests" / "fixtures" / "studio"
WING = REPO / "tests" / "fixtures" / "wing"  # the engine's answers for the wing (ADR-0128), written by scripts/wing-choices.py
SECTIONS = [{"id": "engine:5-failure", "document": "Laminate theory", "title": "5. Failure", "text": "Tsai-Hill combines the stresses of a ply."}]


def fixture(name: str, folder: Path = STUDIO) -> dict:
    return json.loads((folder / name).read_text(encoding="utf-8"))


class FakeApi:
    """Answers the routes the tools call, and keeps what was asked. `blocked` makes the solve answer a check that does not pass."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None, dict]] = []
        self.blocked = False
        self.all_tests = False
        self.sections = SECTIONS
        self.refuse: tuple[int, object] | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body, dict(request.headers)))
        if self.refuse is not None:
            return httpx.Response(self.refuse[0], json={"detail": self.refuse[1]})
        path = request.url.path
        if path == "/v1/materials":
            return httpx.Response(200, json=[
                {"material_id": "im7-8552", "name": "IM7 / 8552", "dataset_id": "ncamp-im7-8552-2019-rtd-measured-v1", "dataset": "NCAMP 2019", "primary": True,
                 "rights": "open-publisher", "elastic_inputs": True},
                {"material_id": "as4-3501", "name": "AS4 / 3501-6", "dataset_id": "maddocks-1995-table-6-2", "dataset": "NASA CR-199802 1995", "primary": False,
                 "rights": "open-publisher", "elastic_inputs": False}])
        if path == "/v1/materials/im7-8552":
            return httpx.Response(200, json={"material_id": "im7-8552", "E1_pa": 162095743962.38818, "dataset_asked": request.url.params.get("dataset")})
        if path.startswith("/v1/materials/"):
            return httpx.Response(404, json={"detail": f"unknown library material {path.rsplit('/', 1)[1]!r}"})
        if path == "/v1/coupon-tests":
            return httpx.Response(200, json={"all": self.all_tests})
        if path == "/v1/coupon-jobs/check":
            return httpx.Response(200, json={"run_id": None, "state": "ready", "designation": "IM7-UNT-L1", "checklist": fixture("checklist.json"),
                                             "preview": fixture("preview.json")})
        if path == "/v1/coupon-jobs/live":
            if self.blocked:
                checklist = fixture("checklist.json")
                checklist["state"] = "blocked"
                checklist["items"][2].update(state="missing", message="Length (mm): required", rows=["Length (mm)"])
                return httpx.Response(200, json={"run_id": None, "state": "blocked", "designation": None, "solver": "kernel", "warm": True, "seconds": 0.1,
                                                 "timings": {}, "checklist": checklist, "preview": None, "fields": None, "explanation": None})
            return httpx.Response(200, json={"run_id": None, "state": "ready", "designation": "IM7-UNT-L1", "solver": "kernel", "warm": True, "seconds": 0.7,
                                             "timings": {}, "checklist": fixture("checklist.json"), "preview": fixture("preview.json"),
                                             "fields": fixture("fields.json"), "explanation": fixture("explanation.json")})
        if path == "/v1/workspace/theory-sections":
            return httpx.Response(200, json={"run_id": None, "sections": self.sections})
        if path == "/v1/wings/analyze":  # the example wing's answer, whatever wing file is sent
            return httpx.Response(200, json=fixture("example-answer.json", WING))
        if path == "/v1/wings/changes":  # two 0° plies on the skin, root to 40 %; caps the example does not have are refused as the engine refuses them
            change = body["change"]
            if change["part"] == "spar_caps" and "[spar_caps]" not in body["toml"]:
                return httpx.Response(422, json={"detail": "The wing has no spar caps: add them on the Layup step first."})
            if change == {"action": "add_plies", "part": "skin", "angle": 0, "count": 2, "start": 0, "end": 0.4, "placement": "beside"}:
                return httpx.Response(200, json=fixture("skin-preview.json", WING))
            return httpx.Response(422, json={"detail": "not in this stand-in"})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def fake() -> FakeApi:
    return FakeApi()


@pytest.fixture
def call(fake):
    """Call a tool as an MCP client does, in process: the tool's answer read back from its text, or the refusal's words."""
    server = build(Api("http://127.0.0.1:8000", transport=httpx.MockTransport(fake)))

    def run(*steps: tuple[str, dict]) -> list:
        async def session() -> list:
            answers = []
            async with Client(server) as client:
                for name, arguments in steps:
                    result = await client.call_tool(name, arguments)
                    text = result.content[0].text if result.content else ""
                    answers.append(Refused(text) if result.is_error else json.loads(text))
            return answers
        return asyncio.run(session())

    return run


class Refused(str):
    """A tool's refusal, as the client's model reads it."""
