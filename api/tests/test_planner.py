"""The workspace's planner (ADR-0144, build step 2): an engineer's sentence read by one call to the model into a plan of typed tool steps,
the checks that keep a plan or refuse it, the day's planned requests, and one approval that applies the changes as a version, checks
the setup and starts the run. The contract with the page is `tests/fixtures/planner/`: every answer here carries the keys of those
files. A scripted client plays the model, as api/tests/test_model_costs.py does; nothing here calls one."""

import dataclasses
import json
import sys
import uuid
from importlib import util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from anisotropy_api import access, planner
from anisotropy_api import setup_tools as tools
from anisotropy_api.assistant import ClaudeAssistant, LimitedAssistant, Reading, TemplateAssistant
from anisotropy_api.coupon_jobs import CouponJobs, JobBusy
from anisotropy_api.main import ENQUEUE_HEADER, RUN_ID_HEADER, app, job_recorder
from anisotropy_api.model_costs import FEATURES
from anisotropy_api.records import PLAN_STATES, PLANS_UNCOUNTED, AgentPlanRow, ModelCallRow
from anisotropy_api.settings import (ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, AGENT_REQUESTS_PER_DAY_VARIABLE, DATABASE_VARIABLE,
                                     RECORDING_VARIABLE, AccessSettings, load_settings)

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from memory_store import MemoryStore
from test_model_costs import answer

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "planner"
PROPOSED = json.loads((FIXTURES / "plan-proposed.json").read_text(encoding="utf-8"))
QUESTION = json.loads((FIXTURES / "plan-question.json").read_text(encoding="utf-8"))
RUNNING = json.loads((FIXTURES / "approve-running.json").read_text(encoding="utf-8"))
PLATE_SETUP = json.loads((ROOT / "tests" / "fixtures" / "setup-tools" / "plate-setup.json").read_text(encoding="utf-8"))

PLATE = {"form": {"test": "plate", "units": "mm-MPa", "length": "250", "width": "25", "library": "im7-8552", "ply_1": "45", "ply_2": "0",
                  "ply_3": "-45", "ply_4": "90", "symmetric": "yes", "element_size": "", "date": "2026-11-26", "filled_by": "A. Engineer",
                  "notes": "the bracket for the north site"},
         "plate": {"supports": [], "loads": [], "regions": []}}
PULLED = {**PLATE, "plate": {"supports": [{"region": "Edge-Bottom", "dofs": [1, 2, 3, 4, 5, 6], "value": ""}],
                             "loads": [{"region": "Edge-Top", "kind": "force", "dof": 2, "total": "2000"}], "regions": []}}
COUPON = {"form": {"test": "unnotched tension", "units": "mm-MPa", "length": "250", "width": "25", "library": "im7-8552", "ply_1": "0",
                   "ply_2": "90", "symmetric": "yes", "control": "displacement", "value": "1", "filled_by": ""},
          "plate": {"supports": [], "loads": [], "regions": []}}
ASK = PROPOSED["ask"]  # "clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds"


def args(**given):
    """A step's arguments as the schema has the model write them: every one, null where the tool takes none."""
    return {name: given.get(name) for name in planner.ARGS}


def step(tool: str, quote: str, **given):
    return {"tool": tool, "args": args(**given), "quote": quote}


def plan(*steps, question=None, unread=()):
    return {"steps": list(steps), "question": question, "unread": list(unread)}


GOOD = plan(step("hold", "clamp the bottom edge", region="Edge-Bottom", dofs=[1, 2, 3, 4, 5, 6]),
            step("force", "pull the top edge with 2 kN", region="Edge-Top", sense="tension", value="2", unit="kN"),
            step("run", "tell me if it holds"),
            step("answer", "tell me if it holds", question="Does it hold at 2 kN?"))


def with_args(raw: dict, n: int, **changed) -> dict:
    """The plan with step n's arguments changed (n from 1)."""
    copied = json.loads(json.dumps(raw))
    copied["steps"][n - 1]["args"].update(changed)
    return copied


# ------------------------------------------------------------------------------------------- what the model is shown and asked for

def test_the_model_sees_the_sentence_the_setup_the_rows_and_the_tools_and_no_name_note_or_email():
    view = planner.plan_view(ASK, PLATE)
    assert view["sentence"] == ASK and view["setup"]["regions"][0]["name"] == "Edge-Bottom" and "digest" not in view["setup"]
    assert [tool["name"] for tool in view["tools"]] == ["hold", "move", "force", "pressure", "free", "unload", "row", "run", "answer"]
    keys = [row["key"] for row in view["rows"]]
    assert "width" in keys and "library" in keys and "ply_1" in keys
    assert not {"filled_by", "notes", "date", "test", "units", "name_part", "own_name", "own_source"} & set(keys)
    shown = json.dumps(view)
    assert "A. Engineer" not in shown and "north site" not in shown and "@" not in shown
    assert "check" not in [tool["name"] for tool in view["tools"]] and "qa" not in [tool["name"] for tool in view["tools"]]
    coupon = planner.plan_view("set the width to 20 mm and run it", COUPON)
    assert [tool["name"] for tool in coupon["tools"]] == ["row", "run", "answer"]  # a coupon is held and loaded by its test's grips


