# ADR-0116: A wing's shape is built by Gmsh's OpenCASCADE from the same description, as surfaces at mid-thickness in millimetres, and its STEP file names every part

- Status: Proposed; with spar caps or zones the skins' faces lie on one reference surface, cut at every cap and zone edge, each with its offset, by [ADR-0125](ADR-0125-a-spar-cap-is-a-strip-of-each-skin-over-each-web-with-its-own-layup-any-layup-may-change-in-zones-along-the-span-and-the-hand-calculation-works-a-section-per-stretch.md) amendment 1; a skin thicker than the nose is round meets at a point there, since amendment 1
- Date: 2026-11-19
- Decided by: Founder, 2026-11-18 ("Wing generator first"; "the same way we have it for abaqus right now", on SolidWorks models going both ways; "please continue with building the software", after step 1) | Drafted by: Claude Code
- Related: [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0004](ADR-0004-sign-and-stacking-conventions.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), `fea/src/anisotropy_fea/wing_shape.py`, `fea/tests/test_wing_shape.py`
- Area: fea

## Context

Step 2 of the wing generator is the wing's shape: the parts a CAD program opens and the surfaces the finite element model of step 3 is meshed on, from the description the engine's hand calculation reads (ADR-0115). The founder works in SolidWorks and wants models to go between it and the product as they do with Abaqus. A STEP file is what both read. The fea package already depends on Gmsh, an optional extra, for the open-hole mesh (ADR-0030 amendment 3); Gmsh's OpenCASCADE kernel builds B-spline curves and surfaces, cuts them where they meet and writes STEP.

Tried here with Gmsh 4.15.2 and OpenCASCADE 7.8 (2026-11-19): the STEP file Gmsh writes states millimetres (`SI_UNIT(.MILLI.,.METRE.)`) whatever the model's numbers mean, and names its products "Open CASCADE STEP translator 7.8 1.k", one per top-level shape in the order they were made, so the parts' names are lost; an interpolation point left after a spline is made is written as a part of its own; a spline whose ends are free leaves the leading edge 116 degrees from its neighbour's direction, a crease, unless its tangent there is given; sizing the mesh by curvature does not finish on the trailing edge's point.

## Options considered

1. Gmsh's OpenCASCADE, building in millimetres, with the products renamed in the written file: no new dependency; the renaming relies on the writer's product text, which the tests read back.
2. CadQuery (OCP), whose assembly writer keeps names and colours: a second OpenCASCADE binding of about 100 MB in the solver's image for one feature, and a second way to build geometry beside the mesher's.
3. A STEP writer of our own: full control, and a large surface of the standard to get right.
4. Each part as its own STEP file: names survive as file names, and SolidWorks opens nine files instead of one.

For the surfaces: the skins on the airfoil's outer surface, as the hand calculation places them, or at their mid-thickness, as a shell element sees them.

## Decision

Option 1. `anisotropy_fea.wing_shape.build_wing_shape` builds every part as one surface in millimetres: the upper and the lower skin as the airfoil's outline moved inward by half the skin's thickness, each a spline leaving the leading edge vertically and stopping where the two meet near the trailing edge (or joined by a flat strip of skin when they do not); the spar webs flat between them; the ribs flat at the root, every rib spacing and the tip, each filling the section. The STEP file is written with each part a product in that order, and `name_step_products` replaces the writer's names with the parts' ("Upper skin", "Front spar", "Rib 1") and refuses a file whose count of products differs. For the mesh, the parts are cut where they meet and meshed with four-node quadrilaterals whose normals point out of the wing, aft for a web and to the root for a rib. A rib layup is an optional table of the wing file, `[rib]`, needed only with a rib spacing.

## As built (2026-11-19)

`fea/src/anisotropy_fea/wing_shape.py` (`mid_surface_section`, `rib_stations`, `build_wing_shape`, `name_step_products`, a command line: `uv run --project fea --extra mesh python -m anisotropy_fea.wing_shape <wing file> <step file> [--mesh SIZE_MM]`) and `fea/tests/test_wing_shape.py`. The engine's `Wing` gained `rib` (ADR-0115 amendment 1). The STEP file carries no thickness: the part table printed beside it gives each part's layup, thickness, area and mass, and a CAD program's thicken feature makes the solid. The mesh is built and checked here; the CalculiX model that uses it is step 3.

## Why (evidence)

