# The plate kind: what was checked on 2026-10-28

Part 5 of the studio plan (ADR-0051), decided by the founder on 2026-10-28 ("Coupon first, then general edges") and recorded as ADR-0054: a `plate` kind that states its supports and loads over named regions, pressures included, and the studio's region picking. Everything below ran on the founder's machine (Windows 11, CalculiX 2.22 from the PrePoMax v2.6.0 bundle).

## The same model stated two ways

The unnotched IM7/8552 coupon (`fea/checks/unnotched-im7-8552/unnotched-im7-8552-nodal.toml`) restated as a plate, with its two tab bands as regions (`Tab-Bottom` held in every direction, `Tab-Top` held in every direction but moved 1 mm along y), builds the same mesh and the same deck apart from the set names, and solves to the same numbers: the largest difference in any displacement is 0.0 m and the top reaction is 16211.75 N in both (`fea/tests/test_plate_kind.py`). A plate loaded in its plane stays with the membrane kernel, as the coupon does.

## The pressure plate (`fea/checks/plate-pressure-isotropic/`)

The simply supported isotropic square plate of the validation case `plate-ss-isotropic-uniform-pressure-navier`, stated as a plate: w and the tilt about the edge held on the four edges, the in-plane motion pinned by two corner boxes of 0.1 mm, a pressure of 0.01 MPa toward +z on the face. The kernel gives the case's centre deflection, 0.633255 mm on the same 16 by 16 mesh, and balances the 100 N to 1e-10 N.

Against CalculiX 2.22 S8R through the generated twin, whose `*DLOAD` carries the pressure with the opposite sign as the conventions file records:

| Quantity | CalculiX | Kernel | Difference |
| --- | --- | --- | --- |
| Centre deflection | +0.633999 mm | +0.633255 mm | 0.12 % |
| Normal stress, bottom face of the ply at the centre element | -28.4782 MPa | -28.4680 MPa | 0.04 % |
| Shear stress there (a small component) | 0.1423 MPa | 0.1430 MPa | 0.5 % |

The record holds 13 numbers within 3 %, the worst at 0.16 of the tolerance. The sign is settled end to end: both solvers lift the plate toward +z. The reaction totals are left out: CalculiX printed -23.9 N on each edge set against the kernel's -25.3 N, 5.5 % short of the load its own deflection agrees with; the printed totals of a shell node set are incomplete, as the pressure detection plate had shown (`shell_set_totals` in `fea/checks/calculix-conventions.toml`; cause UNVERIFIED). `tools/record_from_dat.py --no-reactions` states the omission in the record's notes.

## The lists through the form and the checks

The plate's values file (`tests/fixtures/studio-plate/values.json`: the rows plus `supports`, `loads`, `regions`) reads into the same checks as every coupon: the checklist passes its twelve items, the constraints item says every support and "no rigid-body motion is left", the load item says "a pressure of -0.01 MPa on Face along the normal (pushing toward +z)". Without the corner pins the constraints item fails with "translate along x, translate along y, turn about z"; with one edge held the out-of-plane check fails with "tilt about y". The spec refuses an unknown region, a pressure on an edge, a load that is both a force and a pressure, a moving support with two dofs, a box named like a built-in region and a duplicate box; the values file refuses the same by list and entry number (`test_plate_kind.py`, 23 tests).

## The studio

`npm test` (the plate lists, the region options from the form, the regions an element touches, the words); `npm run test:studio`: the plate scenario picks the plate test, adds a support on Edge-Left and a pressure on the face through the panel, checks (the sent values carry the lists and no grips or loading rows), solves against the fixtures and reads the deflection. Clicking an element on the preview names the regions it belongs to with hold and load buttons; the browser test does not click the WebGL canvas (the element lookup is unit-tested instead).

## Not checked

- A plate with a hole region or a tab region against CalculiX: no evidence yet.
- A force spread over an area region against CalculiX: no evidence yet (the consistent area loads are unit-tested for their sum and shares).
- CalculiX's reaction totals on shell node sets: left out of the record until the under-reporting is understood.
