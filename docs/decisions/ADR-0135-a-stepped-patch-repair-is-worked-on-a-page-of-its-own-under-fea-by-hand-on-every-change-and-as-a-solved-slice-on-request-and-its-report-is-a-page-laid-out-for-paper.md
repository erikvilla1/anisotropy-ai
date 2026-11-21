# ADR-0135: A stepped patch repair is worked on a page of its own under FEA, by hand on every change and as a solved slice on request, and its report is a page laid out for paper

- Status: Proposed
- Date: 2026-11-21
- Decided by: Founder, 2026-11-21 ("Start slice 4", his choice on the card "Start slice 4, the repair's page and report?") | Drafted by: Claude Code
- Related: [ADR-0130](ADR-0130-a-bonded-repairs-hand-calculation-is-the-stepped-lap-as-a-shear-lag-model-in-the-engine-the-patchs-force-at-every-step-boundary-the-adhesives-elastic-limit-and-the-long-overlap-strength-of-a-yielding-adhesive.md), [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md), [ADR-0132](ADR-0132-a-repairs-slice-is-solved-in-calculix-as-a-plane-of-eight-node-elements-held-flat-with-the-laminates-far-field-width-strain-and-its-bondline-and-plies-are-read-back-as-means-by-the-engine.md), [ADR-0118](ADR-0118-the-wing-workspace-works-the-engines-hand-calculation-through-the-api-on-every-settled-change-draws-what-the-engine-returns-and-keeps-the-wing-as-its-wing-file.md), [ADR-0119](ADR-0119-a-wings-finite-element-check-runs-from-the-wing-workspace-as-a-background-job-like-a-coupon-run-and-sets-the-model-beside-the-hand-calculation.md), [ADR-0124](ADR-0124-the-workspace-has-three-sections-fea-cad-and-laminate-fea-opens-blank-and-the-chat-sets-it-up-for-the-work-asked-for.md), [ADR-0134](ADR-0134-the-fea-workspace-is-the-model-across-the-window-with-the-chat-full-height-on-the-right-and-a-results-card-under-the-model.md), [ADR-0112](ADR-0112-a-coupon-report-carries-no-code-of-ours-the-coupon-is-worked-by-hand-with-its-own-numbers-in-its-place.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), `engine/src/anisotropy_engine/repair/`, `fea/src/anisotropy_fea/repair_model.py`, `fea/src/anisotropy_fea/repair_shape.py`, `app/workspace/repair/`
- Area: website, api, engine, fea

## Context

Slices 1 to 3 of the step patch repair are commands: a repair file (ADR-0131) is worked by hand as a stepped lap (ADR-0130) by `repair_report`, its slice is solved in CalculiX by `python -m anisotropy_fea.repair_model` (ADR-0132), and its solids are written as a STEP file by `repair_shape`. Nobody without a terminal can use them. Slice 4 is the page and the report.

Facts the choices rest on:

- The hand calculation is the engine's and answers in milliseconds. The slice's solve takes CalculiX about 3 s for the example (6,344 elements, 38,838 equations) on a development machine, 8 s with the start of the fea environment.
- The API depends on the engine alone and starts the fea tools as processes (ADR-0051, `api/pyproject.toml`). The hosted image holds CalculiX and Gmsh, and the API already builds a wing's STEP file in a process it waits for, up to 90 s (ADR-0118).
- The wing has a page under FEA in layout D (ADR-0118, ADR-0134): its description is the wing file as a JSON object, worked on every settled change. A wing became a project kept on the server one step after its page (ADR-0122), and got its chat later still (ADR-0128).
- A coupon's report is a PDF typeset by LaTeX in the job (ADR-0064, ADR-0112): about half a minute on the hosted tier, a preamble and figures of its own, and an image whose LaTeX cache is filled at build time and checked with the network off.
- The load at the adhesive's elastic limit is not the repair's strength (ADR-0130), and a peak beside a corner is reported only as a mean over a square of adhesive (ADR-0132).

## Options considered

**1. Where the repair is worked.** (a) A page of its own under FEA, `/workspace/repair`, a third kind of FEA work beside the coupon and the wing, in the canvas shell of ADR-0134. (b) Inside the FEA project, as a coupon is: rejected, the FEA project's tree, checklist and viewer are a coupon's, and a repair has none of a coupon's steps. (c) A section of its own beside FEA, CAD and Laminate: rejected, ADR-0124 keeps three sections and a repair is finite element work.

