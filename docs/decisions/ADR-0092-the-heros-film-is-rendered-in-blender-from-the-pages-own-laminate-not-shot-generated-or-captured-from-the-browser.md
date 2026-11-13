# ADR-0092: The hero's film is rendered in Blender from the page's own laminate, not shot, generated or captured from the browser

- Status: Proposed; the script exists, the film is not on the site yet
- Date: 2026-11-13
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-13 ("I like that"; "sure lets do it") | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the hero), [ADR-0084](ADR-0084-a-scroll-driven-tour-leads-from-the-hero-into-the-calculator-with-the-engines-own-answers.md) (the scroll tour), [ADR-0069](ADR-0069-the-licensed-hero-clip-stays-out-of-the-public-repository-a-script-makes-its-web-copy-and-the-page-plays-it-when-present.md) (the stock clip it would replace), [ADR-0001](ADR-0001-deterministic-engine.md) (the engine computes every number), `scripts/hero-plate.py`, `tests/fixtures/home/response-im7-quasi-loaded.json`

## Context

The lead found the hero unclear: "its just a video of carbon fiber", "no visual of how it works", and a hand-over to the scroll tour that plays the clip on a ply. PhysicsX and Scale show the customer's object with the product's answer over it. The lead agreed to one object from the hero to the calculator, the laminate plate, and asked how to make its footage "right now, super good quality".

## Options considered

1. Record the page's own 3D view in the browser. Not chosen: it looks like a web graphic, and this container draws it in software.
2. AI-generated video. Rejected: it invents the plies, the angles and the result, and the site shows only what the engine computes (ADR-0001).
3. Film a coupon test and draw the prediction over it. Deferred: it needs lab footage, a matching run and the team's approval to publish the test data.
4. A path-traced render in Blender, built by a script from the stack. Chosen: it is free, scripted, and shows our own stack.

## Decision

Option 4. `scripts/hero-plate.py` builds and renders the film with Blender's Cycles.

- **The plate** is the home page's stack, IM7/8552 [45/-45/0/90]s: eight unidirectional carbon plies, bottom face up, each with its fibres at its angle. The plies are drawn about seven times thicker than true scale so the layers read.
- **The loop,** 12 s: the solid plate; the plies fan apart towards the camera; arrows for Nx go on at both x ends of every ply; ply 4 (+90°) glows amber; everything returns to the start, so the loop has no jump.
- **Ply 4 is the engine's answer** for this stack under Nx: first-ply failure by maximum stress, ply 4 (+90°), transverse tension (`tests/fixtures/home/response-im7-quasi-loaded.json`, the answer the scroll tour shows live). The film shows which ply and no number.
- **The script renders frames,** not a video, and skips frames that exist, so an interrupted render carries on. It uses the graphics chip when Cycles finds one.

## Why (evidence)

- On 2026-11-13, with Blender 5.0.1 (`bpy`) on this container's four processor cores: six key frames at 768 by 432 and 48 samples rendered in 72 s; a 144-frame preview at 576 by 324 and 24 samples rendered and encoded without error. A contact sheet of the preview shows the five moments in order and the last frame matching the first. The lead was sent the preview.
- The automatic device choice was run here with no graphics chip and fell back to the processor.
- No evidence yet: the film at full size, the render on the lead's Mac, and the Metal path of the device choice.

## Consequences

- Easier: the hero can show what the product does with our own picture, and the stock clip and its licence risk (R-26) can leave the repository once the film replaces it.
- Harder: a full render is hours of processor time, or needs a machine with a graphics chip. The plate's angles and the failing ply are written in the script and must follow the page's stack if it changes.
- The hero's shades and its greyscale filter were tuned for the stock clip and must be set again for the film; the tour's hand-over (ADR-0084) is to be replaced.

## How we will know it was wrong

- The lead or a visitor reads the amber ply as a claim the engine does not make for this stack.
- The render does not reach the quality of the references at full size.
- The team films a real coupon test and prefers it.
