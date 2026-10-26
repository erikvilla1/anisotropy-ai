# Evaluation: the generated Abaqus decks run in Abaqus/Standard as written (ADR-0045 amendment 2) | 2026-10-25

- Scope: `write_abaqus` writes one variable per `*El Print` table and wraps heading comments longer than 256 bytes; the `split_print_tables` option is gone; `tools/run_abaqus.py` writes the spec's deck unchanged; `reactions_by_set` moves to `anisotropy_fea.abaqus` and matches the instance name without regard to case. The five committed Abaqus decks are regenerated, and the two committed CalculiX records that name one take its new digest. New tests: the input rules on every spec's deck, the byte-wise wrap, the reactions per grip set; the Abaqus test solves the committed coupling deck itself and checks for no truncation warning.
- Branch: `feat/abaqus-direct-and-ingest` (worktree `Composite_AI-abaqus-pipeline`, from main a71ab87).
- Environment: Windows 11, uv 0.13.0, Python 3.12.14, Gmsh 4.15.2, Abaqus 2025 under the UCSD teaching licence (one seat per solve).

## Commands and captured output

From `fea/`, before any change: `uv run pytest -q -ra tests ../engine/tests`

```text
781 passed, 7 skipped in 259.39s (0:04:19)
```

`uv run python tools/regenerate_decks.py`, then `git diff --stat main -- fea/checks`:

```text
 .../decks/compression-im7-8552-abaqus.inp          | 11 ++++++--
 .../decks/open-hole-im7-8552-abaqus.inp            | 27 +++++++++++++-----
 .../records/open-hole-im7-8552-calculix.toml       |  2 +-
 .../decks/open-hole-isotropic-kirsch-abaqus.inp    | 32 ++++++++++++++++------
 .../decks/unnotched-im7-8552-coupling-abaqus.inp   | 19 +++++++++----
 .../decks/unnotched-im7-8552-nodal-abaqus.inp      | 19 +++++++++----
 .../records/unnotched-im7-8552-nodal-calculix.toml |  2 +-
```

The two CalculiX decks are unchanged. The digests were moved by a one-off script (not committed) that read each record's deck from git HEAD, checked its digest against the record, compared old and new decks with `deck_equivalence` and solved both with the kernel:

```text
open-hole-im7-8552-calculix.toml: HEAD deck = record digest 0171f31d16d0f228; same model (22 items, largest node offset 0); kernel reaction identical [...]; new digest 8c222726eee8282f
unnotched-im7-8552-nodal-calculix.toml: HEAD deck = record digest e3082666d89e0304; same model (22 items, largest node offset 0); kernel reaction identical [...]; new digest 6e78a4429346d642
```

First direct run, with the tables split and the comments wrapped by characters: `uv run python tools/run_abaqus.py checks/open-hole-im7-8552/open-hole-im7-8552.toml --out ../.local/fea/checks/open-hole-im7-8552/runs/abaqus --tolerance 0.03 --floor 0.02 --element-probes far ...`

```text
Abaqus 2025: 26.0 s, 2 warnings; results in ...
  warning: ***WARNING: Line #7 has been truncated.
  warning: ***WARNING: NO BIAXIAL STRESS LIMIT GIVEN.  DEFAULT F12 USED.
written ...open-hole-im7-8552-abaqus-record.toml | rows per group: {'ply_stress_local': 2, 'ply_mises': 2}
```

Line 7 was 253 characters and 258 bytes (five "·"); the reactions file listed the instance as `"COUPON-1"` against the deck's `*Instance, name=Coupon-1`. After wrapping by bytes, matching the instance without case, regenerating and moving the digests again, the same command:

```text
Abaqus 2025: 26.3 s, 1 warnings; results in ...
  warning: ***WARNING: NO BIAXIAL STRESS LIMIT GIVEN.  DEFAULT F12 USED.
exported open-hole-im7-8552-abaqus-RF.csv: 581 rows, sha256 57bc4f6f4d8b26a0...
written ...open-hole-im7-8552-abaqus-record.toml | rows per group: {'ply_stress_local': 2, 'ply_mises': 2, 'rf': 2}
kernel against the record: 12 numbers compared, 0 outside 0.03 (floor 0.02)
```

`sha256sum` of the committed deck and the run's deck: both `8c222726eee8282f0a4c...`. The `.sta` ends `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`. The record holds `"Grip-Top" = [3.18e-10, 15909.053275]` N; the kernel gave 15915.1 N and CalculiX 15862.6 N on this coupon ([2026-10-19](2026-10-19-gmsh-open-hole.md)).

After every change: `uv run pytest -q -ra tests ../engine/tests`

```text
788 passed, 7 skipped in 207.09s (0:03:27)
```

The seven skips are the local coupon tests: the worktree has no `.local/`. `tests/test_abaqus.py` ran its solve of the committed coupling deck (Abaqus on PATH).

## Reading

- What Abaqus/Standard now runs is the committed deck, byte for byte; before, only CAE's rewrite of it ran, without our print requests.
- The F12 warning stays: the IM7/8552 strengths give no Tsai-Wu interaction term, so Abaqus uses its default for its own Tsai-Wu index. Our stresses do not depend on it.

## Not run, and UNVERIFIED

- The local coupon decks in `.local/fea/<coupon>/ours/decks/` and the digests of the three local CalculiX records are not regenerated here: the worktree has no `.local/`, and the main folder's branch still writes the old text. They are regenerated on the founder's machine once this is on main.
- Abaqus/CAE File > Import of the new decks; the CalculiX runs (their decks did not change).

Options 2 and 5 of the amendment were confirmed by the founder on 2026-10-25 ("do 1-3", on the walkthrough of the two choices).
