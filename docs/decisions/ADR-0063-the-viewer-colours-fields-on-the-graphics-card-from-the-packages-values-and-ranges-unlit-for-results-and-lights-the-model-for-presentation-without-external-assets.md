# ADR-0063: The viewer colours fields on the graphics card from the package's values and ranges, unlit for results, and lights the model for presentation without external assets

- Status: Proposed
- Date: 2026-11-06
- Decided by: Founder, 2026-11-06 ("what do you think about this, is this good to add? A 'presentation' lighting mode", drei's Environment, ContactShadows, a clearcoat MeshPhysicalMaterial; "Colour the stresses on the graphics card"; "A small shader could take the raw values and draw smooth or banded contours with crisp isolines"; "Results mode should stay mostly unlit so the shading never skews the colours"; then "lets do it no mistakes" for this part) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0053](ADR-0053-plate-bending-by-an-mitc4-flat-shell-with-five-dofs-on-the-laminates-a-b-d-and-transverse-shear-stiffness.md), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (part 4); `fea/src/anisotropy_fea/fields.py`, `components/studio/field-material.ts`, `components/studio/scene-lighting.tsx`, `components/studio/scene-canvas.tsx`, `lib/studio-colors.ts`, `lib/studio-fields.ts`; risk R-20
- Area: website

## Context

The viewer of ADR-0051 drew the plate under one ambient and two directional lights with a rough standard material, and coloured a field by computing one red-green-blue triple per vertex in the browser and rebuilding the geometry's colour attribute at every field switch. The lights shaded the colours, so one legend colour stood for two values on faces turned differently. The legend's ends were the smallest and largest of the values in the browser, derived there; the ramp was smooth only, with no bands and no isolines; the model before a run looked flat. The founder, planning part 4 of the workspace refactor (ADR-0062), asked for a presentation lighting mode for the model and for the stresses coloured on the graphics card with banded contours and crisp isolines, the results left unlit.

What binds the design: the browser computes no number (ADR-0001); every number the page shows is written by the fea package (ADR-0051; risk R-20); the site is a static export served behind Access, so a page should fetch no asset from a third party at run time; a results colour must mean one value.

## Options considered

1. **Keep the browser-side vertex colours and the three lights.** Rejected: the shading skews the colours, a field switch rebuilds a geometry attribute on the CPU, the legend's ends are the browser's, and bands and isolines would be more CPU work per switch.
2. **An environment from drei's presets.** The presets download an HDR image from a public bucket at run time. Rejected: an outside dependency on a page behind Access; a room of light panels (`Lightformer`) rendered once into the environment map needs no file.
3. **Post-processing (ambient occlusion, bloom) in the same pass.** Deferred: a further dependency, a cost on laptop GPUs, and an interplay with the on-demand frame loop; to be added if the lit model still looks flat.
4. **Isolines at a count of the user's choosing, apart from the legend.** Rejected: a line not matched by a labelled tick is a number drawn without a name.
5. **Two modes on one scene, the package writing the ranges.** Presentation mode for the sketch and the preview: an environment of light panels rendered once, a contact shadow under the part, a physical material with a clearcoat, ACES tone mapping. Results mode: a shader material with no light, one float per vertex (the package's value there), the ends and the ramp as uniforms, bands with an isoline at every band boundary, each boundary a tick on the legend; the package writes every field's range. Chosen.

## Decision

Option 5.

- **The package writes the ranges.** `fields.py` adds `ranges` to `fields.json`: for every field the viewer can show, the smallest and largest value of the array as written (nine significant digits, so each end equals the array's own extreme), element values and display averages apart, a `[min, max]` per ply, and per ply and face when the package wrote faces, for the ply stresses and the von Mises stress, per criterion for the failure index, and per criterion and ply (the worse face) for the failure index of one ply. `ranges_note` says so.
- **The legend's ends are the package's.** `lib/studio-fields.ts` reads the range of the chosen field as shown; `lib/studio-colors.ts` builds the scale from it and no longer derives the ends from the values. A job solved before the package wrote ranges falls back to the smallest and largest value shown, picked from the package's array, and the legend says so. The symmetric span of a signed field around the grey midpoint and the ticks along the ramp are display positions, as under ADR-0051; the legend prints the written ends beside them.
- **Results mode is unlit and on the graphics card.** `components/studio/field-material.ts` is a shader material: an attribute `value` per vertex, uniforms for the ends, the seven ramp stops, the band count and the isoline width. A fragment's colour is the ramp at its value, or the band's centre colour when banded, with a one-pixel isoline (`fwidth`) at every band boundary; a value the package did not write is the named grey. The top and bottom faces are the pure colour; the side faces are darkened a little so the thickness reads. Switching a field uploads one float per vertex and sets the uniforms; the geometry stays. The contours control offers smooth, 5, 8 (the default) or 10 bands; the legend draws one flat step per band and one tick per boundary. No light is in the scene in results mode.
- **Presentation mode lights the model.** `components/studio/scene-lighting.tsx`: four `Lightformer` panels in an `Environment` rendered once, a `ContactShadows` floor turned to the scene's z-up, a weak directional light, `MeshPhysicalMaterial` with a clearcoat (`PRESENTATION_MATERIAL`), ACES tone mapping on the renderer. The sketch and the preview use it; `data-mode` on the canvas names the mode.
- **Not in this pass:** post-processing (option 3); a bundled HDR image.

## As built (2026-11-06)

`fea/src/anisotropy_fea/fields.py` (`span`, `per_ply_spans`, the `ranges` block and `ranges_note`), `fea/tests/test_fields.py` (every written range equals the array's extremes; the ends of the failure index equal the summary's); the three browser fixtures regenerated by `fea/tools/studio_tool.py --root <empty> fixtures` (their checklist, preview and explanation also caught up with ADR-0061's wording and sets). `lib/studio-api.ts` (`ranges`), `lib/studio-fields.ts` (`rangeFor`, `FieldValues.range`), `lib/studio-colors.ts` (`scaleFor` from a range, `ends` and `source` on the scale, `legendGradient`), `lib/studio-geometry.ts` (`fieldAttribute`), `components/studio/field-material.ts`, `components/studio/scene-lighting.tsx`, `components/studio/scene-canvas.tsx` (`field` replaces `colors`; the modes), `components/studio/sketch-canvas.tsx`, `components/studio/results-view.tsx` (the contours control, the legend). Tests: `tests/studio-colors.test.ts`, `tests/studio-fields.test.ts`, `tests/studio-geometry.test.ts`, `tests/browser/studio.spec.ts` (the mode attribute on the preview and the results, the legend's ends equal to the fixture's written range, the canvas kept across a field switch, the contours control, a scenario photographing the lit sketch and preview, three.js console errors failing the test). Seen in the headless screenshots: the contact shadow reads only faintly on the site's near-black background; a lighter floor under the part is the next thing to try if the founder wants the shadow seen.

## Why (evidence)

- `cd fea && uv run pytest -q tests/test_fields.py tests/test_studio_tool.py`: 15 passed (44.75 s).
- `npm run typecheck`: clean. `npm test`: 151 passed.
- `npx playwright test --config playwright.studio.config.ts`: 13 passed (1.2 min) before the presentation scenario was added; the first scenario rerun with three.js console errors captured: 1 passed. The screenshots `.local/website/screenshots/studio-results.png`, `studio-bending.png`, `studio-sketch-lit.png` and `studio-preview-lit.png` show the banded contours with their isolines on the tension and bending coupons, and the lit sketch and preview; viewed by Claude Code, not yet by the founder.
- `STUDIO_LIVE=1 npx playwright test --config playwright.studio-live.config.ts` against the local API: 1 passed (1.2 min). The whole suite after the presentation scenario was added: 14 passed (1.2 min).
- Frame times on a laptop GPU: no evidence yet.

## Consequences

Easier: a colour on the plate is the legend's colour for that value; the legend's ends are on record in the package's file; a field switch moves uniforms and one attribute; bands and isolines come for free from the shader; the model before a run reads as a part. Harder: two materials and two lighting sets on one scene; a shader is harder to unit-test than a function, so its behaviour is held by the browser scenarios and the screenshots. We now depend on drei's `Environment`, `Lightformer` and `ContactShadows` and on `fwidth` in the fragment shader (WebGL 2, which three 0.186 requires).

## How we will know it was wrong

- A colour on the plate that is not the legend's colour for its value, or a legend end the package did not write.
- The lit model still reads flat and the founder asks for ambient occlusion: option 3 then.
- A field switch or an orbit drops below a smooth frame rate on a laptop at the mesh sizes the checklist admits.
