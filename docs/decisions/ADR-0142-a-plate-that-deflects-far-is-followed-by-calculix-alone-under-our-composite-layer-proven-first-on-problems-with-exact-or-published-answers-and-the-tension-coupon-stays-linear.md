# ADR-0142: A plate that deflects far is followed by CalculiX alone under our composite layer, proven first on problems with exact or published answers, and the tension coupon stays linear

- Status: Proposed; step 1 (the proof) built 2026-11-25; step 2 (the switch on the plate) not built
- Date: 2026-11-25
- Decided by: Founder, 2026-11-25 (chose "Plan it as its own build" on the card asking whether to add nonlinear geometry to our solve) ; Founder, 2026-11-25 (chose "Build steps 1 and 2" on the card asking "Build nonlinear geometry for the plate, as the plan lays out?") | Drafted by: Claude Code
- Related: [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0054](ADR-0054-a-plate-kind-states-supports-and-loads-as-lists-over-named-regions-and-the-studio-lets-the-user-click-a-region.md), [ADR-0110](ADR-0110-abaqus-setup-words-are-answered-from-a-fixed-glossary-on-the-page-and-every-boundary-condition-and-load-is-drawn-on-the-model-and-listed-under-it-before-and-after-a-run.md) (amendment 4, the glossary's "Nonlinear geometry"), [ADR-0132](ADR-0132-a-repairs-slice-is-solved-in-calculix-as-a-plane-of-eight-node-elements-held-flat-with-the-laminates-far-field-width-strain-and-its-bondline-and-plies-are-read-back-as-means-by-the-engine.md) (the earlier answer that is CalculiX's alone), `fea/src/anisotropy_fea/large_displacement.py`, `fea/src/anisotropy_fea/write_calculix.py`, `fea/checks/large_displacement_cases/`, `fea/tools/large_deflection_closed_forms.py`, `fea/tests/test_large_displacement.py`, `fea/docs/theory.md` (Section 14), risk R-39
- Area: fea

## Context

The founder rebuilt in the workspace a model whose static step had nonlinear geometry switched on, and asked what the switch is. Our solve is linear: it writes equilibrium on the shape the model had before the load. The glossary has said since ADR-0110 amendment 4 that nonlinear geometry is not offered. He chose to have it planned as its own build, and then to build the plan's first two steps.

What was found before this record, by running CalculiX 2.21 on decks our own writer made with `*STEP, NLGEOM`:

- **On a tension coupon the switch changes one thing, and programs differ on it.** A coupon stretches and does not turn. CalculiX relates the second Piola-Kirchhoff stress to the Lagrangian strain by the small-strain constants (its manual, `*ELASTIC`), which multiplies the force by $`(1+e)(1+e/2)`$ at a stretch $`e`$: 1.021 at 1.4 %, the order of a carbon ply's first failure, and 1.055 at 3.6 %. A law that keeps the same constants between the true stress and the logarithmic strain on a section that thins gives $`\ln(1+e)/(e(1+e))`$, 0.979 and 0.948. Both are documented choices of a program, neither is measured for a ply, and they move the force in opposite directions.
- **On a plate that bends far the switch matters a great deal.** A clamped 200 mm square IM7/8552 [45/0/-45/90]s plate, 1.46 mm thick, on 10 mm elements (one mesh, a trial and not a check): under 0.002 MPa the centre deflects 0.244 mm linear and 0.241 mm followed; under 0.01 MPa 1.22 and 0.97 mm; under 0.03 MPa 3.67 and 1.86 mm. Once the deflection passes the thickness the linear answer is far too large.
- **Cost.** The followed runs took 15 to 20 times the linear run on one thread.

The rules that bear on the choice: the engine and the fea package compute every number (ADR-0001), and every full run sets our kernel beside CalculiX as a second answer (ADR-0030); new physics comes from CalculiX under our composite layer and our kernel stays the fast path for flat linear laminates (ADR-0067). A followed solve from CalculiX has no second solver of ours beside it.

## Options considered

