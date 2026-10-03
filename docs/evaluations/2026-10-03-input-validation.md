# Input validation review | 2026-10-03

Base: `e8bacf7` (manual and shared case runner included). Implements the existing input policy, ADR-0003; no new constitutive model or failure criterion.

## Chunk 1: numerical entry points

- Before the fix: the new input suite produced `27 failed, 4 passed, 12 warnings in 1.74s`. Failures included NaN stresses returning infinite ratios, non-finite deformations propagating, and unknown fields being ignored.
- Decision: reject unknown model fields; require three finite components for direct stress, strain and curvature inputs; require finite safety factors >= 1 and nonnegative strength ratios. Positive-infinite ratios remain allowed for zero stress.
- After the fix: `cd engine && uv run pytest` produced `182 passed in 0.82s`.
- The six numerical cases passed, including the new analytical 0-degree practice check. Original textbook and homework references are unchanged.
- Expected practice values come from compliance and maximum-stress equations, not a previous engine output: at 100 MPa, eps1 = 100/147000, eps2 = -0.27 eps1, R = 2280/100 = 22.8. Material properties cite Daniel and Ishai Table A.4.
- The Tsai-Wu explanation's sign is corrected. The evaluated equation is unchanged; extreme numerical conditioning remains UNVERIFIED.
- Physical coupon validation remains UNVERIFIED.

## Chunk 2: calculator and case inputs

- The calculator now takes a TOML case path and defaults to the existing Problem 7.11 file. No personal input values are committed or guessed.
- Shared case validation rejects unknown fields, partial strengths, empty layups and incorrectly sized/non-finite applied vectors. This prevents `zip` from silently dropping or defaulting load components.
- The calculator explicitly prints GPa/MPa/mm, Msi/ksi/inches or psi/inches. Its existing modulus plausibility screen requires an explicit override to continue. Missing `f12_star` skips Tsai-Wu instead of assuming -0.5.
- Final command: `cd engine && uv run pytest` produced `200 passed in 13.49s`.
- Running the 0-degree practice case through the calculator printed eps_x = 6.802721e-4, eps_y = -1.836735e-4, local stress = [100, 0, 0] MPa, curvature = [0, 0, 0], and maximum-stress R = 22.8.
- All five loading modes, an explicitly supplied Tsai-Wu assumption, and the unit-review stop have subprocess tests. Decision: [ADR-0009](../decisions/ADR-0009-calculator-inputs-in-case-files.md).
