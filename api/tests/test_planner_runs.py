"""The run of a coupon's or a plate's plan is the server's (ADR-0144 amendment 2): the approval starts it as a job, and the job's own
outcome settles the run step, whether or not a page is open and whatever a page reports. So a plan reaches its end on the server:
`done` once its last step is done, `stopped` when the run fails. A scripted client plays the model, as in api/tests/test_planner.py;
nothing here calls one."""

import datetime as dt
import json
import sys
import time
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from anisotropy_api import access, planner
from anisotropy_api import main as api_main
from anisotropy_api import records
from anisotropy_api.assistant import TemplateAssistant
from anisotropy_api.coupon_jobs import CouponJobs, JobBusy
from anisotropy_api.main import ENQUEUE_HEADER, app, job_recorder
from anisotropy_api.records import AgentPlanRow
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, TEAM, key_for, token
from conftest import TEST_URL, needs_test_database
from memory_store import MemoryStore
from test_planner import ASK, GOOD, PLATE, PROPOSED, STUDIO, a_plan, plan, project, scripted, step

APPROVED = ["done", "done", "done", "running", "planned", "planned"]  # as an approval leaves the contract's plan: the run under way


def steps_as(*states: str) -> list[dict]:
    """The contract's plan of six steps (two changes, the check, the run, the QA, the answer) with these states."""
    steps = json.loads(json.dumps(PROPOSED["steps"]))
    for one, now in zip(steps, states):
        one["state"] = now
    return steps


def states(of: dict | list) -> list[str]:
    return [one["state"] for one in (of["steps"] if isinstance(of, dict) else of)]


# ------------------------------------------------------------------------------------------- the rules, with no database

def test_the_run_is_settled_from_its_jobs_own_outcome():
    steps = steps_as(*APPROVED)
    assert planner.run_ended(steps, True) == "running" and states(steps) == ["done", "done", "done", "done", "planned", "planned"]
    assert planner.run_ended(steps, False) is None and states(steps)[3] == "done"  # settled once: a run that has ended is left alone
    failed = steps_as(*APPROVED)
    assert planner.run_ended(failed, False) == "stopped" and states(failed) == ["done", "done", "done", "failed", "skipped", "skipped"]
    assert failed[3]["note"] == planner.RUN_STOPPED_NOTE
    lost = steps_as(*APPROVED)
    assert planner.run_ended(lost, False, planner.RUN_LOST_NOTE) == "stopped" and lost[3]["note"] == planner.RUN_LOST_NOTE
    # a plan a later step already stopped keeps its stop, and its run still takes its true end
    stopped = steps_as("done", "done", "done", "running", "failed", "skipped")
    assert planner.run_ended(stopped, True) == "stopped" and states(stopped) == ["done", "done", "done", "done", "failed", "skipped"]
    assert planner.run_ended(steps_as("done", "failed", "skipped", "skipped", "skipped", "skipped"), True) is None  # no run under way


def test_a_report_of_the_run_changes_nothing_and_the_pages_own_steps_are_reported_as_before():
    steps = steps_as(*APPROVED)
    for said in ("done", "failed", "skipped", "running"):  # the job is under way: no caller's word stands for its end
        assert planner.report_run_plan(steps, 4, said, "said by a page", job=True) == "running"
        assert states(steps) == APPROVED and steps[3]["note"] is None
    planner.run_ended(steps, True)
    assert planner.report_run_plan(steps, 4, "done", None, job=True) == "running"  # the same end, said again
    with pytest.raises(planner.StepRefused, match="has ended: it is done"):
        planner.report_run_plan(steps, 4, "failed", "late", job=True)
    assert planner.report_run_plan(steps, 5, "done", "every check passes", job=True) == "running"
    assert planner.report_run_plan(steps, 6, "running", None, job=True) == "running"
    assert planner.report_run_plan(steps, 6, "done", "It holds.", job=True) == "done"
    # no job was started (the approval is still under way, or it stopped before the run): there is no run to report
    waiting = steps_as("done", "done", "planned", "planned", "planned", "planned")
    with pytest.raises(planner.StepRefused, match="has not been started"):
        planner.report_run_plan(waiting, 4, "done", None, job=False)
    assert states(waiting)[3] == "planned"
    refused = steps_as("done", "done", "done", "failed", "skipped", "skipped")
    assert planner.report_run_plan(refused, 4, "failed", None, job=False) == "stopped"
    with pytest.raises(planner.StepRefused, match="the server's"):
        planner.report_run_plan(steps, 3, "done", None, job=True)
    with pytest.raises(LookupError):
        planner.report_run_plan(steps, 9, "done", None, job=True)


