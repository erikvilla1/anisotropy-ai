# Plate bending by the flat shell kernel: what was checked on 2026-10-28

Part 4 of the studio plan (ADR-0051), decided by the founder on 2026-10-28 ("Include a bending element now") and recorded as ADR-0053. Everything below ran on the founder's machine (Windows 11, CalculiX 2.22 from the PrePoMax v2.6.0 bundle). Numbers are quoted from the runs' output; the cases and the record recompute them on every test run.

## The element on its own (`fea/tests/test_shell_element.py`)

- The MITC4 element matrix is symmetric and has exactly six zero eigenvalues (three translations, three rotations) on a rectangle and on a skewed quadrilateral; no spurious mode.
- A pure bending field, w = -kappa x^2 / 2 and theta_y = kappa x, is carried with constant curvature and zero transverse shear at every point of both elements, and its nodal forces are the edge moments D11 kappa b / 2.
- Pressure loads are consistent and sum to the load; a clockwise element is refused.

## Engine equality under bending (`fea/checks/cases/bend-1x1-im7-engine-equality.toml`)

One unsymmetric IM7/8552 [0/30/-30/90] element under a prescribed uniform curvature of 1 per metre: 64 numbers (w, the rotation, the curvature, N = B kappa, M = D kappa, both faces of the four plies' stresses and strains in material axes, the first-ply-failure factor, ply, face and mode by three criteria) agree with the engine at 1.8e-7 of the 1e-9 tolerance.

## Closed forms (`fea/tools/plate_closed_forms.py`)

The Navier series with transverse shear deformation (Whitney 1987, Chapters 5 and 10) is the exact solution of the theory the element discretizes; the convergence table (`--converge`) gives the centre deflection and the centre-element moment against it:

| Plate | 8 by 8 | 16 by 16 | 32 by 32 |
| --- | --- | --- | --- |
| Isotropic, h/a = 0.01, uniform pressure: w | -0.514 % | -0.126 % | -0.031 % |
| the same: M_x at the centre element | -1.07 % | -0.258 % | -0.064 % |
| Isotropic, h/a = 0.001 (thin): w | -0.515 % | -0.127 % | -0.031 % |
| the same: M_x | -1.07 % | -0.258 % | -0.064 % |
| IM7/8552 [0/90]s, sinusoidal pressure: w | -3.73 % | -0.937 % | -0.234 % |
| the same: M_x | -4.96 % | -1.26 % | -0.315 % |

The thin plate's numbers equal the thick plate's to three digits: the element does not lock (a displacement-based bilinear plate would give a deflection orders of magnitude too small at h/a = 0.001). The committed cases use 16 by 16 elements for the isotropic plates (tolerance 0.5 %) and 32 by 32 for the cross-ply plate (1 %, both faces of every ply included: the worst value at 0.31 of the tolerance). The cantilever strip with nu = 0 on 40 by 4 elements reproduces the Timoshenko beam's tip deflection within 0.016 % (the shear part is 0.5 % of the total) and its tip rotation, root moment and shear force to 1e-9; the Kirchhoff limit of the series gives the tabulated 0.00406 q a^4 / D of a simply supported square plate.

## The membrane reproduced (`fea/tests/test_shell_solve.py`)

The shell on the one-element symmetric coupon with w and the tilts held gives the membrane's u, v, strain, N and in-plane reactions to 1e-12; through the gripped coupon's kinematic couplings to 1e-10. The dispatch sends the in-plane decks to the membrane, whose committed cases and records are unchanged; an unsymmetric layup under tension is refused by the membrane and solved, bending, by the shell.

## The first bending coupon against CalculiX (`fea/checks/three-point-im7-8552/`)

IM7/8552 [45/0/-45/90]s in ASTM D7264 proportions (13 mm wide, 48 mm span, 6 mm overhangs, 1.463 mm thick), the nose pushed down 1 mm, 6 by 30 elements. CalculiX 2.22 S8R against the kernel: 100 recorded numbers within 3 %, the worst at 0.76 of the tolerance.

| Quantity | CalculiX | Kernel | Difference |
| --- | --- | --- | --- |
| Nose reaction | -42.5847 N | -42.635 N | 0.12 % |
| Each support | 21.2923 N | 21.3175 N | 0.12 % |
| Quarter-span deflection | -0.677254 mm | -0.676943 mm | 0.05 % |
| 45-degree plies' fibre stress, quarter element, outer faces | 112.119 MPa | 112.469 MPa | 0.31 % |
| 0-degree plies' fibre stress, quarter element, outer faces | -67.916 MPa | -68.774 MPa | 1.26 % |

Under the loading nose the element beside the nose line differs on its secondary components: the 0-degree plies' fibre stress (across the width) 30.44 MPa in CalculiX against 32.82 MPa in the kernel (7.8 %), the 45-degree fibre stress of 198.7 MPa within 0.15 %. That element is left out of the record, as the unnotched coupon's record left out its near-grip element; the reading note states it.

## CalculiX conventions detected

- A positive `*DLOAD` P on an S8R shell pushes along the element normal: on a 20 by 10 by 1 mm clamped plate under P = 0.01 MPa the free edge moved w = +2.693e-2 mm, the kernel's one MITC4 element on the same plate and sign -3.350e-2 mm (the Abaqus P label, which the kernel follows, is positive against the normal). A CalculiX deck with a pressure must write the opposite sign; none is written yet.
- The clamped shell set's printed total was 1.666667 N for 2 N applied: a shell node set's `*NODE PRINT, TOTALS=YES` may under-report; cause UNVERIFIED. The bending coupon's support and nose totals balance each other to 1e-5 N, so with every node of a row in the set the totals are complete there.

## The whole chain

`fea/examples/build_model.py` on the bending spec writes both decks, solves with the flat shell (nose reaction 42.635 N, supports 21.3175 N each, equilibrium residual 7e-12 N, first-ply failure by Tsai-Wu at 2.16 times the loading in the bottom 45-degree ply under the nose), draws the deflection, the moment, the curvature and the shear force, writes the `.vtu` with faces, the fields JSON and the explanation ("the loading nose carries 42.63 N, pressing the coupon down"); `fea/tools/studio_tool.py fixtures` on the form's values of the same coupon gives the checklist (twelve items passed), the preview (support frames, the nose arrow along -z) and the fields the browser tests read (`tests/fixtures/studio-bending/`).

## Not checked

- Agreement with Abaqus on a bending coupon: no evidence yet.
- A laminate whose plies differ widely in transverse shear stiffness (the 5/6 correction is applied to every laminate alike): no evidence yet.
- The beam-theory hand check of a bending coupon in the coupon document: not built; the document says laminate theory gives no closed form for the deck and stands on the kernel.
