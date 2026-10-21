# Reading: the team's tension coupon with the cited X840 / Z60 material, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name. It is printed as the last section of the model's comparison document (`docs/models/build.py`). Numbers quoted here are from the CalculiX run of 2026-10-20 (`.local/fea/calculix-prepomax/tension-coupon/ours/`, 3.2 s, 0 warnings) and the record; the document's own tables are recomputed at every build.

## What the numbers show

- The spec is the team's coupon as our generator writes it: 10 mm by 80 mm, [0/45/-45/45/0]s of 0.1 mm plies, 15 mm tabs gripped whole as nodal constraints, 10 mm pull, 1 mm mesh (800 elements). The material is the library record `x840-z60-pw` (Chen 2015, UC San Diego dissertation, Tables 3.1 and 3.2, printed p. 79), the same constants the team typed into Abaqus/CAE, now cited in the deck header and in the document (ADR-0030, amendment 4).
- The grip reaction is 105884 N in CalculiX against 105993 N in the kernel (0.10 %). The centre element's strain agrees to 0.05 % (eps_y 0.2018 against 0.2019; eps_x -0.07728 against -0.07731); the shear strain there is zero in both to within 1.3e-6. The ten plies' stresses and strains in material axes at the centre are in the record and agree within the 3 % tolerance (floor 2 %).
- First-ply failure, from the kernel on the coupled twin `tension-coupon-x840-coupling` with the strengths of Table 3.2: factor 0.0382 of the applied 10 mm by maximum stress (element 225 beside the bottom tab line, ply 2 at 45 degrees, in-plane shear) and 0.0371 by Tsai-Hill (element 215, ply 2). The 10 mm pull is a 20 % nominal strain; first damage at 0.38 mm of pull, 0.76 % nominal strain, is the physically meaningful number.

## What explains the differences

- The 0.10 % on the reaction is the element difference (bilinear kernel element against CalculiX's S8R) once the through-thickness Poisson coupling is removed by `plane_stress = true` (ADR-0030, amendment 1); with the coupling left in, this fabric showed 2.8 % on the local run of 2026-10-16.
- The near-grip element (one row above the tab line) is left out of the record on purpose, as in the first record: CalculiX's mean strain there is [-0.009961, 0.1637, 0.009662] against the kernel's centroid [-0.009692, 0.1635, 0.009414], 2.8 % and 2.6 % on the two small components that are differences of large numbers beside the singular tab-line corner. The axial strain agrees to 0.1 %.
- First-ply failure sits in the row beside the tab line, the singular corner found in the Abaqus comparison; the factor there is mesh-dependent and should be read as "first damage starts at the grip", not as a converged number.

## Verified, and not

- Verified by this record: reactions, the centre probe's displacement, strain and all ten plies' stresses and strains in material axes, on the team's geometry and layup with the cited material.
- UNVERIFIED: the near-grip element; the first-ply-failure factor against any solver's failure output (CalculiX prints none; the team's Abaqus failure indices are not exported); the material's test methods and conditions, which the dissertation does not give (it states the values were manufacturer-provided, §3.2.1).

## What would settle the open items

Have the team export failure indices from their Abaqus run per `docs/abaqus-export-recipe.md`; run the same spec with the kernel's eight-node element (chunk E) and record the near-grip probe; obtain the manufacturer's data sheet for X840 / Z60 to state the test conditions.
