# ADR-0084: A scroll-driven tour leads from the hero into the calculator, with the engine's own answers

- Status: Proposed; amendment 4 removes the bridge and plays one whole step per scroll gesture, which replaces the scroll-driven clock and amendments 1 to 3; amendment 5 lets the page scroll to the stage by itself and slows the steps
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
- **Flaky once:** one earlier run failed a load-in test, with the veil at opacity 0.998 where 1 was expected. ADR-0070 amendment 2 removed that race.
- **Against the built site,** the same day: the whole browser suite, 74 passed and 1 skipped (the live-studio test, which needs the hosted site). One calculator test had counted every request to the engine; reaching the calculator now scrolls through the tour, which may ask for its loaded case on the way, so that test counts the calculator's own requests.
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

## Amendment 1, 2026-11-13 (the bridge starts from the hero's round box)

**Context.** The hero's clip now plays in a box with round corners on a black page (ADR-0077 amendment 17). The bridge assumed the clip filled the window and had square corners.

**Decision.**
- The bridge measures the box's place inside the hero and its corner radius, and carries the clip from there. The corners go from the box's radius to the card's 14 px, and are square when the card is a ply.
- The hero's black ground is a layer of its own. It fades in the first 0.12 screens of scroll, so what the shrinking clip uncovers is the stage; at rest it is opaque, so nothing of the stage shows in the frame around the box.

**Evidence.** `tests/tour-timeline.test.ts` has a case for a box at (32, 64) with 20 px corners: at rest the transform leaves it in place and the clip path draws its corners; landed, the kept part's corner is on the ply's corner within 0.01 px. `tour.spec.ts` reads the box's radius and the ground's opacity at rest, in the bridge and back at the top. Both passed on 2026-11-13 (ADR-0077 amendment 17 has the runs).

## Amendment 2, 2026-11-13 (the bridge starts from the whole window again)

**Context.** The lead took the hero's round box back (ADR-0077 amendment 18).

**Decision.** Amendment 1 is undone in the code: the bridge measures the hero as the whole window, the corners start square, and the hero's ground is no longer a layer the tour fades. Its unit case and its lines in `tour.spec.ts` are removed.

**Evidence.** ADR-0077 amendment 18 has the runs: `tour.spec.ts` passed in the 26 of 26, and `tests/tour-timeline.test.ts` in the 247.

## Amendment 3, 2026-11-13 (the bridge starts from the hero's box again, with square corners)

**Context.** The hero's clip plays in a box again, in Anduril's arrangement (ADR-0077 amendment 19).

**Decision.** Amendment 1's code returns: the bridge measures the box's place and corner radius, which is now 0, and the hero's black ground fades first. Its unit case and its lines in `tour.spec.ts` return, reading a radius of 0 on the page.

**Evidence.** ADR-0077 amendment 19 has the runs; `tour.spec.ts` passed in them, and a screenshot of the hand-over at three moments shows the box shrinking into the card and landing on the top ply.

## Amendment 4, 2026-11-13 (no bridge; one scroll gesture plays one whole step)

**Context.** With a screenshot of the hero's clip lying on the top ply, the lead asked: "lets get rid of this transition. I still like the idea of the scroll interactive demo so keep that, but make sure that each scroll fulfills the entire sequence step animation, ie one scroll does the animation from one to two, the next to three. all fluid and constant speed. instead of having the scroll literally move the animation along manually, I dont want that." This takes back option 2 of this record (no taking of the scroll) for the tour, at the lead's request.

**Decision.**
- **The bridge is removed:** `tour-bridge.ts`, its styles and its tests. The hero is an ordinary section that scrolls away, and the tour writes nothing on it.
- **The stage** is one window tall in the page's flow under the hero, in place of a sticky stage in a wrapper six windows tall. The page is about four screens shorter.
- **The clock no longer follows the scroll** (`tour-timeline.ts`). It has six stops: 0 before the first step, then the end of each step. A gesture plays it from one stop to the next at one speed, 0.6 units a second, linear, forwards and back: 1.0, 1.8, 1.3, 1.5 and 0.75 s for the five steps. The next step's words come up as its move starts, and each stop shows its step complete.
- **A gesture** is a wheel gesture, a swipe, or ArrowDown, ArrowUp, PageDown, PageUp, Space or Shift+Space outside a field (`tour-stepper.ts` decides, `tour-driver.ts` listens and plays). While the stage's top edge is on the window's, down plays the next step and up the one before, and the page does not scroll. While a step plays, and for the rest of the wheel gesture that played it, input is taken and nothing happens. Wheel events less than 200 ms apart in one direction are one gesture; a new one begins after a pause, on a change of direction, or with an event of 50 px or more that is not smaller than the one before (a wheel still being turned), the last not within 300 ms of a move.
- **The ends.** On the hero, with the stage touching the window from below, a gesture down carries the page onto the stage at two window heights a second, linear, and the first step plays. Up from the first step carries the page back to the hero, and the tour starts over. Down from the last step is the browser's, so the page scrolls on to the calculator. Up from there, while the stage touches the window, carries the stage back in at its last step.
- **The scroll bar, links and restored positions** move the page and not the clock, so the tour is never between two steps. Wholly below the window it goes to its start; wholly above, to its end. If the page comes to rest on the stage before the first step has played, it plays. A scroll from elsewhere while a step plays on the stage is undone.
- **Unchanged:** with reduced motion, or under 1024 px wide or 600 px high, every step is shown and no gesture is taken. The loaded case is asked for 0.4 s after its load is typed, while at least half the stage is in the window. The engine's numbers and the shared answers are as before.
- **A finger on the 3D view.** The view's controls write `touch-action: none` on their box. The stepped tour sets it to `pan-y`, so a swipe on the view at the last step scrolls the page on.

