"""Startup configuration: records on by default, refusal without a database, explicit off switch (ADR-0026)."""

import pytest
from sqlalchemy.engine import make_url

from anisotropy_api.settings import (ASSISTANT_MODEL_VARIABLE, ASSISTANT_PROVIDER_VARIABLE, DATABASE_VARIABLE, RECORDING_VARIABLE,
                                     UNPOOLED_DATABASE_VARIABLE, database_url_for_migrations, load_settings, sqlalchemy_url,
                                     ACCESS_AUDIENCE_VARIABLE, ACCESS_TEAM_DOMAIN_VARIABLE, ALLOWED_ORIGINS_VARIABLE, LOCAL_ORIGINS,
                                     AccessSettings, allowed_origins)


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


# ------------------------------------------------------------------------------- a hosted server's addresses (ADR-0056)

NEON_STYLE = "postgresql://u:p@ep-x-pooler.aws.neon.tech/db?sslmode=require&channel_binding=require"


def test_plain_postgresql_address_is_routed_to_psycopg_with_its_query_kept():
    routed = make_url(sqlalchemy_url(NEON_STYLE, DATABASE_VARIABLE))
    assert routed.drivername == "postgresql+psycopg"
    assert (routed.username, routed.password, routed.host, routed.database) == ("u", "p", "ep-x-pooler.aws.neon.tech", "db")
    assert dict(routed.query) == {"sslmode": "require", "channel_binding": "require"}
    assert sqlalchemy_url("postgres://u:p@h/db", DATABASE_VARIABLE) == "postgresql+psycopg://u:p@h/db"
    assert load_settings({DATABASE_VARIABLE: NEON_STYLE}).database_url.startswith("postgresql+psycopg://")


def test_psycopg_address_passes_unchanged():
    assert sqlalchemy_url("postgresql+psycopg://u:p@h/db", DATABASE_VARIABLE) == "postgresql+psycopg://u:p@h/db"


@pytest.mark.parametrize("value", ["postgresql+psycopg2://u:p@h/db", "mysql://u:p@h/db", "sqlite:///x.db"])
def test_other_drivers_are_refused_by_name(value):
    with pytest.raises(RuntimeError, match=f"{DATABASE_VARIABLE} must start with postgresql://"):
        load_settings({DATABASE_VARIABLE: value})


def test_unreadable_address_names_the_variable_not_the_value():
    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL is not a database address"):
        sqlalchemy_url("not an address", "TEST_DATABASE_URL")


def test_migrations_prefer_the_unpooled_address():
    environ = {DATABASE_VARIABLE: NEON_STYLE, UNPOOLED_DATABASE_VARIABLE: "postgresql://u:p@ep-x.aws.neon.tech/db?sslmode=require"}
    assert database_url_for_migrations(environ) == "postgresql+psycopg://u:p@ep-x.aws.neon.tech/db?sslmode=require"


def test_migrations_use_the_one_address_of_a_local_server():
    assert database_url_for_migrations({DATABASE_VARIABLE: "postgresql+psycopg://u:p@127.0.0.1:5432/db"}) == "postgresql+psycopg://u:p@127.0.0.1:5432/db"
    with pytest.raises(RuntimeError, match="migrations need the database"):
        database_url_for_migrations({RECORDING_VARIABLE: "off"})


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


# ------------------------------------------------------------------------------------- Cloudflare Access and the origins (ADR-0056)

def test_access_is_off_unless_both_variables_are_set():
    settings = load_settings(OFF)
    assert not settings.access.on and settings.access == AccessSettings(None, None)


def test_access_is_on_with_both_and_the_addresses_follow():
    settings = load_settings({**OFF, ACCESS_TEAM_DOMAIN_VARIABLE: " MyTeam.cloudflareaccess.com ", ACCESS_AUDIENCE_VARIABLE: " aud-tag "})
    assert settings.access.on and settings.access.team_domain == "myteam.cloudflareaccess.com" and settings.access.audience == "aud-tag"
    assert settings.access.issuer == "https://myteam.cloudflareaccess.com"
    assert settings.access.certs_url == "https://myteam.cloudflareaccess.com/cdn-cgi/access/certs"


@pytest.mark.parametrize("environ, missing", [({ACCESS_TEAM_DOMAIN_VARIABLE: "t.cloudflareaccess.com"}, ACCESS_AUDIENCE_VARIABLE),
                                              ({ACCESS_AUDIENCE_VARIABLE: "aud-tag"}, ACCESS_TEAM_DOMAIN_VARIABLE)])
def test_one_access_variable_without_the_other_is_refused(environ, missing):
    with pytest.raises(RuntimeError, match=missing):
        load_settings({**OFF, **environ})


@pytest.mark.parametrize("domain", ["https://t.cloudflareaccess.com", "t.cloudflareaccess.com/", "example.com", "t", "t.cloudflareaccess.com:443"])
def test_a_domain_that_is_not_a_teams_is_refused(domain):
    with pytest.raises(RuntimeError, match=ACCESS_TEAM_DOMAIN_VARIABLE):
        load_settings({**OFF, ACCESS_TEAM_DOMAIN_VARIABLE: domain, ACCESS_AUDIENCE_VARIABLE: "aud-tag"})


def test_origins_are_the_local_ones_unless_the_variable_replaces_them():
    assert allowed_origins({}) == LOCAL_ORIGINS and load_settings(OFF).allowed_origins == LOCAL_ORIGINS
    given = allowed_origins({ALLOWED_ORIGINS_VARIABLE: " https://studio.example.com, http://localhost:3000 "})
    assert given == ("https://studio.example.com", "http://localhost:3000")
    assert load_settings({**OFF, ALLOWED_ORIGINS_VARIABLE: "https://studio.example.com"}).allowed_origins == ("https://studio.example.com",)


@pytest.mark.parametrize("value", ["studio.example.com", "https://studio.example.com/", "https://studio.example.com/api",
                                   "https://a.example.com,", "ftp://x.example.com", "https://a.example.com?x=1"])
def test_a_value_that_is_not_an_origin_is_refused(value):
    with pytest.raises(RuntimeError, match=ALLOWED_ORIGINS_VARIABLE):
        allowed_origins({ALLOWED_ORIGINS_VARIABLE: value})
