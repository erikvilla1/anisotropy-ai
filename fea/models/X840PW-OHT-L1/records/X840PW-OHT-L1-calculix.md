# Reading: X840PW-OHT-L1, the open-hole coupon built the team's way, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name. It is printed as the last section of the model's comparison document (`docs/models/build.py`). Numbers quoted here are from the CalculiX run of 2026-10-20 (0 warnings; re-run 2026-10-21 after the move to one folder per test, every recorded value unchanged to 6e-8 apart from roundoff-sized lateral displacements, ADR-0036; again for the coupon's name, ADR-0038; that latest run is in `.local/fea/X840PW-OHT-L1/our-runs/attempt-03_2026-10-21/run/calculix/`, ADR-0039) and from the kernel solve of the coupled twin. The document's own tables are recomputed at every build.

## What the numbers show

- The spec is our open-hole coupon in the team's build (ADR-0035): X840-Z60 from the library (Chen 2015, Tables 3.1 and 3.2), [0/45/-45/45/0]s of 0.1 mm plies, the whole 50 mm tabs gripped, and the team's names. The geometry keeps the proportions of ASTM D5766: 36 mm by 300 mm with a 6 mm hole, d/w = 1/6, on the same Gmsh O-grid as before (3168 elements, 32 nodes around the hole). The coupon is pulled 1 mm. It replaces the IM7/8552 open-hole coupon as the model we show; the IM7/8552 spec stays as a public-material regression case.
- Every recorded value agrees with the kernel within the record's 3 % tolerance, with a 2 % floor. The grip reactions are 9415.73 N in CalculiX against 9420.94 N in the kernel, a 0.06 % difference. The gauge node 50 mm below the hole moves 0.245292 mm against 0.2453 mm. The far element and its ten plies agree within 0.06 % on the axial strain.
- The coupled twin gives the same kernel reaction. Its first-ply failure factor is 0.653 by maximum stress and 0.623 by Tsai-Hill. Both are at element 1583 beside the hole on the net section, at (14.88, 149.68) mm, in ply 2 at 45 degrees, in in-plane shear by maximum stress. So first damage comes at about 0.62 mm of pull, 0.31 % nominal strain over the 200 mm free length.

## What explains the differences

- Beside the hole the two formulations differ in the small components, as on the IM7/8552 coupon. At the `hole_side` element CalculiX's mean strain is [-0.004298, 0.0128, 0.002376] against the kernel's centroid [-0.004125, 0.01266, 0.002317], within 1.1 % on the axial strain and 4 % on the transverse strain. The hole-edge node's lateral displacement differs by 2.8 %: -0.01625 mm against -0.01581 mm. Our bilinear element gives one centroid value; CalculiX's S8R averages its integration points over an element that follows the stress concentration. The record therefore stays away from the hole, as the IM7/8552 record did.

## Verified, and not

- Verified by this record: the reactions, the gauge displacement, and the far element's strain with all ten plies' stresses and strains, on the O-grid mesh.
- UNVERIFIED: agreement beside the hole, which waits for the kernel's eight-node element (chunk E). Also unverified: the first-ply-failure factor against any solver, and any Abaqus run of this coupon, because the team has not built it.

## What would settle the open items

Run the same spec with the kernel's eight-node element and record the `hole_side` and `hole_top` probes. Have the team import `fea/models/X840PW-OHT-L1/decks/X840PW-OHT-L1-abaqus.inp` and export per `docs/abaqus-export-recipe.md`.
