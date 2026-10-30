# Chunk 1: call the laminate engine over HTTP

This local API accepts one material, a bottom-first ply stack and six explicit load resultants. It returns the engine's A, B, D stiffness matrices, mid-plane strains and curvatures as JSON. The existing engine computes every engineering result.

Chunk 3 adds `POST /v1/laminates/prescribed-curvature`: known forces and explicit curvature in, required moments and a numerical forward check out. Use `examples/flat-cross-ply.json`; see the [chunk 3 walkthrough](../docs/walkthroughs/chunk-3-constrained-analysis.md). The original forward endpoint below keeps its existing contract.

## The whole engine in one call (chunk 5)

`POST /v1/cases/solve` takes a problem in the engine's case format, either as a JSON object under `case` or as the text of a `.toml` case under `toml`, and returns every result the case determines in the case's own units: stiffness and compliance, any of the seven applied forms including mixed conditions and a temperature change, library and several materials, first-ply failure by every criterion the inputs allow, plate buckling, and the answer-key comparison when the case has `[expected]`. Validation messages are the engine's own. Example: `examples/case-library-axial-check.json`; format: `../engine/validation/README.md`; see [the note](../docs/api-case-endpoint-2026-10-11.md) and ADR-0024.

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/cases/solve' -ContentType 'application/json' -Headers @{ 'X-Anisotropy-Actor' = 'founder-terminal' } -InFile 'api/examples/case-library-axial-check.json' | ConvertTo-Json -Depth 10
```

The `X-Anisotropy-Actor` header is required on all three analysis endpoints: it says which client sent the request (`founder-terminal`, `calculator`, `founder-agent`, `assistant` or `test`; `founder-agent` is the founder's own tooling outside this repository, ADR-0028) and is stored with the run. Every request that reaches the engine is recorded, solved or rejected; the response carries the record's id as `run_id` and in the `X-Anisotropy-Run-Id` header, and `GET /v1/runs/{run_id}` returns the record: the request as received, which endpoint answered, versions, the response or the error (ADR-0026).

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runs/<run_id>' | ConvertTo-Json -Depth 10
```

`GET /v1/runs` lists the newest runs first, one summary line each (id, time, actor, endpoint, status, versions, input digest, error), narrowed by `actor`, `endpoint`, `status`, `since` (inclusive) and `until` (exclusive, both with a timezone offset such as `2026-10-14T00:00:00Z`), and `limit` (1 to 500, default 50). An unknown actor or status is refused, not answered with an empty list.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runs?actor=calculator&since=2026-10-14T00:00:00Z&limit=20' | Format-Table run_id, created_at, actor, endpoint, status
```

## Library materials (chunk 4)

`GET /v1/materials` lists every dataset of the cited material library; `GET /v1/materials/im7-8552` (optionally `?dataset=...`) returns the SI values the engine would use with the page of each. Either analysis endpoint accepts `"material": {"library_id": "im7-8552", "dataset_id": null}` in place of explicit constants, and the response then carries `material_provenance`. See [the loader note](../docs/material-loader-2026-10-10.md) and ADR-0020.

## Coupon jobs (ADR-0050)

A coupon job takes a filled-in coupon input form, or a coupon that already has its specs, to its package in the background. It runs `fea/tools/run_coupon.py` (ADR-0049) through `uv run --project fea`, the same command as in a terminal, so the machine needs uv, the fea environment and CalculiX. One job runs at a time.

```text
POST /v1/coupon-jobs                   {"form_name": "x.xlsx", "form_base64": "...", "run_by": "Erik Villa"}  -> 202, Location
                                       or {"coupon": "AS4-UNT-L2", "run_by": "Erik Villa"}; options replace, pdf, theory
