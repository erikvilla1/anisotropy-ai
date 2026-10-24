# ADR-0017: First-ply failure holds fixed loads and thermal stress constant and scales the rest

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder, 2026-10-10 | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/failure.py`, `engine/tests/test_failure_combined.py`, local evaluation note `.local/notes/evaluations/2026-10-03-validation-ply-failure-fixed-loads.md` (ADR-0042), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0014](ADR-0014-explicit-temperature-change.md) (amended)

## Context

ADR-0014 reported no failure ratio with a temperature change, because `first_ply_failure` scales every stress with the load and residual thermal stress does not scale. A course problem asks for the Nx at first-ply failure with Ny growing in proportion to Nx, while a moment and a cooling stay fixed. Daniel and Ishai Section 9.8 (Eqs. 9.25-9.28) define the safety factor with hygrothermal stresses as the factor on the mechanical stresses, with the hygrothermal stresses added unscaled.

## Options considered

1. Keep reporting nothing with a temperature change. Safe, but leaves a standard course and design question unanswered.
2. Search for the failure load numerically, for example by bisection. General, but slower and approximate, and it hides the closed form the textbook gives.
3. Split the loading into fixed and variable parts and solve for R in closed form: a linear limit for maximum stress, and the textbook's quadratic for Tsai-Wu.

## Decision

Option 3. `max_stress_ratio_combined`, `tsai_wu_ratio_combined` and `first_ply_failure_combined` find the smallest R >= 0 at which fixed + R * variable reaches the criterion on any ply face. R = 0 means the fixed stresses alone already reach it. With nothing fixed, they reproduce the mechanical-only functions, which are unchanged.

A case may give a `[failure]` table with `fixed` and `variable` resultants, and the case's `delta_T` is then held fixed too. Without the table, the case's mechanical loads are variable and only a temperature change is fixed, the textbook definition. The calculator states which applies. Results add the failure loads, the failing ply and the face location. This amends ADR-0014: with a temperature change, failure ratios are reported under this definition.

## Why (evidence)

- That course problem: the engine gives the key's Nx at failure, ply, face and mode; the case is local since ADR-0042 and the numbers are in a local note (ADR-0042). In the repository, `constructed-cross-ply-cooling-first-ply-failure` checks maximum stress and Tsai-Wu with a fixed load and a cooling against closed forms.
- `test_failure_combined.py` checks the following:
  - With nothing fixed, the combined functions equal the mechanical-only ones.
  - Each R lands exactly on the failure envelope.
  - A fixed stress beyond a limit gives R = 0.
  - An independent bisection on the full stress gives the same R.
  - At the failure loads, the governing face's stress has a Tsai-Wu index of 1.
- The Tsai-Wu quadratic matches Daniel and Ishai Eqs. 9.26-9.27, checked against the founder's local copy (printed p. 256).
- Validation of the Tsai-Wu combined ratio against a published worked example: no evidence yet (UNVERIFIED).

## Consequences

Course and design questions with residual stress or held loads can be answered and checked. Only the faces of each ply are checked, as before: for maximum stress the faces provably govern, while for Tsai-Wu this is common practice without a proof. Reversed loading (the textbook's second root) is not reported; give the variable loads with the opposite sign to check it. A ratio is still not an ultimate-strength prediction.

## How we will know it was wrong

Revisit if a problem needs failure where loads are related other than proportionally, an interior Tsai-Wu point lower than the faces, or progressive failure after the first ply.