- `cd fea && uv run --extra mesh pytest tests/test_wing_shape.py`: 13 passed. The STEP file of the example wing reads back into Gmsh with the nine parts' names and their areas to 1e-9; its span is 2000 mm. The webs' areas equal height times span to 1e-9; the skins' are within 0.2 % of the polyline through their points; a rib's is within 0.2 % of the section's area by the shoelace formula. The front web's top and bottom edges are lines of nodes shared with the upper and lower skin from root to tip. Every element of the box's skins has its normal within 26 degrees of up or down, and the nose's point forward.
- The example wing (`engine/examples/example-wing.toml`) is built, written and meshed (6,568 elements at 20 mm) in 1.6 s here.
- No evidence yet that the file opens in SolidWorks with the right names and size: that is the founder's exercise on his PC.

## Consequences

The shape, the mesh and the hand calculation read one description. The STEP naming depends on the text the OpenCASCADE writer produces; a Gmsh update that changes it makes `name_step_products` refuse the file rather than name it wrongly, and the tests fail. The hand calculation places the skins on the outer surface and the shape at mid-thickness, so the two differ in bending stiffness by the skin's offset; step 3 compares them. The mesh is not refined round the leading edge, and a few elements near the trailing edge's point have a corner near 180 degrees; the mesh study of step 3 decides the size.

## How we will know it was wrong

The STEP file does not open in SolidWorks with the part names and the size the part table gives; or a Gmsh release changes the writer's product text and the names cannot be kept this way; or the mesh near the trailing edge changes step 3's answers by more than its mesh study allows.

## Amendment 1, 2026-11-25 (a skin thicker than the nose is round meets at a point at the nose; drafted, not yet confirmed by the founder)

**Context.** On the founder's word of 2026-11-24 after his team's feedback, "the most important part is that our software works, work on step patch, and wing analysis", 60 wings were run through the STEP file and the check. The example wing with a NACA 6409 airfoil was refused with "The mesh has an element without area" at 40, 20 and 10 mm elements, the example with a 0.1 m chord likewise, and with a NACA 6412 the mesh did not finish (stopped after 12 minutes of one processor). The cause is in the section, before any mesh: the outline is moved inward by half the skin's thickness (3.7 mm on the example), and where that is more than the nose's radius the moved outline folds over itself, coming in along one skin, crossing the part that goes out along the other, and turning back twice. The shape then had a sliver of face 0.7 mm wide along the span between the folded skins, which Gmsh filled with elements whose four corners lie on one line. A NACA 0006 folds the same way and was meshed and checked all the same. The test for an element without area was an absolute 10^-18 m^2: the 0.1 m chord at 20 mm passed it with elements of 9 x 10^-9 mm^2.

**Options.** (a) Cut the fold off where the moved outline crosses itself, so the two skins' surfaces meet at a point at the nose as they already do near the trailing edge: chosen; that point is where the surface at that depth under both skins ends. (b) Refuse a wing whose skin is thicker than its nose is round: rejected, thin and cambered sections on small wings are ordinary, and the hand calculation works them. (c) Round the nose with a radius of our own: rejected, a size nobody stated. (d) Leave the section and have the mesher skip slivers: rejected, the STEP file carries the same fold into a CAD program.

**Decision.** `fea/src/anisotropy_fea/wing_shape.py`: `mid_surface_section` cuts every loop of the moved outline forward of mid-chord at its crossing (`_without_fold`) and drops the points crowded within a thousandth of the chord beside the cut (`_spaced`); `Section.nose_closed` says so, and the skins' splines then leave the nose as their own points lead, not vertically. A front spar or cap forward of that point is refused by the checks that were there. A section that does not fold is built as before, point for point. An element of less than a millionth of the square of the element size asked for is refused as one without area (`SLIVER`).

**Evidence.** `cd fea && uv run --extra mesh pytest tests/test_wing_shape.py`: 26 passed. For NACA 6409, 6412 and 0006 and for a 0.1 m chord the section's points lie between 0.95 and 1.01 of the depth from the nearer surface; the first two mesh at 40 mm with about 2,350 elements, none under 2 % of the size squared. The example's mesh is the same 2,354 elements with the same smallest and largest. The check then ran on each (`python -m anisotropy_fea.wing_check`, lowest margin outboard of the root, model against hand calculation): the example +0.106 against +0.114, as before; NACA 6409 -0.333 against -0.314; NACA 6412 +0.117 against +0.089; NACA 0006 -0.611 against -0.646, where the folded shape gave -0.608; a 0.1 m chord -0.964 against -0.993.

