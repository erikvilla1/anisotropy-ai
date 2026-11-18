"""One workflow first (ADR-0089): the page asks whether every coupon test is offered; the switch is read strictly at startup."""

import pytest
from fastapi.testclient import TestClient

from anisotropy_api.main import app
from anisotropy_api.settings import ALL_TESTS_VARIABLE, RECORDING_VARIABLE, load_settings

client = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: the endpoint reads the environment


@pytest.mark.parametrize(("value", "expected"), [(None, False), ("", False), ("off", False), ("OFF", False), ("on", True), (" On ", True)])
def test_the_switch_is_on_only_when_it_says_on(value, expected):
    environ = {RECORDING_VARIABLE: "off"} | ({} if value is None else {ALL_TESTS_VARIABLE: value})
    assert load_settings(environ).all_tests is expected


@pytest.mark.parametrize("value", ["yes", "1", "true", "all"])
def test_any_other_word_is_refused_at_startup(value):
    with pytest.raises(RuntimeError, match=f"{ALL_TESTS_VARIABLE} must be 'on' or 'off'"):
        load_settings({RECORDING_VARIABLE: "off", ALL_TESTS_VARIABLE: value})


def test_the_page_is_told_whether_every_test_is_offered(monkeypatch):
    monkeypatch.delenv(ALL_TESTS_VARIABLE, raising=False)
    monkeypatch.setattr(app.state, "settings", None, raising=False)
    assert client.get("/v1/coupon-tests").json() == {"all": False, "imports": False}
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "on")
    assert client.get("/v1/coupon-tests").json() == {"all": True, "imports": True}  # where every test is offered, so is the import


def test_the_startup_settings_answer_when_they_are_there(monkeypatch):
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "on")  # the settings read at startup win over a later change of the environment
    monkeypatch.setattr(app.state, "settings", load_settings({RECORDING_VARIABLE: "off"}), raising=False)
    assert client.get("/v1/coupon-tests").json() == {"all": False, "imports": False}


# --------------------------------------------------------------------------------------------- part 2: a stored coupon of a hidden test

import sys

from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import job_recorder

HIDDEN_STAND_IN = '''import sys
name = sys.argv[sys.argv.index("values") + 1]
if name == "IM7-OHT-L1":
    sys.exit(f"studio_tool: {name}: its test, open-hole tension, is not offered yet, and the coupon is kept. This workspace runs the "
             "unnotched tension coupon, under ASTM D3039 or no standard.")
sys.exit("studio_tool: something else went wrong")
'''


@pytest.fixture
def hidden_studio(tmp_path, monkeypatch):
    stand_in = tmp_path / "studio_stand_in.py"
    stand_in.write_text(HIDDEN_STAND_IN, encoding="utf-8")
    registry = CouponJobs(None, job_recorder(app), tmp_path / "jobs", studio=[sys.executable, str(stand_in)])
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    return registry


def test_reopening_a_stored_coupon_of_a_hidden_test_is_a_422_that_says_why(hidden_studio):
    answer = client.get("/v1/coupons/IM7-OHT-L1/values")
    assert answer.status_code == 422
    assert answer.json()["detail"].startswith("IM7-OHT-L1: its test, open-hole tension, is not offered yet")
    assert client.get("/v1/coupons/OTHER/values").status_code == 503  # any other failure of the tool stays a 503


# ------------------------------------------- amendment 5: every test by a switch per request; amendment 6: a founder's sign-in is offered the import alone

import dataclasses
import json
from types import SimpleNamespace

from anisotropy_api import access
from anisotropy_api.live import LiveSolver
from anisotropy_api.main import _every_test, _imports
from anisotropy_api.settings import ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, DATABASE_VARIABLE, FOUNDER_EMAILS_VARIABLE, AccessSettings

from access_tokens import AUDIENCE, EMAIL, TEAM, key_for, token
from conftest import TEST_URL, needs_test_database

FOUNDER = "founder@example.com"
# A studio tool that answers by whether it was started with --every-test before its command, as the real one reads the option: the
# checklist's state says which, and a live answer and a stored coupon's values say it the same way.
SWITCH_STAND_IN = '''import json, sys
from pathlib import Path
argv = sys.argv[1:]
every = argv[0] == "--every-test"
argv = argv[1:] if every else argv
state = "ready" if every else "blocked"
if argv[0] == "values":
    if not every:
        sys.exit(f"studio_tool: {argv[1]}: its test, plate, is not offered yet, and the coupon is kept.")
    print(json.dumps({"test": "plate"}))
    sys.exit(0)
out = Path(argv[argv.index("--out") + 1])
out.mkdir(parents=True, exist_ok=True)
if argv[0] == "tow":
    (out / "tow.json").write_text(json.dumps({"checklist": {"state": state, "items": []}, "result": None}), encoding="utf-8")
else:
    (out / "checklist.json").write_text(json.dumps({"state": state, "items": []}), encoding="utf-8")
'''


def request_of(settings, email):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)), state=SimpleNamespace(user_email=email))


