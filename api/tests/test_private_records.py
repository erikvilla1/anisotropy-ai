"""What one signed-in person may see of another's (ADR-0104, ADR-0106): behind Cloudflare Access a run, a job, its files and a
coupon are their owner's alone, each person's coupons in a folder of their own, and a stranger is answered as if there were none;
with no sign-in in front of the API nothing is narrowed. The stand-in of test_coupon_jobs_api.py plays the job's tool, keeping its
coupon in the folder it was started with, and a stand-in here the studio's, so these tests need no fea environment."""

import datetime as dt
import hashlib
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import access
from anisotropy_api.coupon_jobs import COUPONS_ROOT, CouponJobs
from anisotropy_api.live import LiveSolver
from anisotropy_api.main import RUN_ID_HEADER, app, job_recorder
from anisotropy_api.records import EVERYONE, coupon_owners, coupons_of, insert_job, list_jobs, list_runs, update_job
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, service_token, token
from conftest import TEST_URL, needs_test_database
from test_coupon_jobs_api import STAND_IN, form_request

OTHER = "other.engineer@example.com"
COUPON = "IM7-UNT-L1"  # the coupon both stand-ins name
GONE = "These results are no longer available. Run the analysis again from your project."


def signed(email: str = EMAIL) -> dict:
    return {access.HEADER: token(email=email)}



def machine() -> dict:
    return {access.HEADER: service_token()}


# The job's stand-in, keeping its coupon as the tool does: a spec in the folder it was started with, holding who ran it.
KEEPS_ITS_COUPON = f"""
import os, pathlib, sys
_spec = pathlib.Path(os.environ["{COUPONS_ROOT}"]) / "{COUPON}" / "ours" / "{COUPON}.toml"
if sys.argv[1] == "{COUPON}" and not _spec.is_file():
    sys.exit("stand-in: started by name for a coupon its folder does not hold")
if sys.argv[1] != "{COUPON}":
    _spec.parent.mkdir(parents=True, exist_ok=True)
    _spec.write_text(sys.argv[sys.argv.index("--run-by") + 1], encoding="utf-8")
"""

# The studio's stand-in: the coupons of the folder it was started with, and of no other.
STUDIO_OF_A_FOLDER = f"""
import json, os, pathlib, sys
root = pathlib.Path(os.environ["{COUPONS_ROOT}"])
specs = {{d.name: d / "ours" / (d.name + ".toml") for d in sorted(root.iterdir()) if (d / "ours" / (d.name + ".toml")).is_file()}} if root.is_dir() else {{}}
if sys.argv[1] == "coupons":
    print(json.dumps([{{"name": name, "designation": name, "kind": "unnotched_tension", "test": "unnotched tension", "title": name, "layup": "[0]",
                       "status": "in progress", "accepted": "01", "attempts": 1, "category": "team test"}} for name in specs]))
elif sys.argv[1] == "values":
    if sys.argv[2] not in specs:
        sys.exit(f"studio_tool: {{sys.argv[2]}}: no coupon of that name under {{root}}")
    print(json.dumps({{"form_version": "0.3", "test": "unnotched tension", "length": 250.0, "filled_by": specs[sys.argv[2]].read_text(encoding="utf-8")}}))
elif sys.argv[1] == "check":  # the check names the coupon among the coupons of its folder: here, by the folder's own name
    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1])
    out.mkdir(parents=True)
    (out / "checklist.json").write_text(json.dumps({{"items": [], "designation": root.name, "coupon_exists": False, "attempts": 0, "state": "blocked",
                                                    "problems": []}}), encoding="utf-8")
else:
    sys.exit("stand-in: " + sys.argv[1])
"""

# The live solver's stand-in, fresh or warm: its checklist names the folder of coupons the request came with, "its own" for none.
LIVE_OF_A_FOLDER = """
import argparse, json, pathlib, sys

def answer(out, root):
    out = pathlib.Path(out)
    out.mkdir(parents=True)
    (out / "checklist.json").write_text(json.dumps({"items": [], "designation": pathlib.Path(root).name if root else "its own", "coupon_exists": False,
                                                    "attempts": 0, "state": "blocked", "problems": []}), encoding="utf-8")
    return "blocked"

parser = argparse.ArgumentParser()
parser.add_argument("--root")
commands = parser.add_subparsers(dest="command", required=True)
p = commands.add_parser("live"); p.add_argument("values"); p.add_argument("--out", required=True)
commands.add_parser("serve")
args = parser.parse_args()
if args.command == "live":
    answer(args.out, args.root)
else:
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        print(json.dumps({"state": answer(request["out"], request.get("root"))}), flush=True)
"""


def registry(tmp_path, table) -> CouponJobs:
    runner, studio = tmp_path / "stand_in.py", tmp_path / "studio_stand_in.py"
    runner.write_text(KEEPS_ITS_COUPON + STAND_IN, encoding="utf-8")
    studio.write_text(STUDIO_OF_A_FOLDER, encoding="utf-8")
    return CouponJobs([sys.executable, str(runner)], job_recorder(app), tmp_path / "jobs", table=table, studio=[sys.executable, str(studio)],
                      local_root=tmp_path / "coupons")


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


