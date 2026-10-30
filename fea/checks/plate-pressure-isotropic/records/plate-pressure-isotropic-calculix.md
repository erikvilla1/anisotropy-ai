# Reading: the simply supported isotropic plate under pressure, CalculiX 2.22 S8R against the kernel

The reading note of the record with the same name: the first plate stated with supports and loads over named regions (ADR-0054), and the first pressure sent to CalculiX through a generated deck. Numbers quoted here are the ones in the record and in the evaluation note `docs/evaluations/fea/2026-10-28-plate-kind.md`; the document's own tables are recomputed at every build.

## What the numbers show

- The centre deflection is 0.6340 mm in CalculiX against 0.6333 mm in the kernel (0.12 %), both toward +z: the CalculiX deck writes the pressure with the opposite sign of the Abaqus deck, as the conventions file records, and the plate moves the way the spec says. The Navier series with transverse shear deformation gives 0.6341 mm for this plate (the validation case `plate-ss-isotropic-uniform-pressure-navier`, the same mesh): the two solvers sit on either side of it within 0.13 %.
- Both faces of the one ply at the centre element agree within 0.04 % on the normal stresses (28.48 MPa in tension on the top face and compression on the bottom, as a pressure toward +z bends the plate) and within 0.5 % on the small shear stress (0.14 MPa against the 28 MPa group).

## What explains the differences

- The two element formulations differ: the kernel's four-node MITC4 flat shell against CalculiX's eight-node shell expanded to a twenty-node brick; on this smooth field they agree to a tenth of a percent, as the bending coupon's record did.
- The reaction totals are left out of the record. CalculiX printed -23.9 N on each edge set against the kernel's -25.3 N (5.5 % short), while its deflection agrees within 0.12 % and the kernel's reactions balance the 100 N load to 1e-11 N: the printed total of a shell node set is incomplete, as the pressure detection plate already showed (5/6 of the load there; `shell_set_totals` in `fea/checks/calculix-conventions.toml`). The cause is UNVERIFIED; the bending coupon's support rows, where every node of a row is in the set, did not show it.

## Verified, and not

- Verified by this record: the pressure's sign and magnitude through both decks, the centre deflection, both faces of the ply at the centre element, and the regions (edges and corner boxes) as node and element sets in both decks.
- UNVERIFIED: the reaction totals of a shell node set in CalculiX; a plate with a hole or with tabs as regions against CalculiX; a plate loaded in its plane through a region against CalculiX (the kernel reproduces the unnotched coupon exactly when the same coupon is stated as a plate, `fea/tests/test_plate_kind.py`).

## What would settle the open items

Print the reaction forces node by node in CalculiX (`*NODE PRINT` without `TOTALS`) on the expanded nodes of a shell set and sum them, to find where the missing share sits; run a plate with a hole region and a tab region against CalculiX.
