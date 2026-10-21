# fea/models

The models we show the team, one folder per test (ADR-0036). Each one is built the way the team builds its coupons: their material (X840-Z60 from our library, Chen 2015, Tables 3.1 and 3.2), their layup [0/45/-45/45/0]s of 0.1 mm plies, the whole tabs coupled to reference points, and their names (ADR-0035).

| Test | Kind | Team built it? | CalculiX against our kernel |
| --- | --- | --- | --- |
| [tension-coupon](tension-coupon/README.md) | tension, 10 mm by 80 mm, 15 mm tabs, meshed node for node as the team's deck | yes, 2026-10-16; compared side by side | 69 of 69 within 3 %, reaction 0.10 % |
| [compression-coupon](compression-coupon/README.md) | compression, D6641 style, 140 mm by 12 mm, 13 mm gauge | not yet | 69 of 69 within 3 %, reaction 0.19 % |
| [open-hole-coupon](open-hole-coupon/README.md) | open-hole tension, D5766 proportions, 36 mm by 300 mm, 6 mm hole | not yet | 69 of 69 within 3 %, reaction 0.06 % |

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

1. Create `fea/models/<test>/` with `<test>.toml` and `<test>-nodal.toml`. Copy a neighbour's spec and change the geometry, mesh, loading and probes. When the team has built the coupon, seed the mesh as they seeded theirs (`mesh.y_partitions`, `mesh.y_seeds`).
2. From `fea/`, write its decks with `uv run python tools/regenerate_decks.py <test> <test>-nodal --ccx`.
3. Run CalculiX: `uv run python examples/run_calculix.py models/<test>/<test>-nodal.toml --out ../.local/fea/<test>/runs/calculix`.
4. Write the record: `uv run python tools/record_from_dat.py models/<test>/<test>-nodal.toml ../.local/fea/<test>/runs/calculix/<test>-nodal-ccx.dat --version 2.22 --run-by "..." --machine "..." --tolerance 0.03 --floor 0.02 --element-probes centre --out models/<test>/records/<test>-calculix.toml`. Then write `<test>-calculix.md` beside it.
5. Add the test's README and its row above. The tests pick up the new folder by themselves.
