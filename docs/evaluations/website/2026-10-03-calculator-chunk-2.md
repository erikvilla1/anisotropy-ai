# Calculator connection evaluation | 2026-10-03

Base: `33568ed`; branch: `feat/calculator-ui-chunk-2`. Local Windows checks used the production static export, Microsoft Edge and the real loopback Python API. Engine equations and the request/response contract are unchanged.

## Observed results

| Command | Output |
| --- | --- |
| `npm test` | 57 passed, 0 failed |
| `npm run typecheck` | Exit 0, no diagnostics |
| `uv run pytest -q tests ../engine/tests` (from `api/`) | 239 passed in 14.93s |
| `npm run build` | Successful static export, including `/calculator` |
| `npm run test:calculator` | 6 passed in 7.1s |
| `npm run test:e2e -- --workers=2` | 31 passed in 28.2s |

Unit cases check boundary conversions, explicit zeros, blanks, numeric syntax, ply order, field-error mapping and malformed/mismatched responses. Five API cases check CORS for the four local website origins and rejection of an unapproved preflight.

Browser cases send the shared cited example to the actual API and compare its axial strain to `100e6 / 147e9`. They exercise signed loads, a bottom-first 0/90 stack with mixed loads and nonzero coupling, API compliance errors, blank fields, stale-result clearing, network/malformed responses and cancellation. Error/cancellation cases intercept traffic; success cases do not. Desktop/mobile screenshots were inspected locally; widths 390, 768 and 1024 had no page overflow.

## Failures and follow-up

- First calculator run: four passed, two failed because broad alert selectors also matched Next.js's hidden route announcer. Scoped those selectors to the calculator form; all six then passed.
- First full browser run with eight workers: 30 passed, one existing homepage image-loading check exceeded its five-second poll timeout. The same check passed alone (1 passed in 2.9s), and the complete suite passed with two workers without changing the homepage or its test. Cause is not established; parallel-load timing is a hypothesis.

## Limits

The 20-second timeout branch, assistive-technology audit, other browsers and public deployment are UNVERIFIED. Successful rendering does not independently validate all laminate physics; the existing engine tests supply that separate evidence. No material-source verification, persistent run record, authentication or AI behavior is claimed. CI results are recorded on the pull request.

Decision: [ADR-0012](../../decisions/ADR-0012-browser-calculator.md). Learning walkthrough: [chunk 2](../../walkthroughs/chunk-2-calculator.md).
