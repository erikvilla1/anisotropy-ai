# System overview | version 0.1 | last reviewed 2026-10-11 | owner: Founder

## Purpose

Anisotropy AI helps engineers analyze composite laminates and test coupons, with results they can trace to equations, material sources and tests. The proposed first release is screening of unnotched laminates for one reviewed material family.

## Key principle

Tested, deterministic code computes every number. A language model, once added, may help draft inputs and explain results, but never produces a number in a result ([ADR-0001](decisions/ADR-0001-deterministic-engine.md)).

## Layers

| Layer | What it does | Status | Where |
| --- | --- | --- | --- |
| Website | Product pages, materials library, physics references, chat/CSV previews and laminate calculator | Static export; calculator calls local API. Chat still uses a local parser | `app/`, `components/`, `lib/`, [calculator card](components/calculator.md) |
| Material data | 25 cited property datasets with provenance and a rights class per source (NCAMP, NASA, AGATE, MIL-HDBK-17F, datasheets, textbook values); a monitor that detects source changes; a physics page with a card for every engine equation | Built | `lib/curated-materials.ts`, `lib/source-rights.ts`, `lib/physics*.ts`, `services/material-monitor/` |
| Engine | Laminate stiffness and compliance; forward, prescribed-curvature and mixed-condition response; temperature change and residual stresses; first-ply failure by maximum stress, maximum strain, Tsai-Hill and Tsai-Wu with fixed and variable loads; engineering constants; plate buckling of simply supported symmetric laminates; plies of several materials and thicknesses | Built, version 0.1 | `engine/`, [engine card](components/engine.md), [constrained analysis](components/prescribed-curvature.md) |
| Validation cases | Textbook/answer-key references and constructed analytical checks | Built, 32 cases | `engine/validation/` |
| API | Forward response and prescribed curvature with explicit contracts; the whole case format through `POST /v1/cases/solve`; library materials by id | Local development; FastAPI | `api/`, [component card](components/api.md) |
| Material loader | Engine, API and calculator read material values from the cited library by dataset id, with the page of every value used | Built (ADR-0020) | `engine/src/anisotropy_engine/library.py`, [note](material-loader-2026-10-10.md) |
| Run records | Inputs, versions and results stored for every run | Local PostgreSQL 17 from `docker-compose.yml` (ADR-0025); the immutable `runs` table exists and the API refuses to start without the database (ADR-0026); the write on every solve is next | `docker-compose.yml`, `api/alembic/`, `api/src/anisotropy_api/records.py`, [evaluation](evaluations/api/2026-10-14-run-records-table.md) |
| Language model assistant | Drafts inputs from plain language; explains results | Planned | |
| Report generator | Documented report built from a run record | Planned | |
| Finite element analysis | Open-hole and other geometries | Later | |

## How a result is produced today

A problem (material, layup, and loads, stresses or strains) goes into the engine, which works in SI units and returns the results. Today the engine is used from Python, from `engine/examples/laminate_calculator.py` (which reads TOML cases or the course Excel input files and compares results with an answer key), and by the validation runner. The website's `/calculator` converts labelled GPa/mm inputs to SI base units, sends explicit load resultants to the local API and displays its stiffness/deformation response. See [the API walkthrough](../api/README.md) and [website walkthrough](walkthroughs/chunk-2-calculator.md). The chat preview remains separate.

The prescribed-curvature API accepts known forces plus three prescribed curvatures and solves for the required moments; a full forward solve must recover the target deformation within reported tolerances ([chunk 3](walkthroughs/chunk-3-constrained-analysis.md)). Since 11 October, `POST /v1/cases/solve` accepts a whole case, as JSON or TOML text, and returns every result the engine determines plus the answer-key comparison ([note](api-case-endpoint-2026-10-11.md)); a material can be named by its library dataset id anywhere a case or request takes one, and the result carries the citation of every value used. The founder's own problems go through the case calculator by the [cheat sheet](engine-cheat-sheet.md).

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
- Failure checks give first-ply failure only: the onset of ply cracking, not the laminate's ultimate strength. Four criteria run; Hashin does not. Maximum strain limits derived from strengths assume linear behavior to failure and must be requested in the case.
- Plate buckling covers simply supported, midplane-symmetric laminates. The series solution for angle-ply laminates is an upper bound to be converged by the user, and no external buckling answer key has been checked yet. Clamped or free edges, unsymmetric laminates and postbuckling are not modeled.
- A uniform temperature change gives thermal resultants and residual ply stresses (ADR-0014), and first-ply failure includes them (ADR-0017). Moisture and temperature-dependent properties are not modeled.
- Material values can be typed or taken from the library by dataset id. Typed values are not checked against any source; library values are converted once and cited.
- Copyrighted references (Daniel and Ishai, CMH-17, course material) are cited by table and page only; the website hosts no copies and shows only the individual values it records (ADR-0018). Public data comes from NCAMP, AGATE, NASA and manufacturer documents.
- The engine is checked against textbook and course problems, not yet against our own coupon tests. It is not approved for design decisions.
- The website's chat captures inputs but does not calculate results.
