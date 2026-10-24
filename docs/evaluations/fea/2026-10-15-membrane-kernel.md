# Evaluation: finite element chunk 2, the laminate membrane kernel (ADR-0029) | 2026-10-15

- Scope: `fea/` gains the solver: four-node plane-stress elements on the engine's laminate `A` matrix, kinematic couplings as dof aliasing, prescribed displacements and concentrated loads, sparse LU solve with a singularity check, reactions, centroid and Gauss-point strains, section forces; a validation case format and runner; `fea/docs/theory.md` with a code marker per function. No ply stresses or failure yet (chunk 3).
- Environment: Windows 11, uv 0.13, `fea/uv.lock` unchanged (NumPy, SciPy 1.18.1, Pydantic 2, engine editable). A team coupon deck in `.local/`, git-ignored.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests`

```text
96 passed in 1.51s
```

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job)

```text
504 passed in 11.03s
```

From `fea/`: `uv run python examples/solve_deck.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa` (re-run on 2026-10-23 on the generic fixture, ADR-0042)

```text
29 nodes, 16 elements, units mm-MPa
reference Assembly.1 (Grip-Top): RF = [54.8781, 4574.14] N, U = [0, 0.8]
reference Assembly.2 (Grip-Bottom): RF = [-54.8781, -4574.14] N, U = [0, 0]
sum of reactions = [6.37e-12, -3.64e-12] N (equilibrium check); largest free-dof residual 1.18e-11 N
eps_x: min -0.0013281  max -0.000648631  mean -0.00110409
eps_y: min 0.00732887  max 0.00850152  mean 0.008
gamma_xy: min -0.00131043  max -0.000396906  mean -0.000737194
```

The unbalanced layup under rigid grips: the x reaction at the grips is the shear-extension coupling that the `A16` term produces (re-run on 2026-10-23 on the generic 25 by 100 mm [0/30/-30/30/0]s fixture, ADR-0042: 54.9 N against 4574.1 N axial); the mean axial strain equals the nominal 0.8 / 100.

The engine-equality smoke run that produced the case numbers (one element, prescribed axial strain, lateral edges free): kernel strain minus the engine's mixed-solver strain, largest absolute difference 2.6e-17; the section force was the same in both. The case numbers were recomputed on 2026-10-23 for the generic fixture (now Ny 179.4122942 N/mm at 0.8 %, ADR-0042).

The same command on a team coupon deck solved in equilibrium as well; its numbers stay in a local note (ADR-0042).

## What the tests cover (39 new)

- Element (12): shape functions one at their node and zero elsewhere, partition of unity, zero-sum derivatives, Jacobian and `B` on the unit square against hand values, exact recovery of a uniform strain field on a skewed element at every Gauss point, symmetric stiffness with exactly three zero eigenvalues and zero force for rigid translation and rotation, linear scaling with `A`, consistent nodal forces of a uniform traction, clockwise and bow-tie elements refused.
- Solves (11): one element equals the engine's mixed solver to 1e-12 (strain at centroid and Gauss points, section force, reaction, displacement field, equilibrium, residual); 2 by 2, 4 by 8 and 3 by 5 meshes carry the same uniform state; load control equals the engine's forward solve with the reaction balancing the load; isotropic uniaxial and simple-shear closed forms; a coupled edge equals the same edge prescribed node by node with the reference reaction equal to the summed edge reactions and zero reaction at coupled nodes; the gripped coupon in equilibrium with antisymmetric grip reactions and a non-uniform shear field; nested refinement 2 by 8, 4 by 16, 8 by 32 never stiffens and converges within 5 %; refusals for an unsymmetric layup, a free rigid-body motion, a node in no element, a prescription that conflicts through a coupling.
- Validation cases (10): the five cases reproduced; a wrong value reported as `strain[Coupon-1.1][1]: expected 0.02, kernel gives 0.008` (0.01 before the fixture became generic); a zero expected value scaled by its group; an unknown node reported, not skipped; an unknown group, a wrong vector length and a zero tolerance refused at load.
- Theory markers (3): every function the theory names has a marker and every marker a sentence (twelve pairs); every marked name resolves in the package; the sections the manual expects exist.
- Local deck (1 new): the team's coupon solves in equilibrium with the imposed displacement recovered; skipped where the deck is absent.
- Units (1 changed): the section-force kind.

## Not run

Website suites and the manual build: unaffected (the manual does not read `fea/` yet; that extension is its own chunk). UNVERIFIED for this chunk.

## Known difference from Abaqus, to be measured

S4R uses one in-plane integration point with hourglass control and carries a drilling rotation that the couplings fix along the grips; our element is fully integrated with no rotation. For uniform fields the two coincide; near the grips of an unbalanced laminate they differ at a level the first comparison note will measure (risk R-15). No Abaqus numbers exist yet.
