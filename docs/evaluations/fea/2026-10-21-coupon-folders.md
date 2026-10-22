# Evaluation: coupon folders named by the coupon, with everything inside (ADR-0040, chunk 1) | 2026-10-21

- **Scope.**
  - `fea/models/{tension,compression,open-hole}-coupon/` become `fea/models/X840PW-{UNT,UNC,OHT}-L1/`; their specs, decks and records are renamed with `git mv`, and every committed reference is updated (history excluded).
  - `.local/fea/<old name>/` becomes `.local/fea/<coupon>/{from-team, our-runs, comparison, documents}`.
  - `docs/models/build.py`, `team.py` and `share.py` write into the coupon's `documents/`, and `share/` is removed.
- **Branch:** `feat/coupon-folders`, stacked on `feat/attempt-folders` (#70).

## Commands and captured output

The committed rename and text update:

```text
git mv: 3 folders and 21 files under fea/models/
scripted text replacement: 232 mentions in 47 files (evaluation notes, decision records and CHANGELOG left as written)
```

`uv run python tools/regenerate_decks.py` changes the nine coupon decks, whose headings name the spec file; the seven check decks are unchanged. The three twins were re-run in new attempts (tension 14, compression and open-hole 04) and re-recorded with their notes kept. Number by number against the records before:

```text
X840PW-OHT-L1-calculix.toml: 71 numbers, largest relative change 4.28e-05 (expected.rf.Grip-Top[0]), largest change of a near-zero value 1.7e-11
X840PW-UNC-L1-calculix.toml: 71 numbers, largest relative change 0.00e+00 (None), largest change of a near-zero value 9.3e-17
X840PW-UNT-L1-calculix.toml: 71 numbers, largest relative change 2.92e-08 (expected.ply_stress_local.CFRP-Coupon-1.395.10[2]), largest change of a near-zero value 3.7e-13
   text keys changed (each): ['deck_kernel_sha256', 'deck_reference_sha256']
```

The open-hole change is the lateral reaction, 0.0003806769 N becoming 0.0003806932 N, against 9415.727 N along the coupon. Starting the tension attempt pruned the `.frd` of attempt 12, because attempt 13 has a later CalculiX run.

The local move, checked against an inventory of `.local/fea` taken before it:

```text
{'moved, then edited on purpose': 7, 'moved unchanged': 79, 'deleted: superseded zip (ours)': 2, 'deleted: .frd pruned (attempt 13 is later)': 1,
 'deleted: generated, rebuilt into documents/': 11} | before 100 after 142 | problems 0
```

The rebuild wrote, for the tension coupon (`team.py`, `build.py` on the local record, `share.py`):

```text
.local/fea/X840PW-UNT-L1/documents/
  2026-10-21_X840PW-UNT-L1-comparison.zip   2026-10-21_X840PW-UNT-L1-model.zip
  X840PW-UNT-L1-calculix.pdf   X840PW-UNT-L1-comparison.pdf   tension-test-abaqus.pdf   latex/
```

Compression and open-hole each have their `-calculix.pdf`, model zip and `latex/`. Along the way:

- `docs/models/build.py` printed `69 numbers compared, 69 agree` for each coupon and `1800 numbers compared, 1800 agree` for the local Abaqus record.
- The two old zips in `share/` were confirmed as ours (`zip_is_ours`) before `share/` was removed.
- The stale `docs/models/build/<old name>-calculix/` folders were removed.

Tests from `fea/`: `uv run pytest -q -ra tests ../engine/tests` gives `742 passed in 198.14s`, with none skipped; `test_local_tension_deck.py` and `test_convert_deck.py` read the team deck from `from-team/2026-10-16/`. `tools/case_pages.py --check` reports all five pages current.

## Not run, UNVERIFIED

- CI writing the coupon documents to `.local/fea/*/documents/` and uploading them from there. The workflow path is changed and runs on the pull request.
