# Reading: the three-point bending IM7/8552 coupon, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name: the first comparison of the flat shell kernel (ADR-0053) with another solver on a coupon that bends. Numbers quoted here are the ones in the record and in the evaluation note `docs/evaluations/fea/2026-10-28-plate-bending.md`; the document's own tables are recomputed at every build.

## What the numbers show

- Every one of the recorded values agrees with the kernel within the record's 3 % tolerance (floor 2 %). The nose that pushes the coupon down 1 mm carries 42.58 N in CalculiX against 42.64 N in the kernel (0.12 %), and each support 21.29 N against 21.32 N; the quarter-span deflection is 0.6773 mm against 0.6769 mm (0.05 %).
- At the quarter-span element both faces of all eight plies agree: the fibre stress of the outer 45-degree plies within 0.3 %, the 0-degree plies' fibre stress within 1.3 %, the shear components within 2.3 % and the tiny transverse stress of the 90-degree plies (0.1 MPa against a 112 MPa group) under the floor rule. The bottom face is in tension and the top face in compression, mirror images through the midplane, as a symmetric laminate under pure bending must give, and the two faces on the midplane carry nothing in both solvers.
- The sign conventions hold: the nose moved along -z pushes the coupon down, the supports react upward, and CalculiX's layer order and orientation handling are the ones the conventions file records.

## What explains the differences

- The two element formulations differ: the kernel's four-node MITC4 flat shell with the laminate law and a 5/6 shear correction against CalculiX's eight-node shell expanded to a twenty-node brick with reduced integration and a three-dimensional material law (`plane_stress = true`, so the plies' thickness coupling is removed). Away from the nose they agree to a fraction of a percent on every quantity.
- Under the loading nose, where the line load concentrates and the across-width curvature changes sharply, the element right beside the nose line differs more on its secondary components: the 0-degree plies' fibre stress, which runs across the width, is 30.4 MPa in CalculiX against 32.8 MPa in the kernel (7.8 %) while the main 45-degree fibre stress of 198.7 MPa agrees within 0.15 %. The record holds the quarter-span element only, as the unnotched coupon's record left out its near-grip element (ADR-0049); the nose element's numbers are reported in the evaluation note.
- The printed support and nose totals balance each other to 1e-5 N in CalculiX and to 1e-11 N in the kernel. The under-reporting of shell set totals seen on the pressure detection plate (the conventions file) does not show here: with every node of a support row in the set, the totals are complete.

## Verified, and not

- Verified by this record: the reactions along z, the quarter-span deflection, both faces of all eight plies' stresses and strains in material axes at the quarter-span element, the layer order and orientation handling under bending.
- UNVERIFIED: agreement in the element under the loading nose beyond the main fibre stress; first-ply-failure factors against a solver's failure output (CalculiX prints none); any comparison with Abaqus on this generated coupon (the team has not run it); transverse shear stresses through the thickness, which the shell's law takes as uniform.

## What would settle the open items

Refine the mesh under the nose in both solvers and record the element one row further from the nose line; have the team run the generated Abaqus deck `fea/checks/three-point-im7-8552/decks/three-point-im7-8552-abaqus.inp` with an S4R shell and export per the recipe in `docs/abaqus-export-recipe.md`.
