"""Uploads from Abaqus through the API (ADR-0094 part 6, step 5): a bundle is checked by the fea package's own command, stored under a
prefix of its own with its owner's row, put beside a finished run of ours, read back and deleted by its owner alone; to a second
user it does not exist; the founders named in the settings see it and change nothing; the connector sends with a token that is
shown once and refused once cancelled; behind Cloudflare Access the connector's one route passes on its token only when the settings
say so.

The bundles and the run of ours are made once by `abaqus_bundles.py` in the fea environment, and the check and the comparison are the
real `fea/tools/abaqus_upload.py`: no stand-in judges a bundle here. No Abaqus runs: their side is our own kernel's run."""

import datetime as dt
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anisotropy_api import access, main, uploads
from anisotropy_api.coupon_jobs import FEA, CouponJobs, Job
from anisotropy_api.main import app, job_recorder
from anisotropy_api.records import fetch_upload, insert_job, update_job
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, AccessSettings
from anisotropy_api.storage import FolderStore

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, token
from conftest import TEST_URL, needs_test_database
from memory_store import FailingStore, MemoryStore

COUPON = "D3039-CHECK"
OTHER = "someone-else@example.com"
FOUNDER = "founder@example.com"
ROUTE, TOKENS, CONNECTOR = "/v1/abaqus-uploads", "/v1/upload-tokens", "/v1/connector/uploads"
EXCHANGE, CONNECTOR_ZIP = "/v1/abaqus-exchange", "/v1/abaqus-connector"  # what the page's card asks first, and the connector to hand out (step 6)
LIMITS = {"max_bundle_bytes": 50 * 1024 * 1024, "max_uploads": 100, "max_tokens": 10}
needs_uv = pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH: the bundles are made and judged by the fea package's tools")
pytestmark = [needs_test_database, needs_uv]


