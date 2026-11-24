# ADR-0140: A repair's bond is followed to failure in a plane solver of our own: a traction-separation law across the bondline, the path followed by the energy the bond spends, checked against exact fracture answers and MOOSE

- Status: Proposed; the route, the page, the report and the chat since amendment 1
- Date: 2026-11-24
- Decided by: Founder, 2026-11-24 ("let's keep workigin what we were doing earlier on this thread", read as the plan's sixth slice; the plan's route for it, our own bond element with MOOSE as the check, was put to him on 2026-11-20) | Drafted by: Claude Code
- Related: [ADR-0130](ADR-0130-a-bonded-repairs-hand-calculation-is-the-stepped-lap-as-a-shear-lag-model-in-the-engine-the-patchs-force-at-every-step-boundary-the-adhesives-elastic-limit-and-the-long-overlap-strength-of-a-yielding-adhesive.md), [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md), [ADR-0132](ADR-0132-a-repairs-slice-is-solved-in-calculix-as-a-plane-of-eight-node-elements-held-flat-with-the-laminates-far-field-width-strain-and-its-bondline-and-plies-are-read-back-as-means-by-the-engine.md), [ADR-0133](ADR-0133-the-public-record-states-no-result-of-a-run-in-abaqus-or-ansys-and-names-no-licence-the-numbers-of-such-comparisons-are-kept-privately.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), `fea/src/anisotropy_fea/repair_model.py`, `engine/src/anisotropy_engine/repair/step_lap.py`
- Area: fea, engine, api, website, assistant

## Context

The repair has two answers so far, both elastic. The hand calculation (ADR-0130) and the solved slice (ADR-0132) give the load at which the adhesive first reaches its strength at one point. A bonded joint carries more than that: the adhesive softens where it is most loaded and the load moves along the bond, until the bond lets go. The elastic slice cannot say when. Its stress at a step's end has no upper bound, which is why its peaks are read as means over a square of adhesive.

The plan's sixth slice is "the bond that softens and lets go, and the load at which the patch detaches", checked against fracture tests with exact answers, a published repair study, then Abaqus and Ansys. The plan put four routes to the founder on 2026-11-20 and recommended the first, with one trial before committing: the peel test, which has an exact answer, in a prototype of ours and in MOOSE.

ADR-0067 has new physics come from an open-source solver we drive, CalculiX first, and asks any nonlinearity solved by code of ours for a record saying why CalculiX, or another open-source solver, cannot provide it. This is that record. CalculiX, which solves the elastic slice, has no element or material for a bond that softens. MOOSE has one; why it is the check and not the solver is under the options and the evidence.

## Options considered

The solver:

1. **A plane solver of our own for this run, with a bond element (chosen).** NumPy and SciPy, in the fea package, on the slice's own mesh. Every line is ours to check, and the control of the path can be the one this problem needs. More code of ours to keep right.
2. **MOOSE as the solver, driven as CalculiX is.** What ADR-0067 would have us do first: the bond law is built in, and a national laboratory maintains it. Against it, each from the trial: the installation is 4 GB, in a hosted container that holds CalculiX in a few megabytes; its syntax has no control that follows a path past its peak (no arc-length method), so the load at which the bond lets go can be reached only under steps of displacement with artificial damping; the version tried gives a pressed bond a shear law longer than stated; and it took four to five times as long. Kept as the independent check.
3. **Code_Aster.** Has bond laws. A large installation, input in French, no advantage over MOOSE as a check.
4. **CalculiX with a material routine of ours.** Needs CalculiX rebuilt from source wherever it runs, including the hosted container. Rejected.

How the bond is represented:

1. **Pairs of nodes across the bondline, in place of the adhesive's elements (chosen).** The bondline's thickness stays in the mesh; the adhesive's stiffness, strength and energy are the law's. The usual way to model a thin adhesive layer.
2. **The adhesive kept as elements, with a surface of no thickness inside it.** Needs a penalty stiffness that is no property of the adhesive, and the elastic adhesive around the surface still has unbounded corner stresses.

