# ADR-0130: A bonded repair's hand calculation is the stepped lap as a shear-lag model in the engine: the patch's force at every step boundary, the adhesive's elastic limit, and the long-overlap strength of a yielding adhesive

- Status: Proposed; a lap may also end at a plane of symmetry since amendment 1, and a repair stated by its plies gives each step's moduli by [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md)
- Date: 2026-11-20
- Decided by: Founder, 2026-11-20 ("ideally the next project is step patch", on what comes after the wing; then "Downloads, then repair hand calc", his choice on the card "Start building now, and with which piece first?", whose plan names the repair's hand calculation as the step-lap shear-lag model, Volkersen per step and Hart-Smith after it). The form of the model in code, its boundary conditions, what a file states, the cases and what is left for later are the drafter's | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0007](ADR-0007-validation-cases-store-numbers-only.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), `engine/src/anisotropy_engine/repair/`, `engine/docs/theory.md` Section 16, `engine/validation/repair_cases/`, `engine/validation/closed_forms.py`, `engine/tests/test_step_lap.py`
- Area: engine

## Context

- The founder's two first real projects are a step patch repair and a wing (2026-11-18), and the repair is the next structure (2026-11-20). The first users are students at his school, who have Abaqus, Ansys and SolidWorks; his course material works the stepped lap by hand.
- The wing was built hand calculation first, with the finite element model as its check (ADR-0115). The repair's plan follows the same order: this record is its first slice; a repair from a few numbers, a finite element section, the page, the chat and the bond's progressive failure come after it.
- Every number of the product comes from the engine (ADR-0001), in SI inside (ADR-0002), and invalid input is refused (ADR-0003).
- The founder's course material and his own term project are private (ADR-0042). The method itself is public: Volkersen (1938), and Hart-Smith's NASA contractor reports CR-112235 (double laps) and CR-112237 (scarf and stepped laps), 1973.

## Options considered

1. **The stepped lap as a shear-lag model, solved exactly step by step (chosen).** It is what the course teaches and what a reviewer can follow: one equation per step, one linear system for the forces at the step boundaries. It leaves out peel and bending.
2. **An average shear stress, the load over the bonded area.** One line, and wrong where it matters: the shear stress peaks at the ends of the steps at several times the average, so it overstates the strength. Rejected.
3. **Goland and Reissner's single lap, with peel and the bending of the eccentric load path.** It answers a different joint. A flush repair on a supported panel bends little, and its steps are the point. Later, with the finite element section.
4. **The yielding adhesive in the stepped lap now, solved numerically (what Hart-Smith's own program does).** The right strength for a ductile adhesive, and no longer a hand calculation. It belongs with the bond's progressive failure, where the same law is needed. Rejected for this slice; the closed form of a long overlap is kept as the first statement of what yielding adds.
5. **Go straight to a finite element model with a cohesive bond.** It would have nothing to be checked against. Rejected: the hand calculation comes first, as for the wing.

## Decision

**The model.** `anisotropy_engine.repair` works a lap of any number of steps between an outer adherend (the patch) and an inner one (the parent laminate). The steps are listed from the patch's tip, where the patch carries nothing, to the end of the laminate at the cut or the hole, where the patch carries the whole load. In a step each adherend has one thickness and one modulus along the load. The adherends only stretch and the adhesive only shears. The equations are in `engine/docs/theory.md` Section 16.

**What it gives.** The patch's force at every step boundary (a tridiagonal system that makes the adhesive's shear stress continuous from step to step); the force and the shear stress anywhere in a step; the largest shear stress with its step and end; the largest stress of each adherend in each step; and the load at which the largest shear stress reaches the adhesive's shear strength, called the load at the elastic limit and never the failure load.

**A yielding adhesive.** `long_overlap_strength` is the closed-form strength of one bondline between two uniform adherends with an elastic-perfectly plastic adhesive, however long the overlap, and `double_lap_strength` the double lap's. It is not applied to a stepped lap.

**A file.** A lap is stated as a table in one of the engine's unit systems: the adhesive (shear modulus, thickness, and for a strength its shear strength and plastic strain), the steps (length, each adherend's thickness and modulus) and the load per unit width. A missing value, an unknown key or an unknown unit system is refused. `examples/step_lap_calculator.py` prints a file's answer.

**The cases.** The public cases are constructed from round values of our own, each with a closed form worked without the engine by another route. Course examples and the founder's own project stay outside the repository, in the same format under `.local/repair/cases/`, and the same test runs them where they are present.

**Not in this record.** Peel and bending; a yielding adhesive in a stepped lap and the bond's progressive failure; residual stress from cure and thermal mismatch; failure of an adherend between its plies; the modulus of a patch or a laminate worked from its layup; the repair as a kind of model in the workspace, its page and its chat.

## Why (evidence)

