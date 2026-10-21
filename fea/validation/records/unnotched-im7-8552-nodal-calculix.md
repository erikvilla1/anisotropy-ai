# Reading: the unnotched IM7/8552 coupon, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name. It is printed as the last section of the model's comparison document (`docs/models/build.py`). Numbers quoted here are the ones in the record and in the chunk B evaluation note, `docs/evaluations/fea/2026-10-15-calculix-first-comparison.md`; the document's own tables are recomputed at every build.

## What the numbers show

- Every one of the 59 recorded values agrees with the kernel within the record's 3 % tolerance (floor 2 %). The largest relative difference is the axial grip reaction, 16162 N in CalculiX against 16212 N in the kernel (0.3 %); the centre element's strain and its eight plies' stresses and strains in material axes agree within 0.1 %.
- The ply stresses settle the layer mapping: the 90-degree plies carry 1181 MPa of sigma_2 in both solvers and the plus and minus 45 plies carry tau_12 of equal magnitude and opposite sign, so the first layer line is the bottom ply and each ply's orientation is honoured (the conventions file).
- Classical laminate theory with free lateral edges (Section 4 of the document) gives the reaction and the centre strain within the tolerance too. The kernel's reaction sits above the free-edge value because the whole tab is gripped and cannot contract laterally; CalculiX's sits between the two.

## What explains the differences

- The two element formulations differ: the kernel's bilinear four-node membrane with full 2 by 2 integration against CalculiX's eight-node shell expanded to a twenty-node brick with reduced integration, transverse shear and a three-dimensional material law. In the uniform field at the centre they agree; beside the grip, where the field has a gradient, they do not: the element one row past the tab differs by up to 20 % on small strain components (shear strain minus 0.000271 against minus 0.000326) and by 4.7 % on the 0-degree ply's sigma_1. Those numbers are reported in the evaluation note and deliberately left out of the record, which holds the centre probe only.
- The spec states `plane_stress = false`, so CalculiX's law couples the plies' thickness contraction through nu13 and nu23 (ADR-0030, amendment 1). On this material the effect is small because E2, and so E3, are small: the committed record kept its numbers when the plane-stress option was added.

## Verified, and not

- Verified by this record: reactions, probe displacements, the centre strain, all eight plies' stresses and strains in material axes, the layer order and orientation handling, the tensor shear convention.
- UNVERIFIED: agreement in the gradient region beside the grips (waits for the eight-node element in the kernel, chunk E, which removes the formulation difference), first-ply-failure factors against a solver's failure output (CalculiX prints none), and any comparison with Abaqus on this generated coupon (the team has not run it).

## What would settle the open items

Run the same spec with the kernel's eight-node element and record the near-grip probe; have the team run the generated Abaqus deck `fea/validation/decks/generated/unnotched-im7-8552-nodal-abaqus.inp` and export per the recipe in `docs/abaqus-export-recipe.md`.