GET  /v1/coupon-jobs/{job_id}          state (running, done, stopped, refused), the end of the console, the files once done
GET  /v1/coupon-jobs/{job_id}/package  the package as a zip, once done
POST /v1/coupon-jobs                   {"values": {...the form's rows by key...}, "run_by": "Erik Villa"}  -> 202 (the studio's input, ADR-0051)
POST /v1/coupon-jobs/check             {"values": {...}}  -> the setup checklist and the preview, without a run
GET  /v1/coupon-jobs                   this process's jobs, newest first
GET  /v1/coupon-jobs/{job_id}/files/{key}  one file by key (fields, explanation, checklist, preview while it runs; every key once done)
GET  /v1/coupons                       every coupon on this machine, from its spec and case page
GET  /v1/coupons/{name}/values         a coupon's rows as the values object the studio edits
POST /v1/coupon-jobs/{job_id}/explain  {"kind": "result" | "setup"}  -> the explanation and who wrote it (ADR-0052)
```

`uv run python examples/coupon_job.py <filled form>.xlsx --run-by "Erik Villa" --actor founder-terminal` does all three from a terminal: it prints each step as the job reaches it and saves the package zip (`--api` for another address, `--out` for another folder).

Every request needs the `X-Anisotropy-Actor` header. A second job while one runs gets 409. A job's status is kept in memory until the API stops. When a job ends, its receipt is a run record with endpoint `/v1/coupon-jobs`, solved or rejected; the record keeps the form's name and SHA-256, and the tool files the form itself in the coupon's `team/<date>/` folder. A values object is recorded by its digest the same way, and a check by the values' digest too (ADR-0050 amendment 1). The studio's own requests carry the actor `studio` (migration 0004). The status of a running job says its stage and the files made so far. The assistant is off unless `ANISOTROPY_ASSISTANT_PROVIDER`, `ANISOTROPY_ASSISTANT_MODEL` and `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`) are set; off, the template writes every explanation and no request leaves the machine.

## Database (run records, ADR-0025)

Run records will be stored in a local PostgreSQL 17 that Docker runs from `docker-compose.yml` at the repository root. Docker Desktop must be running. Copy `.env.example` to `.env`, set `POSTGRES_PASSWORD` (Compose refuses to start without it) and then, from the repository root:

```powershell
docker compose up -d        # start; `docker compose ps` shows "healthy" when ready
docker compose exec db psql -U anisotropy -d anisotropy   # SQL prompt inside the server; \q to leave
docker compose down         # stop, keep the data
docker compose down -v      # stop and wipe the data
```

Then create the tables (once, and again after every new migration):

```powershell
cd api
uv run alembic upgrade head
```

### Hosted on Neon (ADR-0056, ADR-0025 amendment 1)

The same code runs against Neon's hosted PostgreSQL with a changed address. The repository root is linked to the Neon project by the git-ignored `.neon` file and declares its services in `neon.ts`; the Neon CLI (`npm i -g neon`, `neon login` once in a browser) writes the branch's addresses into `.env`:

```powershell
neon deploy                 # applies neon.ts to the linked branch and writes DATABASE_URL, DATABASE_URL_UNPOOLED and NEON_BRANCH into .env
cd api; uv run alembic upgrade head   # migrates over the unpooled address
```

`DATABASE_URL` is the pooled address (`-pooler` in the host) for the API's own traffic; `DATABASE_URL_UNPOOLED` is used by the migrations whenever it is set, because a pooled connection does not keep session state between statements. Neon writes plain `postgresql://...?sslmode=require` addresses; `settings.sqlalchemy_url` routes them to psycopg, the one driver installed, and refuses any other driver by name. `neon checkout <name> --create` makes a copy-on-write branch of the data and points `.env` at it; `neon checkout production` points back. The tests keep `TEST_DATABASE_URL`, which `neon` never writes.

The API reads `DATABASE_URL` at startup, from the environment or the nearest `.env` found by walking up from the current directory. It refuses to start when the variable is missing, the server is unreachable or the table is absent, and each refusal names the fix. For an experiment without recording, set `ANISOTROPY_RUN_RECORDS=off` on purpose; the browser test does this. The tests use `TEST_DATABASE_URL` (the `anisotropy_test` database, created when the Docker volume is first initialised) and are skipped with a stated reason when it is absent. If the database stops answering while the API runs, a solve returns 503 and no result: a result without its record is not delivered (ADR-0026).

## Run it

From the repository root, in PowerShell:

```powershell
cd api
uv sync --locked
uv run uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000
```

Or in the solver image, which carries the API with CalculiX, Gmsh and Tectonic and listens on port 8080 (ADR-0056, [docker/README.md](../docker/README.md)): `docker build -t anisotropy-solver .` then `docker run --rm -p 8080:8080 -e ANISOTROPY_RUN_RECORDS=off anisotropy-solver`; `GET /healthz` answers `{"status":"ok"}` without the database.

Behind Cloudflare Access (ADR-0056): with `ANISOTROPY_ACCESS_TEAM_DOMAIN` (the team's domain, `<team>.cloudflareaccess.com`) and `ANISOTROPY_ACCESS_AUD` (the Access application's audience tag) set, every request but `GET /healthz` and a CORS preflight must carry the `Cf-Access-Jwt-Assertion` token Access adds, checked against the team's published keys; a request without a valid one is refused with 401, and the signed-in email is recorded as `user_email` on every run (ADR-0026 amendment 1, migration 0005). `ANISOTROPY_ALLOWED_ORIGINS` (comma-separated origins) replaces the local CORS origins. Unset, nothing changes.

Open <http://127.0.0.1:8000/docs>. This is FastAPI's interactive API explorer. Expand `POST /v1/laminates/response`, select **Try it out**, paste `examples/zero-degree-tension.json`, and select **Execute**. The page displays the HTTP status and response JSON. Stop the server with Ctrl+C.

Or, from a second PowerShell terminal at the repository root:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/laminates/response' -ContentType 'application/json' -Headers @{ 'X-Anisotropy-Actor' = 'founder-terminal' } -InFile 'api/examples/zero-degree-tension.json' | ConvertTo-Json -Depth 10
```

The example's material numbers cite Daniel & Ishai Table A.4 and match the existing analytical practice case. Its thickness and load are constructed practice inputs, not test measurements. At zero degrees, the axial strain should be approximately `0.0006802721088435374`; the integration test checks this against the independent uniaxial compliance relation.

## Follow one request through the code

1. **Uvicorn** listens on local port 8000 and hands the HTTP request to **FastAPI**.
2. FastAPI routes `POST /v1/laminates/response` to `analyze_laminate()` in `src/anisotropy_api/main.py`.
3. Before that function runs, **Pydantic** reads the JSON into `AnalysisRequest` from `schemas.py`. It checks required fields, finite numbers, positive moduli/thicknesses, explicit units and unknown fields. `validate_compliance()` reuses the engine's material-validity check.
4. `MaterialInput.to_engine()` and `LoadInput.to_engine()` map the accepted fields into the engine's `Lamina` and `Loads` objects. `Ply` combines each supplied angle and thickness with the material.
5. The existing `abd_matrices()` integrates ply stiffness through the thickness. Its A matrix describes stretching, B describes stretching/bending coupling, and D describes bending stiffness. `midplane_response()` solves the existing ABD system for strain and curvature using **NumPy**.
6. `AnalysisResponse` checks the output shapes and finite values. Arrays become ordinary lists so FastAPI can return JSON, a text format of named fields, lists and numbers.

The API does not implement new laminate equations. `invalid_request()` returns the location and reason for an invalid field with HTTP status 422. Numerical failures also produce 422 rather than an apparent successful calculation. HTTP status 200 means the request completed; it does not establish experimental validity.

## Input and output contract

- `unit_system` must explicitly be `SI_BASE`: moduli in Pa, thickness in m, forces per width in N/m, and moments per width in N*m/m. This is different from the calculator's `SI` display/input scale (GPa, MPa, mm). No conversions are performed by this endpoint.
- Every material value and `source_reference` is required. The source text is supplied by the caller and echoed; the API does not verify that citation or load a curated dataset yet.
- Plies are bottom face first. Angles are degrees, counterclockwise from x to the fibers. All plies use the one supplied material.
- All six components `Nx`, `Ny`, `Nxy`, `Mx`, `My`, `Mxy` are required; enter `0` explicitly for unused components. Signed loads and angles are supported.
- Strings such as `"147e9"`, booleans in numeric fields, NaN/Infinity, empty stacks and unknown fields are rejected.
- Outputs: `A_N_per_m`, `B_N`, `D_N_m`; `midplane_strain = [epsilon_x, epsilon_y, gamma_xy]`; `curvature_per_m = [kappa_x, kappa_y, kappa_xy]`. Shear strain uses the engineering convention.
- `inputs` echoes the accepted request; `engine_version` identifies the installed package release. This is not a persistent run record or a code/dataset fingerprint.

## Libraries and their boundaries

| Library/tool | Job | Where it belongs |
| --- | --- | --- |
| FastAPI | HTTP routing, JSON responses, OpenAPI schema and interactive `/docs` | API only |
| Pydantic | Typed input/output contracts and validation | API and existing engine |
| Uvicorn | Runs the HTTP server | API only |
| NumPy | Matrix arithmetic and solves; API also checks results for finite numbers | Existing engine and API boundary |
| pytest + HTTPX2 | Send test requests to the app and check its behavior | Development/test only |
| uv | Installs the local packages and locked dependencies; runs commands | Development/runtime tooling |

`api/pyproject.toml` lists direct dependencies. `api/uv.lock` pins the resolved versions. `tool.uv.sources` points to `../engine`, so the API imports the existing engine package. The engine retains its own environment and does not depend on FastAPI. Current Starlette's TestClient prefers HTTPX2; using HTTPX emits a deprecation warning in the installed release.

## Check it

```powershell
cd api
uv run pytest -q
uv run pytest -q tests ../engine/tests
```

The combined command also verifies the engine under the API's dependency versions. CI runs the API's contract tests as a separate job. See [the evaluation record](../docs/evaluations/api/2026-10-03-api-chunk-1.md).

## Chunk boundary

This chunk provides local stiffness and deformation calculations only. The [chunk 2 calculator](../docs/walkthroughs/chunk-2-calculator.md) now calls it from the website. CORS permits JSON POST requests from `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:3001` and `http://127.0.0.1:3001`, without credentials. Restart the API after code changes. CORS is a browser policy, not authentication.

Curated material loading, ply-stress/failure endpoints, saved runs and the AI assistant are future chunks. No authentication or deployment controls are implemented; run on loopback for local development. The API inherits the engine's flat-laminate CLT scope and physical limitations.

Read [ADR-0011](../docs/decisions/ADR-0011-local-laminate-api.md) for the choices and [the component card](../docs/components/api.md) for the system-level boundary.
