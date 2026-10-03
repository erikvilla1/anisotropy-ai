# Mixed load and deformation conditions | 2026-10-03

Base: `31b999c`; branch: `feat/mixed-conditions`. A general solver handles any mix of known loads and known deformations, with or without a temperature change (ADR-0016).

## Recorded checks

| Command | Observed output |
| --- | --- |
| `cd engine; uv run pytest` (before the change) | 325 passed |
| `cd engine; uv run pytest -q tests/test_mixed.py` | 18 passed in 1.30s |
| `cd engine; uv run pytest` | 344 passed in 26.40s |
| `cd api; uv run pytest -q tests ../engine/tests` | 421 passed in 25.84s |
| `uv run --project engine python docs/manual/build.py` | Manual written; TeX reported only underfull-line warnings |
| `git diff --check` | No whitespace errors |

## Course problems now solved by the engine

| Problem | Known | Solved | Engine | Answer key |
| --- | --- | --- | --- | --- |
| Homework 2, Problem 1 | sigma_x = 10, sigma_y = -20 MPa, gamma_xy = 0 | tau_xy | -4.1667 MPa | -4.16 MPa |
| Course Reader 3.8, walls | eps_x = -0.01, eps_y = 0, tau_xy = 0 | sigma_x | -281.94 MPa | -282 MPa |
| Course Reader 3.8, no walls | eps_x = -0.01, sigma_y = 0, tau_xy = 0 | sigma_x, eps_y, gamma_xy | -275.86 MPa, 0.0022167, 0.012969 | -276 MPa, 0.002217, 0.01297 |
| Course Reader 5.13 | N = 0, Mx = 0, kappa_y = kappa_xy = 0, delta_T = -150 degC | kappa_x | -13.0507 1/m | -13.035 1/m |

The 5.13 key uses rounded A, B, D, N_T and M_T. Its denominator subtracts two similar numbers, which moves its result about 0.12% from the engine's. The case tolerance, 0.2%, covers that rounding. Repeating the key's arithmetic with its own rounded values gives -13.035.

## Independent checks

- With all loads known the solver equals the forward solve; with all deformations known it equals K d; with forces and curvatures known it equals the prescribed-curvature operation.
- The rectangular lamina and rigid-wall results match closed forms built from S-bar, which is computed without the ABD solve.
- For the partially held cured laminate, every row of K d equals the mechanical plus thermal resultants, and the solved mechanical loads are zero where they were given as zero.
- Unknown names, two or no quantities for a pair, non-finite values and a corrupted forward solve are rejected.

## Meaning and limits

These checks verify the solver against course answer keys and constructed relations, not experiments. Relations between quantities, such as Ny = 0.5 Nx with Nx unknown, are not supported; they are needed for first-ply failure with some loads held fixed, the next chunk.
