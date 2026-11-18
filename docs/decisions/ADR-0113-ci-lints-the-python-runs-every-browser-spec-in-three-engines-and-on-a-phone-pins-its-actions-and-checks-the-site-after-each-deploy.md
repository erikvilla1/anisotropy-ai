# ADR-0113: CI lints the Python, runs every browser spec in three engines and on a phone, pins its actions, and checks the site after each deploy

- Status: Proposed
- Date: 2026-11-18
- Decided by: Founder, 2026-11-17 ("no i think we should leave our CI, what i want is more about what does th CI do, where we can improve on that as well", then "all look very importannt lets build them", on seven improvements listed for him) | Drafted by: Claude Code
- Related: [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md) (the hosted tier; amendment 10, the API restarted by a deploy); [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md) (the studio's browser tests); [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md) (what stays local); `.github/workflows/tests.yml`, `.github/workflows/deploy.yml`, `.github/dependabot.yml`, `ruff.toml`, `playwright.config.ts`, `playwright.site.config.ts`, `tests/browser/phone.spec.ts`, `scripts/check-hosted.py`, `api/src/anisotropy_api/main.py` (`GET /version`)
- Area: process, hosting, website, api

## Context

- On 2026-11-17 the Tests workflow ran nine jobs, about 11 minutes a push. The repository is public, so the minutes cost nothing; the founder chose to keep every job and asked what CI misses.
- Six of the 18 browser spec files ran in CI (calculator, studio, workspace, abaqus-card, import; studio-live only by hand). The other twelve (home, demo, intro, team, research, provenance, shell, expansion, portfolio, material-analysis, physics-foundations, textbook-materials) ran only when someone ran them.
- Every browser test ran in Chromium. Safari on a Mac and every browser on an iPhone or iPad use WebKit; nothing tested it, or Firefox, or a phone as a phone (touch, pixel density, a phone's user agent): the phone specs set a narrow window only.
- No Python lint ran. ruff's own default rules found 986 findings, most of them style; Pyflakes and flake8-bugbear found 297, among them unused imports, variables never read and loop variables never used.
- The deploy's actions were named by a moving tag (`@v7`, `@v4`) while they hold the Cloudflare token and the database address. No tool proposed updates.
- On 2026-11-17 a deploy reached the hosted API only after 20 idle minutes and nothing reported it (ADR-0056 amendment 10). Nothing checked the site after a deploy.
- A pull request uploads a preview version of the Worker that is never visited: `wrangler.jsonc` has `preview_urls: false`, and Cloudflare gives no preview address to a Worker that implements a Durable Object, which the containers are ([Cloudflare's version URLs page](https://developers.cloudflare.com/workers/configuration/previews/)).
- The founder's real coupons live under `.local/` on his machine and never reach the public CI (ADR-0042).

## Options considered

1. Lint with ruff's default rules: 986 findings, mostly style, and the defaults change between releases. Rejected for a named set.
2. Lint with a named set, Pyflakes, pycodestyle's E4/E7/E9 and flake8-bugbear, leaving out the rules that are style or a change of behaviour: chosen.
3. Run the twelve specs by adding each to an existing configuration: a new spec would again be missed. Rejected for one configuration that takes every spec no other claims.
4. Run every spec in every engine as Playwright projects in one job: one long job. Rejected for a job per engine run side by side.
5. Test a phone by running every spec at a phone's size: most specs test the desktop layout and would fail for no fault. Rejected for one phone spec over every page, as an iPhone in WebKit and an Android phone in Chromium.
6. Pin actions by tag and trust the tag: rejected; a tag can be moved. Pinned to the commit, with the version in a comment Dependabot updates.
7. Dependabot per dependency, weekly: a stream of pull requests. Rejected for one grouped pull request a month per kind (actions, npm, Python), majors apart.
8. After a deploy, poll `/api/healthz`: it answers from an old container too. Rejected for `GET /version`, which names the commit the API runs, waited on until it is the deployed one, then one public coupon job through the queue.
9. Test the preview by giving it an address: needs Cloudflare's newer Previews, a container per preview and Access on its address, a hosting change for the founder to decide. Not done here (see Consequences).

## Decision

- `ruff.toml` names the rules (F, E4, E7, E9, B; E402, E731, E741 and B905 left out, each with its reason) and the Tests workflow runs `uvx ruff@0.17.5 check .`.
- `playwright.site.config.ts` runs every spec in `tests/browser/` that the calculator, studio and live configurations do not; the `site-browser` job runs it in Chromium.
- `BROWSER=firefox` or `BROWSER=webkit` picks the engine (`playwright.config.ts`); the `other-browsers` job runs the site's and the workspace's specs in each.
- `tests/browser/phone.spec.ts` opens every page of the app (from `app/**/page.tsx`, the redirects left out) as a phone and checks no sideways scroll and no script error, then taps through the menu to the workspace and answers the chat's first question with a tap.
- Every action in the three workflows is pinned to a commit; the workflows' token is read-only unless a job says otherwise; `.github/dependabot.yml` groups updates monthly.
- The Deploy workflow's `check` job runs `scripts/check-hosted.py` after each production deploy: the home page, `GET /api/version` until it names the deployed commit (10 minutes at most), and one public coupon job (the IM7/8552 fixture, actor `test`, no PDF) to its result. Access admits it with a service token in the repository secrets `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`; without them the job warns and passes.

## Why (evidence)

- Lint: `ruff check --isolated --select E4,E7,E9,F,B .` found 297 findings on main (ad0ce15); with the four rules left out, 68, all fixed or marked where the closure is used within its own pass of the loop; `uvx ruff@0.17.5 check .` passes. After the fixes: engine 525 passed; mcp-server 39 passed; api 546 passed, 138 skipped (no database here); fea 1697 passed, 13 skipped (Abaqus, Tectonic and the local coupons absent).
- The twelve specs, Chromium, on the built site: 81 passed, 7 skipped (switches the specs name), 1 failed, the demo's "a beat takes its own time" at 5.1 s against a 4.8 s limit while ruff and an install ran beside it; run again alone with two workers, `demo` and `portfolio` 17 of 17 passed. The two portfolio cases said to fail on main passed.
- The phone spec, Chromium: 2 passed, 18 pages.
- Firefox and WebKit: no evidence yet. The browsers cannot be downloaded in the cloud session that wrote this (the network policy refuses `cdn.playwright.dev`); the first evidence is the pull request's own run.
- `scripts/check-hosted.py` against a local API behind a stand-in of the Worker's `/api` prefix: home page, version and one coupon job (result after 3 s) passed twice, the second replacing the first's coupon. Against `https://anisotropy.dev` without a token it reports Access's sign-in; with Python's own user agent Cloudflare answered 403, so the script names itself. With a token: UNVERIFIED until the secrets are set.
- Action commits read with `git ls-remote` on 2026-11-18; each tag the workflows used points at the pinned commit, so nothing they run changes.

## Consequences

- A push runs four more jobs (lint, site-browser, Firefox, WebKit) beside the nine, in parallel; the minutes are free while the repository is public, about four times the browser minutes if it goes private (see the CI cost noted for the founder on 2026-11-17).
- A WebKit or Firefox failure may be the browser's own behaviour under test, not a product fault; such a case is fixed or skipped in that engine with the reason in the spec.
- The check after a deploy writes one coupon job a deploy into the hosted store under no signed-in person, and counts against that owner's daily cap; a refusal by the cap warns, not fails.
- The preview stays an upload: it proves the Worker's configuration and bundle are accepted, not that they run. Giving it an address is the founder's choice.
- The founder's real coupons are checked on his own machine on a schedule only if he agrees to it (proposed separately); public CI cannot see them.

## How we will know it was wrong

- A lint finding that is right code more than once a month: the rule leaves the set.
- The Firefox or WebKit job fails for the browser's own reasons more often than for the product's: run them on main only.
- A deploy whose API answers an old commit and the `check` job passes: the version check is wrong.
- Dependabot pull requests left unmerged for two months: the schedule or the grouping is wrong.