1. **Stay linear and keep saying so.** No new dependency and nothing unproven on the page. But a plate or a wing skin that deflects by more than its thickness gets a deflection up to twice the true one with nothing on the page that says so, and a model brought from another program with the switch on cannot be reproduced.
2. **A followed solve in our own kernel** (the four-node shell with von Karman or co-rotational terms and a Newton loop). It would keep two solvers of ours on every number. It is months of work that repeats what CalculiX has had for years and needs its own validation ladder, against ADR-0067 and the founder's direction there ("not something we are trying to replace but more build upon"). Rejected for now; nothing in this record prevents it later.
3. **CalculiX alone, under our composite layer, proven first on problems with exact or published answers.** The writer and the reader exist; what is new is one line of the step and a history by load. The second solver is replaced by a fixed set of problems whose answers do not come from any program of ours, run on every change, and by the small-load check, where the followed solve must be the linear one. Chosen.
4. **Offer the switch on the tension coupon too, or copy another program's large-strain law so that our force matches it.** Rejected: on a coupon the switch changes only the stretch rule, the rule is a property of a program's law and not of the material, and matching one program would mean writing a material law CalculiX does not have in order to agree with a number nobody has measured. The page will say in one line why the coupon is left as it is.

## Decision

Option 3, in the plan's steps, each its own pull request.

- **A followed plate is CalculiX's answer, read by our package.** The plate's eight-node twin is written with `*STEP, NLGEOM` (`write_calculix(..., large=LargeDisplacement(...))`), the load is raised in increments CalculiX sizes itself, and the answer is read as a history, one level per fraction of the load (`large_displacement.follow`, `read_history`). No number of it is our kernel's. This is ADR-0067's rule applied; it is stated here because ADR-0001 and ADR-0030 are otherwise read as "two answers on every run".
- **What stands in for the second solver.** (a) The cases of `fea/checks/large_displacement_cases/`: a clamped square plate under pressure against the table of NACA Report 740, a cantilever strip bent until its tip stands at 0.81 of its length against the elastica, as an isotropic strip and as a [0/90]s laminate, and a strip stretched 3 % against the stretch rule, the same two. Their expected numbers are worked by `fea/tools/large_deflection_closed_forms.py`, which uses neither the package's solvers nor CalculiX. (b) The small-load check: each case under a thousandth of its load must give CalculiX's linear answer and our kernel's. Both run in the fea tests wherever CalculiX is installed, which includes CI.
- **A ply's stresses come from the strains.** CalculiX prints the Lagrangian strain in the plate's first axes and the true stress in the fixed global axes; once a section has turned, the printed stress components are no longer the ply's. Step 2 turns the strain into each ply's axes and multiplies by the ply's stiffness, as the composite layer does for a linear run.
- **Where it is offered.** The plate (step 2), later the wing (step 4 of the plan, not approved). Not the tension coupon. Off by default.
- **Not copied.** No other program's large-strain law, and no arc-length method: the load is raised and never lowered, and a run that cannot hold a load ends there and says which load it reached.

## As built (2026-11-25, step 1)

- `fea/src/anisotropy_fea/write_calculix.py`: `LargeDisplacement` (the first increment, the most increments, the fractions of the load to print at) and the `large` argument of `write_calculix`. Without it the deck is what it was, to the character.
- `fea/src/anisotropy_fea/large_displacement.py`: `follow`, `read_history`, `History`, `Level` (in SI), `under` (the same plate under a part of its load), `eight_node_twin`, the case format and `load_case`, `reading_of`. `spec.spec_from_table` reads a spec that sits in a table of another file; `parse_spec` now calls it.
- `fea/checks/large_displacement_cases/` (five cases; the folder is named in `paths.NOT_TESTS`), written by `fea/tools/large_deflection_closed_forms.py --write`.
- `fea/tests/test_large_displacement.py` (27 tests), `fea/docs/theory.md` Section 14, the checks README, risk R-39.
- Nothing on the page, in the API, in the chat or in the model files changes in this step. The glossary still says the switch is not offered, which stays true until step 2.

## Why (evidence)

`cd fea && uv run pytest -q tests/test_large_displacement.py`: 27 passed in 33 s (cloud container, CalculiX 2.21, 2026-11-25). What the runs gave, on the meshes of the cases:

