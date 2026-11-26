"""The planner on a wing and on a repair (ADR-0144, build step 5): an engineer's sentence read by one call to the model into a plan of
the wing's or the repair's own tools, the checks that keep it or refuse it (the sweep's pick is the sweep's own, never a number the
model writes), the day's planned requests counted across every kind, and one approval that makes the changes and carries the runs.
The contract with the page is `tests/fixtures/planner/` (`wing-plan-proposed.json`, `wing-approve.json`, `repair-plan-proposed.json`,
`repair-approve.json`), written from these tests' answers with ANISOTROPY_WRITE_PLANNER_FIXTURES=1. A scripted client plays the
model, as api/tests/test_planner.py does, and a stand-in plays the fea package's repair tools, which need CalculiX: nothing here calls a
model or a solver."""

import dataclasses
import json
import os
import re
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from anisotropy_engine.repair import RepairSweep, sweep_repair
from anisotropy_engine.wing.changes import PlyChange, change_wing, preview_change
from anisotropy_api import access
from anisotropy_api import planner_kinds as kinds
from anisotropy_api import setup_tools as tools
from anisotropy_api.assistant import REPAIR_PLAN_SYSTEM, WING_PLAN_SYSTEM
from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import ENQUEUE_HEADER, RUN_ID_HEADER, SOLVER_ABSENT, STALE_WING, app, job_recorder
from anisotropy_api.records import STALE_REPAIR
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from memory_store import MemoryStore
from test_planner import GOOD, PLATE, calls, has_keys, project, scripted
from test_repairs_api import close
from test_repairs_api import example as repair_example
from test_wings_api import capped
from test_wings_api import example as wing_example

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "planner"
WRITE = "ANISOTROPY_WRITE_PLANNER_FIXTURES"
REPAIR_FIXTURES = ROOT / "tests" / "fixtures" / "repair"
PLANS = "/v1/workspace/repair-plans"

WING_ASK = "add 2 0-degree plies to the spar caps and run the check"  # the founder's
REPAIR_ASK = "find the smallest repair that stays elastic at 300 N/mm, then solve it"  # the founder's


def repair() -> dict:
    """The example repair with a thinner, stronger adhesive: the example itself keeps no step length elastic at 300 N/mm, so its sweep
    picks nothing there; this one's picks 4 mm."""
    return repair_example(adhesive__thickness=0.12, adhesive__shear_strength=36.0)


def args(names: tuple[str, ...], **given) -> dict:
    """A step's arguments as the schema has the model write them: every one, null where the tool takes none."""
    return {name: given.get(name) for name in names}


def wing_step(tool: str, quote: str, **given) -> dict:
    return {"tool": tool, "args": args(kinds.WING_ARGS, **given), "quote": quote}


def repair_step(tool: str, quote: str, **given) -> dict:
    return {"tool": tool, "args": args(kinds.REPAIR_ARGS, **given), "quote": quote}


def plan(*steps, question=None, unread=()) -> dict:
    return {"steps": list(steps), "question": question, "unread": list(unread)}


WING_GOOD = plan(wing_step("add_plies", "add 2 0-degree plies to the spar caps", part="spar_caps", angle="0", count="2"),
                 wing_step("check", "run the check"))
REPAIR_GOOD = plan(repair_step("sweep", "find the smallest repair that stays elastic at 300 N/mm", quantity="step_length", load="300",
                               load_unit="N/mm"),
                   repair_step("use_pick", "the smallest repair"),
                   repair_step("solve", "then solve it"))


def _refusal(work) -> Exception:
    """The engine's refusal of a piece of work, raised as its own route would read it."""
    try:
        work()
    except kinds.REFUSALS as exc:
        return exc
    raise AssertionError("the engine took it")


def with_args(raw: dict, n: int, **changed) -> dict:
    """The plan with step n's arguments changed (n from 1)."""
    copied = json.loads(json.dumps(raw))
    copied["steps"][n - 1]["args"].update(changed)
    return copied


# ------------------------------------------------------------------------------------------- what the model is shown and asked for

def test_the_model_sees_the_wings_parts_and_the_repairs_quantities_and_never_their_titles():
    wing = capped()
    view = kinds.wing_view(WING_ASK, wing)
    assert view["sentence"] == WING_ASK and [tool["name"] for tool in view["tools"]] == list(kinds.WING_TOOLS)
    assert [part["part"] for part in view["wing"]["parts"]] == ["skin", "spar", "spar_caps"]
    assert view["wing"]["parts"][2]["half_stack"] == [0, 0, 45, -45, 0] and wing["title"] not in json.dumps(view)
    assert [part["part"] for part in kinds.wing_view(WING_ASK, wing_example())["wing"]["parts"]] == ["skin", "spar"], "no caps, none on offer"
    item = kinds.wing_schema(wing)["properties"]["steps"]["items"]
    assert item["properties"]["tool"]["enum"] == list(kinds.WING_TOOLS)
    assert item["properties"]["args"]["properties"]["part"]["anyOf"][0]["enum"] == ["skin", "spar", "spar_caps"]
    assert item["properties"]["args"]["required"] == list(kinds.WING_ARGS)

    shown = kinds.repair_view(REPAIR_ASK, repair())
    assert [tool["name"] for tool in shown["tools"]] == list(kinds.REPAIR_TOOLS) and repair()["title"] not in json.dumps(shown)
    quantities = {q["quantity"]: q for q in shown["repair"]["quantities"]}
    assert quantities["step_length"]["value"] == 12.5 and quantities["step_length"]["unit"] == "mm"
    assert shown["repair"]["patch"] == "flush" and "source" not in json.dumps(shown)
    schema = kinds.repair_schema()
    assert schema["properties"]["steps"]["items"]["properties"]["args"]["required"] == list(kinds.REPAIR_ARGS)
    assert "minimum" not in json.dumps(schema) and "maxItems" not in json.dumps(schema)  # structured outputs take neither


