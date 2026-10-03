# ADR-0013: A dedicated prescribed-curvature tool solves for required moments

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Codex
- Related: [walkthrough](../walkthroughs/chunk-3-constrained-analysis.md), [evaluation](../evaluations/2026-10-03-prescribed-curvature.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0004](ADR-0004-sign-and-stacking-conventions.md)

## Context

The forward API requires all six force/moment components. It cannot represent known forces plus a zero-curvature constraint when moments are unknown. The approved chunk adds this engine/API capability before a real chat harness.

## Options considered

1. Treat unknown moments as zero. Solves a different boundary condition and can allow coupled bending.
2. A universal mixed-boundary-condition schema with nullable load/deformation components. More combinations and ambiguity to validate; deferred until a reviewed use case needs them.
3. A dedicated operation: all three forces and all three curvatures known; all three moments and strains calculated.
4. Put the equations in the API or future assistant. Duplicates the numerical engine and violates ADR-0001.

## Decision

Option 3. Add `prescribed_curvature_response` to the engine and `POST /v1/laminates/prescribed-curvature`. Require `SI_BASE`, explicit `bottom_to_top` stacking, one material/source, plies, three forces and three prescribed curvatures. Unknown moments are absent from the input contract; supplied moments fail validation. Existing forward requests are unchanged.

Solve A eps0 = N - B kappa, then M = B eps0 + D kappa. Feed N/M into the existing forward solve. Reject non-finite output or a failed componentwise deformation check. Report recovered values, signed residuals and allowed errors. Relative tolerance is 1e-9; absolute tolerance is 1e-12 for strain and 1e-9 per metre for curvature. These are implementation choices for numerical consistency, not physical accuracy guarantees.

Extend the existing TOML case format with one explicit six-component `forces_curvature` mode and a `moments` result. Keep course material and the user's original case local; committed examples use constructed analytical inputs.

## Why (evidence)

- [Existing theory](../../engine/docs/theory.md) and [NASA RP-1351, equations 48-51](https://ntrs.nasa.gov/api/citations/19950009349/downloads/19950009349.pdf#page=29) establish the block equations being rearranged. No new constitutive model is claimed.
- [Engine checks](../../engine/tests/test_prescribed_curvature.py) compare to independent scalar solutions, reverse the stack, integrate ply stresses, and deliberately corrupt the forward result to test rejection.
- [API checks](../../api/tests/test_curvature_api.py) exercise the actual engine, malformed/overconstrained requests, OpenAPI and the existing forward endpoint. [Case/CLI checks](../../engine/tests/test_calculator.py) include US-unit conversion.
- The evaluation records actual command output. Experimental accuracy, general mixed constraints, and live model tool selection: no evidence yet (UNVERIFIED).

## Consequences

No new dependencies. All result arithmetic and checks remain in the engine. The forward check shares stiffness code, so it is supplemented by analytical/equilibrium tests. Ill-conditioned inputs can fail the check or remain physically inappropriate. Required applied moments use the repository's sign convention; they are not opposite fixture reactions. This operation constrains curvature, not absolute displacement or support geometry. Chat integration remains the next chunk.

## How we will know it was wrong

Revisit the dedicated contract when a supported problem requires a different mix of prescribed loads and deformations. Revisit tolerances when a documented, independently verified case is incorrectly accepted or rejected.
