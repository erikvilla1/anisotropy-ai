"""What one signed-in person may see of another's (ADR-0104): behind Cloudflare Access a run, a job, its files and a coupon are
their owner's alone, and a stranger is answered as if there were none; with no sign-in in front of the API nothing is narrowed.
The stand-ins of test_coupon_jobs_api.py and test_coupon_check_api.py play the tools, so these tests need no fea environment."""

import datetime as dt
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import access
from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import RUN_ID_HEADER, app, job_recorder
from anisotropy_api.records import EVERYONE, coupon_owners, coupons_of, insert_job, list_jobs, list_runs, update_job
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from test_coupon_check_api import STUDIO_STAND_IN
from test_coupon_jobs_api import STAND_IN, form_request

OTHER = "other.engineer@example.com"
COUPON = "IM7-UNT-L1"  # the coupon both stand-ins name
GONE = "These results are no longer available. Run the analysis again from your project."


def signed(email: str = EMAIL) -> dict:
    return {access.HEADER: token(email=email)}



def machine() -> dict:
    return {access.HEADER: service_token()}


def registry(tmp_path, table) -> CouponJobs:
    runner, studio = tmp_path / "stand_in.py", tmp_path / "studio_stand_in.py"
    runner.write_text(STAND_IN, encoding="utf-8")
    studio.write_text(STUDIO_STAND_IN, encoding="utf-8")
    return CouponJobs([sys.executable, str(runner)], job_recorder(app), tmp_path / "jobs", table=table, studio=[sys.executable, str(studio)])