# ------------------------------------------------------------------------------------------- a wing's plan

def test_the_founders_wing_sentence_is_the_engines_change_and_the_check():
    checked = kinds.check_wing_plan(WING_GOOD, WING_ASK, capped())
    assert checked.ok and checked.question is None
    change = PlyChange(action="add_plies", part="spar_caps", angle=0, count=2, start=0, end=1)
    assert [(s["n"], s["role"], s["tool"], s["regions"]) for s in checked.steps] == [(1, "Setup", "add_plies", ["spar_caps"]), (2, "Solver", "check", [])]
    assert checked.steps[0]["line"] == preview_change(capped(), change)["words"], "the line is the engine's own sentence"
    assert checked.steps[0]["change"] == change.model_dump(mode="json") and checked.steps[1]["change"] is None
    assert kinds.changed_wing(capped(), checked.steps) == change_wing(capped(), change)
    assert kinds.changed_wing(capped(), checked.steps[1:]) is None, "a plan with no change leaves the wing as it is"


def test_a_wing_number_not_in_the_sentence_is_refused():
    assert kinds.check_wing_plan(with_args(WING_GOOD, 1, count="4"), WING_ASK, capped()).reasons == [
        "step 1: 4 is not a number the sentence writes; a value is copied as written and the tools convert it"]
    assert kinds.check_wing_plan(with_args(WING_GOOD, 1, angle="90"), WING_ASK, capped()).reasons == [
        "step 1: 90 is not a number the sentence writes; a value is copied as written and the tools convert it"]
    assert kinds.check_wing_plan(with_args(WING_GOOD, 1, to="40"), WING_ASK, capped()).reasons == [
        "step 1: 40 is not a number the sentence writes; a value is copied as written and the tools convert it"]
    worded = "add two 0-degree plies to the spar caps from the root to 40% span"
    words = plan(wing_step("add_plies", "add two 0-degree plies to the spar caps from the root to 40% span", part="spar_caps", angle="0",
                           count="two", to="40"))
    kept = kinds.check_wing_plan(words, worded, capped())
    assert kept.ok and (kept.steps[0]["change"]["count"], kept.steps[0]["change"]["end"]) == (2, 0.4), "a count in words, a span in percent"


def test_an_unknown_part_and_a_change_after_the_check_are_refused():
    assert kinds.check_wing_plan(WING_GOOD, WING_ASK, wing_example()).reasons == [
        "step 1: spar_caps is not a part of this wing; it has skin, spar"]
    assert kinds.check_wing_plan(with_args(WING_GOOD, 1, part="ribs"), WING_ASK, capped()).reasons == [
        "step 1: ribs is not a part of this wing; it has skin, spar, spar_caps"]
    late = plan(WING_GOOD["steps"][1], WING_GOOD["steps"][0])
    assert kinds.check_wing_plan(late, WING_ASK, capped()).reasons == [
        "step 2: a change after the hand calculation or the check would not be in it: the changes come first"]
    twice = plan(*WING_GOOD["steps"], WING_GOOD["steps"][1])
    assert kinds.check_wing_plan(twice, WING_ASK, capped()).reasons == ["step 3: the plan runs the check once"]
    coupon = plan(wing_step("run", "run the check"))
    assert "'run' is not a tool on offer here" in kinds.check_wing_plan(coupon, WING_ASK, capped()).reasons[0]
    too_many = "take 12 0-degree plies out of the spar"
    removed = plan(wing_step("remove_plies", too_many, part="spar", angle="0", count="12"))
    refused = kinds.check_wing_plan(removed, too_many, capped()).reasons
    expected = str(_refusal(lambda: preview_change(capped(), PlyChange(action="remove_plies", part="spar", angle=0, count=12, start=0, end=1))))
    assert refused == [f"step 1: {expected}"], "the engine's own refusal: the spar has four 0° plies"


# ------------------------------------------------------------------------------------------- a repair's plan

def test_the_founders_repair_sentence_is_a_sweep_its_own_pick_and_the_solve():
    checked = kinds.check_repair_plan(REPAIR_GOOD, REPAIR_ASK, repair())
    assert checked.ok, checked.reasons
    found = sweep_repair(repair(), RepairSweep(quantity="step_length", load=300, load_unit="N/mm"))
    pick = found["rows"][found["pick"]]
    assert pick["value"] == 4.0 and pick["elastic"] is True and found["picked"]["steps"]["length"] == 4.0
    assert [(s["role"], s["tool"]) for s in checked.steps] == [("Solver", "sweep"), ("Geometry", "use_pick"), ("Solver", "solve")]
    sweep, use, solve = checked.steps
    assert sweep["line"] == "Sweep the step length, picking by its rule the smallest repair whose adhesive is still elastic at 300 N/mm"
    assert sweep["change"] == RepairSweep(quantity="step_length", load=300, load_unit="N/mm").model_dump(mode="json")
    assert use["line"] == "Use the sweep's pick: the step length goes from 12.5 mm to 4 mm."
    assert use["change"] == {"action": "set", "quantity": "step_length", "value": pick["value"], "unit": None, "count": None, "angles": None}
    assert solve["line"] == "Solve the slice of the repair as it then stands, and hold the sweep's pick to the load it names"
    assert solve["change"] == {"cut_faces": "open"}


