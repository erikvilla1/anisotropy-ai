# ADR-0012: A static calculator page calls the Python API directly

- Status: Proposed
- Date: 2026-10-03
- Decided by: Implementation proposal for founder review | Drafted by: Codex
- Related: [walkthrough](../walkthroughs/chunk-2-calculator.md), [evaluation](../evaluations/website/2026-10-03-calculator-chunk-2.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0011](ADR-0011-local-laminate-api.md)

## Context

The existing website is statically exported; the local Python API accepts explicit SI-base inputs. The founder approved a small calculator screen with editable inputs, real engine results and clear errors as the next learning chunk.

## Options considered

1. Call the API directly from a React Client Component using browser `fetch`. Keeps static hosting; requires an explicit service address and CORS policy.
2. Add a Next.js server proxy or Server Action. Adds a server deployment and changes the existing static-export setup.
3. Compute laminate results in TypeScript. Duplicates the engine and conflicts with ADR-0001.
4. Require Pa/metres in the form. Matches the API directly but makes the existing GPa/mm practice inputs harder to inspect.
5. Add form/request/schema libraries. Additional abstractions and dependencies for one small form; no evidence yet of a need.

## Decision

Option 1 with existing React/TypeScript and browser APIs. Convert labelled GPa/mm inputs to the API's `SI_BASE` convention at the boundary; preserve explicit loads, signs and bottom-first ply order. Validate returned shapes and echoed inputs at runtime. Clear outputs after every edit and at the start of each submission. Require a configured public API URL; do not silently fall back to a local or remote service. Add explicit local-only CORS origins without credentials. Keep the example in its existing cited JSON file.

## Why (evidence)

- Installed Next.js guides for [static exports](../../node_modules/next/dist/docs/01-app/02-guides/static-exports.md), [Client Components](../../node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md) and [environment variables](../../node_modules/next/dist/docs/01-app/02-guides/environment-variables.md) describe this execution model and build-time public configuration.
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/) explains explicit origin allowlists and preflight behavior.
- [MDN fetch documentation](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch) describes HTTP error handling and cancellation.
- [Unit tests](../../tests/laminate-api.test.ts) check conversions, blanks, ordering and response validation. [Browser tests](../../tests/browser/calculator.spec.ts) exercise real API requests and failure states; actual outputs are recorded in the evaluation.
- Production reliability, accessibility with assistive technology and public deployment behavior: no evidence yet (UNVERIFIED).

## Consequences

No new runtime dependencies. The website must be rebuilt when its API address changes. Four loopback website origins are allowed for local development; CORS is not authentication. TypeScript request types and Python schemas must remain aligned, with real browser integration tests catching drift. The 20-second client timeout stops waiting, not necessarily server execution.

## How we will know it was wrong

Revisit when authenticated deployment requires a different request boundary, when multiple analysis contracts make hand-maintained types error-prone, or when measured requests need a long-running job workflow.
