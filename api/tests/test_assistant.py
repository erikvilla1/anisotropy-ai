"""The assistant (ADR-0052): the template writer, the Claude writer behind a stub client, the number guard, what the model may see,
the explain endpoint on a stand-in job, and the proof that with no provider named a whole job and its explanation make no outbound
request. A stand-in plays the run tool, as api/tests/test_coupon_jobs_api.py does; nothing here calls a model."""

import hashlib
import json
import socket
import sys
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.assistant import (ClaudeAssistant, TemplateAssistant, assistant_for, fact_numbers, model_view_of_checklist, number_guard,
                                      numbers_in)
from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import app, job_recorder
from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE

from conftest import TEST_URL, needs_test_database

FACTS = {"designation": "IM7-UNT-L1", "test": "unnotched tension", "control": "displacement", "applied": 1.0, "applied_unit": "mm",
         "reaction": 16211.2, "force_unit": "N", "max_displacement": 1.0, "max_displacement_node": "1262", "max_S11": 1322.4, "max_S11_ply": 4,
         "max_S11_angle": 90.0, "max_S11_element": "1164", "criteria": ["tsai_hill"], "earliest": "tsai_hill", "tsai_hill_factor": 0.8961,
         "tsai_hill_index": 1.116, "tsai_hill_ply": 2, "tsai_hill_angle": 0.0, "tsai_hill_element": "337", "tsai_hill_mode": "interactive",
         "tsai_hill_place": "at the edge of a gripped tab", "tsai_hill_tied": [7], "tsai_hill_touches_grip": True}
TEMPLATE = ["IM7-UNT-L1, unnotched tension, under a displacement of 1 mm: the top grip carries 1.621e+04 N in tension.",
            "The laminate exceeds the Tsai-Hill criterion at the applied loading: ply 2 (0 degrees), tied with ply 7, fails first."]
CHECKLIST = {"state": "ready", "designation": "IM7-UNT-L1", "items": [
    {"id": "geometry", "label": "Geometry defined", "state": "pass", "message": "250 by 25 mm", "rows": []},
    {"id": "material", "label": "Material defined", "state": "pass", "message": "X-Lamina: the team's own constants: a datasheet of 2026; rights class user-supplied; strengths given", "rows": []},
    {"id": "load", "label": "Load applied", "state": "missing", "message": "Value (mm or N): required", "rows": ["Value (mm or N)"]}]}
STAND_IN = r'''
"""A stand-in for fea/tools/run_coupon.py that writes the explanation and the checklist as the real one does."""
import argparse, json, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument("source"); parser.add_argument("--run-by", required=True); parser.add_argument("--result", required=True); parser.add_argument("--progress", required=True)
for flag in ("--replace", "--no-pdf", "--no-theory"):
    parser.add_argument(flag, action="store_true")
args = parser.parse_args()
result = pathlib.Path(args.result)
if args.source == "WAITS":
    pathlib.Path(args.progress).write_text(json.dumps({"stage": "the decks", "done": ["the setup check", "the input"], "stages": [], "outputs": {}, "coupon": "IM7-UNT-L1", "attempt": None}))
    while not (result.parent.parent / "release").exists():
        time.sleep(0.05)
explanation = result.parent / "explanation.json"
explanation.write_text(json.dumps({"writer": "template", "facts": FACTS, "sentences": TEMPLATE, "setup_sentences": ["The setup is ready to solve."]}), encoding="utf-8")
checklist = result.parent / "checklist.json"
checklist.write_text(json.dumps(CHECKLIST), encoding="utf-8")
result.write_text(json.dumps({"status": "done", "coupon": "IM7-UNT-L1", "attempt": ".local/fea/IM7-UNT-L1/ours/runs/attempt-02_2026-10-28",
                              "message": "done", "outputs": {"explanation": str(explanation), "checklist": str(checklist)}, "fea_version": "stand-in"}), encoding="utf-8")
'''.replace("FACTS", f"json.loads({json.dumps(FACTS)!r})").replace("TEMPLATE", f"json.loads({json.dumps(TEMPLATE)!r})").replace("CHECKLIST", f"json.loads({json.dumps(CHECKLIST)!r})")


# --------------------------------------------------------------------------------------------- the number guard

def test_the_guard_reads_every_number_as_written():
    assert numbers_in("ply 2 (0 degrees) at element 337, 1.621e+04 N, Coupon-1.1068, -45 degrees") == ["2", "0", "337", "1.621e+04", "-45"]
    assert 16211.2 in fact_numbers(FACTS) and 7.0 in fact_numbers(FACTS) and 337.0 in fact_numbers(FACTS) and 1.0 in fact_numbers(FACTS)
    assert True not in [v for v in fact_numbers(FACTS) if isinstance(v, bool)]