def test_the_pick_is_the_sweeps_own_and_never_a_value_the_model_writes():
    given = with_args(REPAIR_GOOD, 2, quantity="step_length", value="300", unit="mm")
    assert kinds.check_repair_plan(given, REPAIR_ASK, repair()).reasons == [
        "step 2: the pick is the sweep's own: use_pick takes no value, and this one gives value, unit"]
    alone = plan(repair_step("use_pick", "the smallest repair"), repair_step("solve", "then solve it"))
    assert kinds.check_repair_plan(alone, REPAIR_ASK, repair()).reasons == [
        "step 1: use_pick takes the pick of the sweep just before it, and there is none"]
    unloaded = with_args(REPAIR_GOOD, 1, load=None, load_unit=None)
    assert kinds.check_repair_plan(unloaded, REPAIR_ASK, repair()).reasons == [
        "step 2: the sweep before it names no load, so it picks nothing: a pick is the smallest repair whose adhesive stays elastic at a load"]
    invented = plan(repair_step("set", "find the smallest repair", quantity="step_length", value="4", unit="mm"), repair_step("solve", "then solve it"))
    assert kinds.check_repair_plan(invented, REPAIR_ASK, repair()).reasons == [
        "step 1: 4 is not a number the sentence writes; a value is copied as written and the tools convert it"]
    nothing = kinds.check_repair_plan(REPAIR_GOOD, REPAIR_ASK, repair_example())  # the example keeps no step length elastic at 300 N/mm
    answer = sweep_repair(repair_example(), RepairSweep(quantity="step_length", load=300, load_unit="N/mm"))["answer"]
    assert nothing.reasons == [f"step 2: the sweep picks nothing to use: {' '.join(answer)}"] and answer[0].startswith("None of these keeps")


def test_a_repair_number_or_unit_not_in_the_sentence_and_a_solve_that_needs_a_value_are_refused():
    assert kinds.check_repair_plan(with_args(REPAIR_GOOD, 1, load="0.3", load_unit="kN/mm"), REPAIR_ASK, repair()).reasons == [
        "step 1: 0.3 is not a number the sentence writes; a value is copied as written and the tools convert it",
        "step 1: the unit kN/mm is not written in the sentence"]
    assert kinds.check_repair_plan(with_args(REPAIR_GOOD, 1, load_unit=None), REPAIR_ASK, repair()).reasons == [
        "step 1: the sentence writes 300 N/mm, and the step gives it with no unit"]
    loose = repair()
    loose["adhesive"].pop("poisson")
    assert kinds.check_repair_plan(REPAIR_GOOD, REPAIR_ASK, loose).reasons == [
        "step 3: The solve of the slice needs: the adhesive's Poisson's ratio."]
    after = plan(*REPAIR_GOOD["steps"], repair_step("sweep", "find the smallest repair", quantity="bondline"))
    assert kinds.check_repair_plan(after, REPAIR_ASK, repair()).reasons == [
        "step 4: a change or a sweep after the solve or the bond would not be in it: they come first"]


def test_a_repairs_digest_is_the_same_description_through_the_browsers_json():
    stated = repair()
    assert kinds.repair_digest(stated) == kinds.repair_digest(json.loads(json.dumps(stated)))
    floated = json.loads(json.dumps(stated))
    floated["applied"]["load"] = float(floated["applied"]["load"])
    assert kinds.repair_digest(floated) == kinds.repair_digest(stated), "100.0 is 100"
    floated["applied"]["load"] += 1
    assert kinds.repair_digest(floated) != kinds.repair_digest(stated)


# ------------------------------------------------------------------------------------------- the routes

STAND_IN = r'''
"""A stand-in for the fea package's repair tools, which need CalculiX: the slice's solve answers the example's real solve
(tests/fixtures/repair/example-solve.json) and the bond the example's real bond (example-bond.json), whatever repair it is given, with
the cut faces it is given; what it was given is written down for the test."""
import json, pathlib, sys
stated = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
with open(SEEN, "a", encoding="utf-8") as seen:
    seen.write(json.dumps({"repair": stated, "options": sys.argv[2:]}) + "\n")
out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1])
out.mkdir(parents=True)
solve = "--cut-faces" in sys.argv
kept = json.loads((pathlib.Path(FIXTURES) / ("example-solve.json" if solve else "example-bond.json")).read_text(encoding="utf-8"))
report = {"headline": kept["headline"], **kept["report"]}
if solve:
    report["model"]["cut_faces"] = sys.argv[sys.argv.index("--cut-faces") + 1]
(out / ("repair-solve.json" if solve else "repair-bond.json")).write_text(json.dumps(report), encoding="utf-8")
'''


@pytest.fixture
def kinds_api(empty_runs, monkeypatch, tmp_path):
    """The API behind Cloudflare Access with run records on, the job queue's front (a wing's check waits there for a solver), a
    stand-in for the repair tools, and no model until a test scripts one."""
    import anisotropy_api.main as main_module
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    seen = tmp_path / "seen.jsonl"
    stand_in = tmp_path / "repair_tools.py"
    stand_in.write_text(STAND_IN.replace("SEEN", repr(str(seen)), 1).replace("FIXTURES)", f"{str(REPAIR_FIXTURES)!r})", 1), encoding="utf-8")
    for name in ("repair_model_command", "repair_bond_command"):
        monkeypatch.setattr(main_module, name, lambda: [sys.executable, str(stand_in)])
    from anisotropy_api.assistant import TemplateAssistant
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser", access.HEADER: token()}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        jobs = CouponJobs([sys.executable, "-c", "pass"], job_recorder(app), tmp_path / "jobs", store=MemoryStore(), table=empty_runs, role="queue")
        monkeypatch.setattr(app.state, "coupon_jobs", jobs, raising=False)
        monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
        yield SimpleNamespace(client=client, jobs=jobs, engine=empty_runs, seen=seen, main=main_module)


