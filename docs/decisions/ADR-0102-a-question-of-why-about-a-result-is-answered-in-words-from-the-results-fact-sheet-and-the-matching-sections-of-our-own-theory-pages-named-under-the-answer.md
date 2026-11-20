# ADR-0102: A question of why about a result is answered in words from the result's fact sheet and the matching sections of our own theory pages, named under the answer

- Status: Proposed; asked for one to three sentences and its note shortened by ADR-0099 amendment 2
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 (chose "Results plus our theory pages" on the question "Choose what a 'why' answer about a result is built from") | Drafted by: Claude Code
- Related: [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md) (the fact sheet and the number guard); [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md) and [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md) (questions about a value); [ADR-0001](ADR-0001-deterministic-engine.md); [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md); [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md); [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md); `api/src/anisotropy_api/theory.py`, `api/src/anisotropy_api/result_answers.py`, `lib/result-why.ts`, `engine/docs/reasons.md`
- Area: assistant, api, website, docs

## Context

- The assistant answers a question about a value of a result by looking it up (ADR-0099, ADR-0100). A question of why ("why is ply 4 in compression?", "why does the 90 fail first?") was answered with a table of values, or with "Not a question I can read yet". ADR-0100 names "why" answers as not built.
- Before a result was on the page, "why is ply 4 in compression?" was read by the setup's patterns and changed the test to compression.
- Every result carries a fact sheet, the numbers our engine computed for it (`explanation.json`, ADR-0052): about 110 values for a tension coupon. A model may rephrase the template's sentences only when every number it writes is a fact.
- Our own theory is written down in two pages the manual prints, `engine/docs/theory.md` and `fea/docs/theory.md`: 33 sections of equations and conventions, each naming the function that computes it. The hosted image carries both.
- The theory pages hold equations, not reasons. Tried on 2026-11-16: "why is ply 4 in compression along the fibres?" found only the conventions section.

## Options considered

What an answer is built from:

1. The fact sheet alone. No new source and nothing to cite; the answer can say what happened and not why.
2. The fact sheet and the matching sections of our own theory pages, with the sections named. The reason comes from text we wrote and review, and the engineer sees where it is from. Needs the sections found for a question, and reasons written where the pages hold only equations.
3. The fact sheet and the model's own knowledge of mechanics. No pages to write; the reason cannot be checked against anything of ours or cited, and it changes with the model.

How the sections are found:

4. By the words the question and a section share (BM25), in the API's own code. No new service, no stored vectors, the same sections for the same question, so a test can pin them. Misses a question worded with none of the section's words.
5. By embeddings in a vector store. Finds a section worded differently; needs an embedding provider, a store and a rebuild on every change of a page, for 45 sections.

Where the numbers come from:

6. The API reads the fact sheet from the job's files. The numbers never pass through the browser; a live preview (ADR-0086) has no job, and it is what the tension screen shows before a run.
7. The page sends the fact sheet of the result it shows. Works for a preview and a run alike; the API cannot tell that the numbers are the engine's.

Which numbers an answer may hold:

8. The fact sheet's and the question's. The same guard as the explanation's; a constant written in a section may not be said.
9. Those and every number written in the sections shown. Lets a constant be quoted; the sections hold many small numbers, so a ratio or a count the model made up would often pass.

## Decision

Options 2, 4, 7 and 8.

- A message that asks why, or what something means ("why", "how come", "explain", "what causes", "what does … mean"), is answered in words when a result is on the page. With no result the page says so and changes no row. It is read before the patterns of ADR-0099 and before the setup's.
- The page sends the question and the fact sheet of the shown result to `POST /v1/workspace/result-answers`. The API finds up to three sections by the question's words and hands a model the question, the fact sheet as the explanation's writer sees it (no name, note, date or record name) and the sections, each with an id.
- The model answers in a fixed schema: the answer, the ids of the sections it rests on, and whether those sections hold the reason asked for. It is told to give no reason of its own and to say so when the sections do not explain the matter.
- The answer is kept only when every number in it is the fact sheet's or the question's, at the precision written. An answer set aside is not shown. The page names the sections from their ids, by document and title; the model never names one, and an id that was not shown is dropped.
- With no model nothing is written, and the page names the sections the question found.
- Reasons in words live in a third page, `engine/docs/reasons.md`, "Reasons behind a result": twelve short sections, each ending with the theory it rests on, holding no value of a result. It is a draft that the founder reviews with this record.

## As built (2026-11-16)

- `api/src/anisotropy_api/theory.py`: `sections()` splits the three pages at their `##` and `###` headings (45 sections); `find(question, limit)` ranks them by BM25 over words (k1 1.5, b 0.75, a title counted three times), with plurals and a few double spellings brought together; `Section.shown` leaves out the lines that pair an equation with its function.
- `api/src/anisotropy_api/result_answers.py`: `answer_view`, `answer_schema`, `answer_guard`. `assistant.py`: `ANSWER_SYSTEM`, `answer_question` on the three writers' interface.
- `POST /v1/workspace/result-answers` in `main.py`, recorded with the question, the digest of the facts, the ids of the sections found and the model's name when one wrote (ADR-0026).
- The page: `lib/result-why.ts` (`asksWhy`, `factsOf`, `whyLines`), `answerResult` in `lib/studio-api.ts`, the `why` entry of `components/studio/coupon-chat.tsx`.
- Difference from the founder's option as worded ("the matching section"): up to three sections are shown to the model, and the page names those the answer says it rests on.

