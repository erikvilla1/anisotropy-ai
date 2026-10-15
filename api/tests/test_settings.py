"""Startup configuration: records on by default, refusal without a database, explicit off switch (ADR-0026)."""

import pytest

from anisotropy_api.settings import DATABASE_VARIABLE, RECORDING_VARIABLE, load_settings


def test_records_on_by_default_with_database():
    settings = load_settings({DATABASE_VARIABLE: "postgresql+psycopg://u:p@127.0.0.1:5432/db"})
    assert settings.run_records is True
    assert settings.database_url == "postgresql+psycopg://u:p@127.0.0.1:5432/db"


@pytest.mark.parametrize("environ", [{}, {DATABASE_VARIABLE: ""}, {DATABASE_VARIABLE: "   "}])
def test_refuses_without_database(environ):
    with pytest.raises(RuntimeError) as excinfo:
        load_settings(environ)
    message = str(excinfo.value)
    assert DATABASE_VARIABLE in message and f"{RECORDING_VARIABLE}=off" in message


def test_explicit_off_needs_no_database():
    settings = load_settings({RECORDING_VARIABLE: "off"})
    assert settings.run_records is False
    assert settings.database_url is None


def test_off_keeps_a_database_address_when_given():
    settings = load_settings({RECORDING_VARIABLE: "OFF", DATABASE_VARIABLE: "postgresql+psycopg://u:p@h/db"})
    assert settings.run_records is False
    assert settings.database_url == "postgresql+psycopg://u:p@h/db"


@pytest.mark.parametrize("value", ["false", "0", "no", "yes", ""])
def test_rejects_other_switch_values(value):
    with pytest.raises(RuntimeError, match="must be 'on' or 'off'"):
        load_settings({RECORDING_VARIABLE: value, DATABASE_VARIABLE: "postgresql+psycopg://u:p@h/db"})
