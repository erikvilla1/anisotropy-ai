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

## After the secrets, 2026-11-07, 22:30 UTC

The founder set the four secrets (`versions secret put`, since a preview version sat above the deployed one) and ran the deploy workflow by hand (3 min 21 s, green). Then, through the service token:

- **The per-user limit holds.** `ANISOTROPY_JOBS_PER_USER_PER_DAY` set: a second `POST /api/v1/coupon-jobs` while the first ran answered 429, "a job of the actor studio is still queued (…, started 22:35 UTC); one runs at a time per person, so wait for it to end or open it". Measured.
- **The model did not write, and the guard's fallback did its job.** `POST /api/v1/coupon-jobs/<id>/explain` answered `writer: template` with the reason "the model answered with an error (404): model: claude-opus-5.5 was not found. Did you mean claude-opus-5-5?": the model secret was typed with a dot. The template's words stood and the page said why, as ADR-0052 intends. The secret is to be set again as `claude-opus-5-5` and the workflow run once more; UNVERIFIED until then.
- **The live browser test failed on the page, not the job.** The job ran to `done` in 180 s (12 files, 57 of 57 values agreeing), but one read of the fields file through the Worker was not answered ("The API did not answer (the fields)") and the page did not ask again, so the results never showed. Fixed the same evening: `components/studio/use-coupon-run.ts` tries a missed poll or read again after two seconds, up to ten times per job, and the browser stand-in now fails the first read of the fields on purpose (`tests/browser/studio.spec.ts`).
- **A job nobody polled stalled.** The cap check's job, started by `curl` with no browser polling it, ended `stopped` after 591 s with "the solver running this job stopped answering for 120 s, so it did not finish; start it again". The same coupon had run to `done` in 80 s at 01:47 and in 180 s at 22:29 with the browser polling. Whether the container slept under no traffic, or the run was starved, is not known from here: it needs the Containers dashboard's CPU and memory for 22:35 to 22:45 UTC. UNVERIFIED; the brief's open question (does polling keep the container awake) stays open, now with one data point against it.
- The coupon `IM7-UNT-L2` is gone from the hosted list: the founder deleted it from the bucket.

## The queue's first night, 2026-11-07 to 2026-11-08

Written from the hosted jobs list (through the service token) and the Worker's log (`npx wrangler tail`, 02:25 to 02:50 UTC on 2026-11-08):

- **Two of the first four hosted jobs after the queue's deploy were stopped by the sweep** as "the solver running this job stopped answering for 120 s": the unpolled job above (started 22:35 UTC; its row never got a stage, a console line or a beat after the claim) and one started at 23:48 UTC, whose row kept the package stage with nine files when the sweep stopped it 252 s in. The fix, with what is known and what is not, is ADR-0056 amendment 5 (PR #142): the heartbeat alone on the row and running to the row's last write, the running files on a thread of their own, keepalives and timeouts on every database connection and on the bucket client, and the folder upload at a job's end sending only what changed.
- **Three jobs on 2026-11-08 ran to `done`**: 151 s (started 02:29 UTC), 219 s (02:39) and 156 s (02:49), each "57 of 57 recorded values agree with CalculiX", as attempts 05 to 07 of the live test's coupon. Against the 80 to 97 s of 2026-11-07: the coupon's folder, uploaded whole at every job's end, has grown with each attempt; PR #142's upload of changed files only is meant for this. The Worker's log over those runs shows the containers' proxy answering "500: Container suddenly disconnected, try again" to the solver's timer four times and to one of the page's polls once, each recovered at the next look; the page's retries (#140) and the timer's three failed looks before it lets go cover these.
- **The live browser test passed through the real page**, 02:46 to 02:49 UTC: `1 passed (3.0m)`. Two things had made it fail for reasons of the test, not the site: the token's headers on every request (this change's first commit), then Chromium keeping the headers a route adds across the redirect to the bucket's signed link, whose preflight the bucket refuses (403, read with curl). The spec now follows a file's redirect itself and checks the bucket's answer: a plain GET from the site's origin gets `Access-Control-Allow-Origin: https://anisotropy.dev`, which is what a real browser needs and gets.
- **The model writes on the live site** since the corrected model secret: `writer: anthropic`, `model: claude-opus-5-5` on the explanation of the 23:39 UTC job, not withheld. Its prose copied the engine's full-precision numbers ("16211.1968902878 N"); the fact sheet now keeps four significant figures (ADR-0052 amendment 1, PR #143).

## Gate of stage 5, as the brief states it

Two of the founder's engineers each run a coupon on the live site, and the founder says to open it to more users. Not reached (UNVERIFIED): no engineer's run is recorded yet; the `runs` table on Neon will show them with their `user_email`.
