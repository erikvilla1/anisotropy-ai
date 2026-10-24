# ADR-0016: One general solver for mixed load and deformation conditions

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder, 2026-10-10 | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/mixed.py`, `engine/tests/test_mixed.py`, local evaluation note `.local/notes/evaluations/2026-10-03-validation-mixed-conditions.md` (ADR-0042), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0013](ADR-0013-prescribed-curvature-analysis.md)

## Context

ADR-0013 added one dedicated operation, known forces with prescribed curvature, and said to revisit it "when a supported problem requires a different mix of prescribed loads and deformations". Three course problems now do:
- the shear stress that keeps a lamina rectangular;
- a lamina compressed between frictionless rigid walls, and then without walls;
- a cured laminate held flat in y and in twist but free to bend in x.

Each combines known loads and known deformations differently.

## Options considered

1. One dedicated operation per combination, like ADR-0013. Each is simple, but there are 64 combinations of six pairs.
2. A six-component vector where unknowns are marked, for example with null or NaN. Compact, but a marker is easy to confuse with a known zero, which ADR-0003 forbids.
3. Named quantities: for each pair (Nx or eps_x, ... Mxy or kappa_xy), exactly one is given by name. A force may be given as an average stress sigma = N/h. One partitioned solve covers every combination.

## Decision

Option 3. `mixed_response(plies, known, delta_T)` requires exactly one name from each pair and rejects unknown names and non-finite values. It splits the ABD rows into known-load and known-deformation rows, solves for the unknown deformations, computes the unknown loads, and adds thermal resultants when `delta_T` is given. Every result must pass the same forward check as ADR-0013, now shared as `forward_verification`.

Cases give `[applied.mixed]` with the six named values. All cases now also report the named scalars (Nx ... Mxy, sigma_x, sigma_y, tau_xy, eps_x ... kappa_xy), so an answer key's single value, such as one curvature, can be compared directly. The existing `forces_curvature` operation and its API endpoint are unchanged.

## Why (evidence)

- The engine solves all four course mixed problems and agrees with their keys:
  - each within its case's tolerance; one key value came from rounded inputs, which its case explains. The cases are local since ADR-0042 and the numbers are in a local note (ADR-0042).
  - In the repository, `constructed-mixed-angle-lamina` checks the mixed solver against a closed form.
- `test_mixed.py` checks agreement with the forward solve (all loads known), with K d (all deformations known) and with the prescribed-curvature solver. It checks two closed-form compliance solutions, thermal consistency in every row, and each rejection.
- The forward check is shared and still fails deliberately corrupted solves.

## Consequences

Any combination of known loads and deformations can be solved and documented. The course Excel template cannot express mixed conditions, so these problems are written as TOML cases. First-ply failure ratios still scale all loads together, including solved ones, and do not hold prescribed deformations fixed. The API does not expose mixed conditions yet.

## How we will know it was wrong

Revisit if a problem needs a relation between quantities, for example Ny = 0.5 Nx while Nx is unknown, or a prescribed displacement rather than a strain or curvature.