@pytest.fixture(scope="session")
def made(tmp_path_factory) -> Path:
    """The bundles and the package of a run of ours, written once by the fea environment."""
    folder = tmp_path_factory.mktemp("abaqus-bundles")
    done = subprocess.run([shutil.which("uv"), "run", "--project", str(FEA), "python", str(Path(__file__).with_name("abaqus_bundles.py")), str(folder)],
                          capture_output=True, text=True, timeout=600, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return folder


def bundle(made: Path, name: str) -> bytes:
    return (made / f"{name}.zip").read_bytes()


def started(tmp_path, engine, monkeypatch, store=None, founders=frozenset()):
    """The app's own registry and uploads replaced by ones on this test's folder: a folder on the disk for the bundles, or `store`."""
    registry = CouponJobs([sys.executable, "no-tool.py"], job_recorder(app), tmp_path / "jobs", store=store, table=engine)
    kept = uploads.Uploads(store if store is not None else FolderStore(tmp_path / "kept"), uploads.tool_command(), founders=founders,
                           scratch=tmp_path / "scratch")
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    monkeypatch.setattr(app.state, "uploads", kept, raising=False)
    return registry, kept


@pytest.fixture
def local(empty_runs, monkeypatch, tmp_path):
    """The local API: run records on, no sign-in, the bundles in a folder of the disk. Yields (client, registry, uploads, engine)."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        registry, kept = started(tmp_path, empty_runs, monkeypatch)
        yield client, registry, kept, empty_runs


@pytest.fixture
def hosted(empty_runs, monkeypatch, tmp_path):
    """The API behind Cloudflare Access with a bucket: each request carries its own token. Yields (client, registry, store, engine)."""
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    store = MemoryStore()
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as client:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        registry, _kept = started(tmp_path, empty_runs, monkeypatch, store=store, founders=frozenset({FOUNDER}))
        yield client, registry, store, empty_runs


def signed(email: str = EMAIL) -> dict:
    return {access.HEADER: token(email=email)}


def as_a_link(client, url: str, **more):
    """As a browser follows a link on the page: the request carries no actor header."""
    kept = client.headers.pop("X-Anisotropy-Actor")
    try:
        return client.get(url, **more)
    finally:
        client.headers["X-Anisotropy-Actor"] = kept


def run_on_this_disk(registry: CouponJobs, engine, made: Path, actor: str = "studio", state: str = "done") -> uuid.UUID:
    """A finished job of this process with its package folder in the job's own folder, as the local API has it."""
    job_id, now = uuid.uuid4(), dt.datetime.now(dt.timezone.utc)
    folder = registry.root / str(job_id)
    package = folder / f"2026-11-13_{COUPON}"
    shutil.copytree(made / "package" / package.name, package)
    insert_job(engine, job_id=job_id, actor=actor, user_email=None, inputs={"coupon": COUPON}, started_at=now, process=registry.process)
    update_job(engine, job_id, state=state, coupon=COUPON, attempt="attempt-01", finished_at=now, outputs={"package": str(package)})
    outcome = {"status": state, "message": "done", "coupon": COUPON, "attempt": "attempt-01", "outputs": {"package": str(package)}}
    registry.jobs[job_id] = Job(job_id, actor, {"coupon": COUPON}, folder, now, state=state, finished_at=now, outcome=outcome)
    return job_id


def run_in_the_bucket(registry: CouponJobs, engine, made: Path, email: str = EMAIL) -> uuid.UUID:
    """A finished job another container ran: its row in the jobs table, its package as the zip the store keeps."""
    job_id, now = uuid.uuid4(), dt.datetime.now(dt.timezone.utc)
    name = f"2026-11-13_{COUPON}"
    archive = shutil.make_archive(str(registry.root / f"{job_id}-package"), "zip", root_dir=made / "package", base_dir=name)
    key = f"coupons/{COUPON}/attempt-01/package.zip"
    registry.store.put(key, Path(archive), "application/zip")
    insert_job(engine, job_id=job_id, actor="browser", user_email=email, inputs={"coupon": COUPON}, started_at=now, process="another-container")
    update_job(engine, job_id, state="done", coupon=COUPON, attempt="attempt-01", finished_at=now, stored={"package": key},
               outputs={"package": f".local/fea/{COUPON}/documents/{name}"})
    return job_id


# ------------------------------------------------------------------------------------------------------- without the database

def test_without_run_records_the_uploads_answer_503(monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "off")
    with TestClient(app, headers={"X-Anisotropy-Actor": "studio"}) as client:
        for answer in (client.post(ROUTE, content=b"PK"), client.get(ROUTE), client.get(f"{ROUTE}/{uuid.uuid4()}"), client.delete(f"{ROUTE}/{uuid.uuid4()}"),
                       client.post(TOKENS, json={"name": "x"}), client.get(TOKENS), client.post(CONNECTOR, content=b"PK")):
            assert answer.status_code == 503 and "switched off" in answer.json()["detail"]
        assert client.get(EXCHANGE).json() == {"uploads": False, "connector_route": True, **LIMITS}  # so the page's card offers nothing here


# ------------------------------------------------------------------------------------------------------- a bundle, stored

def test_a_bundle_is_checked_stored_read_back_and_deleted_by_its_owner_alone(local, made):
    client, _registry, kept, engine = local
    sent = client.post(ROUTE, content=bundle(made, "agrees"), headers={"Content-Type": "application/zip"})
    assert sent.status_code == 201, sent.text
    upload = sent.json()
    assert upload["actor"] == "studio" and upload["user_email"] is None and upload["token_id"] is None and upload["may_train"] is False
    assert upload["units"] == "mm-MPa" and upload["job"] == "Job-1" and upload["coupon"] == COUPON and upload["in_scope"] is True
    assert upload["bundle_bytes"] == len(bundle(made, "agrees")) and upload["bundle_sha256"] == upload["facts"]["bundle"]["sha256"]
    assert upload["facts"]["deck"]["elements"] == 1488 and upload["facts"]["every_output"] == {"read": True, "rows": 11904, "elements": 1488, "layers": 8}
    assert upload["verdict"] is None and upload["comparison"] is None and upload["job_id"] is None
    assert upload["not_compared"] == f"you have no finished run of {COUPON} here to stand beside it: run the coupon, or name a run with job_id"
    assert kept.store.keys("") == [f"uploads/{upload['id']}/bundle.zip"]  # one object, under its own prefix, outside every coupon's
    assert str(kept.scratch) not in sent.text and not list(kept.scratch.iterdir())  # no path of this machine, nothing left behind

    listed = client.get(ROUTE).json()
    assert [u["id"] for u in listed] == [upload["id"]] and listed[0]["facts"] is None and listed[0]["comparison"] is None  # the list is light
    assert client.get(f"{ROUTE}/{upload['id']}").json() == upload
    back = client.get(f"{ROUTE}/{upload['id']}/bundle")
    assert back.status_code == 200 and back.content == bundle(made, "agrees") and "Job-1-anisotropy.zip" in back.headers["content-disposition"]

    linked = as_a_link(client, f"{ROUTE}/{upload['id']}/bundle", params={"actor": "studio"})  # the page's link: no header, the actor in the address
    assert linked.status_code == 200 and linked.content == bundle(made, "agrees")
    assert as_a_link(client, f"{ROUTE}/{upload['id']}/bundle").status_code == 422  # a link that names no actor is refused, as a request without the header is
    assert as_a_link(client, f"{ROUTE}/{upload['id']}/bundle", params={"actor": "test"}).status_code == 404  # and another actor's link finds nothing
    assert as_a_link(client, f"{ROUTE}/{upload['id']}", params={"actor": "studio"}).status_code == 422  # the one route a link asks for; every other needs the header

    stranger = {"X-Anisotropy-Actor": "test"}  # locally the owner is the actor, as a project's is
    assert client.get(ROUTE, headers=stranger).json() == []
    for answer in (client.get(f"{ROUTE}/{upload['id']}", headers=stranger), client.get(f"{ROUTE}/{upload['id']}/bundle", headers=stranger),
                   client.get(f"{ROUTE}/{upload['id']}/bundle", params={"actor": "studio"}, headers=stranger),  # the header is the one that counts when both are there
                   client.post(f"{ROUTE}/{upload['id']}/compare", headers=stranger), client.delete(f"{ROUTE}/{upload['id']}", headers=stranger)):
        assert answer.status_code == 404 and answer.json()["detail"] == f"No upload {upload['id']} of yours"
    assert client.get(f"{ROUTE}/{uuid.uuid4()}").status_code == 404
    assert kept.store.keys("") == [f"uploads/{upload['id']}/bundle.zip"]  # the stranger's delete removed nothing

    assert client.delete(f"{ROUTE}/{upload['id']}").status_code == 204
    assert kept.store.keys("") == [] and fetch_upload(engine, uuid.UUID(upload["id"])) is None and client.get(ROUTE).json() == []
    assert client.get(f"{ROUTE}/{upload['id']}").status_code == 404 and client.delete(f"{ROUTE}/{upload['id']}").status_code == 404


def test_a_file_that_is_not_a_bundle_is_refused_with_every_reason_and_nothing_is_stored(local, made, monkeypatch):
    client, _registry, kept, _engine = local
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("../escape.txt", "out of the zip")
        archive.writestr("run.py", "print('never run')")
    for body, reasons in ((b"not a zip at all", ["not a zip file"]),
                          (packed.getvalue(), ["the member '../escape.txt'", "no manifest.json at the top of the zip"])):
        refused = client.post(ROUTE, content=body)
        assert refused.status_code == 422 and refused.json()["detail"].startswith("Not a bundle this version takes, so nothing was stored: ")
        assert all(reason in refused.json()["detail"] for reason in reasons) and str(kept.scratch) not in refused.text
    assert client.post(ROUTE, content=b"").status_code == 422 and "has no body" in client.post(ROUTE, content=b"").json()["detail"]
    monkeypatch.setattr(main, "MAX_BUNDLE_BYTES", 1000)
    assert client.post(ROUTE, content=bytes(1001)).status_code == 413
    assert kept.store.keys("") == [] and client.get(ROUTE).json() == []
    assert client.get(ROUTE, headers={"X-Anisotropy-Actor": "nobody"}).status_code == 422  # the actor header, as every route


def test_a_person_stores_so_many_uploads_and_no_more(local, made, monkeypatch):
    client, _registry, kept, _engine = local
    monkeypatch.setattr(main, "MAX_UPLOADS", 1)
    first = client.post(ROUTE, content=bundle(made, "unnamed"))
    assert first.status_code == 201
    full = client.post(ROUTE, content=bundle(made, "unnamed"))
    assert full.status_code == 429 and "delete one to send another" in full.json()["detail"] and len(kept.store.keys("")) == 1
    assert client.post(ROUTE, content=bundle(made, "unnamed"), headers={"X-Anisotropy-Actor": "test"}).status_code == 201  # another's count is their own
    assert client.delete(f"{ROUTE}/{first.json()['id']}").status_code == 204
    assert client.post(ROUTE, content=bundle(made, "unnamed")).status_code == 201


def test_a_bundle_that_cannot_be_stored_leaves_no_row(local, made):
    client, _registry, kept, _engine = local
    kept.store = FailingStore()
    refused = client.post(ROUTE, content=bundle(made, "unnamed"))
    assert refused.status_code == 503 and refused.json()["detail"] == "The bundle could not be stored: the bucket refused the upload: AccessDenied"
    assert client.get(ROUTE).json() == []


# ------------------------------------------------------------------------------------------------------- beside a run of ours

def test_an_upload_stands_beside_the_owners_run_of_its_coupon(local, made):
    client, registry, _kept, engine = local
    job_id = run_on_this_disk(registry, engine, made)
    run_on_this_disk(registry, engine, made, actor="test")  # another person's newer run of the same coupon is not picked
    agrees = client.post(ROUTE, content=bundle(made, "agrees")).json()
    assert agrees["verdict"] == "agrees" and agrees["job_id"] == str(job_id) and agrees["not_compared"] is None and agrees["compared_at"] is not None
    comparison = agrees["comparison"]
    assert comparison["ours"]["coupon"] == COUPON and comparison["pairing"]["same_mesh"] is True and comparison["pairing"]["elements"] == 1488
    assert {c["criterion"]: c["met"] for c in comparison["criteria"]} == {c["criterion"]: True for c in comparison["criteria"]} and len(comparison["criteria"]) >= 3
    assert comparison["model"]["same"] is True and set(comparison["compared_by"]) == {"api", "git_commit"}
    assert client.get(ROUTE).json()[0]["verdict"] == "agrees"

    differs = client.post(ROUTE, content=bundle(made, "differs")).json()
    assert differs["verdict"] == "differs" and differs["job_id"] == str(job_id)
    assert [c["criterion"] for c in differs["comparison"]["criteria"] if c["met"] is False] == ["Reaction within 1 %"]


def test_a_run_is_named_when_the_bundle_names_no_coupon_and_a_comparison_asked_for_answers_why_not(local, made):
    client, registry, _kept, engine = local
    job_id = run_on_this_disk(registry, engine, made)
    running = run_on_this_disk(registry, engine, made, state="running")
    unnamed = client.post(ROUTE, content=bundle(made, "unnamed")).json()
    assert unnamed["verdict"] is None and "names no coupon of ours" in unnamed["not_compared"]
    named = client.post(ROUTE, content=bundle(made, "unnamed"), params={"job_id": str(job_id), "may_train": "true"}).json()
    assert named["verdict"] == "agrees" and named["job_id"] == str(job_id) and named["may_train"] is True

    path = f"{ROUTE}/{unnamed['id']}/compare"
    for params, status, reason in (({}, 409, "names no coupon of ours"), ({"job_id": str(uuid.uuid4())}, 409, "there is no coupon job"),
                                   ({"job_id": str(running)}, 409, "is running; an upload stands beside a run that is done"),
                                   ({"job_id": "not-an-id"}, 422, "uuid")):
        refused = client.post(path, params=params)
        assert refused.status_code == status and reason in str(refused.json()["detail"]).lower().replace("uuid_parsing", "uuid")
    later = client.post(path, params={"job_id": str(job_id)})
    assert later.status_code == 200 and later.json()["verdict"] == "agrees" and later.json()["not_compared"] is None
    again = client.post(path, params={"job_id": str(running)})  # a comparison that cannot be made leaves the one there is
    assert again.status_code == 409 and client.get(f"{ROUTE}/{unnamed['id']}").json()["verdict"] == "agrees"


def test_the_page_is_told_what_it_may_offer_and_lists_the_uploads_beside_one_run(local, made):
    client, registry, _kept, engine = local
    assert client.get(EXCHANGE).json() == {"uploads": True, "connector_route": True, **LIMITS}  # no sign-in in front: the connector's route is open
    first, second = run_on_this_disk(registry, engine, made), run_on_this_disk(registry, engine, made)
    beside_first = client.post(ROUTE, content=bundle(made, "agrees"), params={"job_id": str(first)}).json()
    beside_second = client.post(ROUTE, content=bundle(made, "differs"), params={"job_id": str(second)}).json()
    unnamed = client.post(ROUTE, content=bundle(made, "unnamed")).json()  # beside no run
    assert {u["id"] for u in client.get(ROUTE).json()} == {beside_first["id"], beside_second["id"], unnamed["id"]}
    assert [u["id"] for u in client.get(ROUTE, params={"job_id": str(first)}).json()] == [beside_first["id"]]
    assert [u["id"] for u in client.get(ROUTE, params={"job_id": str(second), "mine": "true"}).json()] == [beside_second["id"]]
    assert client.get(ROUTE, params={"job_id": str(uuid.uuid4())}).json() == [] and client.get(ROUTE, params={"job_id": "x"}).status_code == 422


def test_the_connector_is_handed_out_as_one_zip_the_same_each_time(local):
    client, _registry, kept, _engine = local
    answer = client.get(CONNECTOR_ZIP)
    assert answer.status_code == 200 and answer.headers["content-type"] == "application/zip"
    assert 'filename="anisotropy-connector.zip"' in answer.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(answer.content)) as archive:
        assert sorted(archive.namelist()) == [f"anisotropy-connector/{name}" for name in (
            "README.txt", "abaqus_every_output.py", "abaqus_extract_fields.py", "anisotropy_connector.py", "anisotropy_menu.py",
            "anisotropy_plugin.py", "bundle.py")]  # the last three with the menu in Abaqus/CAE (step 8)
        assert archive.read("anisotropy-connector/anisotropy_connector.py") == (FEA / "tools" / "anisotropy_connector.py").read_bytes()
    assert client.get(CONNECTOR_ZIP).content == answer.content and (kept.scratch / "connector" / "anisotropy-connector.zip").is_file()
    kept.command = None  # no uv: the zip already written is still handed out; a fresh process without uv says why not
    assert client.get(CONNECTOR_ZIP).status_code == 200
    (kept.scratch / "connector" / "anisotropy-connector.zip").unlink()
    refused = client.get(CONNECTOR_ZIP)
    assert refused.status_code == 503 and "uv is not on PATH" in refused.json()["detail"]


