# ADR-0132: A repair's slice is solved in CalculiX as a plane of eight-node elements, held flat, with the laminate's far-field width strain; its bondline and plies are read back as means, by the engine

- Status: Proposed; the same slice is written as an Abaqus and an Ansys file and their results are read back, since amendment 1
- Date: 2026-11-21
- Decided by: Founder, 2026-11-20 ("yes start step 3, make no mistakes"; the plan's step 3 reads "CalculiX solves the slice. Shear and peel along the bond, ply stresses at the step ends, which fails first", checked against "The hand calculation, then Abaqus and Ansys run from our own downloaded files"). The element, the condition across the width, the supports, the load, the mesh, how the cut faces are treated, what is read back and how, and the checks are the drafter's | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/repair_files.py` (amendment 1), [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md) (the description and its slice), [ADR-0130](ADR-0130-a-bonded-repairs-hand-calculation-is-the-stepped-lap-as-a-shear-lag-model-in-the-engine-the-patchs-force-at-every-step-boundary-the-adhesives-elastic-limit-and-the-long-overlap-strength-of-a-yielding-adhesive.md) (the hand calculation), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0117](ADR-0117-a-wing-is-checked-in-calculix-with-composite-shells-under-superposed-load-patterns-its-panels-buckle-as-the-engines-ritz-plates-on-the-models-loads-and-flutter-is-a-typical-section-estimate.md), [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0007](ADR-0007-validation-cases-store-numbers-only.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), `engine/src/anisotropy_engine/repair/solid.py`, `fea/src/anisotropy_fea/repair_model.py`, `fea/src/anisotropy_fea/repair_shape.py`
- Area: engine, fea

## Context

- The repair's hand calculation (ADR-0130, ADR-0131) is a stepped lap: one line through the repair, each adherend straining alike through its thickness, nothing moving through the thickness. It gives the patch's force at every step boundary and the adhesive's shear stress. It has no peel stress, no bending and no ply stresses, and its own records name the finite element solution of the slice as the next step.
- The plan's third step asks for that solution in CalculiX: shear and peel along the bond, ply stresses at the step ends, and which fails first, checked against the hand calculation first.
- The engine describes the slice as rectangles, one for each ply and each piece of adhesive, and `fea/` meshes them on a grid (ADR-0131). The plies' constants through the thickness and the adhesive's Poisson's ratio were not part of the description: the lap does not need them.
- New physics comes from CalculiX with our composite layer; the engine computes every number of a result (ADR-0067, ADR-0001).
- An elastic solution has no upper bound on the stress at the corner where a step ends, so a stress read at a point there follows the mesh.

## Options considered

**The element.**

1. Plane-strain eight-node elements with reduced integration (CPE8R), the choice. Quadratic, so one element through a ply carries its bending; the slice is long across the width compared with a bondline.
2. Plane stress. Rejected: it frees every ply across the width, where the laminate holds the plies to one strain.
3. Solid elements, one element wide. The same answer with three times the equations and constraints to write by hand. Rejected.
4. Our own kernel. It has no plane element and no orthotropic solid (ADR-0067). Rejected.

**Across the width.**

1. The laminate's far-field width strain everywhere, the choice. Plain plane strain holds the laminate from its Poisson contraction and puts a stress across the width into every ply that the panel does not have, so the far field would not be the laminate theory's. Every material is given an expansion of -1 across the width and the slice a temperature equal to the laminate's far-field width strain; the strain that makes stress is then that strain everywhere.
2. Plain plane strain. Rejected for the reason above.
3. Generalized plane strain, which also frees the slice to shear in the laminate's plane. CalculiX 2.21 has no such element; left for the cross-check in Abaqus.

**The supports.**

1. The middle a plane of symmetry and the laminate's bottom face held flat, the choice: what the hand calculation assumes and what a panel on its structure nearly is. One linear solve.
2. The panel free to bend. A one-sided patch then bends the panel, and the bending depends on the load (a large-deflection solution) and on how the panel is held. Not built; named as left out.

**The cut faces of a flush repair.**

1. Left open by default, the choice: the adhesive up each cut face is a butt joint in tension between the end of a laminate ply and the patch ply in its place. The hand calculation gives it no load. Solved as bonded on the example it carried 66 MPa across the 0° ply's cut face under 100 N/mm, more than twice the adhesive's shear strength of 30 MPa at 38 % of the load at which the ledges reach that strength, so it is the first thing to crack; and bonded it lowered the largest shear stress on the ledges by 22 %, so counting on it is the unsafe reading.
2. Bonded. Kept as an option (`cut_faces = "bonded"`), with the stress across each face reported.

**What is read from the bondline.**

1. The mean through the bondline's thickness at each station for the curves, and for the largest shear and the largest peel stress the largest mean over a square of adhesive, the bondline's thickness on a side, the choice. Only the adhesive between the patch and the laminate is read: the corner of adhesive under a cut face or over one joins nothing.
2. The stress at a point (a node or an integration point). Rejected: it has no limit as the mesh is refined.
3. The mean through the thickness at the last station of a bond. The first version built. It settled at a patch's free edge, and beside a cut face it kept growing: on the example the largest peel stress read 10.9, 11.5, 12.0 and 12.6 MPa on meshes of 4, 8, 16 and 32 elements to the bondline's thickness. Rejected for the largest values, kept for the curves.
4. Leaving out the stations within half a bondline's thickness of a cut face. Tried: the field there is steep (39, 18 and 5 MPa at 0.1, 0.5 and 1 bondline's thickness from the corner of a laminate cut through, the same on every mesh), so the answer is whatever the cut-off distance makes it, and the rule is special to one kind of end. Rejected for one rule at every end.

**The plies.** Each ply's strains averaged through its thickness at every station, turned into the ply's own stresses by the engine and judged by the engine's strength ratio (maximum stress or Tsai-Hill, the two that need only the five ply strengths), the choice. CalculiX's own stress output in ply axes was not used: the deck holds the nine orthotropic terms of a turned ply, and the engine puts back the terms that tie the ply's in-plane shear to the rest.

**The through-thickness constants.** Stated in the repair's file, as `nu23` alone for a unidirectional ply (the same in every direction across its fibres) or all five for a fabric, the choice. A default was rejected (ADR-0003): a solve without them is refused in words.

## Decision

1. `anisotropy_engine.repair.solid` gives each ply as an orthotropic solid turned to its angle and the adhesive as an isotropic one, the laminate's far field under the load, and a ply's own stresses from its strains in the slice. The repair's file may state the constants through the thickness, the adhesive's Poisson's ratio and a peel strength.
2. `anisotropy_fea.repair_model` builds the CalculiX deck from the description, as chosen above: CPE8R elements on `slice_mesh`'s grid, graded to an eighth of the bondline's thickness beside every edge with two elements through the bondline; the far-field width strain; the middle and the bottom face held; each ply's far-field stress on the panel's end; cut faces open unless asked.
3. Read back: the forces along the load in the patch, the laminate and the adhesive at every station; the shear and peel curves along every bond; the largest of each as a mean over a square of adhesive; the stress across each bonded cut face; every ply's weakest station. First is the lowest of the load at the adhesive's elastic limit in shear, the load at a stated peel strength and the load at the first ply's strength. The first of these is named as the adhesive's elastic limit and not as the repair's strength.
4. Every solve is refused unless CalculiX's stress is the engine's stiffness times CalculiX's strain, the forces add up to the load at every station, and the strain midway to the panel's end is the far field's.
5. `hold = "everywhere"` holds every node from moving through the thickness. It is the check that brings the model to the lap's assumptions, not a repair.

## Why (evidence)

Run in the cloud container on 2026-11-21, CalculiX 2.21:

- `cd engine && uv run pytest -q`: 858 passed, of which `tests/test_repair_solid.py` 33. `cd fea && uv run --extra mesh pytest -q tests/test_repair_model.py tests/test_repair_shape.py tests/test_theory_markers.py`: 47 passed, of which `test_repair_model.py` 18.
- The solid: a turned ply free through its thickness equals `rotation.py`'s transformed reduced stiffness at seven angles; the constructed case of `engine/validation/repair_solid_cases/` equals `turned_solid_ply` in `closed_forms.py`, written term by term with no matrix inverse and no tensor rotation, within 10^-9.
- The model held to the lap's assumptions (`fea/checks/repair_cases/`, a strip patch bonded on top, every Poisson's ratio zero, shear moduli through the thickness ten thousand times the in-plane one, `hold = "everywhere"`; 2,744 elements): the patch's forces at the three boundaries are 34.85, 55.68 and 149.76 N/mm against the closed form's 35.03, 55.86 and 150; the shear stress along the whole bondline is within 0.23 % of the peak of the engine's lap; no peel stress.
- The same strip with real constants (`nu23` 0.4, the adhesive's 0.35), bottom held: the forces add up within 10^-7 and the far field is the laminate theory's within 10^-6. The largest shear stress is 20.6 MPa beside the hole's edge against the lap's 33.3; the bond is pressed together there and pulled apart at the patch's tip, 7.7 MPa over the last bondline's thickness.
- The example (`engine/examples/example-patch-repair.toml`, 6,344 elements, 38,838 equations, 2.7 s), `cd fea && uv run --extra mesh python -m anisotropy_fea.repair_model ../engine/examples/example-patch-repair.toml`: the patch's forces at the five boundaries are 8.65, 24.39, 47.64, 52.12 and 53.29 N/mm against 8.61, 24.66, 47.58, 52.24 and 53.03 by hand; the largest shear stress is 11.5 MPa on the ledge of step 2 against 12.58 by hand; the largest peel stress is 4.1 MPa at the cover ply's edge; the load at the adhesive's elastic limit is 260.8 N/mm against 238.5; the first ply is the laminate's -45° ply at a strength ratio of 4.66, in transverse tension beside the cut of step 2. With `--cut-faces bonded`: 9.0 MPa, 329 N/mm, and 6.5, 19.5, 65.6 and 18.9 MPa across the cut faces of steps 4 to 1.
- The mesh, with 4, 8, 16, 32 and 64 elements to the bondline's thickness beside every edge (`--fine`): the example's largest shear stress 11.47, 11.51, 11.54, 11.57, 11.58 MPa, its largest peel stress 4.12, 4.11, 4.12, 4.09, 4.10 MPa and its first ply's ratio 4.651, 4.661, 4.661, 4.662, 4.663. Over seven solved repairs (the example open and bonded, the strip, a round patch on top, a cut through every ply open and bonded, a repair with a cover ply) the largest shear stress moved by 0.6 % at most from 8 to 64 and the largest peel stress by 1.7 % at most, that one beside an open cut face of the laminate cut through (19.96 to 20.30 MPa). The study's script was not kept; the tests hold the halving of the default on the strip and on the example.
- The founder's own repair, a private case (ADR-0042), was solved with constants through the thickness that its files do not state, taken as assumptions over a range. Its numbers are kept out of the repository.
- Not done: the same model in Abaqus or Ansys, the plan's second check, which needs the founder's computer. No comparison with a test is claimed. UNVERIFIED: that CalculiX's CPE8R and an Abaqus CPE8R of the same deck agree; that the lap's stiffness rule (ADR-0131) is nearer the model than 1 / a11 of each stack, which was not compared.

## As built (2026-11-21)

- `engine/src/anisotropy_engine/repair/solid.py`: `ply_compliance`, `turned_stiffness`, `ply_stiffness`, `adhesive_stiffness`, `plane_stress_stiffness`, `far_field`, `ply_axis_stress`. `description.py`: `ThroughThickness`, `tape_through_thickness`, and `RepairMaterial.through`, refused when the constants do not make a material. `step_lap.py`: `Adhesive.poisson_ratio` and `Adhesive.peel_strength_pa`. `repair_file.py`: `nu23` or all of `E3`, `G13`, `G23`, `nu13`, `nu23` for a material, the five strengths for a typed one, `poisson` and `peel_strength` for the adhesive.
- `fea/src/anisotropy_fea/repair_model.py`: `build_slice_model`, `run_slice_model`, `read_results`, `slice_answer`, `solve_slice`, `slice_report`, and the command `python -m anisotropy_fea.repair_model <repair.toml> [--out DIR] [--criterion NAME] [--size mm] [--fine mm] [--cut-faces open|bonded]`. `repair_shape.py`: `slice_mesh` graded (`fine_m`, `growth`, `adhesive_layers`), with each element's column and layer.
- `engine/docs/theory.md` Section 18 and `fea/docs/theory.md` Section 11, with their code markers; both modules among those the manual prints. Both sections are kept out of a coupon chat's search of the theory pages ([ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md) amendment 6).
- `engine/validation/repair_solid_cases/` (one case) and `turned_solid_ply`; `fea/checks/repair_cases/` (one case; the folder is named in `paths.NOT_TESTS`, since a repair file is not a coupon spec); `engine/tests/test_repair_solid.py`, `fea/tests/test_repair_model.py`. The example states `nu23` and the adhesive's Poisson's ratio, round values of our own.
- Differences from the plan: no run in Abaqus or Ansys yet. The slice is not on a page, in a job or in the assistant: that is the plan's fourth step.

## Consequences

- A repair now has peel stress, the bending of the patch and each ply's stresses at the step ends, from the same description as its hand calculation, in two or three seconds.
- A solve needs three things the hand calculation does not: each material's constants through the thickness, the adhesive's Poisson's ratio, and the plies' strengths for the ply check. For most materials the first two are estimates, and the answer moves with them.
- The largest bondline stresses are means over a square of adhesive. The side of the square is a choice: at a patch's free edge the square's mean is about a quarter below the mean through the thickness at the last station. A peel strength has to be one that suits such a mean.
- The slice is the strip through the repair's middle. It does not hold the laminate beside a hole narrower than the panel or the load that flows around a round repair, so its loads are low for such a panel as a whole; it is elastic, so it stops at the adhesive's elastic limit; it is held flat, so a panel free to bend is not answered. A reader must not take the load at the adhesive's elastic limit for the repair's strength.
- An open cut face is a crack that ends on a bond. What it does to the bond is a question of fracture, left to the step on the bond's failure.
- A laminate that is not balanced is stiffer in the slice than free, since the slice cannot shear in the laminate's plane.

## How we will know it was wrong

- Abaqus or Ansys, given the same slice, disagrees with these forces or bondline stresses by more than their meshes explain.
- A finer mesh moves the largest shear or peel stress of a repair by more than 2 %.
- A tested repair fails in peel at a load the square's mean, with a peel strength from a joint test, misses by more than the scatter of such tests; or a large-deflection solution of a one-sided patch on a free panel shows that holding the bottom face flat hides most of the peel.
- The constants through the thickness, varied over their likely range, move the answer by more than the difference between the model and the hand calculation.

## Amendment 1, 2026-11-21 (the slice written as an Abaqus and an Ansys input file, and what the programs write read back beside CalculiX's answer; no result of a run in either program is stated here, on the founder's word; how the files are written and read is not yet confirmed by the founder)

**Context.** The plan's third step is checked against the hand calculation, "then Abaqus and Ansys run from our own downloaded files". The record above left that run open, and marked as UNVERIFIED that CalculiX's CPE8R and an Abaqus CPE8R of the same deck agree. CalculiX builds a plane element as a twenty-node brick with constraints, so the agreement was not known. Abaqus and Ansys are licensed programs that our code does not run. Asked whether wording that quotes the results of runs under his own licences should be taken out of the public record, the founder answered, 2026-11-20: "merge and yes thee shouldn't wording in our software". This amendment therefore states what the files hold and how their results are read, and no result of a run.

**Options.** How the other two programs are given the model: (a) their own models, meshed in each program, rejected because a difference would then be the mesh's and not the solver's; (b) the same nodes and elements written as each program's input file by our code, chosen. How Mechanical APDL is given an orthotropic material: its stiffness matrix (`TB,ANEL`), rejected because the engineering constants are what every reader of an Ansys file expects and the nine terms have an exact set of nine constants; the constants, chosen. How Abaqus's results are read: the output database through an Abaqus script, rejected because it adds a script that only runs under Abaqus and that no test here can run; the printed tables of the `.dat`, which `abaqus_dat.py` already reads, chosen, at the price of four printed figures. Where the other programs' numbers go: into tests as expected values, rejected as for every coupon (a second solver is evidence, not a reference); into this record, rejected on the founder's word above; kept by whoever runs the files, outside the repository, chosen.

**Decision.** `fea/src/anisotropy_fea/repair_files.py` writes a `SliceModel` as an Abaqus input file (`abaqus_file`: CPE8R, `*Elastic, type=ORTHOTROPIC` in an orientation that is the global axes, the width strain as an expansion and a temperature, `*Dload` P2) and as an Ansys Mechanical APDL input file (`ansys_file`: PLANE183 in plane strain, each material by the nine engineering constants of its nine stiffness terms, `ALPZ` and `TUNIF`, `SFE` on face 2; the file writes its own table of element means). `read_abaqus` and `read_ansys` turn what each program wrote into the element means CalculiX gives, refuse them unless the program's stress is the engine's stiffness times its own strain, and hand them to the same `slice_answer`. `compare_answers` and the command `python -m anisotropy_fea.repair_files <repair.toml> --out DIR | --abaqus FILE.dat --ansys FILE.txt` set the three answers side by side. Neither program is run by our code, by a test or by the hosted product; the files are not offered on a page (the plan's fourth step decides that).

**Evidence.**

- `cd fea && uv run --extra mesh pytest -q tests/test_repair_files.py`: 7 passed (in the cloud container, CalculiX 2.21). The Abaqus file solved by CalculiX, which reads the same keywords, gives the deck's stresses exactly. The Ansys file's nine engineering constants give back the nine stiffness terms by an inverse written in the test.
- Stand-in output in each program's wording and figures is read back as the deck's answer, and a table with a row missing, of another model, with stresses that are not the stiffness times the strains, or with another width strain is refused.
- What sets the tolerances: Abaqus prints four or five figures in its `.dat`, and Mechanical APDL keeps an element table as 32-bit numbers, seven figures, however many it is written with. Abaqus cuts an input line at 256 characters, so the file wraps its comments at 120.
- No result of a run in Abaqus or in Ansys is stated in this record, so within it the line marked UNVERIFIED above stays as it is.

**What this does and does not show.** The files let whoever has the programs set three solvers' answers for one model side by side; that checks the solver and the way the model is stated to it. The three share the model, so such a run says nothing about the model's assumptions (held flat, elastic, the strip through the middle, the square's mean): those are checked only by the hand calculation, the mesh study and, later, a test.
