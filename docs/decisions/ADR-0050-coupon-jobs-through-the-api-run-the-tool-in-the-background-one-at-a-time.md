# ADR-0050: Coupon jobs through the API run the coupon tool in the background, one at a time, with their status in memory and a run record when they end

- Status: Proposed; for the hosted tier the status moves to a jobs table and the outputs to R2, one job at a time kept for the closed beta and one container per job after it, by [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md); the jobs table and the object store are built since amendment 2
- Date: 2026-10-27
- Decided by: Founder, 2026-10-26 ("ok yes lets do it", on the plan: one request that takes a filled form and starts the job, one to check its status, one to download the package, all recorded in the run table) | Drafted by: Claude Code
- Related: [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md) (step 2), [ADR-0049](ADR-0049-one-command-takes-a-coupon-from-its-input-form-to-its-package.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0027](ADR-0027-deployment-tiers-and-assistant-model-location.md), [ADR-0003](ADR-0003-reject-invalid-input.md), `api/src/anisotropy_api/coupon_jobs.py`, `api/tests/test_coupon_jobs_api.py`, `fea/tools/run_coupon.py`

## Context

- `fea/tools/run_coupon.py` takes a coupon from its input form to its package in about a minute (ADR-0049). The API answers each request in the same call and writes one immutable run record per request; a row is never updated (ADR-0026).
- The API's environment holds the engine, FastAPI and the database driver. The fea environment holds the kernel, matplotlib, openpyxl, Gmsh and the document code, and the tool runs CalculiX and Tectonic as programs.
- The API has no authentication (ADR-0011) and lets only the local website origins read its answers.

## Options considered

How a job runs:
1. **Synchronous request.** One call that returns when the package is built. Simplest, but a minute-long request with no progress, and clients time out.
2. **A background thread per job, its status in this process, one run record when it ends.** Nothing new to install. A status is lost when the API stops; the record of an ended job is not.
3. **A jobs table beside the run records.** The status survives a restart. A new migration and rows that change, beside a table whose rows never do.
4. **A task queue (Celery or RQ with Redis).** Durable and parallel. Another service to install and run on a machine that has one user.

What the job calls:
1. **The tool as a program, `uv run --project fea python fea/tools/run_coupon.py`.** The same command as in a terminal, so the same files come out; the two environments stay apart; a crash in the job cannot take the API down.
2. **The fea package inside the API.** The API's environment gains the fea dependencies, and the job's figures and solves run in the API process.

How the form travels:
1. **JSON with the form in base64, or a coupon's name.** One content type, no new dependency, and an assistant can send it.
2. **A multipart upload.** What browsers send by default; needs `python-multipart`.
3. **The raw file as the body.** Leaves no place for the options.

## Decision

A background thread per job, calling the tool as a program, with the form in base64 JSON.

- `POST /v1/coupon-jobs` takes a form (`form_name`, `form_base64`) or a `coupon`, with `run_by` and the tool's options (`replace`, `pdf`, `theory`). It answers 202 with the job and its `Location`, refuses a second job with 409 while one runs (runs share a coupon's folders and its attempt numbers), and refuses with 503 when uv is not on PATH. A request outside the contract is refused with 422 and starts nothing (ADR-0003).
- `GET /v1/coupon-jobs/{job_id}` gives the state (running, done, stopped, refused), the last 40 lines of the console, the attempt and, once done, the files by key. `GET /v1/coupon-jobs/{job_id}/package` gives the package as a zip.
- The tool writes its outcome as JSON (`--result`). When a job ends, its run record is written: solved with the outcome, or rejected with the message. The record keeps the form's name and SHA-256, not the form; the tool files the form in the coupon's `team/<date>/` folder. If the record cannot be written, the job's result is withheld (ADR-0026).

## As built (2026-10-27)

- `api/src/anisotropy_api/coupon_jobs.py` (the jobs and the command), three endpoints in `main.py`, `CouponJobRequest` and `CouponJobOutput` in `schemas.py`; `--result` and an `Outcome` in `fea/tools/run_coupon.py`.
- `api/tests/test_coupon_jobs_api.py`: a stand-in for the tool plays each outcome (done, stopped, a crash with no outcome, a job that waits) so the tests need neither CalculiX nor the fea environment; the contract's refusals; the 409; the 503 without uv; a receipt that cannot be written; the run record of an ended job (test database). `fea/tests/test_run_coupon.py` runs the tool itself.
- Not built: a listing of jobs (the run records list ended ones), cancelling a job, and a website page.

