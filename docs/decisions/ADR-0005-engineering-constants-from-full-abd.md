# ADR-0005: Laminate engineering constants from the full ABD inverse

- Status: Accepted
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: pull request #2, `engine/src/anisotropy_engine/engineering.py`

## Context

Effective moduli such as Ex are what a D3039 tension test measures. For unsymmetric laminates the two common definitions differ a lot: for AS4/3501-6 [0/90], inverting A alone gives Ex = 79.0 GPa, while inverting the full ABD matrix gives 34.2 GPa.

## Options considered

1. **Invert A alone.** Assumes curvature is prevented.
2. **Use the in-plane block of the inverted 6x6 ABD matrix.** The laminate is free to bend as it stretches, with no applied moment (Daniel and Ishai, Section 7.12.3).

## Decision

Option 2. For symmetric laminates both options give identical results.

## Why (evidence)

- It matches the textbook's definitions, and the printed Table 7.3 values for a [+45/-45]s laminate.
- It agrees with a simulated free tension test through the load-response solver, including for unsymmetric and unbalanced layups (`test_engineering.py`).

## Consequences

A gripped coupon is held flat at its ends, so the measured modulus of an unsymmetric coupon can be higher than predicted. Test layups are normally symmetric, where this does not arise.

## How we will know it was wrong

If measured moduli of unsymmetric coupons are consistently above prediction, add a curvature-restrained option.
