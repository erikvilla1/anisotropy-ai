# ADR-0129: The model on the page downloads as a file for the engineer's own program, one writer per program over the neutral model, and the Ansys file is offered to founders only until it has run in Ansys

- Status: Proposed; three questions beside the download answered in fixed words since amendment 1; the file names the maximum stress criterion since amendment 2; the Ansys file is everyone's since amendment 3; no result of a run in Ansys is stated in the record or on the page since amendment 4; the Abaqus file, the page and the assistant say how Abaqus/CAE opens the file, and a download is named after its coupon, since amendment 5; the same menu and route also give the model's shape as a STEP file for a CAD program, by [ADR-0146](ADR-0146-a-coupon-or-a-plate-leaves-the-workspace-as-a-step-file-of-one-solid-per-part-at-its-real-thickness-and-the-layup-goes-with-it-as-a-part-table.md)
- Date: 2026-11-20
- Decided by: Founder, 2026-11-20 ("essentially what i want is the ability to produce ansys models as well the same way we are able to create abaqus models, our software or browser is FEA or CAD going on but upon request of the user say they ask the AI or something shows with, Download abaqus model, or download ansys model etc.", his ask; then "Downloads, then repair hand calc", his choice on the card "Start building now, and with which piece first?", whose plan has founders seeing the Ansys file and customers keeping the Abaqus one until his check in Ansys). The file's format, its commands, the names of its components, the wording and the gate are the drafter's | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0065](ADR-0065-coupon-ply-angles-are-counted-from-the-coupons-length-axis.md), [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0094](ADR-0094-models-move-to-and-from-abaqus-through-a-connector-under-the-users-own-abaqus-and-one-versioned-bundle-compared-privately.md), [ADR-0111](ADR-0111-the-fea-workspace-sets-a-model-up-in-a-model-tree-on-the-left-in-the-words-of-any-finite-element-program-and-the-chat-changes-the-same-tabs.md), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md), `fea/src/anisotropy_fea/write_ansys.py`, `fea/tools/studio_tool.py`, `api/src/anisotropy_api/main.py`, `lib/model-file.ts`, `components/studio/model-download.tsx`
- Area: fea, api, website, assistant

## Context

- A coupon or a plate set up in the workspace becomes one neutral model, `FEModel` (`fea/src/anisotropy_fea/femodel.py`), and one writer per program turns it into text: `write_abaqus.py` and `write_calculix.py` (ADR-0030). Before this record the Abaqus file reached a person only as one of the files of a finished run, and no file for Ansys existed.
- The founder asked for the same for Ansys, on request: a button, or the assistant, "Download abaqus model, or download ansys model". His team and the first users, students at his school, have Abaqus, Ansys and SolidWorks (2026-11-20).
- Ansys is licensed software and never runs on the hosted site, as with Abaqus (ADR-0094). At the time of this record no file of ours has been opened in Ansys.
- The customer's view names no program, with one exception written into the guard: the phrase "Abaqus input file (.inp)" (ADR-0091, `lib/studio-copy.ts`). "Ansys" is not on the banned list.
- A change to what the assistant reads brings its questions (ADR-0121).

## Options considered

1. **One writer per program over the neutral model, the file written on request from the rows as they stand (chosen).** No run is needed, no solver is touched, and the next program is one more writer. The Ansys writer is new code that only a run in Ansys can fully check.
2. **Write the Ansys file through PyMAPDL or PyACP.** They are MIT licensed, but they drive a running, licensed Ansys, so they cannot run on the hosted site. Rejected for the product; they stay useful for a check of the file in Ansys.
3. **Translate the Abaqus file with a third-party converter.** Two translations instead of one, and the layup, the orientation and the grips are where converters differ. Rejected.
4. **Wait until the Ansys import exists and use its reader as the check.** The founder put the download before the import (2026-11-20). A full reader of our own would also check our writer against our own reading of the manual, not against Ansys. Rejected for now; the tests carry a strict reader of exactly the commands the writer may emit, and an independent open-source reader for the mesh.
5. **Plain `N` and `E` commands in place of blocked data.** Readable, but several times larger, slower to read in, and not what Ansys itself writes. Rejected: the file follows the archive layout `CDWRITE` produces, which the open-source reader also understands.
6. **Offer the Ansys file to everyone now.** Rejected: nothing has been run in Ansys. Founders see it; a customer who asks is told it is being checked, as every test but tension is held back until its comparison is validated (ADR-0089).

