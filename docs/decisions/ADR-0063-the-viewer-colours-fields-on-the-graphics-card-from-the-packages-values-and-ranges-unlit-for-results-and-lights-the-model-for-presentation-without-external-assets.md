# ADR-0063: The viewer colours fields on the graphics card from the package's values and ranges, unlit for results, and lights the model for presentation without external assets

- Status: Proposed; a rainbow by default for every field with Spectrum and Green as choices, a white critical outline, a floor grid, axes and a Lighting switch, results unlit by default, amendment 1; results lit by default with a key light that moves with the view, Lighting off for the exact colours, and a Thickness ×2.4 choice, amendment 2; twelve bands by default, no line between bands, and the mesh lines see-through, amendment 3; a tab clamped in its grip drawn grey under jaws, out of the averages and the legend's ends, amendment 4
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

## Amendment 1, 2026-11-21 (the FEA look: a rainbow by default, Spectrum and Green as choices, a white critical outline, a floor grid and axes, and a Lighting switch; decided by the founder)

**Context.** On 2026-11-20 the founder asked whether the workspace's FEA could "look more like FEA, like how the images look like". The mockups ([ADR-0134](ADR-0134-the-fea-workspace-is-the-model-across-the-window-with-the-chat-full-height-on-the-right-and-a-results-card-under-the-model.md)) drew the real coupon and wing records in the home page's rainbow, with element edges, a floor grid, an axis triad, a white outline on the critical element, and lights on the part. Asked whether the rainbow should colour signed stresses too, from lowest to highest as Abaqus and Ansys do, he answered "second yes agree" on 2026-11-21. Asked whether results should be lit, he asked what lit and unlit mean; he was told that unlit, his own choice in this record ("Results mode should stay mostly unlit so the shading never skews the colours"), stays the default, with a switch for the lit look, and that he may still choose lit.

**Options.**
1. *Keep the green ramps.* Rejected by the founder.
2. *The rainbow only for unsigned fields, the grey at zero kept for signed ones.* Rejected by the founder ("second yes agree" to the rainbow for signed stresses).
3. *Lit results by default, as in the mockups.* Not chosen for now: a shaded face shows one legend colour for two values, which this record ruled out; offered as a switch.
4. *A rainbow by default for every field, Turbo and the green ramps as choices, unlit by default with a Lighting switch, and the drawing aids of the mockups.* Chosen.

