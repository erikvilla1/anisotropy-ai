# ADR-0136: A repair's chat reads one change into the engine's form and previews it on a copy, and a sweep names the smallest repair whose adhesive stays elastic at a load, with that pick solved as a slice

- Status: Proposed
- Date: 2026-11-21
- Decided by: Founder, 2026-11-21 ("Start slice 5 make no mistakes"; and his choice "Smallest that stays elastic" on the card "Choose what the repair's sweep may claim when you name a load") | Drafted by: Claude Code
- Related: [ADR-0128](ADR-0128-a-wings-chat-reads-a-change-of-plies-into-the-engines-form-and-previews-it-on-a-copy-answers-from-the-wings-report-and-the-reference-pages-and-the-wing-changes-only-on-the-engineers-apply.md), [ADR-0130](ADR-0130-a-bonded-repairs-hand-calculation-is-the-stepped-lap-as-a-shear-lag-model-in-the-engine-the-patchs-force-at-every-step-boundary-the-adhesives-elastic-limit-and-the-long-overlap-strength-of-a-yielding-adhesive.md), [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md), [ADR-0132](ADR-0132-a-repairs-slice-is-solved-in-calculix-as-a-plane-of-eight-node-elements-held-flat-with-the-laminates-far-field-width-strain-and-its-bondline-and-plies-are-read-back-as-means-by-the-engine.md), [ADR-0135](ADR-0135-a-stepped-patch-repair-is-worked-on-a-page-of-its-own-under-fea-by-hand-on-every-change-and-as-a-solved-slice-on-request-and-its-report-is-a-page-laid-out-for-paper.md), [ADR-0127](ADR-0127-the-wings-references-are-three-pages-in-our-own-words-design-rules-test-methods-and-allowables-searched-by-subject-with-the-wings-theory-each-section-with-the-other-words-it-is-asked-by.md), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), `engine/src/anisotropy_engine/repair/changes.py`, `engine/src/anisotropy_engine/repair/sweeps.py`, `lib/repair-chat.ts`
- Area: engine, api, website, assistant

## Context

The repair's page (ADR-0135) has no chat: a repair is changed field by field in the model tree. The plan's fifth slice is "Add a step", "make each step 0.5 in", and a first sweep, "the smallest repair that brings back a strength you name".

Two facts shape the sweep.

1. The engine gives no strength. Its hand calculation (ADR-0130) and the solved slice (ADR-0132) are elastic: they give the largest bondline stresses and the load at which the adhesive reaches its elastic limit, which every page prints beside "Not the repair's strength".
2. In that elastic model the step length soon stops mattering. Worked by the engine on `engine/examples/example-patch-repair.toml` (100 N/mm, shear strength 30 MPa), the load at the adhesive's elastic limit is 172.4 N/mm at a 0.5 mm step, 216.8 at 2 mm, 233.5 at 4 mm, 238.2 at 8 mm and 238.5 at 10 mm and every longer step the panel holds. On `example-external-patch-repair.toml` it is 142.2 N/mm from 2 mm up. What does move it: the four plies cut as one, two and four steps give 144.1, 178.9 and 238.5 N/mm; a bondline of 0.15 mm in place of 0.1 mm gives 292.1 N/mm. So a pick made on step length alone names a very short step, true to the model and not a design.

The founder was shown fact 2 on a card on 2026-11-21 and chose: the sweep names the smallest repair whose adhesive stays elastic at the load named, checks that pick in a solved slice, and says plainly it is not a strength or a design rule.

## Options considered

How a change is made:

1. **The page's patterns read one change into the engine's form, the engine previews it on a copy, and the engineer applies it** (chosen): the wing's way (ADR-0128). Every number in a change is one the message writes; a unit in the message goes to the engine with the value, which converts it (ADR-0002); nothing changes until Apply, and an applied change can be undone.
2. The chat changes the repair at once. Rejected: a misread message would change the model unseen.
3. A model reads the message. Left for later, behind a guard, as for the wing: no model reads a repair's message on the hosted site in this slice. An outside assistant reaches the same previews through the MCP server.

What a sweep may claim (the founder's card):

1. **The smallest repair whose adhesive stays elastic at the load named, the pick solved as a slice** (chosen).
2. Tables only, and no pick until the adhesive's yielding is modelled (the plan's sixth slice). Not chosen by the founder.
3. "The smallest repair that carries the load" or "that brings back the strength". Rejected: the engine has no strength to compare with (fact 1).

What a sweep varies:

1. **One stated quantity at a time** (chosen): the step length, the number of steps for the same plies, the bondline's thickness, the cover plies' overlap or the patch's overlap. A table of one quantity can be read and checked by eye, and every row is the hand calculation of a whole repair file.
2. Several at once, searched by an optimiser. Rejected for now: nothing to check its answer against, and a result nobody can read back.

How the pick is checked:

