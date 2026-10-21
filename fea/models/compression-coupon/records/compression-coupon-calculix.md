# Reading: X840PW-UNC-L1, the compression coupon built the team's way, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name. It is printed as the last section of the model's comparison document (`docs/models/build.py`). Numbers quoted here are from the CalculiX run of 2026-10-20 (11.3 s, 0 warnings; re-run 2026-10-21 after the move to one folder per test, every recorded value unchanged to 6e-8 apart from roundoff-sized lateral displacements, ADR-0036; again for the coupon's name, ADR-0038; that latest run is in `.local/fea/compression-coupon/attempts/attempt-03_2026-10-21/run/calculix/`, ADR-0039) and from the kernel solve of the coupled twin. The document's own tables are recomputed at every build.

## What the numbers show

- The spec is our compression coupon in the team's build (ADR-0035): X840-Z60 from the library (Chen 2015, Tables 3.1 and 3.2), [0/45/-45/45/0]s of 0.1 mm plies, the whole 63.5 mm tabs gripped, and the team's names. The geometry keeps the proportions of ASTM D6641: 140 mm by 12 mm with a 13 mm unsupported gauge. The mesh has 0.5 mm rows and 3360 elements, and the coupon is shortened by 0.1 mm. It replaces the IM7/8552 compression coupon as the model we show; the IM7/8552 spec stays as a public-material regression case.
- The grip reaction is -5050.67 N in CalculiX against -5060.13 N in the kernel, a 0.19 % difference. The centre element's strain agrees within 0.4 %: eps_x 0.003034 against 0.003025, and eps_y -0.008468 against -0.008478. Its ten plies' stresses and strains are in the record and agree within the 3 % tolerance, with a 2 % floor.
- The coupled twin gives the same kernel reaction, -5060.13 N. Its first-ply failure factor is 0.953 by maximum stress, at element 1674 in the gauge centre (5.5, 69.75) mm, ply 2 at 45 degrees, in in-plane shear. By Tsai-Hill it is 0.858, at element 1525 beside the lower tab line at the free edge (0.5, 63.75) mm, ply 2. So first damage comes at about 0.09 mm of shortening, about 0.7 % nominal strain over the 13 mm gauge.

## What explains the differences

- The 0.19 % on the reaction is the difference between our bilinear kernel element and CalculiX's eight-node S8R once plane stress is stated (ADR-0030, amendment 1). It is the same size as on the tension coupon.
- The Tsai-Hill location sits at the tab-line corner, where a rigid tab meets a free edge. That corner is singular, so the factor there depends on the mesh. Read it as "first damage starts at the grip", not as a converged number. The maximum-stress location in the gauge is not singular.

## Verified, and not

- Verified by this record: the reactions, the centre node's displacement, and the centre element's strain with all ten plies' stresses and strains in material axes.
- UNVERIFIED: buckling of the 13 mm gauge, because the model is linear and in-plane. Also unverified: the first-ply-failure factor against any solver, because CalculiX prints none and the team has not built this coupon, and the material's test conditions, which the dissertation does not give.

## What would settle the open items

Have the team build or import the generated deck `fea/models/compression-coupon/decks/compression-coupon-abaqus.inp` and export per `docs/abaqus-export-recipe.md`. When they build it themselves, seed our spec as they seed theirs and run `docs/models/team.py`.
