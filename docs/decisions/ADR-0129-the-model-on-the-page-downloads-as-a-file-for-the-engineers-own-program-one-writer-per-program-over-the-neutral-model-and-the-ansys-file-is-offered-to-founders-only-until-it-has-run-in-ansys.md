# ADR-0129: The model on the page downloads as a file for the engineer's own program, one writer per program over the neutral model, and the Ansys file is offered to founders only until it has run in Ansys

- Status: Proposed; three questions beside the download answered in fixed words since amendment 1; one coupon's Ansys file run in Mechanical APDL, and the file names the maximum stress criterion, since amendment 2
- Date: 2026-11-20
- Decided by: Founder, 2026-11-20 ("essentially what i want is the ability to produce ansys models as well the same way we are able to create abaqus models, our software or browser is FEA or CAD going on but upon request of the user say they ask the AI or something shows with, Download abaqus model, or download ansys model etc.", his ask; then "Downloads, then repair hand calc", his choice on the card "Start building now, and with which piece first?", whose plan has founders seeing the Ansys file and customers keeping the Abaqus one until his check in Ansys). The file's format, its commands, the names of its components, the wording and the gate are the drafter's | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0065](ADR-0065-coupon-ply-angles-are-counted-from-the-coupons-length-axis.md), [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0094](ADR-0094-models-move-to-and-from-abaqus-through-a-connector-under-the-users-own-abaqus-and-one-versioned-bundle-compared-privately.md), [ADR-0111](ADR-0111-the-fea-workspace-sets-a-model-up-in-a-model-tree-on-the-left-in-the-words-of-any-finite-element-program-and-the-chat-changes-the-same-tabs.md), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md), `fea/src/anisotropy_fea/write_ansys.py`, `fea/tools/studio_tool.py`, `api/src/anisotropy_api/main.py`, `lib/model-file.ts`, `components/studio/model-download.tsx`
- Area: fea, api, website, assistant

## Context

- A coupon or a plate set up in the workspace becomes one neutral model, `FEModel` (`fea/src/anisotropy_fea/femodel.py`), and one writer per program turns it into text: `write_abaqus.py` and `write_calculix.py` (ADR-0030). Before this record the Abaqus file reached a person only as one of the files of a finished run, and no file for Ansys existed.
- The founder asked for the same for Ansys, on request: a button, or the assistant, "Download abaqus model, or download ansys model". His team and the first users, students at his school, have Abaqus, Ansys and SolidWorks (2026-11-20).
- Ansys is licensed software. It runs on the founder's PC under his school's academic licence and never on the hosted site, as with Abaqus (ADR-0094). At the time of this record no file of ours has been opened in Ansys.
- The customer's view names no program, with one exception written into the guard: the phrase "Abaqus input file (.inp)" (ADR-0091, `lib/studio-copy.ts`). "Ansys" is not on the banned list.
- A change to what the assistant reads brings its questions (ADR-0121).

## Options considered

1. **One writer per program over the neutral model, the file written on request from the rows as they stand (chosen).** No run is needed, no solver is touched, and the next program is one more writer. The Ansys writer is new code that only a run in Ansys can fully check.
2. **Write the Ansys file through PyMAPDL or PyACP.** They are MIT licensed, but they drive a running, licensed Ansys, so they cannot run on the hosted site. Rejected for the product; they stay useful for the check on the founder's PC.
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
- The Ansys file's standing rests on a check only the founder's PC can make, under an academic licence whose terms for checking a commercial product are not settled.
- The customer's view now holds a second program's name in one phrase, "Ansys input file (.cdb)", once the file opens to customers.

## How we will know it was wrong

- The file does not read into Mechanical APDL without errors, or its reaction at the grip differs from ours by more than 1 %, the mark the Abaqus comparison is held to (ADR-0089), on the first check on the founder's PC.
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

## Amendment 2, 2026-11-20 (one coupon's Ansys file run in Mechanical APDL: it agrees with ours; the file now names the maximum stress criterion; who sees the Ansys file is unchanged; not yet confirmed by the founder)

**Context.** The founder asked for the check to be run for him on his machine ("merge and driv eit for me", 2026-11-20, after the offer "Run the Ansys file once in Mechanical APDL on your PC, or tell me to drive it with you"). The file of the public example coupon (IM7/8552 [45/0/-45/90]s, 250 x 25 mm, 56 mm tabs, 1200 four-node shells, mm-MPa) was run in batch in Mechanical APDL 2026 R1 (build 26.1, "Ansys Mechanical Enterprise Academic Research", the school's licence on the founder's machine), pulled by 1 mm and, as a second file, by 16,000 N. Both read in and solved with no warning. One thing failed: asked for the failure measures of a layer (`PRESOL,FAIL`) with the criteria left at Ansys's own choice, it answered "One or more materials (such as material 1) do not have all required stress or strain strength limits defined. Therefore, no failure criteria are computed." and, in batch, stopped. The file states stress limits (`TB,FCLI` option 1) and no strain limits.

