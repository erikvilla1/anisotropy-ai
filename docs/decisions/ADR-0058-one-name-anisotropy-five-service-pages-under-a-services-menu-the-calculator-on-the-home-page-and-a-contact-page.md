# ADR-0058: One name, Anisotropy; five service pages under a Services menu; the calculator on the home page; a Contact page; account gating deferred

- Status: Proposed
- Date: 2026-11-05
- Decided by: Founder, 2026-11-01 (the website audit of 2026-10-31, revised 2026-11-01: "Remove 'AI' after Anisotropy. Do this everywhere the company's name is used"; "leave the tab called Services and make it a drop-down menu that will contain the different 'services' we offer: Computer Aided Design, Finite Element Modeling, Test Plans, Documentation, Manufacturing Plans. Where each service will have its own page"; "each service page shows information about it and a demonstration of what it does but not necessarily access to it"; "let's remove Calculator as this is too simple. Instead, the calculator will live on the Home page"; "Let us add my contact for now") and 2026-11-05 (service pages now, account gating after a team meeting; his Gmail on the Contact page; the rename reaches the site, its metadata and the README; placeholder image slots) | Drafted by: Claude Code
- Related: [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md) (`/studio` is a route of the site), [ADR-0055](ADR-0055-the-studio-opens-on-a-guided-chat-that-fills-the-same-form-rows-and-the-full-form-stays-one-click-away.md) (`/chat`), [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md) (the invite-only hosted tier the access sections point to), [ADR-0057](ADR-0057-a-shared-brain-for-the-teams-agents-lives-in-docs-brain-the-one-folder-written-to-main-without-a-pull-request.md) (the brain keeps its own wording; names on the site need consent), `lib/services.ts`, `lib/site-nav.ts`, `components/site-shell.tsx`, `components/services-menu.tsx`, `components/services/service-page.tsx`, `app/services/`, `app/contact/page.tsx`, the website audit (the founder's PDF, kept outside the repository)

## Context

The founder audited the website on 2026-10-31 (layout and interfaces, not copy). The header then read About, Industries, Services, Materials library, Calculator, Studio and the brand "Anisotropy AI". The audit found Services, Calculator and Studio in conflict ("the menu is not intuitive"), the calculator "too simple" for a tab of its own, and the studio a finite element tool that belongs under Services. It asked for one page per service, each showing what the service does and a demonstration first, with access below, and for a Contact page. It also wants access to the "expensive" services granted on creating an account and limited to a number of uses, and asks for a meeting on that; the founder deferred that part on 2026-11-05.

Facts that bound the choice: `/studio`, `/studio/view` and `/chat` are the routes ADR-0051 and ADR-0055 decided, the mocked and live browser tests open them by path, and the hosted live test of ADR-0056 opens `/studio` on anisotropy.dev. The CI job `calculator-browser` waits for `http://localhost:3001/calculator` before it runs. The site is a static export served by a Worker that treats only `/api` specially, so a nested route exports as a page of its own. The whole hostname sits behind Cloudflare Access during the closed beta, so no page is public yet.

## Options considered

1. Keep "Anisotropy AI" and the flat six-link header; add the service pages beside the existing tabs. Rejected: the audit's first two items ask for the opposite, and three overlapping entry points (Services, Calculator, Studio) are what it calls unintuitive.
2. One long `/services` page with an anchor per service. Rejected: the audit asks for a page per service with its own description, demonstration and access section, and a single page cannot carry five demonstrations.
3. Five routes `/services/<slug>` under a disclosure in the header; `/calculator` and `/studio` kept at their routes but out of the header, the studio reached from the finite element page's access section and the calculator from the home page. Chosen.
4. Move `/studio` under `/services/finite-element-modeling`. Rejected for now: it breaks the routes of ADR-0051 and ADR-0055, every studio browser test and the hosted live test, for no gain the audit asks for; the finite element page links to the studio instead.
5. Build account sign-up and per-account use limits now. Rejected by the founder on 2026-11-05 until the team has met; the hosted tier's per-person job limits (ADR-0056, stage 5) already cover the API side.

## Decision

- The name is "Anisotropy" everywhere a visitor sees it: the wordmark, the page titles, the footer, the aria labels, the README and the package name. Decision records, skills, `docs/brain/` and the git history keep the wording they were written with.
- The header is About | Industries | Materials library | Services | Contact us. Services is a link to the landing page plus a disclosure button listing the five service pages: `/services/computer-aided-design`, `/services/finite-element-modeling`, `/services/test-plans`, `/services/documentation`, `/services/manufacturing-plans`, in the audit's order, from one data module `lib/services.ts`. On narrow screens the five appear inside the open mobile menu.
- Each service page has the same shape: the description, what exists today, a demonstration, what is planned (labelled PLANNED), then the access section. Nothing on a page claims more than the repository backs; the one number quoted is the IM7/8552 bending comparison already in the changelog (ADR-0053).
- The finite element page's access section links to `/studio` for the invited users of the closed beta; the documentation and design pages do the same; test plans send the visitor to `/chat`; manufacturing plans, which do not exist, send them to `/contact`.
- `/calculator` stays as a route out of the header; the home page carries the calculator (its own change). `/studio`, `/studio/view`, `/chat`, `/data` and `/sources` do not move.
- `/contact` shows the founder's address as a plain mailto link until an anisotropy.dev address exists. The site is static; there is no form.
- Pictures and clips are slots with a label (`components/media-slot.tsx`); the team supplies the media later. No file is fetched from outside the site.
- Accounts and per-account use limits are not built; they wait for the team meeting the audit asks for.

## As built (2026-11-05)

Four pull requests, in the order the plan set: the site map (the name, the header with the Services disclosure, `/services` and its five pages, `/contact`, the media slots); the engine and API description of a stack (ADR-0059); the About page with the workflow and the roadmap moved from the home page and the team at its end, plus the Industries media slots; and the home page with the laminate calculator up front (`components/home/`), the chat block under it, and five blurbs (mission, the five services, the evidence, the team, what is new). The home page draws the typed stack with react-three-fiber and asks the engine for every number per settled edit; "Want to check the math?" hands the inputs to `/calculator`, kept as the full solution. Differences from the plan: the Services item is a link plus a disclosure button rather than a menu role, so the existing navigation test keeps its "Services" link; the layup reader is the coupon chat's, so a layup may list as many plies as the coupon form has rows; the ABD grid shows A, B and D once each with a note that B appears twice in the ABD matrix.

## Why (evidence)

- The audit of 2026-10-31, revised 2026-11-01, is the founder's; its items 1, 2, 3, 13, 14 and 15 are quoted above. The founder's four answers of 2026-11-05 are recorded in the Decided by line.
- The routes that must not move: `tests/browser/studio.spec.ts` opens `/studio` and `/studio/view`; `tests/browser/studio-live.spec.ts` opens `/studio`; `playwright.studio.config.ts` and `playwright.studio-live.config.ts` wait for `/studio`; `playwright.calculator.config.ts` waits for `/calculator`.
- The Worker's only special path is `/api` (`worker/routing.ts`), so the nested service routes need no routing change; the static export writes `out/services/<slug>.html` (checked by `npm run build` in the evaluation note of this change).
- Test runs, in [the evaluation note](../evaluations/website/2026-11-05-site-map.md): `npm test` 114 passed; `npm run typecheck` and `npm run typecheck:worker` clean; the build exports 19 routes with the five service pages and `/contact`; the studio browser test reaches the studio through the finite element page (7 passed, 1 failure that pull request #115 fixes); the calculator browser test passes by route (7 passed); the local specs 12 passed, with one failure in the physics search count that predates the branch.

## Consequences

- Easier: one data module names the services, so the header, the landing page, the five pages and the home page agree; a planned service is visibly planned; the studio keeps its address and tests.
- Harder: two places now describe the finite element work (the service page and the studio itself), and the service page's facts must be kept true as the studio changes; the Access policy still hides every page, so the public cannot see the new map until the policy is scoped by path (a later ADR-0056 amendment).
- We depend on: the audit's structure holding until the team meeting; each team member's consent before a name appears on the site (ADR-0057 amendment 1).

## How we will know it was wrong

- The team asks for Calculator or Studio back in the header, or visitors cannot find the studio from the services pages (a support question or a beta tester's report says so).
- A service page stays "planned" for a quarter with no change behind it, which means the page promises more than the roadmap holds.
- The team meeting decides on accounts and limits in a shape the access sections cannot express, which means the pages need a new section rather than a link.