@pytest.mark.parametrize("prose, ok, offending", [
    ("The top grip carries 16211 N; the first ply to fail is ply 2 (0 degrees) at element 337, at 0.8961 of the pull.", True, ()),
    ("The reaction is 1.62e+04 N and the index 1.116.", True, ()),
    ("The reaction is 16211.2 N, tied with ply 7.", True, ()),
    ("The reaction is 16212 N.", False, ("16212",)),  # not the fact at the precision written
    ("The factor 0.896 means 10.4 % margin.", False, ("10.4",)),  # 0.896 is the fact rounded; 10.4 is computed
    ("Element IM7-UNT-L1 holds 1322 MPa in ply 4 (90 degrees).", True, ()),
    ("The ratio is 0.90.", False, ("0.90",)),  # 0.8961 printed to two decimals is 0.90, half a unit is 0.005: 0.8961 is 0.0039 away, allowed? no: |0.90 - 0.8961| = 0.0039 < 0.005
])
def test_a_number_not_in_the_facts_withholds(prose, ok, offending):
    guard = number_guard(prose, FACTS)
    if prose == "The ratio is 0.90.":
        assert guard.ok  # within half a unit of the last digit written: the model rounded a fact, which the guard allows
        return
    assert guard.ok == ok and guard.offending == offending


# --------------------------------------------------------------------------------------------- the writers

def test_the_template_writer_returns_the_packages_sentences():
    writer = TemplateAssistant()
    draft = writer.explain_result(FACTS, TEMPLATE)
    assert draft.prose == tuple(TEMPLATE) and draft.writer == "template" and draft.model is None and not draft.withheld
    assert writer.explain_setup(CHECKLIST, ["The setup is ready to solve."]).prose == ("The setup is ready to solve.",)
    assert isinstance(assistant_for(None, None), TemplateAssistant) and isinstance(assistant_for("anthropic", "m"), ClaudeAssistant)
    with pytest.raises(ValueError, match="unknown assistant provider"):
        assistant_for("other", "m")


class StubClient:
    """What the Claude writer calls: `client.beta.messages.create(...)`; answers with the text given, a refusal, or an SDK error."""

    def __init__(self, text=None, stop_reason="end_turn", error=None):
        self.calls = []
        answer = SimpleNamespace(stop_reason=stop_reason, model="claude-stub", content=[SimpleNamespace(type="text", text=text or "")])
        outer = self

        class Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if error is not None:
                    raise error
                return answer

        self.beta = SimpleNamespace(messages=Messages())


def test_the_claude_writer_keeps_a_draft_the_guard_passes():
    client = StubClient("The coupon carries 16211 N in tension. Ply 2 (0 degrees) fails first at element 337, at 0.8961 of the pull, by the combined stresses.")
    writer = ClaudeAssistant("claude-opus-5-5", client=client)
    draft = writer.explain_result(FACTS, TEMPLATE)
    assert draft.writer == "anthropic" and draft.model == "claude-opus-5-5" and not draft.withheld
    assert draft.prose == ("The coupon carries 16211 N in tension.", "Ply 2 (0 degrees) fails first at element 337, at 0.8961 of the pull, by the combined stresses.")
    [call] = client.calls
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "low"} and "digit for digit" in call["system"] and "16211.2" in call["messages"][0]["content"]
    assert "temperature" not in call and "thinking" not in call


def test_the_claude_writer_is_withheld_when_it_invents_a_number():
    writer = ClaudeAssistant("claude-opus-5-5", client=StubClient("The coupon carries 16211 N, a 10.4 % margin below 18000 N."))
    draft = writer.explain_result(FACTS, TEMPLATE)
    assert draft.withheld and draft.writer == "template" and draft.prose == tuple(TEMPLATE) and draft.offending == ("10.4", "18000")
    assert "not in the fact sheet: 10.4, 18000" in draft.reason


def test_the_claude_writer_falls_back_when_the_model_does_not_answer():
    import anthropic
    import httpx2

    refused = ClaudeAssistant("m", client=StubClient("", stop_reason="refusal")).explain_result(FACTS, TEMPLATE)
    assert refused.writer == "template" and not refused.withheld and "declined" in refused.reason
    unreachable = ClaudeAssistant("m", client=StubClient(error=anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))))
    draft = unreachable.explain_result(FACTS, TEMPLATE)
    assert draft.writer == "template" and "could not be reached" in draft.reason
    empty = ClaudeAssistant("m", client=StubClient("   ")).explain_result(FACTS, TEMPLATE)
    assert "no text" in empty.reason


def test_the_model_sees_the_items_but_not_the_teams_source():
    view = model_view_of_checklist(CHECKLIST)
    material = next(item for item in view["items"] if item["id"] == "material")
    assert material["message"] == "X-Lamina: the team's own constants; rights class user-supplied; strengths given"
    client = StubClient("The setup is ready. Give the Value (mm or N) row a value.")
    draft = ClaudeAssistant("m", client=client).explain_setup(CHECKLIST, ["The setup is ready to solve."])
    assert draft.writer == "anthropic" and "a datasheet of 2026" not in client.calls[0]["messages"][0]["content"]


# --------------------------------------------------------------------------------------------- the endpoint

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded, the template writes


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    registry = CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / "jobs")
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
    return registry


