# ADR-0086: Every edit is answered by our kernel as a labelled preview, from warm workers; CalculiX, the mesh study and the package stay on the full run

- Status: Proposed; a mesh past 40,000 elements refused by the setup check before meshing, the file for Abaqus or Ansys excepted, amendment 1 (2026-11-25); a setup past 100,000 elements refused for every file from its rows, amendment 2 (2026-11-27, drafted, not yet confirmed by the founder), which narrows amendment 1's no limit on the file for Abaqus or Ansys
- Date: 2026-11-10
- Decided by: Founder, 2026-11-10 (asked what should update within seconds of an edit: "Live kernel, full run on request (Recommended)"; the plan of that day, part 3, approved) | Drafted by: Claude Code
- Related: `fea/tools/studio_tool.py` (`live`, `serve`), `api/src/anisotropy_api/live.py`, `api/src/anisotropy_api/main.py` (`POST /v1/coupon-jobs/live`), `api/src/anisotropy_api/settings.py` (`ANISOTROPY_LIVE_WORKERS`), [docs/evaluations/fea/2026-11-10-live-solve.md](../evaluations/fea/2026-11-10-live-solve.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md), [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md), risk R-23
- Area: fea

## Context

The founder wants the analysis to update within seconds of an edit, as the engineer changes values in the chat or on the panels. The only way the page had to a result was the full job: setup check, decks, our kernel, the mesh study (ADR-0068), the CalculiX twin, drawings and the PDF. That gives a first result after about 3 to 4 s locally and minutes on the hosted tier. Edits only cleared the old result.

Our kernel alone solves a strip in hundredths of a second (ADR-0067). Measured on 2026-11-10 (the evaluation note):
- A fresh `studio_tool.py live` per call takes 4 to 5 s.
- About 2 s of that is importing the fea package, and 1.5 to 2 s is starting Python and `uv`. The work is under a second.
- A warm worker that keeps the package imported answers the same strips in 0.4 to 0.9 s, and the public open hole in 3.4 to 3.6 s.

## Options considered

What answers an edit:

1. **Our kernel alone, labelled a preview; the full run on request** (chosen by the founder). It is accurate where our kernel is: the same kernel and answer as the full run. CalculiX and the mesh study check it when the engineer asks.
2. The full job on every edit. Rejected: 8 to 17 s locally, minutes hosted.
3. No automatic answer, only a faster button. Rejected: not the founder's "within seconds".

How the API runs it:

1. **Warm `studio_tool.py serve` workers, one JSON line in and one out** (chosen). The imports are paid once, and the API still depends on the engine alone (ADR-0051).
2. A fresh `studio_tool.py live` per call. Kept as the fallback, with `ANISOTROPY_LIVE_WORKERS=0`: 4 to 5 s.
3. The API imports the fea package. Rejected: ADR-0051 keeps the API on the engine alone, and the package's own processes on a separate side.

How the fields reach the page:

1. **As the tool wrote them, compact, gzipped in transit** (chosen). A fine mesh's fields run to megabytes, and parsing and re-encoding them costs more than the solve.
2. Through Pydantic. Rejected for that cost.

## Decision

- **`studio_tool.py live` and `serve`.**
  - `live` runs the setup check and, when nothing blocks but the full run's own tools (CalculiX and the document builder, which our kernel does not need; the checklist still names them and the full run stays blocked), our kernel on the deck as a run writes it. It writes the fields with the answer (ADR-0085), the explanation, the summary apart, and each stage's seconds.
  - There is no mesh study, no CalculiX, no attempt folder and no document.
  - `serve` is `live` kept warm: it imports once, says it is ready, then answers one JSON request per line on stdin with one JSON line on stdout.
  - `fixtures` is `live` and the mesh study, so the two cannot drift.
- **`POST /v1/coupon-jobs/live`** takes the setup check's request. It answers with the check, the preview drawing, and the fields and explanation as the tool wrote them, plus the API's seconds and the tool's stage seconds.
  - **The pool:** `LiveSolver` keeps `ANISOTROPY_LIVE_WORKERS` warm workers (default 1, 0 to 8), started on the first live request.
  - **Failures:** a worker that does not answer in 30 s, or stops, is killed and replaced. The request is answered 504 or 503. When every worker stays busy for 20 s, the answer is 429.
