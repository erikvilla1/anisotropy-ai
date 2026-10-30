# ADR-0046: A coupon enters as an Excel input form the team fills in, read into the spec by a tool

- Status: Proposed
- Date: 2026-10-25
- Decided by: Founder, 2026-10-25: an Excel input form like the audit form; the founder runs the engine and the team only fills in the form; solver inputs only for now; a library material by name or the team's own constants with their source, own constants never in the repository. | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/intake.py`, `fea/src/anisotropy_fea/forms.py`, `fea/tools/coupon_form.py`, `fea/tools/coupon_from_form.py`, `fea/tests/test_intake.py`, [ADR-0018](ADR-0018-source-rights-classes.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), [ADR-0043](ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md)

## Context

- **The founder's aim.** The team should produce data with our engine. An engineer states a coupon test, we build and solve it, and the package goes back. The team recreates the model in Abaqus/CAE and audits it. Later the coupon is fabricated and tested, so the engine can be validated against a physical test.
- **What existed.** A coupon was described only by the TOML spec that `spec.py` reads. The documented way to start one was "copy a neighbour's spec". Nothing told an engineer which inputs are needed, in which units, or what is refused. No template existed anywhere in the repository (checked 2026-10-25).
- **Found on the way:**
  - The library has no short material code. The codes in coupon names (X840PW) are chosen by hand.
  - Only four library records give G13 and G23, which every spec and every Abaqus LAMINA material needs.
  - The documented step `regenerate_decks.py <coupon> <coupon>-nodal --ccx` stopped at the coupling spec and never wrote the twin's CalculiX deck.
  - A file could set `si = true` and skip unit conversion.
  - An unknown unit system crashed a tool instead of being refused.
  - The case pages crashed for a coupon that has specs but no CalculiX record yet.
  - The record tool did not create `ours/verification/`.

## Options considered

1. **The team edits the TOML spec.** Rejected:
   - the team would need the tools and the spec's vocabulary;
   - errors would show only when the founder runs it;
   - there are no pick-lists.
2. **A web form.** Rejected for now. There is nothing to host and no accounts yet (ADR-0006, ADR-0027), and it is far more code for one team.
3. **An Excel input form and a reader.** Chosen:
   - the team already fills in the audit form;
   - openpyxl is already a dependency;
   - the founder runs the engine.

## Decision

Option 3.

- **The form.** `fea/tools/coupon_form.py` writes it on demand, so the material list and the versions are current; no binary is kept in the repository. Its sheets:
  - **Coupon:** one labelled row per input in ten blocks, each with its unit and a line of help. The team's cells are yellow, and the fixed words are lists.
  - **How to fill it in.**
  - **Library materials:** the records the engine can resolve, with their constants, strengths, ply thickness, source and rights class.
  - **Record:** hidden; the form version and the engine version.

  The house style is shared with the audit form through `forms.py`.
- **The reader.** `fea/tools/coupon_from_form.py <form>`, through `intake.convert`:
  - It checks the cells and names every problem by its row, all at once (ADR-0003).
  - It names the coupon by the rules the coupon tests enforce: a code means one thing, and one thing has one code. Blank codes are reused or, for a layup, proposed.
  - It renders the team's build and its CalculiX twin, and lets `parse_spec` judge the exact text it will write. A spec refusal is reported with the form rows it concerns.
  - It writes `ours/<coupon>.toml` and `ours/<coupon>-nodal.toml`. It files the form as received in `team/<date>/` with a README, and writes a case-page skeleton when there is none (status in progress; attempt 01 is the intake). Then it prints the next commands.
  - `--replace` rewrites the two specs and nothing else. `--dry-run` writes nothing.
- **Fixed by us**, stated in the specs' comments and on the form:
  - units mm, MPa and N; element order 1;
  - plane stress and transverse isotropy for CalculiX (ADR-0030 amendment 1);
  - probes from the geometry;
  - max stress and Tsai-Hill when the material has strengths, no Tsai-Wu;
  - every output request.
- **Asked of the team every time:** G13 and G23.
- **The mesh.** An element size is turned into seeds with a node row on each tab line. When the team already has an Abaqus model, it gives that model's elements across, partition lines and rows per segment instead, so the audit's B1 row can match node for node. A compression amount is typed as a magnitude.
- **Only the four in-plane tests are offered.** Bending is refused by the model builder today.
- **The team's own constants.**
  - `material.source` marks them, and the engine gives them the rights class `user-supplied` (ADR-0018).
  - The deck heading, the coupon card, the document's material section, the package's `3-material/<name>.csv` and audit row B6 state the source.
  - The team comparison sets each value beside the one in the team's deck.
  - A spec with them may exist only under `.local/` (a test enforces it). They never enter `lib/`.
