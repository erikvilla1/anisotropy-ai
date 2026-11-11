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
    assert client.get("/v1/coupon-tests").json() == {"all": False}
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "on")
    assert client.get("/v1/coupon-tests").json() == {"all": True}


def test_the_startup_settings_answer_when_they_are_there(monkeypatch):
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "on")  # the settings read at startup win over a later change of the environment
    monkeypatch.setattr(app.state, "settings", load_settings({RECORDING_VARIABLE: "off"}), raising=False)
    assert client.get("/v1/coupon-tests").json() == {"all": False}


# --------------------------------------------------------------------------------------------- part 2: a stored coupon of a hidden test

import sys

from anisotropy_api.coupon_jobs import CouponJobs
from anisotropy_api.main import job_recorder

HIDDEN_STAND_IN = '''import sys
name = sys.argv[sys.argv.index("values") + 1]
if name == "IM7-OHT-L1":
    sys.exit(f"studio_tool: {name}: its test, open-hole tension, is not available yet: the studio offers the unnotched tension coupon, "
             "under ASTM D3039 or no standard, until its comparison with Abaqus is validated; the coupon is kept")
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
    assert answer.json()["detail"].startswith("IM7-OHT-L1: its test, open-hole tension, is not available yet")
    assert client.get("/v1/coupons/OTHER/values").status_code == 503  # any other failure of the tool stays a 503
