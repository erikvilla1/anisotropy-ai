# Reading: the open-hole IM7/8552 coupon, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name. It is printed as the last section of the model's comparison document (`docs/models/build.py`). Numbers quoted here are the ones in the record and in the chunk A2 evaluation note, `docs/evaluations/fea/2026-10-19-gmsh-open-hole.md`; the document's own tables are recomputed at every build.

## What the numbers show

- The coupon is the first model on the Gmsh O-grid (ADR-0030, amendment 3): 36 mm by 300 mm, a 6 mm hole, 3168 quadrilaterals, 32 nodes around the hole, 50 mm tabs gripped whole. CalculiX ran the same corner nodes as S8R (9880 nodes).
- Every recorded value agrees with the kernel within the record's 3 % tolerance (floor 2 %): the grip reactions (15863 N in CalculiX against 15915 N in the kernel, 0.3 %), the displacement of the `gauge` node 50 mm below the hole (0.2456 mm against 0.2458 mm), and the strain, the eight plies' stresses and strains in material axes at the `far` element beside it (within 0.15 %).
- The record stops there on purpose. Beside the hole (`hole_side`, the element whose centroid is 0.2 mm from the hole edge on the net section) CalculiX's mean strain is [-0.00138, 0.01373, 0.00433] against the kernel's centroid value [-0.00340, 0.01312, 0.00286]; at the top of the hole (`hole_top`) [-0.00408, 0.00107, -0.00035] against [-0.00384, 0.00100, 0.00046]. The axial strain beside the hole agrees within 5 %; the small transverse and shear components do not. The hole-edge node's lateral displacement differs by 9 % (-0.0172 mm against -0.0158 mm), and CalculiX gives the node at the top of the hole a lateral displacement of 0.0007 mm where symmetry and the kernel give zero.

## What explains the differences

- The two formulations differ most where the field has a gradient: the kernel's bilinear four-node element gives one centroid value, CalculiX's eight-node shell expanded to a twenty-node brick gives the mean of its integration points over an element that spans the same corners but bends with the stress concentration. On the free edge of the hole the small components are differences of large numbers. The isotropic Kirsch case (`fea/checks/cases/open-hole-isotropic-kirsch.toml`) shows the same element on a finer O-grid converging to the closed form: 1.8 % of the far-field stress beside the hole at the committed mesh, 1.0 % one refinement finer.
- The spec states `plane_stress = true`, so CalculiX's three-dimensional law carries nu13 = nu23 = 0 and does not couple the plies' thickness contraction (ADR-0030, amendment 1); the reaction difference of 0.3 % is the element difference alone, the same size as on the unnotched coupon.

## Verified, and not

- Verified by this record: reactions, the gauge displacement, the gauge element's strain and all eight plies' stresses and strains in material axes on a mesh that is not a structured rectangle; the layer order and orientation handling carry over from the unnotched record.
- UNVERIFIED: agreement beside the hole and at its top in displacement and strain (waits for the eight-node element in the kernel, chunk E, which removes the formulation difference), the first-ply-failure factor against a solver's failure output (CalculiX prints none; the kernel's factor is 0.59 of the 1 mm pull by maximum stress, ply 2 beside the hole), and any Abaqus run of this coupon (the team has not run it).

## What would settle the open items

Run the same spec with the kernel's eight-node element and record the `hole_side` and `hole_top` probes; have the team run the generated Abaqus deck `fea/checks/open-hole-im7-8552/decks/open-hole-im7-8552-abaqus.inp` and export per the recipe in `docs/abaqus-export-recipe.md`.
