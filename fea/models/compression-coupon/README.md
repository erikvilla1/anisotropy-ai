# compression-coupon

Our compression coupon built the team's way: X840-Z60, [0/45/-45/45/0]s of 0.1 mm plies, the whole 63.5 mm tabs coupled to reference points, the team's names. D6641-style geometry: 140 mm by 12 mm with a 13 mm unsupported gauge, shortened 0.1 mm. Linear and in-plane: buckling of the gauge is not modelled.

**Status.** The team has not built it yet. When they do, put their files in `.local/fea/compression-coupon/team/<date>/`, seed our spec as they seed theirs, and add a team comparison.

**Record.** CalculiX 2.22 against our kernel: 69 of 69 values within 3 %; reaction -5050.67 N against -5060.13 N (0.19 %). Reading: [records/compression-coupon-calculix.md](records/compression-coupon-calculix.md).

| File | What it is |
| --- | --- |
| `compression-coupon.toml` | the spec of the team's build; its deck `decks/compression-coupon-abaqus.inp` is the one to open in Abaqus/CAE (File, Import, Model) |
| `compression-coupon-nodal.toml` | the CalculiX twin: the same grips as direct constraints on the tab nodes, because CalculiX reports no reaction at a coupled reference node |
| `decks/` | the decks written from the two specs; never edited by hand |
| `records/` | the CalculiX record and its reading |

## Rebuild

From `fea/`:

```sh
uv run python tools/regenerate_decks.py compression-coupon compression-coupon-nodal
uv run python examples/build_model.py models/compression-coupon/compression-coupon.toml --out ../.local/fea/compression-coupon/runs/kernel
uv run python examples/run_calculix.py models/compression-coupon/compression-coupon-nodal.toml --out ../.local/fea/compression-coupon/runs/calculix
uv run python tools/record_from_dat.py models/compression-coupon/compression-coupon-nodal.toml ../.local/fea/compression-coupon/runs/calculix/compression-coupon-nodal-ccx.dat \
    --version 2.22 --run-by "..." --machine "..." --tolerance 0.03 --floor 0.02 --element-probes centre --out models/compression-coupon/records/compression-coupon-calculix.toml
```

From the repository root, the record's document: `uv run --project fea python docs/models/build.py fea/models/compression-coupon/records/compression-coupon-calculix.toml`.