def test_a_bundle_out_of_scope_is_kept_and_not_compared(local, made):
    client, registry, _kept, engine = local
    job_id = run_on_this_disk(registry, engine, made)
    kept_one = client.post(ROUTE, content=bundle(made, "out-of-scope")).json()
    assert kept_one["in_scope"] is False and kept_one["facts"]["deck"]["read"] is False and kept_one["verdict"] is None
    assert kept_one["not_compared"].startswith("the bundle is out of the comparison's scope")
    assert client.post(f"{ROUTE}/{kept_one['id']}/compare", params={"job_id": str(job_id)}).status_code == 409


def test_only_the_three_files_of_ours_leave_a_packages_zip(tmp_path):
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for name in ("pkg/4-results/ours-every-output.csv", "pkg/4-results/ours-every-output.json", "pkg/2-our-model/abaqus/C-abaqus.inp",
                     "pkg/2-our-model/abaqus/C-build.py", "pkg/4-results/other.csv", "pkg/C.pdf", "../outside-abaqus.inp",
                     "pkg/2-our-model/abaqus/deeper/X-abaqus.inp", "4-results/ours-every-output.csv"):
            package.writestr(name, name)
    uploads._from_archive(archive, tmp_path / "out")
    found = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    assert found == ["out/2-our-model/abaqus/C-abaqus.inp", "out/4-results/ours-every-output.csv", "out/4-results/ours-every-output.json", "package.zip"]


