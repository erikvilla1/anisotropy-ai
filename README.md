# Anisotropy AI · Research preview v.01

A presentation-first, responsive frontend based on the supplied technical specification and architecture. Built with Next.js, React, TypeScript, Lucide icons, and locally bundled fonts. No backend or API keys are required.

## Run locally

Requires Node.js 20.9+ and npm.

```sh
npm ci
npm run dev
```

Open http://localhost:3000. For the presentation, use the production build:

```sh
npm run build
npm run preview
```

Open http://localhost:3001. `npm start` serves the same production output on port 3000. Stop a server with Ctrl+C.

## What's included

- Project overview, four-stage workflow, and phased roadmap.
- Original coupon photographs, microscopy, and source diagrams with accessible image dialogs.
- Internal architecture and technical-specification PDFs are retained in the project root and excluded from the public website.
- An explicitly labeled, local scoping demo with scope briefs, D3039/D5766 comparison tables, test-data checklists, and JSON exports.
- A local CSV workflow: file selection or drag-and-drop, schema checks, row-level errors, data preview, simulated review submission, and JSON export.
- Responsive navigation, reduced-motion support, keyboard controls, focus styles, and locally bundled fonts.
- Dedicated About, Industries, Services, and Materials library pages in the top navigation.
- Home: a message composer that opens `/chat`, plus a research foundation explaining the planned use of reviewed open datasets, published research, and lab evidence as the evidence foundation.
- About: research priorities, the physical model, the fabrication/test loop, and the user-facing engineering model. Behind-the-scenes AI implementation is intentionally omitted.
- Industries: Aerospace and Research & education are priorities; wind, mobility, marine, and manufacturing are potential markets.
- Services: the product workflow from scope and material selection through CAD, CLT/FEA, candidate screening, layup optimization, verification, documentation, and educational explanations.
- Dedicated `/chat` page: editable coupon specification, varied response formats, and a downloadable LaTeX report outline through the conversation. `/data` holds the local test-data submission preview.
- Materials library: 22 source-linked material/process records from the supplied six-page Appendix F, family and text filters, original units, missing-value handling, flagged source inconsistencies, and JSON record export. This is a research reference collection, not design allowables.
- Physics library: 32 expandable functions and methods in five topics—CLT, ply failure, CAD/FEA verification, open-hole/damage, and layup optimization. Includes Q/S/Q-bar, ABD, transformations, local strain/stress recovery, Tsai–Hill, Tsai–Wu, and Hashin with assumptions and references.

## Presentation walkthrough

1. Start with the overview and research foundation: physics produces the numbers, and material records preserve their sources.
2. Walk through the proposed define → analyze → test → document workflow.
3. Browse the supplied lab images and open the source diagrams.
4. In the home composer, enter: `Scope a carbon epoxy D5766 coupon, 250 x 36 mm, at 20 kN`. Press Enter to open the separate chat page with the first response.
5. Follow up with: `Use a factor of safety of 1.5`. Select **Structured JSON** and send `Export my scope` to demonstrate a different response format.
6. Open `/data`, load example data, review the rows, and choose **Preview submission**.
7. End with the research roadmap and material source library.

Use **About** to explain the physics/research/lab loop, then **Industries** to discuss the priorities. **Services** describes the product offering. In **Chat**, open **Edit specification** to enter thickness, hole diameter, layup, restraints, and conditioning. Select the report response format in chat to download a report outline. In **Materials library**, search for a material, open its exact PDF source page, inspect review flags, select a layup concept, and browse the physics topics. **Discuss this material** carries the record name and source context into a draft scope without assigning its raw properties to a solver.

## What is simulated

This is a frontend portfolio, not an engineering system. The assistant uses a small deterministic intent parser in `lib/demo.ts`; it is not connected to an LLM and is not a general conversational assistant. It recognizes test method, supported material-family mentions, two- or three-part dimensions in millimeters, thickness, hole diameter, loads in kN, ply count, bracketed stacking sequences, allowed angles, grip restraints, conditioning, and safety factor. Use the specification form to review or correct captured inputs. Unknown fields stay unfilled. It never calculates strength, layups, or margins. Comparison and checklist responses use curated project content.

