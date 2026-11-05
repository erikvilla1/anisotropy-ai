# The home page's laminate calculator (2026-11-05)

Part 3 of the plan behind the founder's website audit of 2026-10-31, on `feat/home-laminate-hero`, stacked on
`feat/about-industries` with `feat/laminate-summary` merged in: the laminate calculator up front as a 3D view of the typed
stack, the chat block under it, and five blurbs instead of the lab imagery, the workflow steps and the roadmap
([ADR-0058](../../decisions/ADR-0058-one-name-anisotropy-five-service-pages-under-a-services-menu-the-calculator-on-the-home-page-and-a-contact-page.md),
[ADR-0059](../../decisions/ADR-0059-the-engine-describes-the-stack-and-evaluates-first-ply-failure-on-the-response-endpoint-for-the-home-calculator.md)).
This note holds the runs and their output; the component card `docs/components/calculator.md` (0.2) says what was built.

## Unit tests, types and the build

| Check | Command | Result |
| --- | --- | --- |
| website unit tests | `npm test` | 124 passed, 0 failed, 1 skipped (new: `tests/layup.test.ts` 4, `tests/home-calculator.test.ts` 4, one more in `tests/laminate-api.test.ts` for the two optional objects of ADR-0059) |
| types | `npm run typecheck` | `tsc --noEmit` clean |
| the static export | `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000 npm run build` | 19 routes prerendered; `out/index.html` 52.7 kB; the largest script chunk 942 kB (three.js, react-three-fiber and drei, loaded by `components/home/scene.tsx` with `ssr: false` after hydration), the next 324 kB |

## The fixtures

`tests/fixtures/home/response-im7-quasi.json` and `response-im7-quasi-loaded.json` are two answers of the real engine on
the `feat/laminate-summary` branch (`uv run --project api uvicorn anisotropy_api.main:app --port 8010` with
`ANISOTROPY_RUN_RECORDS=off`), for IM7/8552 NCAMP, eight plies of 0.18288 mm at [45/−45/0/90]s, unloaded and under
Nx = 25 kN/m. The unloaded answer: 8 plies, 1.46304 mm, symmetric, balanced, quasi-isotropic, bending–twisting coupling
only, 2.3116 kg/m² from the record's 1.58 g/cm³, first-ply failure "no loads applied". The loaded one: maximum stress
R = 28.1 and Tsai-Hill R = 27.3, both at the bottom face of ply 4 (90°) in transverse tension; maximum strain and Tsai-Wu
not computed, with the engine's reasons. The browser test replaces the echoed `inputs` with each request's own, since the
page checks them.

## Browser tests

Edge channel on this machine, the built site served by `npx serve out -l 3001`.

| Suite | Command | Result |
| --- | --- | --- |
| the home page, API played from the fixtures | `npx playwright test tests/browser/home.spec.ts` | 5 passed, 17.7 s |
| the local specs | `npx playwright test tests/browser/home.spec.ts tests/browser/expansion.spec.ts tests/browser/portfolio.spec.ts` then `tests/browser/research.spec.ts` | 14 passed of the first three (after the two fixes below), research 2 of 3 |
| the calculator job, real API with recording off | `npm run test:calculator` | 8 passed, 21.0 s, the new home scenario first |
| the studio, API played from the fixtures | `npm run test:studio` | 7 passed, 1 failed (the fresh-form scenario pull request #115 fixes) |

What `tests/browser/home.spec.ts` holds: the page draws the stack (the scene container or the WebGL notice), posts the
default stack once (the IM7/8552 NCAMP dataset, the eight angles bottom first, the dataset's thickness), lists eight
plies, shows the engine's description (quasi-isotropic, symmetric and balanced, 1.463 mm, 2.312 kg/m², bending–twisting),
the A matrix's first entry, the record's density and fiber volume fraction, and no failure panel; typing `[0/90]s` posts
the four expanded plies once the typing settles, an unreadable layup shows the error beside the field and in the panel and
posts nothing, and two quick edits post once; a load turns on the failure panel with the engine's R, ply, face and mode and
its reasons for the criteria it did not run; "Want to check the math?" opens `/calculator` with the eight plies, the
dataset and the carried-over notice, nothing calculated yet; a 390 px viewport has no horizontal scroll.

Two failures of the first run were the page's and are fixed: the layup error appeared in two places, so the assertion
now names each; the canvas kept a 4:3 ratio against a 320 px minimum height and grew to 427 px on a 390 px screen, found
with a one-off probe over every element's right edge, fixed by an explicit width and a 260 px minimum.

The remaining failure, `tests/browser/research.spec.ts:27`, is the physics-search count that predates the branch (see
[the site-map note](2026-11-05-site-map.md)).

## Looked at

Screenshots at 768 px (the overflow scenario's) and 1440 px: the slabs show their stripes at ±45°, 0° and 90°, the hovered
ply brightens, the inputs and the results sit beside the view on wide screens and under it on narrow ones, the blurbs
follow in order. Kept in `.preview/`, not committed.

## Not checked

- The hosted site: every page is behind Cloudflare Access (ADR-0056). Not deployed from this branch.
- Headless Chromium's WebGL in CI: the browser tests accept the WebGL notice in place of the scene, so they do not
  depend on it (UNVERIFIED there).
- Battery and frame cost on a phone: the view falls to on-demand frames off screen, in a hidden tab and under reduced
  motion, and draws 120 dust points instead of 300 on coarse pointers; not measured.
- Run-record growth under public traffic (risk R-23): the page has not faced the public.
