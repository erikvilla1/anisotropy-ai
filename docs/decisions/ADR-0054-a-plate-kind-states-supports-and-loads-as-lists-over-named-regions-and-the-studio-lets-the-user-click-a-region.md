# ADR-0054: A `plate` coupon kind states its supports and loads as lists over named regions (edges, tabs, the hole's ring, the face, drawn boxes), including pressures; the studio lets the user click a region and hold or load it

- Status: Proposed
- Date: 2026-10-28
- Decided by: Founder, 2026-10-28 ("Coupon first, then general edges", the interaction question of the studio plan: the four coupon tests first, then any edge, tab, hole or face held or loaded; the shape of the spec and the studio's picking are the drafter's proposal) | Drafted by: Claude Code
- Related: [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md) (models from a spec), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (the form and its values file), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md) (part 5 of the studio plan), [ADR-0053](ADR-0053-plate-bending-by-an-mitc4-flat-shell-with-five-dofs-on-the-laminates-a-b-d-and-transverse-shear-stiffness.md) (the flat shell, the pressure sign), `fea/src/anisotropy_fea/spec.py`, `fea/src/anisotropy_fea/femodel.py`, `fea/src/anisotropy_fea/intake.py`, `fea/src/anisotropy_fea/checks.py`, `fea/checks/plate-pressure-isotropic/`, `lib/studio-plate.ts`, `components/studio/plate-panel.tsx`

## Context

The six coupon kinds fix where a coupon is held and loaded: the grips of an in-plane coupon, the supports and noses of a bending coupon. The founder asked for the studio to let an engineer "fix this face, apply 5 kN here, pressure on this surface", after the coupons. The flat shell (ADR-0053) solves bending and pressures; the reader takes `*Dload`; the mesher names the edges and the tab bands, and the Gmsh mesh names the hole's ring. A support or a load that the user picks on the model must be reproducible from a file, so that a spec, a deck, a record and a document can be made from it as for every coupon (ADR-0030, ADR-0001).

## Options considered

1. **A `plate` kind whose spec lists `[[supports]]` (region, dofs, value) and `[[loads]]` (region with dof and total, or region with pressure) over named regions: the four edges, the hole's ring, the whole face, the tabs, and `[[regions]]` boxes the user draws; the studio picks a region by clicking an element of the model and offers to hold or load it.** Chosen. A region is a set in both decks, so the model is stated once and reproduced everywhere; a box is the one free shape, and it stays reproducible.
2. **Arbitrary node picking in the browser (a list of node labels).** Not reproducible from a spec a person can read, and tied to one mesh; a refinement loses it. Rejected.
3. **More sets in `[grips]` and `[loading]` of the coupon kinds.** Two tables that mean one thing each would grow into the lists of option 1 with worse names. Rejected.
4. **A general boundary-condition language (functions of x and y, surfaces, amplitudes).** More than the studio needs now and nothing the records could compare. Rejected for now.