**Options considered.**
1. Keep the tall wrapper and animate the scroll position between the steps' offsets. Rejected: the scroll would still be the clock, so the scroll bar or a touch fling would move the animation along by hand, which the lead asked not to have.
2. CSS scroll snapping. Rejected: it places the page but cannot play a timed move at constant speed or ignore input while one plays.
3. One duration for every step. Rejected: the steps hold different amounts (the layup types 14 characters and lays 8 plies), so one duration makes some hurry; one speed keeps the same pace in all of them.
4. A stage one window tall with its own clock, taking a gesture only on the stage or towards a stage that touches the window. Chosen.

**Evidence.** On 2026-11-13, headless Chromium on the dev server:
- **One notch, a burst, notches during a step** (1440 by 900, real wheel events): one notch on the hero had the stage in the window and the first step done 1,636 ms later; 45 wheel events in a row played one step; three notches within half a second played one; at the last stop a notch scrolled the page 100 px on; a notch up from 400 px below carried the stage back; five more went back a step each and then to the hero. One request to the engine before the loads step and two after; no page errors.
- **Swipes with coasting,** made in the page from a 16 ms timer (the busy page delivered 11 to 71 events a swipe), coasting 1.2 to 2.4 s: each of six played exactly one step and every event was taken; four of the six coasted on after their step had ended.
- **Touch and keys:** swipes sent as touch events through the browser's debugging protocol played one step each, on the words and on the 3D view, and back; at the last stop a drag on the view moved the page from 800 to 1,164 px (before the `touch-action` rule it did not move). The six keys stepped both ways, and up from the first step went to the hero.
- **Looked at:** contact sheets of a recording at 1280 by 800, one notch a step: the hero scrolling away, the stage arriving, and each of the five steps to its end.
- **Checks:** `npm run typecheck` clean. `npm test`: 248 passed, 1 skipped, with 8 cases on the clock and the rules in `tests/tour-timeline.test.ts`. `tour.spec.ts`, 12 cases, run twice over: 24 of 24. `home.spec.ts` and `intro.spec.ts`: 14 of 14.
- **Run again before the commit,** by the session that reviewed the change: `npm run typecheck` clean; `npm test` 248 passed, 1 skipped; the three files together 26 of 26; `expansion.spec.ts` and the overview case of `portfolio.spec.ts` 7 of 7. The risk is R-27 in the register.
- **Runs that failed first.** The three files together gave 25 of 26: the tour's own new case sent a swipe one wheel event per call, the busy machine spread them more than 200 ms apart, and two steps played; the case now sends the swipe in one go. `home.spec.ts` "typing a layup" failed in one run and in one of three runs alone; it depends on the calculator's typing delay and has failed this way in this container before this change.

**UNVERIFIED.** Smoothness on a real graphics card: here the 3D view draws in software, frames took 67 ms while a step played and up to 250 ms while the stage was carried in. A real trackpad and a real wheel: the swipes were made by script. Safari and Firefox, whose wheel reports lines, which the code converts but no test ran. A real touch screen, and a tablet held wide, where the tour is stepped and the stage is `100vh` tall under the browser's bars. Screen readers. A visitor who scrolls within 2.5 s of the load, when the 3D view is mounted during the carry.

**Consequences now.**
- No longer true: the page is five screens longer; the bridge repeats the view's camera constants; the bridge depends on `:has()`.
- New: on the stage the wheel, swipes and the scrolling keys are the tour's. A visitor cannot pass it faster than its steps play, 6.4 s for the five, except by the scroll bar, a link, Home or End.
- Still true: the stage's ground copies the view's backdrop by hand, and the page mounts two WebGL views.

**How we will know it was wrong.** A swipe plays two steps or none on some device. Visitors leave at the tour because it holds the page.

## Amendment 5, 2026-11-13 (the page scrolls to the stage by itself; slower steps; the way back up is free)

**Context.** With a recording of amendment 4 and a screenshot of the stage filling the window, the lead asked: "dont snap into the first animation by a scroll from the main paige; start it once the scroll reaches the screenshot position. also the animations are way too fast." In the recording one scroll on the hero carried the page a whole window in half a second, and the first step then played in one second.