def test_the_schema_names_only_the_tools_regions_and_rows_on_offer():
    schema = planner.plan_schema(PLATE)
    item = schema["properties"]["steps"]["items"]
    assert item["properties"]["tool"]["enum"] == planner.tool_names(PLATE)
    regions = item["properties"]["args"]["properties"]["region"]["anyOf"][0]["enum"]
    assert regions == ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Face"]
    assert item["properties"]["args"]["required"] == list(planner.ARGS) and item["properties"]["args"]["additionalProperties"] is False
    assert schema["required"] == ["steps", "question", "unread"] and schema["additionalProperties"] is False
    assert "minimum" not in json.dumps(schema) and "maxItems" not in json.dumps(schema)  # structured outputs take neither
    assert planner.plan_schema(COUPON)["properties"]["steps"]["items"]["properties"]["args"]["properties"]["region"] == {"type": "null"}


# ------------------------------------------------------------------------------------------- the checks before a plan is kept

def test_a_good_plan_is_the_contracts_steps_with_the_checks_the_server_adds():
    checked = planner.check_plan(GOOD, ASK, PLATE)
    assert checked.ok and checked.question is None
    assert checked.steps == PROPOSED["steps"]
    assert planner.done_lines(checked.steps) == PROPOSED["done"]
    assert [s["role"] for s in checked.steps] == ["Setup", "Setup", "Solver", "Solver", "QA", "Report"]


def test_a_number_the_sentence_does_not_write_is_refused():
    converted = with_args(GOOD, 2, value="2000", unit="N")
    assert planner.check_plan(converted, ASK, PLATE).reasons == [
        "step 2: 2000 is not a number the sentence writes; a value is copied as written and the tools convert it"]
    no_unit = with_args(GOOD, 2, unit=None)  # 2 with no unit would be 2 N: the sentence wrote kN
    assert planner.check_plan(no_unit, ASK, PLATE).reasons == ["step 2: the sentence writes 2 kN, and the step gives it with no unit"]
    other_unit = with_args(GOOD, 2, unit="lbf")
    assert planner.check_plan(other_unit, ASK, PLATE).reasons == ["step 2: the unit lbf is not written in the sentence"]
    asked = with_args(GOOD, 4, question="Does it hold at 3 kN?")
    assert planner.check_plan(asked, ASK, PLATE).reasons == ["step 4: its question writes 3, which the sentence does not"]


def test_an_unknown_region_a_tool_not_on_offer_and_a_quote_not_in_the_sentence_are_refused():
    assert planner.check_plan(with_args(GOOD, 1, region="Edge-Middle"), ASK, PLATE).reasons == [
        "step 1: Edge-Middle is not a region of this model; it has Edge-Bottom, Edge-Left, Edge-Right, Edge-Top, Face"]
    shell = plan(step("bash", "clamp the bottom edge"))
    assert "'bash' is not a tool on offer here" in planner.check_plan(shell, ASK, PLATE).reasons[0]
    server = plan(step("check", "clamp the bottom edge"))
    assert "'check' is not a tool on offer here" in planner.check_plan(server, ASK, PLATE).reasons[0]  # the server adds it
    quoted = json.loads(json.dumps(GOOD))
    quoted["steps"][0]["quote"] = "clamp the left edge"
    assert planner.check_plan(quoted, ASK, PLATE).reasons == ["step 1: its quote is not words of the sentence"]
    coupon = plan(step("hold", "set the width", region="Edge-Bottom", dofs=[1]))
    assert "'hold' is not a tool on offer here" in planner.check_plan(coupon, "set the width to 20 mm and run it", COUPON).reasons[0]


def test_too_many_steps_are_refused():
    sentence = "hold the bottom edge and the top edge and the left edge and the right edge, free them, run it"
    holds = [step("hold", "hold the bottom edge", region=r, dofs=[1, 2, 3]) for r in ("Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right")]
    frees = [step("free", "free them", region=r) for r in ("Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right")]
    ten = plan(*holds, *frees, step("run", "run it"))  # 9 steps, 11 with the check and the QA: kept
    assert planner.check_plan(ten, sentence, PLATE).reasons == []
    eleven = plan(*holds, *frees, step("unload", "free them", region="Face"), step("unload", "free them", region="Edge-Top"),
                  step("run", "run it"))  # 11 steps, 13 with the check and the QA
    assert planner.check_plan(eleven, sentence, PLATE).reasons == [
        "the plan has 13 steps with the checks the software adds; a plan has at most 12"]


def test_the_order_of_a_plan_is_changes_one_run_and_answers():
    after = plan(step("run", "tell me if it holds"), step("hold", "clamp the bottom edge", region="Edge-Bottom", dofs=[1, 2, 3, 4, 5, 6]))
    assert planner.check_plan(after, ASK, PLATE).reasons == [
        "step 2: a change after the run would not be in it: the changes come before the run"]
    early = plan(step("answer", "tell me if it holds", question="Does it hold?"))
    assert planner.check_plan(early, ASK, PLATE).reasons == [
        "step 1: an answer reads the result of the plan's run, so it comes after a run"]
    twice = plan(step("run", "tell me if it holds"), step("run", "tell me if it holds"))
    assert planner.check_plan(twice, ASK, PLATE).reasons == ["step 2: the plan runs the analysis once"]
    assert planner.check_plan(plan(), ASK, PLATE).reasons == ["the plan has no step and asks no question"]
    none = planner.check_plan(plan(unread=[{"quote": "clamp Edge-Middle", "reason": "not_offered"}]), "clamp Edge-Middle and run it", PLATE)
    assert none.reasons == ["no step on offer does what the sentence asks"]  # the card lists the words under it