## Decision

**The download.** "Download model" sits over the model once there is a model to write (a checked setup or a result), and lists one file per program by the file's own name: "Abaqus input file (.inp)" and "Ansys input file (.cdb)". The file is written from the rows on the page as they stand, by the fea package, through `POST /v1/coupon-jobs/model?program=abaqus|ansys`; the page computes nothing (ADR-0051) and no run is started. A setup the check blocks gets no file and the check's own sentence. The file is named `<designation>-abaqus.inp` or `<designation>-ansys.cdb`.

**The assistant.** A request for the file ("download ansys model", "export to Abaqus", "give me the inp", "can I open this in Ansys?") is answered by the page with the same downloads as buttons, in fixed words, and changes nothing. It is not a request when a file comes in ("import an ansys model"), when work is asked for elsewhere ("can you run this in ansys"), when it asks what a file is, or for the report. An imported model or a past run is told that the file is written from a coupon set up here.

**Who sees the Ansys file.** Founders and a machine with every test switched on. A customer sees the Abaqus file alone, and one who asks for Ansys is told "Not as an Ansys file yet" with the Abaqus file offered. The API refuses the Ansys file to anyone else (403). It opens to customers on the founder's word after his check in Ansys.

**The Ansys file** is a Mechanical APDL archive of our own writing, in the deck's units (`/UNITS,MPA` or `SI`), ASCII only:

| In the model | In the file |
| --- | --- |
| Nodes, elements | `NBLOCK,6,SOLID` and `EBLOCK,19,SOLID`, as `CDWRITE` lays them out |
| Element type | `ET,1,181` (four nodes) or `ET,1,281` (eight); `KEYOPT,1,1,0` membrane and bending, `KEYOPT,1,3,0` reduced or `2` full integration (181 only), `KEYOPT,1,8,2` results kept for every layer |
| Node and element sets | `CMBLOCK` components `N_<NAME>` and `E_<NAME>`, upper case, 32 characters at most |
| Ply angles counted from the coupon's length (ADR-0065) | `LOCAL,11,0,0,0,0,90` and every element's coordinate system 11, the same rotation as the Abaqus file's orientation; `SECDATA` then holds the stated angles |
| Material | `MP,EX…GXZ` (nine values, or `EX` and `PRXY` when isotropic) |
| Strengths | `TB,FCLI` with `TBDATA`: compressive limits negative; through-thickness limits written as 10⁶ times the fibre strength, which means not checked; the Tsai-Wu coupling as `XYCP = 2 f12*`, a zero written as 1E-14 because Ansys reads a zero as its default of -1 |
| Layup | `SECTYPE,1,SHELL`, one `SECDATA,thickness,1,angle,3` per ply from the bottom, `SECOFFSET,MID` |
| Supports | `D` on the component |
| A grip tied to a reference point | The point's supports go onto the grip's nodes; a free direction is coupled with `CP` and its force is put on the lowest-numbered node of the grip, which Ansys takes as the coupled set's primary |
| Forces, pressure | `F`; `SFE,<component>,2,PRES` on the top face with the model's own sign |
| Step and output | `/SOLU`, `ANTYPE,STATIC`, `NLGEOM,OFF`, `OUTRES,ALL,ALL`, `SOLVE`; `/POST1` prints each support's reactions and each probe's displacements |

A grip whose reference point may turn, or that carries a moment, is refused with a sentence that says so: a grip that rotates as a rigid body is not written for Ansys yet.

