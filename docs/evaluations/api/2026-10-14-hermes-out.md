# Evaluation: Hermes leaves the repository; actor `hermes` becomes `founder-agent` (ADR-0028) | 2026-10-14

- Scope: migration 0003 renames the run-record actor and replaces the check constraint; migration 0001 now pins the list it created at the time instead of importing the live one; the `.agents/skills` junction, the Hermes rows in `docs/agents/README.md` and the Hermes metadata in the `project-rules` skill are removed. No engine change; no website change.
- Environment: Windows 11, Docker Desktop with PostgreSQL 17 from `docker-compose.yml`, `TEST_DATABASE_URL` set in `.env`.

## Commands and captured output

From `api/`: `uv run pytest -q -ra tests ../engine/tests` (what CI runs)

```text
540 passed in 45.44s
```

One new test, `test_migration_0003_renames_hermes_rows_and_keeps_the_trigger` in `tests/test_run_records_db.py`: downgrades to 0002, inserts a row with actor `hermes`, upgrades to head, and checks that the row reads back as `founder-agent`, that a new `hermes` row is refused by the constraint, and that an update to the renamed row is still refused by the immutability trigger.

From `api/`: `uv run alembic upgrade head` on the dev database, exit 0. Then, read through SQLAlchemy:

```text
alembic_version: 0003
calculator: 1
founder-terminal: 3
constraint: CHECK (actor IN ('founder-terminal', 'calculator', 'founder-agent', 'assistant', 'test'))   (PostgreSQL's expanded form)
trigger enabled: O
```

The dev database had no `hermes` rows, so the rename touched nothing there; the test above covers the case where rows exist.

From the repository root: `powershell -ExecutionPolicy Bypass -File scripts/link-agent-dirs.ps1`

```text
ok       .claude\skills -> docs\agents\skills
```

The local `.agents\skills` junction and its folder were removed by hand; `.gitignore` no longer lists `/.agents/`.

## Not run

`npm test`, `npm run typecheck` and the browser tests: no website file changed. UNVERIFIED for this chunk.

## Where Hermes is still named

Only in history: ADR-0023, ADR-0025, ADR-0026, ADR-0028, the changelog, earlier evaluation notes, and the pinned list in migration 0001. These record what was decided and built at the time and are not rewritten.