# ------------------------------------------------------------------------------------------------------- behind Access

def test_behind_access_an_upload_is_its_owners_a_second_user_gets_not_found_and_a_founder_sees_it(hosted, made):
    client, registry, store, engine = hosted
    job_id = run_in_the_bucket(registry, engine, made)
    sent = client.post(ROUTE, content=bundle(made, "agrees"), headers=signed())
    assert sent.status_code == 201, sent.text
    upload = sent.json()
    key = f"uploads/{upload['id']}/bundle.zip"
    assert upload["user_email"] == EMAIL and upload["actor"] == "browser" and key in store.objects
    assert upload["verdict"] == "agrees" and upload["job_id"] == str(job_id)  # beside the package the bucket holds

    assert client.get(ROUTE, headers=signed(OTHER)).json() == []
    for answer in (client.get(f"{ROUTE}/{upload['id']}", headers=signed(OTHER)), client.get(f"{ROUTE}/{upload['id']}/bundle", headers=signed(OTHER)),
                   client.post(f"{ROUTE}/{upload['id']}/compare", headers=signed(OTHER)), client.delete(f"{ROUTE}/{upload['id']}", headers=signed(OTHER))):
        assert answer.status_code == 404 and answer.json()["detail"] == f"No upload {upload['id']} of yours"
    assert client.get(ROUTE).status_code == 401  # and no one at all without Access's token

    assert [u["id"] for u in client.get(ROUTE, headers=signed(FOUNDER.upper())).json()] == [upload["id"]]  # the founders also see an upload
    assert client.get(f"{ROUTE}/{upload['id']}", headers=signed(FOUNDER)).json()["user_email"] == EMAIL
    assert client.get(ROUTE, params={"mine": "true"}, headers=signed(FOUNDER)).json() == []  # the page's card lists a founder's own alone
    assert [u["id"] for u in client.get(ROUTE, params={"mine": "true", "job_id": str(job_id)}, headers=signed()).json()] == [upload["id"]]
    assert client.post(f"{ROUTE}/{upload['id']}/compare", headers=signed(FOUNDER)).status_code == 404  # and change nothing
    assert client.delete(f"{ROUTE}/{upload['id']}", headers=signed(FOUNDER)).status_code == 404 and key in store.objects

    link = client.get(f"{ROUTE}/{upload['id']}/bundle", headers=signed(), follow_redirects=False)
    assert link.status_code == 307 and link.headers["location"] == f"https://store.test/{key}?expires=600&filename=Job-1-anisotropy.zip"
    linked = as_a_link(client, f"{ROUTE}/{upload['id']}/bundle", params={"actor": "browser"}, headers=signed(), follow_redirects=False)
    assert linked.status_code == 307 and linked.headers["location"] == link.headers["location"]  # the page's link, signed in: the same short-lived link
    assert as_a_link(client, f"{ROUTE}/{upload['id']}/bundle", params={"actor": "browser"}, headers=signed(OTHER), follow_redirects=False).status_code == 404
    assert client.delete(f"{ROUTE}/{upload['id']}", headers=signed()).status_code == 204
    assert key not in store.objects and client.get(ROUTE, headers=signed(FOUNDER)).json() == []