def test_a_change_the_tools_refuse_makes_no_plan():
    refused = planner.check_plan(plan(step("free", "clamp the bottom edge", region="Edge-Top"), step("run", "tell me if it holds")), ASK, PLATE)
    assert not refused.ok and refused.reasons[0].startswith("step 1: ") and refused.steps == []


def test_a_coupons_size_is_the_geometrys_and_its_material_the_setups():
    sentence = "set the width to 20 mm, use AS4/8552 and run it"
    raw = plan(step("row", "set the width to 20 mm", key="width", value="20", unit="mm"),
               step("row", "use AS4/8552", key="library", value="as4-8552"), step("run", "run it"))
    checked = planner.check_plan(raw, sentence, COUPON)
    assert checked.ok, checked.reasons
    assert [(s["role"], s["tool"]) for s in checked.steps] == [("Geometry", "row"), ("Setup", "row"), ("Solver", "check"), ("Solver", "run"),
                                                               ("QA", "qa")]
    assert checked.steps[4]["line"] == planner.QA_LINES[False]  # a coupon is held by its grips: no held corners to look at
    assert checked.steps[0]["regions"] == [] and checked.steps[0]["change"] == {"action": "row", "key": "width", "value": "20", "unit": "mm"}


def test_a_question_back_stands_alone_and_the_unread_words_are_kept():
    sentence = "fix the end and pull it with 2 kN"
    asked = plan(question=QUESTION["question"], unread=[{"quote": "pull it with 2 kN", "reason": "refers_back"},
                                                        {"quote": "words not there", "reason": "not_offered"}])
    checked = planner.check_plan(asked, sentence, PLATE)
    assert checked.ok and checked.steps == [] and checked.question == QUESTION["question"]
    assert checked.unread == [{"quote": "pull it with 2 kN", "reason": "refers_back"}]  # words not in the sentence are left out


def test_an_answers_line_keeps_a_name_in_capitals():
    assert planner.answer_line("Does it hold at 2 kN?") == "Answer: does it hold at 2 kN?"
    assert planner.answer_line("Edge-Top reaction?") == "Answer: Edge-Top reaction?"
    assert planner.answer_line("Tsai-Wu margin?") == "Answer: Tsai-Wu margin?"


# ------------------------------------------------------------------------------------------- one call, one more try

class FakeWriter:
    """A writer that answers each plan with the next one scripted (a dict), or with no reading (None); never a model."""

    name = "anthropic"

    def __init__(self, *raws):
        self.raws, self.views = list(raws), []

    def plan(self, view, schema):
        self.views.append(view)
        raw = self.raws.pop(0)
        return Reading(None, "template", None, "the model could not be reached") if raw is None else Reading(raw, "anthropic", "claude-opus-5-5")


def test_a_plan_that_fails_the_checks_is_tried_once_more_with_the_reasons():
    writer = FakeWriter(with_args(GOOD, 2, value="2000", unit="N"), GOOD)
    made = planner.make_plan(writer, ASK, PLATE, [])
    assert made.state == "proposed" and made.steps == PROPOSED["steps"] and (made.writer, made.model) == ("anthropic", "claude-opus-5-5")
    assert "refused" not in writer.views[0]
    assert writer.views[1]["refused"]["reasons"] == [
        "step 2: 2000 is not a number the sentence writes; a value is copied as written and the tools convert it"]


def test_a_plan_that_fails_twice_is_refused_with_the_reasons():
    bad = with_args(GOOD, 2, value="2000", unit="N")
    made = planner.make_plan(FakeWriter(bad, bad), ASK, PLATE, [])
    assert made.state == "refused" and made.steps == [] and made.writer == "template" and made.model is None
    assert made.reason == "step 2: 2000 is not a number the sentence writes; a value is copied as written and the tools convert it"
    gone = planner.make_plan(FakeWriter(bad, None), ASK, PLATE, [])
    assert gone.state == "refused" and "2000" in gone.reason


def test_each_answer_the_checks_turned_back_is_kept_with_its_reasons():
    # ADR-0145: a retry that passed used to leave no trace of the first answer; the oversight page shows it
    bad = with_args(GOOD, 2, value="2000", unit="N")
    reason = "step 2: 2000 is not a number the sentence writes; a value is copied as written and the tools convert it"
    passed = planner.make_plan(FakeWriter(bad, GOOD), ASK, PLATE, [])
    assert passed.state == "proposed" and passed.tried == [{"plan": bad, "reasons": [reason]}]
    refused = planner.make_plan(FakeWriter(bad, bad), ASK, PLATE, [])
    assert refused.state == "refused" and refused.tried == [{"plan": bad, "reasons": [reason]}, {"plan": bad, "reasons": [reason]}]
    gone = planner.make_plan(FakeWriter(bad, None), ASK, PLATE, [])
    assert gone.tried == [{"plan": bad, "reasons": [reason]}]
    assert planner.make_plan(FakeWriter(GOOD), ASK, PLATE, []).tried == []


def test_no_model_is_unavailable_and_the_cap_on_calls_says_so():
    assert planner.make_plan(TemplateAssistant(), ASK, PLATE, []).state == "unavailable"
    limited = planner.make_plan(LimitedAssistant(5), ASK, PLATE, [])
    assert limited.state == "unavailable" and limited.reason == "the day's limit of free-text readings for this sign-in is reached"


# ------------------------------------------------------------------------------------------- the values a run takes and the steps as they go

