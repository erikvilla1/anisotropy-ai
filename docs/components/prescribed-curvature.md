# Component card: prescribed-curvature analysis | version 0.1 | updated 2026-10-03

## Purpose and intended use

Calculate moments required for a specified laminate curvature under known in-plane force resultants. Zero curvature requests flatness. Local research and analytical verification; [walkthrough](../walkthroughs/chunk-3-constrained-analysis.md).

## Inputs / outputs

Engine: plies, three forces (N/m), three curvatures (1/m). Output: A/B/D, strain, applied moments (N*m/m), recovered forward deformation, signed residuals and componentwise allowed error. API: one material/source, explicit SI-base units and bottom-to-top stacking. No moment input, missing-value defaults or partial constraints.

## Dependencies and connections

Pydantic API contract -> FastAPI route -> `prescribed_curvature_response` -> NumPy A solve and moment evaluation -> existing `midplane_response` check -> typed JSON. The TOML case runner and terminal calculator call the same engine function. No new dependency. Website/chat integration remains future work.

## Evaluation

[Evidence](../evaluations/2026-10-03-prescribed-curvature.md): independent diagonal/beam solutions, reverse-stack signs, symmetric zero coupling, off-axis stress integration, nonzero curvature, invalid inputs and deliberate check failures. [Decision](../decisions/ADR-0013-prescribed-curvature-analysis.md).

## Limits

Flat, linear elastic CLT; no thermal/moisture effects. Prescribed curvature does not specify rigid-body displacement, supports or fixture design. Applied moments and fixture reactions have opposite signs. Numerical agreement with a solver that shares stiffness code is not experimental validation or a condition-number guarantee. Source citations are caller supplied. No live language-model invocation yet.

## Owner

Founder / engineering.