**Decision.**
- **Colours, under View.** Classic, the default: `RAINBOW` (`lib/rainbow.ts`, the demo's), blue through cyan, green and yellow to red ([ADR-0098](ADR-0098-the-home-pages-demo-shows-an-example-wing-whole-apart-analysed-and-whole-again-from-one-recorded-solve-of-the-mesh-it-draws.md) amendment 12). Spectrum: Turbo's seven stops of [ADR-0071](ADR-0071-the-hero-lens-plays-our-own-public-results-recorded-from-the-workspace-viewer-in-the-turbo-spectrum.md) (amendment 2). Green: the two ramps of before. The choice is remembered in the browser.
- **Signed fields.** Under Classic and Spectrum every field runs from its lowest to its highest value, the ends the package wrote, as finite element programs draw it; zero has no colour of its own and the ticks say where it falls. Under Green a signed field keeps the grey at zero, symmetric about it, as before.
- **The shader** takes up to nine ramp stops and their count, so Classic's five are drawn exactly and not resampled.
- **Outlines and edges.** Under Classic and Spectrum the critical element's outline is white, since red is the rainbow's top, the picked element's is black, and the mesh lines are near black; under Green they stay as before. Mesh lines stay on by default.
- **Ground and axes.** A floor grid under the part that fades with distance, and an X Y Z triad in the model's lower left corner that turns with the view, in both modes.
- **Lighting.** Results stay unlit by default. View, Lighting, turns on a light from the viewer's side: each colour is the ramp's times a shade from 0.6 to 1, and the legend says the shading changes the colours while it is on.
- **Unchanged.** The package writes the ranges, the legend's ends are its ends, the contours default to 8 bands with an isoline at each boundary, and the presentation mode before a run.

**Evidence.** The founder's words above. Scale tests in `tests/studio-colors.test.ts`. Screenshots are named in the As built of [ADR-0134](ADR-0134-the-fea-workspace-is-the-model-across-the-window-with-the-chat-full-height-on-the-right-and-a-results-card-under-the-model.md). No evidence yet that the rainbow is read correctly by an engineer with red-green colour blindness; Spectrum, Green and the legend's numbers are the way around it.

## Amendment 2, 2026-11-21 (results lit by default, the exact colours one tap away, and a Thickness ×2.4 choice; decided by the founder)

**Context.**
- Amendment 1 kept results unlit by default. Its light was a weak one from the viewer's side, and the lit and unlit pictures of the built page hardly differed (`/mnt/project-files/workspace-design/build/lit/`).
- The mockup the founder chose ([ADR-0134](ADR-0134-the-fea-workspace-is-the-model-across-the-window-with-the-chat-full-height-on-the-right-and-a-results-card-under-the-model.md)) draws results lit, with a key light, a fill and a little shine. It also draws the plate 2.4 times as thick as it is.
- On 2026-11-21 he said the live page "doesn't look like how we planned it". A plan offered four choices on a card (https://claude.ai/artifact/S4tPFkM7J9Nery2cjtaP1a). Two of them were:
  - lit by default with the mockup's light, with exact colours one tap away;
  - the true thickness by default, with a choice that draws it 2.4 times as thick and says so on screen.
- He chose "Go with the recommendations".

**Options.**
1. *Unlit by default, as amendment 1.* Rejected by the founder: the model reads flat.
2. *Lit by default with the mockup's light, and Lighting off for the exact colours.* Chosen.
3. *The mockup's 2.4 times thickness by default.* Rejected: a drawing that is not to scale by default misleads. It is a choice instead.

**Decision.**
- **Lit by default.** Results are lit when the page opens, with lights fixed to the camera, so every view is lit alike:
  - a key light up and to the left of the camera;
  - a weaker fill from the right;
  - a small highlight.
- **How much it shades.** A face turned to the viewer keeps about its colour. A side turned away falls to about half of it.
- **Lighting off.** View, Lighting, off, draws every colour exactly as the legend's. The menu says so under the switch ("Off: every colour is exactly the legend's."), and the legend's full sentence for a screen reader says the shading changes the colours while it is on.
- **Thickness ×2.4.** A choice in View, off by default. It draws the plate's thickness 2.4 times as large. While it is on, the legend's line says "thickness ×2.4", and the menu says it draws the plate thicker than it is.
- **Unchanged.** The package's values and ranges, the legend's ends, the bands and the isolines, and the presentation mode before a run.

**As built (2026-11-21).** `components/studio/field-material.ts` (the lit branch of the fragment shader), `components/studio/results-view.tsx` (`lit` true by default, `thick` and `THICKNESS_SHOWN`, the hints in the View menu, the note on the legend). The switches are not remembered between visits.

**Evidence.** The founder's choice above. Screenshots of the lit default beside the mockup in `/mnt/project-files/workspace-design/build/compare/v2-*.png`. No evidence yet that an engineer misreads a lit colour; Lighting off is the way to read a value by colour alone.

## Amendment 3, 2026-11-21 (twelve bands, no line between bands, see-through mesh lines; asked for by the founder)

**Context.**
- After the rebuild of [ADR-0134](ADR-0134-the-fea-workspace-is-the-model-across-the-window-with-the-chat-full-height-on-the-right-and-a-results-card-under-the-model.md) amendment 1, the founder compared the built coupon with the mockup and wrote: "black lines show FEA, not good for engineers to look at not intuitive, wheras on the mockup clearly we can see the stress on the bottom grip, and throughout the entire module which is what i want".
- Three things made the lines black. The mesh lines were opaque near-black (`#1c1c1c`). Every band boundary had an isoline, and where the field is steep, at the tab line, eight isolines sat a few pixels apart and read as one black band. Eight bands also put most of the gauge in one or two colours.
- The mockup (`/mnt/project-files/workspace-design/canvas/fea3d.js`) draws twelve bands with no line between them, and its mesh lines black at 42 % opacity.

**Options.**
1. *Keep the isolines, thinner.* Rejected: at the tab line the field changes by most of the scale in a few elements, so any line per boundary stacks.
2. *Twelve bands, no isolines, the mesh lines see-through, as the mockup.* Chosen.
3. *The smooth ramp by default.* Rejected: a band can be read against the legend; a smooth colour cannot be read as closely. Smooth stays a choice.

**Decision.**
- The contours default to twelve bands. The choices are smooth, 5, 8, 10 and 12.
- Bands are flat colours with no line between them. The isoline uniform and its code are gone from `field-material.ts`.
- Mesh lines over a rainbow are black at 42 % opacity and do not write depth, so the colour reads through them. On the green ramp they stay grey (`#555555`) at the same opacity. Mesh lines stay a layer in View.
- The symbols of a support or a load over an area (a grip) sit a quarter of the area in from its edges, so they no longer cover the tab line, where the field changes most (`sampleNodes`' `inset`). A support or load along a line still runs end to end.
- The legend's ticks (the form outside the workspace) label every band boundary up to ten bands, and every other one above that.
- **Unchanged.** The package's values and ranges, the legend's ends, the lighting of amendment 2.

**As built (2026-11-21).** `components/studio/field-material.ts`, `components/studio/results-view.tsx` (`CONTOURS`, `DEFAULT_CONTOURS`, the tick count), `components/studio/scene-canvas.tsx` (`EDGE_OPACITY`, `SYMBOL_INSET`), `lib/studio-colors.ts` (`overlayColors`), `lib/studio-geometry.ts` (`sampleNodes`).

**Evidence.** The founder's words above. The side-by-side pictures in `/mnt/project-files/workspace-design/build/compare/v3-*.png`, with a close-up of the bottom grip. The mockup's orange patches near the grip come from its own colour lookup, which puts the last band edge at about 94 % where its legend draws it at 90.5 %; the gauge there is 92 to 96 % used, so bands that follow the legend draw it all in the top band. No evidence yet that twelve bands read better than eight to an engineer beyond the founder's own reading.

## Amendment 4, 2026-11-21 (a clamped tab is drawn as the grip, not by value; asked for by the founder)

**Context.**
- The founder asked whether the colours are true: "is the stress true... can't have anything looking wrong needs to be true, also the boundary conditions don't look good and intuitive for an engineer looks wonky as well".
- An independent check (classical laminate theory written apart from the engine, IM7/8552 from the NCAMP record, F12 at 5 % strain) gives the gauge centre's ply stresses to four digits: ply 4 (90°) σ₂ 59.15 MPa and Tsai-Hill 0.9495, the same as element 122 of `tests/fixtures/studio/fields.json`. The reaction by hand from the nominal strain (1 mm over the 138 mm gauge) is 16,128 N against 16,222 N; the 0.6 % is the grips stopping the narrowing near the tabs.
- Two things on the model were not true. Each tab is clamped whole (every node of it held, or moved, by the grip), so its elements move as one body and their zero strain and stress are the clamp's, not a result; they were drawn as "0 % used". And the display averages at the nodes of a tab line took the mean of a clamped element (0) and a gauge element (about 0.95), so a ramp from 0 to 95 % was drawn over one element row on each side, where the model has a step, and the peak at the tab corners (98.7 % as element values) was averaged away.
- The supports were drawn as a cone per held direction at four points of each region; the bottom grip is held in all six directions, so 24 cones stood over the tab line.

**Options.**
1. *Keep the clamp's zeros and the averages across the tab line.* Rejected: a ramp the model does not have.
2. *Leave the clamped elements out of the averages and the ends, draw them in a grey that says "clamped in the grips", and draw each clamped region as its grip.* Chosen. It is what Abaqus does by default with its averaging threshold of 75 %: a node where the elements differ that much is not averaged.
3. *Show element values by default.* Rejected for now: flat squares read worse, and the averaging across the clamp would still be wrong in the smooth view.

**Decision.**
- The fea package names the elements clamped inside a grip, every corner held by it: `mesh.held_elements` (`fields.held_in_grips`). The row along a tab line has free corners and is not one of them.
- The display averages leave them out (`nodal_averages(..., skip)`). A node of a tab line takes the mean of the gauge's elements alone; a node only clamped elements touch has no average.
- The ends the package writes (`ranges`) leave them out of every field but the displacement, so the legend's low end is the free part's. On the example coupon Strength used reads 89.3 % to 98.7 %, and the gauge shows its spread instead of one colour.
- The viewer draws every vertex of a clamped element in the grip's grey (`IN_GRIP`, `GRIP_GRAY` in `field-material.ts`), for every field but the displacement, and the legend says "grey: clamped in the grips" on its own line.
- A support that covers an area and holds it in its plane and out of it is drawn as a grip (`gripOf`): two clear jaws above and below the tab. A fixed grip is hatched at its outer end, the ground symbol. A grip that is also moved is drawn in the load's colour, and its load is three arrows from its outer end. A held edge, a point or a face held out of plane only keeps the cones of ADR-0110.
- A result solved before this has no `held_elements` and is drawn as before.

**As built (2026-11-21).** `fea/src/anisotropy_fea/fields.py` (`held_in_grips`, `nodal_averages`' `skip`, the ranges, the notes), `fea/tests/test_fields.py`; `lib/studio-api.ts`, `lib/studio-fields.ts` (`FieldValues.held`), `lib/studio-geometry.ts` (`fieldAttribute`'s `held`, `gripOf`), `components/studio/field-material.ts`, `components/studio/scene-canvas.tsx` (`Jaws`, `GripArrows`), `components/studio/results-view.tsx` (the legend's note). The averages, ranges and `held_elements` of `tests/fixtures/studio/fields.json` were rewritten from `tools/studio_tool.py live` on its `values.json`; every other part of the file is as it was.

**Evidence.** The hand check above (`/mnt/project-files/workspace-design/build/compare/v4-check.md`). The package tests `test_an_element_clamped_in_a_grip_is_left_out_of_the_averages_and_the_ends` and the updated averages and ranges tests; the page's tests in `tests/studio-fields.test.ts` and `tests/studio-geometry.test.ts`. The pictures `/mnt/project-files/workspace-design/build/compare/v4-*.png`. No evidence yet from an engineer other than the founder on the jaws.