- **The fixes found on the way.**
  - `regenerate_decks.py` skips a CalculiX deck it cannot write and says why.
  - `parse_spec` refuses the loader's fields in a file, and turns an unknown unit system into a refusal.
  - The case pages and indexes say "no record yet". `coupon.py --all` skips such a coupon.
  - `record_from_dat.py` creates the folder it writes to.

## Why (evidence)

- **Tests, 2026-10-25.**
  - `cd fea && uv run pytest`: 417 passed.
  - `tests/test_intake.py`: 32. The public IM7/8552 stand-in filled in gives a spec equal to the stand-in's. Writer and parser agree. An element size lands a node row on each tab line. 17 refusals each name their row, and several problems come in one message. The open-hole block meshes the hole. The designation rules hold. The filing writes five files, refuses a second reading without `--replace`, and writes nothing on a dry run.
  - `tests/test_coupon_document.py`: two builds with the team's own constants, one without and one with a team deck.
- **End to end on the founder's machine, 2026-10-25,** with the public stand-in filled in on a fresh blank form:
  - The layup code L1 was refused: "L1 already names another stacking sequence on this machine". With the code left blank, the coupon was named IM7-UNT-L2.
  - `regenerate_decks.py IM7-UNT-L2 IM7-UNT-L2-nodal --ccx` wrote three decks and skipped the coupling spec's CalculiX deck by name.
  - `new_attempt.py` made attempt 02.
  - Our engine gave a reaction of 16211.7 N; CalculiX 2.22 gave 16161.3 N on the twin.
  - The record: 57 of 57 values within 3 % (floor 2 %), reaction +0.31 %.
  - `case_pages.py --check` exited 0.
  - `coupon.py IM7-UNT-L2` wrote the package with its PDF, the audit form and `3-material/im7-8552.csv`.
  - The demonstration coupon was then removed from `.local/fea/`.
- **The own-constants path, in a scratch folder:** the coupon IM7OWN-UNT-L1, rights class user-supplied, its deck heading line "material IM7-Team: the team's own constants: the NCAMP IM7/8552 report, typed in by the team; rights class user-supplied".
- **The team's experience with the form:** no evidence yet.

## Consequences

- **Easier.** An engineer states a coupon without our tools or vocabulary. Every refusal names its row. Every coupon starts with the same files, case page and commands. The team's own material data can be used without being published.
- **Harder.** The form's rows and the spec's fields must stay in step: a new spec field needs a row, its key-to-row entry and a test. Spec rules still arrive one at a time, because `validate_spec` stops at the first broken rule.
- **We depend on** the team filling in the form as given, and on openpyxl.

## How we will know it was wrong

- A coupon needs more than two form round trips before it reads.
- The team asks for inputs the form does not offer: bending, m-Pa units, second-order elements, Tsai-Wu, fabrication or test-plan fields.
- The team sends coupons by other means than the form.

## Amendment 1, 2026-10-26 (every row says what it means, and a Definitions sheet; form version 0.2; asked for by the founder)

**Context.** Trying the tools on 2026-10-26, the founder asked what the test kind is, what the mesh counts mean, why the material must be typed, what G13 and G23 are and why they are needed, what the probes are, and which way a 0 degree ply points. The founder then asked for the answers on the form ("I would like definitions to be on the excel sheet as to what it means ... everything that has to be put into the excel sheet ... so that the team doesn't ask questions as well and it is easy to understand what it is that they are inputting"). The form's help beside each row was a few words, often none.

**Options.**
1. Longer help beside each row only. Rejected alone: a row cannot hold an example and the reason behind it without becoming a paragraph.
2. Excel pop-ups on each cell (input messages or comments). Rejected: hidden until a cell is selected, not printed, and an input message holds at most 255 characters.
3. A plain explanation beside every row, and a Definitions sheet with each term, what it means and an example (chosen).

**Decision.** Option 3. `intake.write_blank_form` writes a short explanation beside every row of the sheet Coupon (all but the 14 later ply rows), and a sheet Definitions after the instructions, from `intake.GLOSSARY`: the coupon and its directions, the tests, the layup, the material, loading and grips, the mesh, and what we send back. The sheet states the direction convention our models and the team's Abaqus models share: the coupon lies with its length along y, ply angles are measured from x, so 0 = fibres across the coupon and 90 = fibres along the pull. For G13 and G23 without a measured value it gives the usual estimate for a tape, G13 = G12 and G23 = E2 / 3 (MIL-HDBK-17-3F, section 10.2.4.1, with nu23 = 0.5), and says a woven fabric has no reliable estimate; the form still requires both values. The row Library material shows that instruction until a material is picked. Labels align with the first line of their explanation. Form version 0.2; the reader accepts 0.1 forms unchanged, because the labels are unchanged.