**2. How the slice is solved from the page.** (a) On request, in a process the API waits for, as the wing's STEP file is built: `repair_model` with a time limit, its report returned in the answer. (b) A background job through the queue, as the wing's check (ADR-0119): rejected for now, the queue, the solver machines, the per-user limits and the polling are built for runs of minutes, and this one takes seconds; it is the next step if a repair's solve grows long (see "How we will know it was wrong"). (c) On every change like the hand calculation: rejected, seconds per keystroke, and a CalculiX process per change.

**3. Where the repair is kept.** (a) In this browser, one repair, as its repair file's JSON object, saved and opened as a repair file (TOML). (b) A project of kind `repair` on the server with versions, as the wing since ADR-0122: the right end state, left to the slice that brings the chat, as it was for the wing; it needs a migration, the project store, the list of projects and the sync.

**4. The report.** (a) A page laid out for paper, `/workspace/repair/report`, drawn from the same two answers as the workspace (the hand calculation and, when solved, the slice) and saved as a PDF by the browser's print. (b) A PDF typeset by LaTeX as the coupon's: rejected for this slice. It would be a second typesetting of the same numbers and drawings to keep in step with the page, a new document in the image's LaTeX cache and its network-off check, and half a minute's wait on the hosted tier for a report whose content the page already holds. It stays open: if the founder wants the coupon's look, the report's sections are the list to typeset. (c) No report, the page only: rejected, a repair's analysis is handed in or filed, and a screen is neither.

**5. How the page is reached.** (a) A third pick at the FEA start, and the page's own patterns read "patch repair", "bonded repair", "step lap" and "scarf repair" as that pick (`lib/work-intent.ts`), with no change to what the model is asked or told. (b) Also teach the model the new kind (`kinds` of the general question): left to the chat's slice, with its real-model check (ADR-0121). (c) A link only: rejected, ADR-0124 makes the FEA start the way in.

**6. What the page says of the answer.** (a) The largest bondline shear stress under the stated load and the load at which the adhesive reaches its elastic limit, each from the hand calculation, with the slice's values beside them once solved, the peel stress, the first ply, and what reaches its limit first; never the words strength, failure load or margin for the repair as a whole. (b) A pass or fail verdict: rejected, nothing here is a strength (ADR-0130, ADR-0132): the adhesive yields before it fails, and the slice is elastic, held flat and leaves out the panel beside the repair.

## Decision

1 (a), 2 (a), 3 (a), 4 (a), 5 (a), 6 (a).

- **The page.** `/workspace/repair`, "FEA · Patch repair", in the canvas shell (ADR-0134). The model tree holds the repair file's tables as steps: the repair and its file, the laminate, the damage and the steps, the patch, the cover plies of a flush repair, the adhesive, the panel and the load, the solve, the report and the shape. The model's area draws the engine's rectangles of the slice (ADR-0131), the thickness stretched and said to be, and the bondline's shear stress along the bond by hand, with the slice's shear and peel stress over it once solved. The results card holds the answer in its short form; the details hold the lap's steps, the forces at the lap's boundaries by hand and by the slice, the plies, the sizes and the model's facts. The right column says in words what the numbers are and are not; it has no chat yet.
- **The API.** `POST /v1/repairs/analyze` reads a repair (the JSON object of a repair file, or its TOML text) by the engine's own rules and returns `repair_report`, what the page draws (`repair_views`: the hand calculation's shear stress and patch force along the lap) and what a solve of the slice still needs (`solve_needs`). `POST /v1/repairs/solve` runs `anisotropy_fea.repair_model` in a process, 120 s at most, and returns `slice_report`. `POST /v1/repairs/shape` runs `anisotropy_fea.repair_shape` and returns the STEP file's text and its solids. Each is recorded with its actor (ADR-0026); a refusal is the engine's or the tool's own sentence.
- **Every number is the engine's or the solver's** (ADR-0001): the page reads, draws and words. The solve uses ADR-0132's mesh and its three checks; a solve they refuse is refused on the page in the same words.
- **The report.** `/workspace/repair/report` opens the repair this browser holds and lays out for paper: what the repair is, its slice drawn, the hand calculation with its method and every step's numbers, the solved slice when there is one with its checks, and what the analysis is not. "Print or save as PDF" is the browser's print. It holds no code of ours (ADR-0112) and, like the page, names no tool (ADR-0091): the solved slice is described by its elements, its equations and its checks.
- **Reaching it.** A third pick, "Patch repair", at the FEA start; the words above typed there open the page.

## As built (2026-11-21)

