# ADR-0131: A stepped patch repair is one description of a few numbers in the engine; its slice is a set of rectangles, and the hand calculation, the mesh and the STEP file are all made from them

- Status: Proposed
- Date: 2026-11-20
- Decided by: Founder, 2026-11-20 ("merge, and yes repair, step 2", and his choice "Repair, step 2" on the card "Pick what I build once #256 is merged"; the plan's step 2 reads "Parent layup, damage size, number of steps, step length, patch plies, cover plies, adhesive and its thickness give the slice through the repair, meshed, and a STEP file for SolidWorks", checked by "Lengths and areas measured back"). How the bondline is drawn, the rule for a stack's stiffness, where the lap ends, the mesh's form, what the STEP file holds and what is refused are the drafter's | Drafted by: Claude Code
- Related: [ADR-0130](ADR-0130-a-bonded-repairs-hand-calculation-is-the-stepped-lap-as-a-shear-lag-model-in-the-engine-the-patchs-force-at-every-step-boundary-the-adhesives-elastic-limit-and-the-long-overlap-strength-of-a-yielding-adhesive.md) (the stepped lap, and its amendment 1), [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0116](ADR-0116-a-wings-shape-is-built-by-gmsh-opencascade-from-the-same-description-as-surfaces-at-mid-thickness-and-its-step-file-names-every-part.md), [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0007](ADR-0007-validation-cases-store-numbers-only.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), `engine/src/anisotropy_engine/repair/`, `fea/src/anisotropy_fea/repair_shape.py`, `engine/docs/theory.md` Section 17, `engine/validation/patch_repair_cases/`, `engine/tests/test_patch_repair.py`, `fea/tests/test_repair_shape.py`
- Area: engine, fea

## Context

- The repair's first slice (ADR-0130) works a stepped lap from one thickness and one modulus for each adherend in each step. Its own consequences say that someone has to work those moduli from the layup until the repair is stated by its plies.
- The plan's second slice is the repair from a few numbers: the slice through it, meshed, and a STEP file for SolidWorks, checked by lengths and areas measured back. The finite element solution of the slice is the third slice, and the bond's progressive failure the sixth; both need the adhesive as a layer with its own thickness.
- The wing was built the same way: one description in the engine, read by the hand calculation, the shape and the finite element model (ADR-0115, ADR-0116).
- The founder has not yet sent the facts of his real repair. The slice is built on an example of round numbers, and his repair's numbers go into the same file when he sends them.

## Options considered

1. **Where the description lives.** (a) In the engine, with the shape in the fea package, as the wing: the hand calculation needs no Gmsh. Chosen. (b) In the fea package: the hand calculation would depend on the mesher.
2. **What a repair may state.** (a) A round, stepped cut from the top face, equal steps, the same number of plies in every step, patch plies as thick as the laminate's, optional cover plies. Chosen: it is what the plan names, and every size follows from six numbers. (b) Also a scarf, unequal steps, plies of another thickness, a backing plate: each needs geometry rules of its own and none is asked for yet. They are refused in words.
3. **How the bondline is drawn.** (a) A line of no thickness, the patch flush with the laminate: simplest to draw, but the later slices need adhesive elements of real thickness, and a mesh made later from other rules would not be this slice's. (b) The adhesive lines the cavity with its thickness and the patch sits on it, so the patch is raised by one bondline and its top stands that much above the laminate's face. Chosen: it is what the cured repair is, and every part is still a rectangle. (c) Patch plies thinned so the patch ends flush: the ply's thickness would no longer be the material's.
4. **How the slice is stated.** (a) A list of rectangles, and a second rule that answers what lies at one point by its level and its radius, each checking the other on every description. Chosen. (b) The rectangles alone: a mistake in one rule has nothing to be caught by.
5. **An adherend's stiffness in a step.** (a) Each stack alone, 1 / a11 of its own A matrix: the textbook's laminate modulus, but a stack bonded to another cannot contract or shear on its own, and the two values do not add up to the bonded section's stiffness; a single 45° cover ply would count for 12 GPa where it carries 31 GPa inside the section. (b) Each stack's share of the bonded section's stiffness, the section strained by a load along the lap and free to contract and shear as a whole. Chosen: the two shares add up to the section's stiffness, so the force the patch carries where the strains are alike is exact, and for a balanced section it is A11 - nu A12 of the stack, which can be written by hand. (c) A11 alone (no contraction): too stiff. (d) E1 cos^4: ignores the matrix.
6. **Where the lap ends when the cut does not go through.** (a) At the last ledge, with the patch carrying the whole load there: the lap of ADR-0130, but the laminate carries on under the patch and keeps part of the load. (b) Across the floor to the repair's middle, a plane of symmetry with no shear stress. Chosen; it needs the lap model to allow that end (ADR-0130 amendment 1).
7. **The mesh of the slice.** (a) A grid with a line of nodes along every edge of every rectangle, the stretches between divided evenly. Chosen: every element is in one part by construction, the areas can be measured back exactly, and no mesher is needed. Its elements are long and thin in the laminate far from the repair. (b) Gmsh's quadrilaterals on the rectangles: graded sizes, but a second dependency for a shape made of rectangles. The third slice may refine or grade the grid.
8. **What the STEP file holds.** (a) Every ply and every piece of adhesive as a named solid in the panel, the repair's parts swept about its middle. Chosen: it is what opens as a repair in a CAD program, and each solid's volume has a closed form to be measured against. (b) The slice as flat faces: not what a CAD user expects. (c) Surfaces at mid-thickness, as the wing: the adhesive has no place in them.

## Decision

- A repair is `anisotropy_engine.repair.Repair`: the laminate's material and angles, the damage's diameter, the number of steps, the step length, the plies in a step, the patch's material and angles (the laminate's material and the angles of the plies removed unless said), cover plies and their overlap, the adhesive, and the panel drawn around it. Steps and patch groups are counted from the top face. What it cannot state is refused in words (ADR-0003).
- The slice is the rectangles of `regions`, with the adhesive lining the cavity and the patch raised by one bondline, and `region_at` answers the same question for a point by another route. A description on which the two disagree is refused (`check_regions`).
- The lap is one step for the cover's overlap, one for each ledge and, when the cut does not go through, one across the floor to the repair's middle, where it ends at a plane of symmetry. Each stack's stiffness is its share of the bonded section's (`shared_stiffnesses`). The answer is ADR-0130's: the patch's force at every step boundary, the shear stress, and the load at the adhesive's elastic limit, which is not the repair's strength.
- `anisotropy_fea.repair_shape` makes the mesh of the half slice (`slice_mesh`, four-node quadrilaterals on a grid) and the solids of the whole repair in its panel in a STEP file in millimetres, each under its part's name (`build_repair_shape`), from the same rectangles. The areas, the bondline on the laminate and the volumes are measured back against the engine.
- A repair is a TOML file in a unit system (`repair_from_dict`, `repair_report`), its ply material from the library or typed in full.
- Not in this slice: a finite element solution, the page, the chat, a material for the mesh's elements, and the founder's real repair.

