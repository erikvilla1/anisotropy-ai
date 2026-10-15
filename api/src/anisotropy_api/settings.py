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

RECORDING_VARIABLE = "ANISOTROPY_RUN_RECORDS"
DATABASE_VARIABLE = "DATABASE_URL"


@dataclass(frozen=True)
class Settings:
    """What the process was told. `run_records` False means recording was switched off explicitly."""

    database_url: str | None
    run_records: bool


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
    return Settings(database_url=url, run_records=switch == "on")


def database_url_for_migrations() -> str:
    """Migrations need the database even when recording is off."""
    settings = load_settings()
    if settings.database_url is None:
        raise RuntimeError(f"{DATABASE_VARIABLE} is not set; migrations need the database even with {RECORDING_VARIABLE}=off")
    return settings.database_url