@pytest.mark.parametrize("case", PLATE_SETUP["values"], ids=lambda c: c["name"])
def test_a_plates_run_values_are_the_pages(case):
    assert planner.run_values({"form": case["form"], "plate": case["plate"]}, False) == case["values"]


@pytest.mark.parametrize("case", PLATE_SETUP["coupons"], ids=lambda c: c["name"])
def test_a_coupons_run_values_are_the_pages(case):
    """What the page sends for a coupon's run (`workspaceValues`), held by `tests/setup-tools.test.ts` to the same cases."""
    assert planner.run_values({"form": case["form"], "plate": {}}, False) == case["values"]


def test_a_coupons_run_values_are_the_tension_screens():
    form = {**COUPON["form"], "element_size": "1.5", "own_E1": "160000", "G13": "5000", "standard": "none"}
    assert planner.run_values({"form": form, "plate": {}}, False) == {
        "form_version": tools.form_definition()["form_version"], "input": "tension", "library": "im7-8552", "ply_1": 0, "ply_2": 90,
        "symmetric": "yes", "standard": "none", "G13": 5000, "control": "displacement", "value": 1, "length": 250, "width": 25,
        "element_size": 1.5}  # no own constant beside a library material; an element size that is not the blank form's is sent
    assert "element_size" not in planner.run_values({"form": {**form, "element_size": "2"}, "plate": {}}, False)  # the blank form's 2.0
    assert planner.run_values({"form": {**form, "units": "in-psi"}, "plate": {}}, False)["units"] == "in-psi"
    assert planner.run_values({"form": form, "plate": {}}, True) == tools.form_values(form)
    assert planner.run_by({"form": form}) == "studio" and planner.run_by({"form": {**form, "filled_by": "A. Engineer"}}) == "A. Engineer"


def test_steps_are_reported_until_the_plan_is_done_or_stopped():
    steps = json.loads(json.dumps(RUNNING["plan"]["steps"]))
    assert planner.report_step(steps, 4, "done", None) == "running"
    assert planner.report_step(steps, 5, "done", "every check passes") == "running"
    assert planner.report_step(steps, 6, "done", None) == "done" and steps[4]["note"] == "every check passes"
    assert planner.report_step(steps, 6, "done", None) == "done"  # the same report twice changes nothing
    with pytest.raises(planner.StepRefused, match="has ended"):
        planner.report_step(steps, 6, "failed", "late")
    with pytest.raises(planner.StepRefused, match="the server's"):
        planner.report_step(steps, 3, "done", None)
    with pytest.raises(LookupError):
        planner.report_step(steps, 9, "done", None)
    stopped = json.loads(json.dumps(RUNNING["plan"]["steps"]))
    assert planner.report_step(stopped, 4, "failed", "the solver stopped") == "stopped"
    assert [s["state"] for s in stopped] == ["done", "done", "done", "failed", "skipped", "skipped"]


def test_the_states_and_features_are_the_ones_the_migration_allows():
    spec = util.spec_from_file_location("m0017", ROOT / "api" / "alembic" / "versions" / "0017_agent_plans.py")
    migration = util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.FEATURES == FEATURES and "plan_steps" in FEATURES
    assert migration.STATES == PLAN_STATES == planner.STATES and PLANS_UNCOUNTED == planner.UNCOUNTED


def test_the_days_planned_requests_are_thirty_unless_set():
    assert load_settings({RECORDING_VARIABLE: "off"}).agent_requests_per_user_per_day == 30
    assert load_settings({DATABASE_VARIABLE: "postgresql://x@y/z", AGENT_REQUESTS_PER_DAY_VARIABLE: "5"}).agent_requests_per_user_per_day == 5
    for bad in ("0", "many", "-3"):
        with pytest.raises(RuntimeError, match=AGENT_REQUESTS_PER_DAY_VARIABLE):
            load_settings({DATABASE_VARIABLE: "postgresql://x@y/z", AGENT_REQUESTS_PER_DAY_VARIABLE: bad})
    with pytest.raises(RuntimeError, match="needs run records on"):
        load_settings({RECORDING_VARIABLE: "off", AGENT_REQUESTS_PER_DAY_VARIABLE: "5"})


# ------------------------------------------------------------------------------------------- the routes

STUDIO = r'''
"""A stand-in for fea/tools/studio_tool.py's check: a plate held nowhere, or a coupon with no length, is blocked; the values it was
given are written down for the test."""
import argparse, json, pathlib
parser = argparse.ArgumentParser()
parser.add_argument("--every-test", action="store_true")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("check"); p.add_argument("values"); p.add_argument("--out", required=True)
args = parser.parse_args()
values = json.loads(pathlib.Path(args.values).read_text(encoding="utf-8"))
with open(SEEN, "a", encoding="utf-8") as seen:
    seen.write(json.dumps({"values": values, "every": args.every_test}) + "\n")
out = pathlib.Path(args.out)
out.mkdir(parents=True)
problems = []
if values.get("test") == "plate" and not values.get("supports"):
    problems.append("values.json: the plate is held nowhere, so it can move freely")
if "length" not in values:
    problems.append("values.json: Length (mm): required")
items = [{"id": "supports", "label": "Supports", "state": "fail" if problems else "pass", "message": problems[0] if problems else "held", "rows": []}]
(out / "checklist.json").write_text(json.dumps({"items": items, "designation": "IM7-PLT-L1", "coupon_exists": False, "attempts": 0,
                                                "state": "blocked" if problems else "ready", "problems": problems}))
if not problems:
    (out / "preview.json").write_text(json.dumps({"units": "mm-MPa", "mesh": {"element_count": 1200}}))
'''


