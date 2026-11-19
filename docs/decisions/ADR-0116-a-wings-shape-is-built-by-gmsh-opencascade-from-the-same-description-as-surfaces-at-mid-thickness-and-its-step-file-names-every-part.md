# ADR-0116: A wing's shape is built by Gmsh's OpenCASCADE from the same description, as surfaces at mid-thickness in millimetres, and its STEP file names every part

- Status: Proposed
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
