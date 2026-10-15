# Evaluation: run records, chunk 4 (the calculator's endpoints are recorded; the endpoint column) | 2026-10-14

- Scope: `POST /v1/laminates/response` and `POST /v1/laminates/prescribed-curvature` go through the same recorder as the case endpoint and require the actor header; migration 0002 adds the `endpoint` column; the website calculator sends `X-Anisotropy-Actor: calculator` and shows the run id beside the engine version (ADR-0026). No new physics; every engine number is unchanged.
- Environment: as chunk 3. Node 24 for the website; Playwright with Chromium for the browser test.

## Commands and captured output

From `api/`: `uv run alembic upgrade head` on the dev database, exit 0; `alembic_version` is `0002`; the two rows from chunk 3 read `endpoint = /v1/cases/solve` (filled by the column default, the only writer before this revision).

From `api/`: `uv run pytest -q -ra tests ../engine/tests` (what CI runs)

```text
539 passed in 26.56s
```

Three new tests in `tests/test_runs_api.py` (forward endpoint recorded with actor `calculator`, prescribed curvature recorded, both refuse a missing actor); the older endpoint tests send the header through their client's default headers.

From the repository root: `npm test`

```text
pass 71
fail 0
```

`npm run typecheck`: exit 0. `npm run build` then `npm run test:calculator` (static site plus a live API started by Playwright with `ANISOTROPY_RUN_RECORDS=off`; a request without the actor header would be a 422 and a failed test):

```text
7 passed (18.7s)
```

Live, `uvicorn` on port 8003 against the dev database, with `curl`:

```text
POST /v1/laminates/response, zero-degree-tension.json, X-Anisotropy-Actor: calculator
  HTTP/1.1 200 OK; x-anisotropy-run-id: f9ab8d66-946c-4869-bb85-4b6b6110056a
  run_id f9ab8d66-...; midplane_strain [0.0006802721088435374, -0.00018367346938775507, 0.0]
GET /v1/runs/f9ab8d66-...
  actor calculator, endpoint /v1/laminates/response, status solved;
  inputs keys [loads, plies, material, unit_system]; response keys [B_N, D_N_m, inputs, A_N_per_m, engine_version, curvature_per_m, midplane_strain, material_provenance]
POST /v1/laminates/prescribed-curvature, flat-cross-ply.json, founder-terminal
  HTTP/1.1 200 OK; x-anisotropy-run-id: 5f92cc72-3be6-443b-aff0-10e4139da2ac
  moments [-0.36000000000000004, -0.17999999999999997, -1.763491390772189e-17]; verification passed True
POST /v1/laminates/response, no header
  {"detail":"Header X-Anisotropy-Actor is required and must be one of founder-terminal, calculator, hermes, assistant, test; got None"} HTTP 422
```

`psql` afterwards:

```text
      actor       |              endpoint              |  status  |    id
------------------+------------------------------------+----------+----------
 founder-terminal | /v1/cases/solve                    | solved   | 370f3aa3
 founder-terminal | /v1/cases/solve                    | rejected | fc003665
 calculator       | /v1/laminates/response             | solved   | f9ab8d66
 founder-terminal | /v1/laminates/prescribed-curvature | solved   | 5f92cc72
```

## What the checks establish

- Every analysis endpoint records its request with the actor and the route that answered; the stored inputs are the fields the client sent, and the stored response equals what the client received (without `run_id`).
- The calculator's own request path (browser → static site → live API) carries the actor header and still passes all seven browser checks.
- The axial strain for the checked-in example is unchanged at 0.0006802721088435374, the value the API's first evaluation recorded.

## Limits

No existing test drives the forward endpoint into an engine rejection (non-finite solve), so that path is covered only by the case endpoint's rejection tests through the shared `_deliver`. The browser test's API runs with recording off, so it proves the header is sent, not that a browser request is stored; the live `curl` with actor `calculator` stands in for that. The CI jobs for this branch are UNVERIFIED until the pull request's checks run.
