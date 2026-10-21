# Evaluation: the generated deck carries the team's names (ADR-0035, amendment 1) | 2026-10-20

- Scope: spec table `[names]` (`spec.Names`, `DEFAULT_NAMES`, name rules). `femodel.FEModel` takes its part and instance and `SectionDefinition` its section set and layup from it, and the Abaqus writer writes the layup name. `compare.reference_quantities` and `examples/run_calculix.py` use the model's instance instead of "Coupon-1". The equivalence check reads matching names as the same and adds a section set and layup row. Deck headers name a source's authors. The tension coupon specs are named as `Tension-test.inp`, and their decks and CalculiX record are regenerated. In `docs/models/team.py`, the share CSVs carry the CAE section name and follow the team's row order.
- Branch: `feat/deck-names`, stacked on `feat/team-comparison` (PR #62).

## Commands and captured output

From `fea/`, the regenerated coupling deck:

```text
21:*Part, name=CFRP-Coupon
1715:*Elset, elset=CompositeLayup-1-1, generate
1720:*Shell Section, elset=CompositeLayup-1-1, composite, orientation=Ori-1, layup=CompositeLayup-1, symmetric
1728:*Instance, name=CFRP-Coupon-1, part=CFRP-Coupon
1852:*Material, name=X840-Z60
```

`uv run python examples/run_calculix.py validation/specs/tension-coupon-x840-nodal.toml --out ../.local/fea/calculix-prepomax/tension-coupon/ours`

```text
CalculiX 2.22: 3.2 s, 0 warnings; results in ..\.local\fea\calculix-prepomax\tension-coupon\ours (.dat, .frd)
Grip-Top: CalculiX total force [0.0410718, 105884] N; kernel [-1.34605e-09, 105993] N
```

The record's keys now read `CFRP-Coupon-1.395`, and the deck that ran equals the committed one.

From the root, `uv run --project fea python docs/models/team.py .local/fea/abaqus/tension-coupon/comparison/team-comparison.toml`:

```text
equivalence: 23 of 23 items the same; largest node offset 1.87e-06 mm; 800 elements matched
inner: S11 600/600 agree, largest difference 0.425 %; S22 600/600 agree, largest difference 0.160 %; Mises 600/600 agree, largest difference 0.200 %
```

Row order of our `ours-S22.csv` against the team's `Test_01_S22.csv` (scratch check):

```text
team rows 3200 ours rows 1600 first block in the same order: True
```

From `fea/`: `uv run pytest -q` gives `269 passed`. The CI command `uv run pytest -q -ra tests ../engine/tests` gives `706 passed in 113.32s`. From `engine/`: `437 passed in 42.79s`.

## What the numbers show

- Under the defaults every committed IM7/8552 deck is unchanged, because the drift test passes. Only the X840 decks changed: their names, and the author in the header.
- The renamed coupling twin is the team's model in every item, names included.

## Not run, UNVERIFIED

- Opening the renamed deck in Abaqus/CAE; there is no licence here.
- Node and element numbering stays ours; the team's numbers are mapped in the share folder's CSVs.