class Scripted:
    """The client the Claude writer calls: each call is answered with the next plan scripted, as JSON, and what it was asked is kept."""

    def __init__(self, *plans):
        self.plans, self.asked = list(plans), []
        outer = self

        class Messages:
            def create(self, **kwargs):
                outer.asked.append(kwargs)
                return answer(json.dumps(outer.plans.pop(0)))

        self.beta = SimpleNamespace(messages=Messages())


@pytest.fixture
def planning(empty_runs, monkeypatch, tmp_path):
    """The API behind Cloudflare Access with run records on, the job queue's front with a stand-in check, and no model until a test
    scripts one."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    seen = tmp_path / "seen.jsonl"
    studio = tmp_path / "studio.py"
    studio.write_text(STUDIO.replace("SEEN", repr(str(seen))), encoding="utf-8")
    store = MemoryStore()
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser", access.HEADER: token()}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        jobs = CouponJobs([sys.executable, "-c", "pass"], job_recorder(app), tmp_path / "jobs", studio=[sys.executable, str(studio)], store=store,
                          table=empty_runs, role="queue")
        monkeypatch.setattr(app.state, "coupon_jobs", jobs, raising=False)
        monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
        yield SimpleNamespace(client=client, jobs=jobs, engine=empty_runs, seen=seen, store=store)


def scripted(monkeypatch, *plans) -> Scripted:
    client = Scripted(*plans)
    monkeypatch.setattr(app.state, "assistant", ClaudeAssistant("claude-opus-5-5", client=client))
    return client


def project(client, content: dict = PLATE, kind: str = "fea", headers: dict | None = None) -> str:
    pid = str(uuid.uuid4())
    made = client.put(f"/v1/projects/{pid}", json={"kind": kind, "name": "Bracket for the north site", "content": content}, headers=headers or {})
    assert made.status_code == 201, made.text
    return pid


def calls(engine) -> list[ModelCallRow]:
    with Session(engine) as session:
        return list(session.scalars(select(ModelCallRow).order_by(ModelCallRow.called_at)))


def has_keys(ours: dict, theirs: dict) -> None:
    """Every key of the contract's answer is in ours (ours may add keys, never drop or rename one)."""
    missing = set(theirs) - set(ours)
    assert not missing, f"missing keys {sorted(missing)}"


def a_plan(client, pid: str, ask: str = ASK, **headers):
    asked = client.post(f"/v1/projects/{pid}/plans", json={"ask": ask}, headers=headers)
    assert asked.status_code == 200, asked.text
    return asked


@needs_test_database
def test_a_plan_is_proposed_in_the_contracts_shape_and_its_call_kept(planning, monkeypatch):
    model = scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    asked = a_plan(planning.client, pid)
    body = asked.json()
    has_keys(body, PROPOSED)
    for ours, theirs in zip(body["steps"], PROPOSED["steps"]):
        assert set(ours) == set(theirs)
    assert body["steps"] == PROPOSED["steps"] and body["done"] == PROPOSED["done"]
    assert (body["state"], body["project"], body["ask"], body["writer"], body["model"]) == ("proposed", pid, ASK, "anthropic", "claude-opus-5-5")
    assert body["base"] == tools.content_digest(PLATE) and body["requests_left"] == 29 and body["job"] is None and body["version"] is None
    assert body["question"] is None and body["reason"] is None and body["approved_at"] is None and body["withheld"] is False
    assert body["run_id"] == asked.headers[RUN_ID_HEADER]
    with planning.engine.connect() as connection:
        run = connection.execute(text("SELECT endpoint, llm_provider, llm_model_version, user_email, inputs FROM runs WHERE id = :id"),
                                 {"id": body["run_id"]}).one()
    # the route's template, not its path: the ids would not fit the column, and the weekly views would split by project
    assert tuple(run) == ("/v1/projects/{project_id}/plans", "anthropic", "claude-opus-5-5", EMAIL, {"ask": ASK})
    [call] = calls(planning.engine)
    assert (call.feature, call.user_email, call.actor, str(call.run_id)) == ("plan_steps", EMAIL, "browser", body["run_id"])
    [request] = model.asked
    shown = request["messages"][0]["content"]
    assert ASK in shown and "Edge-Bottom" in shown
    assert EMAIL not in shown and "north site" not in shown and "A. Engineer" not in shown and pid not in shown  # R-11
    assert request["output_config"]["format"]["schema"] == planner.plan_schema(PLATE)
    again = planning.client.get(f"/v1/projects/{pid}/plans/{body['id']}").json()
    assert again["steps"] == body["steps"] and again["requests_left"] == 29 and again["run_id"] is None


@needs_test_database
def test_a_number_not_in_the_sentence_is_tried_again_then_refused(planning, monkeypatch):
    bad = with_args(GOOD, 2, value="2000", unit="N")
    model = scripted(monkeypatch, bad, bad)
    body = a_plan(planning.client, project(planning.client)).json()
    assert body["state"] == "refused" and body["steps"] == [] and body["withheld"] is True and body["model"] is None
    assert body["reason"] == "step 2: 2000 is not a number the sentence writes; a value is copied as written and the tools convert it"
    assert body["requests_left"] == 29  # a model was asked: it counts
    assert len(model.asked) == 2 and "refused" in json.loads(model.asked[1]["messages"][0]["content"])
    assert [c.feature for c in calls(planning.engine)] == ["plan_steps", "plan_steps"]