def test_a_plan_is_done_once_its_last_step_is_and_takes_its_runs_end_when_the_job_ends():
    # a page that reports the QA and the answer before the job has ended: the plan is done by its last step, the run still the job's
    steps = steps_as(*APPROVED)
    assert planner.report_run_plan(steps, 5, "done", None, job=True) == "running"
    assert planner.report_run_plan(steps, 6, "done", None, job=True) == "done" and states(steps)[3] == "running"
    assert planner.run_ended(steps, True) == "done" and states(steps) == ["done"] * 6
    early = steps_as("done", "done", "done", "running", "done", "done")
    assert planner.run_plan_state(early) == "done"
    assert planner.run_ended(early, False) == "stopped" and states(early) == ["done", "done", "done", "failed", "done", "done"]


def test_a_stopped_plan_takes_no_step_start_and_the_same_end_reported_again_rewrites_nothing():
    steps = steps_as("done", "done", "done", "done", "planned", "planned")
    assert planner.report_step(steps, 6, "failed", "no answer to read") == "stopped"  # out of order: the QA had not started
    assert states(steps) == ["done", "done", "done", "done", "skipped", "failed"]  # what had not started never will
    for said in ("running", "done", "failed"):
        with pytest.raises(planner.StepRefused, match="has ended: it is skipped"):
            planner.report_step(steps, 5, said, None)
    # a step left planned on a stopped plan (a row kept before this rule) starts no more, and is skipped by a report alone
    old = steps_as("done", "done", "done", "done", "planned", "failed")
    for said in ("running", "done", "failed"):
        with pytest.raises(planner.StepRefused, match="the plan stopped at step 6, so step 5 does not start"):
            planner.report_step(old, 5, said, None)
    assert planner.report_step(old, 5, "skipped", None) == "stopped" and states(old)[4] == "skipped"
    # a step that had started before the stop is reported to its end
    started = steps_as("done", "done", "done", "done", "running", "failed")
    assert planner.report_step(started, 5, "done", "every check passes") == "stopped" and started[4]["note"] == "every check passes"
    # the same end twice: the first note stands
    twice = steps_as("done", "done", "done", "done", "planned", "planned")
    planner.report_step(twice, 5, "done", "every check passes")
    assert planner.report_step(twice, 5, "done", "another note") == "running" and twice[4]["note"] == "every check passes"
    assert planner.report_step(twice, 5, "done", None) == "running" and twice[4]["note"] == "every check passes"
    planner.report_step(twice, 6, "running", None)
    planner.report_step(twice, 6, "running", "still asking")  # a step under way may say more as it goes
    assert twice[5]["note"] == "still asking"


# ------------------------------------------------------------------------------------------- the routes

@contextmanager
def serving(empty_runs, monkeypatch, tmp_path):
    """The API behind Cloudflare Access with run records on, the job queue's front with a stand-in check, and no model until a test
    scripts one (as test_planner.py's `planning`), its jobs listened to as the startup's are. Started on entering, as any start."""
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
        started = getattr(app.state, "coupon_jobs", None)  # the jobs the startup made, with whatever it listens for
        listen = getattr(api_main, "settle_runs", None)
        if listen is not None:
            jobs.on_end = lambda job_id=None, state=None: listen(app, job_id, state)  # as the startup sets it
        monkeypatch.setattr(app.state, "coupon_jobs", jobs, raising=False)
        monkeypatch.setattr(app.state, "assistant", TemplateAssistant(), raising=False)
        yield SimpleNamespace(client=client, jobs=jobs, engine=empty_runs, started=started, tmp=tmp_path)


@pytest.fixture
def running(empty_runs, monkeypatch, tmp_path):
    with serving(empty_runs, monkeypatch, tmp_path) as api:
        yield api


def row_of(engine, plan_id: str) -> AgentPlanRow:
    with Session(engine) as session:
        return session.get(AgentPlanRow, uuid.UUID(plan_id))


