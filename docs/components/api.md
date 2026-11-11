# Component card: local laminate API | version 0.4 | updated 2026-11-05

## Purpose and intended use

Expose the existing engine's stiffness and deformation calculations to local HTTP clients. This is the first integration chunk; see the [step-by-step walkthrough](../../api/README.md).

## Inputs / outputs

`POST /v1/laminates/response`: explicit `SI_BASE` units, one elastic material and source-reference text, bottom-first ply stack and all six load resultants. Returns A/B/D, mid-plane engineering strains, curvatures, accepted inputs and engine package version. Unknown fields and invalid/non-finite values fail with 422. Since ADR-0059 it also returns `summary` (the stack described before any load: ply count, total thickness, symmetric, antisymmetric, balanced, the kind judged on A, the couplings at a stated relative tolerance, and the areal mass from the cited density or the reason it is null) and `first_ply_failure` (under the request's loads, every load scaling together: the criteria the inputs support with R, the ply, its face, z, the mode and the loads at failure; the others listed as not computed with the engine's reason; `evaluated` false with the reason when every load is zero or a ply has no strengths). `material_provenance` carries `density_kg_per_m3` and `fiber_volume_fraction` when the record states them.

`POST /v1/laminates/solve` (ADR-0060): the chat's laminate problem, every value as `{value, unit}` in any unit of the engine's table (`units.py`), a library material or the engineer's own constants (all five strengths or none), the layup bottom ply first, the ply thickness, the six load resultants, an optional f12* and `report_units` (SI, mm-MPa, US or psi). The API converts each value into a case in that system and runs the case solver; it returns the case, every result of `engine_results` in that system with its unit labels, the criteria evaluated, the stack summary and material provenance, the facts and the explanation with its writer (ADR-0052). A unit of the wrong dimension is refused by field name with 422.

`POST /v1/laminates/prescribed-curvature`: explicit `SI_BASE`, `bottom_to_top`, material/source, plies, three forces and three prescribed curvatures. Returns A/B/D, required applied moments, strain and the engine's forward verification with residuals/tolerances. Supplied moments are rejected. Numerical failure returns 422. [Chunk 3 walkthrough](../walkthroughs/chunk-3-constrained-analysis.md).

`POST /v1/cases/solve`: a whole problem in the engine's case format, as `{"case": {...}}` or `{"toml": "..."}`; returns every result the case determines in the case's units, the first-ply criteria evaluated, library provenance per material and the answer-key comparison when the case has `[expected]`. Engine validation messages return as 422. Covers mixed conditions, temperature change, several materials, all four failure criteria and plate buckling (ADR-0024; [note](../api-case-endpoint-2026-10-11.md)).

All three analysis endpoints require the `X-Anisotropy-Actor` header (which client sent the request) and record every request that reaches the engine, solved or rejected; the record's id comes back as `run_id` and in the `X-Anisotropy-Run-Id` header. `GET /v1/runs/{run_id}` returns the record as stored: the request as received, which endpoint answered, engine and API versions, git commit, the response or the error. `GET /v1/runs` lists summaries newest first, filtered by `actor`, `endpoint`, `status`, `since`, `until` (offset required) and `limit` (ADR-0026).

`GET /v1/materials` and `GET /v1/materials/{material_id}?dataset=`: the library datasets and the SI values the engine would use, each with its page. Both analysis endpoints also accept `material: {"library_id": "...", "dataset_id": null}` in place of explicit constants and then return `material_provenance` (ADR-0020).

