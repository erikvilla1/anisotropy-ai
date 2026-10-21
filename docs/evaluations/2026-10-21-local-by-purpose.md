# Evaluation: every private file under .local, by purpose (ADR-0037) | 2026-10-21

- Scope: `.local/` is reorganized into folders named for their purpose: `sources/`, `research/`, `website/`, `manual/`, `services/`, `notes/` and `backup/`, beside `fea/`, `homework/` and `questions/`. The root folders `References/` (now `.local/sources/references/`) and `output/` (split into `.local/manual/` and `.local/notes/project-docs/`) are folded in.
- Deletions approved by the founder on 2026-10-21: 13 logs, 4 drafts of merged pull requests, the pre-cleanup source-viewer copy (a folder, a patch and a screenshot) and the empty `worktrees` folder.
- Code paths updated: `lib/materials.ts`, `scripts/build-reference-archive.ts`, `scripts/render-textbook-evidence.ts`, `services/material-monitor/server.ts` and its README, and `tests/browser/calculator.spec.ts`. Docs updated: `README.md`, three docs, the risk register, `.gitignore` comments and both skills. Inside `.local/`, 22 one-off scripts have their path strings updated and two have their relative imports fixed.
- Branch: `feat/local-by-purpose`, from main.

## Commands and captured output

The inventory before and after, accounted for by a scratch script:

```text
{'deleted (approved leftover)': 22, 'moved unchanged': 698, 'moved, then edited on purpose': 23} | before 743 files, after 722
new files: ['.local/README.md']
problems: 0
```

The top of `.local/` after the move: `backup fea homework manual notes questions research services sources website`, with no loose files except `README.md`.

`npx tsx .local/website/scripts/check-latex.ts`, a moved script with relative imports of `lib/`:

```text
All 29 cards / 84 mathematical expressions render successfully.
```

From the root: `npm test` gives `tests 71, pass 71, fail 0, skipped 0`. With nothing skipped, the course appendix transcription test read `.local/sources/course/material-properties-2026-v2.pdf`. `npm run typecheck` is clean. From `fea/`: `uv run pytest -q -rs tests/test_local_tension_deck.py tests/test_convert_deck.py tests/test_team_document.py` gives `13 passed`.

## Not run, UNVERIFIED

- The material monitor started against its moved database; the file is at the new default path.
- `scripts/build-reference-archive.ts` writing a new snapshot to `.local/sources/references/<date>/`.
- The browser suite saving its calculator screenshots to `.local/website/screenshots/`.