The law:

1. **Two straight lines (bilinear) in peel and in shear, six numbers (chosen for the first build):** two stiffnesses, two strengths, two fracture energies. Onset where the two stresses, each over its strength, reach 1 as a sum of squares; failure where the two energies spent, each over its fracture energy, add to 1. That linear sum needs no seventh number and is the lowest of the usual mixed-mode rules.
2. **A law with a plateau for a ductile adhesive**, which is what the hand calculation's yielding adhesive is. It needs the adhesive's plastic strain, which the repair file does not hold. Left for an amendment; the prototype's law already takes a plateau.
3. **The Benzeggagh-Kenane rule** for the mixed-mode energy. A seventh number, fitted to mixed-mode tests few adhesives have. Not now.

How the path is followed:

1. **Each step spends a set amount of energy in the bond (chosen)** (Gutiérrez 2004; Verhoosel, Remmers and Gutiérrez 2009). The load factor is an unknown of the step. The path is followed through its peak and through snap-backs, and nothing artificial is added.
2. **Steps of displacement with Newton's method.** Tried first in the prototype: it stalled on the peel test at 2.6 mm of opening on a 0.5 mm mesh, at 3.4 mm on 0.25 mm and at 6.5 mm on 0.125 mm, each time where one more point of the bond had to start softening. A line search did not help.
3. **Artificial damping of the damage (what MOOSE and Abaqus offer).** Gets through, at the cost of a number with no physical meaning that moves the answer until it is made small enough.

## Decision

1. **The solver.** A new module in the fea package solves the slice of ADR-0131 with eight-node plane elements with four integration points, the element CalculiX solves it with, on `slice_mesh`'s graded grid. Each ply's stiffness is the engine's (`anisotropy_engine.repair.solid`); the holds, the far-field width strain and the load on the panel's end are those of ADR-0132, all scaled by one load factor.
2. **The bond.** Along every flat bond the adhesive's elements are replaced by pairs of nodes, the laminate's under and the patch's over, each pair one integration point with Simpson's weights. The stiffness in shear is the adhesive's shear modulus over the bondline's thickness; in peel, its modulus when kept from straining in its plane, over the thickness. A pair pressed together carries the pressure undamaged. Damage only grows. Cut faces stay open, as ADR-0132 has them by default.
3. **The numbers.** Six for an adhesive. Four are in the repair file already (`shear_modulus` and `poisson` with `thickness`, `shear_strength`, `peel_strength`); two are new, `peel_energy` and `shear_energy`, the fracture energies in peel and in shear. The run is refused without all six (ADR-0003). The example repair gets round numbers of its own for them.
4. **The path.** Elastic to the first point at onset, found by scaling one linear solve; steps in load while the bond spends little; then steps of energy spent, until the load has fallen well below its peak or no bond is left.
5. **The answer.** The load at onset, the largest load the path reaches, where the damage started and how far it had spread at that load, and the curve of load against the end's movement. What the page may call the largest load is the founder's to say when the page is built; until he says, it is "the load at which the bond lets go in this model", never the repair's strength: the plies are not checked for damage until slice 7, and no test of the repair has been compared.
6. **The checks,** in this order: (a) cases with exact answers, run with the tests: one bond in peel, in shear and mixed; the peel test against beam theory; the shear test against beam theory at rising strength; a patch pulled off a strip held flat against the exact energy answer; (b) the elastic stage against CalculiX's slice; (c) the peel and shear tests in MOOSE, its input files and curves kept in the repository; (d) the published stepped repair tests the plan names; (e) Abaqus and Ansys on the founder's word, their numbers kept privately (ADR-0133).

Not decided here: damage in the plies (slice 7), a law with a plateau, a bond on the cut faces, fatigue, heat and moisture, and what the page, the chat and the report show.

## As built (2026-11-24)

