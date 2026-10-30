"""Shared fixtures: the migrated test database (ADR-0025).

TEST_DATABASE_URL names a database the tests may empty, from the environment or the nearest .env.
Tests marked `needs_test_database` are skipped, with the reason shown, when it is absent; CI sets it.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text

from anisotropy_api.settings import sqlalchemy_url

API_DIR = Path(__file__).resolve().parents[1]

load_dotenv(find_dotenv(usecwd=True), override=False)
TEST_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
if TEST_URL:
    TEST_URL = sqlalchemy_url(TEST_URL, "TEST_DATABASE_URL")  # a hosted branch's plain postgresql:// address works too
needs_test_database = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set: no test database to run against")


def alembic_config(url: str) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(scope="session")
def migrated_database():
    """Everything down, then everything up, once per test session."""
    command.downgrade(alembic_config(TEST_URL), "base")
    command.upgrade(alembic_config(TEST_URL), "head")
    engine = create_engine(TEST_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def empty_runs(migrated_database):
    """The migrated database with an empty runs table."""
    with migrated_database.begin() as connection:
        connection.execute(text("TRUNCATE runs"))
    return migrated_database