- **The run record** (amends ADR-0026) keeps the check's state, the designation, the summary and the fields' SHA-256, never the arrays.
- **Compression:** the API compresses its responses for a browser that asks.
- **A preview is not a result** (amends ADR-0068). It carries no mesh study and no CalculiX comparison, and the page labels it so (part 4). The full run stays `POST /v1/coupon-jobs`.

## As built (2026-11-10)

- **fea:**
  - `studio_tool.py`: `solved`, `live`, `serve`, `write_compact`, and `fixtures` through `live`. The deck is now solved in a folder of its own, so a fixture folder no longer collects decks.
  - `fea/tests/test_studio_tool.py`: live, a blocked live call, and serve.
- **API:**
  - `api/src/anisotropy_api/live.py` (`LiveSolver`); `POST /v1/coupon-jobs/live` in `main.py`; `LiveSolveResponse` (for the documentation); `GZipMiddleware`; the setting `ANISOTROPY_LIVE_WORKERS`.
  - `api/tests/test_live_api.py`: ready, blocked, one warm worker kept, a worker that errs kept, one that stops replaced, slow is 504 and replaced, busy is 429, no workers, no uv, the setting, and the record.
- Part 4 (the page): once the setup has every row but the engineer's name, each settled edit, on a panel or in the chat, asks for a live solve 800 ms after it, the previous one aborted, never while a full run goes and never for the fibre tow (`lib/studio-live.ts` `shouldSolveLive`, `setupComplete`; `components/studio/use-live-solve.ts`, mounted once in the project provider; `useCouponRun` keeps the answer and takes the check from it). The centre shows the newer of the live answer and the full run's fields: the live one under a banner, "Preview: our kernel, answered in 0.6 s; not yet checked by CalculiX or the mesh study", dimmed while a newer one is on its way. The rail's button reads Run full analysis.