**Evidence.** `cd fea && uv run pytest -q tests/test_intake.py`: 35 passed, among them `test_every_row_says_what_it_means`, `test_the_definitions_answer_the_first_questions` and `test_a_form_of_version_0_1_still_reads`. The blank form was exported to PDF by Excel and read page by page (Coupon two pages, Definitions three). The team's experience with it: no evidence yet.

## Amendment 2, 2026-10-28 (the Failure criterion and f12* rows; form version 0.3; asked for by the founder)

**Context.** The founder wants the engineer to choose the failure criterion in the studio (ADR-0051). The form had no row for it: `FPF_CRITERIA` fixed maximum stress and Tsai-Hill whenever the material had strengths, and Tsai-Wu could not be asked for because its interaction term had no row.

**Options.** (1) Keep the fixed pair and let the studio alone choose: two inputs for one coupon. (2) Two rows on the form, Failure criterion (all, one of the three, or none) and Tsai-Wu interaction f12*, read by the same checks (chosen).

**Decision.** Option 2. "all", the default, reports every criterion the material allows: maximum stress and Tsai-Hill, and Tsai-Wu when f12* is given. A criterion on a material without strengths, Tsai-Wu without f12*, and an f12* outside (-1, 1) are refused by row. The library id is now checked on the form too, so an unknown id names its row instead of the spec's `material.library`. Form version 0.3; a 0.2 form still reads, its new rows blank.

**Evidence.** `cd fea && uv run pytest -q tests/test_intake.py tests/test_values_input.py`: 35 and 28 passed (2026-10-28), among them `test_all_reports_every_criterion_the_material_allows` and the five refusals of `test_a_criterion_the_inputs_cannot_support_is_refused_by_row`. The team's experience: no evidence yet.

## Amendment 3, 2026-10-28 (the same rows as one JSON object, a values file; asked for by the founder)

**Context.** The studio (ADR-0051) sends the form's rows from the browser. This record rejected a web form "for now" because there was nothing to host; the API's coupon jobs (ADR-0050) are now the thing to host.

**Options.** (1) The browser writes an Excel file: a spreadsheet library in the browser to make a file the tool reads back. (2) A second schema of the rows in TypeScript: two sources of truth. (3) One JSON object whose keys are the rows' field keys, read by `intake.read_values` into the same `FormInput` the Excel reader gives, so `check_form` and everything after it are unchanged; the rows' definition exported once to `lib/coupon-form-definition.json` with a drift test (chosen).

**Decision.** Option 3. `form_version` is required and must be the current form's; `angles` may stand in for the ply rows; a mesh row may hold a list; an unknown key is refused by name. `intake.read_input` takes either file by its suffix; `convert` and `fea/tools/run_coupon.py` accept both and file the input in `team/<date>/` on every run, a `--replace` included, so each attempt row has its input. `intake.values_of_spec` reads a coupon's spec back into its rows (a spec in other units, of order 2, without plane stress, or asking for a set of criteria the row does not offer is refused by name), so the studio reopens a coupon to change it. The Excel form stays for the team.

**Evidence.** `fea/tests/test_values_input.py`: 28 passed (2026-10-28): the values give the specs the filled form gives; every refusal names its row; the public coupon and four filled variants read back into the values that made them; a values file is filed with its coupon.

## Amendment 4, 2026-10-28 (the bending tests on the form; form version 0.4)

**Context.** The flat shell kernel (ADR-0053) builds three- and four-point bending coupons from the spec, whose bending kinds the form did not offer ("Three- and four-point bending are not on this form yet").

**Options.** (1) A second form for bending: two files to keep in step. (2) The same form with a bending block, read only for the two bending tests, as the open-hole block is read only for open-hole tension (chosen).

**Decision.** Option 2. The Test row offers three-point bending and four-point bending; a block Bending holds Support span (mm), Overhang (mm, default 0) and Loading span (mm, four-point only); for a bending test the tab length is left blank and the grip rows are ignored, since the coupon rests on two support lines; Length must equal the span plus twice the overhang, stated and checked, not derived; the loading type is displacement, the nose's travel, pushed down by the amount given; the mesh is seeded so that a node row falls on each support and nose line; the results are read at the quarter span (a node and an element), the element beside the nose line being left out of the record. The studio's form shows the bending rows for the bending tests and hides the grips and tabs. The sheet Definitions explains the two tests and the spans.

**Evidence.** `fea/tests/test_intake.py` and `test_values_input.py` with the form at 0.4; the public bending coupon `fea/checks/three-point-im7-8552/` and its browser fixtures `tests/fixtures/studio-bending/`, made from a values file of the form's rows.