def approved(api, monkeypatch, raw: dict = GOOD, content: dict = PLATE, ask: str = ASK) -> tuple[str, dict]:
    """A plan of the contract's sentence approved: the plan's route and the approval's answer."""
    scripted(monkeypatch, raw)
    pid = project(api.client, content)
    proposed = a_plan(api.client, pid, ask).json()
    answered = api.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]})
    assert answered.status_code == 200, answered.text
    return f"/v1/projects/{pid}/plans/{proposed['id']}", answered.json()


def end_job(api, job_id: str, state: str = "done", tell: bool = True) -> None:
    """A plan's job ended as a solver ends it: its row moved and, with `tell`, whoever listens told (`CouponJobs._finish` does both)."""
    records.update_job(api.engine, uuid.UUID(job_id), state=state, finished_at=dt.datetime.now(dt.timezone.utc))
    told = getattr(api.jobs, "_ended", None)  # none on a server that tells no one
    if tell and told is not None:
        told(uuid.UUID(job_id), state)


@needs_test_database
def test_a_plan_reaches_its_end_on_the_server_with_no_page_reporting_its_run(running, monkeypatch):
    assert getattr(running.started, "on_end", None) is not None  # the startup listens for a job's end
    # the page reports the QA and the answer and never the run: the plan is done all the same
    route, approval = approved(running, monkeypatch)
    assert approval["plan"]["state"] == "running" and states(approval["plan"]) == APPROVED
    end_job(running, approval["job"]["job_id"])
    kept = row_of(running.engine, approval["plan"]["id"])  # settled as the job ended, with no page asking
    assert states(kept.steps) == ["done", "done", "done", "done", "planned", "planned"] and kept.state == "running"
    assert running.client.post(f"{route}/steps/5", json={"state": "done", "note": "every check passes"}).status_code == 200
    assert running.client.post(f"{route}/steps/6", json={"state": "running"}).json()["state"] == "running"
    done = running.client.post(f"{route}/steps/6", json={"state": "done"}).json()
    assert done["state"] == "done" and states(done) == ["done"] * 6
    assert running.client.get(route).json()["state"] == "done" and row_of(running.engine, approval["plan"]["id"]).state == "done"

    # nobody was told (the process that ran the job is another one): the next look at the plan settles it
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"], tell=False)
    assert states(row_of(running.engine, approval["plan"]["id"]).steps)[3] == "running"
    read = running.client.post(f"{route}/steps/5", json={"state": "done"})  # the QA's report finds the run done
    assert read.status_code == 200 and states(read.json()) == ["done", "done", "done", "done", "done", "planned"]
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"], tell=False)
    assert states(running.client.get(route).json())[3] == "done" and states(row_of(running.engine, approval["plan"]["id"]).steps)[3] == "done"

    # every plan whose job ended while no server listened is settled at the next start, each once
    _, one = approved(running, monkeypatch)
    _, other = approved(running, monkeypatch)
    _, going = approved(running, monkeypatch)
    end_job(running, one["job"]["job_id"], tell=False)
    end_job(running, other["job"]["job_id"], state="refused", tell=False)
    assert api_main.settle_runs(app) == 2 and api_main.settle_runs(app) == 0
    assert states(row_of(running.engine, one["plan"]["id"]).steps)[3] == "done" and row_of(running.engine, other["plan"]["id"]).state == "stopped"
    assert states(row_of(running.engine, going["plan"]["id"]).steps) == APPROVED  # its job is still queued
    # a sweep is for an end that was missed: a plan whose job ended long ago (one kept before the server settled runs) is left as it
    # is by the sweep, and settled like any other when it is next read
    route, old = approved(running, monkeypatch)
    long_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=planner.RUN_SWEEP_S + 60)
    records.update_job(running.engine, uuid.UUID(old["job"]["job_id"]), state="done", finished_at=long_ago)
    assert api_main.settle_runs(app) == 0 and states(row_of(running.engine, old["plan"]["id"]).steps) == APPROVED
    assert states(running.client.get(route).json())[3] == "done"

    # whoever listens failing is said on the console and does not fail the job's own end
    def broken(*_given) -> None:
        raise RuntimeError("the records did not answer")

    running.jobs.on_end = broken
    assert running.jobs._ended(uuid.uuid4(), "done") is None