Rules decided with the kind: a plate takes no `[grips]` or `[loading]` table; it needs at least one support and a load or a support that moves; a nonzero support value needs exactly one dof (a length for dofs 1 to 3, radians for 4 to 6); a force is spread over an edge region as consistent edge loads and over an area region as consistent area loads (a quarter of each element's area per corner node, the serendipity weights for eight-node elements); a pressure acts on an area region only and is positive against the plate's normal, as the Abaqus P label (the CalculiX deck writes it with the opposite sign, as ADR-0053 recorded); a plate with a hole is meshed by Gmsh; a plate's end rows are named Edge-Bottom and Edge-Top beside the mesher's Grip names, which a coupon's mesh keeps unchanged. The setup checklist judges the supports by the rank of the rigid modes on the held dofs: the three in-plane motions must be held, and the three out-of-plane ones when anything acts out of the plane. The values file of the form carries the lists (`supports`, `loads`, `regions`) for the plate test only; the Excel form has no rows for them, so a plate is stated from the studio.

## Decision

Build option 1 with the rules above: the spec's `Region`, `Support` and `Load` records and `plate_regions`; the mesher's boxes; `femodel` building boundaries, consistent loads and pressures from the lists, with `Face` as a node and element set; the writers' `*Dload` and `*DLOAD`; the form's lists through `intake.plate_lists` (form 0.5); the checklist's `rigid_modes_left`; the preview's `loads` and `regions`; the studio's plate panel with region picking.

## As built (2026-10-28)

- `spec.py`: `Kind` "plate", `PLATE_KINDS`, `EDGE_REGIONS`, `AREA_REGIONS`, `RESERVED_REGIONS`, `Region`, `Support`, `Load`, `CouponSpec.supports/loads/regions`, `loading` optional, the plate rules in `validate_spec`, `edge_regions`, `area_regions`, `plate_regions`, SI conversion of the lists; `TEST_CODES["plate"] = ("PLT", "plate")`.
- `mesher.sets_by_coordinates(..., boxes=)`: a box gives a node set and an element set; `femodel.plate_sets` names the end rows Edge-Bottom/Edge-Top for plates; `femodel.build_model` builds the boundaries, `consistent_area_loads`, `PressureDefinition`; `FEModel.plate`, `bending` (a plate bends when a pressure, a load or a value acts out of the plane), `support_sets` (the supports in the spec's order), `Face` in both set lists; `write_abaqus` `*Dload`; `write_calculix` `*CLOAD` for nodal loads and `*DLOAD` with the flipped sign and a comment; a record of a plate holds RF_z, w and the faces as a bending coupon's does, and `record_from_dat --no-reactions` leaves the reaction totals out when a shell set's printed total is known to be incomplete.
- `intake.py`: form 0.5; `FormInput.lists`; `read_values` takes the lists for any test and `check_form` refuses them for every test but the plate; `plate_lists` checks shapes and names and names the list in every refusal; `spec_data` writes the lists and no `[grips]`/`[loading]`; `values_of_spec` reads them back; the plate's probes at its centre; the Excel form offers the plate test and says a plate is stated from the studio.
- `checks.py`: `rigid_modes_left` (the rank test), the constraints and load items of a plate, the rows Supports, Loads and Regions; `preview.py`: `loads` (every load and every moved support) and `regions`; `fields.applied_loading` for a plate loaded in its plane (the supports carry the reaction); the coupon document's statement and model chapter for a plate; the model plotter without a single arrow.
- `fea/checks/plate-pressure-isotropic/`: the simply supported isotropic plate under pressure as a plate spec (six supports over the four edges and two corner boxes, one pressure on Face), its decks and its CalculiX 2.22 S8R record: the centre deflection 0.6340 mm against the kernel's 0.6333 mm (0.12 %), both toward +z through the flipped sign, and both faces of the ply at the centre element within 0.04 %; the reaction totals left out (CalculiX's shell set totals 5.5 % short of the load; see the reading note).
- The studio: `lib/studio-plate.ts` (the lists, the region options from the form and the boxes, the regions an element touches, the values the API takes, the words), `components/studio/plate-panel.tsx` (rows for supports with dof boxes and a travel, loads as a force along a direction or a pressure, boxes), the page's picking (a click on the preview names the regions the element touches, each with hold and load buttons), the form hiding the grips and loading rows for a plate, the browser fixtures `tests/fixtures/studio-plate/` and a Playwright scenario.
- Not built, stated: a load as a prescribed displacement of a region through the `[[loads]]` table (a support with a value does it); regions on the bottom face or through the thickness; surface tractions other than a uniform pressure; a plate's CalculiX reaction totals (left out of its record).

## Why (evidence)

- The unnotched coupon stated as a plate (its two tabs as regions, the top one moved 1 mm) reproduces the unnotched record's solve exactly: every displacement, section force and reaction equal to 1e-12 (`fea/tests/test_plate_kind.py`).
- The pressure plate reproduces the validation case `plate-ss-isotropic-uniform-pressure-navier` on the same mesh (the centre deflection 0.633255 mm, the same number the case's deck gives) and balances its 100 N to 1e-10 (`test_plate_kind.py`); against CalculiX S8R: `fea/checks/plate-pressure-isotropic/records/plate-pressure-isotropic-calculix.toml`, 13 numbers within 3 %, worst at 0.16 of the tolerance, and the reading note on the reaction totals.
- Consistent area loads sum to the total with the expected shares per node; the spec and the values file refuse the listed mistakes by name; the checklist names the free rigid motions ("translate along x, translate along y, turn about z" without the corner pins; "tilt about y" with one edge held) (`test_plate_kind.py`).
- The browser: `npm test` (the plate lists, region options and picking in `tests/studio-plate.test.ts`), `npm run test:studio` (the plate scenario: pick the test, add the supports and the pressure, check, solve, read the deflection).
- A plate with a hole or with tabs against CalculiX, and a plate's reaction totals: no evidence yet.

## Consequences

- Easier: any held or loaded edge, tab, ring, face or box is one spec, one deck for each solver, one record and one studio session; the coupon kinds stay as they are, each a fixed, tested arrangement of the same machinery.
- Harder: the coupon document's hand check has nothing to say for a plate (it states so); a plate's records cannot hold CalculiX's reaction totals until the incomplete shell-set totals are understood; the Excel form cannot state a plate.
- We now depend on the mesher's set naming and on the preview's node and element sets for picking; a region picked in the browser is only ever one of the named sets.

## How we will know it was wrong

- An engineer needs a support or a load the regions cannot express (a point load, a traction that varies, a region on one face only) more often than a box or an edge serves.
- A plate's CalculiX record disagrees with the kernel on a deflection or a ply face beyond its tolerance.
- A region picked on the model does not survive a mesh change, or two meshes of the same plate give different sets for the same name.
