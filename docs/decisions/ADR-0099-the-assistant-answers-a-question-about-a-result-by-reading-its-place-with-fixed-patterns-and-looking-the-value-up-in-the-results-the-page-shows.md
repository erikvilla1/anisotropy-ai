# ADR-0099: The assistant answers a question about a result by reading its place with fixed patterns and looking the value up in the results the page shows

- Status: Proposed
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 ("ok lets start to create this awesome software, i can't wait", on building the assistant he had described the same day: "what is the stress on ply 5 at element 1212 somethng like that and the AI should also know the value of that") | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md) (the engine computes every number); [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md) (the number guard); [ADR-0055](ADR-0055-the-studio-opens-on-a-guided-chat-that-fills-the-same-form-rows-and-the-full-form-stays-one-click-away.md) (the chat reads by fixed patterns); [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md), amendment 2 (the probe table); [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md) (the preview); [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md) (the model proposes rows); [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md) (the product's words); `lib/result-question.ts`, `components/studio/coupon-chat.tsx`, `components/studio/results-view.tsx`
- Area: website, assistant

## Context

- The assistant column (ADR-0055, ADR-0062) reads a typed line into the setup's rows. It could not answer a question about a result: "stress in ply 5 at element 120" fell through to "Not sure what to change".
- The values are already on the page. A solved model's fields hold every ply's stress and strain in the fibre axes at every element centroid (`element.ply.stress_12`, `strain_12`, the invariants), and the probe table (ADR-0066 amendment 2) prints them for a clicked element. The viewer already knows which element was clicked.
- A model that reads a message may propose rows but writes no number of a result (ADR-0052, ADR-0088). No model has been called on the hosted site yet (ADR-0088: UNVERIFIED).
- The founder's plan for the assistant, agreed on 2026-11-16, starts with asking a result and continues with edits by tools that receive the viewer's selection.

## Options considered

1. **The page reads the question by fixed patterns and looks the value up in the fields it shows** (chosen). Works with no model and no key, answers at once, and the number is the same cell the probe table prints. It reads only the phrasings its patterns know.
2. **A model reads the question and proposes the address (element, ply, quantity); code fetches the value.** Reads any phrasing. Needs the model on and tested live first, costs a call per question, and adds nothing to the lookup itself. It can be laid over option 1 later: the typed question is the address a model would propose.
3. **An API endpoint that looks the value up in the stored fields file and writes a run record.** Needed once an assistant on the server, or an outside program, asks. For the browser it repeats a lookup the page can already do, and a preview's fields (ADR-0086) are not stored on the server.
4. **A model answers with the number in its own words.** Rejected: ADR-0001 and ADR-0052; a number typed by a model can be wrong and cannot be traced.

## Decision

- A message is a question about a result when it names a quantity (a stress or a strain, in words or by code or symbol) and a place (an element by its number, a ply, or "here"). `readResultQuestion` reads it into a typed question that holds the place and the probe table's column names, and no number. A message that opens by setting something ("make", "set", "apply") stays the setup's.
- `answerResultQuestion` reads the rows from the fields the page shows through `probeTable`: nothing is computed, converted or rounded. The page prints them as the probe table does.
- "Here" is the element clicked on the model. With none clicked, the assistant asks for one and gives no number.
- An element or a ply the model does not hold is refused with what it holds (the numbering range, the ply count). With no solved model on the page, the assistant says to run first.
- The answer says where and how the value is taken: the element's number, its centroid, the element sets it is in, the probe table's own note (centroid, no averaging, fibre axes), and "from the preview" when the fields are a preview's. One value is a sentence; more are a table.
- The viewer frames the place: the element is outlined and read out, and the model is coloured by the first quantity asked for on the ply named. "Show on the model" on an earlier answer works while the results it was read from are still the page's.
- A question changes no row and calls no service.

## As built (2026-11-16)

- `lib/result-question.ts`: `readResultQuestion`, `answerResultQuestion`, `resultSentence`, `resultUnit`, `RESULT_COLUMNS`.
- `components/studio/project-context.tsx` shares the clicked element (`picked`) and a place to frame (`place`, `showPlace`); `results-view.tsx` reports the one and follows the other; `use-coupon-run.ts` has `shownResults`, the one rule for which fields the page shows, used by the stage and the assistant.
- `components/studio/coupon-chat.tsx`: the question is read before the setup's patterns and before any model; the answer is a `values` entry; the results message gives an example question with an element and a ply of the model.
- Differences from the build plan in the learning guide of 2026-11-16: no API tool and no run record in this step (option 3 waits for the assistant on the server), no flag for a value at a grip edge, and Pressure is not read from words.

## Why (evidence)

- `npx tsx --test tests/result-question.test.ts`: 6 tests pass. They hold the answers equal to the fixture's `element.ply.stress_12`, `strain_12` and `mises` cells and to the probe table's rows, the refusals' words, and that setup messages ("make it [0/90]2s", "10 kN", "strain gauge length 50 mm") are not read as questions.
- `tests/browser/studio.spec.ts`, "the assistant answers a question about a ply's stress…": in Chromium against the recorded fixtures, the answer's cells equal the fixture's numbers as printed, the viewer shows σ₁ of ply 5 at element 125, "here" reads the clicked element, the refusals are shown, and no check or solve is called by a question.
- No evidence yet on how engineers phrase such questions; the patterns come from the founder's examples.

## Consequences

- Asking a value is available to every user with no model, on a preview and on a full run.
- The patterns are a list to maintain; a phrasing they miss gets the setup's "Not sure what to change".
- The typed question (element, ply, columns) and `answerResultQuestion` are the lookup a tool-calling assistant and an MCP server can reuse; the server-side lookup and its run record are still to build.
- The assistant column now reads the clicked element, which the edits planned next ("add a load here") need too.

## How we will know it was wrong

- An answer differs from the probe table's cell for the same element and ply: the lookup is wrong, and the tests failed to hold it.
- Engineers' real questions are mostly missed by the patterns (to be counted once messages are recorded): the model should read the address (option 2).
- A setup message is read as a question in use: the reader's rule for what a question is needs narrowing.