# ------------------------------------------------------------------------------------------------------- the document (step 7)

DOCUMENT_STUB = [sys.executable, str(Path(__file__).with_name("document_stub.py"))]
TECTONIC = shutil.which("tectonic") is not None or (Path.home() / "AppData/Local/Programs/tectonic/tectonic.exe").exists()  # docs/manual/build.py `tectonic`


def stub_said(pdf: bytes) -> dict:
    assert pdf.startswith(b"%PDF-1.4\n")
    return json.loads(pdf.split(b"\n", 1)[1])


def test_the_comparison_is_written_as_a_document_kept_with_the_upload_and_deleted_with_it(local, made, monkeypatch, tmp_path):
    client, registry, kept, engine = local
    log = tmp_path / "stub.log"
    monkeypatch.setattr(kept, "writer", DOCUMENT_STUB)
    monkeypatch.setenv("DOCUMENT_STUB_LOG", str(log))
    upload = client.post(ROUTE, content=bundle(made, "differs")).json()
    address, bundle_key = f"{ROUTE}/{upload['id']}/document", f"uploads/{upload['id']}/bundle.zip"
    for answer in (client.post(address), client.get(address)):  # no run of ours beside it yet: nothing to print
        assert answer.status_code == 409 and answer.json()["detail"] == f"Not compared: {upload['not_compared']}"
    assert not log.exists() and kept.store.keys("") == [bundle_key]

    job_id = run_on_this_disk(registry, engine, made)
    compared = client.post(f"{ROUTE}/{upload['id']}/compare").json()
    assert compared["verdict"] == "differs"
    when = dt.datetime.fromisoformat(compared["compared_at"])
    key = f"uploads/{upload['id']}/compared-{when.astimezone(dt.timezone.utc):%Y%m%dT%H%M%S%f}Z.pdf"
    written = client.post(address)
    assert written.status_code == 200 and written.json() == {"upload_id": upload["id"], "compared_at": compared["compared_at"],
                                                              "filename": "Job-1-compared-with-anisotropy.pdf"}
    assert kept.store.keys("") == [bundle_key, key]  # beside the bundle, under the upload's own prefix: never in the run's files
    assert not any(registry.root.rglob("*.pdf")) and not list(kept.scratch.iterdir())

    got = client.get(address)
    assert got.status_code == 200 and got.headers["content-type"] == "application/pdf"
    assert "Job-1-compared-with-anisotropy.pdf" in got.headers["content-disposition"]
    assert stub_said(got.content) == {"upload": upload["id"], "run": f"our run {job_id}", "verdict": "differs",
                                      "compared": f"{when.astimezone(dt.timezone.utc):%Y-%m-%d %H:%M} UTC"}  # written from the row's comparison
    linked = as_a_link(client, address, params={"actor": "studio"})  # the page's link
    assert linked.status_code == 200 and linked.content == got.content
    assert log.read_text(encoding="utf-8").splitlines() == [f"{upload['id']} pdf"]  # written once, then handed out from the store
    assert as_a_link(client, address).status_code == 422
    stranger = {"X-Anisotropy-Actor": "test"}
    for answer in (client.get(address, headers=stranger), client.post(address, headers=stranger), as_a_link(client, address, params={"actor": "test"})):
        assert answer.status_code == 404 and answer.json()["detail"] == f"No upload {upload['id']} of yours"

    again = client.post(f"{ROUTE}/{upload['id']}/compare").json()  # a new comparison: the document of the last one is not handed out for it
    assert again["compared_at"] != compared["compared_at"]
    later = dt.datetime.fromisoformat(again["compared_at"])
    new_key = f"uploads/{upload['id']}/compared-{later.astimezone(dt.timezone.utc):%Y%m%dT%H%M%S%f}Z.pdf"
    assert stub_said(client.get(address).content)["compared"] == f"{later.astimezone(dt.timezone.utc):%Y-%m-%d %H:%M} UTC"
    assert kept.store.keys("") == [bundle_key, new_key] and len(log.read_text(encoding="utf-8").splitlines()) == 2

    assert client.delete(f"{ROUTE}/{upload['id']}").status_code == 204
    assert kept.store.keys("") == [] and client.get(address).status_code == 404  # the document goes with the upload