- The founder's words and card choice are quoted above.
- `cd engine && uv run pytest tests/test_step_lap.py -q`: 15 passed (2026-11-20), 16 with the private case present.
- Two public cases, `engine/validation/repair_cases/`: a flush repair of three steps and a lap of one step with a long double lap. Every expected number equals `closed_forms.py` within 10⁻⁹: there each step's general solution has two constants, found from one linear system of twice as many unknowns as steps, and the yielding double lap is worked zone by zone. The engine reproduces them within 10⁻⁹ in mm, MPa and N/mm and in in, psi and lb/in.
- Properties held whatever the numbers: one step is Volkersen's formula for unlike adherends; the shear stress integrates to the load and is the slope of the patch's force; a uniform step cut in five gives the same answer; matching adherends give the same stresses from both ends; the answer is linear in the load; a step two metres long neither overflows nor loads its middle, and its elastic limit equals the long overlap's closed form with no plastic strain.
- The yielding bond's equation marched inward by Runge-Kutta from the governing end holds at 0.999 of `long_overlap_strength` and fails at 1.001; a balanced double lap gives Hart-Smith's 4√(η τp (γe/2 + γp) E t).
- The course's worked examples and the founder's term project are reproduced by a private check (`.local/repair/cases/`, and the script kept with the project's files); their numbers are not quoted here (ADR-0042).
- Sources: O. Volkersen, Luftfahrtforschung 15 (1938); L. J. Hart-Smith, "Adhesive-bonded double-lap joints", NASA CR-112235 (1973), and "Adhesive-bonded scarf and stepped-lap joints", NASA CR-112237 (1973), both on the NASA Technical Reports Server.
- No evidence yet: no comparison with a test or with a finite element model of a repair. The published benchmark planned for the later slices is Damghani et al., Int. J. Adhesion and Adhesives 136 (2025) 103886 (open access).

## As built (2026-11-20)

- `engine/src/anisotropy_engine/repair/step_lap.py`: `Adhesive`, `Step`, `StepLap`, `step_constants`, `boundary_forces`, `step_lap`, `elastic_limit_load`, `long_overlap_strength`, `double_lap_strength`; `repair/lap_file.py`: `lap_from_dict`, `lap_report`.
- `engine/docs/theory.md` Section 16 with its code markers; `repair.step_lap` among the modules the manual prints.
- `engine/validation/repair_cases/` (two cases), `stepped_lap` and `ductile_double_lap` in `engine/validation/closed_forms.py`, `engine/tests/test_step_lap.py`, `engine/examples/step_lap_calculator.py`.

## Consequences

- A student's hand calculation of a stepped lap can be checked in one command, in SI or in inches and psi.
- The later slices have their reference: the finite element section of the bond must give these forces and shear stresses where its assumptions are the model's.
- The load at the elastic limit is far below a ductile adhesive's real strength in a stepped lap, and nothing here says how far; until the yielding lap is built, a reader must not take it for the repair's strength.
- A patch or a laminate enters as one modulus per step. Someone has to work that modulus from the layup until the repair is stated by its plies.

## How we will know it was wrong

- A finite element model of the same lap, with adherends that only stretch and an adhesive that only shears, differs from these boundary forces or shear stresses by more than its mesh error.
- On the published repair benchmark, the shear-lag model's ranking of designs (more steps, longer steps, softer adhesive) disagrees with the tests' ranking.
- Students or the professor report that the course's method gives different numbers for a joint this model is meant to cover.

## Amendment 1, 2026-11-20 (a lap may end at a plane of symmetry that both adherends cross; not yet confirmed by the founder)

**Context.** The lap of this record ends where the inner adherend ends, with the outer one carrying the whole load. A patch over a cavity that does not go through every ply is another lap: the laminate carries on under the patch, and the lap runs to the repair's middle, which the patch and the laminate both cross ([ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md)).

**Options.** (1) End the lap at the last ledge as before: the patch would be given the whole load, which it does not carry. (2) Add the plies left under the patch to the patch's side of the last step: the bond between them is the adhesive on the floor, which the model would then leave out. (3) A second end condition: no shear stress at a plane of symmetry, the outer adherend's force there one more unknown. Chosen.

**Decision.** `boundary_forces` and `step_lap` take `inner_continues`. With it the system has one more row, the shear stress at the end of the last step set to zero, and the last boundary force is part of the answer. Without it nothing changes. A lap file (`lap_file.py`) does not state it yet; a repair's description sets it.

**Evidence.** `engine/tests/test_patch_repair.py`: one step equals its closed form, N(L) = P (1 - 1 / cosh(lambda L)) and tau(0) = P lambda tanh(lambda L), within 10^-12; a step cut in three gives the same answer; a step half a metre long hands the patch its whole share. The cases of `engine/validation/patch_repair_cases/` work the same end by the general solution of every step in `closed_forms.py` and agree within 10^-9. The 16 tests of `engine/tests/test_step_lap.py` pass unchanged.
