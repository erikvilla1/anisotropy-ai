# ADR-0117: A wing is checked in CalculiX with composite shells under superposed load patterns; its panels buckle as the engine's Ritz plates on the model's loads, and flutter is a typical-section estimate

- Status: Proposed; a part of more than 13 layers joins its neighbouring plies of one angle since amendment 1; a shell section per face, offset to its mid-surface, with spar caps or zones, by [ADR-0125](ADR-0125-a-spar-cap-is-a-strip-of-each-skin-over-each-web-with-its-own-layup-any-layup-may-change-in-zones-along-the-span-and-the-hand-calculation-works-a-section-per-stretch.md) amendment 1
- Date: 2026-11-19
- Decided by: Founder, 2026-11-18 ("Start step 1", his choice on the seven-step plan whose step 3 is the finite element check; "please continue with building the software", after step 1) | Drafted by: Claude Code
- Related: [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0116](ADR-0116-a-wings-shape-is-built-by-gmsh-opencascade-from-the-same-description-as-surfaces-at-mid-thickness-and-its-step-file-names-every-part.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0090](ADR-0090-a-tension-coupon-is-built-from-its-material-and-layup-and-the-standard-and-the-software-choose-the-rest-and-say-so.md), `fea/src/anisotropy_fea/wing_model.py`, `fea/tests/test_wing_model.py`, `engine/src/anisotropy_engine/wing/flutter.py`, `engine/tests/test_wing_flutter.py`, `fea/docs/theory.md` Section 10, `engine/docs/theory.md` ("Flutter estimate")
- Area: fea, engine

## Context

Step 3 of the wing generator checks the hand calculation of ADR-0115 with a finite element model of the same description, on the shape of step 2 (ADR-0116). The plan asked for a static solution of every flight case, buckling, the first vibration modes, a mesh study, a comparison with the hand calculation, and a flutter estimate, which needs the wing's mass, its first bending and torsion frequencies and its shear center.

CalculiX 2.21 is the solver we build on (ADR-0067). Its composite shells are S8R only (ADR-0030); each ply is a layer with its own orientation. The envelope of ADR-0115 holds seventeen cases at each altitude. The hand calculation takes the skins as the box between the spars and leaves the skin ahead of and behind the box out; whether that skin is structure or a fairing is not yet in the description. A sandwich core's stiffness was not in the description either: the hand calculation reads only its density.

Tried here (2026-11-19):

- A wing clamped at its root has stresses there that rise as the mesh is refined: the clamp stops the plies' Poisson contraction and the box's warping. On the example wing (`engine/examples/example-wing.toml`, box skins) the lowest margin at the root went -0.142, -0.170 and -0.238 at 40, 28 and 20 mm elements, while the lowest margin outboard of one web height (46 mm) went +0.146, +0.167 and +0.174.
- CalculiX's `*BUCKLE` on a flat composite plate alone gives the closed form within 1 %. On the joined skins, webs and ribs of the example wing with its former web, [45/-45/0]s, under the positive high angle of attack case at 40 mm elements, its first four factors were 2.26, 2.46, 3.08 and 3.25 times limit load, and none of their mode shapes was a web buckle: each was mostly the wing's own static deflection (a correlation of 0.94 to 0.996 with it), largest at the tip, the front web's sideways motion at most 0.14 of the largest. A large-deflection static solution of the same model (`NLGEOM`, about five minutes) with a small sideways push on each bay's front web stopped converging at 1.60 times limit load; the root bay's web had moved sideways 0.25 mm at 0.80, 1.0 mm at 1.28 and 6.4 mm at 1.60, and a Southwell line through the steps above 0.8 gives 1.68. The engine's Ritz plate under the model's mean loads in that bay ($`N_x`$ 11.2, $`N_y`$ 0.2 and $`N_{xy}`$ 79.8 kN/m in the web's ply axes) gives 1.82, and the hand calculation's web check 1.09. The same pattern, `*BUCKLE` well above the large-deflection buckle of the web, was seen on a private wing (its numbers stay out of the repository, ADR-0042).
- The hand calculation had no web buckling check.

## Options considered

1. Load per flight case, one static step for each: 34 cases at two altitudes, each a full solve. Rejected: the model is linear, so four solutions superposed give every case exactly, at a twentieth of the time.
2. Four load patterns superposed (chosen): the spanwise lift for 1 N, a uniform pitching moment, and the aileron's lift and moment, each a consistent linear chordwise load on the skins; every case is a sum with the hand calculation's factors.
3. Buckling by CalculiX's `*BUCKLE` on the whole wing. Rejected: on joined shells it missed the web's buckle, its first mode 34 to 41 % above the large-deflection buckle and no web buckle among its first four, though it is right on a flat plate.
4. Buckling by a large-deflection static solution of every case. Rejected for now: ten minutes for one case on one mesh, and it needs a judgment of where buckling begins.
5. Buckling of each panel between ribs as a flat plate simply supported on four edges, under its mean in-plane loads from the model, by the engine's Ritz series with the laminate's bending-twisting coupling (chosen): the hand calculation's own method on the model's loads. It is low on its edges, which are really stiffer, but a web's mean load leaves out the web's own bending stress, so for a web it is not a lower bound (Consequences).
6. Flutter by a p-k solution with Theodorsen's exact function. Rejected for the engine: it needs Bessel functions from SciPy, which the engine does not depend on; the test suite of the fea package has SciPy and checks the engine's k method against it.
7. Flutter by the k method on a typical section with R. T. Jones's approximation of Theodorsen's function (chosen): the textbooks' estimate (Bisplinghoff, Ashley and Halfman 1955, chapter 9; Hodges and Pierce 2011, chapter 5), in NumPy.