Example CSV records and the stress-strain graphic are illustrative, not measured lab evidence. CSV validation checks a preview subset of the proposed schema, not ASTM compliance or engineering validity. Files stay in memory in the current browser tab; reloading clears uploads, submissions, and conversation history. No data is sent to a server or used for training.

The home composer briefly stores its pending prompt and response format in sessionStorage for navigation, then consumes and removes that entry on the chat page. If browser storage is unavailable, an encoded query-string handoff is used and removed from the address bar after consumption. Shift+Enter adds a line; Enter submits. The material query parameter only identifies a catalog record.

Appendix F properties are transcribed in `lib/materials.ts`; the original PDF is in `public/assets/material-properties-2026-v2.pdf`. Source signs and units are preserved, with no inferred replacements for missing entries. Fraction-like values under percentage headings, unusual strength/density magnitudes, and the aluminum core brand attribution are flagged for review. The 2026 appendix contains older dated and nominal records; its document date is not treated as a new measurement date. Educational equations in `lib/physics.ts` are reference content, not an executable analysis library, and remain extensible as more physics and source material are supplied.

The CAD/field visual is code-native concept artwork, not a solver output or representation of entered geometry. Changing its shape is a UI illustration, not an optimization. CAD downloads contain only input definitions; STEP/INP/VTU generation needs the real engine. LaTeX downloads are uncompiled report outlines with the current user inputs, governing-method examples, and pending-result sections. No PDF, physical analysis, failure prediction, or material allowables are generated.

The new research screenshots informed the qualitative fabrication/testing/microscopy story and references. They are not copied into public assets, and their test measurements and performance percentages are not published. Printed-polymer research is explicitly distinguished from validation of the composite-laminate MVP. Industry cards describe targets, not existing customers or certified capabilities.

## CSV fields

Download the template from the interface. This preview expects:

`coupon_id, panel_id, material_id, test_standard, layup, n_plies, thickness_mm, width_mm, hole_d_mm, failure_load_kN, failure_stress_MPa, modulus_GPa, failure_mode`

Only D3039 and D5766 are accepted. Additional metadata columns are preserved in the JSON review package. Limits: 5 MB / 5,000 records. Invalid data cannot advance to the submission preview.

## Validation

```sh
npm run test
npm run typecheck
npm run build
npm run preview
# In a separate terminal:
npm run test:e2e
```

Browser checks use installed Microsoft Edge by default. Set `BROWSER_CHANNEL=chrome` to use Chrome and `PREVIEW_URL` to change the URL. They cover source assets, dialogs, chat context, response formats, downloads, CSV validation/submission, and phone-sized layouts.

## Hosting and future work

The `out/` directory is a static website. Deploy it to a static host; no runtime server or secrets are required. It must be served over HTTP, not opened as a local HTML file. The project has not been published to an external host.

To connect real services later, replace the demo adapter behind the workspace with the planned `/assistant` and test-import APIs, keep credentials on the server, and retain explicit solver provenance for every numerical result. The current design separates project content, workspace components, and demo logic so this can evolve after real tests.

## Source assets

Original root-folder files are preserved. Web copies are in `public/assets`. Lab images are labeled by their source filenames; no test result is inferred from a photograph. The carbon-fiber image is used as a visual background. No HTML files or raw CSV measurements were present in the supplied folder at implementation time.

## Brand and public content

The site uses the supplied Anisotropy AI carbon-weave mark. Its SVG viewport is fitted to the symbol for the header and favicon; the original Downloads files are unchanged. Backend stack, tooling choices, training details, and internal planning documents are excluded from the public experience. Scientific methods, educational references, and honest product-preview limits remain visible.

The header’s **Open chat** action opens `/chat` as a dedicated conversation page. It has a compact brand/back header, conversation, input editor, response formats, and composer. Marketing navigation, footer, sidebar, data-submission link, and the separate analysis showcase are omitted from this page.
