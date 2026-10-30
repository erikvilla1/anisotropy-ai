# ADR-0026: A run record is immutable, keeps rejected runs, names its actor, and the API refuses to start without the database

- Status: Proposed; the signed-in email on every record and the actor `browser` since amendment 1 (the hosted tier behind Cloudflare Access, ADR-0056)
- Date: 2026-10-14
- Decided by: Founder | Drafted by: Claude Code
- Related: ADR-0025 (database stack), ADR-0003 (no silent defaults), ADR-0001 (engine computes every number), [documentation guide](../documentation-guide.md) Document 6, risks R-03 and R-04

## Context

ADR-0025 gives run records a database. This record decides what one row holds and what the API does when the database is absent. Consumers planned to read the rows: the report generator, the language model assistant (which must show what it drafted and what the founder confirmed), and the Hermes nightly log and post drafts (which may quote a number only when a record backs it).

## Options considered

What a row holds:

1. **Only the inputs and a dataset id.** Small; but a corrected library value later changes what the row means, and the result must be recomputed to be read.
2. **Inputs, versions, and the full response as returned** (results, the material provenance snapshot with every value and page, comparison, problems), plus the error text for a rejected request. Larger rows (kilobytes); the row stands on its own.

Who asked:

1. Free text. No migration to add a consumer; typos split one actor into several.
2. A checked list (`founder-terminal`, `calculator`, `hermes`, `assistant`, `test`). A new consumer is a migration, so a reviewed change.

Editing:

1. Rows may be updated (status fixes, annotations). Simple; history can be rewritten quietly.
2. Rows are never updated or deleted, enforced by a database trigger; a correction is a new row whose `supersedes_run_id` names the old one.

Missing database at startup:

1. Start and skip the write silently. Excluded by ADR-0003.
2. Start with recording off and mark every response. Friendlier; one more field a reader can miss, more code.
3. Refuse to start, naming the variable and the fix; an explicit `ANISOTROPY_RUN_RECORDS=off` for experiments and for test servers that have no database.

How the API learns the actor:

1. A field in the JSON body. Visible in the OpenAPI schema; but the body would no longer be exactly the engine's case format, which the validation files and the calculator share.
2. A required HTTP header, `X-Anisotropy-Actor`. Metadata about the sender stays outside the problem; a request without it, or with an unknown value, is refused and not recorded, since there is nothing to attribute it to.

## Decision

Option 2 for the contents, 2 for the actor, 2 for editing, 3 for startup (founder's choice, 2026-10-14). The table is `runs`: `id` (UUID), `created_at`, `actor`, `endpoint`, `status` (`solved` or `rejected`), `inputs` (the request as received, JSONB), `inputs_sha256`, `engine_version`, `api_version`, `git_commit` (nullable), `response` (JSONB, present exactly when solved), `error` (present exactly when rejected), `supersedes_run_id`, and `llm_provider` and `llm_model_version` (nullable; filled only when the assistant drafted the inputs). Check constraints enforce the actor list, the status list and the solved/rejected pairing. Configuration comes from the process environment or the nearest `.env` (python-dotenv), the environment winning. The actor arrives as the header (option 2). `POST /v1/cases/solve` records every request that reaches the engine, solved or rejected, and returns the id as `run_id` and in the `X-Anisotropy-Run-Id` header; a body that fails the HTTP contract before the engine (neither `case` nor `toml`) is not a run. At request time the startup policy holds: when the row cannot be written, the result is withheld with 503 rather than returned without a receipt. `GET /v1/runs/{id}` returns a row as stored; `GET /v1/runs` lists summaries newest first by actor, endpoint, status and an offset-bearing time window, refusing unknown filter values instead of answering with an empty list. The two older endpoints, `POST /v1/laminates/response` (the website calculator's, which sends `calculator`) and `POST /v1/laminates/prescribed-curvature`, are recorded the same way; an `endpoint` column (migration 0002) says which route answered, so a reader knows how to read `inputs` and `response`. Migrations are Alembic scripts under `api/alembic/`; tests run against a second database named by `TEST_DATABASE_URL` and are skipped, with the reason shown, when it is absent.

