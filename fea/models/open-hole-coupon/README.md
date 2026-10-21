# open-hole-coupon

Our open-hole tension coupon built the team's way: X840-Z60, [0/45/-45/45/0]s of 0.1 mm plies, the whole 50 mm tabs coupled to reference points, the team's names. D5766 proportions: 36 mm by 300 mm with a 6 mm hole (d/w = 1/6), on the Gmsh O-grid (3168 elements, 32 nodes around the hole), pulled 1 mm.

**Status.** The team has not built it yet. When they do, put their files in `.local/fea/open-hole-coupon/team/<date>/`, mesh our spec as they mesh theirs, and add a team comparison.

**Record.** CalculiX 2.22 against our kernel: 69 of 69 values within 3 %, away from the hole; reaction 9415.73 N against 9420.94 N (0.06 %). Beside the hole the two element formulations differ in the small components, which the reading explains. Reading: [records/open-hole-coupon-calculix.md](records/open-hole-coupon-calculix.md).

| File | What it is |
| --- | --- |
| `open-hole-coupon.toml` | the spec of the team's build; its deck `decks/open-hole-coupon-abaqus.inp` is the one to open in Abaqus/CAE (File, Import, Model) |
| `open-hole-coupon-nodal.toml` | the CalculiX twin: the same grips as direct constraints on the tab nodes, because CalculiX reports no reaction at a coupled reference node |
| `decks/` | the decks written from the two specs; never edited by hand |
| `records/` | the CalculiX record and its reading |

## Rebuild

From `fea/`:

```sh
uv run python tools/regenerate_decks.py open-hole-coupon open-hole-coupon-nodal
uv run python examples/build_model.py models/open-hole-coupon/open-hole-coupon.toml --out ../.local/fea/open-hole-coupon/runs/kernel
uv run python examples/run_calculix.py models/open-hole-coupon/open-hole-coupon-nodal.toml --out ../.local/fea/open-hole-coupon/runs/calculix
uv run python tools/record_from_dat.py models/open-hole-coupon/open-hole-coupon-nodal.toml ../.local/fea/open-hole-coupon/runs/calculix/open-hole-coupon-nodal-ccx.dat \
    --version 2.22 --run-by "..." --machine "..." --tolerance 0.03 --floor 0.02 --element-probes far --node-probes gauge --out models/open-hole-coupon/records/open-hole-coupon-calculix.toml
```

From the repository root, the record's document: `uv run --project fea python docs/models/build.py fea/models/open-hole-coupon/records/open-hole-coupon-calculix.toml`.