@needs_test_database
def test_a_plans_calls_name_it_say_the_model_was_checked_and_keep_a_fingerprint_of_the_words(planning, monkeypatch):
    # ADR-0145: one query finds a plan's calls; a stand-in model shows as unchecked; what was turned back stays on the plan
    bad = with_args(GOOD, 2, value="2000", unit="N")
    scripted(monkeypatch, bad, GOOD)
    body = a_plan(planning.client, project(planning.client)).json()
    assert body["state"] == "proposed"
    made = calls(planning.engine)
    assert [str(c.plan_id) for c in made] == [body["id"], body["id"]] and [c.checked for c in made] == [True, True]
    assert all(len(c.sent_sha256) == 64 for c in made) and made[0].sent_sha256 != made[1].sent_sha256  # the retry sent the reasons too
    with Session(planning.engine) as session:
        kept = session.get(AgentPlanRow, uuid.UUID(body["id"]))
    assert [a["plan"] for a in kept.attempts] == [bad] and kept.attempts[0]["reasons"][0].startswith("step 2: 2000")


@needs_test_database
def test_an_unknown_region_or_too_many_steps_is_refused_and_a_fixed_plan_is_kept(planning, monkeypatch):
    nowhere = with_args(GOOD, 1, region="Edge-Middle")
    scripted(monkeypatch, nowhere, GOOD)
    kept = a_plan(planning.client, project(planning.client)).json()
    assert kept["state"] == "proposed" and kept["steps"] == PROPOSED["steps"]
    long = plan(*[step("hold", "clamp the bottom edge", region="Edge-Bottom", dofs=[1, 2, 3])] * 10, step("run", "tell me if it holds"))
    scripted(monkeypatch, long, nowhere)
    refused = a_plan(planning.client, project(planning.client)).json()
    assert refused["state"] == "refused" and "Edge-Middle is not a region of this model" in refused["reason"]


@needs_test_database
def test_a_question_back_is_answered_in_the_contracts_shape(planning, monkeypatch):
    scripted(monkeypatch, plan(question=QUESTION["question"]))
    body = a_plan(planning.client, project(planning.client), QUESTION["ask"]).json()
    has_keys(body, QUESTION)
    assert (body["state"], body["steps"], body["done"], body["question"]) == ("question", [], [], QUESTION["question"])
    assert body["requests_left"] == 29


@needs_test_database
def test_with_no_model_the_plan_is_unavailable_and_not_counted(planning):
    body = a_plan(planning.client, project(planning.client)).json()
    assert (body["state"], body["writer"], body["model"], body["requests_left"]) == ("unavailable", "template", None, 30)
    assert calls(planning.engine) == []


@needs_test_database
def test_past_the_days_planned_requests_no_model_is_called(planning, monkeypatch):
    monkeypatch.setattr(app.state, "settings", dataclasses.replace(app.state.settings, agent_requests_per_user_per_day=1))
    model = scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    assert a_plan(planning.client, pid).json()["requests_left"] == 0
    capped = a_plan(planning.client, pid).json()
    assert (capped["state"], capped["reason"], capped["requests_left"], capped["steps"]) == ("capped", planner.PLAN_LIMIT_REASON, 0, [])
    assert len(model.asked) == 1 and len(calls(planning.engine)) == 1
    with Session(planning.engine) as session:
        assert [row.state for row in session.scalars(select(AgentPlanRow).order_by(AgentPlanRow.created_at))] == ["proposed", "capped"]
    other = project(planning.client, headers={access.HEADER: token(email="other@example.com")})
    scripted(monkeypatch, GOOD)
    assert a_plan(planning.client, other, **{access.HEADER: token(email="other@example.com")}).json()["state"] == "proposed"  # per person


@needs_test_database
def test_a_service_tokens_plans_are_not_counted(planning, monkeypatch):
    monkeypatch.setattr(app.state, "settings", dataclasses.replace(app.state.settings, agent_requests_per_user_per_day=1))
    service = {access.HEADER: service_token()}
    pid = project(planning.client, headers=service)
    scripted(monkeypatch, GOOD, GOOD)
    first, second = a_plan(planning.client, pid, **service).json(), a_plan(planning.client, pid, **service).json()
    assert (first["state"], second["state"], first["requests_left"], second["requests_left"]) == ("proposed", "proposed", None, None)
    assert [c.user_email for c in calls(planning.engine)] == [None, None]


@needs_test_database
def test_only_a_models_project_is_planned(planning):
    pid = project(planning.client, {"form": {"title": "a laminate"}}, kind="laminate")
    refused = planning.client.post(f"/v1/projects/{pid}/plans", json={"ask": ASK})
    assert refused.status_code == 422 and "no model to plan on" in refused.json()["detail"] and RUN_ID_HEADER in refused.headers
    for ask in ("", "   ", "x" * 1001):
        assert planning.client.post(f"/v1/projects/{pid}/plans", json={"ask": ask}).status_code == 422


