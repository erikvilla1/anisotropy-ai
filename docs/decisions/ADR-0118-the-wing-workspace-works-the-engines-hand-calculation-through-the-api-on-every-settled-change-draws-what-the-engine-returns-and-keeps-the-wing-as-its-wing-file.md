# ADR-0118: The wing workspace works the engine's hand calculation through the API on every settled change, draws what the engine returns, and keeps the wing as its wing file

- Status: Proposed; the wing is kept as a project of kind `wing`, with its versions, since [ADR-0122](ADR-0122-a-wing-is-a-project-of-its-own-kind-kept-like-a-coupon-or-a-laminate-with-its-versions-in-the-browser.md) (option 5 (b)); the wing is a kind of FEA work, opened from the FEA section, since amendment 1; a wing file is refused in an engineer's words and takes at most 1,000 ribs, since amendment 2
- Date: 2026-11-19
- Decided by: Founder, 2026-11-18 ("Start step 1", his choice on the seven-step plan whose step 4 is the page); 2026-11-19 ("Fix hand calc skins, then page", his choice on what came after step 3) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md), [ADR-0060](ADR-0060-the-chat-solves-laminate-problems-through-the-case-solver-with-every-value-in-its-own-unit.md), [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), `engine/src/anisotropy_engine/wing/wing_file.py` (`wing_views`), `api/src/anisotropy_api/main.py` (`analyze_wing_endpoint`), `api/tests/test_wings_api.py`, `lib/wing.ts`, `components/workspace/wing-*.tsx`, `tests/wing.test.ts`, `tests/browser/wing.spec.ts`, `scripts/wing-choices.py`
- Area: website, api, engine

## Context

Step 4 of the wing generator is the page: a wing's inputs on the left, its answer in the centre, updated within about a second of a change, with a drawing of the wing and of its box section, and the assistant beside them, in the three columns of the workspace (ADR-0062). The hand calculation of ADR-0115 is Python in the engine; it works every flight case of a wing file at once, the example's 34 in about 0.1 s on a development machine. A wing is stated by its wing file, a TOML description the engine reads by `wing_from_dict`. The workspace keeps a coupon or a laminate as a project in the `projects` table, whose kinds are fixed by a check constraint (`api/src/anisotropy_api/records.py`, `projects_kind_known`); a wing is not one of them. The step-4 plan also names a STEP download and a CalculiX check, both of which take seconds to minutes.

## Options considered

1. **Where the numbers come from.**
   - (a) One API address, `POST /v1/wings/analyze`, that runs the engine on the description. Chosen: one engine computes every number (ADR-0001).
   - (b) The hand calculation ported to TypeScript. Rejected: two codes to keep equal, and the page would compute numbers.
   - (c) The engine in the browser through Pyodide. Rejected: NumPy, SciPy and the engine download before the first answer, and the material library loads twice.
2. **When it is worked.**
   - (a) Once the typing settles, 350 ms after the last change, with an older answer dropped when a newer one is asked for. Chosen: the engine takes a tenth of a second, so a settled change is answered within the second the plan asked for.
   - (b) A Solve button. Rejected: the plan asked for the answer to follow the inputs.
   - (c) Every keystroke. Rejected: a request a keystroke, most of them for half-typed numbers.
3. **What the page sends.**
   - (a) The wing file's description as JSON, or a wing file's text. Chosen: the engine's own reader decides what is valid, and the description is what the page saves.
   - (b) A schema of typed fields for the API. Rejected: a second description to keep in step with the engine's.
4. **What the page draws.**
   - (a) Drawing data from the engine, `wing_views`: the airfoil, the walls of the box, the spars, the ribs, the shear center, the centroid and each case's margins along the span and loads at the root, rounded to four significant digits for drawing only. Chosen: the page computes no number, and what it draws is the section the engine worked.
   - (b) The page draws the airfoil and the walls from the description. Rejected: the airfoil and the box would be computed twice, in two languages.
5. **Where the wing is kept.**
   - (a) In this browser's storage, and as a wing file the person saves and opens. Chosen for this step.
   - (b) A project of kind `wing` in the `projects` table, listed with the others. Later: it needs a migration of the constraint and the project store's kinds, and the wing file already carries everything.
   - (c) Nowhere. Rejected: a reload would lose the work.
