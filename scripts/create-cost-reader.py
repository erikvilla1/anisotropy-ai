"""A login that can only read the model-cost views, for the monthly cost report (ADR-0120 amendment 1). Nothing here computes a result.

    # PowerShell, in the repository, with the Neon CLI signed in:
    $env:DATABASE_URL_UNPOOLED = neon connection-string production
    uv run --project api python scripts/create-cost-reader.py

It connects with the owner's address (DATABASE_URL_UNPOOLED, else DATABASE_URL, as the migrations do), creates the role
`cost_reader` with a new random password, or gives it a new one if it exists (the old one stops working), and lets it read the three
views `model_costs_by_person`, `model_costs_by_feature` and `model_costs_by_day` and nothing else: not the `model_calls` table
itself, not the runs, jobs or projects, and no writing (its sessions are read-only too). The role is made in SQL, not in Neon's
console, because a role made there joins `neon_superuser` and can read and write every table.

It prints the reader's address once. Paste it into the project's cloud environment as COST_READER_DATABASE_URL (Project settings,
Cloud environment, the gear); never into a chat, a file in the repository or a GitHub log, which on this public repository anyone
can read. Run it again to replace a lost or leaked password.
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url

from anisotropy_api.settings import database_url_for_migrations

VIEWS = ("model_costs_by_person", "model_costs_by_feature", "model_costs_by_day")
ROLE = "cost_reader"
NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def grant_reader(engine: Engine, role: str = ROLE) -> str:
    """Create or re-key the reader and grant it the views alone; returns the new password."""
    if not NAME.match(role):
        raise ValueError(f"the role is lowercase letters, digits and underscores, not {role!r}")
    password = secrets.token_urlsafe(32)  # letters, digits, - and _: safe inside the quotes below and in an address
    with engine.begin() as connection:
        set_login(connection, role, password)
        database = connection.execute(text("SELECT current_database()")).scalar_one()
        connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}"))
        connection.execute(text(f'GRANT CONNECT ON DATABASE "{database}" TO {role}'))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        connection.execute(text(f"GRANT SELECT ON {', '.join(VIEWS)} TO {role}"))
    return password


def set_login(connection: Connection, role: str, password: str) -> None:
    """Create the role, or give it a new password, as a role that may create roles but is not a superuser (Neon's owner).

    A second run names only LOGIN, NOINHERIT and the password: only a superuser may name SUPERUSER in ALTER ROLE, even to keep it
    off, and Neon's owner is not one ("permission denied to alter role", 2026-11-20). The role was made without the other powers,
    and the check at the end refuses it if it has any of them now."""
    exists = connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}).first() is not None
    if exists:
        connection.execute(text(f"ALTER ROLE {role} WITH LOGIN NOINHERIT PASSWORD '{password}'"))
    else:
        connection.execute(text(f"CREATE ROLE {role} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '{password}'"))
    connection.execute(text(f"ALTER ROLE {role} SET default_transaction_read_only = on"))
    powers = connection.execute(text("SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = :role"),
                                {"role": role}).one()
    if any(powers):
        raise ValueError(f"the role {role} can do more than read (superuser, create databases or roles, or bypass row security); "
                         "drop it in Neon and run this again")


def reader_address(owner_url: str, role: str, password: str) -> str:
    """The owner's address with the reader's name and password, in the plain `postgresql://` form Neon gives."""
    return make_url(owner_url).set(drivername="postgresql", username=role, password=password).render_as_string(hide_password=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/create-cost-reader.py", description=__doc__.splitlines()[0])
    parser.add_argument("--role", default=ROLE, help=f"the reader's name; default {ROLE}")
    args = parser.parse_args(argv)
    try:
        owner = database_url_for_migrations()
    except RuntimeError as exc:
        print(f"refused:\n  {exc}", file=sys.stderr)
        return 2
    engine = create_engine(owner)
    try:
        password = grant_reader(engine, args.role)
    except ValueError as exc:
        print(f"refused:\n  {exc}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()
    print(f"The role {args.role} can now read {', '.join(VIEWS)} and nothing else.")
    print("Its address, shown once. Paste it into Project settings > Cloud environment as COST_READER_DATABASE_URL:\n")
    print(reader_address(owner, args.role, password))
    return 0


if __name__ == "__main__":
    sys.exit(main())
