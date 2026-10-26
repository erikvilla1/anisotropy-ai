# Evaluation: run records, chunk 5 (listing runs) | 2026-10-15

- Scope: `GET /v1/runs`, newest first, one summary per run, filtered by `actor`, `endpoint`, `status`, `since`, `until` and `limit` (ADR-0026). Read only; no table change, no new physics.
- Environment: as chunk 4; main at e510284 (the four run-records pull requests merged).

## Commands and captured output

From `api/`: `uv run pytest -q -ra tests ../engine/tests` (what CI runs)

```text
548 passed in 26.34s
```

Nine new tests in `tests/test_runs_api.py`: order and summary fields, each filter, the time window with an offset, six refused filter values, and 503 when recording is off. `git diff --check`: clean.

Live, `uvicorn` on port 8004 against the dev database (its rows from the earlier live checks), with `curl`:

```text
GET /v1/runs                                4 rows, newest first:
  2026-10-15T04:06:34 founder-terminal /v1/laminates/prescribed-curvature solved
  2026-10-15T04:06:34 calculator       /v1/laminates/response             solved
  2026-10-15T03:53:21 founder-terminal /v1/cases/solve                    rejected  case: missing fields ['applied...
  2026-10-15T03:53:20 founder-terminal /v1/cases/solve                    solved
GET /v1/runs?actor=calculator               1 row (the forward request)
GET /v1/runs?status=rejected&limit=1        1 row (the rejected case)
GET /v1/runs?since=2026-10-15T04:00:00Z     2 rows (the two from 04:06)
GET /v1/runs?actor=somebody                 {"detail":"actor must be one of founder-terminal, calculator, hermes, assistant, test; got 'somebody'"} HTTP 422
GET /v1/runs?since=2026-10-15T04:00:00      {"detail":"since must include a timezone offset, e.g. 2026-10-14T00:00:00Z"} HTTP 422
GET /v1/runs?limit=0                        HTTP 422
```

## What the checks establish

- The listing returns the newest run first and each line carries the id, time, actor, endpoint, status, versions, input digest and error, enough to pick a run for `GET /v1/runs/{run_id}`.
- Each filter narrows as documented; `since` is inclusive and `until` exclusive; a time without an offset, an unknown actor or status, and a limit outside 1 to 500 are refused rather than answered with an empty list (ADR-0003).
- Switched off, the listing answers 503 like the detail endpoint.

## Limits

No paging beyond `limit`; a caller wanting more than 500 narrows the time window. No filter on the inputs digest or on the material dataset yet. The CI run for this branch is UNVERIFIED until the pull request's checks finish.

## Re-run, 2026-10-26, after merging main

Main had renamed the actor `hermes` to `founder-agent` (ADR-0028, migration `0003_rename_hermes_actor.py`), so the refusal above lists the actors as they were on 2026-10-15. The listing tests' rejected run now comes from `founder-agent`. From `api/`, with the dev database running in Docker: `uv run pytest -q -ra tests ../engine/tests`

```text
562 passed in 71.35s (0:01:11)
```
