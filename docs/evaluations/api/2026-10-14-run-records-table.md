# Evaluation: run records, chunk 2 (the `runs` table and the startup policy) | 2026-10-14

- Scope: the first Alembic migration, the `Run` model, configuration reading and the API's refusal to start without the database (ADR-0026). No endpoint writes or reads a row yet; no new physics.
- Environment: Windows 11, Python 3.12.14, PostgreSQL 17.11 in Docker (chunk 1), SQLAlchemy 2.1.4, psycopg 3.3.6, Alembic 1.20.0, python-dotenv 1.2.4. `.env` holds `DATABASE_URL` and `TEST_DATABASE_URL`; the volume was recreated so `docker/initdb/01-test-database.sql` created `anisotropy_test`.

## Commands and captured output

From `api/`: `uv run alembic upgrade head`, exit 0; `\d runs` in `psql` then shows 14 columns, the two indexes, the four check constraints and the self-referencing foreign key; `SELECT * FROM alembic_version` returns `0001`.

From `api/`: `uv run pytest -q tests ../engine/tests` (what CI runs)

```text
526 passed in 23.40s
```

From `api/`: `uv run pytest -q -ra --durations=3 tests/test_run_records_db.py tests/test_settings.py`

```text
5.03s call  test_api_refuses_to_start_when_the_database_is_unreachable
4.99s call  test_check_ready_names_an_unreachable_server_without_the_password
26 passed in 13.46s
```

Skip path. `TEST_DATABASE_URL=` (empty) then the same database test file:

```text
SKIPPED [1] tests\test_run_records_db.py:162: TEST_DATABASE_URL not set: no test database to run against
15 skipped in 1.09s
```

Live startup, `uv run uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8001` under four configurations:

```text
default (.env found, migrated database):   INFO: Application startup complete.
DATABASE_URL=...@127.0.0.1:1/anisotropy:   RuntimeError: Cannot reach the run records database at postgresql+psycopg://anisotropy:***@127.0.0.1:1/anisotropy: (psycopg.errors.ConnectionTimeout) connection timeout expired
ANISOTROPY_RUN_RECORDS=off:                INFO: Application startup complete.
ANISOTROPY_RUN_RECORDS=maybe:              RuntimeError: ANISOTROPY_RUN_RECORDS must be 'on' or 'off', not 'maybe'
```

From the repository root: `npm run typecheck` (`tsc --noEmit`) exit 0, covering the Playwright config edit; `git diff --check` clean.

## What the checks establish

- The migration creates every column, both indexes and the constraints; `downgrade base` removes them and `check_ready` then names `alembic upgrade head` as the fix.
- A solved row and a rejected row round-trip through JSONB; rows with an unknown actor, an unknown status, a solved row without a response, a rejected row without an error or with a response are refused by the database.
- `UPDATE` and `DELETE` on a row are refused by the trigger with the ADR-0026 message; a correction row may name an existing run and may not name a missing one.
- With records on and a migrated database the API starts and holds a connection pool; switched off it starts with none; with an unreachable server it refuses within the 5-second connect timeout and the message hides the password.

## Issues corrected during verification

- SQLAlchemy sent a Python `None` as the JSON value `null`, which is not SQL `NULL`, so the solved/rejected constraints misfired; `JSONB(none_as_null=True)` on the model fixed it.
- A connection to a closed local port waited about 130 seconds on this machine; `connect_timeout=5` on the engine makes the refusal immediate.
- The trigger's error arrives as `ProgrammingError`, not `InternalError`; the test matches the base `DBAPIError`.

## Limits

CI's PostgreSQL service job is UNVERIFIED until this pull request's checks run. The migration was applied to an empty database only; there is no data to migrate yet. `git_commit`, `llm_provider` and `llm_model_version` are columns without a writer. The browser test's server runs with recording switched off, so the calculator's requests are not recorded there by design.
