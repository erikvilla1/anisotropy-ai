# ADR-0088: The model proposes rows from the engineer's words; a source guard keeps only what the message writes, and the engineer ticks what enters

- Status: Proposed; since amendment 2 the page reads the mesh from a message itself: a written element size, and "finer" or "coarser" as half or twice the size held
- Date: 2026-11-10
- Decided by: Founder, 2026-11-10 (asked how the chat should read free text, chose "Model proposes, user confirms (Recommended)": the model reads the message and proposes rows and panels, every value appears in a confirm card before it enters the model, and the engine computes every number; the plan of that day, part 6, approved; "ok sounds good continue") | Drafted by: Claude Code
- Related: `api/src/anisotropy_api/proposals.py` (`source_guard`, `unit_named`, `model_view_of_form`), `api/src/anisotropy_api/assistant.py` (`propose`, `PROPOSE_SYSTEM`, `PROPOSAL_SCHEMA`), `api/src/anisotropy_api/main.py` (`POST /v1/workspace/proposals`, `GET /v1/workspace/assistant`), `lib/proposals.ts`, `components/studio/proposal-card.tsx`, `components/studio/coupon-chat.tsx`, `components/studio/laminate-chat.tsx`, [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md), [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md), [ADR-0055](ADR-0055-the-studio-opens-on-a-guided-chat-that-fills-the-same-form-rows-and-the-full-form-stays-one-click-away.md), [ADR-0060](ADR-0060-the-chat-solves-laminate-problems-through-the-case-solver-with-every-value-in-its-own-unit.md), [ADR-0061](ADR-0061-a-coupon-is-stated-in-the-unit-system-the-engineer-picks-and-its-decks-stay-in-the-deck-system.md), [ADR-0087](ADR-0087-optional-physics-is-a-condition-the-engineer-calls-up-and-the-first-is-a-temperature-change-in-the-laminate-calculator-which-alone-grows-itself-to-failure.md), risk R-11
- Area: assistant

## Context