def test_a_document_that_cannot_be_written_is_answered_with_the_reason_and_nothing_is_kept(local, made, monkeypatch):
    client, registry, kept, engine = local
    monkeypatch.setattr(kept, "writer", DOCUMENT_STUB)
    run_on_this_disk(registry, engine, made)
    upload = client.post(ROUTE, content=bundle(made, "agrees")).json()
    address = f"{ROUTE}/{upload['id']}/document"
    said = {"refused": (409, "Not compared: the comparison was refused, so there is nothing to print: a stand-in's reason"),
            "latex": (503, "The document could not be written: the document was not compiled: Tectonic is not installed, so no PDF was written"),
            "silent": (503, "The document could not be written: the bundle's command failed: the stand-in stopped before it answered")}
    for mode, (status, detail) in said.items():
        monkeypatch.setenv("DOCUMENT_STUB", mode)
        for answer in (client.post(address), client.get(address)):
            assert answer.status_code == status and answer.json()["detail"] == detail
    monkeypatch.setattr(kept, "writer", None)
    monkeypatch.setattr(uploads, "document_command", lambda: None)
    assert client.get(address).status_code == 503 and "uv is not on PATH" in client.get(address).json()["detail"]
    assert kept.store.keys("") == [f"uploads/{upload['id']}/bundle.zip"] and str(kept.scratch) not in client.get(address).text
    assert not list(kept.scratch.iterdir())


def test_the_real_command_writes_the_document_where_tectonic_is_installed_and_says_so_where_it_is_not(local, made):
    """`docs/models/upload.py` itself, from a comparison the real command made. CI's api job has no Tectonic; a machine that has it
    gets the PDF."""
    client, registry, kept, engine = local
    run_on_this_disk(registry, engine, made)
    upload = client.post(ROUTE, content=bundle(made, "differs")).json()
    got = client.get(f"{ROUTE}/{upload['id']}/document")
    if TECTONIC:
        assert got.status_code == 200 and got.content.startswith(b"%PDF") and len(kept.store.keys("")) == 2
    else:
        assert got.status_code == 503, got.text
        assert got.json()["detail"] == "The document could not be written: the document was not compiled: Tectonic is not installed, so no PDF was written"
        assert kept.store.keys("") == [f"uploads/{upload['id']}/bundle.zip"]
    assert not list(kept.scratch.iterdir())


