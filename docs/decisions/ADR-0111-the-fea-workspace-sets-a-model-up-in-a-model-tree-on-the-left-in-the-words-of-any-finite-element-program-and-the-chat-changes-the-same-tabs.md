# ADR-0111: The FEA workspace sets a model up in a model tree on the left, in the words of any finite element program, and the chat changes the same tabs

- Status: Proposed
- Date: 2026-11-18
- Decided by: Founder, 2026-11-17, looking at the live tension screen ("Material and layup", "Change settings", "Model settings", "Files"): "where are those settings on the left think of the abaqus GUI how the settings on the left, with tabs of geometry, boundary conditions, etc ... need the software to be as intuitive as possible ... the chat helps with making changes say if i want to change the boundary condition of a side, face etc the AI helps with that"; then "its not an abaqus style panel but more of an FEA style panel, because ansys will also get imported through our software" | Drafted by: Claude Code
- Related: [ADR-0090](ADR-0090-a-tension-coupon-is-built-from-its-material-and-layup-and-the-standard-and-the-software-choose-the-rest-and-say-so.md) (the tension screen this lays out again); [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (one panel per step, the assistant beside it); [ADR-0110](ADR-0110-abaqus-setup-words-are-answered-from-a-fixed-glossary-on-the-page-and-every-boundary-condition-and-load-is-drawn-on-the-model-and-listed-under-it-before-and-after-a-run.md) (the glossary and what is applied; amendment 1 makes the glossary solver-neutral); [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md) (no program named); [ADR-0105](ADR-0105-a-model-brought-in-as-an-abaqus-input-file-is-read-as-it-stands-solved-by-our-kernel-and-asked-about-nothing-in-it-is-changed-and-nothing-of-it-is-kept.md) (an imported model); [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md) (changes by talking); `lib/model-tree.ts`, `components/workspace/tension-screen.tsx`, `components/workspace/panels/step-panel.tsx`, `components/studio/coupon-chat.tsx`, `components/studio/scene-canvas.tsx`, `lib/fea-terms.ts`
- Area: website, assistant

## Context

- The product's view of the FEA workspace (the switch of ADR-0089 off: customers and founders) was the tension screen of ADR-0090: "Material and layup" with two choices, a "Change settings" panel holding the size, the loading and the mesh, "Model settings" listing what the software chose, and "Files". Boundary conditions, the analysis step and the mesh had no place of their own; the founder could not find where a setting lives.
- Engineers set a model up in a finite element pre-processor: a tree on the left, one branch per part of the analysis, in the order it is built (geometry, material and section, step, boundary conditions, loads, mesh, job, results). The founder asked for that, with the assistant changing the same settings, and for it to be no one program's: models written by Abaqus come in today (ADR-0105) and Ansys models are to come.
- ADR-0090 chose the short screen on 2026-11-11 ("Two choices + chat"). Its rule stands: the screen sends only the rows the engineer may change, and the fea package chooses every other row and says why. A coupon's grips are not a row of the screen: the blank form's grip kind is the Excel form's ("coupling"), and the package chooses clamped grips ("nodal") for the screen.
- The glossary of ADR-0110 knew one program's names only (`lib/abaqus-terms.ts`).

## Options considered

1. **A model tree on the left in general FEA words, ten tabs from the test to the results, each holding its rows, the checklist items that judge them and the software's choices for it; the chat changes the same rows and opens the tab it changed (chosen).** The engineer sees the whole setup in the order of any pre-processor, and what the chat does lands where it can be seen. The tree is longer than the two-choice screen, so the tabs that need nothing start closed with their values in one line.
2. **Keep the screen of ADR-0090 and rename its panels.** Rejected: boundary conditions, the step and the mesh would still have no place, which is what the founder could not find.
3. **The development view's panels (ADR-0062) for everyone.** Rejected: about ninety rows, most of them with one right answer for a D3039 coupon, the reason ADR-0090 was made.
4. **A tree in one program's words and layout (its module names, its icons).** Rejected by the founder ("not an abaqus style panel"): Ansys models are to come in, and the product names no program (ADR-0091).

## Decision

- **The tabs.** Test, Geometry, Material, Layup, Analysis step, Boundary conditions, Loads, Mesh, Solve, Results, numbered in that order (`MODEL_TREE`). Each tab holds the rows of the screen it edits, once; the checklist items that judge them give its badge; the rows the package chose for it are listed in it under "Chosen for you" with their reason. A closed tab says its values in one line ("250 × 25 mm, 56 mm tabs", "1 mm pull", "4 mm elements, 300 in all"). Run analysis heads the tree. The rows sent are those of ADR-0090, unchanged.
- **What a coupon's tabs hold.** Analysis step: one static linear step, said, not changed. Boundary conditions: the coupon's two, in the words under the model ("Bottom grip: fixed (encastre)"), set by its test and changed by no row. Loads: the load in the same words, then the loading type and value, a blank row saying what stands for it ("displacement, chosen for you").
- **The tree and the model.** While Boundary conditions or Loads is open, the model draws that part's sets with heavier frames, before and after a run.
- **The tree and the chat.** A change made by talking, by the page's patterns or a model's proposal, opens the tab that holds the row and marks it for a moment. The chat's links to fix an item or to edit open the tab, by the same lookup.
- **No program's words.** The tab names are general FEA words; the glossary (ADR-0110 amendment 1) answers each program's name for a setup word with one answer.
- **Not in this record.** Boundary conditions on any edge or face of a plate (ADR-0101) on the product's view is the founder's choice, asked on 2026-11-17 and not yet answered; until then the plate stays where ADR-0089 amendment 6 put it.

## As built (2026-11-18)

- `lib/model-tree.ts`: `MODEL_TREE`, `tab`, `TAB_OF_STEP` (the chat's steps to tabs), `tabOfKey`, `tabToFix`, `tabState`, `builtFor`, and the one-line values `sizeLine`, `loadLine`, `meshLine`.
- `components/workspace/tension-screen.tsx`: the screen as the tree (`data-testid="tension-screen"` kept), each tab a `StepPanel`, "Chosen for you" per tab (`defaults-<tab>`), the lists `tree-conditions` and `tree-loads` from `appliedOf` (ADR-0110). `components/studio/coupon-form.tsx`: a blank list row with a value in use says it.
- `components/workspace/panels/step-panel.tsx`: `onToggle`, and `revealPanel` (open, bring into view, mark for 1.8 s, class `ws-panel-changed`). `components/studio/project-context.tsx`: `emphasis`, shared by the tree and the model; `scene-canvas.tsx` draws it (`data-emphasis` on the canvas).
- `components/studio/coupon-chat.tsx`: `reveal` after a change by patterns or by a proposal; the fix and edit links open tabs of the tree on the product's view; "Change settings" in the chat is now "Edit the model".
- `app/workspace/workspace.css`: the tree's head, its lines and "Chosen for you", the mark.
- Different from the plan: the Boundary conditions tab has no grip row. Sending the blank form's grip kind would change the package's choice for the screen (Context), so the tab says the grips' and lists the package's choice.

## Why (evidence)

- `npm test`: 421 tests, 420 pass, 1 skipped, 0 fail. New `tests/model-tree.test.ts` (4: the tabs in order, every row the screen sends and every choice shown in exactly one tab, no program named; a row, a failing item and a choice found in their tab; a tab's state the worst of its items; the one-line values from the rows given or chosen, in mm and in inches). `npm run typecheck`: clean.
- Browser (`playwright.studio.config.ts`), each passed on its own on a fresh build: the tension scenario of ADR-0090 with the choices read from their tabs and the status "under Results"; new, "the setup is a model tree in the words of any finite element program; a tab lights its part of the model and a change in the chat opens its tab" (the ten titles in order, no program and no "Change settings" on the screen; "use 4 mm elements" opens and marks Mesh and sends 4; Boundary conditions open sets `data-emphasis="conditions"` and lists both grips; Loads lists the pull; the loading row says "displacement, chosen for you"). The whole suite on the final build: see the pull request.
- Pictures at twice the screen's scale: `.local/website/screenshots/model-tree-*.png`.
- UNVERIFIED: not deployed; the founder has not used the tree; no engineer has said whether it reads as a pre-processor.

## Consequences

- The setup of the product's view reads like any pre-processor, and a change by talking shows where it went.
- The tree is longer than the two-choice screen; the closed tabs keep it to one line each.
- A new kind of model (a plate, an imported model) needs its own tabs' contents; the tab names stay.

## How we will know it was wrong

- The founder or an engineer still asks where a setting is, or opens the wrong tab for it.
- A change made by talking does not open the tab that holds it, or opens another.
- Engineers coming from another program do not recognise a tab's name.
