# ADR-0025: Run records go in PostgreSQL, run locally in Docker, reached through SQLAlchemy and Alembic

- Status: Proposed
- Date: 2026-10-14
- Decided by: Founder | Drafted by: Claude Code
- Related: [system overview](../00_system_overview.md) (run records "Planned, next"), [documentation guide](../documentation-guide.md) Document 6 (provenance record), risk R-03 and R-04 in the [risk register](../risks/risk_register.md), ADR-0006 (no job queue yet), ADR-0018 (source rights)

## Context

`POST /v1/cases/solve` computes a result, returns it and forgets it. Nothing records which inputs, engine version and material dataset revision produced a number, so a result cannot be reproduced or audited later. The report generator, the language model assistant and the Hermes nightly log are all planned to read such records. The founder works on Windows 11; Docker Desktop 29.8.0 with Compose v5.5.1 is installed, no PostgreSQL is, and the API runs locally with `uv`.

## Options considered

Where the database runs:

1. **A hosted PostgreSQL service now (Supabase, Neon, a cloud provider).** No local setup. Every record leaves the founder's machine before any data-rights review (ADR-0018), the extra services (auto-generated REST API, auth) are not needed yet and must be locked down, and free tiers pause idle projects.
2. **PostgreSQL installed natively on Windows.** No Docker. Scattered configuration, manual version matching with CI and production, and a reset means finding and deleting the data folder.
3. **PostgreSQL in Docker through a `docker-compose.yml` in the repository.** One command starts, stops or wipes it; the version is pinned in the file and matched by CI; anyone cloning the repository gets the same database. Requires Docker Desktop, which is already installed.
4. **SQLite.** No server at all. Its JSON handling and types differ from PostgreSQL, so tests would run against something other than what is deployed.

How Python reaches it:

1. **psycopg 3 with hand-written SQL only.** Transparent; migrations and schema history by hand.
2. **SQLModel.** Compact syntax by FastAPI's author; a thinner layer over SQLAlchemy with fewer resources when something goes wrong.
3. **SQLAlchemy 2.0 with psycopg 3, migrations by Alembic.** The common FastAPI pairing; the table is defined in Python, Alembic keeps versioned schema scripts in git.

## Decision

Option 3 for both. PostgreSQL 17 runs from `docker-compose.yml` at the repository root, bound to `127.0.0.1` only, with its data in a named volume. The password comes from the git-ignored `.env` file and Compose refuses to start without it; nothing is defaulted. The API reads one `DATABASE_URL` setting (`postgresql+psycopg://...`) from the same file. Tests run against a second database on the same server, and CI against GitHub Actions' PostgreSQL service with the same pinned major version. Hosting is decided at deployment, after a rights review of what the records contain; the code depends only on standard PostgreSQL so any host works with a changed `DATABASE_URL`.

Open question for the founder, recorded with the first migration: when `DATABASE_URL` is missing, the API refuses to start (proposed), or runs with recording explicitly off and says so in every response. Recording silently off is excluded (ADR-0003).

## Why (evidence)

- Docker Desktop 29.8.0 and Compose v5.5.1 present on the founder's machine; `psql` absent (checked 2026-10-14).
- Risk R-03 (founder cannot reproduce a result) and R-04 (wrong dataset or typed value) in the risk register both name a per-run record as the mitigation.
- No performance or cost measurements; none are needed at the expected volume (one record per solve, a few kilobytes each).
- No evidence yet that Docker on this machine is reliable day to day; the first chunk is the test.

## Consequences

Easier: every solve can be written and read back; a wiped database is `docker compose down -v`; the schema has a history. Harder: Docker Desktop must be running before the API when recording is on; a second configuration file (`.env`) exists; the API gains three dependencies (`sqlalchemy`, `psycopg`, `alembic`). We now depend on PostgreSQL's `JSONB` type for the variable-shaped parts of a record.

## How we will know it was wrong

If Docker Desktop becomes a daily obstacle (licensing, WSL or startup failures), switch to the native installer; the code does not change. If a record read or write routinely takes more than two seconds, revisit with ADR-0006. If a second consumer needs the records in a shape the table cannot give, record a new decision.