@needs_test_database
def test_an_approval_applies_the_changes_as_a_version_checks_and_starts_the_run(planning, monkeypatch):
    scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    proposed = a_plan(planning.client, pid).json()
    approved = planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]})
    assert approved.status_code == 200, approved.text
    body = approved.json()
    has_keys(body, RUNNING)
    for part in ("plan", "project", "version", "job"):
        has_keys(body[part], RUNNING[part])
    has_keys(body["version"]["run"], RUNNING["version"]["run"])
    assert [s["state"] for s in body["plan"]["steps"]] == ["done", "done", "done", "running", "planned", "planned"]
    assert body["plan"]["state"] == "running" and body["plan"]["approved_at"] is not None and body["plan"]["requests_left"] == 29
    job = body["job"]
    assert job["state"] == "queued" and job["project_id"] == pid and job["user_email"] == EMAIL
    assert body["plan"]["job"] == job["job_id"] and approved.headers[ENQUEUE_HEADER] == job["job_id"]
    assert approved.headers["Location"] == f"/v1/coupon-jobs/{job['job_id']}" and approved.headers[RUN_ID_HEADER] == body["run_id"]
    version = body["version"]
    assert (version["n"], version["by"], version["why"], version["changes"]) == (1, "assistant", ASK, PROPOSED["done"])
    assert version["run"] == {"job": job["job_id"], "result": None} and body["plan"]["version"] == version
    assert version["plate"] == RUNNING["version"]["plate"] and body["project"]["content"]["plate"] == RUNNING["project"]["content"]["plate"]
    assert body["check"]["state"] == "ready" and body["project"]["designation"] == "IM7-PLT-L1"
    # the run is the one the page would start: its values as `workspaceValues` writes them, by "studio", no PDF, and every test for a plate
    values = planner.run_values(body["project"]["content"], app.state.settings.all_tests)
    assert values["supports"] == [{"region": "Edge-Bottom", "dofs": [1, 2, 3, 4, 5, 6]}] and values["loads"] == [{"region": "Edge-Top", "dof": 2, "total": 2000}]
    [seen] = [json.loads(line) for line in planning.seen.read_text(encoding="utf-8").splitlines()]
    assert seen == {"values": values, "every": True}
    with planning.engine.connect() as connection:
        source, options = connection.execute(text("SELECT source, options FROM jobs WHERE id = :id"), {"id": job["job_id"]}).one()
    assert json.loads(planning.store.objects[source][0]) == values
    assert options == ["--run-by", "A. Engineer", "--no-pdf", "--every-test"]  # a plate is offered every test (ADR-0089 amendment 8)
    assert planning.client.get(f"/v1/projects/{pid}/versions").json()[-1]["run"]["job"] == job["job_id"]


@needs_test_database
def test_a_plan_is_approved_once_and_never_over_a_changed_model(planning, monkeypatch):
    scripted(monkeypatch, GOOD, GOOD)
    pid = project(planning.client)
    first = a_plan(planning.client, pid).json()
    wrong = planning.client.post(f"/v1/projects/{pid}/plans/{first['id']}/approve", json={"base": "0" * 64})
    assert wrong.status_code == 409 and "changed since" in wrong.json()["detail"]
    assert planning.client.post(f"/v1/projects/{pid}/plans/{first['id']}/approve", json={"base": first["base"]}).status_code == 200
    twice = planning.client.post(f"/v1/projects/{pid}/plans/{first['id']}/approve", json={"base": first["base"]})
    assert twice.status_code == 409 and "approved already" in twice.json()["detail"]
    second = a_plan(planning.client, pid).json()  # worked out on the setup the first one made
    edited = planning.client.put(f"/v1/projects/{pid}", json={"kind": "fea", "name": "Bracket", "content": PLATE})
    assert edited.status_code == 200
    stale = planning.client.post(f"/v1/projects/{pid}/plans/{second['id']}/approve", json={"base": second["base"]})
    assert stale.status_code == 409 and "changed since" in stale.json()["detail"]
    assert planning.client.get(f"/v1/projects/{pid}/plans/{second['id']}").json()["state"] == "proposed"
    assert len(planning.client.get(f"/v1/projects/{pid}/versions").json()) == 1


@needs_test_database
def test_a_setup_check_that_does_not_pass_stops_the_plan_before_its_run(planning, monkeypatch):
    sentence = "free the bottom edge and run it"
    scripted(monkeypatch, plan(step("free", "free the bottom edge", region="Edge-Bottom"), step("run", "run it")))
    pid = project(planning.client, PULLED)
    proposed = a_plan(planning.client, pid, sentence).json()
    body = planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]}).json()
    assert body["plan"]["state"] == "stopped" and body["job"] is None and body["check"]["state"] == "blocked"
    assert [(s["tool"], s["state"]) for s in body["plan"]["steps"]] == [("free", "done"), ("check", "failed"), ("run", "skipped"), ("qa", "skipped")]
    assert body["plan"]["steps"][1]["note"] == "values.json: the plate is held nowhere, so it can move freely"
    assert body["version"]["n"] == 1 and body["version"]["run"] is None  # the change stands as a version; nothing ran


@needs_test_database
def test_a_busy_solver_or_the_days_cap_on_analyses_stops_the_plan_at_its_run(planning, monkeypatch):
    scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    proposed = a_plan(planning.client, pid).json()

    def busy(*_args, **_kwargs):
        raise JobBusy(uuid.uuid4())

    monkeypatch.setattr(planning.jobs, "start", busy)
    stopped = planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]})
    assert stopped.status_code == 200 and ENQUEUE_HEADER not in stopped.headers
    body = stopped.json()
    assert body["plan"]["state"] == "stopped" and body["job"] is None and body["check"]["state"] == "ready"
    assert [s["state"] for s in body["plan"]["steps"]] == ["done", "done", "done", "failed", "skipped", "skipped"]
    assert body["plan"]["steps"][3]["note"] == "Another analysis is running. Wait for it to finish, then run this one."


