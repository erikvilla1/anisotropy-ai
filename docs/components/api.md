# Component card: local laminate API | version 0.1 | updated 2026-10-03

## Purpose and intended use

Expose the existing engine's stiffness and deformation calculations to local HTTP clients. This is the first integration chunk; see the [step-by-step walkthrough](../../api/README.md).

## Inputs / outputs

`POST /v1/laminates/response`: explicit `SI_BASE` units, one elastic material and source-reference text, bottom-first ply stack and all six load resultants. Returns A/B/D, mid-plane engineering strains, curvatures, accepted inputs and engine package version. Unknown fields and invalid/non-finite values fail with 422.

## Dependencies and connections

Uvicorn -> FastAPI -> Pydantic contract -> existing `anisotropy_engine` -> NumPy. Separate `api/pyproject.toml` and `api/uv.lock`; no HTTP dependency added to the engine. pytest and HTTPX2 exercise the app in process.

The website's `/calculator` now calls this endpoint. CORS allows credential-free JSON POST requests from localhost/127.0.0.1 on ports 3000/3001. See [the calculator card](calculator.md).

## Evaluation

[API integration evidence](../evaluations/api/2026-10-03-api-chunk-1.md) and [browser/CORS checks](../evaluations/website/2026-10-03-calculator-chunk-2.md); numerical equations remain covered by the existing engine tests.

## Out of scope and limits

Local development only. No authentication, curated material loader, persistent records or language model. One material per laminate. No hole geometry, ply stress/failure endpoint, thermal/moisture effects or design approval. A caller's citation is not verified evidence; units are declared, not inferred. Extreme finite inputs can still be poorly conditioned; a finite result alone is not a numerical accuracy guarantee.

## Owner

Founder / engineering.
