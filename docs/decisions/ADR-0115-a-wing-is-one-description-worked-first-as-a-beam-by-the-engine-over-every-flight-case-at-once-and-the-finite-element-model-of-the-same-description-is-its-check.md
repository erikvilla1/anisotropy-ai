# ADR-0115: A wing is one description, worked first as a beam by the engine over every flight case at once; the finite element model of the same description is its check

- Status: Proposed
- Date: 2026-11-18
- Decided by: Founder, 2026-11-18 ("Wing generator first", his choice between the wing generator and the import of drawn shapes; "our code needs to be able to have fast results if i change length f wing, change geometry, change, spar geometry, change skin geometry,change layup etc"; "Start step 1", his choice on the question "Start building step 1 of the wing generator now?") | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0007](ADR-0007-validation-cases-store-numbers-only.md), [ADR-0019](ADR-0019-physics-library-mirrors-engine-theory.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0073](ADR-0073-the-kernel-and-the-failure-checks-form-every-element-at-once-in-numpy-with-the-same-numbers-to-the-last-bit.md), `engine/src/anisotropy_engine/wing/`, `engine/src/anisotropy_engine/sandwich.py`, `engine/docs/theory.md` Sections 12 and 13, `engine/validation/wing_cases/`, `engine/examples/example-wing.toml`, [ADR-0116](ADR-0116-a-wings-shape-is-built-by-gmsh-opencascade-from-the-same-description-as-surfaces-at-mid-thickness-and-its-step-file-names-every-part.md) (the shape, step 2)
- Area: engine

## Context

The product analyses coupons. One of its first two real projects is the design and analysis of a composite wing, and the founder chose to build a wing generator before the import of drawn shapes. He has a wing calculation of his own from a class, in inches and pounds, which he describes as "isn't even fully coded there is so much missing": two symmetric load cases of the seventeen its class asks for at two altitudes, no rolling cases, no check at proof load. Timed here, it takes 0.06 s for two cases and 1.0 s for thirty-four, because every ply of every station of every case is a Python call. He asked for a result that follows every change of the span, the section, the spars, the skins and the layup.

The class's material, its request for proposal and any number compared with its results may not be committed (ADR-0042), and no class name may be shown to a user (the founder, 2026-11-18, on the name of the first template: "users don't need to see that").

The plan agreed with the founder has seven steps: (1) the description and the hand calculation, (2) the shape and a STEP file, (3) the finite element model in CalculiX with a mesh study, (4) the page, (5) a statistical preview trained on our own finite element runs, (6) the import of a drawn shape, (7) a SolidWorks add-in. This record covers step 1 and what the later steps may rely on.

## Options considered

1. **One wing description in the engine, worked as a beam on arrays; the finite element model of step 3 reads the same description.** Chosen.
2. **Only the finite element model.** Rejected as the first answer: a shell model of a wing takes seconds to tens of seconds per change, and thirty-four cases more, so it cannot follow typing; and a number with no hand calculation beside it has nothing to be checked against (ADR-0112 took the same view for coupons).
3. **Keep the founder's script and call it from the product.** Rejected: its numbers would not come from the engine (ADR-0001), it works in inches and pounds inside (ADR-0002), it assumes values a user would have to know about (a sea-level density for every altitude, a core density, an airfoil file), and it is the class's work.
4. **A trained model in place of the calculation.** Rejected for step 1: there is nothing to train it on until the finite element model exists, and its place is step 5, beside the calculation and checked by it.

Within option 1:

- **Where the calculation lives.** In the engine (`anisotropy_engine.wing`), not the fea package: it is closed-form laminate and beam theory, it needs no mesh, and ADR-0001 puts every number of an analysis result in the engine. The fea package will hold the shell model.
- **Loops or arrays.** Arrays over cases and stations (as ADR-0073 did for elements), with one stress state per distinct ply angle, since the plies of a symmetric layup under in-plane load strain alike. Loops, as in the founder's script, are the 1.0 s.
- **Numerical or exact span loads.** Exact integrals of Schrenk's load and of the aileron's, so the loads do not depend on the number of stations; only the deflection and the twist are integrated numerically.
- **A missing input.** A speed, the gust entry, the aileron or the proof factor that is not stated leaves out the cases or the margin that need it, each listed with what it needs. Rejected: a default (ADR-0003), and refusing the whole run, which would give an engineer nothing until the last number is known.
- **Units.** The wing file states "SI" or "US" and its speed unit; `wing_file.py` converts on the way in and out with its own table for the quantities a wing adds (force, mass, density, altitude, speed, stiffness). Rejected for now: adding them to `units.py`, whose table the website's laminate chat offers to users by name (`engine/src/anisotropy_engine/data/units.json`).
- **Validation cases.** Wing files with expected numbers live in `engine/validation/wing_cases/`, beside `cases/`, because the laminate case runner and the problem documents read `cases/` as laminates. Their closed forms are in the same `closed_forms.py`, which imports nothing from the engine (ADR-0007, ADR-0042).

