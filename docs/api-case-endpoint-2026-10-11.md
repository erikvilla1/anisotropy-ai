# API case endpoint — 11 October 2026

The API now covers the whole engine with one call ([ADR-0024](decisions/ADR-0024-api-exposes-the-case-format.md)). `POST /v1/cases/solve` takes a problem in the engine's case format and returns every result the case determines.

## Request

Either the case as a JSON object or the text of a `.toml` case file:

```json
{"case": {"units": "SI", "material": {"library": "im7-8552"}, "laminate": {"layup": [0]}, "applied": {"stress": [100, 0, 0]}}}
```

```json
{"toml": "units = \"SI\"\n[material]\nlibrary = \"im7-8552\"\n[laminate]\nlayup = [0]\n[applied]\nstress = [100, 0, 0]\n"}
```

The format is the one in [engine/validation/README.md](../engine/validation/README.md) and the [cheat sheet](engine-cheat-sheet.md): units, one material or several, the laminate, exactly one applied form (loads, stress, strains, local stress or strain, forces with curvature, or mixed conditions), and the optional `delta_T`, `f12_star`, `[failure]`, `[plate]` with `[buckling]`, and `[expected]`. The engine validates every field and refuses anything unknown or half filled; the message comes back as a 422 response, word for word the same as the calculator prints.

## Response

- `results`: every key the case runner produces, in the case's units: Q, S, Q̄, S̄, A, B, D and their inverse blocks, strains, curvatures, loads, ply strains and stresses per face, engineering constants, thermal resultants, first-ply failure ratios, loads, ply and z per criterion, plate buckling factor, loads and mode. Numbers or nested lists; an unbounded ratio is null.
- `criteria`: which first-ply criteria ran, given the inputs (`max_stress`, `max_strain`, `tsai_hill`, `tsai_wu`).
- `materials`: library provenance for each material that named a library dataset, with the page of every value used.
- `comparison` and `problems`: when the case has `[expected]`, each expected value beside the engine's with `agrees`, and any keys the case cannot produce.

## Try it

```powershell
cd api
uv run uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000
```

Then http://127.0.0.1:8000/docs, **POST /v1/cases/solve**, paste `api/examples/case-library-axial-check.json`. Or send a case file as it is:

```powershell
$body = @{ toml = (Get-Content -Raw .local\questions\lam_inital_ply.toml) } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/cases/solve' -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 10
```

## Checks

`api/tests/test_cases_api.py`: five validation cases posted as TOML (temperature change with fixed and variable failure, mixed conditions, several materials, plate buckling, all four criteria) return the case runner's results to 1e-12 with every expected value agreeing; a library case returns provenance and the criteria list; the example file solves; engine validation errors, an unsymmetric plate and malformed TOML give 422; exactly one of `case` or `toml` is required. `uv run pytest` in `api/`: 92 passed (6 new).

## Not in this chunk

The website calculator still uses the explicit forward endpoint; a case-based calculator screen, and the product agent that would call this endpoint, are later work.
