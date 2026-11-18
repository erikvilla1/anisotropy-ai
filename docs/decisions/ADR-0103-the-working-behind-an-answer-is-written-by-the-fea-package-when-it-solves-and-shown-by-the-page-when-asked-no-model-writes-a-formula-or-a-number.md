# ADR-0103: The working behind an answer is written by the fea package when it solves and shown by the page when asked; no model writes a formula or a number

- Status: Proposed; its note shortened by ADR-0099 amendment 2
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 ("maybe can offer a small detailed explanation through formulas and numbers being inputted if the user decides that, so if htey ask send me the formula or the proof of it being solved and the assistant provides that", asking for the feature); how it is built is the draft's proposal and not yet confirmed | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md); [ADR-0029](ADR-0029-finite-elements-own-membrane-kernel-validated-against-abaqus.md); [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md); [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md); [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md); [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md); [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md); [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md); `fea/src/anisotropy_fea/working.py`, `fea/src/anisotropy_fea/fields.py`, `lib/result-working.ts`, `components/studio/working-steps.tsx`, `fea/docs/theory.md`
- Area: fea, assistant, website

## Context

- A result leads with its answer: the factor at first-ply failure by each criterion, the ply and the element, and the loading then (ADR-0085). The assistant answers a question about a value (ADR-0099, ADR-0100) and a question of why in words (ADR-0102).
- None of these shows how a number follows from the ones before it. The founder asked that an engineer who wants it can be sent "the formula or the proof of it being solved".
- The theory pages hold every equation in symbols. The result's files hold every value: the ply's strain and stress at each element (`fields.json`), the factors and where they govern (`summary`), the reaction.
- The engine computes every number of a result (ADR-0001). A language model asked to put numbers into a formula does arithmetic of its own, and the number guard of ADR-0052 sets aside any number that is not a fact, so a worked step could not pass it.
- The chain behind the answer is short and closed: the ply's strain in its fibre axes, its stress as the stiffness times that strain, the criterion's ratio, and the factor times the applied loading.

## Options considered

Who writes the working:

1. A model writes it from the fact sheet and the theory sections. Any step could be asked for in any words. The intermediate numbers would be the model's own arithmetic, which ADR-0001 forbids and the number guard would set aside; a wrong step would look as certain as a right one.
2. The fea package writes it when it solves, as data beside the result: each step's formula, the same formula with the values in place, and the result. Every number is the solve's or the engine's and a test can pin every line. Covers only the steps we write.
3. The API computes it on request for any ply and element. Covers every place; needs the job's arrays read again or a solve, a new endpoint and a wait, and a preview (ADR-0086) has no job.
4. The page computes it in the browser from the fields it holds. No wait and any place; it would be a second implementation of the stiffness and the criteria in TypeScript, outside the engine.

Which places are worked:

5. The first ply to fail by each criterion, on the answer's basis. It is the number the result leads with, and the chain is small (about 8 kB beside a 670 kB field file for the example coupon).
6. Every ply of every element. Complete; multiplies the file by the number of plies and elements for lines few will read.

How a request is read:

7. By the page's fixed patterns ("show me the formula", "the proof", "the working", "how was that calculated", "step by step"), with a button under a result and under an answer of why. The same words give the same working, with no call and no model.
8. By the model. Reads loose wording; adds a call, and a request it reads wrongly could change a row.

How it is shown:

9. Typeset by KaTeX, which the website already uses for its theory cards, loaded only when a working is shown.
10. As plain text. No library; fractions and roots are hard to read.

## Decision

Options 2, 5, 7 and 9.

- The fea package writes `summary.working` with every solve, a preview's and a full run's: for the first ply to fail by maximum stress and by Tsai-Hill, on the answer's basis (the gauge section, or the whole model where there is none), four steps: the strain in the ply's fibre axes, the stress from the strain, the criterion, the loading at first-ply failure.
- Each step holds a title, a sentence, the values put in (symbol, value, unit, what it is), its equations (the formula in symbols, the formula with the values in place, the result) and the theory section it is from.
- Values are put in to six significant figures and results are written to four, the fact sheet's digits, so a step repeated on a calculator meets its result.
- A chain is written only when it closes: the engine's stiffness times the stored strain gives the stored stress, and the engine's criterion called again on that stress gives the stored factor, each to a relative 1e-9. A chain that does not close is left out. A stress that is zero to roundoff is written as zero and sets no limit.
- The page reads a request for the working by fixed patterns, before a question of why and before the setup's patterns, and shows the chain of the criterion named, else of the earliest. A button "Show the working" stands under the results and under an answer of why.
- No model reads the request and no model writes any part of the working. With no result the page says so and changes no row. A criterion with no working is said, with the ones that have one.

