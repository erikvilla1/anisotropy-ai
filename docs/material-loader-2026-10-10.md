# Material loader — 10 October 2026

The engine, the API and the calculator can now take a material from the cited library by name instead of by typed numbers ([ADR-0020](decisions/ADR-0020-material-library-as-engine-input.md)). Every result that uses a library material carries the dataset id, the record revision, the source citation and the page of every value.

## How data flows

1. **Export.** `npm run export:library` runs `scripts/export-material-library.ts`, which writes every dataset of every library material to `engine/src/anisotropy_engine/data/material-library.json`: values as recorded, printed units, pages, source and rights. A website test fails if the committed file differs from the library, so the two cannot drift.
2. **Load.** `anisotropy_engine.library.library_material("im7-8552")` finds the material's primary dataset (or a named one), converts each value to SI once with the exact inch and pound-force, and returns a `LibraryMaterial`: a `Lamina` for the engine, the ply thickness when the dataset records one, and a `CitedValue` for every value used (role, key, SI value, printed value and unit, basis, page, link).
3. **Cases.** A case can say `[material] library = "im7-8552"` (optional `dataset = "..."`) instead of typing E1, E2, G12 and ν12. `laminate.ply_thickness` may then be omitted when the dataset records a ply thickness. The calculator prints the dataset, citation and pages before the results. A library table cannot also carry typed values.
4. **API.** `GET /v1/materials` lists every dataset and whether it has an elastic input set. `GET /v1/materials/{id}?dataset=` returns the SI values with their pages. `POST /v1/laminates/response` and `/prescribed-curvature` accept `material: {"library_id": "im7-8552", "dataset_id": null}` in place of explicit constants; the response gains `material_provenance`.
5. **Calculator.** A "Library material" picker fills the material fields, the citation and the ply thickness from the chosen dataset and sends the library reference, so what the engine uses is the dataset, not the displayed rounding. Editing any material field switches back to manual entry. The result shows the material source block.

## What the loader refuses, and why

- A dataset without an elastic input set, with the record's own explanation. T650-35 / 976 from the handbook has no Poisson ratio; the 2025 NCAMP glass dataset has none either.
- Unknown material or dataset ids, naming what exists.
- A case table that mixes `library` with typed values, or a typed material without a ply thickness.
- Ranges and lower bounds as engine inputs.

## Key policy

| Engine quantity | Library key, in order of preference | Never used |
| --- | --- | --- |
| E1, E2, G12, ν12 | the dataset's own `elasticInputs` map | compressive moduli |
| F1t, F2t, F2c | F1t, F2t, F2c | |
| F1c | F1c, then F1c-derived (cross-ply back-out, basis kept) | |
| F6 | F12 (V-notched beam, textbook), then F12-5pct (D3518 at 5% strain) | F12-offset (0.2% offset) |
| α1, α2 | alpha1, alpha2 (10⁻⁶/K, 10⁻⁶/°C or 10⁻⁶/°F) | |
| ply thickness | tply, then tply-WT | |

Strengths are attached only when all five resolve; thermal expansion only when both coefficients exist. Otherwise `not_provided` says what is missing and the engine's own checks reject a failure or thermal analysis that needs them (ADR-0003).

## Checks

- Engine: `uv run pytest` in `engine/`: 380 passed (12 new). New tests cover the conversions, the key policy, the refusals, the case integration and a new validation case, `library-im7-8552-axial-check.toml`, whose expected strains are the analytical uniaxial relations with the library's E1 and ν12.
- API: `uv run pytest` in `api/`: 82 passed (5 new). A request by library id reproduces the matrices of the same constants typed explicitly.
- Website: `npm test` 71 passed (export drift guard, request building with a library selection), `npm run typecheck` exit 0, `npm run build` static export completed, calculator browser spec against the real API 7 passed (library pick, posted library reference, provenance block).

## Not in this chunk

The API still takes ply thickness explicitly; the calculator prefills it from the dataset. Several materials per laminate through the API, failure and thermal endpoints, and run records come next.
