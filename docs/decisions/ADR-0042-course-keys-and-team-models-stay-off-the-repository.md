# ADR-0042: Course answer keys and the team's coupon models stay off the repository and out of its history

- Status: Proposed
- Date: 2026-10-23
- Decided by: Founder, 2026-10-23. Scope: the homework and the team's coupon models; the X840-Z60 material record stays. Storage: `.local/` for now, maybe AWS S3 later. One history rewrite at the end. | Drafted by: Claude Code
- Related: [ADR-0007](ADR-0007-validation-cases-store-numbers-only.md), [ADR-0018](ADR-0018-source-rights-classes.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md) amendment 4, [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md) amendments 1 and 2, risks R-06 and R-16

## Context

- **Access today.** The repository is private, with two accounts (one admin, one write) and no forks, checked 2026-10-23. The founder expects future contributors.
- **Committed today:**
  - 22 homework cases with numbers from the course's answer keys, which ADR-0007 allowed as numbers with a source.
  - The three X840PW coupon models, built to the team's test design, with their records. One record, the team summary, holds numbers compared with the team's Abaqus results (ADR-0030 amendment 4, ADR-0035, ADR-0039).
- **In history only:** the models under their earlier names (`fea/models/tension-coupon/`, `fea/validation/*x840*`) and the homework readings, removed by ADR-0040 amendment 1.
- **The founder's view.** This material is proprietary, for the founders only and not for future contributors.

## Options considered

1. The homework and the team's coupon models leave the tree and the history; the X840-Z60 material record stays. Chosen by the founder.
2. Remove the X840-Z60 record as well. Rejected by the founder: its values come from Chen's 2015 UC San Diego dissertation, which the founder states is a public paper.
   - We have not found a public copy: eScholarship refuses automated requests (HTTP 202), and a search on 2026-10-23 found no record of it.
   - So the record's rights class stays `licensed-reference` until a link is recorded.
3. Only the homework leaves; the models stay. Rejected by the founder.
4. Only the readings leave; ADR-0007 and ADR-0030 stand. Rejected by the founder.
5. Rewrite the history now and again later. Rejected: two force-pushes and two re-clones. One rewrite after every move costs less.
6. A second private repository for the material. Not chosen for now: `.local/` holds it, and AWS S3 may follow.

## Decision

Option 1, in chunks, each a pull request:

- **C2.** The homework cases move to `.local/homework/<set>/ours/`, where `homework.py` finds them. Only course cases covered a temperature change, mixed conditions, several materials and fixed-plus-variable failure, so three constructed cases take their place in CI. Their closed forms are in `engine/validation/closed_forms.py`, which imports nothing from the engine. Rejected: tests that skip without `.local/`, which would leave those features untested in CI. Not yet: textbook sample problems, whose values would need checking against the book's pages.
- **C3.** `fea/models/` moves into each coupon's `.local/fea/<coupon>/`: the specs, `decks/` and `records/` beside the team's files, our runs and the documents, and one case page merged from the committed and local READMEs. `paths.MODELS` points there, so the tools follow. Tests of what only the coupon models had (an identity card, a names table, a seeded mesh) read a public stand-in built in the tests from the IM7/8552 check; the tests that need a whole coupon run on the local ones and skip on CI. CI no longer builds coupon documents.
- **C4.** Documents that quote homework or team numbers move to `.local/` or lose the numbers. The founder chose:
  - the 18 evaluation notes that are mostly about the team's coupons or the course go to `.local/notes/evaluations/`, the same subpaths; links to them name the local note;
  - the mixed notes, the ADRs, the CHANGELOG and the READMEs keep their text without the team's file names, model details and results or the course's problems and key values;
  - the four tiny IM7/8552 check decks and the test deck helper, which copied the team's size, layup and (one of them) names, become generic: 25 by 100 mm, [0/30/-30/30/0]s, still unbalanced, names of our own; the three patch cases are recomputed with the engine, as their sources state;
  - `lib/materials.ts`, the course appendix's transcribed values, stays under ADR-0018;
  - every file edited here is purged from the history in C5 and re-added clean, losing its per-file history.
- **C5.** One `git filter-repo` rewrite of every path above, under every former name. The founder runs it after bundle backups. Then:
  - check from a fresh clone;
  - ask GitHub Support to remove cached commits;
  - re-create the branches and pull requests;
  - the cofounder re-clones.

Until C5 is done, nothing new from the course or the team is committed. For this material, this replaces three earlier decisions: ADR-0007's committed answer-key cases, ADR-0030 amendment 4's committed coupon specs, and the team summary committed under ADR-0035 and ADR-0039.

## Why (evidence)

- The founder's decision, 2026-10-23.
- Inventory of 2026-10-23 from `git log --all --name-only`:
  - 585 paths ever committed;
  - 22 homework cases and 25 `fea/models/X840PW-*` files in the tree;
  - 5 readings and 30 model files under former names in history only.
- C2, 2026-10-23:
  - 23 cases copied to `.local/homework/<set>/ours/` with identical SHA-256 digests before `git rm`.
  - The engine matches the closed forms on the three constructed cases: 14 of 14, 6 of 6 and 25 of 25 values.
  - `cd engine && uv run pytest`: 421 passed. `cd fea && uv run pytest`: 310 passed. `api/tests/test_cases_api.py`: 10 passed; the rest of the API suite was not run to the end here, because its run-record tests need the Postgres database, which was not running (25 errors, connection timeout).
  - `homework.py --all` from `.local/`: five sets, 380 of 380 values agree.
- C3, 2026-10-23:
  - 22 model files copied to `.local/fea/<coupon>/` with identical SHA-256 digests before `git rm`; the three case pages and the team tests' index regenerate as current from the moved records (`fea/tools/case_pages.py --check`).
  - `cd fea && uv run pytest`: 311 passed on the founder's machine, the deck tests now including the 9 local X840 decks; with `.local/fea/` replaced by an empty folder, as on CI: 292 passed, 7 skipped, each naming the local file it needs.
  - `docs/models/coupon.py --all` into a scratch folder: the three coupon documents and zips build; the rewritten team summary differs from the committed one only in its build date and commit.
- C4, 2026-10-23:
  - 18 notes copied to `.local/notes/evaluations/` with identical SHA-256 digests before `git rm`.
  - The recomputed patch cases are reproduced by the kernel (`tests/test_fe_validation_cases.py`) and equal the live engine recompute (`tests/test_membrane_solve.py`).
  - `cd engine && uv run pytest`: 421 passed. `cd fea && uv run pytest`: 311 passed; with `.local/fea/` replaced by an empty folder, as on CI, 292 passed and 7 skipped. `api/tests/test_cases_api.py`: 10 passed. `case_pages.py --check`: every page current. The manual and the per-problem documents build.
  - A sweep of every committed file for the team's file and part names, the numbers compared with the team's results and the course's problem names and key values finds none outside `.local/`.
- On the legal question itself: no evidence yet. The rights classes have had no legal review (R-14).

## Consequences

- **Easier.** Once C5 is done, new contributors can be given the repository.
- **Harder: testing.** CI checks the engine on public cases only. The course keys and the team's coupons are checked only on the founder's machine.
- **Harder: safekeeping.** `.local/` has no history, and no backup beyond copies made by hand.
- **We depend on** the founder running the rewrite, and on GitHub Support removing cached commits.

## How we will know it was wrong

A fresh clone after C5 still holds a homework case, a team model or a reading. Or a regression on an X840 coupon reaches `main` because no CI ran it.
