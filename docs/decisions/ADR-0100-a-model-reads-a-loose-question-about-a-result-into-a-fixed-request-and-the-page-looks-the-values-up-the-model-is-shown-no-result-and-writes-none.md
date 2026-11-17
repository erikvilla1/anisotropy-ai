# ADR-0100: A model reads a loose question about a result into a fixed request, and the page looks the values up; the model is shown no result and writes none

- Status: Proposed
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 (on the questions the assistant could not read, "which ply carries the most load?", "where is the shear highest?", "compare the 0° and 90° plies", a question with typos: "you said this is next?") | Drafted by: Claude Code
- Related: [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md), whose option 2 this builds over its option 1; [ADR-0001](ADR-0001-deterministic-engine.md); [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md); [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md) (the gauge section); [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md) (the model answers in a fixed schema, a guard reads it); [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md); `api/src/anisotropy_api/result_questions.py`, `lib/result-question.ts`, `components/studio/coupon-chat.tsx`
- Area: assistant, api, website

## Context

- ADR-0099 answers a question that names a quantity and a place in a wording its patterns know. It could not answer where a quantity is largest, a comparison of plies, or a question worded loosely or with typing mistakes.
- A model already reads setup messages into rows in a fixed schema, behind a source guard (ADR-0088). A model that explains a result may write only numbers of the fact sheet (ADR-0052).
- The page holds the solved fields; a preview's fields are not stored on the server (ADR-0086).
- The package reports failure and the largest ply stresses on the gauge section, the `Gauge` set less the elements at a gripped node, because stress at a clamped edge grows as the mesh is refined (ADR-0066, ADR-0085).

## Options considered

1. **The model names what is asked for in a fixed schema; the page looks the values up** (chosen). The model sees the message and what a question may name (quantities, plies with their angles, regions, whether an element is clicked) and no result. Its answer holds names from that offer and whole numbers, so it cannot carry a value. One model call per loose question; a wrong reading shows as the wrong place or quantity in the answer's heading, never as a wrong number.
2. **The model is given the results and answers in prose under the number guard.** Reads "why" questions too. Rejected for this step: the fields are megabytes, a fact sheet of them would have to be designed first, and prose with numbers needs the guard of ADR-0052 on every sentence. It stays the way for explanations ("why is ply 4 in compression?"), which this step does not give.
3. **Tool calling on the server: the model calls a lookup tool that reads the stored fields.** Needed for an assistant that works without the page (ADR-0099 option 3). Rejected for now: a preview has no stored fields, and the page can run the same request. The request of option 1 is the tool's arguments, so this can follow.
4. **More patterns only.** Done for the plain wordings of an extreme ("where is the shear stress highest?"), which need no model. Patterns do not read typos, positions ("the outer plies") or "carries the most load".

## Decision

- **Two kinds of request.** `values` reads quantities at one element, for every ply or the plies named. `extreme` finds where a quantity is largest (most tensile), smallest (most compressive) or largest in magnitude over a region, for every ply or the plies named. A shear stress, a shear strain, Mises and Tresca are always read by magnitude.
- **An extreme is a stored value picked out, not a derived number.** The page reads the fields' own value per element and ply and picks one; it sums, averages and derives nothing. The answer gives each ply's own extreme and the plies tied with the largest.
- **The region is the gauge section unless the message names another.** The page reads the gauge section as the package does (the `Gauge` set less the elements at a gripped node); a test holds its extremes equal to the package's `ply_extremes`. For the whole model, the answer says so when the largest sits at a grip edge.
- **The page's patterns read first** (ADR-0099, with the plain wordings of an extreme). The model is asked only when a model is on, results are on the page, and neither the result patterns nor the setup's patterns read the message. When it reads nothing of the results, the setup's reading goes on as before.
- **A question is never read as a row of the setup.** With results on the page, a message that opens with why, what, where, which or compare goes to the model even when the setup's patterns would read a word of it ("why is ply 4 in compression?" names a test); when nothing reads it, the assistant says what can be asked, and no row changes.
- **What the model is shown** (`POST /v1/workspace/result-questions`): the message, the twelve quantities in words, the plies with their angles, the regions `default`, `gauge` (when the model has one) and `whole`, and whether an element is clicked. No value of a result, no file, no name or note, and no region the engineer named. The request schema refuses any other field.
- **What the model answers**: a kind (`values`, `extreme`, `none`), quantities and a region from the offer, ply numbers, an element number, whether it means the clicked element, an end, and one short question back.
- **The guard** keeps the reading only when the quantities and the region are on offer, each ply is one the laminate holds, and an element is a number the message writes. A ply may be named by angle or position, so its number need not be written; the answer shows which plies were read. A question back may hold only the message's numbers and is shown only in the product's own words (ADR-0091). The page judges the place again when it answers.
- **Recorded** as a run with the model's name when one read the message (ADR-0026), like a proposal.

## As built (2026-11-16)

- `lib/result-question.ts`: the typed question is `values` or `extreme`; `gaugeSection`, the extremes, `resultOffer`, `questionFrom`, `extremeSentence`; the patterns read "highest", "largest", "minimum", "peak" with a quantity, and leave "maximum stress criterion" to the setup.
- `api/src/anisotropy_api/result_questions.py` (the offer in words, the schema, the guard), `assistant.py` (`read_question`, one prompt), `schemas.py`, `main.py` (the endpoint).
- `components/studio/coupon-chat.tsx`: the model's reading before the setup's; the `extremes` answer (a sentence and each ply's extreme, or one row per quantity), "Show on the model".
- Not built: "why" questions (option 2), named element sets offered to the model, a lookup on the server (option 3). No model has been called: the tests use a stand-in, and whether the hosted site has a key is unknown.

## Why (evidence)

- `npx tsx --test tests/result-question.test.ts`: 12 tests pass. They hold the page's extremes over the gauge section equal to the package's `ply_extremes` (overall and ply by ply, 130 of the `Gauge` set's 140 elements), each extreme equal to a cell of the fields, and the offer free of any value of the results.
- `cd api && uv run pytest -q tests/test_result_questions.py`: the guard on each way a reading can go wrong, the schema (no decimal number, no free text but the question back), what the model is shown, the endpoint, and that a request carrying results is refused (422).
- `tests/browser/studio.spec.ts`, "with a model on, a loose question…": in Chromium with a stand-in model, "wher is teh shear highest?" gets the same sentence as the plain wording read by patterns, the body sent to the API holds the five offered fields only, and "why is ply 4 in compression?" leaves the test as it was, with a model and without.
- No evidence yet from a real model: how well it reads loose questions is UNVERIFIED until the hosted site has a key and real messages are tried.

## Consequences

- With a model on, loose and misspelt questions about values, extremes and comparisons are answered with the solver's numbers; with none, the plain wordings still are.
- A loose question costs one model call; a message that is neither a result question nor readable by the setup's patterns now costs two (this reading, then ADR-0088's).
- The page repeats the package's rule for the gauge section; the test against `ply_extremes` is what keeps the two together.
- The request is the form a server-side tool or an MCP tool will take.

## How we will know it was wrong

- An answer shows a value that is not a cell of the fields, or the gauge-section extremes differ from the package's card on the same page.
- With a real model, readings are often wrong (the heading names a quantity or plies the engineer did not mean) or often dropped by the guard: the prompt, the offer or the guard needs changing; to be counted from the run records.
- Engineers mostly ask "why" questions: option 2 is needed sooner.
