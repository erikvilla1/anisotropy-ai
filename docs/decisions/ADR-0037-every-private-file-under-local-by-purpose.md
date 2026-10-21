# ADR-0037: Every private file lives under .local, in a folder named for its purpose

- Status: Proposed
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (by purpose; delete the old logs, merged-PR drafts and the pre-cleanup copy; keep the purge backups; fold `References/` and `output/` in) | Drafted by: Claude Code
- Related: `.local/README.md`, [ADR-0018](ADR-0018-source-rights-classes.md), [ADR-0036](ADR-0036-one-folder-per-fea-test.md), the `workspace-layout` skill, [evaluation](../evaluations/2026-10-21-local-by-purpose.md)

## Context

After the FEA folders were reorganized (ADR-0036), the founder asked for the same on the rest of `.local/`. Its top level held 20 folders and about 50 loose files: source copies, research work, screenshots, preview scripts, logs, old pull-request drafts, a pre-cleanup copy of the source viewer, an empty `worktrees` folder and the history-purge backups. Two more git-ignored folders sat at the repository root: `References/`, the dated reference snapshots that `scripts/build-reference-archive.ts` writes, and `output/`, holding a built manual and a roadmap PDF. Four pieces of code name these paths: the course appendix copy in `lib/materials.ts`, the reference-archive script, the material-monitor database, and the calculator browser test's screenshots.

## Options considered

1. **By purpose.** About ten folders, each named for what it holds: `sources/`, `research/`, `website/`, `manual/`, `services/`, `notes/` and `backup/`, beside `fea/`, `homework/` and `questions/`. No loose files at the top, and `References/` and `output/` folded in. Chosen.
2. **Minimal.** Keep today's folders and sweep only the loose files into a few new ones. Rejected by the founder, because the source copies and research work would stay spread over twelve top-level folders.
3. **Leave the root folders.** This keeps two places for private files. Rejected by the founder.

## Decision

Option 1.

- **Sources.** `sources/` holds the copies of the documents our values cite (ADR-0018): `ncamp/`, `nasa/`, `milhdbk/`, `cmh17/`, `textbook-daniel-ishai/`, `textbook-evidence/`, `course/`, and `references/<date>/` (the former `References/`).
- **Code paths.** The paths in code move with the files:
  - `lib/materials.ts` points to `.local/sources/course/`;
  - the reference archive reads `.local/sources/cmh17/` and `.local/research/` and writes `.local/sources/references/<date>/` by default;
  - the textbook-evidence renderer writes `.local/sources/textbook-evidence/`;
  - the material monitor's database is `.local/services/material-monitor/monitor.sqlite`;
  - the calculator test saves to `.local/website/screenshots/`.
- **Deletions.** The leftovers the founder approved are deleted: the logs, the drafts of merged pull requests, the pre-cleanup source-viewer copy and the empty `worktrees` folder.
- **Backups.** The purge backups stay in `backup/`.
- **Ignore rules.** The `.gitignore` rules for `References/` and `output/` stay as a safety net, and a test requires the first one.

## Why (evidence)

- The before and after inventories account for every file: 698 moved unchanged, 23 scripts moved with their paths updated, 22 deleted as approved, and 1 new README.
- The two scripts with relative imports of repository code resolve from their new folders. `check-latex.ts` ran and rendered all 84 expressions.
- `npm test` reports 71 passing and none skipped, so the course appendix test found its copy at the new path. `npm run typecheck` is clean. The local FEA tests pass. Output is in the evaluation note.

## Consequences

- **One place for private files.** Every private file is under `.local/`, and its README says which folder holds what.
- **Changing a path.** A script that names a local path must change together with `.local/README.md` and the `workspace-layout` skill.
- **Old references.** Older evaluation notes and ADRs cite the former places.

## How we will know it was wrong

Revisit if a kind of file fits none of the folders twice in a row, or if a script keeps writing outside them.
