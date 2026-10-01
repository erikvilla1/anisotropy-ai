# Anisotropy AI

A research-focused composites website with a materials library, educational physics references, and a guided engineering chat preview. Built with Next.js, React, and TypeScript. No backend or API keys are required.

## Getting started

Requires Node.js 20.9 or newer and npm.

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
| `/industries` | Aerospace and research/education priorities; potential markets |
| `/services` | Composite development workflow and planned product offerings |
| `/library` | Material records, illustrative layups, and physics references |
| `/chat` | Dedicated conversation interface with editable specifications |
| `/data` | Local CSV inspection and submission preview |

## Try the experience

Enter `Scope a carbon epoxy D5766 coupon, 250 x 36 mm, at 20 kN` in the homepage composer and press Enter. Follow up with a safety factor or use **Edit specification** to review the geometry, material, layup, and boundary conditions. Change the response format to explore briefs, comparison tables, checklists, JSON, or a LaTeX report outline.

In the library, browse 22 source material records and 32 educational functions/methods across five physics topics. Records retain the supplied appendix's units and signs. Missing values remain missing; unusual source entries are flagged for review. The collection is a research reference, not qualified design allowables.

On `/data`, load the example or import a CSV. Preview checks cover required fields, positive values, and basic specimen geometry. Files stay in the browser. Limits: 5 MB and 5,000 records.

## Preview limitations

The conversation uses a local intent parser, not a live language model. It captures supported inputs and requests missing information; it does not compute engineering results. Unknown fields stay empty. Reloading clears the conversation and uploaded CSV data. The homepage briefly uses sessionStorage to carry a prompt into chat; a query-string fallback is used if storage is unavailable.

Example CSV values and field illustrations are synthetic. No actual analysis, CAD generation, optimization, failure prediction, or training occurs. LaTeX downloads are uncompiled outlines containing the current inputs and pending-result sections. Physics equations are educational reference content, not an executable solver.

Research screenshots supplied during development are not publicly included. Study-specific measurements remain unpublished. Material values in the separate Appendix F document are included with their source context and review notes.

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
