# Evaluation: case pages, attempt logs and the generated indexes (ADR-0039, chunk 1) | 2026-10-21

- **Scope.**
  - `anisotropy_fea.case_pages` and `fea/tools/case_pages.py`.
  - The three model READMEs restructured as case pages, with backfilled attempt logs.
  - The generated tests index (`fea/models/README.md`) and benchmarks index (`fea/checks/README.md`).
  - `docs/models/team.py` writes `records/<test>-team-summary.toml`, and `paths.all_records()` skips it.
- **Branch:** `feat/case-pages`, stacked on `feat/coupon-identity` (#68).

## Commands and captured output

The team summary for the tension coupon, from `uv run --project fea python docs/models/team.py .local/fea/tension-coupon/comparison/team-comparison.toml --no-pdf`:

```text
Figures written to ...\fea\models\tension-coupon\records\tension-coupon-team-summary.toml
[equivalence] items = 23, same = 23, elements_matched = 800, largest_node_offset = 1.87e-06  # mm
inner: S11 600 of 600 (largest 0.00425), S22 600 of 600 (0.00160), Mises 600 of 600 (0.00200); free length: S11 752 of 1000 (0.238)
```

`uv run python tools/case_pages.py` from `fea/`, twice:

```text
first run:  5 file(s) rewritten (three case pages, models/README.md, checks/README.md), 19 s
second run: 0 file(s) rewritten
```

The tension coupon's generated result:

```text
| Values compared (tension-coupon-calculix.toml) | CalculiX 2.22 S8R, 69 values | our kernel | 69 of 69 within 3 % (floor 2 %) |
| Reaction at Grip-Top, along the coupon | 105884 N | 105993 N | +0.10 % |
| Strain eps_y at element CFRP-Coupon-1.395 | 0.20176 | 0.20186 | +0.05 % |
| The model, item by item | the team's Tension-test.inp (Abaqus/CAE 2026, S4R, 2026-10-16) | our generated deck | 23 of 23 the same; nodes within 1.87e-06 mm |
| S11, y 25 to 55 mm | the team's Abaqus, 600 values | our kernel | 600 of 600 within 1 %; largest 0.43 % |
| Whole free length, y 15 to 65 mm | the team's Abaqus | our kernel | largest 23.80 % (S11); the reading says where |
```

The tests index gives X840PW-UNC-L1 3 attempts and a reaction of -0.19 %, X840PW-OHT-L1 3 attempts and +0.06 %, and X840PW-UNT-L1 12 attempts and +0.10 %, with the team's Abaqus inner band within 0.43 %. The benchmarks index has two IM7/8552 records (57 of 57, 59 of 59), six cases and 35 engine validation cases.

## The attempt logs

They are rebuilt from `docs/evaluations/fea/` and the four local notes in `.local/fea/tension-coupon/comparison/notes/`, read in full by a search agent and mapped to pull requests with `git log`. These quotes were checked with `grep` against the files:

- `from +2.8 % to -0.10 %`, `0.93 %`, `printed 0 N`, `20 of 20` and `by up to 4 %` in the evaluation notes;
- `108965`, `108964.8`, `17233`, `15827`, `15838`, `8e-7`, `18626`, `21555`, `25584` and `0.1250` in the local notes.

Uncertainties:

- **The plane-stress note** is dated 2026-10-16, but its commit is dated 2026-10-18.
- **Pull requests #52 to #55** were stacked and reached main through #57.
- **The local notes** were never committed, so the log names them without a link.

Tests from `fea/`: `uv run pytest -q tests/test_case_pages.py tests/test_team_document.py tests/test_records.py` gives `24 passed in 57.97s`. The first full run failed one test: `test_every_test_folder_has_the_same_shape` wanted a reading note beside the team summary, which now has its reading in the local `team-comparison.md`, so the test skips it as `all_records()` does. Then `uv run pytest -q -ra tests ../engine/tests` gives `738 passed in 125.93s`, with none skipped.

## Not done here (chunk 2)

These are planned in ADR-0039 and do not exist yet:

- the attempt folders under `.local/fea/<test>/attempts/`;
- `new_attempt.py`;
- `.local/sessions/`;
- `.local/INDEX.md` for the four categories;
- the dated zips;
- the skill's procedures.