6. **What is recorded.** Every call is a run record (ADR-0026): the description as the inputs and a summary (passes, the governing check, the design, the cases run and waiting) as the result. The drawings are not kept: they are the engine's to redraw from the description.
7. **Units.** The answer is in the wing file's own units, SI or US, as the engine reports it; no toggle on the page yet.
8. **The STEP file.**
   - (a) A second API address, `POST /v1/wings/shape`, that reads the description by the engine's rules and runs the fea package's `wing_shape` (ADR-0116) in a process of its own, as the coupon tools run. Chosen: the hosted image already holds the fea environment with Gmsh, and the example builds in under half a second.
   - (b) A job in the queue, like a coupon run. Rejected: a job is for minutes of work; this is less than a second.
   - (c) The shape built in the browser (OpenCASCADE compiled to WebAssembly). Rejected: tens of megabytes to download, and a second builder to keep equal to the first.

## Decision

The wing workspace at `/workspace/wing`, the third tile of `/workspace`, sends the wing file's description to `POST /v1/wings/analyze` once the typing settles (350 ms) and shows what comes back: the report of ADR-0115 and the engine's drawing data. The page computes nothing. A value that is not a number is not sent, and an input the engine refuses keeps the last answer on the page, marked as the last wing that could be worked. The wing is kept in this browser and saved and opened as a wing file; the file is read by the engine, not by the page. Download STEP, in the last panel, sends the same description to `POST /v1/wings/shape`, saves the STEP file and lists each part's thickness, which a STEP file cannot hold. The finite element check, a saved wing project and the chat input are later slices.

## As built (2026-11-19)

- Engine: `wing_views(result, units)` in `engine/src/anisotropy_engine/wing/wing_file.py`; `WingGeometry.rib_stations_m`, used by the shape of ADR-0116 too.
- API: `WingRequest` and `WingAnswer` in `api/src/anisotropy_api/schemas.py`; `analyze_wing_endpoint` in `api/src/anisotropy_api/main.py`, a refusal answered with 422 in the engine's words and recorded.
- Website:
  - `lib/wing.ts`: reading and writing values, the wing file writer, the answer in words.
  - `lib/wing-choices.json`, written by `scripts/wing-choices.py`: the example, and the library materials and cores the page offers.
  - `components/workspace/wing-context.tsx`: the state, the settle and the browser's copy.
  - `wing-rail.tsx`: Wing file, Geometry, Material, Layup, Loads, Aerodynamics, Boundary conditions and Solve.
  - `wing-stage.tsx`: the answer, the wing from above coloured by margin, the margins along the span, the section coloured by shear flow or spanwise load, the design and the cases.
  - `wing-assistant.tsx`: what governs and what usually raises it, in words with no number.
- The STEP file: `wing_shape_endpoint` in `api/src/anisotropy_api/main.py` runs `wing_shape_command()` (`coupon_jobs.py`) on the description written as JSON; `anisotropy_fea.wing_shape` reads a `.json` description, writes the part table with `--parts` in the file's units, and ends a refusal with status 2 and its reason. The page's Shape for CAD panel (`ShapePanel` in `wing-rail.tsx`) saves the file and lists the parts. A second STEP file written in one process names its products `… 2.<k>`; `name_step_products` now reads any counter.
- The tile shows for every signed-in person; it is not hidden for founders only.

## Why (evidence)

- `cd engine && uv run pytest tests/test_wing.py`: 63 passed, two of them the drawing data (2026-11-19).
- `cd api && TEST_DATABASE_URL=… uv run pytest tests/test_wings_api.py`: 14 passed (2026-11-19). The API's results equal the engine's; JSON and TOML give the same answer; refusals are 422 and recorded; the browser tests' answer is the API's; the file the page saves reads back as the example.
- `npx tsx --test tests/wing.test.ts`: 4 passed; `npm test`: 430 passed, 1 skipped (2026-11-19).
- `npx playwright test --config playwright.studio.config.ts wing.spec.ts workspace.spec.ts`: 7 passed on Chromium (2026-11-19).
- The STEP file: `cd api && uv run pytest tests/test_wings_api.py`: 19 passed, one of them building the example's shape through the fea package; `cd fea && uv run --extra mesh pytest tests/test_wing_shape.py`: 15 passed; the browser's Download STEP and a check that the page names no tool: `wing.spec.ts` 6 passed (2026-11-19). On the local page the example's STEP file, 9 parts named, came back in 0.48 s.
- Timing on a development machine, 12 calls with the example wing: the engine 0.12 s, the whole request 0.15 s median, 0.17 s at most; the answer is 174 kB.
- A private wing file opened in the page gave the same margins as the command-line calculator (numbers kept off the repository, ADR-0042).
- The hosted request time is not measured yet: UNVERIFIED.

## Consequences

- The page needs the API: with the analysis service down it says so and keeps the last answer.
- Every settled change is a request and a run record, so a wing's session writes many records; the drawings are not among them.
- The wing is not listed in "Your projects", and another browser does not see it until the file is opened there.

