# ADR-0059: The engine describes the stack and evaluates first-ply failure on the response endpoint, so the home page calculator shows them without computing

- Status: Proposed
- Date: 2026-11-05
- Decided by: Founder, 2026-10-31 (the website audit: the home page calculator "will still calculate the ABD matrices, first-ply failure (only when loading conditions are provided), and other useful features like total thickness, volume fraction, total weight, laminate type (i.e., anisotropic), etc."); the plan that puts every one of those numbers in the engine approved 2026-11-05 | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0012](ADR-0012-browser-calculator.md), [ADR-0013](ADR-0013-prescribed-curvature-analysis.md), [ADR-0020](ADR-0020-material-library-as-engine-input.md), [ADR-0021](ADR-0021-maximum-strain-and-tsai-hill.md), [ADR-0024](ADR-0024-api-exposes-the-case-format.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), `engine/src/anisotropy_engine/summary.py`, `engine/src/anisotropy_engine/library.py`, `engine/src/anisotropy_engine/cases.py`, `engine/validation/cases/library-as4-3501-stack-summary.toml`, `engine/tests/test_summary.py`, `api/src/anisotropy_api/schemas.py`, `api/src/anisotropy_api/main.py`, `api/tests/test_laminate_summary.py`

## Context

The website audit of 2026-10-31 moves the laminate calculator onto the home page as a live view of the user's stack, and asks it to show, beside the A, B and D matrices, the total thickness, the fiber volume fraction, the total weight, the laminate type and first-ply failure when loads are given. The browser computes nothing (ADR-0001), and the response endpoint `POST /v1/laminates/response` returned only A, B, D, the mid-plane strains and the curvatures. The engine already evaluates first-ply failure for the case format (ADR-0017, ADR-0021) but had no function that describes a stack, and the material loader cited no density (`library.py` took E1, E2, G12, nu12, the strengths, the expansion coefficients and the ply thickness). The library records a density for 23 of its 29 datasets and a fiber volume fraction for most, as one value or as a range.

## Options considered

1. Classify the stack and sum the thicknesses in the browser, and ask the engine only for failure. Rejected: ADR-0001 puts every number in a result in the engine; a sum of thicknesses or a symmetry test in TypeScript is a second implementation that can drift from the one the documents use.
2. A new endpoint `POST /v1/laminates/summary` beside the response endpoint. Rejected: the home page would send two requests and write two run records (ADR-0026) for every edit of the stack.
3. Send the home page's inputs through `POST /v1/cases/solve` (ADR-0024). Rejected: the page sends explicit plies and loads in SI base units, the contract the calculator page already uses; the case format needs units and tables the page does not have, and the response endpoint's fields would then exist twice.
4. Extend the response endpoint: the engine gains `summary.py`, with the thickness, the symmetry, antisymmetry and balance of the stacking, the kind of laminate judged on A, the couplings the matrices show, the areal mass from each ply's recorded density, and first-ply failure under the request's loads by every criterion the inputs support; the endpoint adds `summary` and `first_ply_failure`, both defaulted so every older client keeps working. Chosen.

For the density: on `Lamina`, next to the strengths. Rejected: `Lamina` is the elastic model that every kernel and every case builds; a field unused by all of them widens their inputs for one number. On `LibraryMaterial`, as a cited value with its page. Chosen: the areal mass exists only where a record states a density, and a typed material states none.

For the tolerance that decides "zero": the relative tolerance of the forward verification, 1e-9 of the matrix's largest entry (ADR-0013), with B judged against max|A| h/2 because B of a symmetric stack is roundoff. For the criteria: maximum stress and Tsai-Hill whenever the plies have strengths; maximum strain and Tsai-Wu only when their inputs are given, named as not computed otherwise, never assumed (ADR-0021). For the run records: the home page sends the actor `calculator`, so no migration (ADR-0026).

## Decision

Option 4. `engine/src/anisotropy_engine/summary.py` holds `total_thickness`, `is_symmetric`, `is_antisymmetric`, `is_balanced`, `laminate_kind`, `coupling_flags`, `areal_mass`, `laminate_summary`, `face_of` and `first_ply_failure_summary`; `library.py` cites `density` and `Vf` when a record states one value for them, beside the values the analysis used (`extra_values`, so a deck header, which lists `values`, stays as it was) and lists them under `not_provided` otherwise; `cases.py` reports `total_thickness` and, when every ply's material is a library dataset with a density, `areal_mass`; the API's `AnalysisResponse` carries `summary` and `first_ply_failure`, and `MaterialProvenance` carries `density_kg_per_m3` and `fiber_volume_fraction`. The home page calculator (its own part of the plan) reads these fields and computes nothing.

## As built (2026-11-05)

Built as decided, in one pull request. `units.py` gained `POUND_MASS`, `FOOT` and the unit kind `areal_mass` (kg/m²; lb/in² with the pound-mass for the US and psi systems); the loader converts `kg/m³`, `g/cm³`, `lb/ft³` and `%`. A record whose density or fraction is a range (the AGATE E-765 dataset) lists it under `not_provided` instead of failing to load. The first build appended the two citations to `values`, and every committed Abaqus and CalculiX deck then differed from its spec, since `fea/src/anisotropy_fea/spec.py` prints `values` in the deck header; they moved to `extra_values`, which the API's provenance appends to its `values` list and the deck writer does not read. Section 10 of `engine/docs/theory.md` and the physics card "Laminate symmetry, balance & areal mass" document the definitions. The validation case `library-as4-3501-stack-summary.toml` states `B11 = 0` nowhere: B of a symmetric stack is roundoff and the comparison cannot judge it, as the validation README says.

## Why (evidence)

- `cd engine && uv run pytest`: 463 passed, with `tests/test_summary.py` (symmetry, antisymmetry and balance on ten stacks; the kind on ten; the coupling flags on six; roundoff of a symmetric stack read as no coupling; areal mass 1.6 kg/m² exactly for eight plies of 0.125 mm at 1600 kg/m³ and the named refusals; the failure summary equal to the direct `first_ply_failure` call per criterion) and the two loader tests (AS4/3501-6: 1600 kg/m³ and 0.63; IM7/8552 NCAMP: 1.58 g/cm³ to 1580 kg/m³ and 57.3 % to 0.573).
- `engine/validation/cases/library-as4-3501-stack-summary.toml`: h = 8 × 0.125 mm = 1.0 mm and ρh = 1.6 kg/m², reproduced at 1e-9, with A16 = A26 = 0 judged against the size of A.
- `cd api && uv run pytest tests/test_laminate_summary.py`: the typed example is described, its areal mass and failure left out with the reasons; the IM7/8552 stack under Nx = 25 kN/m gives maximum stress and Tsai-Hill equal to the engine's direct call and names maximum strain and Tsai-Wu as not computed; the response's older fields are unchanged.
- The evaluation note [2026-11-05-laminate-summary.md](../evaluations/2026-11-05-laminate-summary.md) holds the commands and their output.

## Consequences

Easier: the home page and the calculator page show what a stack is and where it first fails from one request, with every number the engine's; a material record's density and fiber volume fraction reach the API with their pages. Harder: every response carries two more objects, and a client that reads `not_provided` sees two more entries for records without a density or a fraction; the kind of laminate is a judgement to a tolerance, which the response states. We now depend on the library recording densities as single values; a range is left out.

## How we will know it was wrong

A stack the engine names symmetric, balanced or quasi-isotropic that a textbook example contradicts; an areal mass that disagrees with a weighed panel of a library material by more than the record's own rounding; or a second client that needs the description without the matrices, which would argue for option 2 after all.
