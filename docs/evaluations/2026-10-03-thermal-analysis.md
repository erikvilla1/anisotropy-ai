# Thermal analysis verification | 2026-10-03

Base: `b381ecf`; branch: `feat/thermal-analysis`. This adds a uniform temperature change to the CLT engine: expansion coefficients, thermal force and moment resultants, and residual ply stresses (ADR-0014).

## Recorded checks

| Command | Observed output |
| --- | --- |
| `cd engine; uv run pytest` (before the change) | 228 passed in 15.35s |
| `cd engine; uv run pytest -q tests/test_thermal.py` | 35 passed in 0.40s |
| `cd engine; uv run pytest -q tests/test_validation_cases.py` | 14 passed in 0.25s, including both Course Reader 5.9 cases |
| `cd engine; uv run pytest` | 270 passed in 21.03s |
| `cd api; uv run pytest -q tests ../engine/tests` | 347 passed in 21.25s |
| `uv run --project engine python docs/manual/build.py` | Manual written; TeX reported only underfull-line warnings |
| `git diff --check` | No whitespace errors |

## Answer-key comparison

Course Reader Problem 5.9: [0/90]s laminates of AS4/3501-6 and S-glass/epoxy, 0.127 mm plies, cooled by 150 degC. The engine reproduces 46 values printed in the answer key within 0.1%: ply stiffness Q, the A matrix, the S-glass thermal forces N_T, the AS4 mid-plane strain, and fiber-axis stresses in every ply (AS4 -36.35 and +36.35 MPa; S-glass -21.48 and +21.48 MPa).

Two printed values contradict the key's own other numbers, so they are not recorded:

- AS4 N_T is printed as -7.447 kN/m. The key's strain gives (A11 + A12) eps0 = -7.478 kN/m; the engine gives -7.4776 kN/m.
- The S-glass strain is printed as -1.37e-4. The key's N_T / (A11 + A12) and its stresses both require -1.37e-3, which the engine gives.

A separate hand-formula script that does not import the engine gave the same values (kept locally with the problem).

## Independent physical checks

- A single free ply expands by alpha * delta_T with no stress, at 0, 30 and 90 degrees.
- With alpha1 = alpha2, an unsymmetric five-ply layup expands uniformly with no stress or curvature.
- A balanced symmetric cross-ply matches the closed-form strain dT [(Q11+Q12) a1 + (Q12+Q22) a2] / (Q11 + 2 Q12 + Q22) and its ply stresses.
- An unsymmetric [0/90] laminate warps into a saddle; integrating its face stresses separately from the ABD solve gives zero net force and moment.
- Thermal and mechanical responses superpose, and delta_T = 0 reproduces the mechanical results.
- Prescribing the free thermal deformation needs zero mechanical load; solved flattening moments remove the warp when applied.
- SI and US inputs (degF, 1/degF) give the same strains. Missing or partial coefficients, a non-numeric or non-finite delta_T, and failure ratios with delta_T are rejected or not reported.

## Meaning and limits

These checks verify that the code solves the CLT thermal equations and reproduce one course answer key. They are not experimental validation. Strength ratios with residual stress, moisture, temperature-dependent properties and through-thickness temperature gradients are not modeled. The API and website calculator do not accept a temperature change yet.
