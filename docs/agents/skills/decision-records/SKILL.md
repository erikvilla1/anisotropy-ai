---
name: decision-records
description: How to write and amend decision records (ADRs) in docs/decisions of the Anisotropy AI repository. Load whenever a change chooses between alternatives (a library, algorithm, data format, architecture, units or conventions), whenever the founder decides something that changes an earlier ADR, and before changing an ADR's status. Covers new record or amendment, numbering, the Status, Decided by and Related lines, the numbered amendment heading, the As built section, evidence, the index row in docs/README.md and the changelog line.
version: 0.1.0
---

# Decision records

## When to use

Whenever a change chooses between alternatives (AGENTS.md, documentation rule 1), whenever the founder decides something that changes an earlier record, and before changing a record's status. Read `project-rules` first. The template is `docs/decisions/_template.md`. Why we use ADRs and how they are reviewed is in `docs/documentation-guide.md` (Part 2, Document 2).

## New record or amendment

| The change | What to write |
| --- | --- |
| A choice no record covers | A new ADR |
| A change to, or a refinement of, a choice a record already makes | An amendment at the end of that record |
| A later ADR that replaces part or all of an earlier one | The new ADR, plus a note in the earlier record's Status line. Never delete or rewrite the earlier text |
| No choice between alternatives | No ADR; the pull request says "none needed" (`.github/pull_request_template.md`) |

## Procedure: a new record

1. Number: the highest `ADR-NNNN` in `docs/decisions/` plus one. The file is `ADR-NNNN-<the-decision-as-a-choice>.md`, and its title is `# ADR-NNNN: <the decision, stated as a choice>`.
2. Copy `_template.md` and keep its headings exactly. `docs/manual/build.py` (`decisions()`) reads the `# ` title and the `- Status:` and `- Date:` lines. It also reads the sections Context, Options considered, Decision, Why (evidence) and How we will know it was wrong, and it fails if one is missing.
3. Fill the header lines:
   - `- Status: Proposed`. It becomes `Accepted` only when the founder says so.
   - `- Date: YYYY-MM-DD`, the day the record was drafted.
   - `- Decided by: Founder, YYYY-MM-DD ("their words", on what) | Drafted by: Claude Code`. Quote the founder; a later decision appends its own date and words.
   - `- Related:` links to the ADRs and code paths it touches, in the form `[ADR-0030](ADR-0030-<slug>.md)` and `fea/src/...`.
4. Context: facts only. Options considered: every option, the rejected ones with the reason they lost.
5. Why (evidence): link real evidence, such as a test command and its output, a `file:line`, a source URL or a measurement. Where there is none, write "no evidence yet"; mark anything unchecked UNVERIFIED.
6. When the code lands, add `## As built (YYYY-MM-DD)` after the Decision. It lists what was built and where, and names any difference from the plan.
7. Add the record's row to the "Decision records" table in `docs/README.md`: `| [NNNN](decisions/<file>.md) | <one sentence> (proposed) |`.
8. Add one line to `CHANGELOG.md` under Unreleased that names the ADR.

## Procedure: an amendment

1. Add the amendment at the end of the record: `## Amendment N, YYYY-MM-DD (what changed; confirmed by the founder)`. N counts up within the record. Write "confirmed by the founder" only once the founder has confirmed it.
2. Write the body in short bold-led paragraphs: **Context.** what forced the change; **Options.** each one, with the reason for rejecting it; **Decision.** the choice and the founder's words; **Evidence.** what supports it, or "no evidence yet". ADR-0045 amendment 1 and ADR-0043 amendments 1 to 4 are examples.
3. Leave the earlier sections as they were. If the amendment changes what the record decides, add a clause to its Status line, for example `- Status: Proposed; ... since amendment 3`.
4. Extend the record's row in `docs/README.md`, for example `(proposed; the rule for S12, amendment 1)`.
5. Add the CHANGELOG line, naming the ADR and the amendment, for example `(ADR-0045 amendment 1)`.

## Procedure: a later record changes an earlier one

1. The new ADR names the earlier one under Related and says in its Context what it replaces.
2. The earlier record's Status line gets a clause that says what changed and links the new record: `- Status: Proposed; <what changed> by [ADR-NNNN](ADR-NNNN-<slug>.md)`. A full replacement is `- Status: Superseded by ADR-NNNN`. The rest of the earlier record stays as it was.
3. Update both rows in `docs/README.md`.

## Pitfalls

- Never invent evidence or a founder decision. A plan the founder has not accepted is a proposal; say so.
- State what was decided and what supports it, not your own reasoning presented as fact (AGENTS.md, rule 5). Keep entries short (rule 6).
- No private numbers. Do not quote course answer keys, the team's models, or numbers compared with the team's results (ADR-0042). Cite the local file by its `.local/` path instead.
- A rubric row change raises the rubric version (ADR-0043). Never change a row's text without raising it.
- A record's file name and number never change, because other records, code comments and the changelog link to them.

## Verification

- `ls docs/decisions | grep ADR-NNNN` shows one file.
- `grep -c '^## \(Context\|Options considered\|Decision\|Why (evidence)\|Consequences\|How we will know it was wrong\)$' <file>` gives 6.
- Every relative link in the record resolves: `ls` each linked path from `docs/decisions/`.
- `docs/README.md` has the record's row, and `CHANGELOG.md` has its line under Unreleased.
- The file is LF: `tr -cd '\r' < <file> | wc -c` gives 0.