1. **The API solves the pick's slice in the same request** (chosen), when the repair states what a solve needs: the hand calculation has no peel stress and no ply stresses, so a pick is reported by both. A pick the slice does not hold is said so.
2. Sweep with solved slices throughout. Rejected: about 3 s a row.
3. The hand calculation alone. Rejected: the pick would rest on the weaker of the two models.

Where the chat's explanations come from:

1. **A page of our own words, "Bonded repairs", with its public sources, searched with the repair's theory by the subject "repair"** (chosen): as the wing's references (ADR-0127). The repair's theory sections stay out of every other search (ADR-0102 amendments 5 and 6).
2. A model's own knowledge. Rejected: ADR-0001, ADR-0102.

## Decision

**A change.** `anisotropy_engine.repair.changes.RepairChange` is one change: a quantity set to a value (`step_length`, `bondline`, `load`, `damage`, `cover_overlap`, `patch_overlap`, each with the unit the engineer wrote, or the file's), steps added or removed, the number of steps set, or the same plies regrouped into more or fewer steps (`plies_per_step`). `change_repair` writes the repair file the change gives and never changes the one given. A new step of a patch whose plies are listed (every patch bonded on top, and a flush patch with its own layup) needs its plies' angles, and is refused without them. `preview_change` reads both files by the engine's own rules, works both by hand and returns the changed file, the change in one sentence, and both summaries: the largest bondline shear and where, the load at the adhesive's elastic limit, the repair's width, its steps. A change the repair cannot take is refused in the engine's words.

**A sweep.** `anisotropy_engine.repair.sweeps.RepairSweep` names one quantity and, optionally, its range and a load. `sweep_repair` works the repair by hand at every value (the values are round ones the engine chooses, about 25 of them, with the repair as it stands among them) and returns a row for each: the value, the repair's width, the largest shear and where, the load at the elastic limit, or the engine's refusal of that value. With a load named, each row says whether the adhesive is still elastic at it, and the pick is the row of the smallest repair that is (the narrowest, then the nearest to the repair as it stands). The answer also says from which value the limit load stays within 1 % of its value at the end of the range: where the quantity stops mattering. A sweep with a load needs the adhesive's shear strength and is refused without it.

**The words.** A pick is "the smallest of these whose adhesive is still elastic at N". It is never the repair's strength, a design, a margin or "carries". Every sweep answer carries "Not the repair's strength" and, for the step length, that a short step that keeps the adhesive elastic is not a design rule for step length.

**The API.** `POST /v1/repairs/changes` previews a change. `POST /v1/repairs/sweeps` runs a sweep and, with a pick and `confirm` (the default), solves the pick's slice as `/v1/repairs/solve` does, returning its largest shear and peel, what comes first and at what load, and whether that load is at or above the load named. A solve that cannot run leaves the sweep's answer whole and says the pick is not checked. `POST /v1/workspace/theory-sections` takes `about: "repair"`.

**The page.** `lib/repair-chat.ts` reads a message by fixed patterns into one of: a change, a sweep, a question about the result (the largest shear, the limit load, the peel stress, the first ply, the patch's forces, the repair's size, its layups, or a verdict), a question of why, how or what a thing is, a command (solve the slice, the report, the STEP file), or "not read". A question about the result is answered from the report and the solved slice the page holds, every number as the engine or the solver gave it. A question that asks for a verdict ("is it strong enough?") is answered that the page gives no strength, with what it does give. "Solve the slice" starts the solve. The chat sits under the assistant's words; the line "This page has no chat yet" goes.

**Outside assistants.** The MCP server gains `read_repair`, `repair_results`, `preview_repair_change`, `sweep_repair` and `search_repair_references`: read and preview only, as the wing's.

**Questions.** `tests/assistant-questions/repair.json` holds the repair's questions (ADR-0121). The real-model "Assistant check" of the bank is run on the founder's word, since it spends his key.

## Why (evidence)

- Fact 2 above: `engine/tests/test_repair_changes.py::test_the_examples_limit_load_goes_flat_in_the_step_length` holds the example's numbers.
- The wing's chat has worked this way since ADR-0128 (preview on a copy, Apply by the engineer).
- No evidence yet that engineers ask a repair's chat for these changes in these words: the question bank is written from the plan's examples and the wing's bank, not from use.

## Consequences

- A repair can be changed and compared in words, and "what if" is one message.
- The sweep's pick teaches what the elastic model says: more steps and a thicker bondline lower the peak, a longer step does not. It can name a step far shorter than practice uses; the words beside it carry that.
- Every sweep row is a whole hand calculation, so a sweep costs milliseconds; the one solved slice costs seconds and is the API's longest wait on this page.
- The patterns read English as engineers typed the plan's examples. What they cannot read is said plainly, with examples.

## How we will know it was wrong

- An engineer reads a pick as a design or a strength: the wording, or the pick itself, goes (option 2 of the card).
- The solved slice often fails to hold the hand calculation's pick: the sweep should rank by the slice.
- The bank's real-model run shows an outside assistant quoting a pick as a strength: the tools' instructions change before the feature is offered to one.
