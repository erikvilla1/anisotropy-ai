# Anisotropy AI

A research-focused composites website with a materials library, educational physics references, a guided engineering chat preview and a laminate calculator. Built with Next.js, React, and TypeScript. The calculator uses the local Python API; the other pages run without a backend. No AI API keys are required.

## Getting started

Requires Node.js 24 or newer and npm (including the material-monitor service).

```sh
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000). For the production preview:

```sh
npm run build
npm run preview
```

Open [localhost:3001](http://localhost:3001). Stop either server with Ctrl+C.

## Project structure

```text
api/                    Local laminate calculation API (optional, Python)
engine/                 Standalone laminate analysis engine
app/                    Pages, layout, and styles
components/             Shared UI and conversation components
lib/                    Demo behavior, material records, physics references
public/assets/
  brand/                Company logo and favicon artwork
  documents/            Material-property source appendix
  figures/              Research diagrams
  images/               Coupon, microscopy, and background images
tests/                  Unit and browser tests
```

All website media is stored under `public/assets`. Original duplicate files and the unused analysis-showcase component have been removed. Internal planning PDFs and one unused source photograph are retained locally under `.local/notes/project-docs/`, which is excluded from Git. `CLAUDE.md` files at any directory level are excluded too. Dependencies, generated builds, environment files, local previews, and test output are not committed.

The [local API and chunk 1 walkthrough](api/README.md) exposes one-material laminate stiffness and deformation from the Python engine. The website now calls it from `/calculator`; see [chunk 2 setup and walkthrough](docs/walkthroughs/chunk-2-calculator.md). Copy `.env.example` to an untracked `.env.local` if absent, start the API on port 8000, and restart development or rebuild the website. Without a configured API address, calculation is disabled. Other pages remain usable.

[Chunk 3](docs/walkthroughs/chunk-3-constrained-analysis.md) adds the API tool for known forces and prescribed curvature, returning required moments with numerical verification. It is available in the API explorer at `http://127.0.0.1:8000/docs`; the browser calculator and chat do not call this new operation yet.

## Pages

| Route | Contents |
| --- | --- |
| `/` | Project overview, research imagery, roadmap, and chat entry |
| `/about` | Engineering model, research priorities, and lab workflow |
| `/industries` | Aerospace and research/education priorities; potential industries |
| `/services` | Composite development workflow and planned product offerings |
| `/library` | Material records and physics references |
| `/sources` | Textbook citations, recorded property values and unit conversions |
| `/chat` | Dedicated conversation interface with editable specifications |
| `/data` | Local CSV inspection and submission preview |
| `/calculator` | Editable laminate form with engine stiffness, strains and curvatures |

## Try the experience

Enter `Scope a carbon epoxy D5766 coupon, 250 x 36 mm, at 20 kN` in the homepage composer and press Enter. Follow up with a safety factor or use **Edit specification** to review the geometry, material, layup, and boundary conditions. Change the response format to explore briefs, comparison tables, checklists, JSON, or a LaTeX report outline.

The material lookup contains 15 materials with 17 distinct datasets and 286 property entries from Daniel and Ishai, original manufacturer publications, NASA, NCAMP and experimental research. English/imperial and SI/metric columns are grouped with stiffness first. Publication/revision dates, original-source links, exact test or model conditions, and per-property methods/pages accompany the values. Exports pin the selected dataset and reference and preserve ranges and lower bounds. Thirteen unresolved imports are preserved in the repository but excluded from the public lookup; there is no classroom-source fallback. See [the current property release](docs/material-property-expansion-2026-10-02.md) and [the earlier reference audit](docs/material-research-audit-2026-10-01.md).

The original 22-record school import still has transcription tests against its pinned six-page PDF. Agreement with that document does not establish experimental validity. The public catalog uses separately cited datasets and does not merge properties across processing conditions.

Engineers can export preliminary analysis inputs for a selected purpose when its required properties are present, internally consistent and free of unresolved flags. An unrelated questionable property does not block an otherwise complete input set. Exports include source evidence, original units, conversions and acknowledged applicability assumptions. They do not constitute qualified design allowables or approval for a manufactured part. School data and manufacturer data are separate datasets, particularly where processing conditions differ.

On `/data`, load the example or import a CSV. Preview checks cover required fields, positive values, and basic specimen geometry. Files stay in the browser. Limits: 5 MB and 5,000 records.

## Preview limitations

The conversation uses a local intent parser, not a live language model. It captures supported inputs and requests missing information; it does not compute engineering results. Unknown fields stay empty. Reloading clears the conversation and uploaded CSV data. The homepage briefly uses sessionStorage to carry a prompt into chat; a query-string fallback is used if storage is unavailable.

