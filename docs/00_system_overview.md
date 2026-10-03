# System overview | version 0.1 | last reviewed 2026-10-03 | owner: Founder

## Purpose

Anisotropy AI helps engineers analyze composite laminates and test coupons, with results they can trace to equations, material sources and tests. The proposed first release is screening of unnotched laminates for one reviewed material family.

## Key principle

Tested, deterministic code computes every number. A language model, once added, may help draft inputs and explain results, but never produces a number in a result ([ADR-0001](decisions/ADR-0001-deterministic-engine.md)).

## Layers

| Layer | What it does | Status | Where |
| --- | --- | --- | --- |
| Website | Product pages, materials library, physics references, chat preview, CSV preview | Built; static export. The chat uses a local intent parser, not a language model | `app/`, `components/`, `lib/` |
| Material data | Cited property datasets with provenance; a monitor that detects source changes | Built | `lib/curated-materials.ts`, `services/material-monitor/` |
| Engine | Laminate analysis: ply stiffness, rotation, A-B-D, load response, first-ply failure, engineering constants | Built, version 0.1 | `engine/` |
| Validation cases | Textbook and answer-key problems the engine must reproduce | Built, 5 cases | `engine/validation/` |
| API | One-material laminate stiffness and deformation over HTTP | Local development; FastAPI, explicit SI-base inputs | `api/`, [component card](components/api.md) |
| Run records | Inputs, versions and results stored for every run | Planned (PostgreSQL) | |
| Material loader | Engine reads material values from the cited library instead of typed numbers | Planned | |
| Language model assistant | Drafts inputs from plain language; explains results | Planned | |
| Report generator | Documented report built from a run record | Planned | |
| Finite element analysis | Open-hole and other geometries | Later | |

## How a result is produced today

A problem (material, layup, and loads, stresses or strains) goes into the engine, which works in SI units and returns the results. Today the engine is used from Python, from `engine/examples/laminate_calculator.py`, and by the validation runner. The local API also accepts explicit load resultants for one-material laminates and returns stiffness and deformation. The website does not call it yet. See [the API walkthrough](../api/README.md).

## External dependencies

| Dependency | Used for | Version record |
| --- | --- | --- |
| Python 3.12+, uv | Engine runtime and packaging | `engine/uv.lock` |
| numpy, pydantic, pytest | Engine math, input checking, tests | `engine/uv.lock` |
| FastAPI, Uvicorn, Pydantic, NumPy, pytest, HTTPX2 | Local API, serving, validation and integration tests | `api/uv.lock` |
| Node.js 24, Next.js 16, React 19 | Website | `package-lock.json` |
| GitHub | Code, pull requests, automated tests | |
| Language model provider | None yet | |

Accounts: the repository is owned by erikvilla1, with cvv-mx-256 as collaborator. [Founder to complete: hosting, domain and other accounts, and who holds each credential.]

## Known limitations

- The engine analyzes flat laminates under in-plane loads and moments with classical laminate theory. It does not model holes, through-thickness stresses or finite element geometry.
- Failure checks give first-ply failure only: the onset of ply cracking, not the laminate's ultimate strength.
- Temperature and moisture effects are not modeled yet. Without curing residual stresses, first-ply failure predictions can be unconservative.
- Material values are typed in; the engine does not yet read the website's material library.
- The engine is checked against textbook and course problems, not yet against our own coupon tests. It is not approved for design decisions.
- The website's chat captures inputs but does not calculate results.