@needs_test_database
def test_a_run_that_fails_or_is_stopped_stops_its_plan(running, monkeypatch):
    for ended in ("stopped", "refused"):
        route, approval = approved(running, monkeypatch)
        end_job(running, approval["job"]["job_id"], state=ended)
        failed = running.client.get(route).json()
        assert failed["state"] == "stopped" and states(failed) == ["done", "done", "done", "failed", "skipped", "skipped"], ended
        assert failed["steps"][3]["note"] == planner.RUN_STOPPED_NOTE
        # the page then reports its own two steps as it shows them, skipped: nothing changes
        for n in (5, 6):
            assert running.client.post(f"{route}/steps/{n}", json={"state": "skipped"}).json()["state"] == "stopped"
        late = running.client.post(f"{route}/steps/5", json={"state": "done"})
        assert late.status_code == 409 and "has ended: it is skipped" in late.json()["detail"]
    # a job the sweep stopped (its solver went silent): no job is named, and every plan whose job ended is settled
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"], state="stopped", tell=False)
    running.jobs._ended()
    assert row_of(running.engine, approval["plan"]["id"]).state == "stopped"
    # a job whose record is gone: its result cannot be read, so the next look at the plan stops it there
    route, approval = approved(running, monkeypatch)
    with running.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM jobs WHERE id = %s", (approval["job"]["job_id"],))
    assert api_main.settle_runs(app) == 0  # a sweep of every plan leaves it: only a look at this plan says its record is gone
    assert running.client.get(route).json()["state"] == "running"  # so new that its approval may be about to start the job
    long_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=planner.RUN_LOST_AFTER_S + 1)
    records.update_plan(running.engine, uuid.UUID(approval["plan"]["id"]), approved_at=long_ago)
    lost = running.client.get(route).json()
    assert lost["state"] == "stopped" and lost["steps"][3]["state"] == "failed" and lost["steps"][3]["note"] == planner.RUN_LOST_NOTE


@needs_test_database
def test_no_report_of_the_run_stands_where_its_job_says_otherwise(running, monkeypatch):
    # the job is queued: a run reported done, or failed, is taken and changes nothing
    route, approval = approved(running, monkeypatch)
    for said in ("done", "failed", "skipped"):
        answered = running.client.post(f"{route}/steps/4", json={"state": said, "note": "said by a page"})
        assert answered.status_code == 200 and answered.json()["state"] == "running" and states(answered.json()) == APPROVED, said
        assert answered.json()["steps"][3]["note"] is None
    # the job ends done: the run is done, and a failed report of it is refused as any ended step's is
    end_job(running, approval["job"]["job_id"], tell=False)
    late = running.client.post(f"{route}/steps/4", json={"state": "failed", "note": "the solver stopped"})
    assert late.status_code == 409 and "has ended: it is done" in late.json()["detail"]
    assert running.client.get(route).json()["state"] == "running" and states(running.client.get(route).json())[3] == "done"
    # the job ends stopped: a run reported done is refused, and the plan is stopped
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"], state="stopped", tell=False)
    lied = running.client.post(f"{route}/steps/4", json={"state": "done"})
    assert lied.status_code == 409 and "has ended: it is failed" in lied.json()["detail"]
    assert running.client.get(route).json()["state"] == "stopped"
    # the QA and the answer reported done while the job is still queued: the plan is done by its last step and the run is still the
    # job's; when the job then fails the plan is stopped at its run, and when it ends done the plan stays done
    for ended, state, run in (("stopped", "stopped", "failed"), ("done", "done", "done")):
        route, approval = approved(running, monkeypatch)
        running.client.post(f"{route}/steps/5", json={"state": "done"})
        early = running.client.post(f"{route}/steps/6", json={"state": "done"}).json()
        assert early["state"] == "done" and states(early) == ["done", "done", "done", "running", "done", "done"]
        end_job(running, approval["job"]["job_id"], state=ended)
        after = running.client.get(route).json()
        assert after["state"] == state and states(after) == ["done", "done", "done", run, "done", "done"]
    # a plan that names no job has no run to report: an approval under way, or one that did not finish
    route, approval = approved(running, monkeypatch)
    waiting = steps_as("done", "done", "planned", "planned", "planned", "planned")
    records.update_plan(running.engine, uuid.UUID(approval["plan"]["id"]), state="approved", steps=waiting, job_id=None)
    early = running.client.post(f"{route}/steps/4", json={"state": "done"})
    assert early.status_code == 409 and "has not been started" in early.json()["detail"]
    assert states(row_of(running.engine, approval["plan"]["id"]).steps) == states(waiting)


