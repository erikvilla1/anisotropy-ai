# ADR-0101: On a plate the model proposes supports and loads from the engineer's words and the element clicked, and a guard keeps what the words or the click hold

- Status: Proposed; since amendment 1 a plate that states no support or no load yet shows its shape, so its first hold can be the edge clicked
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 ("right now i can't edit the model click on an edge and tell the AI to make edits, or change boundary conditions or change load really fast", on what the assistant lacks; the same day, on the card asking where "hold this, add a 10 kN load here" should work first, he chose "The plate, only you see it live") | Drafted by: Claude Code
- Related: [ADR-0054](ADR-0054-a-plate-kind-states-supports-and-loads-as-lists-over-named-regions-and-the-studio-lets-the-user-click-a-region.md) (the plate, its regions and the click); [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md), which this extends from rows to a plate's lists; [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md) (the clicked element as "here"); [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md) (the plate is hidden on the hosted tier); [ADR-0001](ADR-0001-deterministic-engine.md); `api/src/anisotropy_api/plate_proposals.py`, `lib/proposals.ts`, `lib/studio-plate.ts`, `components/studio/coupon-chat.tsx`
- Area: assistant, api, website

## Context

- A plate is held and loaded over named regions: its four edges, its face, its tabs and a hole's ring (ADR-0054). The engineer adds a row on the Loads and supports panel, or clicks an element on the checked model and presses hold or load on one of its regions.
- The assistant column did nothing for a plate. It said "Plates are set up on the model", and its own check of a plate sent no supports and no loads.
- A model already reads a message into rows the engineer ticks, behind a source guard that keeps only what the message writes (ADR-0088). It was offered rows, and a plate's supports and loads are lists, not rows.
- The clicked element is shared between the viewer and the assistant (ADR-0099), on the results only.
- A force "in tension" on an edge has a direction and a sign that follow from the edge, not from the words.
- The mesh that can be clicked exists only once the setup builds a model: a plate with no support has no preview (`studio_tool.py check` writes `checklist.json` alone).

## Options considered

1. **Offer a plate's supports and loads to the model as lists in the same reading, with the regions on offer and the regions clicked (chosen).**
2. **Fixed patterns only ("hold the left edge", "10 kN on the top edge").** Rejected as the first step: the wordings of a support (held, fixed, clamped, pinned, simply supported) and of a load's direction are many, and the hosted assistant has a model on. Patterns can follow for the plainest wordings, as they did for results (ADR-0099, ADR-0100).
3. **Let the model call tools that change the plate (set a support, add a load).** Rejected: a change would enter the problem before the engineer saw it. ADR-0088's card already holds a change until it is ticked.
4. **Let the model work out the direction and sign of a force in tension.** Rejected: it is geometry, the same for every message, and a wrong sign is a wrong problem. The code knows each edge's outward normal.
5. **Offer the boxes the engineer drew, by their names.** Rejected for now: the names are the engineer's own words, which the model is not shown (R-11; ADR-0100 left named regions out for the same reason).

## Decision

**The offer.** On a plate, with every test offered, the page sends with the message: the plate's own regions with their kind (edge or area), the regions the clicked element belongs to (`here`), the units a force and a pressure are stated in, and the names of the regions already held and loaded. No value, no box the engineer drew.

**The reading.** The model answers in the rows' schema with two lists added. A support: a region on offer, the directions it holds (x, y, z, the two tilts, the turn about z), and the quoted words. A load: a region, a force or a pressure, the value and unit as written, the quoted words, and for a force either a direction (x, y, z) or the word tension or compression. The schema lists the regions on offer and no other can be named.

**The guard** (`plate_guard`) keeps a support or a load only when:
- its region is on offer, and the quoted words name it ("the left edge", "the face", "the hole", "the top tab") or it is one of the regions clicked;
- its quote is in the message;
- a support names at least one of the six directions; a region is held once per message;
- a load's number is one the quote writes, in a unit of the plate's own system, converted to the list's unit as a coupon's row is (kN to N);
- a pressure acts on an area; a force names a direction.

**Tension and compression.** For a force stated as tension or compression the guard takes the direction and the sign from the edge: tension pulls along the edge's outward normal (Edge-Right +x, Edge-Left −x, Edge-Top +y, Edge-Bottom −y), compression pushes against it, whatever sign and direction the model wrote. On a region with no one outward normal (the face, a tab, the hole) it is refused with the reason.