## Decision

- **The description** (`wing/description.py`, SI): one side of a straight wing of constant chord, an airfoil (NACA four digits by formula, or points), two spars by chord fraction, an optional rib spacing, a skin layup and a spar layup, each the outer half of a symmetric laminate with an optional core between the halves, the aerodynamic center and pitching moment coefficient, and a flight envelope: weight, the two limit load factors, seven speeds stated as equivalent or true, altitudes, the gust load factors or the gust speeds they are derived from, an aileron as a change of lift and moment coefficient over its span, the ultimate factor, an optional proof factor and the failure criterion.
- **The calculation** (`wing/analysis.py`, `wing/section.py`, `wing/loads.py`): the section as the box between the spars, by thin-walled beam theory; seventeen cases at every altitude (level flight at five speeds, four maneuver corners, four gusts, four rolls); for every case and station the in-plane load of each skin and web, the strength ratio of its weakest ply angle by the engine's own criteria, and the skin's buckling ratio; deflection, twist, mass, stiffness and first bending frequency; margins at ultimate and at proof. The equations and their sources are in `engine/docs/theory.md` Sections 12 and 13.
- **It is a hand calculation and says so.** What it leaves out is listed in the theory document: taper, sweep, shear lag, the skin outside the spars, web buckling, shear with compression in skin buckling, the core's transverse shear, the wing's own weight. The shell model of step 3 reads the same description and is shown beside it; where they differ, the difference is shown, not hidden.
- **The founder's script** is a regression check only, kept with the class's wing under `.local/wing/class-wing/` and never committed. The public example (`engine/examples/example-wing.toml`) and the validation wing are our own, with library or cited material values.
- **No class or course name** appears in the engine's names, files, templates or messages.
- **Physics cards.** The website's physics library shows what the product does, and the product has no wing page yet. The cards for Sections 12 and 13 are written with the page in step 4, not now; until then `engine/docs/theory.md` is the only statement of these equations. This departs from ADR-0019 for the time between the two steps.

## As built (2026-11-18)

- `engine/src/anisotropy_engine/sandwich.py`: `sandwich_abd`, the faces' plies at their own heights with a core of no in-plane stiffness.
- `engine/src/anisotropy_engine/wing/`: `airfoil.py`, `atmosphere.py`, `description.py`, `loads.py`, `section.py`, `analysis.py`, `wing_file.py`.
- `engine/examples/example-wing.toml` and `engine/examples/wing_calculator.py`, which prints a wing file's design summary and its table of margins.
- `engine/validation/wing_cases/constructed-straight-sandwich-wing.toml` with `straight_sandwich_wing` in `engine/validation/closed_forms.py`.
- `engine/tests/test_sandwich.py`, `engine/tests/test_wing.py`, `engine/tests/test_wing_validation.py`.
- `docs/manual/build.py` reads the new modules for the theory document's code markers.
- Not built: a page, an API endpoint, a physics card, taper, and anything of steps 2 to 7.

## Why (evidence)

