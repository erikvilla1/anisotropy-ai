# Beta launch checks: what the hosted tier measures, and what is measured so far

- Date: 2026-11-05
- Scope: stage 5 of [ADR-0056](../../decisions/ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md): the numbers the closed beta needs before more people are invited (cold start, job time, peak memory, the fields JSON, cost per job), the live browser test, and the per-user limits.
- Environment: the solver image as `main` builds it; the hosted site at anisotropy.dev behind Cloudflare Access (pull requests #106 to #112).

## The numbers

| Quantity | Measured where | Value | Status |
| --- | --- | --- | --- |
| Job time, public IM7/8552 coupon, PDF included | the image on the founder's machine (Docker Desktop, WSL 2), network off, 2026-10-30 | 26.3 s | measured |
| Job time, same | the image on GitHub's runner, network off, run 41038205487 | 13.0 s | measured |
| Job time, same, with the jobs table and the object store | the image on the founder's machine, a fresh PostgreSQL and moto's S3 server, 2026-10-30 | 30.3 s | measured |
| Peak memory of the container, the API included | founder's machine / GitHub's runner | 445 MiB / 392 MiB | measured |
| Fields JSON of that coupon | the same runs | 538,999 bytes | measured |
| Package zip / document | the same runs | 978,192 / 961,518 bytes | measured |
| Image size | Docker Desktop / the runner's Docker | 2.07 GB / 1.48 GB (the two count layers differently) | measured |
| Cold start of the container on Cloudflare | the live site | no measurement yet | UNVERIFIED |
| Job time on Cloudflare (standard-3) | the live site | no measurement yet | UNVERIFIED |
| Peak memory on Cloudflare | the Containers dashboard | no measurement yet | UNVERIFIED |
| Cost per job | the Workers & Pages billing page, vCPU-seconds and GiB-seconds of the container | no measurement yet; the list-price estimate of ADR-0056 is $0.0055 for a 90 s job on standard-3 | UNVERIFIED |

How to take the live numbers, once a service token exists (the walkthrough, "Checks against the live site"):

1. Cold start: with the container asleep (twenty idle minutes), time one request: `curl -s -o /dev/null -w "%{time_total}\n" -H "CF-Access-Client-Id: ..." -H "CF-Access-Client-Secret: ..." https://anisotropy.dev/api/healthz`, then the same request again for the warm time; the difference is the cold start, which Cloudflare's own page puts at one to three seconds plus the image's own start.
2. Job time: `PREVIEW_URL=https://anisotropy.dev npm run test:studio-live` with the token; the job's status (`GET /api/v1/coupon-jobs/<id>`) carries `started_at` and `finished_at`. `docker/check-image.py` does the same against a local container.
3. Peak memory and cost: Workers & Pages → Containers → the container → Metrics, and the account's billing page for the month's vCPU-seconds and GiB-seconds; divide by the month's jobs (the `jobs` table counts them).

## The live browser test

`tests/browser/studio-live.spec.ts` runs against `PREVIEW_URL` with a service token (`playwright.studio-live.config.ts`). Not run yet: the service token and its Service Auth policy do not exist (UNVERIFIED). On the founder's machine the same test ran green against the local API on 2026-10-29 ([the studio's evaluation](2026-10-28-coupon-studio.md)).

## The per-user limits

`ANISOTROPY_JOBS_PER_USER_PER_DAY` (off unless set; needs run records on): one running job per person, at most that many a day, UTC, counted in the `jobs` table; 429 with the reason, which the chat shows under "The run could not start". Tests: `api/tests/test_settings.py` (the number, the refusals), `api/tests/test_coupon_jobs_api.py` (a second running job refused naming the first; the fourth job of a day refused by a cap of three; another person not limited; the one-at-a-time 409 unchanged), `api/tests/test_run_records_db.py` (the two counts, by email or by actor). Results in the pull request.

## Measured on the live site, 2026-11-07

The service token exists and the Access application carries its Service Auth policy (the founder made both in the Zero Trust dashboard; the token sits in the root `.env`, never in the repository). With it:

| Quantity | How | Value | Status |
| --- | --- | --- | --- |
| Cold start of the container | the first `GET /api/healthz` after the policy took, the container asleep: 503 at 0 s and at 15 s, 200 at 30 s | between 30 and 45 s, at the 15 s grain of the probe | measured |
| Warm answer | three `GET /api/healthz` in a row, the container awake | 0.66, 0.52, 0.75 s from this machine | measured |
| The live browser test | `PREVIEW_URL=https://anisotropy.dev npx playwright test --config playwright.studio-live.config.ts` with the token, 01:47 to 01:49 UTC | 1 passed (1.6 min end to end, the page included) | measured |
| Job time on Cloudflare (standard-3), the public coupon, PDF included | `GET /api/v1/coupon-jobs`: the job's `started_at` to `finished_at` | 80 s; 12 files; "57 of 57 recorded values agree with CalculiX; our reaction +0.35 % from CalculiX's" | measured |
| The project store on the hosted tier (ADR-0062 part 6) | `GET /api/v1/projects` with the token (no email: the actor owns it) | one project, kind fea, designation `IM78552-UNT-L1`, form version 0.6; the job's row names it | measured |
| Peak memory on Cloudflare | the Containers dashboard | not read in this session | UNVERIFIED |
| Cost per job | the billing page | not read in this session | UNVERIFIED |

Seen in the hosted jobs list and worth a fix: two jobs of 2026-11-06, started by the founder signed in, were refused with "IM7-UNT-L2: ours/runs/ holds attempt-02_2026-11-06 but the attempt log ends at row 01; add the missing rows to the README first (ADR-0039)". The hosted store's copy of that coupon holds a run folder whose row never reached the coupon's README: the two were written out of step, most likely a job that stored its run folder and stopped before the README went to the bucket, or a restore that brought one back without the other. Until the coupon's README is repaired (a row for attempt 02) that coupon refuses every new run on the hosted tier; a fresh coupon, as the live test's, runs. Not fixed here.

## Gate of stage 5, as the brief states it

Two of the founder's engineers each run a coupon on the live site, and the founder says to open it to more users. Not reached (UNVERIFIED): no engineer's run is recorded yet; the `runs` table on Neon will show them with their `user_email`.