@needs_test_database
def test_a_stopped_plan_takes_no_step_start_and_a_repeated_report_keeps_its_note(running, monkeypatch):
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"])
    failed = running.client.post(f"{route}/steps/6", json={"state": "failed", "note": "no answer to read"})  # before the QA was reported
    assert failed.json()["state"] == "stopped" and states(failed.json()) == ["done", "done", "done", "done", "skipped", "failed"]
    for said in ("running", "done"):
        late = running.client.post(f"{route}/steps/5", json={"state": said, "note": "every check passes"})
        assert late.status_code == 409 and "has ended: it is skipped" in late.json()["detail"], said
    assert running.client.get(route).json()["state"] == "stopped" and states(running.client.get(route).json())[4] == "skipped"
    # a row kept before this rule, its QA left planned on a stopped plan: it starts no more
    route, approval = approved(running, monkeypatch)
    old = steps_as("done", "done", "done", "done", "planned", "failed")
    records.update_plan(running.engine, uuid.UUID(approval["plan"]["id"]), state="stopped", steps=old)
    late = running.client.post(f"{route}/steps/5", json={"state": "done"})
    assert late.status_code == 409 and "the plan stopped at step 6, so step 5 does not start" in late.json()["detail"]
    # the same end reported again: the first note stands
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"])
    running.client.post(f"{route}/steps/5", json={"state": "done", "note": "every check passes"})
    again = running.client.post(f"{route}/steps/5", json={"state": "done", "note": "another note"})
    assert again.status_code == 200 and again.json()["steps"][4]["note"] == "every check passes"


@needs_test_database
def test_a_plan_whose_page_closed_before_its_last_step_stays_running(running, monkeypatch):
    """What stays as it is: the QA and the answers are the page's to carry, so a page closed before the last of them leaves the plan
    `running` on the server, its run settled. Nothing here ends such a plan after a time."""
    route, approval = approved(running, monkeypatch)
    end_job(running, approval["job"]["job_id"])
    running.client.post(f"{route}/steps/5", json={"state": "done"})
    running.client.post(f"{route}/steps/6", json={"state": "running"})
    left = running.client.get(route).json()
    assert left["state"] == "running" and states(left) == ["done", "done", "done", "done", "done", "running"]
    assert api_main.settle_runs(app) == 0


@needs_test_database
def test_a_jobs_own_end_and_a_sweep_of_stale_jobs_tell_whoever_listens(running, monkeypatch):
    # a job this process runs, as the local API runs it: the stand-in tool writes no outcome, so the job ends stopped
    told = []
    local = CouponJobs([sys.executable, "-c", "pass"], job_recorder(app), running.tmp / "local", table=running.engine)
    local.on_end = lambda job_id=None, state=None: told.append((job_id, state))
    job = local.start("browser", {"values": {}}, [], values=b"{}")
    for _ in range(200):
        if told:
            break
        time.sleep(0.05)
    assert told == [(job.id, "stopped")] and local.get(job.id).state == "stopped"
    # a queued job no solver took up: the sweep stops it, and the plan whose run it was is stopped with it
    route, approval = approved(running, monkeypatch)
    with running.engine.begin() as connection:
        connection.exec_driver_sql("UPDATE jobs SET started_at = started_at - interval '2 hours' WHERE id = %s", (approval["job"]["job_id"],))
    running.jobs.swept_at = None
    assert running.jobs.sweep() == 1
    swept = row_of(running.engine, approval["plan"]["id"])
    assert swept.state == "stopped" and states(swept.steps) == ["done", "done", "done", "failed", "skipped", "skipped"]


def jobs_kept(engine) -> list[str]:
    with engine.connect() as connection:
        return [str(found) for found, in connection.exec_driver_sql("SELECT id FROM jobs ORDER BY started_at")]


