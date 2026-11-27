# ADR-0146: A coupon or a plate leaves the workspace as a STEP file of one solid per part at its real thickness, and the layup goes with it as a part table

- Status: Proposed
- Date: 2026-11-27
- Decided by: Founder, 2026-11-27 9:43 AM PT ("Ok launch multiple agents to complete this, we wan tto start deploying fast, make no mistakes.", his go to build the first phase of the company plan, whose CAD part reads "generate what is routine" and "read, generate, connect; do not build a kernel"); Founder, 2026-11-26 5:26 PM PT ("also connect it to how the FEA and CAD should be incorporatied into thsi since that is what we have", on the plan). What the file holds, the choice of solids over surfaces or plies, the parts' names, how tabs are drawn, the header, the route and the wording are the drafter's | Drafted by: Claude Code
- Related: [ADR-0129](ADR-0129-the-model-on-the-page-downloads-as-a-file-for-the-engineers-own-program-one-writer-per-program-over-the-neutral-model-and-the-ansys-file-is-offered-to-founders-only-until-it-has-run-in-ansys.md) (the download this joins), [ADR-0116](ADR-0116-a-wings-shape-is-built-by-gmsh-opencascade-from-the-same-description-as-surfaces-at-mid-thickness-and-its-step-file-names-every-part.md) (the wing's surfaces and the STEP writer), [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md) (the repair's solids), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0004](ADR-0004-sign-and-stacking-conventions.md), [ADR-0065](ADR-0065-coupon-ply-angles-are-counted-from-the-coupons-length-axis.md), [ADR-0072](ADR-0072-a-coupons-test-standard-is-a-profile-of-clause-tagged-requirements-the-specimen-is-checked-against-and-a-deviation-is-reported-never-refused.md), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0133](ADR-0133-the-public-record-states-no-result-of-a-run-in-abaqus-or-ansys-and-names-no-licence-the-numbers-of-such-comparisons-are-kept-privately.md), `fea/src/anisotropy_fea/coupon_shape.py`, `fea/src/anisotropy_fea/mesher.py`, `fea/tools/studio_tool.py`, `fea/tests/test_coupon_shape.py`, `api/src/anisotropy_api/main.py`, `api/tests/test_coupon_step_api.py`, `lib/model-shape.ts`, `components/studio/model-download.tsx`, `tests/model-shape.test.ts`
- Area: fea, api, website

## Context

- "Download model" over a model in the FEA workspace saves it as a file for a solver (ADR-0129). Nothing saved its shape for a CAD program. A wing has a STEP file of surfaces (ADR-0116) and a patch repair one of solids (ADR-0131), each from its own page; a coupon and a plate had none.
- A coupon's or a plate's mesh is cut from one description, the spec's `geometry` (`femodel.mesh_for_spec`): the length, the width, a dog-bone's outline (`dogbone.Outline`) and one hole at the middle. Its thickness is the sum of the section's plies. Bonded tabs are stated only when the spec carries a `[tabs]` table (thickness, bevel, material); the finite element model then holds the gripped length and carries no tab material.
- A STEP file as Gmsh's OpenCASCADE writes it (AP214, `AUTOMOTIVE_DESIGN`) holds shape, names and units. It holds no ply, no angle and no material.
- Gmsh is GPL and an optional extra of the fea package (`mesh`). It runs on the server only.
- A flat laminate differs from the wing and the repair in one way that matters here: every ply has the same outline, and the laminate has a thickness a designer needs (a fixture, a drawing, a mass).

## Options considered

