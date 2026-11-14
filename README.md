# Anisotropy

Composite laminate analysis and coupon finite element models, with a cited materials library. The website is Next.js; the engine, the finite element package (`fea/`) and the API are Python. A language model is optional: without a key the assistant uses templates, and the engine still computes every number.

The hosted site, [anisotropy.dev](https://anisotropy.dev), is invite-only (ADR-0056). This repository is public, but its code and content are not open source: see [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Getting started

### The website

Requires Node.js 24 or newer and npm.

```sh
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000). Without the API every page opens, but nothing is calculated. For the production preview:

```sh
npm run build
npm run preview
```

Open [localhost:3001](http://localhost:3001). Stop either server with Ctrl+C.

### The API, the engine and the finite element package

Requires [uv](https://docs.astral.sh/uv/). `engine/`, `fea/` and `api/` are separate uv projects; the API uses the engine and runs coupons through the `fea` project. Start the API from the repository root:

```sh
cd api
uv sync --locked
ANISOTROPY_RUN_RECORDS=off uv run uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000
```

In PowerShell, run `$env:ANISOTROPY_RUN_RECORDS = "off"` first, then the `uv run` command without the prefix. `ANISOTROPY_RUN_RECORDS=off` starts the API without its run-records database; [api/README.md](api/README.md) sets up the database and describes every endpoint.

Point the website at the API: copy `.env.example` to `.env.local` (it sets `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000`), then restart `npm run dev` or rebuild.

A coupon run also needs CalculiX: set `ANISOTROPY_CCX` to its `ccx` executable, or put `ccx` on `PATH` ([docs/installation-fea-tools.md](docs/installation-fea-tools.md)). The PDF report needs [Tectonic](https://tectonic-typesetting.github.io/); without it the run still finishes, without the PDF.

## Try it

With the API, the website and CalculiX set up as above:

1. Open [localhost:3000/workspace/fea](http://localhost:3000/workspace/fea).
2. Keep ASTM D3039, pick **IM7 / 8552** under Material, type `[45/0/-45/90]s` under Layup and select **Use**.
3. Select **Run analysis**. The run shows its steps; the result opens in the 3D view with the report (a PDF when Tectonic is installed) and the files to download.

For a laminate, open `/workspace/laminate` or `/calculator`.

## Project structure

```text
api/          The laminate and coupon API (Python, FastAPI)
app/          Pages, layout and styles (Next.js)
components/   User interface components
docker/       Helpers for the solver image (root Dockerfile) and the local database's first-start script (docker-compose.yml)
docs/         Decision records, theory, evaluations, manuals and the documentation index
engine/       The laminate analysis engine (Python)
fea/          The finite element package: decks, kernel, checks and the coupon tool (Python)
lib/          Client logic, material records and physics references
public/       Brand marks, images and other files the site serves
scripts/      Build, export and asset scripts
services/     The material source monitor
tests/        Unit tests (tests/*.test.ts) and browser tests (tests/browser/)
worker/       The Cloudflare Worker of the hosted site
```

[docs/README.md](docs/README.md) is the index to what is built, why, and how it is checked. Dependencies, builds, environment files and test output are not committed, and private material lives in the git-ignored `.local/` (ADR-0037, ADR-0042).

## Pages

| Route | Contents |
| --- | --- |
| `/` | The home page: what Anisotropy does, a demonstration, the supporters, the services, the team and the news |
| `/about` | What we are building, the workflow, the roadmap, the lab loop and the team |
| `/industries` | Aerospace first, research and education next, and the industries that may follow |
| `/services` | The five services, one card each, from `lib/services.ts` (ADR-0058) |
| `/services/<slug>` | One page per service: computer-aided design, finite element modeling, test plans, documentation, manufacturing plans |
| `/contact` | How to reach us |
| `/library` | Material records and physics references |
| `/sources` | Textbook citations, recorded property values and unit conversions |
| `/workspace` | The front door (ADR-0062): a tile per kind of work and the projects this browser keeps |
| `/workspace/fea` | The coupon workspace: an unnotched tension coupon, under ASTM D3039 or no standard, built from its material and layup (ADR-0089, ADR-0090), solved and viewed in 3D, with the coupon assistant beside it |
| `/workspace/fea/view` | The viewer window of one job, by `?job=<id>` |
| `/workspace/laminate` | The laminate workspace: the problem's panels, the stack and the engine's answer in the units you pick (ADR-0060), the laminate assistant beside them |
| `/chat`, `/chat/view`, `/studio`, `/studio/view` | Redirect to the workspace with their query (ADR-0062; ADR-0058 amendment 1) |
| `/data` | Local CSV inspection and submission preview (not in the header) |
| `/calculator` | Editable laminate form with engine stiffness, strains and curvatures (not in the header) |

## Limits

- The assistants read typed messages with fixed patterns. When a language model is configured for the API (`ANISOTROPY_ASSISTANT_PROVIDER`, `ANISOTROPY_ASSISTANT_MODEL` and the provider's key; see `.env.example`), it may propose rows from a message, which enter only when the engineer ticks them (ADR-0088), and rephrase an explanation, which is withheld unless every number in it is the engine's (ADR-0052). The engine and the `fea` package compute every number.
- The coupon workspace offers the unnotched tension coupon only, under ASTM D3039 or no standard, until its comparison with Abaqus is verified (ADR-0089). `ANISOTROPY_ALL_TESTS=on` shows the other tests for development.
- First-ply failure is offered for laminates and coupons. CAD generation, optimization and training are not.
- Results and exports are analyses, not qualified design allowables or approval of a manufactured part.
- A project is kept in this browser and, when the API keeps run records (as the hosted site does), also on the server under the signed-in person (ADR-0062). The example CSV values on `/data` are synthetic.

## Materials library

`/library` lists each material with its cited datasets: every value with its source, test conditions and units, the publication or revision date and a link to the original source. Every source carries a rights class: public domain, open publisher, or a licensed reference whose individual values are cited by table and page only (ADR-0018). The engine reads the same records through `npm run export:library` (ADR-0020). How the datasets were chosen is in the material data documents listed in [docs/README.md](docs/README.md).

Engineers can export preliminary analysis inputs for a selected purpose when its required properties are present, internally consistent and free of unresolved flags. Exports include source evidence, original units, conversions and acknowledged applicability assumptions. School data and manufacturer data are separate datasets, particularly where processing conditions differ.

On `/data`, load the example or import a CSV. Preview checks cover required fields, positive values and basic specimen geometry. Files stay in the browser. Limits: 5 MB and 5,000 records.

The physics library's formula cards are cited and rendered with KaTeX. Numerical reference checks reproduce selected textbook examples; they are not a production analysis solver.

## Local reference archive

`.local/sources/references/` holds local PDF snapshots, per-property references, dataset exports and file fingerprints (it was `References/` at the root until 2026-10-21). `.local/` is excluded from Git, and its layout is in `.local/README.md` (ADR-0037); full textbooks and handbooks are not bundled with the website. `scripts/build-reference-archive.ts` recreates a dated archive when the original local research PDFs, handbook metadata and supplied books are available at the paths listed in that script. These local inputs are optional for running the website and its tests. Existing archive folders are never overwritten.

Textbook material-property links open `/sources` with the exact table citation and selected property. The viewer covers Daniel and Ishai, second edition: printed pp. 377-380 / supplied PDF pp. 397-400 (Tables A.4-A.6). It distinguishes recorded source values from website conversions and links to the publisher. Page scans and the full supplied PDF remain local; they are not website assets. For internal inspection, `npx tsx scripts/render-textbook-evidence.ts <pdf-path> [pdftoppm-path]` writes fingerprinted images and a manifest under ignored `.local/sources/textbook-evidence/daniel-ishai-2006/`. A different PDF fingerprint is rejected. Formula-library book links still identify the publisher.

Research screenshots supplied during development are not publicly included. Study-specific measurements remain unpublished.

## Checks

From the repository root:

```sh
npm test
npm run typecheck
(cd engine && uv run pytest)
(cd fea && uv run pytest -q -ra tests ../engine/tests)
(cd api && uv run pytest -q)
```

The API's database tests run when `TEST_DATABASE_URL` is set ([api/README.md](api/README.md)) and are skipped with the reason otherwise; finite element tests that need CalculiX or Gmsh are skipped the same way without them.

Browser tests run against the production preview. Build and start it (`npm run build`, `npm run preview`), then in another terminal:

```sh
npm run test:e2e
```

`npm run test:calculator` runs the calculator cases against the real API and starts missing local servers itself; the website must be built with `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000`. `npm run test:studio` runs the workspace cases with the API played from `tests/fixtures/studio`; the website must be built with `NEXT_PUBLIC_ANISOTROPY_API_URL` set to any address. Browser checks use an installed Microsoft Edge; set `BROWSER_CHANNEL=chrome` to use Chrome, or `PREVIEW_URL` to test another address.

## Deployment

`npm run build` exports a static website to `out/`; serve that folder over HTTP, since opening the HTML files directly is not supported. A merge to `main` whose Tests workflow passes deploys anisotropy.dev through `.github/workflows/deploy.yml`: the site, and the API with its solver image, on Cloudflare (ADR-0056). [docs/walkthroughs/hosted-deploy.md](docs/walkthroughs/hosted-deploy.md) explains the pieces and how to roll back.

## Customer data and government deployment direction

Future MVP work should treat customer data protection as an architecture requirement: define the deployment boundary, isolate customer workspaces, restrict and audit access, control retention and deletion, and prevent customer content from entering unapproved services or shared training. Keep sensitive content out of URLs and telemetry. Model and dependency licenses must support the intended commercial deployment.

Determine applicable export-control and contract requirements for each intended deployment before accepting controlled data. These are development requirements, not implemented controls or a claim of ITAR compliance, certification, or government authorization.

## Material source monitoring

The monitor checks manufacturer datasheets, ASTM active-edition catalog pages and fixed original publications for changes, and queues each change for review. The public catalog uses `lib/curated-materials.ts`; the original evidence mappings remain an investigation archive. A standard revision never retroactively changes a measured property, fixed-paper monitoring does not discover new papers, and no source check qualifies a material or creates design allowables.

The service writes a sanitized status feed to `public/materials/catalog-status.json` and the local `out/` export. A website build made with `NEXT_PUBLIC_MATERIAL_MONITOR=on` reads the feed every 30 seconds, stops asking after a 404 and marks a missing or stopped monitor unavailable. The hosted build leaves the flag unset: the library then fetches nothing and says the values are pinned to the cited edition. Only metadata and structured reference values enter this feed; original documents and reviewer information remain local. Static deployment alone does not run the monitor: a persistent worker and feed publication must be configured for the target host.

With Node.js 24+, run `npm run monitor:start` and open [the local review console](http://127.0.0.1:3210). Due sources are checked on startup and daily while the service remains running. No OS startup service or external notifications are installed. See [monitor setup and boundaries](services/material-monitor/README.md) for the sources, commands, operation and tests.