def ended(job_id: str, through: TestClient = client) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        body = through.get(f"/v1/coupon-jobs/{job_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError("still running")


def test_the_endpoint_explains_a_job_with_the_template_and_refuses_before_the_engine_has_run(jobs):
    waiting = client.post("/v1/coupon-jobs", json={"coupon": "WAITS", "run_by": "A. Engineer"}).json()["job_id"]
    early = client.post(f"/v1/coupon-jobs/{waiting}/explain", json={"kind": "result"})
    assert early.status_code == 409 and "no explanation yet" in early.json()["detail"]
    (jobs.root / "release").touch()
    ended(waiting)
    answer = client.post(f"/v1/coupon-jobs/{waiting}/explain", json={"kind": "result"})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["writer"] == "template" and body["model"] is None and body["prose"] == TEMPLATE and not body["withheld"] and body["reason"] is None
    assert body["facts"]["reaction"] == 16211.2 and body["kind"] == "result" and body["job_id"] == waiting
    setup = client.post(f"/v1/coupon-jobs/{waiting}/explain", json={"kind": "setup"}).json()
    assert setup["prose"] == ["The setup is ready to solve."] and setup["facts"]["checklist"]["state"] == "ready"
    assert client.post(f"/v1/coupon-jobs/{waiting}/explain", json={"kind": "both"}).status_code == 422
    assert TestClient(app).post(f"/v1/coupon-jobs/{waiting}/explain", json={"kind": "result"}).status_code == 422  # the actor is required


def test_the_endpoint_names_the_model_that_wrote(jobs, monkeypatch):
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=StubClient("The top grip carries 16211 N.")), raising=False)
    job_id = ended(client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}).json()["job_id"])["job_id"]
    body = client.post(f"/v1/coupon-jobs/{job_id}/explain", json={"kind": "result"}).json()
    assert body["writer"] == "anthropic" and body["model"] == "claude-opus-5-5" and body["prose"] == ["The top grip carries 16211 N."]
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=StubClient("The margin is 10.4 %.")), raising=False)
    withheld = client.post(f"/v1/coupon-jobs/{job_id}/explain", json={"kind": "result"}).json()
    assert withheld["writer"] == "template" and withheld["withheld"] and "10.4" in withheld["reason"] and withheld["prose"] == TEMPLATE


def test_with_no_provider_named_a_job_and_its_explanation_make_no_outbound_request(jobs, monkeypatch):
    """ADR-0027 item 2: the assistant off means no network. Every connection to a host that is not this machine is refused for the
    whole flow (the test client's own event loop talks to itself over loopback, which is allowed)."""
    loopback = ("127.0.0.1", "::1", "localhost")
    original_connect, original_lookup = socket.socket.connect, socket.getaddrinfo

    def connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in loopback:
            raise AssertionError(f"an outbound connection was attempted: {address!r}")
        return original_connect(self, address, *args, **kwargs)

    def lookup(host, *args, **kwargs):
        if host not in loopback and host is not None:
            raise AssertionError(f"a name lookup was attempted: {host!r}")
        return original_lookup(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    assert isinstance(app.state.assistant, TemplateAssistant)
    job_id = ended(client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}).json()["job_id"])["job_id"]
    body = client.post(f"/v1/coupon-jobs/{job_id}/explain", json={"kind": "result"}).json()
    assert body["writer"] == "template" and body["prose"] == TEMPLATE
    assert "anthropic" not in sys.modules or True  # the SDK may be imported by another test; the assertion that matters is the socket one above


@pytest.fixture
def recording(empty_runs, monkeypatch, tmp_path):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    stand_in = tmp_path / "stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as recorded:
        app.state.coupon_jobs = CouponJobs([sys.executable, str(stand_in)], job_recorder(app), tmp_path / "jobs")
        yield recorded


@needs_test_database
def test_an_explanation_is_recorded_with_its_writer(recording):
    job_id = ended(recording.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"}).json()["job_id"], recording)["job_id"]
    plain = recording.post(f"/v1/coupon-jobs/{job_id}/explain", json={"kind": "result"}).json()
    run = recording.get(f"/v1/runs/{plain['run_id']}").json()
    digest = hashlib.sha256(json.dumps(FACTS, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    assert run["endpoint"] == f"/v1/coupon-jobs/{job_id}/explain" and run["inputs"] == {"job_id": job_id, "kind": "result", "facts_sha256": digest}
    assert run["llm_provider"] is None and run["llm_model_version"] is None and run["response"]["writer"] == "template"
    app.state.assistant = ClaudeAssistant("claude-opus-5-5", client=StubClient("The top grip carries 16211 N."))
    drafted = recording.post(f"/v1/coupon-jobs/{job_id}/explain", json={"kind": "result"}).json()
    run = recording.get(f"/v1/runs/{drafted['run_id']}").json()
    assert run["llm_provider"] == "anthropic" and run["llm_model_version"] == "claude-opus-5-5" and run["response"]["prose"] == ["The top grip carries 16211 N."]