- Fixed after CI, 2026-11-10: on a slower runner a live answer landed after the engineer had checked or started the full run, replaced the check (so the chat's Run went stale) and could take the stage. Now a live answer for rows already checked, or one sent before the latest check, leaves that check in place; starting the full run cancels a live request on its way; and rows that move on cancel the request for the old ones. The browser mock's live route answers only when a scenario asks (`live`), and `THROTTLE=<n>` slows the browser's CPU to meet CI's timing on this machine: the studio suite passes at six times slower.

## Why (evidence)

- The measurements: [docs/evaluations/fea/2026-11-10-live-solve.md](../evaluations/fea/2026-11-10-live-solve.md).
- The tests named above. Running the fixtures through `live` left them byte-identical but for the mesh study's measured solve seconds.

## Consequences

- **Easier:** an edit is answered in under a second for a strip, a bending coupon or a plate; the chat and the panels can keep the answer current (part 4).
- **Harder:**
  - Each warm worker holds the fea package in memory in the API's container.
  - Every edit is a run record (R-23).
  - The open hole's preview still takes about 3.5 s, mostly computing its fields and its Gmsh mesh.
- **We now depend on** the tool's one-line protocol, and on the API container's memory for its workers.

## How we will know it was wrong

- Hosted, a warm preview of a strip takes more than 2 s, or the API container runs out of memory with its workers.
- A preview and the full run of the same rows disagree on the answer.
- The records table grows faster from previews than R-23's controls can carry.

## Amendment 1, 2026-11-25 (a mesh past 40,000 elements is refused before it is built; the file for Abaqus or Ansys is not held to it; the founder chose)

**Context.** A preview builds and solves the model in the API's own container, which every engineer's previews share (one warm worker by default, `ANISOTROPY_LIVE_WORKERS`; a request past 30 s is ended and its worker replaced). Nothing limited the mesh: the setup check built whatever the element size gave. On 2026-11-25 a 0.0787 mm element size (the tension screen's inch default read as millimetres, fixed by ADR-0090 amendment 2) gave a strip of 1,009,968 elements; on this machine the process reached 12 GB before it was stopped, and on the hosted site the check never answered. An engineer could do the same by typing a small element size. Measured here, preview of the IM7/8552 [45/0/-45/90]s strip, check and solve: 2 mm (1,488 elements) 0.6 s and 120 MB; 1 mm (6,500) 2.5 s and 235 MB; 0.5 mm (25,000) 9.7 s and 610 MB; 0.35 mm (51,408) 21 s and 1.2 GB; 0.25 mm (100,000) 44 s and 2.1 GB. The mesh study already leaves out a refinement past 40,000 elements (ADR-0068), so that it stays under about half a minute on the hosted solver.

**Options.**
1. *One limit for every model our kernel builds, the study's 40,000, judged from the mesh's counts before meshing* (chosen): the setup check fails its mesh item and names an element size that fits, so the preview, the run and the chat's "is it ready" all stop there in under a second.
2. *A limit in the mesher itself.* Rejected: the file for Abaqus or Ansys is built by the same mesher, and the founder wants that file free of it.
3. *A memory or time limit on the worker.* Rejected: the worker is already ended at 30 s; by then a fine mesh has taken the container's memory, and the engineer learns nothing they can act on.

**Decision.** Option 1. `MOST_ELEMENTS = 40_000` in `fea/src/anisotropy_fea/spec.py`, used by the setup check (`checks.too_many_elements`, and `plate_shape`, which draws no shape past it) and by the mesh study (`convergence.CAP`, the same number as before). `element_estimate` counts a structured mesh exactly (nx by ny) and Gmsh's plate with a hole from above. The check's words, for example: "the mesh would have 1,009,968 elements; our solver takes at most 40,000 in one model: use an element size of 0.4 mm or more", the size in the coupon's units. The model file for Abaqus or Ansys (`studio_tool.model_file`, ADR-0129) calls the check with no limit. The founder, asked whether the limit applies to Abaqus or Ansys: "no no there shouldn't be an edit for abaqus or ansys, for right now let's do it for our software" (2026-11-24 8:32 PM PT). Such a file is still meshed in the API's worker, so a very fine one can take its memory as before; that stays as it is on his word.

**Evidence.** `fea/tests/test_studio_tool.py::test_a_mesh_past_the_limit_is_refused_before_meshing_and_the_file_for_another_program_is_still_written`: a 0.38 mm mesh is refused by the preview with "use an element size of 0.4 mm or more", and the Abaqus file of the same rows is written with the very element count the check judged (the nearby fea tests: 145 passed; one test needs Gmsh, which this machine lacks, and fails on main too). Through the local API, the 0.0787 mm preview answered in 0.6 s, "blocked", with the words above; in the browser the chat answered "element size 0.05" in 0.7 s with the fix under Mesh. Hosted memory and timings are not measured. Risk R-37 records what is left open.


## Amendment 2, 2026-11-27 (a setup states at most 100,000 elements, whatever is made of it; the file for Abaqus or Ansys, which amendment 1 left with no limit, and a STEP file are held to that; drafted, not yet confirmed by the founder)

**Context.** Amendment 1 left the file for Abaqus or Ansys with no limit, on the founder's word, and recorded that a very fine one could take the worker's memory (risk R-37). The review of the STEP file (ADR-0146) measured what that costs on 2026-11-27. The spec's own check built one coordinate per element row before anything was judged, so an element size of 1e-5 mm cost a STEP request 12 s and 1.2 GB and 1e-6 mm over 10 GB, though a shape cuts no mesh; 99999999999 rows in a segment, or 10^12 elements across, ended the request of every program at the route's 30 s (504). Measured here the same day, a fresh tool writing the file of a 237.3 by 19.7 mm strip for Abaqus and for Ansys: 49,664 elements in 7.5 s; 99,918 in 13 to 14 s; 200,208 in 26 to 28 s; 399,854 in 51 to 54 s, which the route ends first. So each attempt at a large file held the worker every engineer shares until it was ended.

The first draft of this amendment set the number at 200,000, the largest mesh the tool alone wrote inside 30 s. The third review ran files of 200,000 elements through the route: Abaqus took 31.7 to 34.6 s and Ansys 34.4 to 36.0 s end to end, past the limit. It also found the count wrong for a hole: the count added the rings round the hole to the rectangle at the element size, and left out that the column and the band through the hole carry a quarter of the nodes around it across the whole plate. A plate with 39,000 or 190,000 nodes around its hole, in one ring, counted as 44,000 or 195,000 elements, passed the check, and its file for Abaqus or Ansys ended as a 504.

Measured again on 2026-11-28, through `POST /v1/coupon-jobs/model` with the real tool behind it and the tool's 30 s lifted, so that a slow file is timed and not cut. First one file of every kind at about 100,000 elements (strip, compression, dog-bone, open-hole coupon, three-point and four-point bending, plate, plate with a hole): 16.1 to 18.6 s for Abaqus and 17.5 to 20.1 s for Ansys, the dog-bone's the slowest. Then three runs each, in seconds from the request to the whole file:

| Elements | Kind | Abaqus | Ansys |
| --- | --- | --- | --- |
| 80,000 | dog-bone | 13.4 to 15.0 | 15.2 to 15.5 |
| 79,652 | plate with a hole | 12.7 to 13.7 | 13.7 to 14.9 |
| 79,936 | open-hole coupon | 12.8 to 13.2 | 13.5 to 14.1 |
| 98,736 | dog-bone | 16.3 to 17.6 | 18.5 to 19.4 |
| 99,984 | plate with a hole | 15.3 to 16.0 | 16.8 to 16.9 |
| 98,076 | open-hole coupon | 16.2 to 16.7 | 17.3 to 18.6 |
| 100,000 | strip | 15.2 to 15.4 | 16.3 to 16.7 |
| 117,696 | dog-bone | 19.5 to 20.5 | 21.0 to 21.6 |
| 119,844 | plate with a hole | 17.7 to 19.7 | 20.7 to 21.0 |
| 119,936 | open-hole coupon | 20.1 to 20.4 | 20.9 to 21.4 |
| 199,836 | dog-bone | 33.2 to 34.0 | 35.9 to 37.0 |

The machine was the development container, four cores shared with other work (load 1 to 6 while this ran). The hosted machine is not measured.

**Options.**
1. *One number for any setup, judged from the rows by arithmetic before a spec is made of them: 100,000, where the slowest file came back in about two thirds of the route's 30 s* (chosen). The slowest at that size, the dog-bone's Ansys file, took 18.5 to 19.4 s.
2. *200,000, the first draft.* Rejected: through the route a file of that size takes 33 to 37 s here, so the number let through what the route then ended.
3. *About 150,000, where the times above reach 30 s.* Rejected: it leaves no room for a slower moment of the machine or a slower machine, and the hosted one is not measured.
4. *Hold every file to the solver's 40,000.* Rejected: the founder wants the file free of the solver's limit, and a file of 50,000 to 100,000 elements is written well inside the 30 s.
5. *No number; only stop the spec's check from building rows.* Rejected: the file for Abaqus or Ansys would still mesh anything in the shared worker, and the check would still be handed 10^11 rows to count.
6. *Give the file's route more than 30 s.* Not taken here: the worker that writes the file is the one every engineer's preview waits on, so a longer limit holds it longer.

**Decision.** Option 1, the drafter's choice after the reviews, not yet confirmed by the founder. What it narrows: amendment 1 gave the file for Abaqus or Ansys no limit, on the founder's word of 2026-11-24 ("there shouldn't be an edit for abaqus or ansys"). That file is still free of the solver's 40,000 and is now held to 100,000. Why: a larger file already ended as a 504 at the route's 30 s on this machine (200,000 elements took 33 to 37 s through the route), and until it ended it held the worker every engineer shares. What it costs: a file of 100,000 to about 150,000 elements, which would come back inside 30 s here on a quiet machine (120,000 took 18 to 22 s), is refused. Hosted timings are UNVERIFIED. The choice is put to him with the pull request; raising or removing the number is one constant. `MOST_ELEMENTS_STATED = 100_000` in `fea/src/anisotropy_fea/spec.py`.

`intake.stated_elements` counts the mesh from the rows as `mesh_data` would seed it, with nothing built. For a plate or a coupon with a hole the count is the count of the blocks the mesher cuts (`mesher.hole_blocks`, which `gmsh_open_hole_plate` now meshes from), so it is the mesh's own number and not an estimate of it. The setup check (`checks._judged`) makes no spec of rows past the number and fails its mesh item: for a preview or a run in the solver's own words, as before ("our solver takes at most 40,000 in one model"); for a file in these, "the mesh would have 625,000 elements; a setup holds at most 100,000, whatever is made of it: use an element size of 0.25 mm or more", or "give fewer elements across the width or fewer rows per segment" when the rows state a seeded mesh. A hole's refusal names what to change by its cause (`intake.hole_mesh_change`), for the solver's 40,000 as for this number: "give at most 3,424 nodes around the hole" where the nodes pass it at any element size, the most rings where the rings do, both where either would do, and an element size only where the mesh would pass the number with the fewest nodes and one ring too. A count past a million million is written "more than 1,000,000,000,000". `intake.build_specs` refuses the same rows when a form is read, `spec.validate_spec` refuses a spec file that states such a mesh from its counts before it builds a row, and `checks.plate_shape` judges the count from the rows too. A STEP file is held to the same number, inside which the element size costs a shape nothing (ADR-0146).

**Evidence.** The timings above. `fea/tests/test_gmsh_mesher.py::test_the_count_of_the_blocks_is_the_count_of_the_mesh_for_a_grid_of_holes` holds the stated count to the built count for 120 holes, and `fea/tests/test_values_input.py::test_the_count_a_hole_setup_states_is_the_count_of_the_mesh_built_from_it` for a plate with a hole and the open-hole coupon from their rows (20 setups each): equal in every one. `::test_a_hole_whose_mesh_would_pass_the_most_is_refused_by_arithmetic_with_what_to_change_at_the_hole` refuses nine hole setups in under a second each with no spec made, and checks that what the refusal names fits and one step more does not. `::test_rows_whose_mesh_would_pass_the_most_a_setup_holds_are_refused_by_arithmetic_before_a_spec_is_made` stands the spec's parser in by one that fails if it is called, and each of seven setups is refused in under a second; `::test_the_count_the_rows_state_is_the_count_of_the_spec_they_make` holds the rows' count against the spec's own. `fea/tests/test_spec.py::test_a_spec_whose_mesh_would_pass_the_most_a_setup_holds_is_refused_from_its_counts_before_a_row_is_built` takes 100,000 elements and refuses 100,250 and a hole with 39,000 nodes around it. `fea/tests/test_studio_tool.py::test_a_setup_past_the_most_elements_a_setup_holds_is_blocked_for_every_file_in_a_moment_and_in_little_memory` runs the tool under 4 GB and 60 s for Abaqus, Ansys and STEP at 1e-5 mm, 1e-6 mm, 5e-324 mm, 0.1 mm, 99999999999 rows in a segment and 10^12 elements across (18 cases); `::test_a_plate_with_a_hole_and_far_too_many_nodes_around_it_is_blocked_for_every_file_in_a_moment` does the same for the review's plate (6 cases); `::test_a_run_of_a_plate_with_a_hole_past_the_solvers_limit_names_the_nodes_and_not_an_element_size` and `::test_a_run_past_the_most_a_setup_holds_is_refused_in_the_solvers_own_words_as_before` hold the run's words; `::test_the_most_a_setup_holds_leaves_a_third_of_the_routes_time_and_still_takes_a_mesh_past_the_solvers` writes a file past 40,000 elements. Amendment 1's test passes unchanged. Through the route with the real tool, `api/tests/test_coupon_step_api.py::test_what_no_file_can_hold_is_a_422_with_its_rows_reason_for_every_program_and_soon` and `::test_a_plate_with_a_hole_and_far_too_many_nodes_around_it_is_a_422_for_every_program_and_soon` get a 422 in under 10 s for each program. Before the count was corrected the review's plate stated 44,000 and 195,000 elements and a spec was made of it; after, 1,113,900 and 5,417,400, refused. The whole fea suite with the engine's, as CI runs it (`uv run --extra mesh pytest -q tests ../engine/tests`): `2641 passed, 14 skipped`. Hosted memory and timings are UNVERIFIED: the room left is a third of the limit on this machine and not known there.

**How we will know it was wrong.** An engineer asks for a file of more than 100,000 elements for their own program that the route could have written; a file inside the number ends as a 504 on the hosted machine; or the founder says the file is to have no limit at all.
