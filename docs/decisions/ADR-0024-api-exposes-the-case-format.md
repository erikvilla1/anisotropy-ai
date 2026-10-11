# ADR-0024: The API exposes the engine's case format as one endpoint instead of one contract per operation

- Status: Accepted
- Date: 2026-10-11
- Decided by: Erik Villa (founder) | Drafted by: Claude Code
- Related: `api/src/anisotropy_api/main.py`, `api/src/anisotropy_api/schemas.py`, `api/tests/test_cases_api.py`, `engine/src/anisotropy_engine/cases.py`, `docs/api-case-endpoint-2026-10-11.md`, [ADR-0009](ADR-0009-calculator-inputs-in-case-files.md), [ADR-0011](ADR-0011-local-laminate-api.md), [ADR-0015](ADR-0015-course-inputs-and-several-materials.md)

## Context

ADR-0011 gave the API explicit JSON contracts, one per operation, and two were built: the forward response and prescribed curvature. The engine since gained mixed conditions, a temperature change, several materials per laminate, four failure criteria with fixed and variable loads, library materials and plate buckling. None of them was reachable over HTTP. Meanwhile the case format (ADR-0009, ADR-0015) already describes every one of those inputs, is validated field by field by the engine, is used by the calculator and the course Excel reader, and is checked by 32 validation cases.

## Options considered

1. **One explicit contract per operation**, as ADR-0011 intended: five or six new request and response models mirroring the case format piece by piece. Clear OpenAPI schemas, but a second description of the same inputs to keep in step with the engine, and every future engine feature needs a new contract.
2. **One endpoint that takes a case**, as a JSON object or as TOML text, validated and solved by the engine's own case functions, returning the same results dictionary the validation runner compares against answer keys. One description of inputs; every present and future engine operation is covered the day the case format covers it; the error messages are the ones users already see in the calculator. The OpenAPI schema cannot describe the case object's fields, so the format documentation does.
3. **Both**: keep the two explicit endpoints and add the case endpoint.

## Decision

Option 3. `POST /v1/cases/solve` accepts `{"case": {...}}` or `{"toml": "..."}` and returns `results` (every key of `engine_results`, in the case's units), the failure `criteria` evaluated, library `materials` provenance, and the `comparison` with `problems` when the case has `[expected]`. Non-finite ratios are returned as null. The two explicit endpoints stay as they are for the website calculator and as examples of the contract style.

## Why (evidence)

- `test_cases_api.py` posts five validation cases that together use loads with a temperature change and fixed-and-variable failure, mixed conditions, several materials, plate buckling and all four criteria, and checks every returned value against `engine_results` to 1e-12 and every expected value as agreeing.
- The engine's validation messages come back unchanged as 422 responses (`unknown fields ['E9']`, `midplane-symmetric`).
- The case format and its validation are the parts of the engine with the most test coverage (`test_validation_cases.py`, `test_course_inputs.py`, `test_mixed.py`, `test_failure_combined.py`).

## Consequences

Easier: the whole engine is callable from any client today, and the founder's case files can be sent as they are. Harder: clients must read the case format documentation rather than the OpenAPI schema for the case object; a product agent calling this endpoint needs that documentation in its context. ADR-0011's one-contract-per-operation rule is relaxed to: explicit contracts where a client form needs them, the case endpoint for everything.

## How we will know it was wrong

If a client needs field-level OpenAPI schemas for the case object (for example, generated SDKs), or if the case format grows inputs that only make sense in files, an explicit contract for that operation should be added and this ADR amended.