**The card and the tick.** What is kept is shown in ADR-0088's card, one line per support and load in the plate's words ("Force on Edge-Top 10000 N along y", how it was written, that tension pulls outward), with what was dropped and why. Nothing enters the plate until the engineer applies it. Applied, the lines become rows of the Loads and supports panel, and the setup is checked with them, so the model on the page shows what is now held and loaded.

**"Here".** The element clicked on a plate's checked model is the project's, as one clicked on the results is. The page says under the conversation which regions "here" is. A new model lets the click go.

**The assistant's own check of a plate** now sends the plate's supports and loads.

**Not in this record.** A support that moves by a stated travel; a moment; a load on a drawn box; fixed patterns for a plate with no model on; picking before a model exists (a plate with no support has nothing to click, so the first support and load are named in words); the plate on the hosted tier (ADR-0089 keeps it hidden; its amendment 5 offers it to founder sign-ins).

## As built (2026-11-16)

- API: `api/src/anisotropy_api/plate_proposals.py` (`REGION_KINDS`, `DIRECTIONS`, `EDGE_NORMAL`, `PLATE_SYSTEM`, `plate_schema`, `plate_view`, `plate_guard`); `schemas.py` (`PlateOffer`, `OfferedRegion`, `SupportProposal`, `LoadProposal`, `ProposalRequest.plate`, `ProposalResponse.supports` and `.loads`); `assistant.py` (`propose` takes a schema and added instructions); `main.py` (`propose_rows`).
- Page: `lib/studio-plate.ts` (`ownRegions`, `regionsHere`); `lib/proposals.ts` (`plateOffer`, `plateLines`, `plateWith`); `lib/studio-api.ts` (`PlateOffer`, `SupportProposal`, `LoadProposal`, `readProposalAnswer`); `components/studio/coupon-chat.tsx` (the offer, the card's lines, the apply and its check, the "here" line); `components/studio/coupon-studio.tsx` (the preview's clicked element is the project's `picked`).
- Different from a first sketch: the model names directions by word (x, tilt_x) and the guard turns them into the plate's numbers, so the schema holds no number but a load's value.

## Why (evidence)

- `cd api && uv run pytest -q tests/test_plate_proposals.py`: 34 passed. The founder's sentence "hold this edge and add a 10 kN load in tension here", clicked on the top edge, is kept as a support on Edge-Top in x, y, z and a force of 10000 N along y; tension and compression on each of the four edges give the eight signs whatever the model wrote; each way a support or load can fail the guard is dropped with its reason; the regions, their kinds and the directions equal the form definition's `plate` block; a malformed offer is refused.
- `npx tsx --test tests/studio-plate.test.ts`: the offer holds the plate's own regions and no drawn box or value; the card's lines and the lists after a tick; the answer's shape.
- The browser scenario "a plate is held and loaded by talking" in `tests/browser/studio.spec.ts` passes with a stand-in model: regions named in words, the card, the apply, the check sent with the lists, an element clicked on the model, "here" sent with the next message.
- The real package, no stand-in: `ANISOTROPY_ALL_TESTS=on uv run python tools/studio_tool.py live` on a 100 × 100 mm plate with the lists the assistant enters (Edge-Bottom held in x, y, z; Edge-Top, 10000 N along y) solved with our kernel: the top edge moves +0.14 mm in y and the reactions sum to −10000 N in y, so the plate is pulled as "tension on the top edge" says. The same plate with no support wrote no preview.
- Whole suites at this commit: `npm test` 353 tests, 352 pass, 1 skipped; `npm run typecheck` clean; `cd api && uv run pytest -q` 478 passed, 112 skipped; the studio browser suite 41 passed.
- UNVERIFIED: no real model has read a plate's message. How well one reads supports, directions and "here" has no evidence yet.

## Consequences

- **Easier:** a plate's supports and loads are stated in a sentence, with a click for the place, and confirmed line by line. The same offer, guard and card can take the next kind of edit (a dimension from a picked edge).
- **Harder:** the plate's regions and directions are now named in three places that must agree (the form definition, the API's schema and guard, the page); a test ties the API's to the form definition's.
- **We now depend on** the model choosing the right region among those clicked. The card names the region on every line, and the engineer unticks a wrong one.

## How we will know it was wrong

- Engineers untick or correct the region or the direction on the card often (to be seen in run records once a real model reads plates).
- A support or a load enters a plate that neither the engineer's words nor the click hold. That would be a guard failure: add the case to `test_plate_proposals.py`.
- A force stated as tension pushes. `test_tension_pulls_along_the_edges_outward_normal_whatever_sign_the_model_wrote` and the real solve above are the checks.

