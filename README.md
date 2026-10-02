# Anisotropy AI

A research-focused composites website with a materials library, educational physics references, and a guided engineering chat preview. Built with Next.js, React, and TypeScript. No backend or API keys are required.

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

All website media is stored under `public/assets`. Original duplicate files and the unused analysis-showcase component have been removed. Internal planning PDFs and one unused source photograph are retained locally under `.local/reference/`, which is excluded from Git. `CLAUDE.md` files at any directory level are excluded too. Dependencies, generated builds, environment files, local previews, and test output are not committed.

## Pages

| Route | Contents |
| --- | --- |
| `/` | Project overview, research imagery, roadmap, and chat entry |
| `/about` | Engineering model, research priorities, and lab workflow |
| `/industries` | Aerospace and research/education priorities; potential industries |
| `/services` | Composite development workflow and planned product offerings |
| `/library` | Material records and physics references |
| `/chat` | Dedicated conversation interface with editable specifications |
| `/data` | Local CSV inspection and submission preview |

## Try the experience

Enter `Scope a carbon epoxy D5766 coupon, 250 x 36 mm, at 20 kN` in the homepage composer and press Enter. Follow up with a safety factor or use **Edit specification** to review the geometry, material, layup, and boundary conditions. Change the response format to explore briefs, comparison tables, checklists, JSON, or a LaTeX report outline.

The material lookup contains 15 materials with 17 distinct datasets and 286 property entries from Daniel and Ishai, original manufacturer publications, NASA, NCAMP and experimental research. English/imperial and SI/metric columns are grouped with stiffness first. Publication/revision dates, original-source links, exact test or model conditions, and per-property methods/pages accompany the values. Exports pin the selected dataset and reference and preserve ranges and lower bounds. Thirteen unresolved imports are preserved in the repository but excluded from the public lookup; there is no classroom-source fallback. See [the current property release](docs/material-property-expansion-2026-10-02.md) and [the earlier reference audit](docs/material-research-audit-2026-10-01.md).

The original 22-record school import still has transcription tests against its pinned six-page PDF. Agreement with that document does not establish experimental validity. The public catalog uses separately cited datasets and does not merge properties across processing conditions.

Engineers can export preliminary analysis inputs for a selected purpose when its required properties are present, internally consistent and free of unresolved flags. An unrelated questionable property does not block an otherwise complete input set. Exports include source evidence, original units, conversions and acknowledged applicability assumptions. They do not constitute qualified design allowables or approval for a manufactured part. School data and manufacturer data are separate datasets, particularly where processing conditions differ.

On `/data`, load the example or import a CSV. Preview checks cover required fields, positive values, and basic specimen geometry. Files stay in the browser. Limits: 5 MB and 5,000 records.

## Preview limitations

The conversation uses a local intent parser, not a live language model. It captures supported inputs and requests missing information; it does not compute engineering results. Unknown fields stay empty. Reloading clears the conversation and uploaded CSV data. The homepage briefly uses sessionStorage to carry a prompt into chat; a query-string fallback is used if storage is unavailable.

Example CSV values and field illustrations are synthetic. No actual analysis, CAD generation, optimization, failure prediction, or training occurs. LaTeX downloads are uncompiled outlines containing the current inputs and pending-result sections. The physics library contains 29 cited formula cards rendered with KaTeX. Numerical reference checks reproduce selected textbook examples; they are not a production analysis solver.

## Local reference archive

`References/` holds local PDF snapshots, per-property references, dataset exports and file fingerprints. It and `.local/` are excluded from Git; the supplied textbooks and handbooks are not bundled with the website. `scripts/build-reference-archive.ts` recreates a dated archive when the original local research PDFs, handbook metadata and supplied books are available at the paths listed in that script. These local inputs are optional for running the website and its tests. Existing archive folders are never overwritten.

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
