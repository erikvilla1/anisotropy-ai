# Evaluation: run records, chunk 3 (every solve is recorded; one run read back) | 2026-10-14

- Scope: `POST /v1/cases/solve` writes a row for every request that reaches the engine, the required `X-Anisotropy-Actor` header, `run_id` in the response and the `X-Anisotropy-Run-Id` header, `GET /v1/runs/{run_id}`, and the 503 when a row cannot be written (ADR-0026). No new physics; the engine's numbers are unchanged.
- Environment: as chunk 2 (PostgreSQL 17.11 in Docker, SQLAlchemy 2.1.4, psycopg 3.3.6, Alembic 1.20.0). Dev database migrated to `0001`.

## Commands and captured output

From `api/`: `uv run pytest -q -ra --durations=3 tests ../engine/tests` (what CI runs)

```text
5.02s call  tests/test_run_records_db.py::test_api_refuses_to_start_when_the_database_is_unreachable
5.00s call  tests/test_run_records_db.py::test_check_ready_names_an_unreachable_server_without_the_password
4.02s call  tests/test_runs_api.py::test_a_result_is_withheld_when_it_cannot_be_recorded
536 passed in 25.09s
```

Ten new tests in `tests/test_runs_api.py`; the five existing case-endpoint tests now send the header. `git diff --check`: clean.

Live, `uv run uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8002` against the dev database, requests with `curl`:

```text
POST /v1/cases/solve, example file, X-Anisotropy-Actor: founder-terminal
  HTTP/1.1 200 OK
  x-anisotropy-run-id: 370f3aa3-2529-4672-aa11-d00906049cd1
POST /v1/cases/solve, same body, no header
  {"detail":"Header X-Anisotropy-Actor is required and must be one of founder-terminal, calculator, hermes, assistant, test; got None"} HTTP 422
POST /v1/cases/solve, {"case":{}}, with header
  {"detail":"case: missing fields ['applied', 'laminate', 'units']; unknown fields []"}
  x-anisotropy-run-id: fc003665-2df0-462f-850f-833279a60e7a
GET /v1/runs/370f3aa3-2529-4672-aa11-d00906049cd1
  HTTP 200; actor founder-terminal, status solved, engine_version 0.1.0, api_version 0.1.0,
  git_commit 11b4386f6da7a18d353900cd72d5e1fdfb2d8fd5, created_at 2026-10-15T03:53:20.739788+00:00,
  inputs_sha256 ac78c26b...; inputs keys ['case']; response keys [title, units, results, criteria, problems, materials, comparison, engine_version];
  stored Ex = 162.09574396238818; provenance dataset ncamp-im7-8552-2019-rtd-measured-v1
GET /v1/runs/00000000-0000-0000-0000-000000000000
  {"detail":"No run 00000000-0000-0000-0000-000000000000"} HTTP 404
```

In `psql` on the dev database afterwards:

```text
      actor       |  status  | engine_version | commit  |                  error                   |          created_at
------------------+----------+----------------+---------+------------------------------------------+-------------------------------
 founder-terminal | solved   | 0.1.0          | 11b4386 |                                          | 2026-10-15 03:53:20.739788+00
 founder-terminal | rejected | 0.1.0          | 11b4386 | case: missing fields ['applied', 'lamina | 2026-10-15 03:53:21.222487+00
```

## What the checks establish

- A solved request is stored with the request as received, both versions, the git commit, a SHA-256 of the canonical inputs, and the response body as returned (results, criteria, provenance, comparison, problems) without `run_id`; the read-back equals what the client got.
- A request the engine rejects, including a TOML parse error, is stored as `rejected` with the same message the client saw and no response.
- A missing or unknown actor is refused with the list of known actors and nothing is stored; a body that fails the HTTP contract before the engine is not stored either.
- Identical requests share a digest and get different ids; every listed actor is accepted.
- Switched off, a solve returns `run_id: null` with no header and `GET /v1/runs` answers 503; with the database unreachable at request time, a solve answers 503 "could not be recorded" and no result.

## Limits

`POST /v1/laminates/response` and `POST /v1/laminates/prescribed-curvature` are not recorded; the website calculator calls the first and sends no actor header yet. There is no list endpoint, so a run is found only by its id. `git_commit` comes from `git rev-parse` next to the package and is null for an install without the repository. The CI PostgreSQL job for this chunk is UNVERIFIED until the pull request's checks run. Nothing writes `supersedes_run_id` or the language-model fields yet.
