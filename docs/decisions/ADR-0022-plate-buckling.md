# ADR-0022: Plate buckling by the Navier closed form for specially orthotropic laminates and a Ritz sine series otherwise, simply supported edges only

- Status: Proposed
- Date: 2026-10-11
- Decided by: Erik Villa (founder) | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/buckling.py`, `engine/tests/test_buckling.py`, `engine/validation/cases/constructed-cross-ply-plate-buckling.toml`, `engine/docs/theory.md` §8, [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0004](ADR-0004-sign-and-stacking-conventions.md)

## Context

The engine solved the in-plane and bending response of a flat laminate but had no stability analysis. The founder's course and two textbooks on hand (Whitney 1987; the course formula sheet) treat buckling of simply supported rectangular plates, and course problems ask for the critical load of a given laminate and plate size.

## Options considered

1. **Navier closed form only** (Whitney Eq. 5.72): exact for specially orthotropic laminates (D16 = D26 = 0) under Nx and Ny. Cheap and exact, but angle-ply laminates have D16 and D26, and shear cannot be handled; using the formula anyway is nonconservative, as Whitney shows.
2. **Closed form where it is exact, Ritz double sine series otherwise** (Whitney Eq. 6.38, equivalent to Galerkin with the same series): handles D16, D26 and Nxy on simply supported edges; converges from above; needs a series length. Numpy only, no new dependency.
3. **General Ritz with beam functions for any edge condition** (Whitney Section 6.6): clamped and free edges too. More integrals, more validation, and no problem on hand that needs it yet.
4. **Finite elements**: the deferred research phase.

For an unsymmetric laminate (B ≠ 0): refuse, since the bending equation alone does not govern (Whitney Chapter 7 treats specific classes).

## Decision

Option 2. `plate_buckling` uses the Navier form when the laminate is specially orthotropic and the reference load has no shear, and the Ritz series otherwise, requiring the number of terms as an explicit input (ADR-0003: the engine does not pick a series length). Reference loads use the engine's tension-positive sign convention, so compression is negative, and the result is a load factor on the reference loads. Unsymmetric laminates are refused. The Ritz result is reported together with the orthotropic closed-form factor so the effect of coupling is visible.

## Why (evidence)

- `test_buckling.py` reproduces Whitney's four worked results for the orthotropic plate with D11/D22 = 10 and (D12 + 2D66)/D22 = 1: 13π²D22/a² (square, uniaxial), (2√10 + 2)π²D22/b² at a/b = 10^¼ (absolute minimum), 6.5π²D22/a² (equal biaxial), 26π²D22/a² (transverse tension at half the compression).
- The Ritz series with D16 = D26 = 0 reproduces the closed form to 10 significant figures; with coupling it lies below the orthotropic estimate, as it must since the orthotropic mode is in its trial space; it decreases monotonically with more terms; mirroring the layup leaves compression unchanged and reverses the shear direction.
- `constructed-cross-ply-plate-buckling.toml`: a hand-computed D matrix and critical load for a [0/90/90/0] square plate.
- No course answer key for buckling has been checked yet; the first one the founder supplies becomes a validation case. Until then the anisotropic branch rests on the self-consistency tests above and on Whitney's description of the method.

## Consequences

Easier: critical loads for simply supported laminated plates in both closed form and series form, with the coupling effect shown. Harder: the Ritz answer is an upper bound and the user must confirm convergence by increasing `terms`; other edge conditions need option 3. We depend on Whitney's formulation, cited by section and equation; the book is a licensed reference and is not copied.

## How we will know it was wrong

A course or textbook buckling answer for a simply supported plate that the series misses by more than its stated convergence, or a need for clamped or free edges in more than one problem.