@pytest.fixture(params=["with the jobs table", "without it"])
def hosted(request, empty_runs, monkeypatch, tmp_path):
    """The API behind Cloudflare Access with run records on; each request carries its own token. Once with the jobs table, as the
    hosted site runs, and once with the jobs of this process alone."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        app.state.coupon_jobs = registry(tmp_path, app.state.records if request.param == "with the jobs table" else None)
        yield client


def ended(client: TestClient, job_id: str, headers: dict) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        body = client.get(f"/v1/coupon-jobs/{job_id}", headers=headers).json()
        if body["state"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError(f"coupon job {job_id} still running after 30 s")


def a_job_of(client: TestClient, headers: dict) -> dict:
    started = client.post("/v1/coupon-jobs", json=form_request(), headers=headers)
    assert started.status_code == 202, started.text
    done = ended(client, started.json()["job_id"], headers)
    assert done["state"] == "done"
    return done


# ------------------------------------------------------------------------------------------------------------ the jobs and their files

@needs_test_database
def test_a_job_and_its_files_are_its_owners_alone(hosted):
    client = hosted
    job = a_job_of(client, signed())
    path = f"/v1/coupon-jobs/{job['job_id']}"

    assert [j["job_id"] for j in client.get("/v1/coupon-jobs", headers=signed()).json()] == [job["job_id"]]
    assert client.get(path, headers=signed()).json()["user_email"] == EMAIL
    assert client.get(f"{path}/files/fields", headers=signed()).json() == {"summary": {"reaction": {"value": 1.0}}}
    assert client.get(f"{path}/package", headers=signed()).status_code == 200

    unknown = client.get(f"/v1/coupon-jobs/{uuid.uuid4()}", headers=signed(OTHER))
    assert unknown.status_code == 404 and unknown.json()["detail"] == GONE
    for stranger in (signed(OTHER), machine(), signed(EMAIL.upper())):  # the email is the owner's as Access states it, to the letter
        assert client.get("/v1/coupon-jobs", headers=stranger).json() == []
        for answer in (client.get(path, headers=stranger), client.get(f"{path}/package", headers=stranger),
                       client.get(f"{path}/files/fields", headers=stranger), client.get(f"{path}/files/package", headers=stranger),
                       client.post(f"{path}/explain", json={"kind": "result"}, headers=stranger)):
            assert answer.status_code == 404 and answer.json() == unknown.json()  # the same words as for a job there is none of
    assert client.get(path).status_code == 401  # and no one at all without Access's token


@needs_test_database
def test_each_person_lists_their_own_jobs(hosted):
    client = hosted
    mine, theirs, the_machines = a_job_of(client, signed()), a_job_of(client, signed(OTHER)), a_job_of(client, machine())
    assert [j["job_id"] for j in client.get("/v1/coupon-jobs", headers=signed()).json()] == [mine["job_id"]]
    assert [j["job_id"] for j in client.get("/v1/coupon-jobs", headers=signed(OTHER)).json()] == [theirs["job_id"]]
    # a service token has no email: it sees what was made with none, and no person's
    assert [j["job_id"] for j in client.get("/v1/coupon-jobs", headers=machine()).json()] == [the_machines["job_id"]]
    assert client.get(f"/v1/coupon-jobs/{the_machines['job_id']}", headers=signed()).status_code == 404


# ----------------------------------------------------------------------------------------------------------------- the run records

@needs_test_database
def test_a_run_record_is_its_owners_alone(hosted):
    client = hosted
    job = a_job_of(client, signed())
    solved = client.post("/v1/cases/solve", headers=signed(), json={"case": {}})  # rejected by the engine, still a run
    mine = {job["run_id"], solved.headers[RUN_ID_HEADER]}
    theirs = client.post("/v1/cases/solve", headers=signed(OTHER), json={"case": {}}).headers[RUN_ID_HEADER]

    assert {run["run_id"] for run in client.get("/v1/runs", headers=signed()).json()} == mine
    assert [run["run_id"] for run in client.get("/v1/runs", headers=signed(OTHER)).json()] == [theirs]
    assert client.get("/v1/runs", headers=machine()).json() == []
    assert client.get("/v1/runs", params={"endpoint": "/v1/coupon-jobs"}, headers=signed(OTHER)).json() == []  # a filter widens nothing

    unknown = client.get(f"/v1/runs/{uuid.uuid4()}", headers=signed(OTHER))
    assert unknown.status_code == 404
    for run_id in mine:
        assert client.get(f"/v1/runs/{run_id}", headers=signed()).json()["user_email"] == EMAIL
        for stranger in (signed(OTHER), machine()):
            answer = client.get(f"/v1/runs/{run_id}", headers=stranger)
            assert answer.status_code == 404 and answer.json()["detail"] == f"No run {run_id}"  # as for a run there is none of
    assert unknown.json()["detail"].startswith("No run ")


# --------------------------------------------------------------------------------------------------------------------- the coupons

@needs_test_database
def test_a_coupon_is_offered_to_those_whose_jobs_ran_it(hosted):
    client = hosted
    assert client.get("/v1/coupons", headers=signed()).json() == []  # before any job of theirs, nothing to reopen
    a_job_of(client, signed())

    assert [c["name"] for c in client.get("/v1/coupons", headers=signed()).json()] == [COUPON]
    assert client.get(f"/v1/coupons/{COUPON}/values", headers=signed()).json()["values"]["length"] == 250.0

    never = client.get("/v1/coupons/NONE-UNT-L9/values", headers=signed(OTHER))
    assert never.status_code == 404 and never.json()["detail"] == "no coupon of that name: NONE-UNT-L9"
    for stranger in (signed(OTHER), machine()):
        assert client.get("/v1/coupons", headers=stranger).json() == []
        values = client.get(f"/v1/coupons/{COUPON}/values", headers=stranger)
        assert values.status_code == 404 and values.json()["detail"] == f"no coupon of that name: {COUPON}"  # as for a name there is none of
        refused = client.post("/v1/coupon-jobs", json={"coupon": COUPON, "run_by": "A. Engineer"}, headers=stranger)
        assert refused.status_code == 404 and refused.json()["detail"] == f"no coupon of that name: {COUPON}"
        assert client.get("/v1/coupon-jobs", headers=stranger).json() == []  # and nothing was started

    again = client.post("/v1/coupon-jobs", json={"coupon": COUPON, "run_by": "A. Engineer"}, headers=signed())  # the owner runs it again by its name
    assert again.status_code == 202 and ended(client, again.json()["job_id"], signed())["state"] == "done"

    # the coupon's folder holds the rows of whoever ran it last: once a second person's job has run that name, it is offered to neither
    a_job_of(client, signed(OTHER))
    for either in (signed(), signed(OTHER)):
        assert client.get("/v1/coupons", headers=either).json() == []
        assert client.get(f"/v1/coupons/{COUPON}/values", headers=either).status_code == 404
        assert client.post("/v1/coupon-jobs", json={"coupon": COUPON, "run_by": "A. Engineer"}, headers=either).status_code == 404
    assert len(client.get("/v1/coupon-jobs", headers=signed()).json()) == 2  # each still has their own jobs and files


# ------------------------------------------------------------------------------------------------ with no sign-in, nothing is narrowed

@needs_test_database
def test_the_local_api_shows_every_record(empty_runs, monkeypatch, tmp_path):
    """ADR-0011: with no sign-in in front of the API there is one user, and a record made behind Access elsewhere is theirs to see."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.delenv(ACCESS_TEAM_DOMAIN_VARIABLE, raising=False)
    monkeypatch.delenv(ACCESS_AUDIENCE_VARIABLE, raising=False)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        assert app.state.access_verifier is None
        app.state.coupon_jobs = registry(tmp_path, app.state.records)
        now = dt.datetime.now(dt.timezone.utc)
        theirs = uuid.uuid4()
        insert_job(empty_runs, job_id=theirs, actor="browser", user_email=OTHER, inputs={"coupon": COUPON}, started_at=now, process="another-container")
        update_job(empty_runs, theirs, state="done", coupon=COUPON, attempt="attempt-01", finished_at=now)
        started = client.post("/v1/coupon-jobs", json=form_request())
        mine = ended(client, started.json()["job_id"], {})

        assert {j["job_id"] for j in client.get("/v1/coupon-jobs").json()} == {mine["job_id"], str(theirs)}
        assert client.get(f"/v1/coupon-jobs/{theirs}").json()["user_email"] == OTHER
        assert client.get(f"/v1/runs/{mine['run_id']}").status_code == 200
        assert [c["name"] for c in client.get("/v1/coupons").json()] == [COUPON]
        assert client.get(f"/v1/coupons/{COUPON}/values").status_code == 200


