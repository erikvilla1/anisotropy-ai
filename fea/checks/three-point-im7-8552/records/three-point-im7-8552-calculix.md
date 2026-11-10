# Reading: the three-point bending IM7/8552 coupon, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name: the first comparison of the flat shell kernel (ADR-0053) with another solver on a coupon that bends. Numbers quoted here are the ones in the record and in the evaluation note `docs/evaluations/fea/2026-10-28-plate-bending.md`; the document's own tables are recomputed at every build.

## What the numbers show

- Every judged value agrees with the kernel within the record's 3 % tolerance (floor 2 %); six strain components of the quarter-span element are written nan and not judged (below). The nose that pushes the coupon down 1 mm carries 98.04 N in CalculiX against 97.96 N in the kernel (0.08 %), and each support 49.02 N against 48.98 N; the quarter-span deflection is 0.6781 mm against 0.6770 mm (0.17 %). With the angles counted from the coupon's length (ADR-0065, the deck regenerated on 2026-11-08) the 0-degree plies' fibres run along the span and the coupon is 2.3 times stiffer in bending than the record of 2026-10-28 read (42.58 N at the nose then, the same laminate turned by 90 degrees).
- At the quarter-span element the main stresses of both faces of all eight plies agree: the 0-degree plies' fibre stress (205.8 MPa against 206.4 MPa, 0.3 %), the 90-degree plies' fibre-direction compression (38.5 against 38.8 MPa, 0.8 %), the 45-degree plies' fibre stress within 2.1 %. The bottom face is in tension and the top face in compression, mirror images through the midplane, as a symmetric laminate under pure bending must give, and the two faces on the midplane carry nothing in both solvers.
- The sign conventions hold: the nose moved along -z pushes the coupon down, the supports react upward, and CalculiX's layer order and orientation handling are the ones the conventions file records.

## What explains the differences

- The two element formulations differ: the kernel's four-node MITC4 flat shell with the laminate law and a 5/6 shear correction against CalculiX's eight-node shell expanded to a twenty-node brick with reduced integration and a three-dimensional material law (`plane_stress = true`, so the plies' thickness coupling is removed). Away from the nose they agree to a fraction of a percent on every quantity.
- The six strain components written nan are the face shear strain of the plies along and across the span (plies 2, 4, 5 and 7, both faces off the midplane): the face twist, 3 % of the largest strain, which the two formulations resolve 14 % apart (8.9e-5 in CalculiX against 7.8e-5 in the kernel at the bottom face of ply 2), just above the floor that admits the matching stress component (0.42 against 0.36 MPa under a 206 MPa group). The same component in the 45-degree plies, their largest (-0.0027), agrees within 0.5 %, and every stress agrees. The nan says the value is stated and not judged; what the two elements do with the twist is UNVERIFIED. Under the loading nose, where the line load concentrates and the across-width curvature changes sharply, the element right beside the nose line differs more still on its secondary components; the record holds the quarter-span element only, as the unnotched coupon's record left out its near-grip element (ADR-0049). The evaluation note of 2026-10-28 reports the nose element's numbers for the laminate as it was then counted.
- The printed support and nose totals balance each other to 1e-5 N in CalculiX and to 1e-11 N in the kernel. The under-reporting of shell set totals seen on the pressure detection plate (the conventions file) does not show here: with every node of a support row in the set, the totals are complete.

## Verified, and not

- Verified by this record: the reactions along z, the quarter-span deflection, both faces of all eight plies' stresses and strains in material axes at the quarter-span element, the layer order and orientation handling under bending.
- UNVERIFIED: agreement in the element under the loading nose beyond the main fibre stress; first-ply-failure factors against a solver's failure output (CalculiX prints none); any comparison with Abaqus on this generated coupon (the team has not run it); transverse shear stresses through the thickness, which the shell's law takes as uniform.

## What would settle the open items

Refine the mesh under the nose in both solvers and record the element one row further from the nose line; have the team run the generated Abaqus deck `fea/checks/three-point-im7-8552/decks/three-point-im7-8552-abaqus.inp` with an S4R shell and export per the recipe in `docs/abaqus-export-recipe.md`.
