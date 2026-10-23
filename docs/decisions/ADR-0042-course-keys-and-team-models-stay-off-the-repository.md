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

- **C2.** The homework cases move to `.local/homework/<set>/`. Tests that used them switch to public cases, or skip when the files are absent.
- **C3.** `fea/models/X840PW-*` moves into each coupon's `.local/fea/<coupon>/`. Code, tests and examples switch to the public IM7/8552 set.
- **C4.** Documents that quote homework or team numbers move to `.local/` or lose the numbers.
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
- On the legal question itself: no evidence yet. The rights classes have had no legal review (R-14).

## Consequences

- **Easier.** Once C5 is done, new contributors can be given the repository.
- **Harder: testing.** CI checks the engine on public cases only. The course keys and the team's coupons are checked only on the founder's machine.
- **Harder: safekeeping.** `.local/` has no history, and no backup beyond copies made by hand.
- **We depend on** the founder running the rewrite, and on GitHub Support removing cached commits.

## How we will know it was wrong

A fresh clone after C5 still holds a homework case, a team model or a reading. Or a regression on an X840 coupon reaches `main` because no CI ran it.