## Why (evidence)

- The founder's choice on 2026-11-16, quoted above.
- `cd api && uv run pytest -q tests/test_theory.py tests/test_result_answers.py`: 31 passed on 2026-11-16, with a test database. They cover the split, the ranking on a stand-in page, nine questions of why that find their reason first on the real pages, the guard (a number of the model's own is set aside; a section that was not shown is dropped), the Claude writer behind a stand-in client, the endpoint on the public example coupon's fact sheet, and the run record.
- `npx tsx --test tests/result-why.test.ts`: 7 passed. The browser scenario "a question of why is answered in words from the results and our theory pages, the section named, and no row changes (ADR-0102)" passed, with a stand-in for the API and stand-in answers.
- The whole suites on 2026-11-16, in a cloud container: `cd api && uv run pytest -q` with a test database, 626 passed and 1 skipped; `npm test`, 365 passed and 1 skipped; `npm run typecheck`, clean; the studio browser suite, 45 passed; `cd engine && uv run pytest -q`, 525 passed. The fea package is not changed; its document tests (`test_coupon_document.py`, `test_documents_for_the_team.py`, `test_theory_markers.py`) gave 43 passed and 2 skipped.
- No evidence yet that a real model's answers are right or useful: no real model has answered a question here. UNVERIFIED until the founder asks questions on the hosted site.
- The reasons page was written from the theory pages and the example coupon's result (the sign of the shear in the 45-degree ply, the compression along the fibres of the 90-degree ply, the failure index as one over the factor). It has not been reviewed by the founder.

## Consequences

- A question of why gets a short answer with its source named, and never changes a row.
- The answer is as good as the pages. A reason the pages do not hold is said to be missing; adding a section to `reasons.md` is how a gap is closed, and each section is ours to review.
- The fact sheet is the page's copy. A caller who alters it gets an answer about the altered numbers, shown to that caller alone; the run record keeps the digest of what was sent.
- A constant written in a section cannot be quoted as a number in an answer.
- Each answer is one call to the model, with the fact sheet and up to three sections as input.
- The sections are named by document and title. A customer cannot open them yet: the manual is not on the website.

## Not in this record

- A place where a customer can open a named section.
- Follow-up questions that lean on the answer before: each question is read alone.
- Questions of why about the setup check or a laminate problem.
- Finding sections by meaning, and customer documents (later phases of the plan).

## How we will know it was wrong

- The founder's live questions get answers that are wrong, or that he would not put in front of a customer.
- More than one answer in five is set aside by the number guard, or says the pages do not explain the matter, on the questions engineers ask.
- A question finds none of the sections that hold its answer because it shares no word with them, more than rarely: then the sections are found by meaning (option 5).

## Amendment 1, 2026-11-20 (the answer as the heading, the sections folded)

**Context.** In the first real-model run of the question banks (ADR-0121, run 44654876004, 2026-11-20), nine of fourteen answers of why were graded weak and one failed, all for their shape, none for a number: four long sentences of terms and symbols where one to three short ones were asked for, the heading a word ("Why") rather than the answer, and a line under it citing "Reasons behind a result, ...; Finite element theory, 7. First-ply failure" that read as the product's internals. The founder asked for answers that are "simple and fast to the point" with the details folded (2026-11-17).

**Options.** (1) Cut the model's text to three sentences on the page: a cut can drop the sentence that makes the answer true. Rejected. (2) A schema of a one-line answer and its reasons: every stored answer and the guard's tests change for the same effect as a sharper instruction. Rejected for now. (3) Ask the model for at most three sentences of at most 25 words, the first the answer on its own and a quantity named in words with its symbol beside them; show that first sentence as the heading and the rest under it; say in one short line what it rests on ("From the results and our theory pages.", or "From the results only."), and fold the sections' names under Details. Chosen. An answer not shown keeps its line naming the sections the question found, since that is then all there is to read.

**Decision.** Option 3: `ANSWER_SYSTEM` in `api/src/anisotropy_api/assistant.py`; `whyLines` (`heading`, `more`) in `lib/result-why.ts`; `whyMessage` in `components/studio/coupon-chat.tsx`, with the test ids `chat-why-answer` and `chat-why-sources`.

**Evidence.** `tests/result-why.test.ts` 7 of 7 and the browser spec of this record pass (2026-11-20); the screenshot `.local/website/screenshots/studio-why.png` shows "Ply 4 (90 degrees) fails first by tension across its fibres: σ₂ is 60.6 MPa there." as the heading, one sentence under it and the section under Details. How a real model's answers grade after the change: UNVERIFIED until the next real run.
