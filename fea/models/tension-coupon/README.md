# tension-coupon

The team's tension coupon: 10 mm by 80 mm, [0/45/-45/45/0]s of 0.1 mm X840-Z60 plies, the 15 mm tabs at each end coupled to a reference point, a 10 mm pull. Meshed node for node as the team's Abaqus deck (partitions at 15, 35.97, 44.03 and 65 mm, seeded 15, 21, 8, 21 and 15 rows) and named as they named it.

**Status.** The team built it in Abaqus/CAE 2026 (Tension-test.inp, 2026-10-16). Our coupled deck is the same model item by item (23 of 23), and their exported S11, S22 and Mises agree with our kernel within 0.43 % from y = 25 to 55 mm. The side-by-side comparison is built locally from `.local/fea/tension-coupon/comparison/team-comparison.toml` by `docs/models/team.py`.

**Record.** CalculiX 2.22 against our kernel: 69 of 69 values within 3 %; reaction 105884 N against 105993 N (0.10 %). Reading: [records/tension-coupon-calculix.md](records/tension-coupon-calculix.md).

| File | What it is |
| --- | --- |
| `tension-coupon.toml` | the spec of the team's build; its deck `decks/tension-coupon-abaqus.inp` is the one to open in Abaqus/CAE (File, Import, Model) |
| `tension-coupon-nodal.toml` | the CalculiX twin: the same grips as direct constraints on the tab nodes, because CalculiX reports no reaction at a coupled reference node |
| `decks/` | the decks written from the two specs; never edited by hand |
| `records/` | the CalculiX record and its reading |

## Rebuild

From `fea/`:

```sh
uv run python tools/regenerate_decks.py tension-coupon tension-coupon-nodal
uv run python examples/build_model.py models/tension-coupon/tension-coupon.toml --out ../.local/fea/tension-coupon/runs/kernel
uv run python examples/run_calculix.py models/tension-coupon/tension-coupon-nodal.toml --out ../.local/fea/tension-coupon/runs/calculix
uv run python tools/record_from_dat.py models/tension-coupon/tension-coupon-nodal.toml ../.local/fea/tension-coupon/runs/calculix/tension-coupon-nodal-ccx.dat \
    --version 2.22 --run-by "..." --machine "..." --tolerance 0.03 --floor 0.02 --element-probes centre --out models/tension-coupon/records/tension-coupon-calculix.toml
```

From the repository root, the record's document: `uv run --project fea python docs/models/build.py fea/models/tension-coupon/records/tension-coupon-calculix.toml`.