## Decision

`anisotropy_fea.wing_model` builds the CalculiX model: the shape's mesh promoted to S8R composite shells carrying every ply and the core, fibre axes in groups of 2 degrees around the curved skins, ADR-0090's out-of-plane constants, the root clamped. The skins run round the whole airfoil or, with `--skins box`, only between the spars as in the hand calculation; both are run until the description says which. The loads are the four superposed patterns. The checks are the engine's strength ratios of every ply at every integration point and the core's transverse shear against its strength, read outboard of a root zone one web height long, with the root's own values printed beside them.

Panels buckle as in option 5. CalculiX's `*FREQUENCY` gives the first six modes, each named bending, torsion, fore and aft or local by what the webs do at the tip. The uniform moment and the lift pattern give the box's torsion stiffness and shear center; the mesh and the layups' areal masses give the mass properties. These make the typical section of `anisotropy_engine.wing.flutter`, whose k method gives the flutter speed at each altitude of the envelope, as the envelope's kind of airspeed.

A layup's core gains its stiffness (`CoreMaterial`), from the library by its id (`core = "divinycell-h45"`, `library_core`) or typed; the hand calculation still reads only its density. The hand calculation gains web shear buckling (ADR-0115 amendment 2).

`python -m anisotropy_fea.wing_model <wing file> --mesh 40 --skins box --modes` prints every case beside the hand calculation, the modes, the beam properties, divergence, flutter and panel buckling.

## As built (2026-11-19)

- `fea/src/anisotropy_fea/wing_model.py`: the model, the deck, the four patterns, the cases, the modes, the panel buckling, the beam properties and the flutter strip; the command.
- `engine/src/anisotropy_engine/wing/flutter.py`: the typical section, R. T. Jones's C(k), Theodorsen's airload, the k method.
- `engine/src/anisotropy_engine/wing/description.py`, `wing_file.py`, `library.py`: `CoreMaterial`, `Layup.core`, `library_core` for the library's sandwich cores.
- `engine/src/anisotropy_engine/buckling.py`: the Ritz assembly formed on arrays, the same numbers to 2e-14, because the panels of a wing call it hundreds of times.
- `fea/docs/theory.md` Section 10 and `engine/docs/theory.md` ("Flutter estimate") hold the equations.

## Why (evidence)