## Why (evidence)

- `cd api && uv run pytest -q -ra tests ../engine/tests` with the test database: 584 passed (2026-10-27). `cd fea && uv run pytest -q -ra tests/test_run_coupon.py`: 7 passed.
- On 2026-10-27, the API started from a scratch copy with records in the test database: a form filled with the founder's own coupon was posted as base64; the answer was 202; the job was done after 80 s; its run record reads solved, actor `founder-terminal`, endpoint `/v1/coupon-jobs`, inputs with the form's name and SHA-256; the package came back as a 1,072,034-byte zip with the document, the decks, the specs, the material and the audit form.

## Consequences

- Easier: the website and the assistant start the same tested job; every ended job has its receipt with its actor (ADR-0048 step 3 can call it).
- Harder: a job's status is gone when the API stops. A job running then finishes on its own and writes its attempt row, but gets no run record.
- Depends on: uv, the fea environment, CalculiX and, for the PDF, Tectonic on the machine that serves the API; today that is the founder's.

## How we will know it was wrong

If two people need coupon jobs at the same time, or a restart loses a job that mattered: then a jobs table or a queue.

## Amendment 1, 2026-10-28 (what the studio needs: the values as an input, a check without a run, the stage and the files while a job runs, a listing, and the actor `studio`; asked for by the founder)

**Context.** The coupon studio (ADR-0051) sends the form's rows from the browser, must check a setup before solving, needs the fields as soon as our engine has run while CalculiX and the PDF continue, lists the jobs and the coupons, and reopens a coupon. This record built the job with a form or a coupon name, a status of the console's last lines, and the package zip.

**Options.** For the check: (1) start a job and stop it after the check, which takes an attempt number and writes files; (2) a synchronous request that runs `fea/tools/studio_tool.py check` and waits (chosen: a check is a few seconds, and it writes nothing to the coupons' folders). For the files while a job runs: (1) wait for the job to end (a minute with a PDF); (2) the tool rewrites a progress file after every step, and the API serves any file it has reported by its key (chosen). For the inputs of the check's run record: (1) the rows themselves, as `/v1/cases/solve` records its case; (2) the values' digest, version and row count, as this record keeps the form's digest (chosen: the team's own constants stay with the coupon, ADR-0046).

**Decision.** `POST /v1/coupon-jobs` also takes `values`, one of the three inputs; the tool reads them from a file named by the job and files it with the coupon. `POST /v1/coupon-jobs/check` answers with the checklist and the preview, 504 when the tool does not answer within two minutes, recorded by the values' digest. The job's status carries `stage`, `stages_done` and the files made so far; `GET /v1/coupon-jobs/{id}/files/{key}` serves one by key, from the repository or the job's folder only; `GET /v1/coupon-jobs` lists this process's jobs newest first. `GET /v1/coupons` and `GET /v1/coupons/{name}/values` run the studio tool's `coupons` and `values`. The studio sends the actor `studio`, added by migration 0004. The check's temporary folder is removed after the answer. Still not built: cancelling a job, and a status that survives a restart.

**Evidence.** `cd api && uv run pytest -q tests/test_coupon_jobs_api.py tests/test_coupon_check_api.py`: 38 passed without the database (2026-10-28); the four database tests are in the evaluation note `docs/evaluations/fea/2026-10-28-studio-foundations.md`. A stand-in plays the studio tool, as one plays the run tool.

## Amendment 2, 2026-10-30 (durable outputs: the jobs table, the object store and the restore at startup; with ADR-0056, not yet confirmed by the founder)

**Context.** In the hosted tier the API runs in a container whose disk is gone when it stops or is replaced (ADR-0056). This record kept a job's status in the API process and its files where the tool wrote them, under `.local/fea/`; both would vanish, and with them the coupon list, a coupon's values and the next attempt's number. One job at a time stays for the closed beta.

**Options.** For the status: (1) in the process, as before: gone with the container; (2) a `jobs` table beside the run records, with rows that change state, option 3 of this record's first list (chosen); (3) the run record itself: written once, at the end, never changed (ADR-0026). For the files: (1) the container's disk: gone with it; (2) an object store through the S3 API, R2 in the hosted tier, with boto3, the client Cloudflare's own R2 pages use (chosen; the S3 API is also what a local stand-in and a self-hosted customer's store speak); (3) the files as rows in PostgreSQL: megabytes per job in the database that keeps the receipts. For how a browser gets a file: (1) streamed through the container: every byte is the container's egress (ADR-0056); (2) a redirect to a short-lived link into the store, ten minutes (chosen; the bucket needs a CORS policy for the site's origin). For the coupons: (1) the coupon list and a coupon's values read from the store object by object: new code beside the studio tool, which reads folders; (2) the coupon's whole folder goes to the store with every done job, and a starting container restores every coupon's folder into `.local/fea/` before it serves (chosen: the studio tool, the attempt numbering and the local tests are unchanged; the cost is a startup download proportional to what the store holds). For a job whose files cannot be stored: (1) `done` with a warning; (2) `stopped` with the reason and its result withheld, as for a job whose receipt cannot be written (chosen).

