# Component card: browser laminate calculator | version 0.2 | updated 2026-11-05

## Purpose and intended use

Two faces of one calculation. The home page (`/`, `components/home/laminate-hero.tsx`) shows a laminate as the visitor types it: a 3D view of the stack, the library material's recorded properties, the engine's description of the stack, the A, B and D matrices and, once a load is typed, first-ply failure (ADR-0058, ADR-0059). `/calculator` (`components/laminate-calculator.tsx`) is the full solution: an editable form with typed or library materials, the strains and curvatures, every cited value, and the run id. "Want to check the math?" on the home page carries the current inputs to `/calculator` through `sessionStorage` (`lib/home-calculator.ts`), read once on arrival. [Chunk 2 walkthrough](../walkthroughs/chunk-2-calculator.md) covers the full page's origin.

## Inputs / outputs

Home page: one library dataset (the cited records with elastic inputs, `lib/material-library-options.ts`), a layup in laminate notation expanded by `lib/layup.ts` (the coupon chat's reader plus the mirror an `s` asks for; bottom face first, ADR-0004), one ply thickness in mm, and six optional loads per width. Full page: one material (GPa, dimensionless Poisson ratio, source text), a bottom-first stack (degrees/mm) and all six force/moment resultants per width. Both send `POST /v1/laminates/response` in SI base units and display the API's A/B/D matrices; the home page also shows `summary` (ply count, thickness, symmetric, antisymmetric, balanced, kind, coupling, areal mass or why not) and `first_ply_failure` (R, ply, face and mode per criterion the inputs support, the rest named as not computed); the full page shows the mid-plane strains, the curvatures and the provenance.

## Dependencies and connections

Next.js static routes -> React state -> boundary conversion and validation (`lib/laminate-api.ts`, which also validates the two optional objects of ADR-0059) -> browser fetch -> FastAPI -> engine (`summary.py`, `failure.py`, `laminate.py`, `response.py`) -> checked JSON -> tables and the 3D view. The view is react-three-fiber and drei, the libraries the studio already uses (ADR-0051), loaded only in the browser; it draws the typed stack and computes nothing. `NEXT_PUBLIC_ANISOTROPY_API_URL` is embedded at build time; without it the home view still draws and the numbers say the service is unavailable.

## Evaluation

[The home page's laminate calculator](../evaluations/website/2026-11-05-home-laminate-hero.md); [the original connection checks](../evaluations/website/2026-10-03-calculator-chunk-2.md). The home page's browser test plays the API from `tests/fixtures/home/` (two answers of the real engine captured on 2026-11-05); one scenario in the calculator job asks the real engine.

## Failure behavior and limits

Home page: an unreadable layup or a blank thickness is an error beside the field and sends nothing; a request goes out 450 ms after the last edit, the previous one aborted, and only the newest answer is shown; a result that no longer matches the inputs is dimmed until the new one arrives; a network or service error clears the numbers and says so. Each settled edit is one run record under the actor `calculator` (ADR-0026). First-ply failure appears only when a load is given, and maximum strain and Tsai-Wu are listed as not computed unless their inputs exist (ADR-0021). Full page: blank values never become zeros, field errors sit beside inputs, results are cleared after edits, inputs are frozen while a request is pending, cancellation and network errors show no fallback. The engine's physical applicability limits still apply (flat laminate, one material, linear elastic classical laminate theory). Reloading clears work. WebGL missing: the view says so and the numbers stand without it.

## Owner

Founder / engineering.