## Why (evidence)

Run in the cloud container on 2026-11-20:

- `cd engine && uv run pytest -q`: 786 passed, of which `tests/test_patch_repair.py` 63 and `tests/test_step_lap.py` 16.
- `cd fea && uv run --extra mesh pytest -q tests/test_repair_shape.py`: 17 passed, with Gmsh 4.15.2.
- Two constructed cases, `engine/validation/patch_repair_cases/`, cross-ply laminates so that every stiffness can be written by hand. Their expected sizes, areas, volumes, stiffnesses, boundary forces and shear stresses equal `stepped_patch_repair` in `engine/validation/closed_forms.py`, which uses no engine code, within 10^-9, and the engine reproduces them within 10^-9. While writing that closed form its first version of the adhesive's area left out the top of the patch above the laminate's face; the engine's rectangles had it right, and the closed form was corrected before any expected number was stored.
- Over nine repairs (with and without cover plies, through and not, one and two plies a step, a patch of other angles): no two rectangles overlap; a grid of 171 by 59 points gives the same part by the rectangles and by `region_at`; areas and volumes equal the sums written out in the test.
- The mesh of the example (1288 elements at the default size): the area of each kind of part equals the engine's to 10 digits, 62.5 mm of bondline lies flat on the laminate (three ledges of 12.5 mm, the floor's 12.5 mm and the cover's 12.5 mm) and 0.7315 mm stands on the cut faces (four plies).
- The STEP file of the example: 22 solids, each one's volume equal to its ring, disc or slab with a hole within 10^-9; read back from the file, the solids have the same volumes under the same names.
- The example (`engine/examples/example-patch-repair.toml`, IM7/8552 [45/0/-45/90]s, 25 mm of damage, four steps of 12.5 mm, one 45° cover ply, 0.1 mm of an adhesive of 1000 MPa and 30 MPa, under 100 N/mm): the largest shear stress is 12.58 MPa at the end of the ledge of step 1, where the 0° patch ply begins, and the load at the adhesive's elastic limit is 238.5 N/mm. At the repair's middle the patch carries 53.0 N/mm of the 100.
- No comparison with a finite element model or a test yet: that is the third slice. The STEP file has not been opened in SolidWorks. UNVERIFIED: that a CAD program shows the names as written (the wing's file, named the same way, did in SolidWorks on 2026-11-19).

## As built (2026-11-20)

- `engine/src/anisotropy_engine/repair/description.py` (`Repair`, `RepairMaterial`, `RepairError`), `section.py` (`Region`, `regions`, `region_at`, `areas`, `volumes`, `bond_lengths`, `check_regions`), `patch_lap.py` (`stretching_matrix`, `shared_stiffnesses`, `lap_steps`, `repair_lap`), `repair_file.py` (`repair_from_dict`, `repair_report`).
- `fea/src/anisotropy_fea/repair_shape.py`: `slice_mesh`, `SliceMesh`, `build_repair_shape`, `RepairShape`, `read_step_volumes`, and the command `python -m anisotropy_fea.repair_shape <repair.toml> --step <file.step>`.
- `engine/docs/theory.md` Section 17 with its code markers; the three modules among those the manual prints. Sections 16 and 17 are kept out of a coupon chat's search of the theory pages ([ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md) amendment 5).
- `engine/validation/patch_repair_cases/` (two cases), `stepped_patch_repair` in `engine/validation/closed_forms.py`, `engine/tests/test_patch_repair.py`, `fea/tests/test_repair_shape.py`, `engine/examples/example-patch-repair.toml`, `engine/examples/patch_repair_calculator.py`.

## Consequences

- A repair is stated once, by its plies, and its hand calculation, mesh and CAD file cannot drift apart.
- The third slice has its mesh and its reference: the finite element solution of this slice is to be compared with these forces and shear stresses.
- The patch stands one bondline above the laminate's face in every picture and file. A reader who expects a flush patch needs to be told why.
- The lap is one line through a round repair. It says nothing of the load that flows around the repair, and a student must not read its answer as the panel's.
- The stiffness rule differs from a textbook's laminate modulus for each adherend. A hand calculation that uses 1 / a11 of each stack will not match ours where a stack is not balanced, and the report prints each step's moduli so the difference can be seen.
- The grid's elements are long and thin far from the repair, which the third slice has to judge.

## How we will know it was wrong

- The finite element solution of the slice gives forces in the patch that differ from the lap's by more than the difference between a line and a section explains, or shows that the stiffness rule is further from it than 1 / a11 of each stack.
- A real repair the founder or a student brings cannot be stated: its steps are unequal, it is a scarf, or its patch plies are of another thickness.
- SolidWorks or another CAD program does not open the STEP file as named solids of the stated volumes.
- The published repair benchmark's ranking of designs disagrees with the lap's.