- **Engine.** `repair_views` and `solve_needs` in `engine/src/anisotropy_engine/repair/repair_file.py`: the lap's boundaries from the repair's middle and, with a load, the hand calculation's shear stress and patch force along it; and what a solve of the slice still needs, each by the description's path and in words. A second example, a patch bonded on top, `engine/examples/example-external-patch-repair.toml`; its slice was solved at three mesh sizes before any of its numbers was used (largest shear 13.37, 13.38 and 13.39 MPa, largest peel 7.36, 7.33 and 7.32 MPa).
- **Solver tools.** `repair_model` and `repair_shape` read a repair as TOML or as JSON (`read_repair_file`), answer a refusal with exit code 2 and a stopped solve with 3, and write `repair-solve.json` (the report and its headline) and `--parts` (the table of the solids).
- **API.** `POST /v1/repairs/analyze`, `/v1/repairs/solve` and `/v1/repairs/shape` in `api/src/anisotropy_api/main.py`, with `RepairRequest`, `RepairSolveRequest` and their answers in `schemas.py`. The solve refuses with what it needs before it starts a process; a tool's refusal is passed on as 422, a failure as 503 with its cause in the log only, and a solve past 120 s as 504.
- **Page.** `app/workspace/repair/page.tsx` and `components/workspace/repair-{workspace,context,rail,stage,drawings,details,assistant}.tsx`, with `lib/repair.ts` (the description, its file, the words) and `app/workspace/repair.css`. The repair and its last solve are kept under `anisotropy.repair.v1` and `anisotropy.repair-solve.v1`. A solve made of an earlier state of the repair is said to be, and its curves leave the chart.
- **Report.** `app/workspace/repair/report/page.tsx` and `components/workspace/repair-report.tsx`: five A4 pages for the example with its solved slice. While it prints, the page's title is the repair's name, which the browser offers as the PDF's file name. A solve that belongs to an earlier state of the repair is left out, and the report says so.
- **Reaching it.** `FEA_KINDS` holds the third pick; `readRepair` in `lib/work-intent.ts` reads the repair's words before a coupon's, so "a bonded repair over an open hole" is a repair; a question that names a repair is answered as any question and offers the page under the answer. A model is still offered a coupon and a wing only (`ASKED_KINDS`).
- **Differences from the plan.** The page and the report name no tool (ADR-0091): the first draft of this record let the report name the open-source solver. The right column offers no chat; the repair's theory stays out of the general search, as ADR-0102 amendments 5 and 6 left it.
- **Checks.** `engine/tests/test_patch_repair.py`, `fea/tests/test_repair_page.py`, `api/tests/test_repairs_api.py`, `tests/repair.test.ts`, `tests/work-intent.test.ts`, `tests/browser/repair.spec.ts` (ten scenarios), and six questions in `tests/assistant-questions/sections.json`. `scripts/repair-choices.py` writes the page's choices and the answers its tests draw. No real-model check was run: nothing a model reads changed.

## Why (evidence)

- The time of the solve: `uv run python -m anisotropy_fea.repair_model ../engine/examples/example-patch-repair.toml` printed "CalculiX 2.21: 6344 elements (CPE8R), 38838 equations, 3.3 s" and took 8.3 s in all in a cloud container on 2026-11-21.
- The wing's STEP file has been built in a process the API waits for since ADR-0118, on the same image, with a 90 s limit.
- No evidence yet that a printed page serves a class report as well as a typeset PDF; the founder has not seen either.
- No evidence yet for the hosted tier's time for a solve; it is measured on the first live use.

## Consequences

- A repair is not in the list of projects and not on the server: another browser does not have it. The repair file is how it moves. The project of kind `repair`, its versions and the chat are the next slice.
- Two answers stand side by side that differ by design (the hand calculation leaves out peel, bending and shear through the thickness); the page says which is which and never averages them.
- The API container runs CalculiX for a few seconds per request to solve, beside the wing's shape. Nothing limits how often one person asks beyond the sign-in; the queue's limits do not apply.
- The report changes with the page's code, not with a run: a repair printed today and next month may be laid out differently. The numbers are the engine's each time.

## How we will know it was wrong

- A solve on the hosted tier takes over 30 s for an ordinary repair, or times out: move it to a background job (option 2 (b)).
- Students or the professor ask for the report as a file made by the site, or its print layout breaks across browsers: typeset it (option 4 (b)).
- People lose repairs with a cleared browser, or ask to open one on another machine, before the next slice lands: bring the project kind forward.
- Someone reads the load at the adhesive's elastic limit as the repair's strength in spite of the words: change what the card leads with.
