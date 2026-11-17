# ADR-0099: The assistant answers a question about a result by reading its place with fixed patterns and looking the value up in the results the page shows

- Status: Proposed; extended by [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md) (where a quantity is largest, several plies at once, and a model reading loose questions into the same typed question); a question of failure is answered with the package's own first-ply failure since amendment 1; every answer about a result is said short, with the rest folded, since amendment 2
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

## Amendment 1, 2026-11-16 (a question of which ply fails is answered with the package's own first-ply failure; not yet confirmed by the founder)

**Context.** On the hosted site the founder asked "what is the the ply that fails" of a solved tension coupon and was shown "Extremes in the gauge section": the largest σ₁, σ₂ and τ₁₂ with their plies. No ply was named as the one that fails. The patterns here read a quantity and a place, so the message was no question of theirs; with a model on it went to [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md)'s reading, whose kinds were `values`, `extreme` and `none`, and the model chose `extreme`. The package already writes the answer (ADR-0085): per criterion the first ply to fail, its mode, element, load factor and the loading at failure, in the gauge section (ADR-0108). The founder's words on it: "didn't really tell me which is the ply that fails".

**Options.**
1. Leave it to the model and widen its instructions only. Rejected: with no model the question stays unread, and a plain wording should not cost a model call.
2. Send it to the answer in words of ADR-0102. Rejected: a model would write sentences for an answer the package already holds as values, and the answer would be withheld whenever the model's numbers drift.
3. Chosen: a third kind of question, read by fixed patterns before any model, answered with the package's own first-ply failure.

**Decision.** A message that asks which ply fails, breaks or goes first, whether the coupon fails or holds, or for the load, factor or strength ratio at first-ply failure is a question of failure (`lib/result-failure.ts`, `asksFailure`). It is read after a request for the working (ADR-0103), a question of why (ADR-0102) and a question that names a quantity, and before the setup's reading; a line that opens by setting something, a question of which criteria there are, and a run, check or file that failed are not it. The answer is `answerOf`'s (the answer card's), for the criterion the message names, else the one that governs. It is three short lines (`failureLines`): the ply as the heading ("Ply 4 (90°) fails first"), the loading with the verdict ("At 1.032 × the applied load (1.032 mm, 16740 N). The coupon holds."), and one line of labels for what it rests on (the criterion, the mode, the element, where it is read, the plies tied). Each criterion's row, where the gauge section is read and the earlier failure at a grip are folded under "Details". The first build said all of it in sentences with the table and a long note open; the founder, on seeing it: "There is too much wording ... simple and fast to the point". "Show on the model" frames the element and colours the model by that ply's failure index in that criterion. With no result, or a result solved before the answer was written, the page says so. No model writes a word of the answer and the page computes nothing (ADR-0051).

**Evidence.** `npx tsx --test tests/result-failure.test.ts`: 4 tests pass (22 wordings read, the founder's among them; 18 setup lines, value questions and software failures left alone; the three lines equal to the package's numbers of the stored result). `tests/browser/studio.spec.ts`, "with a model on, a loose question…": in Chromium the founder's wording gets the first ply to fail with no model asked. UNVERIFIED on the hosted site.

## Amendment 2, 2026-11-17 (every answer about a result is said short, the answer first, with the rest folded under "Details"; not yet confirmed by the founder)

**Context.** The founder, on the first build of amendment 1's answer (2026-11-16): "There is too much wording it looks like need it to be more simple and less AI generated, make it more trustworthy and user friendly response simple and fast to the point". That answer was cut to three lines. The other answers kept their form: a value as a sentence ("σ₁ in ply 2 (0°) at element 125 is … MPa."), an extreme as a sentence with every ply's row and a note of up to four sentences open under it, a why with a note of two sentences, the working with a note of two.

**Options.**
1. Leave the older answers as they were. Rejected: the same conversation would then answer in two voices.
2. Drop what is not the answer (how the values are taken, each ply's row, the sections). Rejected: an engineer who checks the answer needs them.
3. Chosen: one form for every answer, with the rest kept and folded.

**Decision.** An answer about a result is, in order: the answer itself as the heading; one muted line of short labels joined by " · " for what it is of (the ply, the element, the region, the plies tied, "preview" when it is one); a table only where the answer is several values; and "Details", closed, for the rest. So:
- **One value** (`valueLines`): "σ₁ = 1182 MPa", then "ply 2 (0°) · element 125". Details: the element's position and how the value is taken.
- **Several values at an element**: the table, as before. Details as above.
- **Where a quantity is largest** (`extremeLines`, [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md)): "Largest |τ₁₂|: −45.86 MPa", then "ply 1 (45°) · element 73 · gauge section · tied with plies 3, 6, 8". Several quantities are three columns (quantity, value, ply). Details: each ply's own extreme or each quantity's element and ties, and the count of elements read. A largest value at a grip edge keeps one open line, "At a grip edge, so it grows with a finer mesh. Ask for the gauge section.", because it is a value not to rely on.
- **Why** ([ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md)): the model is asked for one to three short sentences (it was two to five), and the line under them is "Based on the results and: <sections>." or "Based on the results only.".
- **The working** ([ADR-0103](ADR-0103-the-working-behind-an-answer-is-written-by-the-fea-package-when-it-solves-and-shown-by-the-page-when-asked-no-model-writes-a-formula-or-a-number.md)): its steps are what was asked for and stay open; its note is one sentence.
No value, place or source is taken away, and nothing new is computed.

**Evidence.** `npm test`: 382 pass, 1 skipped (`tests/result-question.test.ts`, `tests/result-why.test.ts` hold the new lines equal to the stored result's numbers). The browser scenarios of ADR-0099, ADR-0100, ADR-0102 and ADR-0103 assert the headings, the labels and that the tables are hidden until "Details" is opened. No evidence yet that engineers find the short form clearer: the founder has seen one answer in it.

