# ADR-0009: Reuse TOML cases for calculator inputs

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Codex
- Related: ADR-0002, ADR-0003, ADR-0007; `engine/tests/test_calculator.py`

## Context

The editable calculator mixed personal inputs with a shared reference example. The local file selected psi with E1 = 140e9; the user identified the intended E1 as 140 GPa. Other personal values still require unit confirmation. The repository already has a TOML case reader used by tests and the generated manual.

## Options considered

1. Continue editing the calculator's source constants. Keeps the current interaction but changes the reference example with every problem.
2. Add a separate JSON format. Requires another input contract without evidence of a benefit.
3. Reuse the existing TOML case format for the calculator and personal cases.

## Decision

Option 3. Keep Problem 7.11 as the default case; accept an optional case path. Personal inputs remain under ignored `.local/`. Show input scales explicitly. Missing strengths or interaction coefficients are not filled in.

The calculator's existing 0.5-1000 GPa warning becomes a stop with an explicit override. The bound is an input-error heuristic inherited from the example, not an independently established material limit; it does not restrict the engine.

## Why (evidence)

`test_calculator.py` runs the default example, practice case, loading modes, explicit Tsai-Wu assumption and unit-review stop. Case tests reject incomplete load vectors and partial strengths. See the [evaluation](../evaluations/2026-10-03-input-validation.md).

## Consequences

Practice files can be run, inspected and later compared with independent answers without changing calculator code. Users must express all load components and assumptions explicitly. The file format remains a local practice interface, not the future material loader or API contract.

## How we will know it was wrong

Revisit when a supported problem needs inputs the case format cannot express. Do not silently discard those inputs.