## As built (2026-11-16)

- `fea/src/anisotropy_fea/working.py`: `working_of(solution, field, summary, units)`, with `given` and `tex` for the digits and `settled` for roundoff zeros; `fields.py` puts its result in `summary["working"]`. Isotropic parts and results with no criterion get none.
- `fea/docs/theory.md`, section 7: the working and its check, with the marker for `working_of`; `docs/manual/build.py` and `fea/tests/test_theory_markers.py` know the module.
- The page: `lib/result-working.ts` (`asksWorking`, `criterionNamed`, `workingOf`, `workingFor`, `givenText`), `components/studio/working-steps.tsx` (KaTeX, set in line so a long formula breaks at its operators in the narrow chat), the `working` entry of `components/studio/coupon-chat.tsx`, the type in `lib/studio-api.ts`.
- No change to the API: the working travels in the fields the page already receives.
- Difference from the founder's words ("the assistant provides that"): the assistant shows working the solver wrote; it cannot derive one for another quantity or place.

## Why (evidence)

- The founder's request on 2026-11-16, quoted above. The choice of options 2, 5, 7 and 9 is the draft's; no evidence yet that it is what he wants.
- `cd fea && uv run pytest -q tests/test_working.py`: 11 passed on 2026-11-16. They cover: every result of the working equals the solve's own value at that ply and element; each step repeated from the values as written meets its result at the digits written; the lines with values in place are built from those values; a chain that does not close is left out; a result with no criterion has no working; a bending coupon is worked on the face that fails; a zero stress sets no limit; the theory sections named exist as headings; and the page's fixture holds what `studio_tool.py live` writes today for the public example coupon.
- For that coupon ([45/0/-45/90]s, IM7/8552, 1 mm): ply 4 (90°) of element 183, a stress across the fibres of 60.6 MPa from the strain, maximum stress R = 64.0523/60.597 = 1.057, Tsai-Hill FI = 0.9388 and R = 1.032, so 1.032 mm and 16740 N at first-ply failure, each equal to the result's own answer.
- `npx tsx --test tests/result-working.test.ts`: 6 passed (the requests read and not read, the criterion named, the fixture's chains, malformed shapes, and every formula typeset by KaTeX in strict mode).
- The browser scenario "the working behind an answer is shown when asked: each formula with the solver's numbers put in, and no model is asked (ADR-0103)" passed: the button and three typed requests show the chains, typeset, with no call to a model's endpoint, no second check or solve and no row changed.
- The whole suites on 2026-11-16, in a cloud container: `cd fea && uv run pytest -q tests ../engine/tests`, 1585 passed, 43 skipped, 3 failed and 1 error, the four that need Gmsh, which the container lacks (the same four as before this change); `cd api && uv run pytest -q` with a test database, 626 passed and 1 skipped; `npm test`, 371 passed and 1 skipped; `npm run typecheck`, clean; the studio browser suite, 46 passed.
- UNVERIFIED: no engineer has yet repeated a chain by hand outside the tests, and the working has not been seen on the hosted site.

## Consequences

- An engineer can check the answer by hand from what the page shows, with each step's theory section named.
- The working cannot disagree with the answer: it is written from the same arrays, and left out when it does not close.
- Only the first ply to fail by maximum stress and by Tsai-Hill is worked. The working of another ply or element, of Tsai-Wu and maximum strain, of the rotation from the laminate's strain to the ply's axes, and of an isotropic part is not written.
- Each new kind of working is code and tests in the fea package, not a prompt.
- A result solved before this record carries no working; the page says to run it again.
- `fields.json` and each preview grow by the chains, about 8 kB for the example coupon.
- KaTeX and its stylesheet load in the workspace the first time a working is shown.

## Not in this record

- The working at a ply and element the engineer names or clicks (option 3).
- A model that explains a step in words beside the formula; ADR-0102's answers stay apart from the working.
- A way to copy or download the working, and the working in the PDF package.

## How we will know it was wrong

- The founder, or an engineer, repeats a step by hand and does not meet the result shown.
- Engineers ask for the working of places or criteria that are not written more often than for the first ply to fail: then it is computed on request (option 3).
- Requests worded outside the patterns are common enough that the button is the only way people find it.
