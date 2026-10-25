# ADR-0044: The audit form carries its own summary, the rule's verdict as a formula, and the numbers behind our rows as values

- Status: Proposed
- Date: 2026-10-24
- Decided by: Founder, 2026-10-24 ("complete it all", on the plan for audit form v0.2; the form is the proof that the engine matches Abaqus, and later the fabrication comparison) | Drafted by: Claude Code
- Related: [ADR-0043](ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md), [ADR-0001](ADR-0001-engine-computes-every-number.md), `fea/src/anisotropy_fea/audit.py` (`form_tables`, `write_form`), `fea/tests/test_audit.py`

## Context

The first audit forms (ADR-0043) held the rubric rows, with our results in prose evidence cells, and the verdict as a word the auditor picks. The headline of the proof, how far the team's stresses are from ours and against which tolerance, sat inside a long cell. Nothing on the form told the auditor what verdict the rule gives for the results and findings as entered; a mismatch was found only when the form came back and `read_form` refused it. What the team's next export should include had to be worked out from the rows left Not checked. Excel did not fit the row heights of a file it had not written, and the sheets printed across pages at random. The founder's words, 2026-10-24: the Excel form must be "perfect since this is what is needed as proof to show that our engine is matching with what is being produced in Abaqus".

## Options considered

1. **Formulas for everything,** the counts within tolerance included, over a sheet of the compared values. Rejected: the engine computes every number in a result (ADR-0001); a second computation in Excel would disagree with the PDF and the evidence whenever it differed, and the digest covers our results, not a sheet of values anyone can edit.
2. **Values for everything,** the verdict and the counts included, written when the form is built. Rejected: they would not follow the auditor's entries, which is the point of showing the rule's verdict on the form.
3. **Values for what our tools computed; formulas only for what depends on the auditor's entries** (the rule's verdict, the counts per section, the findings count). Chosen.
4. **A separate summary document** instead of a sheet on the form. Rejected: the PDF already has the audit chapter; the form is what the auditor holds while filling in.

## Decision

Option 3. `write_form` writes version 0.2 of the form:

- on the cover: the rule's verdict as one formula that restates `verdict_of` over the Rubric and Findings sheets (COUNTIF and COUNTIFS only, which Excel and LibreOffice both evaluate); a line per section counting pass, fail, not applicable, not checked and without a result; the findings count; the lines at a glance (the agreement per quantity in the graded band, the reaction, the hand check); the list of what the next export should include, from the `needs` of the rows left Not checked; a legend with an example finding;
- a Results sheet of values: the agreement per quantity and layer in the graded band (values compared, within tolerance, the tolerance, the largest team value, the worst difference and where), the gauge centre against free-edge laminate theory (strains, section forces, ply stresses per ply) with the free length in widths and N_x/N_y at the centre, and the reaction at the loaded grip;
- a Compared values sheet of every paired value, with a filter, left unprotected; the same numbers are in the package's `4-results/`;
- colours for results, verdicts and severities by conditional formatting, so a cell the auditor fills in shows its colour too; Arial throughout; row heights fitted to the text; letter paper, landscape where the sheet is wide, with the header row repeated on every page.

`form_tables` computes the values from the same `Evidence` the rows were scored from. `read_form` reads the first three sheets, in their order, and ignores any that follow; a formula's cached value is never read.

## Why (evidence)

- `fea/tests/test_audit.py` (`test_the_form_computes_the_rule_counts_the_rows_and_shows_the_numbers_behind_them`, `test_a_form_with_the_numbers_behind_it_reads_back`): the rule formula's text against the rule, the section formulas, the glance lines, the list to send, the sheets and their protection, the colours, the fonts and the print setup; a form with the new sheets reads back.
- The tension coupon's form, rebuilt at commit ee58797 and recalculated in Excel 16 through COM, with the auditor's entries scripted: 7 formulas, 0 errors in every scenario. As built, the rule said "no verdict yet: 7 required row(s) have no result other than Not checked"; with every auditor row Pass, "Pass"; plus one open Minor finding, "Pass with observations"; the finding made Major, "Fail"; the finding closed, "Pass"; E1 (required) set to Fail, "Fail"; D5 cleared, "no verdict yet: 1 required row(s)". Each is what `verdict_of` gives (its tests in `fea/tests/test_audit.py`).
- The return path, dry-run on a scratch copy of the tension coupon's folder with the rebuilt form filled in as an auditor would: `read_form` accepted it, `case_pages.file_audit` kept it under `team/<date>/` and wrote the case page's audit block, `coupon.py --check` found "the 15 rows our tools passed in the audit of 2026-10-24 still pass", and a form with one of our results changed was refused by the digest.

