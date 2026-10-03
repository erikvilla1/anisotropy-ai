# Prescribed-curvature verification | 2026-10-03

Base: `b716e54`; branch: `feat/constrained-laminate-chunk-3`. This adds a boundary-condition solve using the existing CLT stiffness equations, not a new constitutive model.

## Recorded checks

| Command | Observed output |
| --- | --- |
| `uv run pytest -q tests/test_prescribed_curvature.py` (engine, before implementation) | Collection error: the new function did not exist |
| Same command after implementation | 22 passed in 0.47s |
| Focused engine, validation-case and calculator checks | 56 passed in 15.01s |
| New API contract checks | 38 passed in 1.07s |
| `cd engine; uv run pytest` | 228 passed in 25.29s |
| `cd api; uv run pytest -q tests ../engine/tests` | 305 passed in 25.65s |
| `npm run test:calculator` against the restarted real API | 6 passed in 7.3s |

The new endpoint also completed a live local HTTP request using the founder's private practice inputs. Its accepted inputs and checked output remain under ignored `.local/practice/`; no problem statement or solution is published with this change. The local OpenAPI document exposes both the existing forward endpoint and the new prescribed-curvature endpoint.

## Independent checks and failure behavior

- Constructed 0/90 cross-ply with zero Poisson ratio: diagonal scalar stiffness relations give strain and nonzero flattening moments independently of the implementation.
- Constructed single 0-degree ply: nonzero bending/twist moments follow the scalar beam stiffness Q h^3/12. Both cases are included in the automatic validation runner.
- Reversing an unsymmetric stack reverses flattening moments; a symmetric stack needs no flattening moments. An off-axis unequal-thickness stack reproduces force and moment resultants by separate integration of ply face stresses.
- US force/curvature case conversion, explicit zero inputs, missing components, malformed dimensions, NaN/infinity, invalid materials, extreme thicknesses, and supplied/overconstraining moments are checked.
- Deliberately corrupted forward solutions (wrong strain, wrong curvature, non-finite output) stop the engine; a failed verification returns HTTP 422 at the API boundary.

## Meaning and limits

The production check uses relative tolerance 1e-9, absolute strain tolerance 1e-12 and absolute curvature tolerance 1e-9 per metre. These are explicit numerical policy, not measured physical accuracy. Forward/inverse paths share ABD code; their agreement alone is not independent validation. Analytical and stress-integration checks cover additional failure modes.

No live language-model selection, experimental coupon comparison, displacement/support boundary-value solution, general mixed constraints, or public deployment has been verified in this chunk. Those remain UNVERIFIED. The original forward contract and website calculator behavior are retained. CI checks, including manual generation, are recorded on the pull request.

Decision: [ADR-0013](../decisions/ADR-0013-prescribed-curvature-analysis.md). Explanation: [chunk 3 walkthrough](../walkthroughs/chunk-3-constrained-analysis.md).