- `fea/tests/test_wing_model.py`, 13 passed (2026-11-19, about 11 s on a 60 mm box): every pattern sums to its stated lift and moment; the bending and torsion stiffness meet an independent thin-walled beam of the same walls written in the test (1.5 % and 4 % at 40 mm, within 5 % and 7 % on the coarse box); the panel that buckles is the compressed skin; the first mode is bending within 15 % of the hand calculation; the engine's k method meets a p-k solution with Theodorsen's exact function, written in the test, within 1 % (2.170 against 2.184 on the textbook strip).
- `engine/tests/test_wing_flutter.py`, 5 passed: Jones's C(k) within 0.02 of the exact function; the steady lift slope of 2 pi; the strip flutters where its damping crosses zero; mass ahead of the axis and a heavier strip fly faster before flutter.
- The example wing, `engine/examples/example-wing.toml`, at 40 mm elements (2026-11-19; `python -m anisotropy_fea.wing_model ../engine/examples/example-wing.toml --mesh 40 --skins box --modes`, 20 s): 1,260 shells, four patterns in 9.7 s, modes in 4.0 s. With box skins the lowest margin outboard of the root zone (46 mm) is +0.146, the upper skin's 0 degree plies in compression in the positive high angle of attack case, against the hand calculation's +0.691; the tip deflects 227 mm against 189 mm. The gap is not the root's: at every station from 61 to 509 mm the model's strength ratio is 0.67 to 0.70 of the hand calculation's at the same station. The hand calculation takes one spanwise load across a flat skin and gives the skins only the torsion shear; in the model the skins are curved at mid-thickness, the box bends about 20 % more, the spanwise load peaks where the airfoil is thickest, and the lift's shear flows from the webs into the skins at the corners. With skins round the whole airfoil the margin is +0.827 and the tip 138 mm. First bending 19.6 Hz (hand 21.4 Hz), first torsion 246.7 Hz; shear center 186.1 mm from the leading edge (hand 171.2 mm), GJ 17,745 N m² (hand 20,021); divergence at 300.0 m/s equivalent (hand 356.8); flutter at 336 m/s equivalent at sea level, 4.0 times the envelope's flutter speed. The skin panel that buckles first is the upper skin's root bay at 2.46 times limit load (margin +0.641; hand +0.406).
- The example wing's mesh study (box skins; 1,260, 1,773 and 3,069 shells at 40, 28 and 20 mm): the lowest margin outboard of the root zone +0.146, +0.167 and +0.174, the same ply and case each time; the root's own -0.142, -0.170 and -0.238, as in the Context. A private wing was run the same way; its numbers stay in `.local/` (ADR-0042).
- The evidence against `*BUCKLE` on joined shells is the comparison in the Context, on the example wing with its former web (the script is not kept; the numbers can be rebuilt with `wing_model`'s deck and a `*BUCKLE` or `NLGEOM` step). UNVERIFIED on other wings; no test keeps it.
- No wing has been compared with a physical test.

## Consequences

- Every flight case comes from four solutions; a fifth pattern (the wing's own weight, a fuel load) is one more step.
- The checks outboard of the root zone are what the model can stand behind; a real root fitting needs its own model.
- Panel buckling is not a lower bound for a web. The edges are taken simply supported, which errs low, but the mean load leaves out the web's own bending stress, which errs high: on the example wing's former web the Ritz plate on the model's loads was 8 to 14 % above the large-deflection solution. Until a web panel carries its bending stress (a follow-up), a web's margin stands on the hand calculation's web check, which was 32 to 35 % below it there.
- Flutter is an estimate on one strip of two-dimensional air with the structure's own mass. A wing near its flutter speed needs a proper aeroelastic analysis and a ground vibration test.
- We depend on CalculiX's S8R composite shells and `*FREQUENCY`, and on Gmsh for the mesh.

## How we will know it was wrong

- A wing whose finite element stiffness differs from the thin-walled beam of the same walls by more than 10 %, or whose lowest outboard margin moves by more than 0.05 between the two finest meshes.
- A physical or a large-deflection test that buckles a skin panel below the simply supported Ritz load or a web below the hand calculation's web check, or a newer CalculiX whose `*BUCKLE` agrees with the large-deflection solution on joined shells.
- A ground vibration test whose first bending or torsion frequency differs from the model's by more than 15 %.

## Amendment 1, 2026-11-20 (a part of more than 13 layers joins its neighbouring plies of one angle)

**Context.** The wing page's finite element check (ADR-0119) stopped on a wing whose web was the 14-ply layup `[45, -45, 45, -45, 45, -45, 0]s`, the web the hand calculation recommends when a thin web buckles. CalculiX 2.21 as Ubuntu 24.04 builds it, the one in the solver image (`Dockerfile`, `calculix-ccx`), ends with "stack smashing detected" (exit -6) while reading a composite shell section of 14 layers or more, and solves 13. The limit is the solver's, not the wing's: the D3039 check's own deck (`fea/checks/d3039-im7-8552/decks/d3039-im7-8552-ccx.inp`) with its 8 layers repeated to 13 finishes, and to 14 or 16 stops the same way. Each ply was a layer of its own, so any part with a core and six plies a side, or with seven plies a side, could not be checked.

**Options.** (a) Join neighbouring plies of one angle into one layer of their summed thickness when, and only when, the stack would exceed 13 layers. The stiffness is the same; the stresses of the pair are read at two points through it instead of two in each ply, a small change for a membrane-loaded wing. Chosen. (b) Join them always. Rejected: it changes every wing's results that solve today, the example's among them, for no gain. (c) Build CalculiX from source without the limit, in the image and on every machine. Rejected for now: a solver build of our own to keep, and the cause is not yet found in its source. (d) Refuse every part over 13 layers. Kept only for a stack still over 13 after joining, for example `[45, -45, 45, -45, 45, -45, 0, 90]s`, which joins to 15.

**Decision.** `wing_model.layers` joins neighbouring plies of one angle once the stack passes `MAX_LAYERS = 13`; `check_describable` refuses a part still over it, in words that say how to change the layup. The 14-ply web joins its middle pair of 0 degree plies and is solved as 13 layers. No result of a wing within the limit changes. Drafted with the founder's choice of the background check (ADR-0119); not yet confirmed by the founder.

**Evidence.** `fea/tests/test_wing_model.py::test_past_the_solvers_limit_plies_of_one_angle_side_by_side_are_one_layer` and `::test_a_fourteen_ply_web_is_solved_as_thirteen_layers` (the solve through CalculiX), 2026-11-20; `cd fea && uv run --extra mesh pytest tests/test_wing_model.py tests/test_wing_check.py`: 24 passed. The coupon jobs' CalculiX twin (`write_calculix.py`) also writes every ply as a layer and is not changed here: its deck of a coupon of more than 13 plies would stop the same way, and how a coupon run takes that is not yet checked (UNVERIFIED).