## How we will know it was wrong

- The hosted request takes more than a second at the median for the example wing.
- People lose wings they did not save as files, or the founder asks for the wing among the projects: then a `wing` project kind replaces the browser's copy.
- The run records from wings crowd out the others in the history or the database's free tier.

## Amendment 1, 2026-11-20 (the wing is a kind of FEA work, opened from the FEA section; drafted, not yet confirmed by the founder)

**Context.** ADR-0124 (PR #249, merged 2026-11-20 as 2dc6577) gave the workspace three sections, FEA, CAD and Laminate, on the founder's words "it should be only FEA, CAD, then Laminate for right now on the bottom 3", with FEA opening blank and the chat setting it up when the user says, in his example, "you know what I want to start a wing analysis". The wing had its own tile on this branch (ADR-0122); the three sections leave no place for it. ADR-0124 left the wing for this branch to join "by the same `analysis` field".

**Options.** (a) An FEA project with `analysis: "wing"`, the wing description inside it, worked on the FEA page: rejected for now, since the wing page (this record) has its own three columns, the panels of ADR-0125 and its own versions (ADR-0122), and moving them into the coupon's page is a rewrite with nothing for the user. (b) Keep the wing tile beside the three sections: rejected, it is the fourth tile the founder took away. (c) Keep project kind `wing` and its page, now a page of the FEA section: chosen.

**Decision.** The wing is the second kind of FEA work, "Wing analysis", beside "Coupon test" (`FEA_KINDS` in `lib/workspaces.ts`, with its page `WING_HREF`). It is set up from the FEA section: the kind's button on the blank FEA page, the start box or the FEA chat's words ("start a wing analysis", read by `readIntent`, routed `set-up` by `routeStart`), or the coupon chat's words, which ask first when the coupon holds work (the `section` route, `SwitchAsk`). Setting it up opens the newest wing when it holds no work (differs from the example), else a new wing from the example, on the wing's page (`goTo` in `components/workspace/go-to.ts`). No message is carried to the wing page, which has no chat yet (step 5 of the wing plan). The project stays of kind `wing` in storage; the list and the page's header name it "FEA · Wing analysis", and a wing in the list opens its own page.

**Evidence.** `tests/work-intent.test.ts` (FEA kinds coupon and wing), `tests/project-store.test.ts` (a new wing holds no work, a renamed one does), the question bank `tests/assistant-questions/sections.json` (the two wing questions now open the wing, one of them asking first), `tests/browser/wing.spec.ts` (the FEA tile, the kind's button, the start box and the FEA chat all reach the wing page) and `tests/browser/workspace.spec.ts`. Results are in the pull request.

## Amendment 2, 2026-11-25 (a wing file is refused in an engineer's words whichever record refuses it, and a wing takes at most 1,000 ribs; drafted, not yet confirmed by the founder)

**Context.** On the founder's word of 2026-11-24 after his team's feedback, "the most important part is that our software works, work on step patch, and wing analysis", 820 wing and repair files with one value changed (zero, negative, huge, text, missing, another unit) were read by the engine. None crashed. Of the 414 wing files, 326 were refused, 202 of them in the validation library's own text, which the page shows as it is: "1 validation error for WingGeometry", our class and field names, "[type=greater_than, input_value=...]" and a web address. A rib spacing of a thousandth of a millimetre on a 2 m half span asked for two million ribs, and the hand calculation did not return.

**Options.** For the words: (a) the reader turns a record's refusal into "`[table] key must be ...`" in the file's own names, and keeps the sentence where a record already wrote one: chosen. (b) Rewrite every record's checks as sentences of our own: rejected, every check stated twice. (c) Have the page reword what it shows: rejected, the MCP server and the command line read the same refusal. For the ribs: (a) a limit in the description, 1,000 ribs: chosen; every rib is a station of the hand calculation, a part of the shape and a row of the mesh, and no wing of the kind this page takes has a tenth of that. (b) A time limit on the route: rejected, the engineer would learn only that it took too long.

**Decision.** `engine/src/anisotropy_engine/wing/wing_file.py`: `plain_refusal` and the reader's `_in_words` state a record's refusal by the file's table and key, with the key's unit ending left off ("`[geometry] chord must be greater than 0`"); a speed, an altitude or a stack that is not a number or a list is refused by its place. `description.py`: `MOST_RIBS = 1_000`, refused with "use a longer rib spacing, and check the units of both". No number of a wing that was accepted changes.

**Evidence.** `cd engine && uv run pytest tests/test_wing.py`: thirteen refusals word for word, no refusal in the library's words with every value of the example made zero, negative, text, empty and absent in turn, and the rib limit; results are in the pull request.