**Decision.** Migration 0006 creates `jobs`: id, actor, `user_email`, state, stage, the stages done and all stages, coupon, attempt, message, inputs, outputs by key, `stored` (key to object key), started and finished at, `run_id`, the log's tail and the API process that ran it. A job's row is inserted before its thread starts and updated when it ends; a row still `running` when a process starts is marked `stopped` with the reason; `GET /v1/coupon-jobs` and `GET /v1/coupon-jobs/{id}` answer from the table for the jobs of earlier processes. With `ANISOTROPY_R2_BUCKET`, `ANISOTROPY_R2_ENDPOINT`, `ANISOTROPY_R2_ACCESS_KEY_ID` and `ANISOTROPY_R2_SECRET_ACCESS_KEY` (all four or none), a done job's reported files go under `coupons/<coupon>/<attempt>/files/<key>/<name>`, its package zip under `coupons/<coupon>/<attempt>/package.zip` and the coupon's folder under `coupons/<coupon>/folder/`; the API restores the folders at startup and refuses to start when the store cannot be read; the file endpoints redirect to ten-minute links; PDFs, zips, decks and results carry `Content-Disposition: attachment`. Without the settings, the files stay on the disk as before; with the database, the table is kept all the same. Not built: uploading the fields while a job runs (the container that runs it serves them from its disk), a queue with one container per job (stage 3 of ADR-0056), and a lifetime for the stored objects.

**Evidence.** `cd api && uv run pytest -q tests` with a fresh test database, 2026-10-30: 276 passed, 1 skipped (the live store test, which needs `TEST_S3_*`), 1 failed (`test_a_slow_tool_is_a_504_and_a_broken_one_a_503`, whose 0.5 s budget a Python process did not meet on the founder's machine that afternoon, where one took 1.2 to 1.9 s to start; it passed in CI for #107 and is untouched here). The live round trip against moto's S3 server: `tests/test_storage.py`, 6 passed. The manual check in the solver image with a fresh PostgreSQL and moto's server on the host: the public coupon's job done in 30.3 s in a first container, 53 objects stored (13 of the attempt, 40 of the coupon folder); the container removed; a second container restored 40 files of 1 coupon at startup, listed the job from the table (`done`, 12 outputs, its `run_id`), redirected the fields, the document and the package to the store, where they are 538,999, 961,518 and 978,192 bytes (the zip with its `attachment` disposition), and listed the coupon with its two attempts. Cloudflare's pages read 2026-10-30: [the S3 API](https://developers.cloudflare.com/r2/api/s3/api/), [presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/) (1 second to 7 days), [bucket CORS](https://developers.cloudflare.com/r2/buckets/cors/) ("Without a CORS policy, browser-based uploads and downloads using presigned URLs will fail") and [boto3](https://developers.cloudflare.com/r2/examples/aws/boto3/). MinIO, the local stand-in the plan named, was not pullable that day (Docker Hub: "pull access denied"; quay.io: 401), so moto's server stands in (`moto[server]`, a development dependency). CI's `api` job with a fresh database and its `image` job, run 41052770062 of pull request #108: green. Against R2 itself: no evidence yet (chunk 4 of the build brief).
