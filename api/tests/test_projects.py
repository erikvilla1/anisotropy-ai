"""Workspace projects through the API (ADR-0062 part 6): a project is kept as the page states it, under the signed-in email behind
Cloudflare Access or the actor locally; it is created or replaced by its id, listed last-changed first, read with its jobs, renamed;
another's project answers as if it did not exist; without run records there is no table and the routes say so."""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import access
from anisotropy_api.main import app
from anisotropy_api.records import insert_job
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, token
from conftest import TEST_URL, needs_test_database

COUPON = {"form": {"test": "unnotched tension", "length": "250", "width": "25"}, "plate": {"supports": [], "loads": [], "regions": []}}
LAMINATE = {"system": "SI", "material": {"library": "im7-8552"}, "layup": None, "thickness": None, "loads": None, "f12_star": "", "strain_limits": False}


def body(kind: str = "fea", name: str = "OHT study", content: dict | None = None, **more) -> dict:
    return {"kind": kind, "name": name, "content": COUPON if content is None else content, **more}


def test_without_run_records_the_projects_answer_503(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        refused = client.put(f"/v1/projects/{uuid.uuid4()}", json=body())
        assert refused.status_code == 503 and "switched off" in refused.json()["detail"]
        assert client.get("/v1/projects").status_code == 503
        assert client.get(f"/v1/projects/{uuid.uuid4()}").status_code == 503


def test_the_routes_need_the_actor_header():
    client = TestClient(app)  # no lifespan: the actor is checked before anything else
    assert client.get("/v1/projects").status_code == 422
    assert client.put(f"/v1/projects/{uuid.uuid4()}", json=body()).status_code == 422


@pytest.fixture
def recording(empty_runs, monkeypatch):
    """The API with run records on, as the studio."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        yield client


@needs_test_database
def test_a_project_is_created_replaced_listed_and_renamed(recording):
    pid = str(uuid.uuid4())
    made = recording.put(f"/v1/projects/{pid}", json=body(form_version="0.7", units="mm-MPa"))
    assert made.status_code == 201
    row = made.json()
    assert row["id"] == pid and row["kind"] == "fea" and row["name"] == "OHT study" and row["content"] == COUPON and row["actor"] == "studio"
    assert row["user_email"] is None and row["form_version"] == "0.7" and row["units"] == "mm-MPa" and row["designation"] is None and row["jobs"] == []
    again = recording.put(f"/v1/projects/{pid}", json=body(name="OHT study, wider", content={**COUPON, "form": {**COUPON["form"], "width": "36"}}))
    assert again.status_code == 200 and again.json()["name"] == "OHT study, wider" and again.json()["content"]["form"]["width"] == "36"
    assert again.json()["created_at"] == row["created_at"] and again.json()["updated_at"] >= row["updated_at"]
    assert [p["id"] for p in recording.get("/v1/projects").json()] == [pid]
    assert recording.get("/v1/projects", headers={"X-Anisotropy-Actor": "test"}).json() == []  # locally, by actor
    assert recording.get(f"/v1/projects/{pid}", headers={"X-Anisotropy-Actor": "test"}).status_code == 404
    assert recording.put(f"/v1/projects/{pid}", json=body(name="taken"), headers={"X-Anisotropy-Actor": "test"}).status_code == 404
    renamed = recording.patch(f"/v1/projects/{pid}", json={"name": "Renamed"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Renamed" and renamed.json()["content"] == again.json()["content"]
    changed_kind = recording.put(f"/v1/projects/{pid}", json=body(kind="laminate", content=LAMINATE))
    assert changed_kind.status_code == 409 and "does not become a laminate one" in changed_kind.json()["detail"]
    lam = str(uuid.uuid4())
    assert recording.put(f"/v1/projects/{lam}", json=body(kind="laminate", name="ABD check", content=LAMINATE)).status_code == 201
    assert [(p["kind"], p["name"]) for p in recording.get("/v1/projects").json()] == [("laminate", "ABD check"), ("fea", "Renamed")]  # last changed first
    assert recording.get(f"/v1/projects/{uuid.uuid4()}").status_code == 404
    assert recording.patch(f"/v1/projects/{uuid.uuid4()}", json={"name": "x"}).status_code == 404
    assert recording.get("/v1/projects", params={"limit": 1}).json()[0]["id"] == lam


@needs_test_database
@pytest.mark.parametrize("bad, reason", [
    (body(kind="stl"), "kind"),
    ({"kind": "fea", "name": "x", "content": {}}, "empty"),
    ({"kind": "fea", "name": "x", "content": {"big": "x" * 300_000}}, "far below"),
    ({"kind": "fea", "name": "x", "content": COUPON, "owner": "me"}, "extra"),
    ({"kind": "fea", "name": "x" * 201, "content": COUPON}, "200"),
])
def test_a_project_outside_the_contract_is_refused(recording, bad, reason):
    refused = recording.put(f"/v1/projects/{uuid.uuid4()}", json=bad)
    assert refused.status_code == 422 and reason in str(refused.json()["detail"]).lower()
    assert recording.get("/v1/projects").json() == []


@needs_test_database
def test_a_projects_jobs_are_listed_with_it(recording, migrated_database):
    pid = uuid.uuid4()
    assert recording.put(f"/v1/projects/{pid}", json=body()).status_code == 201
    job_id = uuid.uuid4()
    insert_job(migrated_database, job_id=job_id, actor="studio", user_email=None, inputs={"coupon": "IM7-UNT-L1"}, started_at=dt.datetime.now(dt.timezone.utc),
               process="p", project_id=pid)
    detail = recording.get(f"/v1/projects/{pid}").json()
    assert [job["job_id"] for job in detail["jobs"]] == [str(job_id)] and detail["jobs"][0]["state"] == "running" and detail["jobs"][0]["run_id"] is None
    assert recording.get(f"/v1/coupon-jobs/{job_id}").json()["project_id"] == str(pid)
    assert recording.get("/v1/projects").json()[0]["jobs"] == []  # the list is light; the jobs come with the detail


@pytest.fixture
def behind_access(empty_runs, monkeypatch):
    """The API with run records on and Access on; each request carries its own token."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        yield client


@needs_test_database
def test_behind_access_a_project_belongs_to_the_signed_in_email(behind_access):
    mine = {access.HEADER: token()}
    theirs = {access.HEADER: token(email="someone-else@example.com")}
    pid = str(uuid.uuid4())
    made = behind_access.put(f"/v1/projects/{pid}", json=body(), headers=mine)
    assert made.status_code == 201 and made.json()["user_email"] == EMAIL and made.json()["actor"] == "browser"
    assert [p["id"] for p in behind_access.get("/v1/projects", headers=mine).json()] == [pid]
    assert behind_access.get("/v1/projects", headers=theirs).json() == []
    assert behind_access.get(f"/v1/projects/{pid}", headers=theirs).status_code == 404
    assert behind_access.put(f"/v1/projects/{pid}", json=body(name="taken"), headers=theirs).status_code == 404  # no taking over
    assert behind_access.patch(f"/v1/projects/{pid}", json={"name": "taken"}, headers=theirs).status_code == 404
    assert behind_access.get(f"/v1/projects/{pid}", headers=mine).json()["name"] == "OHT study"
    # the same actor with no email, locally, is not the owner either: ownership is the email once there is one
    assert behind_access.get("/v1/projects", headers={access.HEADER: token(email="someone-else@example.com")}).json() == []