def solved(seen: Path) -> list[dict]:
    """What the stand-in was given, in order."""
    return [json.loads(line) for line in seen.read_text(encoding="utf-8").splitlines()] if seen.exists() else []


def run_of(engine, run_id: str):
    with engine.connect() as connection:
        return connection.execute(text("SELECT endpoint, status, inputs, response, llm_provider FROM runs WHERE id = :id"), {"id": run_id}).one()


_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def fixed(body: dict) -> dict:
    """An answer as the contract keeps it: each id another fixed one by its order, and each time one time, so the file holds still."""
    ids: dict[str, str] = {}

    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str) and _ID.match(value):
            return ids.setdefault(value, f"5d1f2c3a-7777-4888-9999-{len(ids) + 1:012d}")
        if isinstance(value, str) and _TIME.match(value):
            return "2026-11-26T09:00:00+00:00"
        return value

    return walk(body)


def contract(name: str, body: dict) -> dict:
    """The contract's file for this answer, written from it with ANISOTROPY_WRITE_PLANNER_FIXTURES=1, and held to it otherwise: the same
    keys and values (numbers to a part in a billion), every id and time aside, the engine's version, which moves with each release, and
    how long a hand calculation took (`seconds`), which differs each time."""
    path, ours = FIXTURES / name, fixed(body)
    if os.environ.get(WRITE) == "1":
        path.write_text(json.dumps(ours, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    assert path.exists(), f"no {name}: run these tests with {WRITE}=1"
    kept = json.loads(path.read_text(encoding="utf-8"))

    def aside(value):
        if isinstance(value, dict):
            return {key: aside(item) for key, item in value.items() if key not in ("engine_version", "seconds")}
        if isinstance(value, list):
            return [aside(item) for item in value]
        return value

    assert close(aside(ours), aside(kept)), f"{name} is not this answer: if the change is meant, run these tests with {WRITE}=1"
    return kept


def a_wing_plan(client, pid: str, ask: str = WING_ASK, **headers):
    asked = client.post(f"/v1/projects/{pid}/plans", json={"ask": ask}, headers=headers)
    assert asked.status_code == 200, asked.text
    return asked


def a_repair_plan(client, stated: dict | None = None, ask: str = REPAIR_ASK, **headers):
    asked = client.post(PLANS, json={"ask": ask, "repair": repair() if stated is None else stated}, headers=headers)
    assert asked.status_code == 200, asked.text
    return asked


@needs_test_database
def test_the_founders_wing_example_end_to_end(kinds_api, monkeypatch):
    model = scripted(monkeypatch, WING_GOOD)
    client = kinds_api.client
    pid = project(client, {"wing": capped()}, kind="wing")
    asked = a_wing_plan(client, pid)
    body = asked.json()
    kept = contract("wing-plan-proposed.json", body)
    has_keys(body, kept)
    assert (body["state"], body["kind"], body["project"], body["ask"], body["writer"]) == ("proposed", "wing", pid, WING_ASK, "anthropic")
    assert body["base"] == tools.content_digest({"wing": capped()}) and body["requests_left"] == 29 and body["run_id"] == asked.headers[RUN_ID_HEADER]
    assert body["steps"] == kinds.check_wing_plan(WING_GOOD, WING_ASK, capped()).steps and body["done"] == [body["steps"][0]["line"]]
    [request] = model.asked
    assert request["system"] == WING_PLAN_SYSTEM and request["output_config"]["format"]["schema"] == kinds.wing_schema(capped())
    shown = request["messages"][0]["content"]
    assert "spar_caps" in shown and capped()["title"] not in shown and EMAIL not in shown and pid not in shown  # R-11
    [call] = calls(kinds_api.engine)
    assert (call.feature, call.user_email, str(call.run_id)) == ("plan_steps", EMAIL, body["run_id"])

    approved = client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": body["base"]})
    assert approved.status_code == 200, approved.text
    done = approved.json()
    kept = contract("wing-approve.json", done)
    has_keys(done, kept)
    for part in ("plan", "project"):
        has_keys(done[part], kept[part])
    change = PlyChange(**body["steps"][0]["change"])
    assert done["project"]["content"]["wing"] == change_wing(capped(), change), "the project's wing is the engine's change of it"
    assert client.get(f"/v1/projects/{pid}").json()["content"]["wing"] == change_wing(capped(), change)
    assert done["version"] is None and done["job"] is None and done["check"] is None, "a wing's versions are the browser's (ADR-0122)"
    [run] = done["runs"]
    job = run["answer"]
    assert (run["n"], run["tool"], job["state"]) == (2, "check", "queued") and done["plan"]["job"] == job["job_id"]
    assert approved.headers["Location"] == f"/v1/wings/checks/{job['job_id']}" and approved.headers[ENQUEUE_HEADER] == job["job_id"]
    listed = client.get(f"/v1/projects/{pid}").json()["jobs"]
    assert [(j["job_id"], j["state"]) for j in listed] == [(job["job_id"], "queued")], "the check is the project's"
    assert [s["state"] for s in done["plan"]["steps"]] == ["done", "running"] and done["plan"]["state"] == "running"
    record = run_of(kinds_api.engine, done["run_id"])
    assert record.endpoint == "/v1/projects/{project_id}/plans/{plan_id}/approve" and record.status == "solved"
    assert record.response["runs"] == [{"n": 2, "tool": "check", "answer": {"job_id": job["job_id"], "state": "queued", "message": job["message"]}}]

    again = client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": body["base"]})
    assert again.status_code == 409, "approved once"
    server = client.post(f"/v1/projects/{pid}/plans/{body['id']}/steps/1", json={"state": "done"})
    assert server.status_code == 409 and "the server's to carry out" in server.json()["detail"]
    reported = client.post(f"/v1/projects/{pid}/plans/{body['id']}/steps/2", json={"state": "done", "note": "lowest margin 0.146 in case 6"})
    assert reported.status_code == 200 and reported.json()["state"] == "done" and reported.json()["steps"][1]["note"] == "lowest margin 0.146 in case 6"


@needs_test_database
def test_a_wing_worked_by_hand_answers_the_routes_own_answer_and_needs_no_solver(kinds_api, monkeypatch):
    ask = "add 2 0-degree plies to the spar caps and work it by hand"
    scripted(monkeypatch, plan(wing_step("add_plies", "add 2 0-degree plies to the spar caps", part="spar_caps", angle="0", count="2"),
                               wing_step("analyze", "work it by hand")))
    monkeypatch.setattr(app.state, "coupon_jobs", None)  # no solver here: the hand calculation runs all the same
    client = kinds_api.client
    pid = project(client, {"wing": capped()}, kind="wing")
    body = a_wing_plan(client, pid, ask).json()
    done = client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": body["base"]})
    assert done.status_code == 200, done.text
    [run] = done.json()["runs"]
    wing = done.json()["project"]["content"]["wing"]
    direct = client.post("/v1/wings/analyze", json={"wing": wing}).json()
    assert run["tool"] == "analyze" and set(run["answer"]) == {"engine_version", "wing", "report", "views"}
    timed = lambda report: {key: value for key, value in report.items() if key != "seconds"}  # noqa: E731 - how long it took differs
    assert run["answer"]["wing"] == wing and close(timed(run["answer"]["report"]), timed(direct["report"])), "the hand calculation of the changed wing"
    assert done.json()["plan"]["state"] == "done" and [s["state"] for s in done.json()["plan"]["steps"]] == ["done", "done"]
    record = run_of(kinds_api.engine, done.json()["run_id"])
    assert record.response["runs"][0]["answer"]["passes"] == direct["report"]["passes"] and "views" not in json.dumps(record.response)


@needs_test_database
def test_a_wing_changed_since_its_plan_is_not_changed_again(kinds_api, monkeypatch):
    scripted(monkeypatch, WING_GOOD)
    client = kinds_api.client
    pid = project(client, {"wing": capped()}, kind="wing")
    body = a_wing_plan(client, pid).json()
    assert client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": "0" * 64}).status_code == 409
    edited = {**capped(), "spar_caps": {"front_width": 0.05, "rear_width": 0.045, "half_stack": [0, 0, 45, -45, 0]}}
    assert client.put(f"/v1/projects/{pid}", json={"kind": "wing", "name": "Wing", "content": {"wing": edited}}).status_code == 200
    stale = client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": body["base"]})
    assert stale.status_code == 409 and stale.json()["detail"] == STALE_WING
    assert client.get(f"/v1/projects/{pid}").json()["content"]["wing"] == edited and kinds_api.jobs.jobs == {}
    assert client.get(f"/v1/projects/{pid}/plans/{body['id']}").json()["state"] == "proposed"


@needs_test_database
def test_a_wing_check_past_the_days_analyses_stops_the_plan_at_its_step(kinds_api, monkeypatch):
    scripted(monkeypatch, WING_GOOD)
    monkeypatch.setattr(kinds_api.jobs, "per_day", 0)
    client = kinds_api.client
    pid = project(client, {"wing": capped()}, kind="wing")
    body = a_wing_plan(client, pid).json()
    done = client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": body["base"]})
    assert done.status_code == 200, done.text
    plan_now = done.json()["plan"]
    assert plan_now["state"] == "stopped" and [s["state"] for s in plan_now["steps"]] == ["done", "failed"] and plan_now["steps"][1]["note"]
    assert done.json()["runs"] == [] and plan_now["job"] is None


@needs_test_database
def test_a_wing_the_engine_cannot_read_is_not_planned(kinds_api, monkeypatch):
    model = scripted(monkeypatch, WING_GOOD)
    pid = project(kinds_api.client, {"wing": {**capped(), "units": "furlongs"}}, kind="wing")
    refused = kinds_api.client.post(f"/v1/projects/{pid}/plans", json={"ask": WING_ASK})
    assert refused.status_code == 422 and refused.json()["detail"].startswith("The wing cannot be read") and model.asked == []
    laminate = project(kinds_api.client, {"form": {"title": "a laminate"}}, kind="laminate")
    assert kinds_api.client.post(f"/v1/projects/{laminate}/plans", json={"ask": WING_ASK}).status_code == 422


@needs_test_database
def test_the_wing_cards_contract_a_change_worked_by_hand_checked_and_answered(kinds_api, monkeypatch):
    """The wing page's plan card (ADR-0144, step 5, page) is mocked from this plan: a change, the hand calculation, the check and an
    answer, proposed and approved."""
    ask = "add 2 0-degree plies to the spar caps, work it by hand, run the check and tell me the lowest margin"
    scripted(monkeypatch, plan(wing_step("add_plies", "add 2 0-degree plies to the spar caps", part="spar_caps", angle="0", count="2"),
                               wing_step("analyze", "work it by hand"), wing_step("check", "run the check"),
                               wing_step("answer", "tell me the lowest margin", question="What is the lowest margin?")))
    client = kinds_api.client
    pid = project(client, {"wing": capped()}, kind="wing")
    body = a_wing_plan(client, pid, ask).json()
    contract("wing-plan-answered.json", body)
    assert body["state"] == "proposed", body["reason"]
    assert [(s["role"], s["tool"]) for s in body["steps"]] == [("Setup", "add_plies"), ("Solver", "analyze"), ("Solver", "check"), ("Report", "answer")]
    assert body["steps"][3]["line"] == "Answer: what is the lowest margin?"
    approved = client.post(f"/v1/projects/{pid}/plans/{body['id']}/approve", json={"base": body["base"]})
    assert approved.status_code == 200, approved.text
    done = approved.json()
    contract("wing-approve-answered.json", done)
    analyze, check = done["runs"]
    assert (analyze["n"], analyze["tool"], check["n"], check["tool"]) == (2, "analyze", 3, "check")
    assert analyze["answer"]["wing"] == done["project"]["content"]["wing"], "the hand calculation is of the wing the plan leaves"
    assert check["answer"]["state"] == "queued" and done["plan"]["job"] == check["answer"]["job_id"]
    assert [s["state"] for s in done["plan"]["steps"]] == ["done", "done", "running", "planned"] and done["plan"]["state"] == "running"


@needs_test_database
def test_a_wing_plan_the_engine_cannot_make_is_refused_in_its_words(kinds_api, monkeypatch):
    """The wing page shows a refused plan's reason (ADR-0144, step 5, page): the engine's own words for the change it cannot make."""
    ask = "remove 2 90-degree plies from the skin and run the check"
    steps = plan(wing_step("remove_plies", "remove 2 90-degree plies from the skin", part="skin", angle="90", count="2"), wing_step("check", "run the check"))
    model = scripted(monkeypatch, steps, steps)
    client = kinds_api.client
    pid = project(client, {"wing": capped()}, kind="wing")
    body = a_wing_plan(client, pid, ask).json()
    contract("wing-plan-refused.json", body)
    assert (body["state"], body["kind"], body["steps"]) == ("refused", "wing", []) and len(model.asked) == 2, "asked again with the reasons, then refused"
    assert body["reason"] == "step 1: [0/45/-45/0]s has 0 plies at 90°: 2 cannot be taken out."
    assert client.get(f"/v1/projects/{pid}").json()["content"]["wing"] == capped(), "nothing changes"


@needs_test_database
def test_the_founders_repair_example_end_to_end(kinds_api, monkeypatch):
    model = scripted(monkeypatch, REPAIR_GOOD)
    client = kinds_api.client
    asked = a_repair_plan(client)
    body = asked.json()
    kept = contract("repair-plan-proposed.json", body)
    has_keys(body, kept)
    assert (body["state"], body["kind"], body["project"], body["ask"], body["writer"]) == ("proposed", "repair", None, REPAIR_ASK, "anthropic")
    assert body["base"] == kinds.repair_digest(repair()) and body["requests_left"] == 29 and body["run_id"] == asked.headers[RUN_ID_HEADER]
    assert body["steps"] == kinds.check_repair_plan(REPAIR_GOOD, REPAIR_ASK, repair()).steps
    assert body["done"] == [body["steps"][1]["line"]], "the pick is the plan's one change"
    [request] = model.asked
    assert request["system"] == REPAIR_PLAN_SYSTEM and request["output_config"]["format"]["schema"] == kinds.repair_schema()
    assert repair()["title"] not in request["messages"][0]["content"] and EMAIL not in request["messages"][0]["content"]
    record = run_of(kinds_api.engine, body["run_id"])
    assert (record.endpoint, record.llm_provider) == (PLANS, "anthropic") and record.inputs["ask"] == REPAIR_ASK
    assert client.get(f"{PLANS}/{body['id']}").json()["steps"] == body["steps"]
    assert solved(kinds_api.seen) == [], "nothing runs before the approval"

    approved = client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": body["base"]})
    assert approved.status_code == 200, approved.text
    done = approved.json()
    kept = contract("repair-approve.json", done)
    has_keys(done, kept)
    has_keys(done["plan"], kept["plan"])
    found = sweep_repair(repair(), RepairSweep(quantity="step_length", load=300, load_unit="N/mm"))
    assert done["repair"] == found["picked"] and done["repair"]["steps"]["length"] == 4.0, "the repair is the sweep's own pick"
    [given] = solved(kinds_api.seen)
    assert given["repair"] == found["picked"] and given["options"][-2:] == ["--cut-faces", "open"], "the slice solved is the pick"
    sweep, solve = done["runs"]
    assert (sweep["n"], sweep["tool"], solve["n"], solve["tool"]) == (1, "sweep", 3, "solve")
    assert close(sweep["answer"]["rows"], found["rows"]) and sweep["answer"]["pick"] == found["pick"] and sweep["answer"]["check"] is None
    assert sweep["answer"]["answer"] == found["answer"] and sweep["answer"]["target"] == 300.0
    solve_kept = json.loads((REPAIR_FIXTURES / "example-solve.json").read_text(encoding="utf-8"))
    assert solve["answer"]["headline"] == solve_kept["headline"] and "headline" not in solve["answer"]["report"]
    check = solve["answer"]["check"]
    assert check["state"] == "solved" and check["headline"] == solve_kept["headline"]
    assert check["holds"] is (solve_kept["report"]["first"]["load"] >= 300.0), "the sweep's own check of its pick, at the load it named"
    assert [s["state"] for s in done["plan"]["steps"]] == ["done", "done", "done"] and done["plan"]["state"] == "done"
    assert done["run_id"] == approved.headers[RUN_ID_HEADER]
    record = run_of(kinds_api.engine, done["run_id"])
    assert record.endpoint == PLANS + "/{plan_id}/approve" and record.status == "solved"
    runs = record.response["runs"]
    assert runs[0]["answer"]["rows"] == len(found["rows"]) and runs[0]["answer"]["pick"]["value"] == 4.0, "a sweep's record keeps its pick, not every row"
    assert runs[1]["answer"]["check"]["state"] == "solved" and "lines" not in json.dumps(runs[1]), "a solve's record keeps its headline numbers"
    assert client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": body["base"]}).status_code == 409, "approved once"


@needs_test_database
def test_the_repair_cards_contract_a_sweep_its_pick_the_solve_the_bond_and_an_answer(kinds_api, monkeypatch):
    """The repair page's plan card (ADR-0144, step 5, page) is mocked from this plan: every run a repair's approval carries, and an answer
    the page gives, proposed and approved."""
    ask = "find the smallest repair that stays elastic at 300 N/mm, solve it, follow the bond and tell me what fails first"
    scripted(monkeypatch, plan(REPAIR_GOOD["steps"][0], REPAIR_GOOD["steps"][1], repair_step("solve", "solve it"), repair_step("bond", "follow the bond"),
                               repair_step("answer", "tell me what fails first", question="What fails first?")))
    client = kinds_api.client
    body = a_repair_plan(client, ask=ask).json()
    contract("repair-plan-answered.json", body)
    assert body["state"] == "proposed", body["reason"]
    assert [(s["role"], s["tool"]) for s in body["steps"]] == [("Solver", "sweep"), ("Geometry", "use_pick"), ("Solver", "solve"), ("Solver", "bond"),
                                                               ("Report", "answer")]
    approved = client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": body["base"]})
    assert approved.status_code == 200, approved.text
    done = approved.json()
    contract("repair-approve-answered.json", done)
    assert [(r["n"], r["tool"]) for r in done["runs"]] == [(1, "sweep"), (3, "solve"), (4, "bond")]
    assert done["repair"] == done["runs"][0]["answer"]["picked"] and [given["repair"] for given in solved(kinds_api.seen)] == [done["repair"]] * 2
    assert [s["state"] for s in done["plan"]["steps"]] == ["done", "done", "done", "done", "planned"] and done["plan"]["state"] == "running"


@needs_test_database
def test_a_repair_plan_whose_sweep_picks_nothing_is_refused_in_the_engines_words(kinds_api, monkeypatch):
    """The founder's sentence on the stock example (ADR-0144, step 5, page): no step length keeps its adhesive elastic at 300 N/mm, so
    the plan is refused with the sweep's own answer, and the page shows it."""
    ask = "find the shortest step length that stays elastic at 300 N/mm and solve it"
    steps = plan(repair_step("sweep", "find the shortest step length that stays elastic at 300 N/mm", quantity="step_length", load="300", load_unit="N/mm"),
                 repair_step("use_pick", "the shortest step length"), repair_step("solve", "solve it"))
    model = scripted(monkeypatch, steps, steps)
    body = a_repair_plan(kinds_api.client, repair_example(), ask).json()
    contract("repair-plan-refused.json", body)
    found = sweep_repair(repair_example(), RepairSweep(quantity="step_length", load=300, load_unit="N/mm"))
    assert found["pick"] is None and found["answer"][0].startswith("None of these keeps")
    assert (body["state"], body["kind"], body["project"], body["steps"]) == ("refused", "repair", None, []) and len(model.asked) == 2
    assert body["reason"] == f"step 2: the sweep picks nothing to use: {' '.join(found['answer'])}"
    assert solved(kinds_api.seen) == [], "nothing runs"


@needs_test_database
def test_a_repair_changed_since_its_plan_is_409_and_nothing_runs(kinds_api, monkeypatch):
    scripted(monkeypatch, REPAIR_GOOD)
    client = kinds_api.client
    body = a_repair_plan(client).json()
    changed = repair()
    changed["steps"]["length"] = 10.0
    stale = client.post(f"{PLANS}/{body['id']}/approve", json={"repair": changed, "base": body["base"]})
    assert stale.status_code == 409 and stale.json()["detail"] == STALE_REPAIR
    other = client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": kinds.repair_digest(changed)})
    assert other.status_code == 409 and other.json()["detail"] == STALE_REPAIR
    assert solved(kinds_api.seen) == [] and client.get(f"{PLANS}/{body['id']}").json()["state"] == "proposed"
    browsers = json.loads(json.dumps(repair()))
    browsers["applied"]["load"] = float(browsers["applied"]["load"])  # 100.0 from the browser is the plan's 100
    assert client.post(f"{PLANS}/{body['id']}/approve", json={"repair": browsers, "base": body["base"]}).status_code == 200


@needs_test_database
def test_a_repair_plans_answer_is_reported_by_the_page_and_the_plan_is_its_owners(kinds_api, monkeypatch):
    ask = "find the smallest repair that stays elastic at 300 N/mm, solve it and tell me what fails first"
    scripted(monkeypatch, plan(*REPAIR_GOOD["steps"][:2], repair_step("solve", "solve it"),
                               repair_step("answer", "tell me what fails first", question="What fails first?")))
    client = kinds_api.client
    body = a_repair_plan(client, ask=ask).json()
    assert body["state"] == "proposed", body["reason"]
    theirs = {access.HEADER: token(email="other@example.com")}
    assert client.get(f"{PLANS}/{body['id']}", headers=theirs).status_code == 404
    assert client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": body["base"]}, headers=theirs).status_code == 404
    assert client.post(f"{PLANS}/{body['id']}/steps/4", json={"state": "done"}).status_code == 409, "not approved yet"
    done = client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": body["base"]}).json()
    assert done["plan"]["state"] == "running" and [s["state"] for s in done["plan"]["steps"]] == ["done", "done", "done", "planned"]
    assert client.post(f"{PLANS}/{body['id']}/steps/1", json={"state": "done"}).status_code == 409, "the sweep is the server's"
    answered = client.post(f"{PLANS}/{body['id']}/steps/4", json={"state": "done", "note": "the adhesive, in shear"})
    assert answered.status_code == 200 and answered.json()["state"] == "done"
    project_route = client.get(f"/v1/projects/{uuid.uuid4()}/plans/{body['id']}")
    assert project_route.status_code == 404, "a repair's plan is read at its own route"


@needs_test_database
def test_a_repair_the_engine_refuses_and_a_server_with_no_solver(kinds_api, monkeypatch):
    model = scripted(monkeypatch, REPAIR_GOOD)
    client = kinds_api.client
    unread = repair()
    unread["steps"]["length"] = -1
    refused = client.post(PLANS, json={"ask": REPAIR_ASK, "repair": unread})
    assert refused.status_code == 422 and model.asked == [] and RUN_ID_HEADER in refused.headers
    assert client.post(PLANS, json={"ask": REPAIR_ASK, "repair": {}}).status_code == 422
    body = a_repair_plan(client).json()
    monkeypatch.setattr(kinds_api.main, "repair_model_command", lambda: None)
    absent = client.post(f"{PLANS}/{body['id']}/approve", json={"repair": repair(), "base": body["base"]})
    assert absent.status_code == 503 and absent.json()["detail"] == SOLVER_ABSENT
    assert client.get(f"{PLANS}/{body['id']}").json()["state"] == "proposed", "nothing is approved before a planned solve can run"


@needs_test_database
def test_the_days_planned_requests_are_counted_across_every_kind(kinds_api, monkeypatch):
    monkeypatch.setattr(app.state, "settings", dataclasses.replace(app.state.settings, agent_requests_per_user_per_day=2))
    model = scripted(monkeypatch, GOOD, WING_GOOD, REPAIR_GOOD)
    client = kinds_api.client
    plate = project(client, PLATE)
    assert client.post(f"/v1/projects/{plate}/plans", json={"ask": "clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds"}) \
        .json()["requests_left"] == 1
    wing = a_wing_plan(client, project(client, {"wing": capped()}, kind="wing")).json()
    assert (wing["state"], wing["requests_left"]) == ("proposed", 0)
    capped_plan = a_repair_plan(client).json()
    assert (capped_plan["state"], capped_plan["kind"], capped_plan["requests_left"], capped_plan["steps"]) == ("capped", "repair", 0, [])
    assert len(model.asked) == 2 and len(calls(kinds_api.engine)) == 2, "past the cap no model is called"
    with kinds_api.engine.connect() as connection:
        rows = connection.execute(text("SELECT kind, state FROM agent_plans ORDER BY created_at")).all()
    assert [tuple(row) for row in rows] == [("plate", "proposed"), ("wing", "proposed"), ("repair", "capped")]


@needs_test_database
def test_with_no_model_a_repair_plan_is_unavailable_and_a_service_tokens_are_not_counted(kinds_api, monkeypatch):
    body = a_repair_plan(kinds_api.client).json()
    assert (body["state"], body["writer"], body["model"], body["requests_left"]) == ("unavailable", "template", None, 30)
    assert calls(kinds_api.engine) == []
    monkeypatch.setattr(app.state, "settings", dataclasses.replace(app.state.settings, agent_requests_per_user_per_day=1))
    scripted(monkeypatch, REPAIR_GOOD, REPAIR_GOOD)
    service = {access.HEADER: service_token()}
    first, second = a_repair_plan(kinds_api.client, **service).json(), a_repair_plan(kinds_api.client, **service).json()
    assert (first["state"], second["state"], first["requests_left"], second["requests_left"]) == ("proposed", "proposed", None, None)
    assert kinds_api.client.get(f"{PLANS}/{first['id']}", headers=service).status_code == 200
    assert kinds_api.client.get(f"{PLANS}/{first['id']}").status_code == 404, "a service token's plan is not a person's"


@needs_test_database
def test_a_repairs_plan_has_no_project_and_a_projects_plan_has_one(kinds_api):
    insert = text("INSERT INTO agent_plans (id, kind, project_id, actor, ask, state, steps, base, unread, writer, created_at, updated_at) "
                  "VALUES (:id, :kind, NULL, 'browser', 'x', 'proposed', '[]', :base, '[]', 'template', now(), now())")
    with kinds_api.engine.begin() as connection:
        connection.execute(insert, {"id": str(uuid.uuid4()), "kind": "repair", "base": "0" * 64})
    for kind in ("wing", "beam"):
        with pytest.raises(IntegrityError), kinds_api.engine.begin() as connection:
            connection.execute(insert, {"id": str(uuid.uuid4()), "kind": kind, "base": "0" * 64})