## Why (evidence)

- Risk R-04: a typed value or wrong dataset must be visible in the record; the provenance snapshot inside `response` carries every value and its page (ADR-0020 format).
- Risk R-03: the row holds everything needed to reproduce the run; the engine is deterministic (ADR-0001).
- The trigger and constraints are checked by `api/tests/test_run_records_db.py` against PostgreSQL 17; results in the evaluation note of the pull request.
- No usage evidence yet for the actor list or the row size; revisit when a consumer appears that the list does not name.

## Consequences

Easier: any consumer reads a row and has the whole story; a quoted number can be traced to a `run_id`. Harder: a new actor or column is a migration; TRUNCATE by the database owner remains possible (the trigger is row level) and is used by the tests; test servers must set the off switch on purpose. The API now needs Docker Desktop running before it starts, unless switched off.

## How we will know it was wrong

If rows grow past tens of kilobytes or the table past what one PostgreSQL instance handles comfortably, split the response into referenced parts. If the actor list changes more than a few times a year, replace it with a registered-clients table. If the off switch appears in any non-test configuration, the startup policy is being worked around and should be revisited.

## Amendment 1, 2026-10-30 (the signed-in email on every record, and the actor `browser`; with ADR-0056, not yet confirmed by the founder)

**Context.** The hosted tier puts the API behind Cloudflare Access (ADR-0056), which verifies a user's email with the identity provider and adds a signed token, `Cf-Access-Jwt-Assertion`, to every request it lets through. This record's actor is a label naming the client, not a person; a hosted run should also say who was signed in, and the API must refuse a request that did not come through Access.

**Options.** For who the person is: (1) a sign-in of our own, with users and sessions in the database: code to write, test and secure before the first invited user, which ADR-0027 had scheduled for the first proprietary customer; (2) Access's token, checked by the API against the team's published keys whenever its settings are present, and its `email` claim recorded (chosen). For where the email goes: (1) inside `inputs`, which the digest covers, so the same request from two people would get two digests and a reader would need to know the key; (2) a nullable column, `user_email`, beside the actor (chosen), empty with Access off and for a service token, which carries no email. For the actor list: `browser` is added for the hosted tier's clients; the site keeps sending `studio` and `calculator`.

**Decision.** Migration 0005 adds `user_email` (nullable, 320 characters) and the actor `browser`. `record_run` takes `user_email`; every route that records passes the email the Access middleware put on the request; a coupon job keeps the email of the request that started it, on its status and in its receipt. The row stays immutable; the downgrade refuses while a row carries an email or the new actor. With Access off the column stays empty and nothing else changes. The check itself is ADR-0056's (`api/src/anisotropy_api/access.py`): the settings `ANISOTROPY_ACCESS_TEAM_DOMAIN` and `ANISOTROPY_ACCESS_AUD`, both or neither; `GET /healthz` and a CORS preflight exempt; 401 with the reason for a missing, expired, foreign or unsigned token; 503 when the team's keys cannot be fetched.

**Evidence.** `cd api && uv run pytest -q tests` with the test database, 2026-10-30: 256 passed, among them `tests/test_access.py` (a valid token; a missing one; an expired one, another application's, another team's, another key's; a service token; `/healthz` and a preflight without a token; the keys unreachable; Access off; the email on a run record and in the listing) and the job's receipt with the email in `tests/test_coupon_jobs_api.py`. The migration's refusal to downgrade over a row with an email: `tests/test_run_records_db.py`. CI's `api` job with a fresh database, run 41041557285 of pull request #107: green. Live behind Cloudflare Access: no evidence yet (stage 2 of ADR-0056).