**Options.** (1) Leave the file as it is and tell the engineer to name the criterion: the first thing an engineer asks of a composite in Ansys ends in an error whose cause is not in view. Rejected. (2) Write strain limits too, each strength over its modulus: those are numbers the lamina does not state and nobody measured. Rejected. (3) Name the maximum stress criterion in the file's own post-processing (`FCTYP,DELE,ALL`, `FCTYP,ADD,SMAX`), the one criterion the stated limits serve and the page shows. Chosen. The Tsai-Wu measure stays unnamed: Ansys works it with its own interaction term of -1 unless the coupon states one, and that value is not ours.

**Decision.**

- The writer adds `FCTYP,DELE,ALL` and `FCTYP,ADD,SMAX` after `SET,LAST` when the material states strengths, with a comment that says why.
- The file is taken as checked in Ansys for what was run: an unnotched tension strip of four-node layered shells in mm-MPa, its grips held and moved or held and pulled by a force through a coupled set. Still unchecked there: a pressure (`SFE`, its face and sign), the eight-node shell, a force on nodal grips, a file in metres and pascals, a coupon that states a Tsai-Wu term, reading the file through the window's File menu, and Workbench's External Model.
- The page's line beside the Ansys download becomes "The Ansys file was checked in Ansys on one tension coupon. Compare its reaction with the one shown here before relying on it."
- Who sees the Ansys file does not change: founders and a machine with every test switched on, until the founder's word opens it.

**Evidence.** Runs of 2026-11-20 on the founder's machine, 0 warnings in each; the outputs stay on that machine (`im7check.out`, `im7fail.out`, `im7force.out`, `im7v2.out`) and the inputs are in the project's files, outside the repository. Ours is the kernel's run of the same rows and, for the ply stresses, laminate theory under its reaction.

| Pulled by 1 mm | Mechanical APDL | Ours |
| --- | --- | --- |
| Reaction at the top grip, N | 16,210.30 | 16,211.75 |
| Movement at the gauge centre, mm | 0.50000 | 0.5 |
| Ply 1 (45°): σ1, σ2, τ12, MPa | 413.62, 29.582, -44.911 | 413.65, 29.58, -44.92 |
| Ply 2 (0°) | 1180.6, 0.0548, 0.00004 | 1180.76, 0.05, 0 |
| Ply 3 (-45°) | 413.62, 29.582, 44.911 | 413.65, 29.58, 44.92 |
| Ply 4 (90°) | -353.42, 59.108, -0.00004 | -353.46, 59.11, 0 |

The reaction differs by 0.009 % and no stress by more than 0.03 %; plies 5 to 8 mirror plies 4 to 1. The sign of the shear in the 45° and -45° plies is ours, so the angles, coordinate system 11, the element system and the order of the layers read as written (`SLIST` lists the eight layers bottom-first as the coupon states them; `CSLIST` gives system 11 its x along global y and its y along global -x).

- The strength table: with the maximum stress criterion named, the measure at the gauge centre is 0.49272, 0.46146, 0.49272 and 0.92281 in plies 1 to 4, each the governing stress over its limit (44.911 / 91.149, 1180.6 / 2558.5, 59.108 / 64.052). Over the whole model the largest in ply 4 is 1.0765 in element 281 (and its three mirror images), where ours is 1.0732 in the same element and ply: 0.3 % apart, the cause not examined (the corner values Ansys lists in that element run from 0.908 to 1.245).
- Pulled by 16,000 N: the top grip is one coupled set of 319 nodes that all move 0.987027 mm, where ours is 0.986939 mm (0.009 %, the same ratio as the reactions above); the bottom grip's reaction is -16,000 N; the ply stresses are those of the first run times 0.98703.
- The file as the writer gives it now, with the two `FCTYP` lines inside it, ran the same day with 0 warnings and 0 errors: the same reactions (16,210 N at each grip as `PRRSOL` prints them), and `PRESOL,FAIL` asked after the file had ended, with no criterion named again, lists 0.49272, 0.46146, 0.49272 and 0.92281 for plies 1 to 4. The measures of the two lines above were made on the first file with the same two commands given after it.
- `cd fea && uv run pytest -q tests/test_write_ansys.py tests/test_studio_tool.py`: 32 passed; `npx tsx --test tests/model-file.test.ts tests/assistant-questions.test.ts`: 24 passed (2026-11-20).
- No evidence yet from an engineer's own Ansys, from the window rather than batch, or from any model but this coupon.

