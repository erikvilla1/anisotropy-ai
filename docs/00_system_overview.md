# System overview | version 0.1 | last reviewed 2026-10-03 | owner: Founder

## Purpose

Anisotropy AI helps engineers analyze composite laminates and test coupons, with results they can trace to equations, material sources and tests. The proposed first release is screening of unnotched laminates for one reviewed material family.

## Key principle

Tested, deterministic code computes every number. A language model, once added, may help draft inputs and explain results, but never produces a number in a result ([ADR-0001](decisions/ADR-0001-deterministic-engine.md)).

## Layers

| Layer | What it does | Status | Where |
| --- | --- | --- | --- |
| Website | Product pages, materials library, physics references, chat/CSV previews and laminate calculator | Static export; calculator calls local API. Chat still uses a local parser | `app/`, `components/`, `lib/`, [calculator card](components/calculator.md) |
| Material data | Cited property datasets with provenance; a monitor that detects source changes | Built | `lib/curated-materials.ts`, `services/material-monitor/` |
| Engine | Laminate stiffness and compliance, forward, prescribed-curvature and mixed-condition response, temperature change and residual stresses, first-ply failure, engineering constants; plies of several materials and thicknesses | Built, version 0.1 | `engine/`, [constrained analysis](components/prescribed-curvature.md) |
| Validation cases | Textbook/answer-key references and constructed analytical checks | Built, 28 cases | `engine/validation/` |
| API | One-material forward response and required moments for prescribed curvature | Local development; FastAPI, explicit SI-base inputs | `api/`, [component card](components/api.md) |
| Run records | Inputs, versions and results stored for every run | Planned (PostgreSQL) | |
| Material loader | Engine reads material values from the cited library instead of typed numbers | Planned | |
| Language model assistant | Drafts inputs from plain language; explains results | Planned | |
| Report generator | Documented report built from a run record | Planned | |
| Finite element analysis | Open-hole and other geometries | Later | |

## How a result is produced today

A problem (material, layup, and loads, stresses or strains) goes into the engine, which works in SI units and returns the results. Today the engine is used from Python, from `engine/examples/laminate_calculator.py` (which reads TOML cases or the course Excel input files and compares results with an answer key), and by the validation runner. The website's `/calculator` converts labelled GPa/mm inputs to SI base units, sends explicit load resultants to the local API and displays its stiffness/deformation response. See [the API walkthrough](../api/README.md) and [website walkthrough](walkthroughs/chunk-2-calculator.md). The chat preview remains separate.

The new prescribed-curvature API accepts known forces plus three prescribed curvatures and solves for the required moments. A full forward solve must recover the target deformation within reported numerical tolerances. It is the first constrained-analysis tool for the planned chat harness; see [chunk 3](walkthroughs/chunk-3-constrained-analysis.md).

## Where AI and machine learning fit

The planned layers each use the validation evidence differently. None of them is built yet.

- **Engine (built).** Its equations come from published laminate theory ([engine theory](../engine/docs/theory.md)). Validation cases, such as textbook examples and course answer keys, test that the code solves those equations. They are not training data, and they do not show that the theory predicts real parts; coupon tests will.
- **Language-model assistant (planned).** A general model with tool access, not a model trained on our cases. It drafts a case from a plain-language request, asks for missing inputs, calls the engine through the API and explains the result with the theory references. Its requests pass the same input checks as any other caller (ADR-0003), and it never produces a result number (ADR-0001). Validation cases double as its tests: given a problem statement, it must build the inputs that reproduce the answer.
- **Machine learning (later, once there is enough data).** Candidates are surrogate models trained on many engine runs, for faster layup search, and correction models trained on our coupon tests where theory and measurement disagree. Before use, their predictions are rechecked by the engine or against held-out tests.
- **Run records (planned).** Saved inputs, versions, results and test outcomes are the data any later model learns from. Customer data is not used for shared training by default.

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
- A uniform temperature change gives thermal resultants and residual ply stresses (ADR-0014), but first-ply failure does not include them yet, so its predictions can be unconservative. Moisture and temperature-dependent properties are not modeled.
- Material values are typed in; the engine does not yet read the website's material library.
- The engine is checked against textbook and course problems, not yet against our own coupon tests. It is not approved for design decisions.
- The website's chat captures inputs but does not calculate results.