@needs_test_database
def test_a_job_is_started_only_once_its_plan_names_it(running, monkeypatch):
    write, start, order = api_main.update_plan, running.jobs.start, []
    failing: list[int] = []  # the writes of the plan that fail, counted from 1 within an approval

    def written(engine, plan_id, **fields):
        order.append(("plan", fields["job_id"], fields["state"], states(fields["steps"])))
        if sum(1 for one in order if one[0] == "plan") in failing:
            raise OperationalError("UPDATE agent_plans", {}, Exception("the database closed the connection"))
        return write(engine, plan_id, **fields)

    def started(*args, **more):
        with Session(running.engine) as session:  # the plan as it is kept at the moment the job starts
            [kept] = [row for row in session.query(AgentPlanRow) if row.job_id == str(more["job_id"])]
        order.append(("start", str(more["job_id"]), kept.state, states(kept.steps)))
        return start(*args, **more)

    monkeypatch.setattr(api_main, "update_plan", written)
    monkeypatch.setattr(running.jobs, "start", started)

    def approve() -> tuple[str, str, object]:
        order.clear()
        scripted(monkeypatch, GOOD)
        pid = project(running.client)
        proposed = a_plan(running.client, pid).json()
        return pid, proposed["id"], running.client.post(f"/v1/projects/{pid}/plans/{proposed['id']}/approve", json={"base": proposed["base"]})

    # the plan is written with its run under way and its job's id, then the job is started as that id
    _, _, answered = approve()
    job = answered.json()["job"]["job_id"]
    assert answered.status_code == 200 and answered.json()["plan"]["job"] == job and jobs_kept(running.engine) == [job]
    assert order == [("plan", job, "running", APPROVED), ("start", job, "running", APPROVED), ("plan", job, "running", APPROVED)]

    # the write that names the job fails: nothing is started, and the plan says nothing of a run
    failing[:] = [1]
    pid, plan_id, answered = approve()
    assert answered.status_code == 503 and ENQUEUE_HEADER not in answered.headers and "Location" not in answered.headers
    assert [one[0] for one in order] == ["plan"] and jobs_kept(running.engine) == [job]
    row = row_of(running.engine, plan_id)
    assert row.state == "approved" and row.job_id is None and states(row.steps) == ["done", "done", "planned", "planned", "planned", "planned"]
    refused = running.client.post(f"/v1/projects/{pid}/plans/{plan_id}/steps/4", json={"state": "done"})
    assert refused.status_code == 409 and "has not been started" in refused.json()["detail"]

    # the write after the start fails: the job runs, and the plan already says so and names it
    failing[:] = [2]
    pid, plan_id, answered = approve()
    assert answered.status_code == 503 and [one[0] for one in order] == ["plan", "start", "plan"]
    row = row_of(running.engine, plan_id)
    assert row.state == "running" and row.job_id == order[1][1] and states(row.steps) == APPROVED and row.job_id in jobs_kept(running.engine)
    failing[:] = []
    end_job(running, row.job_id)
    assert states(running.client.get(f"/v1/projects/{pid}/plans/{plan_id}").json())[3] == "done"

    # a start refused once the plan names the job: the plan is stopped at its run and names no job
    def busy(*_args, **_more):
        raise JobBusy(uuid.uuid4())

    monkeypatch.setattr(running.jobs, "start", busy)
    _, plan_id, answered = approve()
    assert answered.status_code == 200 and answered.json()["job"] is None and answered.json()["plan"]["job"] is None
    assert answered.json()["plan"]["state"] == "stopped" and states(answered.json()["plan"]) == ["done", "done", "done", "failed", "skipped", "skipped"]
    assert order[0][1] is not None and order[1][1] is None and row_of(running.engine, plan_id).job_id is None

    # that last write lost too: the plan names a job that never started. It is left alone while its approval may still be under way,
    # and once it cannot be, the next look at the plan says the record is gone and stops it
    failing[:] = [2]
    pid, plan_id, answered = approve()
    assert answered.status_code == 503
    failing[:] = []
    row = row_of(running.engine, plan_id)
    assert row.state == "running" and row.job_id is not None and row.job_id not in jobs_kept(running.engine)
    route = f"/v1/projects/{pid}/plans/{plan_id}"
    assert running.client.get(route).json()["state"] == "running"
    assert running.client.post(f"{route}/steps/5", json={"state": "done"}).json()["steps"][3]["state"] == "running"
    long_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=planner.RUN_LOST_AFTER_S + 1)
    write(running.engine, uuid.UUID(plan_id), approved_at=long_ago)
    lost = running.client.get(route).json()
    assert lost["state"] == "stopped" and lost["steps"][3]["state"] == "failed" and lost["steps"][3]["note"] == planner.RUN_LOST_NOTE


