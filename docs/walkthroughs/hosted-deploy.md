# The hosted tier: what runs where, how to deploy, how to roll back

The decision is [ADR-0056](../decisions/ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md); this page is the operator's side of it. Everything below is invite-only: nobody reaches the site or the API without signing in through Cloudflare Access.

## The pieces

| Piece | What it is | Where it is configured |
| --- | --- | --- |
| The Worker `anisotropy-studio` | Serves the website's static export (`out/`) and forwards `/api/*` to the container | [`wrangler.jsonc`](../../wrangler.jsonc), [`worker/index.ts`](../../worker/index.ts) |
| The container `ApiContainer` | The API with CalculiX, Gmsh and Tectonic, one instance, built from the [`Dockerfile`](../../Dockerfile) by `wrangler deploy`; with the queue it files coupon jobs and runs none | `wrangler.jsonc` (`containers`), [docker/README.md](../../docker/README.md) |
| The containers `SolverContainer` | The same image in the role `solver`: one per coupon job, named by the job's id, at most ten at once (ADR-0056 amendment 3) | `wrangler.jsonc` (`containers`), [`worker/solver-queue.ts`](../../worker/solver-queue.ts) |
| The queues `anisotropy-coupon-jobs` and `anisotropy-coupon-jobs-dead` | One message per coupon job, consumed by the Worker; a message that fails 100 times goes to the second | `wrangler.jsonc` (`queues`); created once by hand, below |
| Cloudflare Access | Sign-in with an email allow list and one-time PINs, in front of the Worker; adds the token the API checks | Zero Trust dashboard; the API's `ANISOTROPY_ACCESS_*` secrets |
| Neon PostgreSQL | The run records, the jobs table and the projects table (migration 0007, ADR-0062 part 6) | the `DATABASE_URL` secret; migrations by the deploy workflow |
| R2 | A done job's files, its package and the coupon folders; the coupons are restored from it when the container starts | the `ANISOTROPY_R2_*` secrets; the bucket's CORS policy |
| GitHub Actions | [`deploy.yml`](../../.github/workflows/deploy.yml): build, migrate, deploy on a green merge to `main`; a preview version per pull request | repository secrets |

The site is built with `NEXT_PUBLIC_ANISOTROPY_API_URL=/api`, so the browser calls the API on the same origin and no CORS list is needed. The site's calls send same-origin credentials, so Access's `CF_Authorization` cookie goes with them; without it Access answers a call with a redirect to its sign-in page, which the browser does not follow across origins, and the studio says the API did not answer. The Worker strips `/api` and hands the request to the container unchanged, headers included; the container's FastAPI refuses any request without Access's `Cf-Access-Jwt-Assertion` token when its Access settings are set.

## The first deploy, from a laptop

Docker Desktop must be running: `wrangler deploy` builds the image from the Dockerfile and pushes it to Cloudflare's registry (the first push is the slow one, about 2 GB).

```bash
npm ci
npx wrangler login       # a browser window; signs Wrangler into the Cloudflare account
npm run build:hosted     # the site into out/, calling the API at /api (scripts/build-hosted.ts sets the address; shells differ)
npx wrangler deploy      # the Worker, then the image, at https://anisotropy.dev
```

Wrangler creates a queue the configuration names when it does not exist: the pull request that added the job queue created `anisotropy-coupon-jobs` this way on 2026-11-07, in its preview step. The dead-letter queue `anisotropy-coupon-jobs-dead` is created when a consumer names it, by Cloudflare's queue configuration page (not yet seen here). `npx wrangler queues list` shows both. For a deploy without the queue, remove the `queues` block and the `SolverContainer` entries: the API then runs one job at a time in its own container, as before.

A pull request's preview step (`wrangler versions upload`) fails while a Durable Object class the configuration names has never been deployed: "Durable Object binding 'SOLVER' references class 'SolverContainer', which is declared in `exports` but not yet provisioned". The first `wrangler deploy` with the class provisions it, and previews work again after it.

Then the secrets, one by one (each asks for the value; nothing goes into the repository):