def test_a_founders_sign_in_is_offered_the_import_and_not_every_test_and_nobody_else_either():
    off = load_settings({RECORDING_VARIABLE: "off"})
    founders = dataclasses.replace(off, founder_emails=frozenset({FOUNDER}))
    # every test is the machine's switch alone (amendment 6): a founder sees the product as a customer does
    for email in (FOUNDER, " Founder@Example.com ", "engineer@example.com", None):
        assert _every_test(request_of(founders, email)) is False
    assert _every_test(request_of(dataclasses.replace(off, all_tests=True), None)) is True
    # bringing a model in as a file is a founder's, and anyone's where the switch is on
    assert _imports(request_of(founders, FOUNDER)) is True
    assert _imports(request_of(founders, " Founder@Example.com ")) is True  # as Access writes it, whatever its case
    assert _imports(request_of(founders, "engineer@example.com")) is False
    assert _imports(request_of(founders, None)) is False  # no sign-in: a local user, a service token
    assert _imports(request_of(off, FOUNDER)) is False  # no founders named: nobody
    assert _imports(request_of(dataclasses.replace(off, all_tests=True), None)) is True


@pytest.fixture
def switch_studio(tmp_path, monkeypatch):
    stand_in = tmp_path / "switch_stand_in.py"
    stand_in.write_text(SWITCH_STAND_IN, encoding="utf-8")
    command = [sys.executable, str(stand_in)]
    registry = CouponJobs(None, job_recorder(app), tmp_path / "jobs", studio=command)
    monkeypatch.setattr(app.state, "coupon_jobs", registry, raising=False)
    monkeypatch.setattr(app.state, "live", LiveSolver(command, tmp_path / "live", workers=0), raising=False)
    return registry


@pytest.mark.parametrize("founder", [False, True])  # `founder`: whether every test is offered to the request, as amendment 5 named it
def test_the_tools_are_started_with_the_option_where_every_test_is_offered_and_without_it_otherwise(switch_studio, monkeypatch, founder):
    monkeypatch.setattr("anisotropy_api.main._every_test", lambda request: founder)
    state = "ready" if founder else "blocked"
    values = {"values": {"form_version": "0.9", "test": "plate"}}
    assert client.get("/v1/coupon-tests").json() == {"all": founder, "imports": founder}
    assert client.post("/v1/coupon-jobs/check", json=values).json()["state"] == state
    assert client.post("/v1/coupon-jobs/live", json=values).json()["state"] == state
    reopened = client.get("/v1/coupons/NOM-PLT-L1/values")
    assert (reopened.status_code, reopened.json().get("values")) == ((200, {"test": "plate"}) if founder else (422, None))


def test_nothing_a_request_says_reaches_the_tool_as_the_option(switch_studio, monkeypatch):
    """The option goes before the tool's command, and only the API puts it there: a name or a text that spells it is refused or is a name."""
    monkeypatch.setattr("anisotropy_api.main._every_test", lambda request: False)
    assert client.get("/v1/coupons/--every-test/values").status_code in (404, 422, 503)  # the stand-in reads it as a coupon's name, not offered
    for body in ({"coupon": "--every-test", "run_by": "A. Engineer"}, {"coupon": "IM7-UNT-L1", "run_by": "--every-test"},
                 {"form_name": "--every-test.xlsx", "form_base64": "AA==", "run_by": "A. Engineer"}):
        assert client.post("/v1/coupon-jobs", json=body).status_code == 422, body


def test_a_founders_job_carries_the_option_to_its_tool_and_another_persons_does_not(tmp_path, monkeypatch):
    started = []

    class Recorded:
        def start(self, actor, inputs, options, **more):
            started.append(options)
            raise JobRefused("recorded, not run")

    from anisotropy_api.coupon_jobs import JobRefused
    monkeypatch.setattr(app.state, "coupon_jobs", Recorded(), raising=False)
    for founder in (False, True):
        monkeypatch.setattr("anisotropy_api.main._every_test", lambda request, founder=founder: founder)
        client.post("/v1/coupon-jobs", json={"coupon": "IM7-UNT-L1", "run_by": "A. Engineer"})
    assert started == [["--run-by", "A. Engineer"], ["--run-by", "A. Engineer", "--every-test"]]


@needs_test_database
def test_behind_access_the_founders_sign_in_is_offered_the_import_alone_and_another_neither(empty_runs, monkeypatch):
    monkeypatch.setenv(RECORDING_VARIABLE, "on")
    monkeypatch.setenv(DATABASE_VARIABLE, TEST_URL)
    monkeypatch.setenv(ACCESS_TEAM_DOMAIN_VARIABLE, TEAM)
    monkeypatch.setenv(ACCESS_AUDIENCE_VARIABLE, AUDIENCE)
    monkeypatch.setenv(FOUNDER_EMAILS_VARIABLE, f"Someone@example.com, {FOUNDER}")
    monkeypatch.delenv(ALL_TESTS_VARIABLE, raising=False)
    with TestClient(app, headers={"X-Anisotropy-Actor": "browser"}) as hosted:
        app.state.access_verifier = access.verifier(AccessSettings(TEAM, AUDIENCE), key_for=key_for)
        assert hosted.get("/v1/coupon-tests", headers={access.HEADER: token(email=FOUNDER)}).json() == {"all": False, "imports": True}
        assert hosted.get("/v1/coupon-tests", headers={access.HEADER: token(email=FOUNDER.upper())}).json() == {"all": False, "imports": True}
        assert hosted.get("/v1/coupon-tests", headers={access.HEADER: token(email=EMAIL)}).json() == {"all": False, "imports": False}
