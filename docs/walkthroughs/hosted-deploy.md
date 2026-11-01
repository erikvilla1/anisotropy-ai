# The hosted tier: what runs where, how to deploy, how to roll back

The decision is [ADR-0056](../decisions/ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md); this page is the operator's side of it. Everything below is invite-only: nobody reaches the site or the API without signing in through Cloudflare Access.

## The pieces

| Piece | What it is | Where it is configured |
| --- | --- | --- |
| The Worker `anisotropy-studio` | Serves the website's static export (`out/`) and forwards `/api/*` to the container | [`wrangler.jsonc`](../../wrangler.jsonc), [`worker/index.ts`](../../worker/index.ts) |
| The container `ApiContainer` | The API with CalculiX, Gmsh and Tectonic, one instance, built from the [`Dockerfile`](../../Dockerfile) by `wrangler deploy` | `wrangler.jsonc` (`containers`), [docker/README.md](../../docker/README.md) |
| Cloudflare Access | Sign-in with an email allow list and one-time PINs, in front of the Worker; adds the token the API checks | Zero Trust dashboard; the API's `ANISOTROPY_ACCESS_*` secrets |
| Neon PostgreSQL | The run records and the jobs table | the `DATABASE_URL` secret; migrations by the deploy workflow |
| R2 | A done job's files, its package and the coupon folders; the coupons are restored from it when the container starts | the `ANISOTROPY_R2_*` secrets; the bucket's CORS policy |
| GitHub Actions | [`deploy.yml`](../../.github/workflows/deploy.yml): build, migrate, deploy on a green merge to `main`; a preview version per pull request | repository secrets |

The site is built with `NEXT_PUBLIC_ANISOTROPY_API_URL=/api`, so the browser calls the API on the same origin and no CORS list is needed. The Worker strips `/api` and hands the request to the container unchanged, headers included; the container's FastAPI refuses any request without Access's `Cf-Access-Jwt-Assertion` token when its Access settings are set.

## The first deploy, from a laptop

Docker Desktop must be running: `wrangler deploy` builds the image from the Dockerfile and pushes it to Cloudflare's registry (the first push is the slow one, about 2 GB).

```bash
npm ci
npx wrangler login       # a browser window; signs Wrangler into the Cloudflare account
npm run build:hosted     # the site into out/, calling the API at /api (scripts/build-hosted.ts sets the address; shells differ)
npx wrangler deploy      # the Worker, then the image; prints the workers.dev address
```

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
```

The container reads these at its next start (`worker/routing.ts` lists the names it is given). After the migrations have run once against Neon (`cd api && DATABASE_URL=... uv run alembic upgrade head`, or the deploy workflow), the API is complete: with `DATABASE_URL` set and no `ANISOTROPY_RUN_RECORDS=off`, it refuses to start until the database is reachable and migrated, as locally.

Wait a few minutes after the first deploy before expecting the container to answer; Cloudflare provisions it after the Worker is live. `npx wrangler containers list` shows its state.

## Sign-in: the Access application

1. Zero Trust → Integrations → Identity providers → add **One-time PIN** (new organisations do not get it by default).
2. Zero Trust → Access controls → Applications → Add an application → Self-hosted and private → **Workers** → select `anisotropy-studio`. A Worker application covers its `workers.dev` address, any custom domain and its previews.
3. One policy, action Allow, Include → **Emails** → the invited addresses (or **Emails ending in** a domain).
4. Save; then Configure → Additional settings → copy the **Application Audience (AUD) Tag** into the `ANISOTROPY_ACCESS_AUD` secret, with the team domain into `ANISOTROPY_ACCESS_TEAM_DOMAIN`.

To add or remove a user: edit the policy's email list. Access applies it at the next sign-in; the API records the signed-in email on every run (`user_email`).

## The bucket

Create the R2 bucket, then an API token with **Object Read & Write** scoped to it; its Access Key ID and Secret Access Key are the two `ANISOTROPY_R2_*` key secrets. Add a CORS policy on the bucket allowing the site's origin (the `workers.dev` address, later the domain) for `GET` and `HEAD`: the browser fetches a job's files from the bucket through short-lived links, and without the policy those fetches fail.

## Deploys after the first

`deploy.yml` runs when the Tests workflow finishes green on `main`: it builds the site, applies the migrations to Neon and runs `wrangler deploy`, passing the commit as `ANISOTROPY_GIT_COMMIT` so run records carry it. It needs three repository secrets: `CLOUDFLARE_API_TOKEN` (a token made from the "Edit Cloudflare Workers" template, with the account's Workers, Containers and R2 permissions), `CLOUDFLARE_ACCOUNT_ID`, `DATABASE_URL` (and `DATABASE_URL_UNPOOLED` when Neon gives one). A pull request uploads a preview version of the Worker without production traffic and without a new container image. **Run workflow** on the Actions page deploys `main` by hand.

## Rolling back

`npx wrangler rollback` returns the Worker to its previous version; `npx wrangler versions list` shows them. A deploy that changed the container image rolls the image out with the version; what a rollback does to a running container image was not tested here (UNVERIFIED). The database is never rolled back: migrations only add tables and nullable columns (ADR-0056), so an older API runs against a newer schema.

## What was and was not verified

Verified on 2026-10-30: the Worker bundles and type-checks, its path rewriting has unit tests, `wrangler deploy --dry-run` accepts the configuration, and the site builds with `/api` as its API address. Not verified until the first real deploy: the container answering on Cloudflare, Access's header reaching the container through the Worker, the R2 bucket with its CORS policy, and the deploy workflow's run.