def test_behind_access_the_document_is_a_short_lived_link_for_its_owner_and_the_founders_alone(hosted, made, monkeypatch):
    client, registry, store, engine = hosted
    monkeypatch.setattr(app.state.uploads, "writer", DOCUMENT_STUB)
    run_in_the_bucket(registry, engine, made)
    upload = client.post(ROUTE, content=bundle(made, "agrees"), headers=signed()).json()
    assert upload["verdict"] == "agrees"
    address = f"{ROUTE}/{upload['id']}/document"
    when = dt.datetime.fromisoformat(upload["compared_at"])
    key = f"uploads/{upload['id']}/compared-{when.astimezone(dt.timezone.utc):%Y%m%dT%H%M%S%f}Z.pdf"
    for answer in (client.get(address, headers=signed(OTHER)), client.post(address, headers=signed(OTHER))):  # to a second user it does not exist
        assert answer.status_code == 404
    assert key not in store.objects and client.get(address).status_code == 401

    link = as_a_link(client, address, params={"actor": "browser"}, headers=signed(), follow_redirects=False)  # the page's link, signed in
    assert link.status_code == 307 and link.headers["location"] == f"https://store.test/{key}?expires=600&filename=Job-1-compared-with-anisotropy.pdf"
    assert store.objects[key][1] == "application/pdf" and stub_said(store.objects[key][0])["upload"] == upload["id"]
    founder = client.get(address, headers=signed(FOUNDER), follow_redirects=False)  # the founders also read it
    assert founder.status_code == 307 and founder.headers["location"] == link.headers["location"]
    assert client.delete(f"{ROUTE}/{upload['id']}", headers=signed()).status_code == 204
    assert not [k for k in store.objects if k.startswith(f"uploads/{upload['id']}/")]


# ------------------------------------------------------------------------------------------------------- the tokens

def test_a_token_is_shown_once_sends_for_its_owner_and_is_refused_once_cancelled(hosted, made, monkeypatch):
    client, registry, store, engine = hosted
    run_in_the_bucket(registry, engine, made)
    created = client.post(TOKENS, json={"name": "the Abaqus workstation"}, headers=signed())
    assert created.status_code == 201
    secret, token_id = created.json()["token"], created.json()["id"]
    assert secret.startswith("anisotropy_upload_") and len(secret) > 50 and created.json()["hint"] == secret[-4:]
    listed = client.get(TOKENS, headers=signed())
    assert [(t["id"], t["name"], t["last_used_at"], t["revoked_at"]) for t in listed.json()] == [(token_id, "the Abaqus workstation", None, None)]
    assert secret not in listed.text and "token" not in listed.json()[0] and client.get(TOKENS, headers=signed(OTHER)).json() == []
    with engine.connect() as connection:  # the database holds the digest alone
        kept = connection.exec_driver_sql("SELECT token_sha256 FROM upload_tokens").scalar()
    assert kept == uploads.token_digest(secret) and secret not in kept

    monkeypatch.setattr(app.state, "connector_uploads", True, raising=False)  # the connector's route, open to an upload token
    bearer = {"Authorization": f"Bearer {secret}"}
    sent = client.post(CONNECTOR, content=bundle(made, "agrees"), headers={**bearer, "X-Anisotropy-Actor": ""})  # no actor header, no Access token
    assert sent.status_code == 201, sent.text
    upload = sent.json()
    assert upload["user_email"] == EMAIL and upload["actor"] == "browser" and upload["token_id"] == token_id and upload["verdict"] == "agrees"
    assert client.get(TOKENS, headers=signed()).json()[0]["last_used_at"] is not None
    assert [u["id"] for u in client.get(ROUTE, headers=signed()).json()] == [upload["id"]] and client.get(ROUTE, headers=signed(OTHER)).json() == []

    assert client.delete(f"{TOKENS}/{token_id}", headers=signed(OTHER)).status_code == 404  # another's token is not theirs to cancel
    assert client.post(CONNECTOR, content=bundle(made, "agrees"), headers=bearer).status_code == 201
    cancelled = client.delete(f"{TOKENS}/{token_id}", headers=signed())
    assert cancelled.status_code == 200 and cancelled.json()["revoked_at"] is not None
    assert client.delete(f"{TOKENS}/{token_id}", headers=signed()).json()["revoked_at"] == cancelled.json()["revoked_at"]  # once
    before = sorted(store.objects)
    for headers in (bearer, {}, {"Authorization": "Bearer anisotropy_upload_" + "x" * 43}, {"Authorization": f"Basic {secret}"}, {"Authorization": secret}):
        refused = client.post(CONNECTOR, content=bundle(made, "agrees"), headers=headers)
        assert refused.status_code == 401 and "a cancelled token is refused" in refused.json()["detail"] and refused.headers["www-authenticate"] == "Bearer"
    assert sorted(store.objects) == before and len(client.get(ROUTE, headers=signed()).json()) == 2  # what it sent before stands
    assert client.get(f"{ROUTE}/{upload['id']}", headers=signed()).json()["token_id"] == token_id


