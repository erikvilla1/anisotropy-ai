# ADR-0062: The chat becomes a workspace product: a solver-independent project, three columns, one panel per step, the assistant beside it

- Status: Proposed
- Date: 2026-11-06
- Decided by: Founder, 2026-11-06 ("it should be different options so like FEA, or Laminate response, then later, STL, etc. Right now everything seems clunky, everything is clustered"; "might need to refactor anisotropy chat around a persistent solver independent project model"; "refactor it to where the 3D model viewer is active, where the user has the project setup panel, then a geometry editor with live edits happening on the side, composite layup editor, loads/BCs, mesh settings, model validation panel then the run analysis then with everything outputted there for one to download like before"; "The layup code, material code, is confusing, any user will just put anything"; "needs to feel like another CAD/FEA software. We are following PhysicsX type of platform but for composites"; and, on the choices asked: three columns like PhysicsX, names derived with a free project name, CAD as a placeholder tile, the full form kept as an Advanced panel, the route `/workspace`, free project names with the Date row hidden, one pull request per part) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md) (amendment 1), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (amendment 6), [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0054](ADR-0054-a-plate-kind-states-supports-and-loads-as-lists-over-named-regions-and-the-studio-lets-the-user-click-a-region.md), [ADR-0055](ADR-0055-the-studio-opens-on-a-guided-chat-that-fills-the-same-form-rows-and-the-full-form-stays-one-click-away.md) (amendment 3 superseded in part), [ADR-0058](ADR-0058-one-name-anisotropy-five-service-pages-under-a-services-menu-the-calculator-on-the-home-page-and-a-contact-page.md), [ADR-0059](ADR-0059-the-engine-describes-the-stack-and-evaluates-first-ply-failure-on-the-response-endpoint-for-the-home-calculator.md), [ADR-0060](ADR-0060-the-chat-solves-laminate-problems-through-the-case-solver-with-every-value-in-its-own-unit.md), [ADR-0061](ADR-0061-a-coupon-is-stated-in-the-unit-system-the-engineer-picks-and-its-decks-stay-in-the-deck-system.md); `lib/project-store.ts`, `components/studio/project-context.tsx`, `components/studio/use-coupon-run.ts`, `tests/project-store.test.ts`; risks R-12, R-20, R-23

## Context

`/chat` opens on one question whose answers are the coupon tests and "Laminate response" (ADR-0055 amendment 3). The guided chat fills the rows of the one values file (ADR-0046 amendment 3), the full form shows them all, and the viewer draws the package's preview after a check and its fields after a run (ADR-0051). The founder tried it on 2026-11-06, typed "coupon" and read "I could not read a coupon value in that" three times: the chat reads fixed coupon phrases and the word named no value.

What the code held that day (`origin/main` 924d5ff): the check, solve, poll and read-the-files logic written twice, in `components/studio/coupon-chat.tsx` and `coupon-studio.tsx`; each tab owning its rows and its run, so switching tabs unmounted the other and lost its conversation, check and results; nothing drawn before a check; and the coupon's name built from a Material code and a Layup code the engineer typed (ADR-0038), the chat asking for the material code in its last step, and the example form pre-filling `IM7`, which fails the check for any other material.

The founder wants what an engineer expects of CAD or FEA software, in the style of PhysicsX: a persistent project that is not the solver's input file, a workspace per kind of work (coupon finite elements, laminate response, later geometry from CAD files), the 3D viewer always on, panels for the project, the geometry with live edits, the layup, the loads and supports, the mesh, the validation, the run and the outputs, with the assistant beside them. The CalculiX and Abaqus workflows are not in question.

What binds the design: the browser computes no number (ADR-0001; drawing typed geometry and plies without numbers is allowed, as the home page draws the typed stack, ADR-0059); no silent defaults (ADR-0003); one values file and one definition JSON with a form version (ADR-0046 amendment 3); a code means one thing (ADR-0038); the checklist, the preview and the fields come from the fea package and a failing setup never runs (ADR-0051); supports and loads are lists over named regions (ADR-0054); the unit system is fixed once a number is typed (ADR-0061).

## Options considered

1. **Keep the chat as the one surface and put the panels inside its messages.** The conversation stays the spine; the viewer stays a side bench. Rejected: it is what the founder called clustered, and a panel in a scrolling message cannot be the place an engineer returns to.
2. **A page per tool, each with its own state, as before amendment 3.** Rejected: the rows, the check and the results would again live in one component each; the founder asked for one persistent project.
3. **A workspace shell with a project store shared by the panels, the viewer and the assistant.** The project holds the rows and a name; its run (the check, the job, the files) is kept once; the panels edit named rows of the same values file; the viewer draws a sketch of the typed rows before a check, the package's preview after it and its fields after a run; the assistant reads and writes the same store and points at the panel that asks for what it could not read. Chosen.
4. **A rewrite on a new front-end stack.** Rejected: the viewer, the results panels, the form renderer, the plate panel, the checklist, the readers of the API and the browser tests exist and are kept.