`POST /v1/coupon-jobs`, `GET /v1/coupon-jobs/{job_id}`, `GET /v1/coupon-jobs/{job_id}/package`: a coupon job runs `fea/tools/run_coupon.py` in the background on a filled-in input form (base64), the form's rows as one JSON object (`values`, what the studio sends) or a coupon's name, one at a time (409 while one runs; with the hosted tier's job queue, `ANISOTROPY_JOB_ROLE=queue`, the job is answered `queued` and many run at once in solver containers, one per coupon, ADR-0056 amendment 3), and gives its state, its stage and the files made so far, the end of its console, its files and the package as a zip. An ended job has one run record with endpoint `/v1/coupon-jobs` (ADR-0050). Needs uv, the fea environment and CalculiX on the machine.

The laminate calculator (`POST /v1/laminates/solve`, ADR-0060) takes a temperature change, `delta_T` with its unit, and a typed material's `alpha1` and `alpha2`, both or neither (ADR-0087); with no load, the answer gives the change at first-ply failure.

The live solve (ADR-0086): `POST /v1/coupon-jobs/live` takes the check's request and answers with the checklist, the preview drawing and, when nothing blocks, our kernel's fields and explanation as `fea/tools/studio_tool.py live` writes them, with the stage seconds; warm `studio_tool.py serve` workers answer it (`ANISOTROPY_LIVE_WORKERS`, default 1, 0 for a fresh process per call), 429 when all stay busy, 504 when one does not answer in 30 s, 503 when none can run; the record keeps the summary and the fields' SHA-256.

For the coupon studio (ADR-0051, ADR-0050 amendment 1): `POST /v1/coupon-jobs/check` runs `fea/tools/studio_tool.py check` on the values and answers with the setup checklist and the preview without a run (504 when the tool does not answer within two minutes; recorded by the values' digest); `GET /v1/coupon-jobs` lists this process's jobs; `GET /v1/coupon-jobs/{job_id}/files/{key}` serves one file of a job by key, from the repository or the job's folder only (`fields`, `explanation`, `checklist` and `preview` while it runs, every key once done, `package` as the zip); `GET /v1/coupons` and `GET /v1/coupons/{name}/values` list the coupons on the machine and read one back as the values object. The studio is the actor `studio` (migration 0004).

The fibre tow test (ADR-0074): `POST /v1/tow-tests` runs `fea/tools/studio_tool.py tow` on a tow record (the tow's rows and its specimens as one values object, `test` = "fibre tow tension", an optional `project_id`) and answers at once with its checklist and, when nothing blocks, its result: each specimen's strength and chord modulus, their statistics, the planning loads and, under ASTM D4018-23, each clause judged. No model and no solver; 504 when the tool does not answer within two minutes; recorded by the values' digest.

The workspace's projects (ADR-0062 part 6, migration 0007): `GET /v1/projects` lists the requester's projects, the last changed first, by signed-in email behind Cloudflare Access or by actor locally; `PUT /v1/projects/{id}` creates (201) or replaces (200) a project as the page states it (`kind`, `name`, `content` as one JSON object, `form_version`, `units`), answering 404 for another's project and 409 for a change of kind; `GET /v1/projects/{id}` reads one with the jobs started for it; `PATCH /v1/projects/{id}` renames it. `POST /v1/coupon-jobs/check` and `POST /v1/coupon-jobs` take an optional `project_id`: the check writes the derived designation and its run back to the project, the job's row names it; a project the API does not hold blocks nothing. With run records off the routes answer 503: there is no table.

`POST /v1/workspace/proposals` (ADR-0088): a chat message, the rows and conditions the chat offers and the filled rows; the model named for the assistant reads the message in a fixed JSON schema, and the source guard keeps each proposal only when the message writes it: the quote, the number, the unit, the choice. A coupon value in another decimal unit of its own system is converted to the row's unit; a laminate value keeps its unit. The model sees no name, note or source (R-11). With no model it proposes nothing. Recorded with the model's name. `GET /v1/workspace/assistant` says whether a model reads messages; not a run.

`POST /v1/coupon-jobs/{job_id}/explain` (ADR-0052): the explanation of a job's result or setup, by the template (always) or by the model a deployment names in `ANISOTROPY_ASSISTANT_PROVIDER` and `ANISOTROPY_ASSISTANT_MODEL` with a credential; a model's draft stands only when every number in it is the engine's, else the template's words with the reason. Recorded with the facts' digest, and with `llm_provider` and `llm_model_version` when a model wrote.

## Dependencies and connections

Uvicorn -> FastAPI -> Pydantic contract -> existing `anisotropy_engine` -> NumPy. Separate `api/pyproject.toml` and `api/uv.lock`; no HTTP dependency added to the engine. pytest and HTTPX2 exercise the app in process.

Run records (ADR-0025, ADR-0026): SQLAlchemy 2 and psycopg 3 reach a local PostgreSQL 17 started by `docker-compose.yml`; Alembic migrations under `api/alembic/` own the `runs` table. Configuration is `DATABASE_URL` and the explicit `ANISOTROPY_RUN_RECORDS=off` switch, read from the environment or the nearest `.env` (python-dotenv). The API refuses to start without a reachable, migrated database unless switched off, and withholds a result (503) when its row cannot be written.

The solver image (ADR-0056): the `Dockerfile` at the repository root builds the API with the engine and fea environments, CalculiX, Gmsh and Tectonic (its TeX files fetched at build by `docker/warm-tectonic.py`, which builds the public coupon's document once), listening on port 8080 as the service user `app`; `GET /healthz` answers without the database; `ANISOTROPY_GIT_COMMIT` gives the run records their commit where there is no `.git`. The CI job `image` runs one public coupon job inside it with the network off (`docker/check-image.py`, [docker/README.md](../../docker/README.md)).

Behind Cloudflare Access (ADR-0056, `api/src/anisotropy_api/access.py`): with `ANISOTROPY_ACCESS_TEAM_DOMAIN` and `ANISOTROPY_ACCESS_AUD` set, a middleware inside the CORS layer refuses with 401 every request but `GET /healthz` and a preflight that lacks a valid `Cf-Access-Jwt-Assertion` token (PyJWT, RS256, the team's published keys matched by key id and refetched when one rotates; 503 when the keys cannot be fetched), and puts the token's email on the request; `record_run` writes it as `user_email` (migration 0005, which also admits the actor `browser`), and a coupon job keeps it for its receipt and status. `ANISOTROPY_ALLOWED_ORIGINS` replaces the local CORS origins. Unset, the API is the local one.

Durable outputs (ADR-0050 amendment 2, `api/src/anisotropy_api/storage.py`): with the four `ANISOTROPY_R2_*` settings, a done job's reported files go by key, with its package zip and the coupon's whole folder, to an object store through the S3 API (boto3, path-style addresses, SigV4), the coupons are restored from the store into `.local/fea/` at startup, and the file endpoints redirect to ten-minute links; a job whose files cannot be stored is `stopped` and its result withheld. With run records on, the `jobs` table (migration 0006) keeps every job's status across restarts, and the rows still `running` when the API starts are marked `stopped` with the reason. The run record stays the immutable receipt.

Per-user limits (ADR-0056, stage 5): `ANISOTROPY_JOBS_PER_USER_PER_DAY`, off unless set, gives each person (the signed-in email, else the actor) one running job at a time and a daily cap, read from the `jobs` table (`running_job_of`, `jobs_started_since`); a request past a limit is a 429 with the reason.

The website's `/calculator` now calls this endpoint. CORS allows credential-free JSON POST requests from localhost/127.0.0.1 on ports 3000/3001. See [the calculator card](calculator.md).

## Evaluation

[API integration evidence](../evaluations/api/2026-10-03-api-chunk-1.md) and [browser/CORS checks](../evaluations/website/2026-10-03-calculator-chunk-2.md); numerical equations remain covered by the existing engine tests.

[Prescribed-curvature engine/API evidence](../evaluations/2026-10-03-prescribed-curvature.md).

## Out of scope and limits

Local development only. No authentication; a language model only behind the assistant's settings, and then only to rephrase (ADR-0052); no language model yet (the library loader and the run records exist since ADR-0020 and ADR-0026). A job's status is lost when the process stops (ADR-0050). One material per laminate. No hole geometry, ply stress/failure endpoint, thermal/moisture effects or design approval. A caller's citation is not verified evidence; units are declared, not inferred. Extreme finite inputs can still be poorly conditioned; a finite result alone is not a numerical accuracy guarantee.

## Owner

Founder / engineering.
