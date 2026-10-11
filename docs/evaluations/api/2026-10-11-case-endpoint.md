# Evaluation: API case endpoint and library materials | 2026-10-11

- Scope: `POST /v1/cases/solve` (ADR-0024), `GET /v1/materials`, `GET /v1/materials/{id}` and the library form of the material input on the two explicit endpoints (ADR-0020). No new physics; every number comes from the engine's case functions.
- Release tested: API 0.1.0 and engine 0.1.0 at commit `1402c46`.
- Environment: Windows, Python 3.12; dependencies pinned in `api/uv.lock`.

## Commands and captured output

From the repository root: `uv run --project api pytest api/tests -q`

```text
92 passed in 1.03s
```

CI on PR #34: api, calculator-browser, engine, manual, website all pass.

## What the tests establish

| Check | Result |
| --- | --- |
| Five validation cases posted as TOML text (thermal with fixed-and-variable failure; mixed conditions; several materials; plate buckling; all four criteria) | every returned value equals the case runner's to 1e-12; every expected value agrees |
| A JSON case with a library material | provenance returned with dataset id, record revision and page per value; criteria list excludes maximum strain when no limits exist |
| The committed example `api/examples/case-library-axial-check.json` | solves; comparison agrees |
| Engine validation errors (`unknown fields ['E9']`), an unsymmetric plate, malformed TOML | 422 with the engine's message |
| Request form | exactly one of `case` or `toml`; an empty case is refused with the missing fields named |
| Unbounded strength ratios | returned as null, never infinity |
| Analysis by `library_id` on the forward endpoint | same matrices as the same constants typed explicitly, plus `material_provenance` |

## Known limits

- The OpenAPI schema describes the request envelope, not the fields of the case object; clients use `engine/validation/README.md`.
- The endpoint solves the case twice internally (once for results, once for the comparison); fine for laminate sizes in use, and a place to optimise if cases grow.
- CORS allows local website origins only; there is no authentication, as before (ADR-0011).
