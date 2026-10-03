# ADR-0003: Reject invalid input; never substitute defaults

- Status: Accepted
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/lamina.py`, `engine/src/anisotropy_engine/failure.py`, [physics foundations](../physics-foundations-2026-10-02.md)

## Context

A result that silently relies on a default value cannot be traced, and a reviewer cannot tell that an assumption was made.

## Options considered

1. **Convenient defaults**, for example a Tsai-Wu interaction term of -0.5 or a factor of safety of 1.5. Easier to call. The assumption disappears from the record.
2. **Explicit inputs.** Invalid values raise an error, and every assumption must be passed by the caller.

## Decision

Option 2. Input models reject non-finite, non-positive and physically impossible values, such as nu12^2 >= E1/E2. The Tsai-Wu interaction term `f12_star` has no default. A factor of safety below 1 is rejected.

## Why (evidence)

- Invalid-input tests in `test_lamina.py`, `test_laminate.py`, `test_response.py` and `test_failure.py`.
- The [2026-10-03 input review](../evaluations/2026-10-03-input-validation.md) and `test_input_validation.py` cover non-finite vectors, unknown fields and invalid safety factors. Unknown fields are errors, not omitted loads. Positive-infinite strength ratios remain valid for zero stress.
- The physics library already states that the Tsai-Wu interaction coefficient must be measured or explicitly assumed.

## Consequences

- Callers, including the future API and interface, must collect every assumption from the user, so reports can list them.
- Calling the engine directly takes a few more arguments.

## How we will know it was wrong

If users regularly cannot supply a required value, offer opt-in recommended values that show their source, rather than hidden defaults.
