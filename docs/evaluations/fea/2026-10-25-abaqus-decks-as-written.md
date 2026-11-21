# Evaluation: the generated Abaqus decks run in Abaqus/Standard as written (ADR-0045 amendment 2) | 2026-10-25

- Scope: `write_abaqus` writes one variable per `*El Print` table and wraps heading comments longer than 256 bytes; the `split_print_tables` option is gone; `tools/run_abaqus.py` writes the spec's deck unchanged; `reactions_by_set` moves to `anisotropy_fea.abaqus` and matches the instance name without regard to case. The five committed Abaqus decks are regenerated, and the two committed CalculiX records that name one take its new digest. New tests: the input rules on every spec's deck, the byte-wise wrap, the reactions per grip set; the Abaqus test solves the committed coupling deck itself and checks for no truncation warning.
- Branch: `feat/abaqus-direct-and-ingest` (worktree `Composite_AI-abaqus-pipeline`, from main a71ab87).
- Environment: Windows 11, uv 0.13.0, Python 3.12.14, Gmsh 4.15.2, Abaqus 2025.

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

The open-hole deck, with the tables split and the comments wrapped by characters, drew a truncation warning from Abaqus/Standard: line 7 was 253 characters and 258 bytes (five "·"), and Abaqus reads 256 bytes. The reactions file listed the instance as `"COUPON-1"` against the deck's `*Instance, name=Coupon-1`. After wrapping by bytes, matching the instance without regard to case, regenerating and moving the digests again, the deck is read with no truncation warning and the reactions per grip set are recorded. The committed deck and the deck that was solved have the same SHA-256. The run's output is kept privately.

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
