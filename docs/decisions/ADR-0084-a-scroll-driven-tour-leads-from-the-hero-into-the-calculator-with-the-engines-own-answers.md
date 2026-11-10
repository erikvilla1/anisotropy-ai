# ADR-0084: A scroll-driven tour leads from the hero into the calculator, with the engine's own answers

- Status: Proposed
- Date: 2026-11-10
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-09 and 2026-11-10 | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md) (the engine computes every number), [ADR-0059](ADR-0059-the-engine-describes-the-stack-and-evaluates-first-ply-failure-on-the-response-endpoint-for-the-home-calculator.md) (the home calculator's endpoint), [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the hero and the demo), [ADR-0083](ADR-0083-the-laminate-view-draws-carbon-plies-with-a-procedural-fibre-pattern-and-takes-four-props-for-the-scroll-tour.md) (the 3D view's props), `components/home/demo-tour.tsx`, `components/home/tour-timeline.ts`, `components/home/tour-bridge.ts`, `components/home/engine-answers.tsx`, `app/home-tour.css`, `tests/browser/tour.spec.ts`, `tests/tour-timeline.test.ts`

## Context

The lead asked for a "Scroll to explore" button after scale.com's, and for the scroll to take a visitor through the demo: "have the first scroll for example be an animation of numbers being input into the calculator from the material library then the model/engine running and etc... run the demo thru from start to finish with a few scrolls to progress it", with a transition "from the carbon fiber video background to the plies". Afterwards the scroll should "take it back to the next section like normal". The work is cosmetic: nothing in the engine changes.

The lead's recording of scale.com, read at 15 frames a second, shows:
1. The hero video in a card shrinks as the page scrolls, and the ground turns black.
2. The card turns in perspective and becomes one layer of a stack of outlined layers.
3. The stack stays pinned while short blocks of text step in beside it.

The home page went from the hero straight to the calculator. The engine computes every number in a result (ADR-0001), and a browser test asserts exactly one request to the engine after the page loads.

## Options considered

1. A recorded video of the demo. Rejected: its numbers would be a recording, not the engine's answer for the stack on screen.
2. Scroll hijacking or snapping. Rejected: it takes the scroll from the visitor, and the lead asked for ordinary scrolling after the tour.
3. A scroll animation library. Rejected: a new package for what one sticky element and one scroll reading do.
4. A sticky stage inside a tall wrapper, with the scroll position read once per animation frame. Chosen.

For the bridge from the clip to the plies:
- a second copy of the clip inside the stage: two decoders for one picture;
- cross-fading the 3D canvas in over the clip: in headless software rendering this gave one frame of 1.4 to 2.8 s when the canvas first showed;
- moving the hero's own clip with one transform onto the stack, which already stands behind it. Chosen: the worst frame in the same sweep was 233 ms.

For the numbers:
- the tour asks the engine itself on load: a second request on every visit;
- a shared store of answers that the calculator fills, with the tour asking only for the loaded case when its step is reached. Chosen.

## Decision

- **Scroll to explore.** A button at the hero's bottom right scrolls to the tour's first step. Nothing else ever sets the scroll position.
- **The stage.** `#tour` is a tall `<div>` that starts at the hero's top; inside it one viewport-tall stage is `position: sticky`. A clock, scroll into the tour in viewport heights, drives everything (`tour-timeline.ts`). The tour is about five screens long. When the last step ends the stage unpins, and ordinary scrolling carries on to the white calculator and then Mission.
- **The bridge (0 to 1 screen).** The hero's words fade. The hero's own clip, or the still where the clip is absent, shrinks to a card, lies back onto the top ply of the 3D stack and fades off, and the plies separate. The clip is moved by one `matrix3d` and a clip path, whose landing points are the top ply's corners projected with the scene's camera (`tour-bridge.ts`).
- **The five steps,** each a monospace label, a heading and one sentence beside the pinned stack and a compact panel:
  1. Material: IM7/8552 is picked and its cited constants type in.
  2. Layup: `[45/-45/0/90]s` types in and the plies are laid one by one.
  3. Engine: the request is shown, then the engine's description and its A, B and D matrices.
  4. Loads: Nx = 25 kN/m types in, first-ply failure appears, and the failing ply is marked in the 3D view.
  5. Your turn: the stage hands over to the live calculator, which shows the same stack.
- **The panels are the calculator's own components** (`PropertyRow`, `StackList`, `SpecsList`, `AbdGrid`, `FailurePanel`), so the tour cannot drift from the calculator.
- **Honest numbers.** `engine-answers.tsx` is a small store keyed by the request. The calculator reports its request and answer to it; the tour shows that answer for the default stack. The tour asks for the loaded case itself, once, when the visitor reaches that step. Nothing is recorded, hard-coded or read from test fixtures. Without an engine the tour shows the material, the layup and the plies, and says plainly that the numbers need the engine.
- **When it is not pinned.** With reduced motion, or in a window under 1024 px wide or 600 px high, the tour is an ordinary stacked section with every step shown and the hero untouched.
- **The 3D view is mounted late:** when the browser is idle 2.5 s after the tour mounts, or at the first scroll, so the page's load is not held up by a second WebGL view.
- **Tests.** The tour renders the calculator's panels a second time, so the calculator's browser tests now look inside `#laminate` (nine look-ups in `home.spec.ts`; no expected value changed). The tour's tests look inside `#tour`.

## Why (evidence)

On 2026-11-10, in headless Chromium on the dev server:
- **Contact sheets** of the scroll at 1440 by 900 and 1860 by 1000, down and back up, with the clip and with the still, were looked at: the bridge, each step, the hand-over and the reverse.
- **Load,** medians on a quiet machine at 1440 by 900: 2,339 ms from load to idle with the tour, against 2,269 ms without it. A click from the home page to About took 475 ms, against 463 ms.
- **Requests:** one before the loads step and two after it. With the engine's address emptied the page sent none.
- **Checks:** `npm run typecheck` clean. `npm test`: 205 passed, 1 skipped, including 7 unit tests of the clock and the bridge's transform. `home.spec.ts`, `tour.spec.ts` and `intro.spec.ts`: 20 of 20.
- **Flaky once:** one earlier run failed a load-in test, with the veil at opacity 0.998 where 1 was expected; it passed in every later run.
- **UNVERIFIED:** smoothness on a real graphics card (headless Chromium draws in software, and shows the view's plainer look); Safari and Firefox; phones beyond "nothing overflows at 390 px"; screen readers.

## Consequences

- Easier: a visitor sees one real calculation from start to finish without touching anything.
- Harder: the home page is about five screens longer before the calculator.
- The bridge repeats the 3D view's camera and stack constants, and the stage's ground copies the view's backdrop by hand. A change to either must be made in both places.
- The bridge depends on CSS `:has()`. A browser without it shows the tour without the bridge.
- The page mounts two WebGL views once the tour's view has loaded.

## How we will know it was wrong

- The bridge or the steps stutter on a common laptop.
- Visitors stop scrolling before the calculator.
- A number in the tour differs from the calculator's for the same stack.