Example CSV values and field illustrations are synthetic. The separate `/calculator` performs stiffness/deformation analysis through the Python API using explicit inputs; its example uses cited material properties and constructed loads. CAD generation, optimization, failure prediction and training are not offered by the website. LaTeX downloads are uncompiled outlines containing the current chat inputs and pending-result sections. The physics library contains 29 cited formula cards rendered with KaTeX. Numerical reference checks reproduce selected textbook examples; they are not a production analysis solver.

## Local reference archive

`.local/sources/references/` holds local PDF snapshots, per-property references, dataset exports and file fingerprints (it was `References/` at the root until 2026-10-21). `.local/` is excluded from Git, and its layout is in `.local/README.md` (ADR-0037); full textbooks and handbooks are not bundled with the website. `scripts/build-reference-archive.ts` recreates a dated archive when the original local research PDFs, handbook metadata and supplied books are available at the paths listed in that script. These local inputs are optional for running the website and its tests. Existing archive folders are never overwritten.

Textbook material-property links open `/sources` with the exact table citation and selected property. The viewer covers Daniel and Ishai, second edition: printed pp. 377-380 / supplied PDF pp. 397-400 (Tables A.4-A.6). It distinguishes recorded source values from website conversions and links to the publisher. Page scans and the full supplied PDF remain local; they are not website assets. For internal inspection, `npx tsx scripts/render-textbook-evidence.ts <pdf-path> [pdftoppm-path]` writes fingerprinted images and a manifest under ignored `.local/sources/textbook-evidence/daniel-ishai-2006/`. A different PDF fingerprint is rejected. Formula-library book links still identify the publisher.

Research screenshots supplied during development are not publicly included. Study-specific measurements remain unpublished. The original Appendix F import is preserved for investigation; it is not the public lookup dataset.

## Checks

```sh
npm test
npm run typecheck
npm run build
npm run preview
```

With the preview running, use another terminal:

```sh
npm run test:e2e
```

The calculator cases require the local API on port 8000 and a website built with `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000`. After that build, `npm run test:calculator` runs just these cases and starts missing local servers automatically. CI also runs these cases against real API and website processes.

Browser checks use an installed Microsoft Edge browser. Set `BROWSER_CHANNEL=chrome` to use Chrome or `PREVIEW_URL` to change the test URL. Checks cover navigation, images, chat handoff, specification editing, downloads, material references, CSV review, and responsive layouts.

## Deployment

The production build exports a static website to `out/`. Serve that directory through an HTTP static host; opening the HTML files directly is not supported. Pushing this repository to GitHub does not automatically publish the website.

## Customer data and government deployment direction

Future MVP work should treat customer data protection as an architecture requirement: define the deployment boundary, isolate customer workspaces, restrict and audit access, control retention and deletion, and prevent customer content from entering unapproved services or shared training. Keep sensitive content out of URLs and telemetry. Model and dependency licenses must support the intended commercial deployment.

Determine applicable export-control and contract requirements for each intended deployment before accepting controlled data. These are development requirements, not implemented controls or a claim of ITAR compliance, certification, or government authorization.

## Material source monitoring

The monitor checks six manufacturer sources, eight ASTM active-edition catalogs and three fixed original-publication URLs. The public catalog uses `lib/curated-materials.ts`; the original evidence mappings remain an investigation archive. Automatic checks detect changed sources and queue review. A standard revision never retroactively changes a measured property.

Four supplier datasets support separately reviewed immutable releases through the console. Public adoption checks source identity and property definitions; incompatible changes retain the current dataset. Research and CR III replacements currently require a reviewed code/data release. The conflicting Toray tensile-modulus row is absent from the public table and exports. Fixed-paper monitoring does not discover new papers or new document filenames. The three new publication checks succeeded in the final live run; NCAMP access was intermittent during research and failures remain visible. No source check qualifies a material or creates design allowables.

The service writes a sanitized status feed to `public/materials/catalog-status.json` and the local `out/` export. The website refreshes it every 30 seconds and marks a missing or stopped monitor unavailable. Only metadata and structured reference values enter this feed; original documents and reviewer information remain local. Static deployment alone does not run the monitor: a persistent worker and feed publication must be configured for the target host.

With Node.js 24+, run `npm run monitor:start` and open [the local review console](http://127.0.0.1:3210). Due sources are checked on startup and daily while the service remains running. No OS startup service or external notifications are installed. See [monitor setup and boundaries](services/material-monitor/README.md) for commands, operation, tests, and next increments.