@needs_test_database
def test_a_coupons_plan_ends_as_a_plates_does_and_a_wings_check_is_still_the_pages_to_report(running, monkeypatch):
    from test_planner import COUPON

    sentence = "set the width to 20 mm and run it"
    route, approval = approved(running, monkeypatch, plan(step("row", "set the width to 20 mm", key="width", value="20", unit="mm"), step("run", "run it")),
                               COUPON, sentence)
    assert [(one["tool"], one["state"]) for one in approval["plan"]["steps"]] == [("row", "done"), ("check", "done"), ("run", "running"), ("qa", "planned")]
    end_job(running, approval["job"]["job_id"])
    assert states(running.client.get(route).json()) == ["done", "done", "done", "planned"]
    assert running.client.post(f"{route}/steps/4", json={"state": "done"}).json()["state"] == "done"
    assert planner.RUN_KINDS == ("coupon", "plate")  # a wing's check is a job its page reports, as before


def without_a_number(engine, plan_id: str) -> list[dict]:
    """A plan kept in a shape the rules do not read: its run step has no number. The steps as they are then kept."""
    steps = [{k: v for k, v in one.items() if not (one["tool"] == "run" and k == "n")} for one in row_of(engine, plan_id).steps]
    records.update_plan(engine, uuid.UUID(plan_id), steps=steps)
    return steps


@needs_test_database
def test_one_plan_a_sweep_cannot_settle_is_said_and_the_others_are_settled(running, monkeypatch, capsys):
    _, bad = approved(running, monkeypatch)
    _, one = approved(running, monkeypatch)
    _, other = approved(running, monkeypatch)
    kept = without_a_number(running.engine, bad["plan"]["id"])
    for approval in (bad, one, other):
        end_job(running, approval["job"]["job_id"], state="stopped", tell=False)
    capsys.readouterr()
    assert api_main.settle_runs(app) == 2  # the two that can be
    said = capsys.readouterr().out
    assert f"plan {bad['plan']['id']}: its run was not settled: KeyError" in said
    for approval in (one, other):
        assert row_of(running.engine, approval["plan"]["id"]).state == "stopped"
    left = row_of(running.engine, bad["plan"]["id"])
    assert left.state == "running" and left.steps == kept  # as it was
    # told of that job's own end, the server says the same and the job's end goes on
    assert running.jobs._ended(uuid.UUID(bad["job"]["job_id"]), "stopped") is None
    assert f"plan {bad['plan']['id']}: its run was not settled" in capsys.readouterr().out

    # whatever else a sweep meets is said too, and nothing is raised: at a start, as a job ends and after a sweep of stale jobs
    def broken(*_given, **_named):
        raise RuntimeError("the plans could not be read")

    monkeypatch.setattr(api_main, "settle_plan_runs", broken)
    assert api_main.settle_runs(app) == 0
    assert "the plans' runs were not settled: the plans could not be read" in capsys.readouterr().out
    assert running.jobs._ended() is None and running.jobs._ended(uuid.uuid4(), "done") is None


@needs_test_database
def test_the_api_starts_whatever_its_first_sweep_of_the_plans_meets(empty_runs, monkeypatch, tmp_path, capsys):
    with serving(empty_runs, monkeypatch, tmp_path) as api:  # a server that stops with two jobs' ends unheard, one of a plan it cannot read
        _, bad = approved(api, monkeypatch)
        _, good = approved(api, monkeypatch)
        without_a_number(empty_runs, bad["plan"]["id"])
        for approval in (bad, good):
            end_job(api, approval["job"]["job_id"], state="stopped", tell=False)
    capsys.readouterr()
    with TestClient(app) as client:  # the next start
        assert client.get("/healthz").status_code == 200
        assert row_of(empty_runs, good["plan"]["id"]).state == "stopped" and row_of(empty_runs, bad["plan"]["id"]).state == "running"
    assert f"plan {bad['plan']['id']}: its run was not settled" in capsys.readouterr().out

    def broken(*_given, **_named):
        raise RuntimeError("the plans could not be read")

    monkeypatch.setattr(api_main, "settle_plan_runs", broken)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
    assert "the plans' runs were not settled: the plans could not be read" in capsys.readouterr().out
