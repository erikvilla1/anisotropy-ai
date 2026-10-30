"""Configuration read from the environment when the API starts. Nothing here has a silent default (ADR-0003).

Run records are on unless ANISOTROPY_RUN_RECORDS=off is set on purpose. With records on, DATABASE_URL
must be set and the API refuses to start otherwise (ADR-0026). Variables may come from a `.env` file
found by walking up from the current directory (python-dotenv); values already in the process
environment win over the file.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv
from sqlalchemy.engine import make_url

RECORDING_VARIABLE = "ANISOTROPY_RUN_RECORDS"
DATABASE_VARIABLE = "DATABASE_URL"
# A hosted PostgreSQL (Neon, ADR-0056) hands out two addresses: the pooled one for the application and an unpooled one for
# migrations and other session-level work. `neon env pull` writes both; a local Docker server has only the first.
UNPOOLED_DATABASE_VARIABLE = "DATABASE_URL_UNPOOLED"
# The one driver the API installs (ADR-0025). A plain `postgresql://` address, which hosted services hand out, is routed to it;
# an address that names another driver is refused rather than guessed.
DRIVER = "postgresql+psycopg"
ASSISTANT_PROVIDER_VARIABLE = "ANISOTROPY_ASSISTANT_PROVIDER"
ASSISTANT_MODEL_VARIABLE = "ANISOTROPY_ASSISTANT_MODEL"
CREDENTIAL_VARIABLES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")  # what the Anthropic SDK reads; one of them must be present
PROVIDERS = ("anthropic",)


@dataclass(frozen=True)
class AssistantSettings:
    """The assistant's model, as ADR-0027 requires it: off unless a deployment names a provider and a model (ADR-0052). With it off,
    only the template writes, and a solve makes no outbound request."""

    provider: str | None
    model: str | None

    @property
    def on(self) -> bool:
        return self.provider is not None


@dataclass(frozen=True)
class Settings:
    """What the process was told. `run_records` False means recording was switched off explicitly."""

    database_url: str | None
    run_records: bool
    assistant: AssistantSettings = AssistantSettings(None, None)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read the switch and the database address; raise with the fix when the combination is invalid.

    With no `environ`, the process environment is used after loading the nearest `.env` file.
    """
    if environ is None:
        load_dotenv(find_dotenv(usecwd=True), override=False)
        environ = os.environ
    switch = environ.get(RECORDING_VARIABLE, "on").strip().lower()
    if switch not in {"on", "off"}:
        raise RuntimeError(f"{RECORDING_VARIABLE} must be 'on' or 'off', not {switch!r}")
    url = environ.get(DATABASE_VARIABLE, "").strip() or None
    if switch == "on" and url is None:
        raise RuntimeError(
            f"{DATABASE_VARIABLE} is not set. Run records are on by default and need the database "
            f"(see .env.example and ADR-0025). To run without recording, set {RECORDING_VARIABLE}=off."
        )
    if url is not None:
        url = sqlalchemy_url(url, DATABASE_VARIABLE)
    return Settings(database_url=url, run_records=switch == "on", assistant=assistant_settings(environ))


def sqlalchemy_url(url: str, variable: str) -> str:
    """The address as SQLAlchemy needs it: `postgresql://` and `postgres://` become `postgresql+psycopg://`, the installed
    driver; `postgresql+psycopg://` passes unchanged; any other scheme is refused, naming the variable and the fix. Query
    parameters such as Neon's `sslmode=require` and `channel_binding=require` are kept; psycopg reads them."""
    try:
        parsed = make_url(url)
    except Exception as exc:  # SQLAlchemy raises ArgumentError; the message names the variable, not the secret
        raise RuntimeError(f"{variable} is not a database address SQLAlchemy can read: {exc}") from exc
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername=DRIVER)
    elif parsed.drivername != DRIVER:
        raise RuntimeError(f"{variable} must start with postgresql:// or {DRIVER}://, not {parsed.drivername}://; "
                           "the API installs psycopg only (ADR-0025)")
    return parsed.render_as_string(hide_password=False)


def assistant_settings(environ: Mapping[str, str]) -> AssistantSettings:
    """The assistant is off unless the provider is named; named, it needs its model and a credential, each refusal naming the variable."""
    provider = environ.get(ASSISTANT_PROVIDER_VARIABLE, "").strip().lower() or None
    if provider is None:
        return AssistantSettings(None, None)
    if provider not in PROVIDERS:
        raise RuntimeError(f"{ASSISTANT_PROVIDER_VARIABLE} must be one of {', '.join(PROVIDERS)} or unset, not {provider!r}")
    model = environ.get(ASSISTANT_MODEL_VARIABLE, "").strip() or None
    if model is None:
        raise RuntimeError(f"{ASSISTANT_MODEL_VARIABLE} is not set: name the model the assistant uses (see .env.example and ADR-0052), or unset "
                           f"{ASSISTANT_PROVIDER_VARIABLE} to run with the template writer only")
    if not any(environ.get(name, "").strip() for name in CREDENTIAL_VARIABLES):
        raise RuntimeError(f"{ASSISTANT_PROVIDER_VARIABLE}={provider} needs a credential: set {' or '.join(CREDENTIAL_VARIABLES)}, or unset "
                           f"{ASSISTANT_PROVIDER_VARIABLE} to run with the template writer only")
    return AssistantSettings(provider, model)


def database_url_for_migrations(environ: Mapping[str, str] | None = None) -> str:
    """Migrations need the database even when recording is off, and need a session of their own: with a hosted server the
    unpooled address (DATABASE_URL_UNPOOLED) is used when it is set, because a pooled connection does not keep session state
    across statements; a server with one address (local Docker) uses DATABASE_URL."""
    if environ is None:
        load_dotenv(find_dotenv(usecwd=True), override=False)
        environ = os.environ
    unpooled = environ.get(UNPOOLED_DATABASE_VARIABLE, "").strip() or None
    if unpooled is not None:
        return sqlalchemy_url(unpooled, UNPOOLED_DATABASE_VARIABLE)
    settings = load_settings(environ)
    if settings.database_url is None:
        raise RuntimeError(f"{DATABASE_VARIABLE} is not set; migrations need the database even with {RECORDING_VARIABLE}=off")
    return settings.database_url
