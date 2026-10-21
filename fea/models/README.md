# fea/models

The models we show the team, one folder per test (ADR-0036). Each one is built the way the team builds its coupons: their material (X840-Z60 from our library, Chen 2015, Tables 3.1 and 3.2), their layup [0/45/-45/45/0]s of 0.1 mm plies, the whole tabs coupled to reference points, and their names (ADR-0035).

| Coupon | Test | Folder | Size | Team built it? | Test data | CalculiX against our kernel |
| --- | --- | --- | --- | --- | --- | --- |
| **X840PW-UNT-L1** | unnotched tension | [tension-coupon](tension-coupon/README.md) | 80 mm by 10 mm, 15 mm tabs: the team's design, meshed node for node as their deck | yes, Tension-test, 2026-10-16; compared side by side | none yet | 69 of 69 within 3 %, reaction 0.10 % |
| **X840PW-UNC-L1** | unnotched compression | [compression-coupon](compression-coupon/README.md) | 140 mm by 12 mm, 13 mm gauge, in D6641 proportions | not yet | none yet | 69 of 69 within 3 %, reaction 0.19 % |
| **X840PW-OHT-L1** | open-hole tension | [open-hole-coupon](open-hole-coupon/README.md) | 300 mm by 36 mm, 6 mm hole, in D5766 proportions | not yet | none yet | 69 of 69 within 3 %, reaction 0.06 % |

None of these coupons follows a test standard, and none has test data yet: Chen 2015 tested no flat tension, compression or open-hole coupons. The comparisons are solver against solver.

## Coupon names (ADR-0038)

A coupon's name reads `<material>-<test>-<layup>`, and each spec's `[coupon]` table holds it with the rest of its identity card: the standard, where the size comes from, the team's own model and the test data. The name is the title of every document, the folder in `our-models.zip` and the first line of each deck heading. The team's build and its CalculiX twin share one card.

| Code | Means |
| --- | --- |
| X840PW | X840-Z60 plain-weave fabric, library record `x840-z60-pw` (Chen 2015, Table 3.1, the "Fabric" row) |
| UNT, UNC, OHT | unnotched tension, unnotched compression, open-hole tension (from the spec's `kind`; IPS, 3PB and 4PB are reserved for shear and bending) |
| L1 | [0/45/-45/45/0]s, the team's layup |

A new material or layup gets the next code here. `tests/test_coupon.py` refuses a code that means two things, or one thing with two codes.

## What every test folder holds

```
<test>/
  README.md                 what the test is, its status, the commands that rebuild it
  <test>.toml               the team's build: the deck the team imports in Abaqus/CAE
  <test>-nodal.toml         the CalculiX twin: the same grips as direct constraints on the tab nodes
  decks/                    written from the specs by tools/regenerate_decks.py; never edited by hand
    <test>-abaqus.inp       open in Abaqus/CAE with File, Import, Model
    <test>-nodal-abaqus.inp the order-1 twin our kernel solves against CalculiX
    <test>-nodal-ccx.inp    what CalculiX runs (S8R)
  records/
    <test>-calculix.toml    CalculiX against our kernel, numbers with provenance
    <test>-calculix.md      the reading of that record
```

The same test name is used on the founder's machine, in `.local/fea/<test>/`, for the team's files, our runs and the comparison with the team.

## Adding a test

1. Create `fea/models/<test>/` with `<test>.toml` and `<test>-nodal.toml`. Copy a neighbour's spec and change the geometry, mesh, loading and probes. Give both the same `[coupon]` card, with the coupon's name at the start of each title. When the team has built the coupon, seed the mesh as they seeded theirs (`mesh.y_partitions`, `mesh.y_seeds`).
2. From `fea/`, write its decks with `uv run python tools/regenerate_decks.py <test> <test>-nodal --ccx`.
3. Run CalculiX: `uv run python examples/run_calculix.py models/<test>/<test>-nodal.toml --out ../.local/fea/<test>/runs/calculix`.
4. Write the record: `uv run python tools/record_from_dat.py models/<test>/<test>-nodal.toml ../.local/fea/<test>/runs/calculix/<test>-nodal-ccx.dat --version 2.22 --run-by "..." --machine "..." --tolerance 0.03 --floor 0.02 --element-probes centre --notes "..." --out models/<test>/records/<test>-calculix.toml`. Then write `<test>-calculix.md` beside it.
5. Add the test's README and its row above, and any new code to the coupon names. The tests pick up the new folder by themselves.
