# ADR-0002: SI units inside the engine; convert only at inputs and outputs

- Status: Accepted
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/units.py`, `engine/examples/laminate_calculator.py`

## Context

Users work in SI (GPa, MPa, mm), US customary (Msi, ksi, in) and psi. Mixed units are a common cause of silent errors in engineering software.

## Options considered

1. **Unit-tagged quantities throughout**, for example with the pint library. Errors are caught automatically. Adds a dependency, slows the numerical code and complicates every function.
2. **SI everywhere inside the engine**, with conversion tables applied only where values enter and leave.

## Decision

Option 2. Engine functions take and return Pa, m, N, N/m and 1/m. `units.py` holds the SI, US and psi systems used by the examples, the validation runner and the future API.

## Why (evidence)

- Unit conversion is tested against the exact inch and pound-force definitions (`tests/test_units.py`).
- On 2026-10-02, two unit-entry mistakes happened while checking homework: E1 entered as 2.13 instead of 21.3 Msi, and E1 = 140e9 entered with psi units. The second was caught by the calculator's plausibility warning. Both mistakes happened where values are typed in, not inside the engine.

## Consequences

- Every input must state its units, and the API will need a units field.
- Entry points should check plausibility, as the calculator does for moduli.
- The engine never guesses units.

## How we will know it was wrong

If unit errors keep getting past the entry checks, move to unit-tagged quantities at least for inputs.
