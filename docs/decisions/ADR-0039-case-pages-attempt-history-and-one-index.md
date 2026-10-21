# ADR-0039: Case pages, attempt history and one index, inside the existing layout

- Status: Proposed
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (keep our layout and add the good parts of the proposal; one folder per attempt, no code copies, result files only for the latest attempt; one transcript per session; index team tests, benchmarks, homework and projects) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/case_pages.py`, `fea/tools/case_pages.py`, `fea/tests/test_case_pages.py`, [ADR-0036](ADR-0036-one-folder-per-fea-test.md), [ADR-0037](ADR-0037-every-private-file-under-local-by-purpose.md), [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md), [evaluation](../evaluations/fea/2026-10-21-case-pages.md)

## Context

The founder brought a proposed folder structure, written outside this repository. It proposes one folder per problem holding the inputs, every attempt (failed ones included) with its prompt, code, engine inputs and outputs, the method, and the answer checked against a reference. A `CASE.md` page would show status, result and attempt log, and an `INDEX.md` would list every case. The aim is that an outside reviewer can see how each problem was solved and how many tries it took.

What we had:

- **The story of a case was spread out.** For the tension coupon it ran across its README, its record, about twelve evaluation notes, four local notes, five ADRs and the CHANGELOG.
- **Runs were overwritten.** `.local/fea/<test>/runs/` held only the last run.
- **Partial indexes.** Two tables were typed by hand: tests in `fea/models/README.md` and local tests in `.local/fea/README.md`.

Parts of the proposal conflict with this repository:

- It assumes the engine sits in a separate repository. `Composite_AI` is the repository that holds the engine, so moving `.local/fea/` to its root would let git commit the team's files (risk R-16).
- `materials/*.toml` would be a second copy of the material library, which already holds each value with its page.
- Copying code into every attempt duplicates git.
- Its draft `CLAUDE.md` would replace ours, which points to `AGENTS.md`.

## Options considered

1. **Keep our layout and add the good parts.** Chosen by the founder:
   - the README of each model folder becomes the case page;
   - the result table and the indexes are generated from the records;
   - the attempt log is kept by hand;
   - attempt folders replace `runs/` locally (chunk 2).
2. **The proposal's tree, git-ignored, at the repository root.** Rejected. It undoes ADR-0036 and ADR-0037, made a day earlier, and one missed ignore rule would commit team data.
3. **A separate folder outside the repository, such as OneDrive.** Rejected. The specs, decks and records that carry the numbers are committed, so the case pages would live apart from them.
4. **Code copies in every attempt, and `materials/` copies.** Rejected. The commit hash identifies the code, and the library identifies the material.

## Decision

Option 1.

- **The case page.** `fea/models/<test>/README.md`, in this order:
  - the coupon's name (ADR-0038);
  - a case line: `**Case.** Category: ... | Status: in progress, verified or validated | Accepted attempt: NN`;
  - the problem;
  - **Result**, generated;
  - **Attempt log**, by hand: the number, date, what was tried, result, outcome and evidence, failed tries included;
  - where to look.
- **What the status words mean.** Verified: our engine agrees with a reference solver. Validated: it agrees with test data.
- **Generated blocks.** `anisotropy_fea.case_pages` writes the text between `<!-- generated: <name> -->` and `<!-- end generated -->`:
  - each page's result, from the CalculiX record and the team summary;
  - the tests index in `fea/models/README.md`, which reads the case lines and attempt counts;
  - the benchmarks index in `fea/checks/README.md`, covering the check records, the cases and the engine's validation cases.

  `fea/tools/case_pages.py` writes them. `fea/tests/test_case_pages.py` fails when one is out of date, so no number is typed by hand.
- **The team summary.** `docs/models/team.py` also writes `records/<test>-team-summary.toml`: the equivalence counts and the agreement per quantity and band. It holds names and a digest of the team's deck but no value from their files. `paths.all_records()` skips it, because it is not a comparison record.
- **The backfilled logs.** The attempt logs were rebuilt from the evaluation notes and local notes. Tension has 12 attempts, including the 2.8 % CalculiX stiffness found on 2026-10-16 and fixed by plane stress, and the open tab-line corner. Compression and open-hole have 3 each.
- **Chunk 2, the local side:**
  - `.local/fea/<test>/attempts/attempt-NN_<date>/{prompt.md, notes.md, run/}` replaces `runs/`;
  - a tool starts each attempt with the engine commit, and keeps `.frd` files only in the latest attempt;
  - `.local/sessions/` holds one transcript per session;
  - `.local/INDEX.md` covers all four categories;
  - the zips are dated;
  - the workspace-layout skill takes on the proposal's procedures.

  Chunk 2 amends the local layout of ADR-0036.

## Why (evidence)

- The generator is idempotent: a second run rewrites 0 files. Its numbers match the records: tension reaction 105884 N against 105993 N, +0.10 %. The team rows match the figures `docs/models/team.py` prints: 23 of 23 items, inner band 0.425 / 0.160 / 0.200 %.
- Every attempt-log row quotes a number found in the note it cites; the evaluation note lists the checks.
- The tests and their output are in the evaluation note.

## Consequences

- **One page per case.** A reviewer opens one page per case and sees the status, the result with its reference, and every try.
- **Keeping it current.** After a record, team summary, case line or attempt log changes, run `tools/case_pages.py`; CI fails otherwise.
- **By hand.** The attempt log stays a hand-written table that cites its evidence.
- **Two digests of one file.** The team summary's digest is of the team deck's bytes as received (`3dfec8ae…`), like the team comparison PDF. The records digest a deck after turning CRLF line ends into LF (`compare.sha256_of`), so the local record `tension-test-abaqus.toml` gives the same file as `844e2174…`. Making them one is left for later.

## How we will know it was wrong

Revisit if the attempt logs fall behind the notes, if reviewers ask for the run files of old attempts (chunk 2 keeps those only from now on), or if the generated tables grow too wide to read.