@needs_test_database
def test_a_persons_running_analysis_stops_the_next_plan_at_its_run(planning, monkeypatch):
    planning.jobs.per_day = 5  # the hosted tier's per-user limits: one running job a person
    scripted(monkeypatch, GOOD, GOOD)
    pid = project(planning.client)
    first = a_plan(planning.client, pid).json()
    assert planning.client.post(f"/v1/projects/{pid}/plans/{first['id']}/approve", json={"base": first["base"]}).json()["job"] is not None
    second = a_plan(planning.client, pid).json()
    body = planning.client.post(f"/v1/projects/{pid}/plans/{second['id']}/approve", json={"base": second["base"]}).json()
    assert body["plan"]["state"] == "stopped" and body["job"] is None and "still waiting to start" in body["plan"]["steps"][3]["note"]


@needs_test_database
def test_the_steps_the_page_carries_are_reported_until_the_plan_is_done(planning, monkeypatch):
    scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    proposed = a_plan(planning.client, pid).json()
    route = f"/v1/projects/{pid}/plans/{proposed['id']}/steps"
    early = planning.client.post(f"{route}/4", json={"state": "done"})
    assert early.status_code == 409 and "not approved" in early.json()["detail"]
    planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]})
    assert planning.client.post(f"{route}/4", json={"state": "done"}).json()["state"] == "running"
    assert planning.client.post(f"{route}/5", json={"state": "done", "note": "every check passes"}).json()["state"] == "running"
    done = planning.client.post(f"{route}/6", json={"state": "done"})
    assert done.status_code == 200 and done.json()["state"] == "done" and done.json()["steps"][4]["note"] == "every check passes"
    assert planning.client.post(f"{route}/6", json={"state": "done"}).status_code == 200  # the same report twice
    server = planning.client.post(f"{route}/3", json={"state": "done"})
    assert server.status_code == 409 and "the server's" in server.json()["detail"]
    assert planning.client.post(f"{route}/9", json={"state": "done"}).status_code == 404
    assert planning.client.post(f"{route}/6", json={"state": "planned"}).status_code == 422
    assert planning.client.get(f"/v1/projects/{pid}/plans/{proposed['id']}").json()["state"] == "done"


@needs_test_database
def test_a_failed_answer_stops_the_plan(planning, monkeypatch):
    scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    proposed = a_plan(planning.client, pid).json()
    planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]})
    route = f"/v1/projects/{pid}/plans/{proposed['id']}/steps"
    planning.client.post(f"{route}/4", json={"state": "done"})
    planning.client.post(f"{route}/5", json={"state": "done"})
    failed = planning.client.post(f"{route}/6", json={"state": "failed", "note": "the answer was set aside by its number guard"}).json()
    assert failed["state"] == "stopped" and failed["steps"][5]["note"] == "the answer was set aside by its number guard"


@needs_test_database
def test_a_coupons_plan_runs_the_tension_screens_values(planning, monkeypatch):
    sentence = "set the width to 20 mm and run it"
    scripted(monkeypatch, plan(step("row", "set the width to 20 mm", key="width", value="20", unit="mm"), step("run", "run it")))
    pid = project(planning.client, COUPON)
    proposed = a_plan(planning.client, pid, sentence).json()
    assert [s["role"] for s in proposed["steps"]] == ["Geometry", "Solver", "Solver", "QA"]
    body = planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]}).json()
    assert body["plan"]["state"] == "running" and body["project"]["content"]["form"]["width"] == "20"
    with planning.engine.connect() as connection:
        source, options = connection.execute(text("SELECT source, options FROM jobs WHERE id = :id"), {"id": body["job"]["job_id"]}).one()
    content = body["project"]["content"]
    sent = json.loads(planning.store.objects[source][0])
    assert sent == planner.run_values(content, app.state.settings.all_tests)
    if not app.state.settings.all_tests:  # the tension screen's own rows, as the page sends them
        assert sent == planner.tension_values(content["form"]) and sent["width"] == 20 and options == ["--run-by", "studio", "--no-pdf"]


@needs_test_database
def test_another_persons_plan_is_not_found(planning, monkeypatch):
    scripted(monkeypatch, GOOD)
    pid = project(planning.client)
    proposed = a_plan(planning.client, pid).json()
    other = {access.HEADER: token(email="other@example.com")}
    for answered in (planning.client.get(f"/v1/projects/{pid}/plans/{proposed['id']}", headers=other),
                     planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]}, headers=other),
                     planning.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/steps/4", json={"state": "done"}, headers=other),
                     planning.client.post(f"/v1/projects/{pid}/plans", json={"ask": ASK}, headers=other)):
        assert answered.status_code == 404
    elsewhere = project(planning.client)
    assert planning.client.get(f"/v1/projects/{elsewhere}/plans/{proposed['id']}").status_code == 404  # a plan is its own project's
    assert planning.client.get(f"/v1/projects/{pid}/plans/{uuid.uuid4()}").status_code == 404
    assert planning.client.get(f"/v1/projects/{pid}/plans/{proposed['id']}").json()["state"] == "proposed"
