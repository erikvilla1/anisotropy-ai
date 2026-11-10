# ADR-0083: The laminate view draws carbon plies with a procedural fibre pattern, and takes four props for the scroll tour

- Status: Proposed
- Date: 2026-11-10
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-10 | Drafted by: Claude Code
- Related: [ADR-0004](ADR-0004-sign-and-stacking-conventions.md) (angles and ply order), [ADR-0063](ADR-0063-the-viewer-colours-fields-on-the-graphics-card-from-the-packages-values-and-ranges-unlit-for-results-and-lights-the-model-for-presentation-without-external-assets.md) (the studio's generated lighting), `components/home/laminate-scene.tsx`, `components/home/carbon-material.ts`, `components/home/laminate-studio.tsx`

## Context

The home page's 3D view drew each ply as a flat-coloured slab with stripes along its fibres. The lead: "greatly improve the visuals of the model itself, the plies look super shit and overall looks very low quality. keep accurate with the actual model tho too if you can". A scroll tour, being built at the same time, needs to lay, separate, mark and turn the stack on every animation frame. The work is cosmetic: nothing the engine computes changes. No assets may be downloaded and no packages added.

## Options considered

1. Keep the unlit stripe shader and restyle it. Rejected: it cannot give the sheen that makes carbon read as carbon.
2. Colour, roughness and normal textures drawn on a canvas, on a physical material, rotated for each ply. Not chosen: one texture set per angle, and cut edges would show the same picture as faces.
3. A procedural solid pattern written into three.js's physical material. Chosen: one shared program, the fibres at each ply's real angle on faces and on cut edges, and nothing to download.

Also:
- **Shadow.** drei's `ContactShadows` re-renders the scene every frame. Chosen instead: an analytic shadow, the blurred footprint of the box on a floor plane.
- **Tone mapping.** ACES shifts colours. Chosen instead: neutral tone mapping, so each ply's angle colour matches its swatch in the list beside the view.

## Decision

- **The plies.** Each is a physical material with a pattern that is a function of position across the fibres, through the thickness and along the fibres. Faces show tows and fine fibres at the ply's angle. A cut edge that meets the fibres end-on shows a fine speckle; one the fibres run along shows streaks. The reflection is anisotropic about the fibre direction, under a clearcoat. A bevel in the shader gives the edge highlights, and the geometry stays one shared box.
- **The angle colour** is a thin line along each ply's cut edges and a restrained tint of its reflection. Hovering a ply outlines it in white and dims the others a little.
- **Light and ground.** Nine generated light panels captured once into the environment, a hemisphere light and one key light, over a dithered dark gradient drawn in WebGL. The dust is gone. The axes are thin lines with x, y and z letters, in front of the stack.
- **Slow machines.** A browser that draws in software starts with a plain look: no environment map, clearcoat or anisotropy. While the view turns, a ladder steps down on frame time: pixel ratio 1.5, then 1, then the plain look, then no turning.
- **Four optional props,** all driven through uniforms and object transforms, so nothing is rebuilt:
  - `laid`: how many plies are laid, bottom first; a fractional ply drops into place and fades in.
  - `explode`: 0 to 1, how far the plies stand apart through the thickness.
  - `marked`: a ply to mark, which glows in its colour while the others dim.
  - `azimuth`: the camera's turn in degrees, set by the caller, which turns off the view's own turning and dragging.
- **True to the model:** the number of plies, their order from the bottom up, each ply's fibre angle counterclockwise from x seen from above, their relative thicknesses, and the axes' directions.
- **Illustrative only:** the thickness scale, as the caption says; the tow width and fibre grain; the seams, bevel, gloss and lighting; the coloured edge line; and the plate's outline.

## Why (evidence)

On 2026-11-10, in headless Chromium on the dev server:
- **Screenshots** before and after of 1, 2, 8, 16 and 32 plies, a hovered ply, the workspace's view and a phone, and of each new prop, were looked at.
- **No rebuilds:** over 41 frames with all four props changing each frame, no program, geometry or texture was created and no mesh was remounted (9 programs, 30 geometries and 7 textures before and after).
- **A fix found on the way:** the environment was being re-captured on every render of the view. With the lighting memoized, 12 prop changes cost 13 to 14 render calls a scene, not 323.
- **Turning:** 133 frames in 4 s while turning; none after a drag, or while idle with reduced motion.
- **Software WebGL:** the full look ran at about 3.4 frames a second with timers 3 to 6 s late; the plain look at 23 to 37 a second, measured under heavy machine load.
- **Checks:** `npm run typecheck` clean, also on this commit's tree alone. `home.spec.ts` and `workspace.spec.ts` against the dev server: 11 of 11 before and after.
- **UNVERIFIED:** frame rate and shader compile time of the full look on real graphics cards and phones; the step-down ladder beyond its first step. The full look was only drawn here by software, forced through a temporary hook that is removed.

## Consequences

- Easier: the view reads as a carbon laminate, and the tour can drive it frame by frame.
- Harder: the look lives in shader code inside three.js's material, which a three.js upgrade can break.
- The home page will mount two views once the tour is in, so two WebGL contexts and two shader compiles.
- The workspace's two captions still say "Stripes follow the fibres"; the view now draws tows and fibres.

## How we will know it was wrong

- The view stutters or stalls on a common laptop or phone.
- An engineer reads the grain or the edge line as data.
- A three.js upgrade breaks the injected shader.