**Not in this record.** The wing's files, a file of an imported model or a past run, a tool of the MCP server, and the download in CAD.

## Why (evidence)

- The founder's words and card choice are quoted above.
- `cd fea && uv run pytest tests/test_write_ansys.py tests/test_studio_tool.py -q`: 13 and 4 passed (2026-11-20). The tests read every file back with a strict reader that fails on any command the writer is not meant to emit, and compare the nodes, the elements, the components, the material, the strengths, the layup, the supports, the couplings, the forces and the pressure with the model.
- An independent reader finds the same mesh: `mapdl-archive` 0.4.2 (MIT, https://pypi.org/project/mapdl-archive/) reads our files' nodes, elements, element type, key options and components, and they equal the model's (`test_an_independent_reader_finds_the_same_mesh`). It reads no material, layup, support or load. It is a test dependency only.
- `cd api && uv run pytest tests/test_coupon_model_api.py tests/test_coupon_tests.py tests/test_live_api.py -q`: 47 passed, 2 skipped (the two need the test database).
- `npx tsx --test tests/model-file.test.ts` (3 passed) and `tests/assistant-questions/model-downloads.json`, 17 questions held by `npx tsx --test tests/assistant-questions.test.ts`; two browser scenarios in `tests/browser/studio.spec.ts` (the founders' view and the customer's) pass in Chromium.
- From Ansys's command reference (v261, read 2026-11-20): `CP` with `ALL` takes the lowest-numbered selected node as the primary and sums the forces of the set onto it (https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_CP.html); the failure limits' signs, their defaults and the effective zero of the coupling coefficients (https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_cmd/Hlp_C_FC.html, https://ansyshelp.ansys.com/public/views/secured/corp/v251/en/ans_mat/elemmatstrenlimits.html); SHELL181's layers stack from the bottom along the element's normal and a positive pressure acts into the element (https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_SHELL181.html).
- UNVERIFIED: nothing has been run in Ansys. Unchecked there: that the file reads in without a warning, the face number of `SFE` (2 as the top), the argument orders of `SECDATA` and `LOCAL` as written, how system 11 is projected onto each element, the `FCLI` table, and that Workbench's External Model reads the file. The reaction and the ply stresses of a run in Ansys have not been compared with ours.
- The Abaqus file is the writer every coupon run already uses (ADR-0030) and whose comparison with Abaqus opened tension to customers (ADR-0089).

## As built (2026-11-20)

- `fea/src/anisotropy_fea/write_ansys.py`: `write_ansys(model, units)`, `AnsysWriterError`, `component_name`; `fea/tests/test_write_ansys.py`.
- `fea/tools/studio_tool.py`: the command `model <values> --program abaqus|ansys --out <dir>` and the same request of a warm worker; it writes the file and `model.json` (name, units, bytes, sha256, nodes, elements), or says the setup is blocked or the model refused.
- `api`: `LiveSolver.model_file`, `POST /v1/coupon-jobs/model`, the header `X-Anisotropy-Model-File`, `ansys_model` in `GET /v1/coupon-tests`; the request is recorded like a live solve, without the file's text.
- The page: `lib/studio-api.ts` (`modelFile`, `MODEL_FILE_LABELS`), `components/studio/model-download.tsx` (the menu and the chat's buttons), `lib/model-file.ts` and the route `model-file` in `lib/chat-route.ts`.
- Different from the plan: the page says the kind of file it saved, not the file's name, because the name carries the program's (ADR-0091).

## Consequences

- An engineer takes the model on the page into their own Abaqus or Ansys in one click or one sentence, before any run.
- A new program is one writer and one line of `MODEL_PROGRAMS`; a new kind of model (the wing) needs its neutral model to reach the same writers.
- We now keep a second writer in step with the neutral model: every new kind of support, load or section must be written, or refused in words, in both.
- The Ansys file's standing in this repository rests on our own tests and an open-source reader; a run in Ansys is not something the repository can show (amendment 4).
- The customer's view now holds a second program's name in one phrase, "Ansys input file (.cdb)", once the file opens to customers.

## How we will know it was wrong

- The file does not read into Mechanical APDL without errors, or its reaction at the grip differs from ours by more than 1 %, the mark the Abaqus comparison is held to (ADR-0089), on a first check.
- An engineer reports plies turned by 90°, a pressure pointing the wrong way, or a grip that carries a different load than the page shows.
- A request for the file is read as something else, or another question is read as a request, in the question bank's real-model run or on the live site.

## Amendment 1, 2026-11-20 (what a model file is, where the report is, and a model brought in from another program are answered in fixed words; not yet confirmed by the founder)

**Context.** The founder chose "Run it now" on the card "Run the assistant's real-model check for the model downloads now?" (2026-11-20). The run asked the three questions of the bank that the page does not read as a download and a model reads instead: 0 held, 2 were weak and 1 failed, for $0.03 (https://github.com/erikvilla1/anisotropy-ai/actions/runs/44818448757). "what is an abaqus input file" was told "Not a question I can read yet" (criteria 1 and 10 of the `chat-answer-quality` skill); "import an ansys model" and "download the report" were told "Read, but nothing to enter", with nothing to ask instead (criteria 8 and 11). None offered a file, which is what the bank asked of them.

**Options.** (1) Leave them to the model and change its instructions: the answers are the same for everyone, so a model adds cost, time and a chance of a wrong word, and nothing else. Rejected. (2) Answer each on the page in fixed words (chosen): the way the chat already answers who it is, the units and another program named (ADR-0121 amendment 2). (3) Read "download the report" as a press of the report's button: the report is written on request in half a minute and belongs to a finished run (ADR-0064 amendment 3); the chat pressing it is a decision of its own. Not here.

**Decision.** Three topics join the chat's fixed answers (`lib/chat-about.ts`), tried after the request for a file and the glossary, and changing nothing:

- What a model file is ("what is an abaqus input file", "whats a cdb file"): "A text file that holds the whole model", what it states, and "download the model" to get one.
- The report asked for or looked for ("download the report", "where is the pdf"): "The report is under Files", and that there is no result yet when there is none. "report the stress in ply 3" and a question of why are not read as this.
- A model brought in from a program whose files are not read here ("import an ansys model", "can I upload a nastran file?"): that it cannot be brought in yet, to set the coupon up here, and that the other way works. Ansys is named back; another program is not (ADR-0091). An Abaqus file brought in keeps its own answer (ADR-0105).

**Evidence.** `tests/assistant-questions/model-downloads.json` now holds 20 questions, the three with the good answer and three more in other words; `npx tsx --test tests/assistant-questions.test.ts` 20 passed, `npx tsx --test tests/model-file.test.ts` 4 passed, `npm test` 489 passed and 1 skipped (2026-11-20). No question of this bank is read by a model any more (`scripts/assistant-live.py --features model-downloads --dry-run`: "No live question"), so there is no second real-model run to make. No evidence yet from a user's own words for these three.

## Amendment 2, 2026-11-20 (the file names the maximum stress criterion; who sees the Ansys file is unchanged; not yet confirmed by the founder; the results of a run that stood here were taken out by amendment 4)

**Context.** Mechanical APDL works out a layer's failure measures after the solution, for the criteria `FCTYP` names. Left at its own choice, the criteria include the maximum strain criterion, and a material that states stress limits and no strain limits then gets no failure measure at all: asked for them (`PRESOL,FAIL`), the program answers with an error, and a batch run stops there. The file states stress limits (`TB,FCLI` option 1) and no strain limits.

**Options.** (1) Leave the file as it is and tell the engineer to name the criterion: the first thing an engineer asks of a composite in Ansys ends in an error whose cause is not in view. Rejected. (2) Write strain limits too, each strength over its modulus: those are numbers the lamina does not state and nobody measured. Rejected. (3) Name the maximum stress criterion in the file's own post-processing (`FCTYP,DELE,ALL`, `FCTYP,ADD,SMAX`), the one criterion the stated limits serve and the page shows. Chosen. The Tsai-Wu measure stays unnamed: Ansys works it with its own interaction term of -1 unless the coupon states one, and that value is not ours.

**Decision.**

- The writer adds `FCTYP,DELE,ALL` and `FCTYP,ADD,SMAX` after `SET,LAST` when the material states strengths, with a comment that says why.
- Who sees the Ansys file does not change: founders and a machine with every test switched on, until the founder's word opens it.

**Evidence.** `cd fea && uv run pytest -q tests/test_write_ansys.py tests/test_studio_tool.py`: 32 passed; `npx tsx --test tests/model-file.test.ts tests/assistant-questions.test.ts`: 24 passed (2026-11-20). No result of a run in Ansys is stated here (amendment 4).

## Amendment 3, 2026-11-20 (the Ansys file is offered to everyone; confirmed by the founder)

**Context.** The founder was asked whether to open the Ansys download to customers and chose "Open it with the fix" (his card choice, 2026-11-20), the option that adds the opening to the pull request of amendment 2's fix. A customer sets up one kind of model, the unnotched tension coupon (ADR-0089), pulled by a displacement or a force, on four-node shells.

**Options.** (1) Keep the file with founders longer: a plate and a pressure, which a customer cannot set up today, would be the reason. Not chosen. (2) Offer it to everyone, with a line on the page beside it. Chosen by the founder. (3) Offer it to everyone and take the line away: a file from a new writer should be compared by the engineer in their own program. Rejected.

**Decision.**

- The API offers the Ansys file to every request: `_ansys_model` answers true, and `GET /v1/coupon-tests` says `ansys_model` true to everyone. The 403 "The Ansys model is not offered yet." and the page's "Not as an Ansys file yet" stay in the code for the day the file must be closed again, which is one line in `_ansys_model`.
- The menu and the assistant offer both files to a customer. A line stays beside every Ansys download; its words are amendment 4's.
- What a founder can set up and a customer cannot (a plate with a pressure, ADR-0089 amendment 6) still writes an Ansys file; its pressure (`SFE`, its face and sign) is checked only by reading the text back.

**Evidence.** `cd api && uv run pytest -q tests/test_coupon_model_api.py tests/test_coupon_tests.py`: 34 passed, 1 skipped (a request with no sign-in gets the file; a closed file is 403). Three browser scenarios in Chromium, `BROWSER_CHANNEL=chromium npx playwright test -c playwright.studio.config.ts -g "ADR-0129"`: 3 passed, among them a customer who is offered both files by the menu and by asking, with the customer's view checked for words it must not show, and the closed state (2026-11-20). No evidence yet from a customer's own Ansys.

## Amendment 4, 2026-11-21 (the record and the page state no result of a run in Ansys; on the founder's word given for ADR-0132 amendment 1 and read as covering this record, not yet confirmed by him for this one; the new lines on the page are the drafter's)

**Context.** Amendments 2 and 3 as first written, and a line on the page beside every Ansys download, rested the file's standing on a run in Ansys, with its results and the name of the licence. Ansys is a licensed program that our code does not run. Asked whether wording that quotes such runs should be taken out of ADR-0132 amendment 1, the founder answered, 2026-11-20: "merge and yes thee shouldn't wording in our software".

**Options.** (1) Leave this record as written and hold only new records to the rule: the page would go on telling every customer of a run in a licensed program. Rejected. (2) Change the page and leave the record: the public record would still quote the run. Rejected. (3) Take the wording out of the page and of this record, and say here that earlier text was changed, which the records of this repository otherwise never do. Chosen.

**Decision.**

- The line beside an Ansys download is "Compare the Ansys file's reaction with the one shown here before relying on it." Asked for while it is closed, the answer's line is "The Ansys file is not offered yet."
- The results of the run, the licence's name and the sentences that rested the file's standing on the run are taken out of this record's Status line, Context, Consequences and amendments 2 and 3, and out of the changelog, `fea/README.md`, the index row and the comments in the code. What the file holds, the `FCTYP` lines and who is offered the file do not change.
- In the repository the file's standing rests on what the repository can show: the tests that read every file back command by command, and the open-source reader that finds the same mesh.
- This record states no result of a run in Ansys, as ADR-0132 amendment 1 states none. Records that quote runs of other licensed programs are not changed here; that is the founder's to decide.

**Evidence.** `npx tsx --test tests/model-file.test.ts tests/assistant-questions.test.ts`: 24 passed; `npm test`: 490 passed, 1 skipped; `npm run typecheck`: clean; `cd fea && uv run --extra mesh pytest -q tests/test_write_ansys.py tests/test_studio_tool.py tests/test_coupon_document.py tests/test_theory_markers.py`: 60 passed, 2 skipped; `cd api && uv run pytest -q tests/test_coupon_model_api.py tests/test_coupon_tests.py tests/test_assistant_questions.py`: 57 passed, 1 skipped (2026-11-21, in the cloud container). The files the writer gives are unchanged; only the page's two lines, comments and documents changed. The browser scenarios of this record run in the pull request's checks. No evidence is stated in this record that the file runs in Ansys.

## Amendment 5, 2026-11-25 (the Abaqus file, the page and the assistant say how the file is opened in Abaqus/CAE, and a download carries its coupon's name; drafted, not yet confirmed by the founder)

**Context.** The founder downloaded a coupon's Abaqus file to rebuild a colleague's model and could not get a job out of it ("i even tried downloading through abaqus but it isn't even poppin up to create the job. there is some serious fixing needed to be done with our software", 2026-11-25). Abaqus/CAE 2025 has two imports for an input file. File > Import > Part reads the mesh alone, as a part with no material, layup, instance, step, boundary condition or load, and a job written from that model has an empty assembly, which the solver refuses with "THIS MODEL HAS EITHER INCORRECT OR NO ELEMENT DEFINITIONS". File > Import > Model reads the whole file into a new model. The file is the same for both, and nothing in it, on the page or in the chat said which to use. Beside this, every download was saved as `model-abaqus.inp`: in `api/src/anisotropy_api/main.py` the constant for the header that carries the file's name was given a second value further down (the import's header for a file's name, ADR-0105), so the page never found the name and fell back to its default.

**Options.** (a) Leave the file and write the way to open it in the documentation only: rejected, the engineer is in Abaqus/CAE with the file when the question comes, not on our documentation. (b) Write the file so that Import > Part also brings a whole model: rejected, that import reads the mesh alone whatever the file holds. (c) Say it where the engineer is: in the file's first lines, on the page under the file once it is saved, and in the assistant's fixed words when asked or when the error is quoted: chosen. (d) Add the same for Ansys: not now, how its menus take our file has not been tried, and the page says nothing it has not seen.

**Decision.** (c).

- A downloaded Abaqus file opens with three comment lines under `*Heading` (`OPENING` and `write_abaqus_download` in `fea/src/anisotropy_fea/write_abaqus.py`): open it with File > Import > Model and create the job from the model that makes; Import > Part reads the mesh alone; to run it as it is, a job with Source: Input file, or the command line. The deck a run writes and hashes into its record (`write_abaqus`) is unchanged.
- After an Abaqus file is saved, the page says under it "Open it with File > Import > Model, then create the job from the model that makes. File > Import > Part brings in the mesh only, so a job from it has no elements." (`MODEL_FILE_OPENING` in `lib/studio-api.ts`): under the "Download model" menu, under the assistant's download button, and under the run's own input file in the list of files. In the card at the window's foot the note sits in the card's column, where the window's edge does not cut it. Nothing is said for the Ansys file.
- Asked how the file opens in Abaqus, why the imported model is empty, or given the words "no element definitions", the assistant answers in fixed words, with no model: "Open it with File > Import > Model" and the two lines above (`model-file-open` in `lib/chat-about.ts`). A request for the file ("can I open this in Abaqus?") is still a request for the file.
- The header that carries a download's name has a constant of its own (`MODEL_FILE_HEADER`), so the file is saved under its coupon's name, as amendment 3's page already expected.

**Evidence.** How the two imports behave is stated for Abaqus/CAE 2025 as its behaviour (ADR-0133); no result of a run is stated here. `cd fea && uv run pytest -q tests/test_studio_tool.py -k model`: 4 passed, the Abaqus file's first lines are the three comments and the next is the deck's own first comment. `cd api && uv run pytest -q tests/test_coupon_model_api.py tests/test_imported_models_api.py`: 23 passed, 1 skipped, the name's header asserted by its own words, and the import's header absent from a download's answer. `npx tsx --test tests/model-file.test.ts tests/assistant-questions.test.ts`: passed, with three new questions in `tests/assistant-questions/model-downloads.json`. Browser scenarios (Chromium, a local build): the line shows under the menu and under the assistant's button after an Abaqus download, not after an Ansys one, and under the run's input file; 4 passed. A picture of the menu's note taken before the last change showed its second line cut by the window's foot; after it, the whole note in the card's column.

## Amendment 6, 2026-11-26 (a plate with nonlinear geometry on downloads with it on in both files; drafted, not yet confirmed by the founder)

**Context.** Both writers stated a linear step (`nlgeom=NO`, `NLGEOM,OFF`), which was the page's own solve. Since [ADR-0142](ADR-0142-a-plate-that-deflects-far-is-followed-by-calculix-alone-under-our-composite-layer-proven-first-on-problems-with-exact-or-published-answers-and-the-tension-coupon-stays-linear.md) step 2 a plate's Analysis step can ask for nonlinear geometry, and the founder's plan for that step says the downloaded files are written with it on, to match (his card choice "Build steps 1 and 2", 2026-11-25).

**Options.** (a) Keep the files linear and say so on the page: rejected, an engineer who runs the file would get the linear answer beside our followed one and read the difference as a fault. (b) Write the step with the switch on in the file a person downloads, in the tenths of the load our own solve is read at, and keep the deck our kernel reads and a run hashes as it was: chosen. (c) Also refuse the download for a plate our own followed solve does not take (more than 13 plies, or too fine a mesh): rejected, those limits are our solver's and the file is for another program.

**Decision.** (b).

- Abaqus (`write_abaqus_download`, `FOLLOWED_STEP` in `fea/src/anisotropy_fea/write_abaqus.py`): `*Step, name=Step-1, nlgeom=YES, inc=200`, `*Static`, `0.1, 1., 1e-06, 0.1`, with a comment that the step follows the plate's shape in increments of a tenth of the load and that the answer does not scale.
- Ansys (`fea/src/anisotropy_fea/write_ansys.py`): `NLGEOM,ON`, `AUTOTS,ON`, `NSUBST,10,200,10`, `KBC,0`, `OUTRES,ALL,ALL`, with the same said in its comments.
- `write_abaqus` without `followed` is the deck it was, to the character: the kernel is linear and never reads the switch.
- The files state no large-strain law. A program that relates other stress and strain measures than ours will differ from our followed answer at strains of percents; on a plate that bends, the difference is small (ADR-0142, the stretch rule).

**Evidence.** `cd fea && uv run pytest -q -p no:cacheprovider tests/test_followed_plate.py -k "downloaded or another_program"`: 2 passed; the Abaqus download holds the step line and the kernel's deck holds `nlgeom=NO`, the Ansys download holds `NLGEOM,ON`, and a plate of 14 plies, and one meshed too fine, pass the download's setup check with the switch on though a run here is refused. Neither file with the switch on has been run in its program: what the keywords do there is UNVERIFIED (ADR-0133: no result of such a run is stated in this repository).