**Decision.**
- **Nothing carries the page.** From the hero it scrolls as any page does, by what each wheel event, key or finger asks for, and it may rest part of the way. The first step plays once the stage's top edge is on the window's. Two things put it there: the wheel event or key that asks for at least what is left is stopped on the stage (`decide` returns `arrive`; a gap over 24 px is closed at two window heights a second, at least 150 ms), and a scroll made by a wheel, key or finger in the last 600 ms that brings the edge onto or across the window's is put back on it (`crossed`). What is left of that gesture begins no step.
- **Up from the first step** the stage lets go and the page scrolls up; there is no carry back to the hero. While part of the stage shows, it keeps its first step; out of sight below the window the tour is at its start again, as before.
- **On the way back up from the calculator the stage is passed like any section,** showing its last step. Amendment 4 stopped the page on it there, which, with the slower steps, would make a visitor going back to the top watch all five steps backwards. A stage met again from above holds the window at the step it shows.
- **The clock's speed is 0.25 units a second** in place of 0.6: the five steps take 2.4, 4.4, 3.2, 3.6 and 1.8 s (15.4 s in all), and the layup's 14 characters are typed in about 2 s.

**Options considered.** Keep the carry and slow it: rejected, the lead asked for no snap. Stop the page on the stage from below as well: rejected for the reason above; it is the drafter's choice, not asked for by the lead. One second longer per step in place of one slower speed: rejected, amendment 4's reason for one speed stands.

**Evidence.** On 2026-11-13, headless Chromium on the dev server:
- **Swipes sent as a trackpad sends them** (a wheel event every 16 ms, 1280 by 800, hero 800 px): the first two moved the page to 353 and 706 px and nothing played; the third stopped it at 800 px, the stage's place, and the first step played in 2.4 s; four more played one step each in 4.1, 2.7, 3.3 and 1.7 s; the next moved the page on to 1,259 px; two swipes up moved it to 583 px and to 0 with the tour at its last step and then at its start. Contact sheets of that recording were looked at.
- **Checks:** `npm run typecheck` clean. `npm test`: 249 passed, 1 skipped, with 9 cases on the clock and the rules. `tour.spec.ts`, 13 cases, among them the page keeping to the wheel notch by notch down the hero, the first step's length, the free way back up and a finger's scroll stopped on the stage: 13 of 13 on the first run. `home.spec.ts` and `intro.spec.ts`: 14 of 14.

**UNVERIFIED.** As in amendment 4: a real trackpad, wheel and touch screen, a real graphics card, Safari and Firefox. Also: a browser that animates a wheel notch's scroll may run a few pixels past the stage before it is put back; headless Chromium does not animate it, so this was not seen.

**Consequences now.** A visitor on the stage cannot pass it faster than its steps play, 15.4 s for the five, except by the scroll bar, a link, Home or End (R-27, updated). `tour.spec.ts` takes about four minutes.

## Amendment 6, 2026-11-13 (nothing of the stage shows until its first step; no timeline at its foot)

**Context.** With a screenshot of the stage coming up under the hero, its first step's words, panel and stack already drawn, the lead asked to "have it animate it only when it hits the bottom, like shouldnt be visible here", and of the five ticks along the stage's foot, "we dont need the timeline things on the bottom either".

**Decision.**
- **Until its first step starts, the stage is empty.** While the tour stands at its start and nothing plays, the stage's parts and the light on its ground are not drawn; when the stage fills the window and the first step begins they fade in over 0.9 s. Back at its start, out of sight, they are gone again. Met from below, at its last step, the stage shows as before.
- **The ticks are removed,** with their styles and the per-frame values that filled them.

This is the first part of a larger change the lead asked for in the same message, the tour modelled on Scale's home page and on the workspace; that part is not in this amendment.

**Evidence.** On 2026-11-13 on the dev server at 1440 by 900: with the page 650 px down the hero, every pixel of the stage's part of the window reads 0; a screenshot after the first step shows the stage without the ticks. `tour.spec.ts`: the stage's head, view and steps read opacity 0 at the start and 1 after the first step, and no tick list exists; the four cases that cover the start, the first step and the way back: 4 of 4. `npm run typecheck` clean.

**Two faults found on the way, both from amendment 5.**
- **A finger's throw could carry the page off the stage after the first step.** In the whole file the touch case failed 1 run in 3, and 4 in 6 under load, with the stage resting 30 or 114 px above the window's top after its first step: the page was still coasting on the swipe that had brought the stage in, and nothing held it once the step had ended. For 3 s after a finger has brought the stage in, a scroll that takes it off the window's top again is undone, unless a new gesture has let the stage go; and while a step plays the hold is checked on every frame. The touch case repeated six times after the change: 6 of 6.
- **The test of a step's length measured its own pace:** it timed the first step from the test's side and read 1.0 to 1.5 s for a 2.4 s step when the machine was busy. It now has the page note when the second step starts and ends: 4 of 4 repeated, between 4.2 and 5.6 s for a 4.4 s step.

`tour.spec.ts`, `home.spec.ts` and `intro.spec.ts` after both, run together: 27 of 27.