## Consequences

- Easier: the auditor sees the verdict the rule gives while filling in, the headline numbers at the top, and what to export next time; the numbers are filterable without opening the CSVs.
- Harder: `write_form` has more to keep in step with `verdict_of`, so a test pins the formula's text to the rule. Row heights are estimates, not Excel's own fit.
- We depend on openpyxl's conditional formatting and page setup (openpyxl is already a dependency, ADR-0015).

## How we will know it was wrong

- A returned form's verdict differs from the rule although the cover showed the rule's verdict.
- Auditors still send findings outside the form, or ask for the numbers behind a row.
- The rule formula and `verdict_of` disagree on any returned form.

## Amendment 1, 2026-10-24 (form v0.3: the cover says what is audited; the record and the headline numbers leave it)

**Context.** The founder, on the first forms of the real coupons: the cover must say the coupon, which files are compared, the attempt, what the sections mean and how to fill in the form; the rest is noise, "a lot of engine commits": the engine commit, the team deck's SHA-256 and our results digest (three hex strings), who built it, the headline numbers, and the counts as long sentences. On the Rubric sheet the evidence was one semicolon-separated cell per row ("too clustered"), and the section name was repeated in every row.

**Options.**
1. Keep the v0.2 cover and shorten its texts. Rejected: the hex strings stay in view.
2. Move how the package was built to a Record sheet at the end (the team deck and its digest, the engine's version and commit, who built it and when, the rubric version, our results digest), the headline numbers to the top of the Results sheet, and leave the cover with the identity (coupon, test, attempt, package), a Files compared block (the team's deck and field reports, our deck, spec and result files, by their place in the package), the auditor's fields with the rule's verdict, a table of the sections with one count per column (pass, fail, N/A, not checked, no result, rows) and the instructions. Chosen.
3. Drop the record from the form. Rejected: a returned form must still name its team deck and show our results were not changed (row A2, `read_form`, `case_pages.file_audit`).

**Decision.** Option 2: `write_form` version 0.3. On the Rubric sheet each section is a banner row above its items, and the auditor's columns are Observation and Cause (ADR-0043 amendment 3). What our tools found is three columns, Team, Ours and Difference (`audit.Found`), one fact per line with the lines of the three columns corresponding, so the team reads its value beside ours; the founder asked for this on 2026-10-24 after a single evidence cell proved "a cluster". A row that involves only us (the hand check, equilibrium, the card) leaves Team empty; a row waiting on the team's export says "left blank, for the team to fill in" there. The chapter stacks the three parts in one cell with bold labels. Cut further the same day, at the founder's request ("too clustered and unclear"): the Record sheet is hidden (the return path still reads it); the counts table and the verdict-rule text are gone; the Verdict is a formula that fills itself and stays blank until every required row has a result, so the auditor enters only a name and a date (`read_form` takes the formula's saved value when the spreadsheet left one and the rule's verdict otherwise, and refuses a mismatch); the cover's "What is compared" block names the values compared and the files each side comes from; the sections are listed with their meaning (`Section.meaning` in the rubric); and no decision record is named anywhere the team reads, on the form or in the audit chapter. Each table of the Results sheet ends with a "How to check" line (`Table.check`) naming the file and the operation that reproduce its numbers: the team's report and 4-results/team-vs-ours.csv for the band, any laminate calculator for the theory columns, and Abaqus on our deck (element label, ply, output) for our engine's columns; the founder asked how the team knows the values are true, and the answer is that they can redo them. The Results and Compared values sheets carry a number format per column, and the gauge-centre table is split into strains and section forces so each has a format of its own. `read_form` reads Cover and Rubric first and the Record sheet by name, and merges the two label sets, the cover's winning. The chapter's "package audited" table shows the same identity and files as the cover. The title of this record stands: the summary that depends on the auditor (the rule's verdict and the counts) is still on the cover; the glance lines are now the first block of the Results sheet.

**Evidence.** The founder's words of 2026-10-24. `cd fea && uv run pytest`: 366 passed on 2026-10-24; `tests/test_audit.py::test_the_form_computes_the_rule_counts_the_rows_and_shows_the_numbers_behind_them` pins the cover's order, the formulas' text, the absence of the commit, the digests and "Run by" from the cover, the banners, the number formats and the Record sheet. The tension coupon's package was rebuilt on 2026-10-24 with the new form; its cover, recalculated in Excel 16 through COM, counts the rows as entered (as built: A 2 pass and 1 fail of 3, B 8 pass and 1 without a result of 9, C 2 pass, 3 not checked and 2 without a result of 7; with every auditor row filled in: 3, 9, 4, 3 and 3 pass) with 0 formula errors.
