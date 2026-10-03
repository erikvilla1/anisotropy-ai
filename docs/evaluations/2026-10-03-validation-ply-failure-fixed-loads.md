# First-ply failure with fixed and variable loads | 2026-10-03

Base: `9cde322`; branch: `feat/failure-fixed-loads`. First-ply failure now holds residual thermal stress and any fixed loads constant while the remaining loads scale, in closed form (ADR-0017, Daniel and Ishai Section 9.8).

## Recorded checks

| Command | Observed output |
| --- | --- |
| `cd engine; uv run pytest` (before the change) | 344 passed |
| `cd engine; uv run pytest -q tests/test_failure_combined.py` | 24 passed in 1.25s |
| `cd engine; uv run pytest` | 368 passed in 27.33s |
| `cd api; uv run pytest -q tests ../engine/tests` | 445 passed in 26.84s |
| `uv run --project engine python docs/manual/build.py` | Manual written; TeX reported only underfull-line warnings |
| `git diff --check` | No whitespace errors |

Two earlier tests asserted that no failure ratio is reported with a temperature change (ADR-0014). They now check the new behavior: the ratio equals the combined function's, and it is lower than the mechanical-only ratio for a cooled cross-ply.

## Course answer key

Homework 5 Problem 1 part D, a [45/-45/90/0_2]s laminate: Nx grows with Ny = 0.5 Nx while Mx = -4 lb*in/in and a cooling of 275 degF stay fixed; maximum-stress criterion.

| Result | Engine | Answer key |
| --- | --- | --- |
| Nx at failure | 568.256 lb/in | 568.25 lb/in |
| Ny at failure | 284.128 lb/in | 284.13 lb/in |
| Failing ply and face | ply 3, bottom, z = -0.015 in | ply 3, bottom, z = -0.015 in |
| Mode | transverse tension | matrix, tension |

The engine solves this in closed form. A bisection on the full stress, used in the course audit before this change, gave 568.2556.

## Independent checks

- With nothing fixed, the combined ratios and laminate failure equal the existing mechanical-only functions.
- Each ratio lands exactly on its criterion: one maximum-stress limit reached, or a Tsai-Wu index of 1.
- A fixed stress beyond a limit gives R = 0; variable stress that never grows gives infinity.
- An independent bisection on a cooled, bent laminate gives the same R to 1e-9.
- At the failure loads, a full thermomechanical solve gives the governing face's stress, and its Tsai-Wu index is 1.

## Meaning and limits

These are first-ply failure predictions, the onset of ply cracking, not ultimate strength. Only ply faces are checked; for Tsai-Wu that is common practice, not proven. The Tsai-Wu combined ratio has no published worked example in the validation set yet.