def test_a_person_has_so_many_live_tokens_and_no_more(local, monkeypatch):
    client, _registry, _kept, _engine = local
    monkeypatch.setattr(main, "MAX_TOKENS", 2)
    first = client.post(TOKENS, json={}).json()
    assert client.post(TOKENS, json={"name": "second"}).status_code == 201
    full = client.post(TOKENS, json={"name": "third"})
    assert full.status_code == 429 and "cancel one to create another" in full.json()["detail"]
    assert client.post(TOKENS, json={"name": "x" * 101}).status_code == 422 and client.post(TOKENS, json={"token": "mine"}).status_code == 422
    assert client.delete(f"{TOKENS}/{first['id']}").status_code == 200
    assert client.post(TOKENS, json={"name": "third"}).status_code == 201 and len(client.get(TOKENS).json()) == 3
    assert client.post(TOKENS, json={}, headers={"X-Anisotropy-Actor": "test"}).status_code == 201  # another's count is their own


def test_behind_access_the_connectors_route_passes_on_its_token_only_when_the_settings_say_so(hosted, made, monkeypatch):
    client, _registry, store, _engine = hosted
    secret = client.post(TOKENS, json={"name": "workstation"}, headers=signed()).json()["token"]
    bearer = {"Authorization": f"Bearer {secret}"}
    closed = client.post(CONNECTOR, content=bundle(made, "unnamed"), headers=bearer)  # the setting is off: Access's token is needed, as everywhere
    assert closed.status_code == 401 and "behind Cloudflare Access" in closed.json()["detail"] and store.objects == {}
    both = client.post(CONNECTOR, content=bundle(made, "unnamed"), headers={**bearer, **signed(OTHER)})  # through Access, the upload token still names the owner
    assert both.status_code == 201 and both.json()["user_email"] == EMAIL
    assert client.post(CONNECTOR, content=bundle(made, "unnamed"), headers=signed()).status_code == 401  # Access's token alone is not an upload token

    assert client.get(EXCHANGE, headers=signed()).json() == {"uploads": True, "connector_route": False, **LIMITS}  # the page offers no upload key yet
    assert client.get(EXCHANGE).status_code == 401 and client.get(CONNECTOR_ZIP).status_code == 401  # both behind the sign-in, as everything is

    monkeypatch.setattr(app.state, "connector_uploads", True, raising=False)
    assert client.get(EXCHANGE, headers=signed()).json()["connector_route"] is True
    assert client.post(CONNECTOR, content=bundle(made, "unnamed"), headers=bearer).status_code == 201
    for answer in (client.get(ROUTE, headers=bearer), client.get(f"{ROUTE}/{both.json()['id']}", headers=bearer), client.get(TOKENS, headers=bearer),
                   client.post(ROUTE, content=bundle(made, "unnamed"), headers=bearer), client.post(TOKENS, json={}, headers=bearer),
                   client.get(CONNECTOR, headers=bearer), client.delete(f"{ROUTE}/{both.json()['id']}", headers=bearer)):
        assert answer.status_code == 401 and "behind Cloudflare Access" in answer.json()["detail"]  # an upload token opens one route, one method


def test_the_connectors_own_request_is_what_the_route_takes(local, made, tmp_path):
    """`fea/tools/anisotropy_connector.py --send`'s request, built by the connector itself, answered by the API."""
    client, registry, _kept, engine = local
    job_id = run_on_this_disk(registry, engine, made)
    spec = importlib.util.spec_from_file_location("connector_under_test", FEA / "tools" / "anisotropy_connector.py")
    connector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(connector)
    secret = client.post(TOKENS, json={"name": "workstation"}).json()["token"]
    assert secret.startswith(connector.TOKEN_PREFIX) and connector.SEND_ROUTE == CONNECTOR

    def poster(request, timeout):
        assert request.get_method() == "POST"
        path = request.full_url.removeprefix("http://localhost:8000")
        answer = client.post(path, content=request.data, headers={**dict(request.header_items()), "X-Anisotropy-Actor": ""})
        return answer.status_code, answer.content

    answer = connector.send(connector.send_address("http://localhost:8000", str(job_id)), secret, made / "agrees.zip", poster)
    assert answer["verdict"] == "agrees" and answer["job_id"] == str(job_id) and answer["bundle_bytes"] == len(bundle(made, "agrees"))
    with pytest.raises(connector.NotSent, match=r"the site refused it \(401\): This route takes a bundle sent with an upload token"):
        connector.send(connector.send_address("http://localhost:8000"), "anisotropy_upload_" + "x" * 43, made / "agrees.zip", poster)