def a_job_of(client: TestClient, headers: dict, **changes) -> dict:
    started = client.post("/v1/coupon-jobs", json=form_request(**changes), headers=headers)
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
def test_each_person_has_a_folder_of_coupons_of_their_own(hosted, tmp_path):
    client = hosted
    assert client.get("/v1/coupons", headers=signed()).json() == []  # before any job of theirs, nothing to reopen
    a_job_of(client, signed())

    assert [c["name"] for c in client.get("/v1/coupons", headers=signed()).json()] == [COUPON]
    assert client.get(f"/v1/coupons/{COUPON}/values", headers=signed()).json()["values"]["filled_by"] == "A. Engineer"

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

    # a second person's coupon of the same name is another coupon, in their own folder: each keeps their own rows and reopens their own
    a_job_of(client, signed(OTHER), run_by="B. Other")
    for person, ran_by in ((signed(), "A. Engineer"), (signed(OTHER), "B. Other")):
        assert [c["name"] for c in client.get("/v1/coupons", headers=person).json()] == [COUPON]
        assert client.get(f"/v1/coupons/{COUPON}/values", headers=person).json()["values"]["filled_by"] == ran_by
        rerun = client.post("/v1/coupon-jobs", json={"coupon": COUPON, "run_by": "Someone"}, headers=person)
        assert rerun.status_code == 202 and ended(client, rerun.json()["job_id"], person)["state"] == "done"
    assert client.get("/v1/coupons", headers=machine()).json() == []  # and the shared folder holds neither

    # on the disk: one folder per person under a key that holds no address, and nothing in the shared folder
    owners = tmp_path / "coupons-owners"
    assert sorted(p.name for p in owners.iterdir()) == sorted(hashlib.sha256(email.encode()).hexdigest()[:32] for email in (EMAIL, OTHER))
    assert not (tmp_path / "coupons").exists()
    assert client.get("/v1/coupons", headers=signed(EMAIL.upper())).json() == []  # the email to the letter, as for the records (ADR-0104)


@needs_test_database
def test_a_request_with_no_email_keeps_the_shared_folder(hosted, tmp_path):
    """A service token has no email: its jobs keep their coupons in the shared folder, offered to it by the jobs that ran them
    (ADR-0104), and no person's folder holds them."""
    client = hosted
    a_job_of(client, machine(), run_by="The machine")
    assert [c["name"] for c in client.get("/v1/coupons", headers=machine()).json()] == [COUPON]
    assert client.get(f"/v1/coupons/{COUPON}/values", headers=machine()).json()["values"]["filled_by"] == "The machine"
    assert (tmp_path / "coupons" / COUPON / "ours" / f"{COUPON}.toml").is_file() and not (tmp_path / "coupons-owners").exists()
    assert client.get("/v1/coupons", headers=signed()).json() == []
    assert client.get(f"/v1/coupons/{COUPON}/values", headers=signed()).status_code == 404
    # the shared folder's rule is still ADR-0104's, by the names in the jobs table: once a person's job has named a coupon of that
    # name too (theirs is another coupon, in their own folder), the shared one is offered to no one
    a_job_of(client, signed())
    assert client.get("/v1/coupons", headers=machine()).json() == []
    assert client.get(f"/v1/coupons/{COUPON}/values", headers=signed()).json()["values"]["filled_by"] == "A. Engineer"


@needs_test_database
@pytest.mark.parametrize("workers", [1, 0], ids=["a warm worker", "a fresh tool"])
def test_the_check_and_the_preview_name_a_coupon_among_the_askers_own(hosted, tmp_path, workers):
    """The setup check and the live preview read the folder of whoever asked: a coupon's name and its codes are settled among that
    person's coupons, never among another's (ADR-0106)."""
    client = hosted
    stand_in = tmp_path / "live_stand_in.py"
    stand_in.write_text(LIVE_OF_A_FOLDER, encoding="utf-8")
    app.state.live = LiveSolver([sys.executable, str(stand_in)], tmp_path / "live", workers, timeout_s=10.0, wait_s=20.0)
    values = {"values": {"form_version": "0.9", "test": "unnotched tension", "filled_by": "A. Engineer"}}
    try:
        for headers, folder, live_folder in ((signed(), hashlib.sha256(EMAIL.encode()).hexdigest()[:32], None),
                                             (signed(OTHER), hashlib.sha256(OTHER.encode()).hexdigest()[:32], None),
                                             (machine(), "coupons", "its own")):  # no email: the shared folder, the tool's own
            checked = client.post("/v1/coupon-jobs/check", json=values, headers=headers)
            assert checked.status_code == 200 and checked.json()["designation"] == folder
            previewed = client.post("/v1/coupon-jobs/live", json=values, headers=headers)
            assert previewed.status_code == 200 and previewed.json()["designation"] == (live_folder or folder)
    finally:
        app.state.live.close()


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
