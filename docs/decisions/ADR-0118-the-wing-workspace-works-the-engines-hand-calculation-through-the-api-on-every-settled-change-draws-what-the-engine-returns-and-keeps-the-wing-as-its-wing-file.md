# ADR-0118: The wing workspace works the engine's hand calculation through the API on every settled change, draws what the engine returns, and keeps the wing as its wing file

- Status: Proposed
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

## Decision

The wing workspace at `/workspace/wing`, the third tile of `/workspace`, sends the wing file's description to `POST /v1/wings/analyze` once the typing settles (350 ms) and shows what comes back: the report of ADR-0115 and the engine's drawing data. The page computes nothing. A value that is not a number is not sent, and an input the engine refuses keeps the last answer on the page, marked as the last wing that could be worked. The wing is kept in this browser and saved and opened as a wing file; the file is read by the engine, not by the page. The STEP download, the CalculiX check, a saved wing project and the chat input are later slices.

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
- The tile shows for every signed-in person; it is not hidden for founders only.

## Why (evidence)

- `cd engine && uv run pytest tests/test_wing.py`: 63 passed, two of them the drawing data (2026-11-19).
- `cd api && TEST_DATABASE_URL=… uv run pytest tests/test_wings_api.py`: 14 passed (2026-11-19). The API's results equal the engine's; JSON and TOML give the same answer; refusals are 422 and recorded; the browser tests' answer is the API's; the file the page saves reads back as the example.
- `npx tsx --test tests/wing.test.ts`: 4 passed; `npm test`: 430 passed, 1 skipped (2026-11-19).
- `npx playwright test --config playwright.studio.config.ts wing.spec.ts workspace.spec.ts`: 7 passed on Chromium (2026-11-19).
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