- The chats read a message with fixed patterns (`lib/studio-chat.ts` `readMessage`, `lib/laminate-chat.ts` readers). A phrase they do not know changes nothing and sends the engineer to a panel. ADR-0055 rejected a model reading messages (its option 4): "a model's reading of a number is not checkable the way a pattern is".
- The founder wants a chat that understands free wording and offers the panels asked for (ADR-0087's conditions are the first). He chose that the model proposes and the engineer confirms.
- The assistant's model writes only explanations, behind the number guard (ADR-0052). ADR-0048 lists "draft a form or spec" among the assistant's tools, not yet built.
- The Messages API constrains an answer to a JSON schema (`output_config.format`, structured outputs), and the installed SDK (anthropic 1.17.0) takes it on `beta.messages.create`.

## Options considered

1. **The model proposes, the engineer ticks** (chosen by the founder). Every value is shown with the words it came from, and only what is ticked goes in. A guard drops what the words do not hold before the engineer sees it.
2. The model fills the rows directly, with undo. Rejected: a misread number would enter the problem, and the live preview (ADR-0086) would solve it, before anyone looked.
3. Patterns only (ADR-0055 as it stood). Rejected by the founder: wording outside the patterns is lost.
4. The model returns rows and the page parses them. Rejected: the page would have to judge the model. The API owns the guard, as it owns the number guard.

## Decision

- **What the model sees.** The page offers the rows a message may fill:
  - a coupon: its choices, its numbers each in the unit of the coupon's system, the layup as a notation, and the loading as a displacement or a force;
  - a laminate: the system, the material, the constants, the layup, the ply thickness, the six loads, f12*, the temperature change and the expansions, each number with the dimension of its units; and the conditions that are off.

  The model sees those rows, the message, and the filled rows without names, notes, sources, the team's model or data. The page leaves them out and the API takes them out again (R-11). It never sees a file, a deck or a result.
- **What the model answers.** Structured outputs, one fixed schema: proposals `{key, value, unit, quote}`, conditions `{id, quote}` and an optional question. The value is as written, the unit is copied as written, and the quote is the span of the message stating them. The call is the assistant's own (ADR-0052): `beta.messages.create`, effort low, `fallbacks: "default"`. A refusal, a cut answer (`max_tokens`) or text that is not the JSON proposes nothing, with the reason.
- **The source guard** (`proposals.source_guard`), per proposal:
  - the row was offered, and is proposed once;
  - the quote is in the message;
  - a number is one the quote writes. Its sign may be read from the words ("cooled by 150" is -150), and a zero may be written "zero";
  - a written unit is in the quote, and is one the row takes;
  - a choice is one of the row's;
  - a notation is written in the quote.

  A condition must be offered and asked for in its quote. A question may hold only numbers the message holds. What fails is dropped with its reason.
- **Units.**
  - A coupon value in another unit of the coupon's own system (kN for N, GPa for MPa, cm for mm, kip for lbf, ksi for psi) is converted by an exact power of ten.
  - A value in the other system is dropped with a reason that names both systems, as the chat's switch requires (ADR-0061).
  - A laminate value keeps the unit written, and the engine converts it at solve (ADR-0060). With no unit written, the system's unit applies, as with the patterns.
- **The card.** Each kept value shows its row, its value and unit, how it was written when converted, and its quote, ticked by default. Next come the conditions, the question, and "Not taken" with each dropped proposal's reason. Apply puts the ticked values into the rows or the draft and turns ticked conditions on, opening their panels. Ignore changes nothing. Nothing enters before Apply.
- **Fallback.** With no model, or one that proposes nothing or does not answer, the page's patterns read the message as before. A model that does not answer is not asked again in that session, so a wrong setting costs one wait, not one per message. The page learns whether a model reads messages from `GET /v1/workspace/assistant`, asked once.
- **The record.** Each reading is a run record. It holds the request as received, the guard's answer, and the model's name.
- **Amends** ADR-0055 (its option 4 becomes this, with the patterns kept as the fallback), ADR-0052 (the writers gain `propose`, and the call stops on `max_tokens`), and ADR-0048 (step 3's "draft a form", for a message's rows).

## As built (2026-11-10)

- **API:**
  - `proposals.py`: the source guard, the unit reader and the model's view.
  - `assistant.py`: `Reading`, `propose` on both writers, `PROPOSE_SYSTEM` and `PROPOSAL_SCHEMA`. `_ask` takes a schema and stops on `max_tokens`.
  - `schemas.py`: `OfferedRow`, `ProposalRequest`, `ProposalResponse` and `AssistantInfo`.
  - `main.py`: the two endpoints.
- **Page:**
  - `lib/proposals.ts`: `couponOffer`, `couponRowsFrom`, `laminateOffer` and `laminateDraftFrom`.
  - `lib/studio-api.ts`: `proposeRows` and `assistantInfo`.
  - `components/studio/proposal-card.tsx`.
  - Both chats read with the model when one is on, and with the patterns otherwise. A model that fails is set aside for the session.
  - `blankOwn` moved to `lib/laminate-chat.ts`.
- **Differences from the plan:**
  - The pattern readings still apply at once with "Got it", as ADR-0055 decided, rather than through the card. They are tested and deterministic, and the card exists because a model's reading is not.
  - A coupon message that names another unit system goes to the patterns, which own the switch.
  - The plan's "°F to °C" became "°F kept as written": the laminate keeps every value in its own unit, and the engine converts.

## Why (evidence)

- `api/tests/test_proposals.py`, with a stand-in client and no model called:
  - the unit reader;
  - a good reading kept, with kN and GPa converted;
  - a laminate reading kept in °F, with a cooling read negative;
  - eleven ways a proposal is dropped, each with its reason: a quote not in the message, an invented number, a converted number, a row not offered, the other system, a unit not written, a unit of another row, a unit on a pure number, a choice not offered, a notation not written, and a word for a number;
  - a unit of another dimension;
  - a row proposed twice;
  - conditions and the question;
  - what the model sees;
  - the schema asked for;
  - a refusal, a cut answer and text that is not JSON;
  - the endpoints with the template and with the stand-in;
  - a malformed offer;
  - the run record naming the model.
- `tests/proposals.test.ts`: the offers, the rows and draft from ticked proposals, and the answer's reader.
- `tests/browser/studio.spec.ts`:
  - the coupon card, with values ticked and one unticked, and the offer's units;
  - the laminate card, with a temperature change and its condition.
  - a model that does not answer: the patterns read the message, and the model is not asked again.
- No live model was called. The quality of real readings is UNVERIFIED until the hosted assistant runs with a key, and has no evaluation set yet.

## Consequences

- **Easier:** an engineer writes the coupon or the problem in their own words and confirms what was read, with the words beside each value. A new row or condition is offered by adding it to the offer.
- **Harder:** each message costs a model call and a few seconds while a model is on. Every offered row's kind and unit must stay true to the form.
- **We now depend on** structured outputs and the model copying the engineer's words. When it does not, the guard drops the proposal and the card says why.

## How we will know it was wrong

- Engineers untick or retype values the card proposed often enough that the patterns alone would have served them as well (to be measured from run records once the hosted assistant runs).
- A value enters a problem that the engineer's words do not state. That would be a guard failure: add the case to `test_proposals.py`.

## Amendment 1, 2026-11-16 (the model names the words it could not use, each with a reason by name, and the page says why; drafted after the founder's first live message that read nothing, not yet confirmed by the founder)

**Context.** On 2026-11-16 the founder typed "same thing but make it compresion and 16 plys" on the hosted site, with the model on. Nothing in it can become a row: the product's view offers the unnotched tension coupon only (ADR-0089), a count of plies is not a layup's notation, and each message is read on its own. The model proposed nothing, the patterns read nothing, and the page answered "Not sure what to change" with three example phrases. The engineer could not tell a message that was not understood from one that was understood and cannot be entered.

**Options.** (1) Let the model write a sentence that says why. Rejected: free prose from the model would need the number guard (ADR-0052) and the product's words (ADR-0091) checked on every answer, for a sentence the page can write itself. (2) Show the guard's `dropped` list when nothing is kept. Rejected: it lists proposals the model made and the guard refused, in the guard's words; here the model proposed nothing. (3) Have the page guess from its own word lists. Rejected: the patterns already answer a hidden test spelt as the form spells it; the gap is the misspelt and the loosely worded, which only the model reads. (4) Chosen: a fourth list in the fixed schema.

**Decision.** The model's answer gains `unread`: for each change the message asks for and the model proposes nothing for, the words that ask, copied from the message, and one of three reasons by name: `not_offered` (no row or choice on offer covers it), `no_value` (it names a row on offer and writes no value the row takes), `refers_back` (it leans on an earlier message). The guard keeps a part only when its words are in the message, its reason is one of the three, and no kept proposal quotes the same words; five at most. The page writes the sentence for each reason; the model phrases nothing the engineer reads. The patterns still read first: the page lists the unread parts only when the patterns read none of the message, in place of the pointer to the next panel, and a card that holds proposals lists them under its rows. An API from before this amendment sends no list, and the page reads that as an empty one.

**As built.** `api/src/anisotropy_api/assistant.py` (`PROPOSE_SYSTEM`, `PROPOSAL_SCHEMA`), `proposals.py` (`UNREAD_REASONS`, `source_guard`), `schemas.py` (`UnreadPart`, `ProposalResponse.unread`); `lib/studio-api.ts` (`readProposalAnswer`), `lib/proposals.ts` (`unreadLines`), `components/studio/proposal-card.tsx` (`UnreadList`), and both chats (`notUsed`).

**Evidence.** `cd api && uv run pytest -q tests/test_proposals.py`: 58 passed, 1 skipped (the founder's message kept as three parts; a part outside the message, with a phrased reason, already quoted by a kept proposal, or past the fifth is left out). `npx tsx --test tests/proposals.test.ts`: 7 pass. The browser scenario "the assistant says which words it could not use and why" in `tests/browser/studio.spec.ts` passes with a stand-in model, in the product's view. The first live reading by a model: on 2026-11-16 the founder's message "chnage the lenght to 300 mm and make it 30 wide, layup [0/45/-45/90]s" on the hosted site (`claude-opus-5-5`) came back as a card of three rows, each with its quote, and was applied 3 of 3 (the founder's screenshot; not stored in the repository). Whether a real model fills `unread` as asked is UNVERIFIED: no live message has been read since this amendment.

## Amendment 2, 2026-11-16 (the mesh by talking: a written element size, and "finer" or "coarser" as half or twice the size the form holds, read by the page; not yet confirmed by the founder)

**Context.**
- On 2026-11-16 the founder drew the line between the product's sections: shapes and dimensions belong to a CAD section, and the FEA section is "you already have the model and now you want to do an analysis on it and put necessary configuration for the model such as loads, boundary conditions, mesh". The mesh is the FEA assistant's to change.
- The element size is a row, so a model already proposes it when the message writes the number ("2 mm elements"). The page's own patterns (ADR-0055) read nothing about the mesh, so with no model on the message was not understood.
- "Finer mesh" writes no number. The source guard keeps only a number the message writes, so a model can enter nothing for it and names it unread (amendment 1): the assistant answered a plain request with "names no value to enter".
- At "Who is running it?" the assistant took any message with no digit as the engineer's name. "finer mesh" and a question both became the name.

**Options.**
1. **The page reads the mesh by fixed patterns: a written size as written, and a step from the size the form holds, half for finer and twice for coarser (chosen).** No model is needed, the rule is the same every time, and the answer names the size before and after.
2. Let the model work out the new size. Rejected: the guard exists so that a model writes no number the engineer did not; a size it chose would be the first.
3. Ask "what size?" each time. Rejected for a request this plain: the engineer asked for a step, and the size before and after is shown at once, with the next message able to undo it.
4. A step that follows the model's features (elements across the width, around a hole). Left for later: it needs the mesher's own measures, and a rule per kind of coupon.

**Decision.**
- **A written size.** "2 mm elements", "element size 1.5", "mesh of 3 mm", "set the mesh to 2" set the Element size row to the number written, in the coupon's unit system (`studio-chat.readMesh`). A written size wins over a step in the same message.
- **A step.** "finer", "refine", "smaller elements", "more elements", "twice as fine", "halve the element size" give half the size the form holds (`FINER`); "coarser", "coarsen", "bigger elements", "fewer elements", "twice as coarse", "double the element size" give twice it (`COARSER`), to four figures. The assistant says both sizes: "element size 1 mm (half of 2 mm)". A message that says both ways changes nothing. With no size on the form nothing is guessed, and the assistant says to state one.
- **A question changes nothing.** A message that asks ("would a finer mesh change the answer?") is not an edit; "can you make it finer?" is a request.
- **Where it sits.** The mesh is read with the page's other patterns (`applyMessage`), so it applies at once and is listed under "Got it", as a size or a layup is. With a model on, the model reads first, as before: a written size comes back as a card to tick, and a step, which the model cannot turn into a value, is read by the page.
- **The page computes no mesh.** It sends the new size; the package meshes and the setup check judges the mesh, as for a size typed on the panel.
- **A name is not an edit or a question.** At "Who is running it?" a message is the name only when the page's patterns read nothing in it, it does not ask, it has no digit, and, on a plate read by a model, it names no region or action (ADR-0101 amendment 1).

**Evidence.**
- `npx tsx --test tests/studio-mesh.test.ts`: 4 passed. Seven wordings of a written size, in mm and in inches; seven of finer and five of coarser, each with the size before; 6.25 halves to 3.125; no size on the form gives the sentence and no row; a message with both ways, a question, "stress at element 120" and a layup change nothing of the mesh; a size and a finer mesh in one message are both read. `npm test`: 359 tests, 358 pass, 1 skipped; `npm run typecheck` clean.
- The studio browser suite: 44 passed. Two are new. With no model, "finer mesh" typed while "Who is running it?" is open answers "element size 1 mm (half of 2 mm)" and the preview is asked for with 1; "use 4 mm elements" sends 4; "would a finer mesh change the answer?" sends nothing and is not the name. With a stand-in model that returns nothing to enter, "make the mesh coarser" is sent to the model first and then read by the page as 4 mm (twice 2 mm).
- UNVERIFIED: not deployed, so not tried on the live site; whether half and twice are the steps engineers want has no evidence yet.