Built as decided, in `fea/src/anisotropy_fea/bond_solver.py` (the law, the plane elements, the path) and `fea/src/anisotropy_fea/repair_bond.py` (the repair's model, its run, its answer and report; `python -m anisotropy_fea.repair_bond <repair file> --out <folder>`). The engine reads the two new numbers and says what a run still needs (`bond_needs`). The theory is `fea/docs/theory.md`, Section 12. The record was drafted as ADR-0137 and renumbered 0140 the same day, before its pull request, because another open pull request had taken 0137.

What the plan left open, as built:

- **Where the path ends** (item 4). It is followed until the load has fallen 10 % below the largest it reached, the whole bond has parted, or 1,500 steps are taken. The load at which the bond lets go is the first peak after which the load falls by 5 % of it before rising above it again; a path that ends before such a fall reports no such load and says why.
- **Where nothing is softening**, because what was has parted and nothing else has begun, no step can spend energy. The load leads again there until something does.
- **The mesh.** The elements beside every edge are a quarter of the bondline's thickness long (the elastic slice uses an eighth, with two elements through the adhesive; here the adhesive is the pairs).
- **The answer** (item 5) also holds, state by state, the length of bond softening and parted, and the largest shear and peel stress on each stretch of the bond at first softening and at the load at which the bond lets go.
- **The example's numbers** are round ones of our own, for no named adhesive: peel strength 40 MPa, fracture energy 0.5 N/mm in peel and 2.0 N/mm in shear, beside the shear strength of 30 MPa it had. The example of a patch bonded on top has the same.

The checks of item 6:

- (a) and (b) are tests, `fea/tests/test_bond_solver.py` and `fea/tests/test_repair_bond.py`: 17 and 17 pass. The peel test's load is beam theory's within 2 % while the crack grows; the shear test's largest load is 7.8 % under beam theory's at 60 MPa; the strip runs at its energy answer within 0.5 %. On CalculiX's own nodes and elements the plane elements return CalculiX's strains and stresses within 2 parts in a million; held to the stepped lap's assumptions the bond first softens at the lap's elastic limit load within 1 part in 10,000; with the bond whole the patch carries, midway along every step, what it carries in CalculiX's slice within 0.3 % of the load.
- (c) The MOOSE input files and curves of the shear test and the peel test are in `fea/checks/bond_cases/`. A test holds our largest load in the shear test to MOOSE's 729.5 N within 0.3 %. No whole repair was run in MOOSE: its version at hand ends a pressed bond's shear law at √2 times the stated slip, and the repair's bond is pressed where it first softens.
- (d) and (e) are not done: no published repair test is compared, and no Abaqus or Ansys run was made.

**The example repair** (flush, four steps of 12.5 mm, bondline 0.1 mm): the bond first softens at 184.0 N/mm, 37.38 mm from the middle, in the adhesive on the ledge of step 2, in shear alone with the bond pressed together by 14.03 MPa there. It lets go at 1,339.8 N/mm with 18.65 mm of its 62.1 mm softening and none parted; the path was followed on to 1,153 N/mm, with 1.59 mm parted. 3,045 elements, 319 pairs, 46 states, about 10 s on four cores. The mesh study, each row one run:

| Longest element, mm | Element beside an edge, mm | Pairs | First softens, N/mm | Lets go, N/mm | Softening then, mm |
| --- | --- | --- | --- | --- | --- |
| 1.5625 | 0.2 | 175 | 174.3 | 1,337.0 | 18.86 |
| 1.5625 | 0.1 | 229 | 178.3 | 1,341.2 | 18.61 |
| 1.5625 | 0.05 | 265 | 181.2 | 1,341.2 | 18.80 |
| 1.5625 | 0.025 (the run's) | 319 | 184.0 | 1,339.8 | 18.65 |
| 1.5625 | 0.0125 | 373 | 183.1 | 1,336.8 | 18.69 |
| 1.0 | 0.025 | 341 | 183.9 | 1,341.4 | 18.42 |
| 0.25 | 0.025 | 613 | 184.2 | 1,341.1 | 18.58 |
| 0.25 | 0.0125 | 665 | 183.2 | 1,337.0 | 18.46 |

The load at which the bond lets go stays within 0.35 % over the eight. The load of first softening rises by 5.6 % from the coarsest to the run's mesh and moves 0.5 % on the finer ones.

The load of first softening, 184.0 N/mm, is below the solved slice's elastic limit load for the same repair, 260.8 N/mm. The two are read differently: a point of the bond here, a mean over a square of adhesive there (ADR-0132). The difference was not traced further: UNVERIFIED.

In the solved slice the first ply reaches a strength at 466.1 N/mm, below the load at which the bond lets go. For the example the plies decide, which this run cannot see; that is slice 7.

**The patch bonded on top** (the other example): first softens at 161.9 N/mm at the patch's edge, lets go at 873.2 N/mm with 26.7 of its 40 mm softening; 873.4 N/mm on a mesh four times coarser beside each edge.

No evidence yet: the run's time on the hosted container (UNVERIFIED; the route allows it 120 s), and any comparison with a test of a repair.

## Why (evidence)

A trial on 2026-11-24, before any product code: a prototype of the decision's items 1, 2 and 4 (with the Benzeggagh-Kenane rule, which is the same law when peel and shear have equal numbers, as in the comparisons below) and MOOSE (image `idaholab/moose`, version 2026.08.12-167ee97). The scripts, input files and curves are kept with the project's files, not in the repository; the checks of item 6 replace them as they are built. A unidirectional carbon ply (E1 150 GPa), 0.5 mm elements unless said.

- **Peel test** (two arms 100 by 1.98 mm, 20 mm wide, crack 30 mm, fracture energy 0.352 N/mm, strength 30 MPa). While the crack grows, opening 2.0 to 5.3 mm, the prototype's load is within 1.02 % of beam theory's with the root correction, mean +0.00 %; MOOSE's within 0.81 %, mean +0.32 %. With the ends moved the same way the two programs' elastic stiffnesses are 0.192961 and 0.192988 N/mm at 0.05 mm of opening.
- **Shear test** (span 100 mm, crack 35 mm, fracture energy 1.0 N/mm, strength 60 MPa). Peak load 729.5 N in the prototype (728.8 N on 0.25 mm elements); in MOOSE 731.0, 730.0 and 729.5 N as its damping is made smaller. Against beam theory's 790.3 N the prototype is 7.8 % low at 60 MPa, 2.65 % at 120 MPa and 0.40 % at 240 MPa: beam theory assumes a sharp crack, and the softening zone shrinks as the strength rises.
- **After the shear test's peak** the programs drift apart, 592.1 against 606.4 N at 2.0 mm, both settled in mesh and step. Cause found: in that MOOSE version a bond that is not opening ends its shear law at √2 times the stated slip (`_delta_final = std::sqrt(2) * 2 * GII_c / S` in `BiLinearMixedModeTraction.C`), shown on one bond sheared while pressed. MOOSE's current source no longer has the factor. A MOOSE comparison of a pressed bond needs a later version.
- **A patch pulled off a strip held flat**, the repair's own arrangement (strip 2 mm, patch 1 mm, energy 0.5 N/mm in both modes). The bond runs at 950.8 N/mm; the exact answer by energy, √(2 Gc Sa (Sa + Sb) / Sb), is 950.9 N/mm. The first point reaches its strength at 211.6 N/mm, under a quarter of that. With an adhesive's unequal numbers (peel 40 MPa and 0.5 N/mm, shear 30 MPa and 2.0 N/mm, stiffnesses 4 to 1) it runs at 1,893.3 N/mm on 0.5 and on 0.25 mm elements, with no step cut back.
- **Time**, four cores: the prototype 84 s for the peel test in 1,570 small steps, 8 s for the shear test, 14 to 18 s for the strip; MOOSE 337 s and 37 to 58 s. MOOSE's installation in the image is 4.0 GB, and a search of its whole input syntax for an arc-length or Riks control finds none.

No evidence yet: the slice of a real repair run to failure, its time on the hosted container, the elastic stage against CalculiX, and any comparison with a test of a repair.

## Consequences

- The repair gets a third answer, a failure load of the bond, that a finer mesh does not move: the law caps the stress the elastic corner leaves unbounded.
- The fea package now holds a finite element solver for a plane of solids, beside its plate and shell kernel. Its elastic stage has CalculiX's slice to be held to.
- Two numbers are asked of the engineer that datasheets seldom give. A repair without them keeps its two elastic answers.
- MOOSE is a check kept as files and recorded curves, not a dependency: nothing that runs needs it.
- It is the first nonlinear solve in code of ours, the exception ADR-0067 allows by a record. The elastic slice stays CalculiX's, and the kernel for coupons is untouched.
- The answer is the bond's alone. A repair whose plies fail first is not caught until slice 7; the first-ply check of ADR-0132 stays beside it.

## How we will know it was wrong

- A case with an exact answer is off by more than 2 % on the mesh the run uses.
- The elastic stage differs from CalculiX's slice by more than the mesh study's 2 %.
- The path cannot be followed to the peak on a real repair, or the run takes more than a few minutes on the hosted container.
- CalculiX gains a bond that softens, or MOOSE a control that follows the path past its peak: ADR-0067's first choice then applies again.
- The published repair tests are missed by more than their own scatter with the adhesive's measured numbers put in.

## Amendment 1, 2026-11-24 (the route, the page, the report and the chat; proposed, not yet confirmed by the founder)

**Context.** The record left open what the page, the chat and the report show. They are built with the solver so that the run can be seen and judged.

**Options.** (1) *Run the bond with every solve of the slice.* One click fewer; rejected, since the run takes about ten seconds against a few for the slice, and needs three numbers most repairs do not state. (2) *Its own request, on its own button (chosen).* (3) *Draw the load against the movement of the panel's end.* The usual curve; rejected after it was drawn: the long elastic panel makes it a nearly straight line with a snap-back at its end, which shows nothing. The load is drawn against the length of bond past its strength instead. (4) *Draw the peel stress along the bond with the shear.* Rejected: where a step's end presses on the laminate the peel stress has spikes of contact pressure that hide the rest; the table gives the largest peel stress on each stretch.

**Decision.**

1. `POST /v1/repairs/bond` takes the repair as the other repair routes do, runs `anisotropy_fea.repair_bond` in a process with 120 s allowed, and returns its report. A repair that lacks what the run needs is refused with what it lacks. `POST /v1/repairs/analyze` also returns `bond_needs`.
2. The page asks for the run from a button in the Solve step and beside the results, shown once the repair states the six numbers. The card under the results says "it first softens at ... and lets go at ... in this model. Not the repair's strength." The details show the run's lines, a table by stretch of the bond, the load against the length of bond past its strength, and the adhesive's shear stress along the bond at first softening and at the load at which it lets go. Where the solved slice's first ply reaches a strength below that load, the page says so beside it. A run of the repair as it was is marked as such after a change. The report gains the section.
3. The chat reads "when does the bond let go", "where does the bond soften first", "follow the bond", the two fracture energies as values the repair states, and "does the bond fail before the plies?", which it answers with Yes or No from the two loads. It changes neither fracture energy, and never reads one as the load, whose unit it shares. A question that asks for a strength or a verdict is told the page gives none, with the bond's load added to what it does give.
4. The reference page "Bonded repairs" gains two sections, "How a bond softens and lets go" and "Fracture energy", for questions of why and what.
5. The MCP server gets no tool for the run yet.

What the page calls the load is still the founder's to say (the Decision's item 5).

**Evidence.** `tests/browser/repair.spec.ts` (15 pass, two of them the bond's), `tests/repair.test.ts` and `tests/repair-chat.test.ts` (50 pass with the bank's check), `api/tests/test_repairs_api.py` (27 pass, 3 skipped without a database; one runs the real solver and holds the route's answer to the kept run), 16 questions in `tests/assistant-questions/repair.json`. The repair's chat is read by fixed patterns and no model answers there, so no real-model run was made.