```bash
npx wrangler secret put DATABASE_URL                 # Neon's pooled address, postgresql://...?sslmode=require
npx wrangler secret put DATABASE_URL_UNPOOLED        # Neon's unpooled address, for the migrations
npx wrangler secret put ANISOTROPY_R2_BUCKET
npx wrangler secret put ANISOTROPY_R2_ENDPOINT       # https://<account id>.r2.cloudflarestorage.com
npx wrangler secret put ANISOTROPY_R2_ACCESS_KEY_ID
npx wrangler secret put ANISOTROPY_R2_SECRET_ACCESS_KEY
npx wrangler secret put ANISOTROPY_ACCESS_TEAM_DOMAIN   # <team>.cloudflareaccess.com, once the Access application exists
npx wrangler secret put ANISOTROPY_ACCESS_AUD           # the application's audience tag
npx wrangler secret put ANISOTROPY_ASSISTANT_PROVIDER   # anthropic; leave all three unset and the template writer explains alone (ADR-0052)
npx wrangler secret put ANISOTROPY_ASSISTANT_MODEL      # claude-opus-5-5, or claude-sonnet-5-5 at lower cost
npx wrangler secret put ANTHROPIC_API_KEY               # from console.anthropic.com, with a spend limit set there
```

The container reads these at its next start (`worker/routing.ts` lists the names it is given). After the migrations have run once against Neon (`cd api && DATABASE_URL=... uv run alembic upgrade head`, or the deploy workflow), the API is complete: with `DATABASE_URL` set and no `ANISOTROPY_RUN_RECORDS=off`, it refuses to start until the database is reachable and migrated, as locally.

Wait a few minutes after the first deploy before expecting the container to answer; Cloudflare provisions it after the Worker is live. `npx wrangler containers list` shows its state.

## Sign-in: the Access application

1. Zero Trust → Integrations → Identity providers → add **One-time PIN** (new organisations do not get it by default; it sits beside any provider already listed).
2. Zero Trust → Access controls → Applications → Add an application → Self-hosted and private → destination **Public DNS**: subdomain empty, domain `anisotropy.dev`, path empty. Not the **Workers** tab: it targets the `workers.dev` address, which this Worker does not have (ADR-0056 amendments 1 and 2).
3. Policies → **Create new policy**: action Allow, Include → **Emails** → the invited addresses (or **Emails ending in** a domain); save it and check it is listed under the application before saving the application. Access is default-deny: with no policy attached, the sign-in page still says a code was sent, but none is.
4. Login methods: **One-time PIN** ticked.
5. Save; then Configure → Additional settings → copy the **Application Audience (AUD) Tag** into the `ANISOTROPY_ACCESS_AUD` secret, and the team domain (`<team>.cloudflareaccess.com`, under Zero Trust → Settings) into `ANISOTROPY_ACCESS_TEAM_DOMAIN`.

To add or remove a user: edit the policy's email list. Access applies it at the next sign-in; the API records the signed-in email on every run (`user_email`).

## The bucket

Create the R2 bucket, then an API token with **Object Read & Write** scoped to it; its Access Key ID and Secret Access Key are the two `ANISOTROPY_R2_*` key secrets. Add a CORS policy on the bucket allowing the site's origin, `https://anisotropy.dev`, for `GET` and `HEAD`: the browser fetches a job's files from the bucket through short-lived links, and without the policy those fetches fail.

## Moving the address

To serve the Worker at another hostname without a moment unguarded (as amendment 2 did, from `app.anisotropy.dev` to `anisotropy.dev`): first add the new hostname to the Access application (**+ Add public hostname**) beside the old one, and its origin to the bucket's CORS policy; then change `routes` in `wrangler.jsonc` and deploy; check the new address, then remove the old hostname from the application, its origin from the CORS policy and, if Workers → `anisotropy-studio` → Settings → Domains & Routes still lists it, the old custom domain. The application keeps its audience tag, so the secrets stay as they are.

## Deploys after the first