## Decision

Option 3, delivered one pull request per part, the site working after every merge:

1. **Records, project store, naming** (this record; ADR-0038 amendment 1; ADR-0046 amendment 6). `lib/project-store.ts` is the project: an id, a kind, a free name, the rows, a plate's lists, two stamps; pure, so its tests run in Node. `components/studio/project-context.tsx` holds one project and one run for everything under it and keeps the newest twenty in this browser under `anisotropy.projects.v1`, so a reload picks up where the engineer left off until the server store exists. `components/studio/use-coupon-run.ts` is the one copy of the check, the solve, the polling and the reading of the files. The codes in the coupon's name are derived when blank and no longer asked for.
2. **Shell, chooser, routes.** `/workspace` lists the projects and three tiles, Coupon FEA, Laminate response and CAD (planned); `/workspace/fea`, `/workspace/laminate`, `/workspace/cad`; `/chat`, `/chat/view`, `/studio` and `/studio/view` redirect with their query. Three columns: the panels on the left, the viewer in the centre, the assistant on the right, collapsible; drawers below 1100 px. ADR-0058 amendment 1 moves the frozen routes.
3. **The step panels and the sketch.** Project, Geometry, Layup and material, Loads and BCs, Mesh, Validate, Run, Outputs, and Advanced (every row, the old full form), each editing named rows and showing its checklist items; `lib/studio-sketch.ts` draws the typed rows as a sketch labelled "not meshed" until the check brings the mesh.
4. **Viewer quality** (its own record, ADR-0063): presentation lighting for the model, unlit contours on the graphics card for the results, the legend's range written by the package.
5. **The assistant column and the laminate workspace.**
6. **The server project store**: a `projects` table and `jobs.project_id`, after the per-user limits of ADR-0056's stage 5.
7. **Docs and cleanup.**

Hidden from the engineer's path: `filled_by` (the run's name), `date` (today, in the file only), `material_code` and `layup_code` (derived; overrides on the Advanced panel), `team_model`, `test_data` and the Abaqus names.

## As built (2026-11-06, part 1)

`lib/project-store.ts` (`newProject`, `reduce`, `readProjects`, `writeProjects`, `upsert`, `projectTitle`), `components/studio/project-context.tsx` (`ProjectProvider`, `useProject`: the rows, the plate lists, the name, `restored`, and the run), `components/studio/use-coupon-run.ts` (`useCouponRun`: `check`, `solve`, `clearChecked`, `clearResults`, `reset`, the polling and the files; `loadedJob` fires once per job so the chat can post its result message). `StudioModes` wraps the tabs in the provider; `CouponChat` and `CouponStudio` lost their own rows and run state and the duplicated logic. The chat's last step asks for the name only; `lib/studio-form.ts` no longer pre-fills `IM7`; `stepOfKey` returns null for the codes (the full form has them). `intake.designation_for` derives a blank material code (`derived_material_code`): the library id without punctuation when that code is free, `M<n>` otherwise and for own constants. Parts 2 to 7 are not built.

## Why (evidence)

- The founder's words of 2026-11-06, quoted above, and his answers to the four choices.
- Part 1: `cd fea && uv run pytest -q tests/test_intake.py tests/test_checks.py tests/test_values_input.py tests/test_coupon.py tests/test_studio_tool.py`: 104 passed (AS4/8552 without a code names itself `AS48552-UNT-L1`, own constants `M1-UNT-L1`, the hand codes IM7 and L1 reused, the clashes still refused); `npm test`: 142 passed (`tests/project-store.test.ts`: the reducer stamps every change, the newest project first under one key, a corrupt or blocked storage reads as nothing); `npm run typecheck`: clean; `npx playwright test --config playwright.studio.config.ts`: 11 passed, unchanged scenarios but the name step, which asks for the name alone; `STUDIO_LIVE=1 npx playwright test --config playwright.studio-live.config.ts`: 1 passed (1.2 min), the example coupon checked and solved from the form tab with its codes derived or reused.
- Parts 2 to 7: no evidence yet.

## Consequences

Easier: one place for the rows and the run, so the chat, the form and later the panels cannot disagree; a reload keeps the project; an engineer never types a code; a new capability is a workspace tile with its own panels and endpoint. Harder: every browser scenario of `tests/browser/studio.spec.ts` changes ids or routes across parts 2 to 5; a live geometry edit is a sketch until the check meshes it (2 to 4 s), and a debounced auto-check would meet R-23; three columns need about 1280 px. We now depend on the project store being the one state the panels read, and on the fea package writing every number the panels and the viewer show.

## How we will know it was wrong

- Engineers still reach for the full form or the Excel form instead of the panels, or ask what the designation means after the project name is theirs.
- The sketch is read as a mesh, or a number appears on the page that the package did not write.
- The panels need state the project store does not hold, so a panel keeps its own.