1. Mid-surfaces and a part table, as the wing (ADR-0116). The file is the shell model's own geometry. A coupon then opens as a rectangle with no thickness: nothing to measure, weigh or fit in a fixture until the reader thickens it, and tabs become three stacked surfaces. The wing has a reason a coupon lacks: its skins are sized by the analysis and thickened in CAD afterwards.
2. One solid per part at its real thickness, and a part table. The laminate opens as the part a designer expects, with the thickness the plies sum to; tabs are separate named solids. The layup is not in the shape, so it has to be stated beside it, and the solid's thickness is the nominal sum of the plies, not a measured cured thickness.
3. One solid per ply, as the repair (ADR-0131). In the repair each ply has its own extent, so a solid per ply shows something. In a flat laminate it is n identical slabs: 8 bodies for the example coupon and one per ply for any other, with coincident faces between them, a file that grows with the ply count, and still no fibre direction in the file, only an angle in a name. It also reads as if the plies were modelled in CAD.

Where the file is asked for: a route of its own, as the wing and the repair have, or the existing download route with one more value. A route of its own would restate the access rules, the naming and the blocked-setup answer of ADR-0129.

## Decision

Option 2, through the existing download.

- The laminate is one solid: the outline the mesh is cut from, extruded by the sum of the model's ply thicknesses, in millimetres, x across the width and y along the length from the same corner as the mesh, z = 0 at mid-thickness. A hole is drilled at `mesher.hole_centre`, which the mesher now reads too. Nothing is typed twice.
- Bonded tabs are four more solids, drawn only when the coupon states their thickness: on the gripped length at each end, on each face, with the bevel the coupon states toward the gauge section. A coupon that gives a gripped length and no tab thickness gets no tab. Tabs that would reach a dog-bone's fillet, or a bevel longer than the tab, are refused with the reason: their outline is not stated.
- Every solid is named ("Laminate", or "Coupon" for one isotropic material; "Bottom tab, top face" and so on). A file of several solids is an assembly named after the coupon.
- Where the layup is: in the part table that comes with the file (each part's layup as the coupon writes it, ply count, ply thickness, part thickness, material, volume, and whether the finite element model carries it as material), in the file's own header (`FILE_DESCRIPTION`, which also states the axes, that angles are counted from y and that plies are listed from the face at -z up), and on the page, which prints one line per part after the save. The file and the page both say that a STEP file holds no plies.
- It is offered as "CAD (STEP)" in the "Download model" menu, after the solver files, to everyone who is offered the model. `POST /v1/coupon-jobs/model?program=step` answers it under the rules of ADR-0129: the tests this request is offered (ADR-0089), a blocked setup as a 422 with its first reason, the file named `<designation>.step`.
- Where Gmsh is not installed the tool writes no file and says so, and the API answers 503 "The shape builder is not installed here", the words of the wing's and the repair's shape routes.
- The wing keeps its surfaces and the repair its solids per ply. This record does not change them.

## As built (2026-11-27)

- `fea/src/anisotropy_fea/coupon_shape.py`: `build_coupon_shape(model, step_path)` draws the solids from the built `FEModel` in Gmsh's OpenCASCADE, checks the laminate's bounding box against the model to 1e-6 mm before it writes, names the products and writes the header; `part_table` states the parts in the coupon's units; `read_step_solids` reads a file back (names, volumes, boxes, round holes). It reuses `wing_shape`'s optional import of Gmsh, its quiet writer and `name_step_products`. A file of one solid has one product and no assembly, so the product takes the part's name and the coupon's name is in the header and the file name.
- `fea/src/anisotropy_fea/mesher.py`: `hole_centre`, read by `gmsh_open_hole_plate` and by the shape.
- `fea/tools/studio_tool.py model --program step` (and the warm worker): `<designation>.step` and `model.json` with the part table, or `unavailable` (no Gmsh), or `refused` with the reason.
- `api/src/anisotropy_api/main.py`: `program=step` on the model route; the answer is `model/step` with the part table as ASCII JSON in `X-Anisotropy-Model-Parts`, exposed to the page's origin. No migration.
- `lib/model-shape.ts`, `lib/studio-api.ts`, `components/studio/model-download.tsx`: the menu entry, "Saved the STEP file.", the note and one line per part.
- Every kind a spec may be is drawn: unnotched tension (a gripped strip, bonded tabs, a dog-bone), open-hole tension, compression, in-plane shear, three- and four-point bending, a plate and a plate with a hole.
- Differences from the plan: the assistant does not offer the STEP file. The chat reads "download the step file" as a question about the CAD section today, and a test of ADR-0129 holds that reading, so reading it as a download is a change to how the chat reads a question and is left for its own change. The MCP server has no download tool, so nothing was added there. The repair already saves a STEP file from its own page and is unchanged.

## Why (evidence)

- One description: `cd fea && uv run --extra mesh pytest -q tests/test_coupon_shape.py` gives `107 passed`. For each of 12 cases over all 7 kinds the file is read back by OpenCASCADE and held against the model and the mesh: the laminate's box is the model's length, width and thickness to 1e-6 mm; every node on the mesh's edge lies on the file's outline within 1e-6 mm; a hole's centre and diameter are the mesh's hole nodes' within 1e-6 mm; the volume is the outline's area times the thickness (relative 1e-9 for a rectangle, 1e-7 with fillets); the part table's thickness is the engine's plies' sum and the solid's z extent.
- The neighbours are unchanged: the same command over `tests/test_studio_tool.py tests/test_gmsh_mesher.py tests/test_open_hole.py tests/test_mesher.py tests/test_wing_shape.py tests/test_repair_shape.py tests/test_theory_markers.py tests/test_plate_kind.py` with the new file gives `234 passed`.
- The route: `cd api && uv run pytest tests/test_coupon_step_api.py -q` gives `43 passed` (each kind, a test not offered, the plate, the name, the part table, a signed-in person's own folder, a blocked setup, a refused shape, no Gmsh; a fresh tool and a warm worker).
- The page's logic: `npx tsx --test tests/model-shape.test.ts` gives 6 of 6 passing, and no line it prints holds a banned term (`bannedIn`).
- End to end on a local API with the real tool: the example coupon's file came back in 1.2 s, 15,948 bytes, named after the coupon, and the page saved it from the menu and printed "Laminate: [45/0/-45/90]s, 8 plies of 0.1829 mm, 1.463 mm thick, IM7-8552."
- Size: a file of one solid is about 16 kB (20 kB with a hole, 48 to 63 kB for a dog-bone, 85 kB with four tabs). A solid per ply would multiply the first figure by the ply count.
- The schema and the unit are read from the files: `AUTOMOTIVE_DESIGN` (AP214) and `SI_UNIT(.MILLI.,.METRE.)`.
- UNVERIFIED: no file has been opened in SolidWorks, Onshape, Fusion or any other CAD program. They have been read back by OpenCASCADE alone, the kernel that wrote them.
- No evidence yet on which form a customer's CAD work needs; the choice of a solid over surfaces rests on the reasoning under Options.

## Consequences

- A model set up in the workspace can be handed to a designer as a part with its real thickness, and the part table tells them the layup the shape cannot.
- The thickness in the file is the nominal one. A reader who needs a cured thickness changes the ply thickness in the model, not the file.
- A flat part's STEP file now differs in form from the wing's (surfaces) and matches the repair's (solids). The reason is stated above and in each file's header.
- The shape depends on Gmsh being installed with the fea package. The solver image has it; a laptop without the extra gets the 503.
- The file is not the same byte for byte from one request to the next: the writer stamps the time in its header. The run record keeps each file's digest.
- The header and the product names are rewritten in the written file by text, as for the wing. A change in the writer's text is caught by the tests that read the names back, and the tool refuses a file it cannot name rather than half name it.

## How we will know it was wrong

- A CAD program a customer uses does not open the file as named solids in millimetres, or reads another size than the model's.
- A customer asks for the plies as bodies, or for the mid-surface, more than once: then a second form is offered beside this one.
- A designer builds from the file with the wrong layup because the part table was not seen: then the layup has to travel in the file in a form their program shows.
- A coupon's STEP outline and its mesh are found to differ by more than the 1e-6 mm the tests hold.
