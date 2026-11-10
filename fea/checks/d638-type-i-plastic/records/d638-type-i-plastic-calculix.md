# Reading: a plastic dog-bone in the size of ASTM D638-22 Type I, CalculiX 2.21 S8R against the kernel

The reading note of the record with the same name. Numbers quoted here are the ones in the record and the run of 2026-11-10 in a cloud container (CalculiX 2.21 from Ubuntu's `calculix-ccx`); the document's own tables are recomputed at every build.

## What the numbers show

- The coupon is Fig. 1's Type I dog-bone at its least overall size, 165 by 19 mm, narrowing to 13 mm over the 57 mm narrow section with 76 mm fillets, gripped over 25 mm at each end so the grips are 115 mm apart, with an extensometer over the 50 mm gage length (ADR-0075). The material is nominal, one isotropic plastic of E = 3000 MPa and nu = 0.35, 3.2 mm thick, written in both decks as a homogeneous shell section. Its mesh follows the outline with 12 columns and puts node rows on the grip lines, where the fillets meet the narrow section and the full width, and at the extensometer's ends: 1584 elements; CalculiX ran the same corner nodes as S8R.
- Every one of the 19 recorded values agrees with the kernel within the record's 3 % tolerance (floor 2 %): the grip reactions (595.275 N in CalculiX against 594.972 N in the kernel, 0.05 %), the three probe nodes' displacements, and the centre element's strain and stress in material axes.
- The closed form: in the narrow section the stress is the force over 13 by 3.2 mm, so an extensometer there reads E. The extensometer's nodes move 0.130775 and 0.369225 mm along the coupon in CalculiX, a strain of 0.0047690 over 50 mm; through the same functions (`test_quantities`) both solvers' modulus is 3000.5 MPa against the material's 3000 MPa (0.02 %), and the kernel's Poisson's ratio across the narrow section is 0.35006 against 0.35.

## What explains the differences

- The 0.02 % above E is the fillets': the 50 mm gage length ends 3.5 mm from where each fillet starts, and the narrow section's strain is not quite uniform that close to a change of width.
- The 0.05 % between the reactions is the two elements' difference (the kernel's bilinear membrane, CalculiX's S8R expanded to a brick), smaller here than on the laminates' records (0.6 to 0.8 %), whose bricks carry plies with different Poisson's ratios.

## Verified, and not

- Verified by this record: that a dog-bone and a homogeneous isotropic section are written so both solvers read the same coupon, the reactions, the displacements at the extensometer's ends and at the centre, and the centre element's strain and stress; with them, that the virtual extensometer reads the material's modulus.
- UNVERIFIED: anything against a coupon test (no test data), and the D638 quantities a linear model cannot give (tensile strength, yield, elongation at break).