`deploy.yml` runs when the Tests workflow finishes green on `main`: it builds the site, applies the migrations to Neon and runs `wrangler deploy`, passing the commit as `ANISOTROPY_GIT_COMMIT` so run records carry it. It needs three repository secrets: `CLOUDFLARE_API_TOKEN` (a token made from the "Edit Cloudflare Workers" template, with the account's Workers, Containers and R2 permissions, and Zone → Workers Routes → Edit on `anisotropy.dev` for the custom domain), `CLOUDFLARE_ACCOUNT_ID`, `DATABASE_URL` (and `DATABASE_URL_UNPOOLED` when Neon gives one). A pull request uploads a preview version of the Worker without production traffic, without a new container image and, with preview URLs off, without an address of its own. **Run workflow** on the Actions page deploys `main` by hand.

## Limits per person

`ANISOTROPY_JOBS_PER_USER_PER_DAY`, a Worker secret like the others, caps what one signed-in person can run: one job at a time and that many a day (UTC), counted in the jobs table. A request past a limit is refused with 429 and a sentence the studio's chat shows ("a job of you@example.com is still running", "you have started 20 job(s) today, the cap of 20 per person per day"). Unset, there is no cap. With the queue, a person's queued job counts as their one job; without it, the container's one-job-at-a-time rule applies to everybody.

## Many jobs at once: the queue

With the `queues` block in `wrangler.jsonc`, the Worker gives the API's container the role `queue`: `POST /api/v1/coupon-jobs` answers `queued` at once, the job's input goes to R2 and its id to the queue, and the Worker's consumer starts a `SolverContainer` for it. Up to ten run at once (`max_concurrency` and `max_instances`, raise both together); the rest wait in the queue, and the studio says "waiting for a free solver; N job(s) ahead". Two jobs on the same coupon never run together: the second goes back to the queue and runs when the first has ended. A job stops at 12 minutes. What to watch:

- `npx wrangler queues info anisotropy-coupon-jobs` for the backlog; the dead-letter queue should stay empty.
- Each job's container peak memory is in the jobs table: `SELECT coupon, finished_at - started_at AS took, peak_memory_bytes FROM jobs WHERE peak_memory_bytes IS NOT NULL ORDER BY started_at DESC LIMIT 20;`. If the largest stays far below standard-3's 8 GiB, a smaller instance type for `SolverContainer` saves money; if it nears it, a larger one.
- A job whose solver went silent for 2 minutes, or that sat queued for an hour, is marked `stopped` with the reason; start it again.

## Checks against the live site

The studio's live browser test can run against the hosted site instead of a local API: `PREVIEW_URL=https://anisotropy.dev npm run test:studio-live`, with `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` set to a Zero Trust service token (Zero Trust → Access controls → Service credentials → Service tokens) that the Access application's policy admits (a policy with the action Service Auth). The API records such a run with no signed-in email, since a service token carries none. The test runs the public example end to end and writes a coupon in the hosted store. The numbers to take from such a run, and from the Cloudflare dashboard, are listed in [the beta checks note](../evaluations/website/2026-11-05-beta-launch-checks.md).

## Rolling back

`npx wrangler rollback` returns the Worker to its previous version; `npx wrangler versions list` shows them. A deploy that changed the container image rolls the image out with the version; what a rollback does to a running container image was not tested here (UNVERIFIED). The database is never rolled back: migrations only add tables and nullable columns (ADR-0056), so an older API runs against a newer schema.

## What was and was not verified

Verified on 2026-10-30: the Worker bundles and type-checks, its path rewriting has unit tests, `wrangler deploy --dry-run` accepts the configuration, and the site builds with `/api` as its API address. Verified on 2026-11-02: the deploy workflow's run from `main` (migrations, image, Worker); `app.anisotropy.dev` (the address until amendment 2) sends a visitor without a session to the Access sign-in, and the `workers.dev` address answers 404; sign-in with the emailed PIN; `/api/healthz` answers `{"status":"ok"}` from the container, which starts serving only after its database check and the restore from the bucket. On 2026-11-03, after the cookie fix (#111), the founder reported that the studio works, signed in. Not yet verified: the move to `anisotropy.dev` (amendment 2); the files in R2, the ten-minute links through the bucket's CORS policy and the signed-in email on the record, each checked on its own. The job queue (2026-11-07) is tested locally only (ADR-0056 amendment 3, Evidence): the queues' creation, the consumer reaching ten at once, ten jobs submitted together all finishing, and a solver's cold start on Cloudflare are UNVERIFIED until its first deploy.