| Case | Read | CalculiX against the exact or published value |
| --- | --- | --- |
| Clamped square plate, NACA Report 740, Table 5, nine pressures up to a centre deflection of 1.9 thicknesses | centre deflection | -0.17, -0.25, -0.37, -0.76, -1.00, -1.30, -1.46, -1.65, -2.03 % |
| Isotropic cantilever, $`PL^2/EI`$ = 1, 2, 5, 10 | tip deflection; tip displacement along the strip; strain at the lowest integration points below mid-length | +0.04, +0.09, +0.01, +0.02 %; +0.09, +0.21, +0.03, +0.02 %; +0.05, +0.13, +0.00, -0.01 % |
| [0/90]s cantilever, the same loads | the same | +0.05, +0.10, +0.05, +0.08 %; +0.09, +0.21, +0.07, +0.08 %; +0.02, +0.09, -0.03, -0.06 % |
| Isotropic strip stretched 3 % | force at half the pull and at the whole | -0.00001 %, 0 |
| [0/90]s strip stretched 3 % | the same | -0.0015 %, -0.0015 % (the same difference is there in the linear run: the layered bricks' free sides) |

- **The plate's difference is not the mesh's.** At the table's last row: -2.11 % on 8 elements a side, -2.03 % on 16, -2.02 % on 32. The report estimates the error of its own deflections below 2 %. The case's tolerance is 2.5 %.
- **The small-load check.** Under a thousandth of the load the followed deflection differs from CalculiX's linear one by 1 to 2 parts in 100,000 and the stretched strips' force by 4.5 parts in 100,000, which is the rule's $`1.5\,e`$ at that stretch. Our kernel's deflection differs by 0.25 % on the plate (a four-node element where CalculiX has eight-node ones) and 0.01 % on the strips.
- **What is printed.** In the bent strips the printed strain along the strip, at a section turned by more than a radian, equals $`\big((1+e_0-z\kappa)^2-1\big)/2`$ within 0.13 %, with $`e_0`$ the middle's stretch from the force along the strip less $`3EI\kappa^2/(2EA)`$, the shortening the material law itself gives a bent strip. The printed stress at the same points has the strip's stress spread over three global components. CalculiX's manual says the same in words: "the full Lagrangian strain tensor is used" (Static analysis), "S is the second Piola-Kirchhoff stress and E is the Lagrange deformation tensor" (`*ELASTIC`), "for the output on file the second Piola-Kirchhoff stress is converted into the Cauchy or true stress" (Static analysis). The manual read was version 2.11's, the one packaged for Debian; the solver run was 2.21.
- **The loads.** A force keeps its direction; a pressure stays square to the plate as it turns (the reaction of a strip bent far under pressure is the pressure on its chord, within 1 %). Detected by running, held by a test; the manual was not found to state it.
- **Sources of the expected numbers.** NACA Report 740 (Levy, 1942), NASA Technical Reports Server 19930091819, public domain, Table 5 read from the scan. The elastica: Timoshenko and Gere, Theory of Elastic Stability, Section 2.7; its tip values agree with the published tables to their five digits (`test_the_elastica_gives_the_printed_tables_and_the_small_deflection_beam`).
- **Open, and said so.** (1) The report's stresses are not compared: at the plate's centre, at the last row, CalculiX's membrane stress is about 10 % above the report's and its bending stress about 12 % below, their sum 3 % below. The deflections agree, so the plate's stiffness is right; which split is nearer is not settled, and no stress of a followed plate has a published value behind it yet. (2) That other programs relate the true stress to the logarithmic strain in their shells is UNVERIFIED here: their manuals could not be reached from the environment this was built in. The record's choice does not rest on it, since the coupon is left out whichever law another program uses.

## Consequences

- A followed answer rests on one solver's binary. A wrong CalculiX build or a changed convention would show first in the cases, which is what they are for; risk R-39 holds it, beside R-17.
- The cases add about half a minute to the fea tests.
- A followed run costs many linear runs. Step 2 makes it a background job.
- CalculiX 2.21 stops on a layered shell of 14 layers or more (ADR-0117 amendment 1). Step 2 must join same-angle neighbours as the wing does, or refuse such a plate in words.
- The load is raised and never lowered: a plate that snaps or buckles ends its run at the last load it held.
- The tension coupon stays linear, and a model brought from another program with the switch on will differ from ours on a coupon by that program's stretch rule. The page will say so.
- Step 3 of the plan, a private comparison of one plate with a second program, is not approved and not built.

## How we will know it was wrong

- A case fails on a newer CalculiX with the deck unchanged.
- A published large-deflection result with stresses (to settle the open item) differs from CalculiX's ply strains by more than 5 % where the deflection agrees.
- A plate compared with a second program at strains under 1 % differs in deflection by more than 3 %.
- Engineers ask for the switch on tension coupons often enough that "the laws differ" stops being an answer: then the large-strain law is a decision of its own, with test data.
- Followed runs of ordinary plates do not finish in the job's time on the hosted solver.
