# Component card: browser laminate calculator | version 0.1 | updated 2026-10-03

## Purpose and intended use

`/calculator` connects an editable form to the existing engine API for local research exploration. [Chunk 2 walkthrough](../walkthroughs/chunk-2-calculator.md).

## Inputs / outputs

One material (GPa, dimensionless Poisson ratio, source text), a bottom-first stack (degrees/mm) and all six force/moment resultants per width. Displays the API's A/B/D matrices, mid-plane strains and curvatures in labelled SI units. The shared cited JSON practice example supplies the initial form.

## Dependencies and connections

Next.js static route -> React state -> boundary conversion/validation -> browser fetch -> FastAPI CORS and request validation -> existing engine -> checked JSON -> tables. Existing React, Next.js, TypeScript and lucide-react; no new runtime library. `NEXT_PUBLIC_ANISOTROPY_API_URL` is embedded at build time.

## Evaluation

[Website/API connection checks](../evaluations/website/2026-10-03-calculator-chunk-2.md). Real-browser success cases use the actual local API, including signed loads, an unsymmetric laminate and mobile rendering.

## Failure behavior and limits

Blank values never become zeros. Field errors are shown next to inputs, results are cleared after edits, inputs are frozen while a request is pending, and cancellation/network errors do not display fallback results. No configured service means calculation is disabled. Source text is caller supplied; dataset selection, persistent run records, AI, failure/stress outputs and deployment controls remain future work. The engine's physical applicability limits still apply. Reloading clears work.

## Owner

Founder / engineering.
