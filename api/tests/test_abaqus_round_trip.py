"""A round trip through Abaqus from one sentence (ADR-0094, step 4): the assistant chooses among three fixed tools, a guard keeps the
names on offer, and the tools of the fea package do the work. The model is a stub client and the tools are a stand-in that records
the command it was given; one test asks the real tool for its state. Nothing here calls a model or Abaqus."""

import json
import shutil
from types import SimpleNamespace

import pytest

from anisotropy_api import abaqus_round_trip as trip
from anisotropy_api.assistant import ClaudeAssistant, TemplateAssistant, tool_choice_schema
from anisotropy_api.coupon_jobs import FEA

from test_assistant import StubClient

SPEC = FEA / "checks" / "d3039-im7-8552" / "d3039-im7-8552.toml"
TOLD = {"coupon": "IM7-UNT-L1", "job": "IM7-UNT-L1", "units": "mm-MPa", "state": {"built": False, "ran": False, "sent": False, "next": "build"},
        "tools": [{"name": "build", "description": "Build the coupon in Abaqus/CAE."}, {"name": "run", "description": "Run that job."},
                  {"name": "send", "description": "Read the finished job into one bundle and compare it with ours."}]}
MESSAGE = "build this coupon in Abaqus and compare"
WHICH = shutil.which  # the real one: the fixture below replaces it for every test


class Tools:
    """The fea package's tool as this module starts it: the state as JSON when asked, otherwise the command is kept and the code given."""

    def __init__(self, told=TOLD, code=0, state_code=0):
        self.told, self.code, self.state_code, self.calls = told, code, state_code, []

    def __call__(self, argv, capture):
        self.calls.append(list(argv))
        if capture:
            return SimpleNamespace(returncode=self.state_code, stdout=json.dumps(self.told), stderr="refused:\n  the coupon is not one the script draws")
        return SimpleNamespace(returncode=self.code)


@pytest.fixture(autouse=True)
def uv(monkeypatch):
    monkeypatch.setattr(trip.shutil, "which", lambda name: "/bin/uv")


def plan_of(tools: Tools) -> list[str]:
    return tools.calls[-1][tools.calls[-1].index("plan"):]


def test_the_guard_keeps_the_names_on_offer_once_each_in_the_tools_own_order():
    offered = ["build", "run", "send"]
    kept = trip.tool_guard({"tools": ["send", "build", "run"]}, offered)
    assert kept.tools == offered and kept.dropped == []
    kept = trip.tool_guard({"tools": ["run", "abaqus cae noGUI=evil.py", "run", 7, {"name": "build"}], "script": "import os"}, offered)
    assert kept.tools == ["run"]
    assert [d["reason"] for d in kept.dropped] == ["not a tool on offer", "chosen twice; once stands", "not a tool on offer", "not a tool on offer",
                                                   "not part of the answer asked for"]
    assert trip.tool_guard({"tools": "build"}, offered).tools == [] and trip.tool_guard({}, offered).tools == []


def test_the_model_sees_the_sentence_the_tools_and_what_is_done_and_nothing_of_the_coupon(tmp_path):
    client = StubClient(json.dumps({"tools": ["send", "build", "run"]}))
    tools, said = Tools(), []
    code = trip.round_trip(MESSAGE, SPEC, tmp_path / "work", ClaudeAssistant("m", client=client), runner=tools, say=said.append)
    assert code == 0 and said == ["The assistant chose: build, run, send."]
    request = client.calls[0]
    assert request["output_config"]["format"]["schema"] == tool_choice_schema(["build", "run", "send"])
    seen = json.loads(request["messages"][0]["content"])
    assert seen == {"message": MESSAGE, "tools": TOLD["tools"], "done": []}
    sent = json.dumps(request, default=str)
    assert str(tmp_path) not in sent and SPEC.name not in sent and "IM7-UNT-L1" not in sent  # no path, no file and no coupon reach the model
    assert plan_of(tools) == ["plan", str(SPEC), "--folder", str(tmp_path / "work"), "--tools", "build", "run", "send", "--chosen-by", "anthropic (m)",
                              "--asked", MESSAGE]
    assert tools.calls[0] == ["/bin/uv", "run", "--project", str(FEA), "python", str(trip.TOOL), "state", str(SPEC), "--folder", str(tmp_path / "work"), "--json"]


def test_the_model_chooses_a_part_of_the_job_and_leaves_out_what_is_done(tmp_path):
    told = {**TOLD, "state": {"built": True, "ran": False, "sent": False, "next": "run"}}
    client = StubClient(json.dumps({"tools": ["run"]}))
    tools, said = Tools(told, code=0), []
    assert trip.round_trip("just run the job", SPEC, tmp_path, ClaudeAssistant("m", client=client), abaqus="C:/SIMULIA/abaqus.bat", runner=tools, say=said.append) == 0
    assert json.loads(client.calls[0]["messages"][0]["content"])["done"] == ["build"]
    assert plan_of(tools)[4:] == ["--tools", "run", "--chosen-by", "anthropic (m)", "--asked", "just run the job", "--abaqus", "C:/SIMULIA/abaqus.bat"]