- `cd engine && uv run pytest`: 582 passed (2026-11-18), 57 of them new.
- The constructed wing: of 26 numbers (stiffnesses, shear center, buckling load, mass, frequency; root loads, strength ratios, deflection and twist of a maneuver, a gust and a rolling case), 24 agree with the closed form worked without the engine to 1e-12 and the two numerically integrated ones, deflection and twist, to 1e-6 (`engine/tests/test_wing_validation.py`).
- The ply check equals `first_ply_failure` of the whole laminate to 1e-12 (`test_the_ply_check_is_the_engines_first_ply_failure_of_the_whole_laminate`); the gust formula agrees with the regulation's printed form to its rounding (`test_gust_load_factor_agrees_with_the_regulations_printed_form`).
- Time: the example's 34 cases at 51 stations take 0.009 s in this container, 0.030 s at 201 stations (`timeit` over 50 runs), against 1.0 s for 34 cases in the founder's script.
- The founder's script and the engine on the class's wing: `.local/wing/class-wing/compare.py` (not committed; its numbers are not quoted here, ADR-0042).
- No evidence yet that the beam model is close to a wing's real behaviour: no finite element model and no test has been compared. That is step 3 and the class's test.

## Consequences

- An engineer gets every case of the envelope in a hundredth of a second, so a page can rerun it on every change.
- The engine now holds flight loads and beam theory beside laminate theory, and one more file format, the wing file.
- Two unit tables exist until the wing's quantities are offered on the site.
- The equations of Sections 12 and 13 have no physics card until step 4.
- The calculation's approximations (the shear split between the webs, the flat skins, the long-plate buckling load without shear) are now ours to state wherever a margin is shown.

## How we will know it was wrong

- The shell model of step 3 differs from this calculation by more than 15 % on root bending strain or tip deflection for the example wing, without a reason the list of limits already names: then the section model, not the mesh, needs work.
- The 34 cases take more than 0.1 s on a laptop after later additions (taper, more members): then a page can no longer rerun it on every keystroke.
- An engineer enters a wing this description cannot hold (taper, three spars, different skins top and bottom) before step 3 is done: then the description is the next thing to widen.

## Amendment 1, 2026-11-19 (divergence and aileron reversal in the hand calculation; a rib layup and the section's lift slope in the description)

**Context.** On 2026-11-18 the founder shared his class's notes on aeroelasticity ("not sure if this helps with anything, also please continue with building the software"). They work the divergence and the aileron reversal speed of a uniform straight wing from its torsion stiffness, the distance from its shear center to its aerodynamic center, the lift slope and the aileron's lift and moment, all of which the calculation already has but the lift slope. The notes are course material and stay out of the repository (ADR-0042); the equations are the textbooks' (Bisplinghoff, Ashley and Halfman 1955, chapter 8; Hodges and Pierce 2011, chapter 5). Flutter needs the wing's mass and its bending and torsion frequencies, which the finite element model of step 3 gives. The shape of step 2 (ADR-0116) needs the ribs' layup.

**Options.** (1) Add both checks to the beam calculation now, with exact closed forms on the uniform wing, a part-span aileron included. (2) Leave them to the finite element model: it would need a fluid model the plan does not have. (3) The class's typical section of unit length: simpler, and it does not use where the aileron sits along the span. Chosen: 1. For the lift slope: the gust entry's slope is the whole aircraft's and optional with the gust speeds, so the section's is its own optional entry, `[aerodynamics] lift_curve_slope`; without it, both checks are listed as not run with what they need.

**Decision.** `anisotropy_engine.wing.aeroelastic` computes the divergence dynamic pressure, the lift a part-span aileron adds to the twisting wing and the reversal dynamic pressure at which it adds none (by bisection; the engine has no SciPy). `WingResult.aeroelastic` gives both as equivalent airspeeds beside the envelope's dive speed, the highest equivalent dive speed of its altitudes when the speeds are true airspeeds. A wing whose aerodynamic center is not ahead of its shear center never diverges, and an aileron whose moment twists the nose up never reverses before divergence; the report says so. `Wing.rib` is an optional layup, refused without a rib spacing; the hand calculation does not use it. The example wing gained ribs every 0.5 m with a [45/-45]s layup and a lift slope of 6.0 per radian; its lowest margin is unchanged (+0.304).

**Evidence.** `engine/tests/test_wing_aeroelastic.py`, 21 passed: the same torsion equation solved by finite differences without these formulas gives the divergence pressure to 1e-6, the twist integral to 2e-5 for both signs of lambda squared and near zero, and the aileron's lift to 1e-4, changing sign within 1 % of the reversal pressure. `cd engine && uv run pytest`: 603 passed (2026-11-19). The example wing: divergence at 355 m/s and reversal at 278 m/s equivalent airspeed, 5.1 and 4.0 times its dive speed. No wing has been compared with a flight or wind tunnel test.
