# ADR-0020: The engine loads materials from the website's cited library through one exported JSON file

- Status: Proposed
- Date: 2026-10-10
- Decided by: Erik Villa (founder) | Drafted by: Claude Code
- Related: `scripts/export-material-library.ts`, `engine/src/anisotropy_engine/library.py`, `engine/src/anisotropy_engine/data/material-library.json`, `api/src/anisotropy_api/schemas.py`, `lib/material-library-options.ts`, `docs/material-loader-2026-10-10.md`, [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0018](ADR-0018-source-rights-classes.md)

## Context

The website library holds 25 materials with every value cited to a page, in TypeScript. The engine, the API and the calculator take raw numbers typed by hand, converted by hand, with no link back to a source. Risk R-04 (a mistyped or mis-converted value) stays open, and no result can say which dataset it used.

## Options considered

1. **Export the library to JSON that the engine bundles and reads.** One source of truth (the TypeScript records); the engine stays free of web code; a test fails when the committed JSON drifts from the library. Cost: a generated file in the repository and a regeneration step after library changes.
2. **Duplicate the records in Python.** No build step, but two copies that drift, and the citation work would have to be redone.
3. **Have the engine call the website at run time.** No file, but the engine would depend on a server and could not run offline or in tests.

For the strength set the engine needs (F1t, F1c, F2t, F2c, F6):

1. Take whatever shear strength the record has, including the 0.2% offset value.
2. Take F12 (V-notched beam or textbook) or F12-5pct (D3518 at 5% strain), never the 0.2% offset; take F1c, or the cross-ply back-out F1c-derived when no direct value exists; attach strengths only when all five resolve, otherwise none, with the reason recorded.

## Decision

Option 1 for the data path and option 2 for the key policy. `scripts/export-material-library.ts` writes every dataset of every material, values as recorded with printed units and pages, to `engine/src/anisotropy_engine/data/material-library.json`. `library.py` converts to SI in one place, builds the `Lamina`, and returns a `CitedValue` for every value it used. A dataset without an elastic input set is refused with the record's own explanation. Case files, the API (`material: {library_id, dataset_id}`, `GET /v1/materials`) and the calculator picker all go through this loader, and every result carries the dataset id, record revision and citation.

## Why (evidence)

- `tests/material-library-export.test.ts` fails when the committed JSON differs from the current library export.
- `engine/tests/test_library.py` checks the unit conversions against the exact inch and pound-force (23.51 Msi → 162.0957 GPa), the key policy (F1c-derived for the NCAMP tape, F12-5pct for F6, the offset value never used), the refusals, and a validation case that takes its material and ply thickness from the library.
- `api/tests/test_library_api.py` shows a request by library id gives the same matrices as the same constants typed explicitly, plus provenance.

## Consequences

Easier: an analysis names its dataset and every value's page; a material revision in the library is one regeneration away from the engine; the calculator cannot mistype a library value. Harder: a library change must be followed by `npm run export:library`, or the website test fails; the JSON file is about 300 KB in the repository. The engine now depends on the export format (schema version 1).

## How we will know it was wrong

If the export has to carry website-only fields the engine never reads, or if a second consumer (run records, the product agent) needs a different shape, revisit whether the library records should live in a shared package instead of TypeScript.
