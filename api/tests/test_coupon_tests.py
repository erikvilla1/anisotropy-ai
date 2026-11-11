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