# ------------------------------------------------------------------------------------------------------- the queries on their own

@needs_test_database
def test_the_lists_are_narrowed_in_the_query_not_after_it(empty_runs):
    """An owner's rows are found however many of other people's are newer: the limit counts their own."""
    now = dt.datetime.now(dt.timezone.utc)
    mine = uuid.uuid4()
    insert_job(empty_runs, job_id=mine, actor="browser", user_email=EMAIL, inputs={}, started_at=now - dt.timedelta(hours=1), process="p")
    update_job(empty_runs, mine, state="done", coupon=COUPON, attempt="attempt-01", finished_at=now)
    for index in range(3):
        other = uuid.uuid4()
        insert_job(empty_runs, job_id=other, actor="browser", user_email=OTHER if index else None, inputs={}, started_at=now, process="p")
        update_job(empty_runs, other, state="done", coupon=f"OTHER-UNT-L{index}", attempt="attempt-01", finished_at=now)

    assert [row.id for row in list_jobs(empty_runs, limit=1, user_email=EMAIL)] == [mine]
    assert len(list_jobs(empty_runs, limit=50, user_email=OTHER)) == 2 and len(list_jobs(empty_runs, limit=50, user_email=None)) == 1
    assert len(list_jobs(empty_runs, limit=50)) == 4 and len(list_jobs(empty_runs, limit=50, user_email=EVERYONE)) == 4
    owners = coupon_owners(empty_runs)
    assert coupons_of(owners, EMAIL) == {COUPON} and coupons_of(owners, OTHER) == {"OTHER-UNT-L1", "OTHER-UNT-L2"}
    assert coupons_of(owners, None) == {"OTHER-UNT-L0"} and coupons_of(owners, "nobody@example.com") == set()
    assert coupons_of(owners | {(COUPON, OTHER)}, EMAIL) == set() and coupons_of(owners | {(COUPON, None)}, EMAIL) == set()  # a shared name is no one's
    assert list_runs(empty_runs, user_email=EMAIL) == []  # no run was recorded here
