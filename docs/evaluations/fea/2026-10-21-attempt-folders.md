# Evaluation: attempt folders, the local index and dated zips (ADR-0039, chunk 2) | 2026-10-21

- **Scope.**
  - `anisotropy_fea.attempts` and `fea/tools/new_attempt.py`.
  - `.local/fea/<test>/runs/` migrated into `attempts/attempt-NN_<date>/`.
  - `case_pages.py --local` writes `.local/INDEX.md`; `.local/sessions/` and `.local/projects/` are new.
  - `team.py` and `share.py` write dated zips.
  - The workspace-layout skill goes to 0.4.0; the `runs/` paths in docstrings and READMEs are updated.
- **Branch:** `feat/attempt-folders`, stacked on `feat/case-pages` (#69).

## The migration

An inventory of `.local/fea` was taken before the move and checked after it, file by file, with a scratch script:

```text
before 93 files, after 129; moved 42, in place 51; problems 0
new files: 36 ['notes.md', 'prompt.md']
```

Each kept run went to the attempt that made it, judged by its deck heading and file times:

| Run kept | Went to | Why |
| --- | --- | --- |
| tension `runs/team-in-calculix` | attempt 04 | its deck's elastic line has nu13 = nu23 = 0, and its files date from 2026-10-16 20:36 (the plane-stress fix) |
| tension `runs/kernel` | attempt 11 | its heading predates the coupon name |
| tension `runs/calculix` | attempt 12 | — |
| compression and open-hole `runs/kernel` | attempt 02 | — |
| compression and open-hole `runs/calculix` | attempt 03 | — |

The other attempts got `notes.md` only, rebuilt from the attempt log, plus a `prompt.md`:

- **Requests.** The founder's message, word for word, where it could be matched after the fact; otherwise "Not recorded".
- **Commits.** A pull request's head commit, labelled as an approximation.
- **Session.** The session is named for attempts made in this one. Pull request #61 was opened 27 minutes into it, so attempts 08 to 12 (tension) and 01 to 03 (compression, open-hole) belong to it.

No `.frd` was deleted: each kind's only run is also its latest. The size is unchanged at 218 MB.

## The first attempt made with the tool

```text
uv run python tools/new_attempt.py tension-coupon --prompt "ok keep going"
attempt folder: .local/fea/tension-coupon/attempts/attempt-13_2026-10-21
notes.md: - Engine commit: 44569f3 + local changes / - Spec: ... tension-coupon-nodal.toml, sha256 2c0ccc3ad3eb7c2c / ...
uv run python examples/run_calculix.py models/tension-coupon/tension-coupon-nodal.toml --out ../.local/fea/tension-coupon/attempts/attempt-13_2026-10-21/run/calculix
```

A record written from that run's `.dat` to a scratch folder, compared number by number with the committed record:

```text
tension-coupon-calculix.toml: 71 numbers, largest relative change 2.92e-08 (expected.ply_stress_local.CFRP-Coupon-1.395.10[2]), largest change of a near-zero value 8.3e-14
   text keys changed: ['deck_kernel', 'deck_reference', 'solver.conventions', 'solver.notes', 'spec']   (relative paths of the scratch copy; the deck digests are equal)
```

Attempt 13 is logged on the case page. The accepted attempt stays 12, because the record did not change.

## The local index

`uv run python tools/case_pages.py --local` writes `.local/INDEX.md`:

- **Team tests:** the attempt folders against the log. Tension has 13 of 13, and compression and open-hole 3 of 3 each.
- **Benchmarks:** the committed table.
- **Homework:** from `.local/homework/README.md`, with the engine cases per HW.
- **Projects:** none yet.

The index found two out-of-date homework statuses. HW2 has 6 engine cases, not 5. HW5 P2 (micromechanics) is covered by two cases, Vf 0.58 and 0.65. The local homework README is corrected. The index first listed a code folder for HW1, which has none, so it now links existing folders only.

## Dated zips

The full rebuild wrote `.local/fea/share/2026-10-21_tension-coupon-comparison.zip` (12 files) and `2026-10-21_our-models.zip` (17 files, 3 coupons):

- each holds one undated folder and no `.frd`;
- the two undated zips were confirmed as ours (`zip_is_ours`) and deleted.

## Tests

From `fea/`:

- `uv run pytest -q tests/test_attempts.py tests/test_case_pages.py tests/test_team_document.py` gives `17 passed`.
- `uv run pytest -q -ra tests ../engine/tests` gives `742 passed in 123.75s`, with none skipped.
- `tools/case_pages.py --check` reports all five pages current.

## Not done, waiting on the founder

- **Session export.** The transcript of session 1a384ccb is not exported yet (`/export` to `.local/sessions/2026-10-21-fea-team-models.md`).
- **OneDrive.** The team's OneDrive path, the master copy of their data, is not in `team/2026-10-16/README.md` yet.
- **Files from the proposal.** `Tension-test-print.inp`, `tension-compare/`, `frd_stress_summary.py` and `benchmark-plan.md` are not on this machine.
- **The checks' local runs.** `.local/fea/checks/<test>/runs/` keeps its layout, because the checks are benchmarks with no attempt logs yet.

## Follow-up the same day: runs only

The founder read the backfilled `notes.md` files and decided that `prompt.md`, `notes.md` and the OneDrive location are not needed, because they add no value. The changes:

- `start_attempt` creates only `attempt-NN_<date>/run/`, NN being the next row of the case page's attempt log (or the last folder plus one, whichever is larger).
- `new_attempt.py` takes no `--prompt`.
- The local index lists the runs kept per attempt instead of counting folders.
- Locally, the 38 `prompt.md` and `notes.md` files were deleted, and the 11 attempt folders left empty were removed: tension 01 to 03 and 05 to 10, compression 01 and open-hole 01.
- What remains holds runs only: tension 04, 11, 12 and 13, and compression and open-hole 02 and 03.

The case pages' attempt logs are the record of every try and are unchanged, apart from their introduction.