## Amendment 1, 2026-11-16 (a plate that states no support or no load yet shows its shape to be clicked; not yet confirmed by the founder)

**Context.**
- This record left one gap: a plate with nothing held had no model on the page, so "hold this edge" could not be the first thing said. The founder's wish was to click an edge and tell the assistant what to do with it.
- The setup check built no model for such a plate: `intake.check_form` refuses a plate with no support, and `spec.py` requires at least one support and a load, so nothing reached the mesher.
- A plate's mesh follows its size, hole, tabs, drawn boxes and element size. No support and no load moves a node.
- Two things on the page stood in the way. The live preview was asked for only once a plate's tab length and loading rows were filled, and a plate has no loading rows and may have no tabs. And the assistant's open question "Who is running it?" took any message with no digit as the name, so "hold this edge" became the engineer's name.

**Options.**
1. **Build the plate's mesh with a stand-in for the list that is missing, and show it as a shape: nothing drawn for the stand-in, the setup still blocked (chosen).**
2. Let the spec and the form accept a plate with no support. Rejected: the rule that a plate is held and loaded is what keeps an unheld plate from being solved (ADR-0054, ADR-0003), and every reader of a spec would have to learn the exception.
3. Draw the plate in the page from its length and width, and find the clicked region there. Rejected: a hole's ring and a drawn box's elements come from the mesher, and the page would hold a second mesh that must agree with the first.
4. Leave it: the first hold and load are named in words. Rejected: it is the wish this record was written for.

**Decision.**
- **The shape.** For a plate whose supports or loads are not stated, `checks.plate_shape` builds the model with a stand-in for each missing list (`SHAPE_SUPPORT`: Edge-Bottom held; `SHAPE_LOAD`: a pressure on the Face), and only when nothing else about the plate is refused. `preview.shape_data` writes it as the preview with nothing drawn for a stand-in, `loaded` null when no load is stated, and `shape` naming the missing lists. A list the plate does state is drawn as stated.
- **Nothing else changes.** The checklist is the real form's: blocked, with its own reason. A shape is never solved, kept, recorded or written to a deck. A hidden plate (ADR-0089) shows no shape.
- **The page.** `readPreview` takes a preview with no load only when it is a shape. Under the model the page says what is still missing ("Nothing is held or loaded yet. This is the plate's shape: it cannot be solved until it is held and loaded."). A click on the shape is "here", as on the checked model.
- **When it is asked for.** On a plate the live preview no longer waits for a tab length or for loading rows (`missingIn`), so the shape appears once the size, material and layup are stated, and again after each hold or load.
- **A plate edit is not a name.** At "Who is running it?", on a plate read by a model, a message that names an action on a region, a kind of region, a load or the place clicked goes on to be read (`studio-plate.namesPlateEdit`); any other message with no digit is the name, as before.

**Evidence.**
- `cd fea && uv run pytest -q tests/test_plate_shape.py`: 9 passed. A plate with nothing held or loaded stays blocked and shows its mesh and regions with nothing held and no load; its mesh, node sets and element sets equal those of the same plate with its lists stated; a stated list is drawn and only the missing one is stood in; no shape for another test, for a plate refused for another reason, or for a hidden plate; `studio_tool.py check` and `live`, each as its own process, write the shape as the preview and no result file. The whole suite (`uv run pytest -q tests ../engine/tests`): 1574 passed, 43 skipped, 3 failed and 1 error, the four that need Gmsh, which this machine does not have (they fail the same way without this change).
- `npm test`: 355 tests, 354 pass, 1 skipped; `npm run typecheck` clean. `tests/studio-plate.test.ts`: a shape is read with no load and a model with no load is refused; the element clicked on the shape names the same regions as on the checked model; a plate edit is told from a name. `tests/studio-live.test.ts`: a plate is complete without a tab length or loading rows, and a strip is not.
- The studio browser suite: 42 passed. New: "a plate with nothing held shows its shape, and the first hold is the edge clicked", with a stand-in model and the package's answer played: the shape appears with its line, an element on an edge is clicked, "hold this edge" is sent with that edge as `here` while "Who is running it?" is open, the card holds that edge, and applying sends the check with it. The older plate scenario's click now waits for the scene to draw.
- By hand on 2026-11-16, the real tool: `studio_tool.py check` and `live` on a 100 × 100 mm plate with no support and no load wrote `preview.json` with 256 elements, `shape: ["supports", "loads"]`, nothing held and no load, the checklist blocked on "Supports: required for a plate"; with the switch off, no preview.
- UNVERIFIED: not deployed, so not tried on the live site; no real model has read "hold this edge" with a click.