def test_with_the_assistant_off_the_words_are_not_read_and_every_step_left_runs(tmp_path):
    tools, said = Tools(code=1), []
    assert trip.round_trip(MESSAGE, SPEC, tmp_path, TemplateAssistant(), runner=tools, say=said.append) == 1  # the tools' own code: the bundle differs
    assert said == ["Your words were not read (the assistant is off), so every step that is not done runs: build, run, send."]
    assert plan_of(tools)[4:] == ["--tools", "build", "run", "send", "--chosen-by", "template", "--asked", MESSAGE]


def test_a_model_that_does_not_answer_leaves_the_tools_own_order_with_the_reason(tmp_path):
    tools, said = Tools({**TOLD, "state": {"built": True, "ran": True, "sent": False, "next": "send"}}), []
    assert trip.round_trip(MESSAGE, SPEC, tmp_path, ClaudeAssistant("m", client=StubClient("", stop_reason="refusal")), runner=tools, say=said.append) == 0
    assert said == ["Your words were not read (the model declined the request), so every step that is not done runs: send."]
    tools = Tools()
    assert trip.round_trip(MESSAGE, SPEC, tmp_path, ClaudeAssistant("m", client=StubClient("not json")), runner=tools, say=said.append) == 0
    assert "the model's answer was not the JSON asked for" in said[-1] and plan_of(tools)[5:8] == ["build", "run", "send"]


def test_nothing_runs_when_nothing_is_chosen_or_nothing_is_left(tmp_path):
    tools, said = Tools(), []
    assistant = ClaudeAssistant("m", client=StubClient(json.dumps({"tools": []})))
    assert trip.round_trip("what is the weather", SPEC, tmp_path, assistant, runner=tools, say=said.append) == 2
    assert said == ["The assistant found none of the steps in your words. They are: build, run, send."] and len(tools.calls) == 1
    tools, said = Tools({**TOLD, "state": {"built": True, "ran": True, "sent": True, "next": None}}), []
    assert trip.round_trip(MESSAGE, SPEC, tmp_path, assistant, runner=tools, say=said.append) == 2 and len(tools.calls) == 1
    assert "already done" in said[0]


def test_a_long_sentence_is_cut_before_the_model_and_the_record_see_it(tmp_path):
    client, tools = StubClient(json.dumps({"tools": ["build"]})), Tools()
    trip.round_trip("x" * 5000, SPEC, tmp_path, ClaudeAssistant("m", client=client), runner=tools, say=lambda line: None)
    assert len(json.loads(client.calls[0]["messages"][0]["content"])["message"]) == trip.MAX_MESSAGE and len(plan_of(tools)[-1]) == trip.MAX_MESSAGE


def test_what_the_tools_refuse_before_any_choice_is_said_and_the_command_ends_with_two(tmp_path, monkeypatch, capsys):
    with pytest.raises(trip.RoundTripRefused, match="the coupon is not one the script draws"):
        trip.round_trip(MESSAGE, SPEC, tmp_path, TemplateAssistant(), runner=Tools(state_code=2))
    monkeypatch.setattr(trip.shutil, "which", lambda name: None)
    monkeypatch.setattr(trip, "environment", lambda: {})
    assert trip.main([MESSAGE, "--coupon", str(SPEC), "--folder", str(tmp_path)]) == 2
    assert "uv is not on PATH" in capsys.readouterr().err
    monkeypatch.setattr(trip, "environment", lambda: {"ANISOTROPY_ASSISTANT_PROVIDER": "anthropic"})
    assert trip.main([MESSAGE, "--coupon", str(SPEC), "--folder", str(tmp_path)]) == 2
    assert "ANISOTROPY_ASSISTANT_MODEL is not set" in capsys.readouterr().err


@pytest.mark.skipif(WHICH("uv") is None, reason="uv is not on PATH")
def test_the_real_tool_tells_its_state_in_the_shape_this_module_reads(tmp_path, monkeypatch):
    monkeypatch.setattr(trip.shutil, "which", WHICH)
    tools = Tools()

    def runner(argv, capture):
        return trip.start(argv, capture) if capture else tools(argv, capture)

    said = []
    assert trip.round_trip(MESSAGE, SPEC, tmp_path / "work", TemplateAssistant(), runner=runner, say=said.append) == 0
    assert said == ["Your words were not read (the assistant is off), so every step that is not done runs: build, run, send."]
    assert plan_of(tools)[4:8] == ["--tools", "build", "run", "send"] and not (tmp_path / "work").exists()
