# Reading: the IM7/8552 coupon under ASTM D3039, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name. Numbers quoted here are the ones in the record and the run's console of 2026-11-08 (`.local/fea/checks/d3039-im7-8552/runs/calculix/`); the document's own tables are recomputed at every build.

## What the numbers show

- The coupon is the public IM7/8552 [45/0/-45/90]s strip in Table 2's size for a balanced and symmetric laminate, 250 by 25 mm, with our 56 mm grips and a 25 mm extensometer at mid-length (ADR-0072). Its mesh puts node rows at the tab lines and at the extensometer's ends, 112.5 and 137.5 mm, and 12 elements across so its two nodes sit on the centre line: 1488 elements; CalculiX ran the same corner nodes as S8R (4737 nodes).
- Every one of the 61 recorded values agrees with the kernel within the record's 3 % tolerance (floor 2 %): the grip reactions (16086 N in CalculiX against 16211 N in the kernel, 0.78 %), the three probe nodes' displacements, and the centre element's strain and its eight plies' stresses and strains in material axes.
- The extensometer's two nodes move 0.408951 and 0.591049 mm along the coupon in both solvers, so both read a strain of 0.007284 over the 25 mm. Through the same functions (`test_quantities`), our chord modulus over 1000 to 3000 microstrain is 60.85 GPa and CalculiX's 60.38 GPa; laminate theory, the engine's ABD, gives the laminate 60.85 GPa along the pull.

## What explains the differences

- The chord modulus differs by the reaction alone: the two strains agree to the seventh significant figure, and the two reactions differ by 0.78 %. Our chord modulus and laminate theory's modulus agree within 0.002 % (60.8494 against 60.8485 GPa); CalculiX's printed grip total is the lower one, as on the open-hole record (15816 N against 15915 N, 0.6 %). Its cause is not settled here.
- The lateral displacement CalculiX gives the extensometer's nodes, ±0.00016 mm against the kernel's exact zero on the centre line, is the expanded brick's asymmetry seen on the open-hole record, within the floor.

## Verified, and not

- Verified by this record: the reactions, the displacements at the extensometer's ends and at the centre, and the centre element's strain and ply values; with them, that the virtual extensometer reads the same strain in both solvers.
- UNVERIFIED: the chord modulus and Poisson's ratio against a coupon test (no test data), and the first-ply-failure stress against any solver's failure output (CalculiX prints none).

## What would settle the open items

A tension test of this laminate to D3039 with an extensometer of the same gauge length, reduced by the standard's equations; the cause of CalculiX's reaction being lower than its strains imply.

## Re-run, 2026-11-11 (ADR-0090)

The spec now holds what the studio's tension screen builds for IM7/8552 [45/0/-45/90]s: G23 = E2 / 3 = 2987.73 MPa, the form's estimate for a tape, in place of a nominal 3000 MPa, and a second element probe on the row beside the bottom tab, left out of this record like the other near-grip probes. CalculiX 2.22 ran the regenerated deck; every recorded value moved in its fifth significant figure or later (the grip reaction 16086.37 N against 16086.43 N), and the numbers quoted above stand as printed.
