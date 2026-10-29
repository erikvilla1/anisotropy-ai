"""Startup configuration: records on by default, refusal without a database, explicit off switch (ADR-0026)."""

import pytest

from anisotropy_api.settings import ASSISTANT_MODEL_VARIABLE, ASSISTANT_PROVIDER_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE, load_settings


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


# --------------------------------------------------------------------------------------------- the assistant (ADR-0052)

OFF = {RECORDING_VARIABLE: "off"}


def test_the_assistant_is_off_unless_a_provider_is_named():
    settings = load_settings(OFF)
    assert settings.assistant.provider is None and settings.assistant.model is None and not settings.assistant.on
    assert load_settings({**OFF, ASSISTANT_PROVIDER_VARIABLE: "  "}).assistant.on is False


def test_a_named_provider_needs_its_model_and_a_credential():
    with pytest.raises(RuntimeError, match=f"{ASSISTANT_MODEL_VARIABLE} is not set"):
        load_settings({**OFF, ASSISTANT_PROVIDER_VARIABLE: "anthropic", "ANTHROPIC_API_KEY": "k"})
    with pytest.raises(RuntimeError, match="needs a credential: set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN"):
        load_settings({**OFF, ASSISTANT_PROVIDER_VARIABLE: "anthropic", ASSISTANT_MODEL_VARIABLE: "claude-opus-5-5"})
    with pytest.raises(RuntimeError, match="must be one of anthropic or unset"):
        load_settings({**OFF, ASSISTANT_PROVIDER_VARIABLE: "other", ASSISTANT_MODEL_VARIABLE: "m", "ANTHROPIC_API_KEY": "k"})
    settings = load_settings({**OFF, ASSISTANT_PROVIDER_VARIABLE: "Anthropic", ASSISTANT_MODEL_VARIABLE: "claude-opus-5-5", "ANTHROPIC_AUTH_TOKEN": "t"})
    assert settings.assistant.on and settings.assistant.provider == "anthropic" and settings.assistant.model == "claude-opus-5-5"
