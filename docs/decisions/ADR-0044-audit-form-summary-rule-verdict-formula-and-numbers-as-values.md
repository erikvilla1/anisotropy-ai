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
- The formulas on the tension coupon's rebuilt form, recalculated in Excel: see the pull request's walkthrough for the output. UNVERIFIED until it is recorded there.

## Consequences

- Easier: the auditor sees the verdict the rule gives while filling in, the headline numbers at the top, and what to export next time; the numbers are filterable without opening the CSVs.
- Harder: `write_form` has more to keep in step with `verdict_of`, so a test pins the formula's text to the rule. Row heights are estimates, not Excel's own fit.
- We depend on openpyxl's conditional formatting and page setup (openpyxl is already a dependency, ADR-0015).

## How we will know it was wrong

- A returned form's verdict differs from the rule although the cover showed the rule's verdict.
- Auditors still send findings outside the form, or ask for the numbers behind a row.
- The rule formula and `verdict_of` disagree on any returned form.
