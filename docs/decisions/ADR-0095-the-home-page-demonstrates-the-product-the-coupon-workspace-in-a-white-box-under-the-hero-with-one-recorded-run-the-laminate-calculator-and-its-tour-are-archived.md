# ADR-0095: The home page demonstrates the product, the coupon workspace, in a white box under the hero with one recorded run; the laminate calculator and its tour are archived

- Status: Proposed, with amendments 1 to 8
- Date: 2026-11-13
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-13 (the words are quoted below) | Drafted by: Claude Code
- Related: [ADR-0076](ADR-0076-the-home-page-opens-on-the-hero-and-the-laminate-calculator-follows-it-as-the-demonstration.md) and [ADR-0084](ADR-0084-a-scroll-driven-tour-leads-from-the-hero-into-the-calculator-with-the-engines-own-answers.md), which this supersedes for the home page; [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md) (the live solve the demo does not call); ADR-0001; ADR-0042; ADR-0045; ADR-0091

## Context

Under the hero the home page had the laminate calculator (ADR-0076) and, between the two, a scroll tour that replayed one run of it (ADR-0084). On 2026-11-13 the lead wrote, with a screenshot of the calculator: "i just got word. this is the laminate calculator, its a cool feature (that will probably end up in references), and is NOT THE product (?) (still kinda confused on this but...). So archive these, and instead the demo should be based around THE PRODUCT", with a screenshot of the workspace's coupon page, and "should have the analysis part shown too", with an example image of coloured contour plots beside a load curve. Who gave the word is not stated.

Of the tour's black stage, empty until it filled the window (ADR-0084 amendment 6), the lead wrote: "this is too much black space... maybe lets try a white box which will be same size as the carbon fiber video but underneath it where the demo animation will live".

The public pages could ask the API for a live solve of an example coupon (ADR-0086) or replay a run made beforehand. Asked which, the lead answered: "Yes but why would we need that for a demo, not taking user input."

## Options considered

What the home page demonstrates:

1. **The product: the coupon workspace** (chosen by the lead). Describe a coupon, the model, the analysis, the report.
2. The laminate calculator, as until now. Rejected by the lead: a feature, not the product.

Where the calculator goes:

1. **Off the home page, its code kept, nothing else moved yet** (chosen; the lead: "yeah, we'll figure out what to do with it later"). The full calculator stays at `/calculator` and in the workspace.
2. Moved to the Resources page now. Not chosen: undecided.

Where the demo's analysis comes from:

1. **One recorded run of the repository's own solver on a public example coupon** (chosen). A demo that takes no input always shows the same answer, so nothing is gained by asking for it again on every visit, and the page needs no API to show it. The record can fall behind the solver; it carries the solver's version and its date.
2. A live solve on every visit (ADR-0086). Not chosen, for the reason above; it would also need the hosted API to answer anonymous visitors.
3. A drawing that only looks like a result. Rejected: ADR-0001, every number in a result is the engine's.

Where it stands:

1. **A white box with the clip's width and height, under the clip, on the black page** (the lead's proposal, to be tried).
2. The black stage one window tall (ADR-0084). Rejected by the lead: too much black.

## Decision

- The laminate calculator and its tour are unmounted from the home page. `components/home/laminate-hero.tsx`, `demo-tour.tsx` and their parts stay in the repository, unused; the tour's browser cases and the calculator's cases in `tests/browser/home.spec.ts` are removed with them and are in the history before this change. The tour's rules and clock keep their unit tests.
- "Scroll to explore" scrolls to whatever section follows the hero.
- The demo that replaces them shows the coupon workspace with one recorded run, in a white box under the hero. It is built separately; its record is this ADR's first amendment.
- Only the public example is recorded: nothing from the team's coupons (ADR-0042), no output of commercial software (ADR-0045), and the product's own words on the page (ADR-0091).

## Why (evidence)

- The lead's words above.
- For the archive, on 2026-11-13 against the dev server: `home.spec.ts` (the page's first section is the hero, the calculator and the tour are not on it, the page asks the API for nothing), `intro.spec.ts` (a press on "Scroll to explore" brings the next section to the window), the overview case of `portfolio.spec.ts` and `expansion.spec.ts`: 16 of 16. `npm run typecheck` clean.
- No evidence yet that a white box reads better than the black stage, or that visitors understand the product from the demo: neither has been shown to anyone outside the team.

## Consequences

- Until the demo lands, the hero is followed by the Mission band, and the home page asks the API for nothing.
- ADR-0076's order (hero, then calculator) and ADR-0084's tour no longer describe the home page.
- The calculator's home-page code is unused and will rot if it stays unmounted for long.

## How we will know it was wrong

- The founder or the lead asks for the calculator back on the home page.
- Visitors who see the demo cannot say what the product does.
- The recorded run is found to differ from what the workspace gives for the same coupon.

## Amendment 1, 2026-11-13 (as built)

**Decision.**
- **The box.** `components/home/product-demo.tsx` is the section after the hero: a white box with the clip's width and height, 32 px of black under the clip and under the box (`app/home-demo.css`, the hero's margins). The page scrolls to it as any page does. While the box stands in the window's middle it holds the window, and one scroll gesture plays one whole beat; up from the first beat and down from the last are the browser's, and on the way back up from below the box is passed. The box comes up empty: its parts fade in when the first beat starts. There is no timeline.
- **The driver is the tour's** (`tour-driver.ts`, `tour-stepper.ts`), now told which stops to play, at what speed, and at which line in the window its element holds; a page that comes to rest within 160 px of that line by a link is put on it, which is how the hero's "Scroll to explore" starts the demo. Whether the element is out of sight is read from its own edges.
- **Four beats** (`product-demo-timeline.ts`; 4.4, 3.2, 5.6 and 2.8 s at 0.25 clock units a second):
  1. *Describe the coupon.* The assistant's "Which material?" with the workspace's four material chips and IM7 / 8552 picked, the standard, and the layup typed, the plies coming down as it is typed.
  2. *The model builds itself.* The setup's summary in the workspace's cell names (test, material, layup, size, mesh) and the mesh drawn on the coupon.
  3. *Run the analysis.* The run's five stages from `lib/studio-copy.ts` one after another, then the plies coloured by the stress along the fibres on the workspace's own colour scale, with its legend in MPa, and the first ply to fail as the run's summary gives it.
  4. *It comes with the report.* The first three download names the workspace lists, the About page's sentence on time, and a link to `/workspace/fea`.
- **The centre model** (`product-demo-scene.tsx`) is the coupon, one slab a ply, its thickness enlarged. It moves in one eased move of 1.44 s at the start of a beat: in the middle and leaning back a little with the words under it, then three-quarter at the right with the words at the left, then at the left with its plies apart and the words at the right, then back in the middle. The words of the beat before go as the move starts; the next come in after.
- **The cards are dark on the white box,** in the workspace's shapes, so they read as pieces of the product.
- **The recorded run.** `scripts/demo-run.py` asks the solver, through the command the workspace's live preview runs, for the public IM7 / 8552 tension example under ASTM D3039 (the rows of `tests/fixtures/studio-standards/values.json`) and keeps in `lib/demo-run.json` the mesh, the stress along the fibres in every ply of every element and the summary's numbers, with the version and the date. The demo names it under the analysis: "A recorded run of the public IM7 / 8552 tension example · version 0.1.0 · 2026-11-13". The page asks nothing of the API.
- **Reduced motion and windows under 1024 px:** an ordinary section in the white box, a head, the model at the run's end, and the four beats one under another, finished.

**Options considered.** The words under the model in every beat: rejected, the lead asked for Scale's change of sides. Light cards: rejected, the dark ones are the workspace's own look. Colouring by a failure index: rejected for the first version, a stress in MPa with a legend is what the lead's example showed. The box's hold line at the section's top: rejected, the box is shorter than the window and would hold with all its black below it.

**Evidence.** On 2026-11-13, headless Chromium on the dev server:
- **The recorded run:** `python3 scripts/demo-run.py` printed "359 nodes, 300 elements, 8 plies, stress along the fibres -364.5 to 1201.3 MPa, 25353 bytes"; the solve took 0.008 s. The reaction at the 1 mm pull is 16221.8 N; the first ply to fail is ply 4 (90°), in transverse tension at the edge of a gripped tab, at 1.0191 mm. The setup check called the run "blocked" only because the reference solver is not installed in the container, which the live command does not use.
- **Measured at 1440 by 900:** the box and the clip are both 1376 by 784 px, the box 32 px under the clip; it holds with 58 px of black above and below. With trackpad-like swipes at 1280 by 800 (a wheel event every 16 ms): two swipes moved the page to 353 and 706 px and nothing played, the third stopped it on the line and the first beat played; three more played one beat each; the next two moved the page on to 1,289 and 1,684 px.
- **Looked at:** screenshots of each beat's end, a contact sheet of the recording at two frames a second (the approach, each beat and each move), and the ordinary section on a desktop with reduced motion and on a 390 px phone.
- **Checks:** `npm run typecheck` clean. `npm test`: 255 passed, 1 skipped, 6 of them new in `tests/product-demo.test.ts` (the record whole and consistent, the clock, the poses, every word against the product view's banned terms, the stepper with its own stops). `demo.spec.ts`, 10 cases, with `home.spec.ts` and `intro.spec.ts`: 20 of 20 on the last run. The touch case repeated eight times: 8 of 8. `npm run build`: exit 0.
- **Runs that failed first.** `demo.spec.ts` gave 9 of 10: back at the top of the page the demo did not go back to its start, because the driver judged "out of sight" from the hold line and not from the box's edges; corrected. With the demo mounted, `intro.spec.ts`'s exit case gave 16 where it expected 1 or less: the section was 32 px taller than its box, so "Scroll to explore" left the box 16 px off its line; the black under the box is now a margin and the two coincide. The touch case failed once in the three files together and once in six repeats, with the box 1 px off its line after the finger's scroll: the driver holds to within a pixel and a half, and a finger leaves the page between whole pixels; the case now allows that pixel.

**UNVERIFIED.** A real graphics card (the container draws WebGL in software), a real trackpad, wheel and touch screen, Safari and Firefox. Whether a first-time visitor understands the product from it. The model on a phone is small. The solver's version is the package's, 0.1.0, which does not change with every commit, so the label cannot tell two builds of the same version apart.

**Consequences now.** On the box the wheel, swipes and the scrolling keys are the demo's: 16 s for the four beats (R-27). The recorded run goes out of date when the solver changes (R-28): it is regenerated by the script, by hand. `tour-driver.ts` and `tour-stepper.ts` serve the demo, while `demo-tour.tsx` and `tour-timeline.ts`, which they were written for, are unmounted.

## Amendment 2, 2026-11-13 (the demo stands on black, a window tall; the white box is dropped)

**Context.** Seeing amendment 1 the lead wrote that the demo is great, and: "I dont like the white box idea tho. lets put back on the black background".

**Decision.**
- The demo's ground is black, as the page is, so it has no edge. Its words are white and grey, its cards keep the workspace's dark panels behind a hairline, the coupon's carbon is a little lighter so it reads on black, and the shadow under it becomes a faint pool of light.
- With no box to show, the stage is a window tall, as wide as the hero's clip, and holds the window with its top edge on the window's, so nothing of the hero shows above it while a beat plays. In amendment 1 it had the clip's height and held in the window's middle, which left a strip of the clip at the window's top.
- Nothing else changes: the four beats, the recorded run, the gestures.

**Options considered.** Keeping the clip's height on black and holding in the middle: rejected, the strip of the hero's clip at the top reads as a fault once the box has no edge. A hairline around a black box, to keep the "box under the clip": not chosen, the lead asked for the black ground, not a box.

**Evidence.** On 2026-11-13 against the dev server: screenshots of the four beats at 1440 by 900 and a recording at 1280 by 800 with swipes sent as a trackpad sends them were looked at; no page errors. `npm run typecheck` clean; `demo.spec.ts` (the stage is black, as wide as the clip and a window tall, straight after the hero), `home.spec.ts` and `intro.spec.ts`: 20 of 20. UNVERIFIED, as in amendment 1: a real graphics card, trackpad, wheel and touch screen, Safari and Firefox. The lead's earlier remark that the black stage is "too much black space" while it comes up empty stands against this choice; it was the lead's to make.

## Amendment 3, 2026-11-13 (one more home case of the calculator is removed; CI found it)

**What happened.** The archive removed the calculator's cases from `tests/browser/home.spec.ts` and missed one in `tests/browser/calculator.spec.ts`: "the home page's laminate view asks the real engine for its default stack and shows the engine's description (ADR-0059)". It opens the home page and waits for a request to the API. The home page now asks the API for nothing (`home.spec.ts` checks that), so the case timed out in CI's `calculator-browser` job on the first run after the archive.

**Decision.** The case is removed with the view it tested, as the others were. Nothing replaces it in the browser: the view is not mounted on any page.

**Evidence.** CI run 43491534208, job `calculator-browser`, on `fd462a0`: 1 failed, 8 passed, "page.waitForResponse: Test timeout of 30000ms exceeded" at `calculator.spec.ts:21`. The same failure in a cloud container on a production build. The engine's description of that stack is still tested without a browser: `engine/tests/test_summary.py` and `api/tests/test_laminate_summary.py` (found by search; not run locally, CI's `engine` and `api` jobs passed on the same commit). The calculator's eight other browser cases after the removal: see the pull request.

## Amendment 4, 2026-11-14 (the hero hands over to the demo: it stays and dims while the first beat's words come up through it)

**Context.** The lead, with a recording of the deployed page: "I dont like how when u scroll down its all black. it feels too empty, and like a bulky transition. the animations and movements and demo is good rn tho". In the recording the clip scrolls off the top, the window is black for about a second, and then the first beat's words fade in.

**Options considered.** (1) The hero stays in the window and dims as the page scrolls, the first beat's words come up through it, and the stage starts half a window up so the way to it is half as long: chosen. (2) Keep the layout and only show the first beat's words in the stage as it scrolls in: rejected, the stage's top half, where the model goes, enters the window first and is empty, so the black slab stays. (3) A curtain, the black stage sliding up over a hero that stays: rejected, the same slab. (4) Play the hand-over on the first gesture with no scrolling: rejected, the lead asked on 2026-11-13 that a scroll from the hero should not snap into the first animation.

**Decision.** Where the demo is a stepped stage (a window at least 1024 px wide and 600 px tall, no reduced motion):

- The hero and the demo share a wrapper. The hero is sticky at the window's top and lies over the stage, which starts half a window up behind it; half a window of scrolling brings the stage's top edge onto the window's, where it holds as before.
- `components/home/hero-handover.tsx` writes how far that scroll has gone. The hero's opacity falls with it and is zero when the stage holds, where the hero is hidden altogether. The first beat's words and its empty card come in over the same stretch, while the demo is at its start; the model and the line under it still wait for the first beat.
- The driver learns where the stage counts as out of sight (`hiddenFrom`), so the demo is back at its start when the hero covers it again.
- The demo's beats, clock and moves are not changed. Phones, small windows and reduced motion keep two ordinary sections, one under the other.

This replaces two statements of amendment 2 and of amendment 1: the stage no longer starts straight after the hero, and it no longer comes up empty.

**Evidence.** On 2026-11-14 against the dev server:

- A trackpad-style swipe at 1440 by 810 px was recorded and cut at 8 frames a second: every frame shows the clip, the first beat's words, or both.
- `demo.spec.ts`, `intro.spec.ts` and `home.spec.ts`: 21 of 21. One case is new: on the way to the stage the hero does not move, only dims, the words only come in, and at each tenth of the way one of the two is at more than 0.3 opacity. `shell.spec.ts`, `expansion.spec.ts` and the overview case of `portfolio.spec.ts`: 13 passed, 3 skipped (ADR-0058 amendment 4).
- A run that failed first: with the stage behind the hero the demo did not go back to its start at the top of the page, because the driver read "out of sight" from the window's foot; `hiddenFrom` corrects it and the case passes.
- `npm test`: 299 tests, 298 passed, 1 skipped. `npx tsc --noEmit` clean.

UNVERIFIED: a real trackpad, wheel and graphics card; Safari and Firefox; the deployed site. The hero's place is the browser's own (sticky), and only its opacity is written by script, once a frame.

## Amendment 5, 2026-11-14 (the clip grows to the whole window as the scroll starts)

**Context.** The lead, with a recording of amendment 4 on their own machine: "I like the fade in for the below, but can we also have the hero vid expand to full as it scrolls down, instead of staying around a black box".

**Options considered.** (1) The clip's box grows: its edges move out to the window's as the scroll starts, and the picture with them: chosen. (2) Lay the clip out whole-window from the start and uncover its edges with a clip path: not chosen, it would change how the clip is cropped while the page is at its top. (3) Move the hero's words and corner items out with the edges too: not chosen; the words have usually left by then, and the mark and "Scroll to explore" stand 64 px inside the window, an ordinary margin for a whole-window picture.

**Decision.** Over the first half of the way to the stage the clip's box grows from its place under the header (84 px from the top, 32 px from the sides and the foot at 1440 px) to the whole window, eased (`--hero-grow`, written by `components/home/hero-handover.tsx`). It is whole-window while it dims. On the way back up it returns to its box. Nothing else of amendment 4 changes.

**Evidence.** On 2026-11-14 against the dev server: stills at nine points of the scroll and a recorded trackpad-style swipe at 1440 by 810 px were looked at. The hand-over case of `demo.spec.ts` now also checks that the clip's four edges only move outward, reach the window's by half way and are back in the box at the top; `demo.spec.ts`, `intro.spec.ts` and `home.spec.ts`: 21 of 21. `npx tsc --noEmit` clean. UNVERIFIED, as in amendment 4: a real trackpad, wheel and graphics card; Safari and Firefox; whether resizing the clip's box on every frame stays smooth on a slow machine (it lays out one element).

## Amendment 6, 2026-11-14 (the hand-over in order: the clip grows, then dims, then the words come; the button goes; the recorded line is taken out)

**Context.** The lead, on amendments 4 and 5 running on their machine, with screenshots: "wait until the hero vid becomes full screen to fade to black and have the other stuff fade in when it fades more black"; "the 'scroll to explore' button should also be fading out"; and, of the line under the analysis ("A recorded run of the public IM7 / 8552 tension example · version 0.1.0 · 2026-11-13"), "dont need this".

**Decision.**

- The hand-over runs in order over the same half window of scrolling: the clip grows to the whole window over the first 40 % at full strength; only then does it dim, to nothing when the stage holds; the first beat's words come in between 60 % and 90 %, when the clip is at less than 0.6 of its strength.
- "Scroll to explore" fades as the clip grows and is gone when the clip is whole-window.
- The line under the analysis is removed from the page. The record (`lib/demo-run.json`) still says what it is, by which version and when, and a unit test reads that. The page therefore shows the analysis's numbers without saying they are a recorded example: the lead's choice, for the founder to weigh with the pull request.

**Evidence.** On 2026-11-14 against the dev server: stills at nine points of a wheel scroll were looked at. The hand-over case of `demo.spec.ts` now scrolls by the wheel in tenths and checks the order (growing at full strength with no words; the button gone by 40 %; the words only once the clip is under 0.6). `demo.spec.ts`, `intro.spec.ts`, `home.spec.ts`, `shell.spec.ts`, `expansion.spec.ts` and the overview case of `portfolio.spec.ts`: 34 passed, 3 skipped (ADR-0058 amendment 4). `npm test`: 299 tests, 298 passed, 1 skipped. A run that failed first: the case for the way to the box still expected the words after the first wheel notch, which is now while the clip grows; it expects none there. UNVERIFIED, as before: a real trackpad, Safari, Firefox.

## Amendment 7, 2026-11-14 (a hard stop on the stage, and the demo plays once)

**Context.** The lead, with a screenshot of the first beat and a white strip of the next section at the window's foot: "when I scroll down shouldnt have that clipping thing going on when I can pull up into the white zone, should approach a hard stop." And, with a recording of the demo starting again after it had been played, left and come back to: "once the demo animation runthru is complete and u scroll down and then back up, dont retrigger any animations, just back to the home screen."

**What was wrong.** The scroll that brings the page to the stage is the browser's own, so the browser does not let a script cancel what is left of it, a trackpad's coasting above all. The page was scrolled past the stage and put back frame by frame. On a black page that did not show; since ADR-0077 amendment 33 the next section is white.

**Options considered.** (1) End the page at the stage until the demo has played through, so the browser itself has nowhere to scroll: chosen. (2) Only undo the scroll faster, or lock the page once it has been stopped: rejected alone, the first frames past the stage are drawn before any script runs. (3) Take the wheel over from the hero down and move the page by script: rejected, a wheel's own smooth step would be lost on the way. (4) CSS scroll snapping with a forced stop: not chosen, it also pulls a resting page to the stage, which the lead ruled out on 2026-11-13, and its forced stop could not be tried in Safari or Firefox here.

**Decision.**

- **The gate.** Where the demo is a stepped stage, until it has played through, everything after it (the bands, the closing band, the footer) is taken out of the page's height, as visually hidden text is, so the page ends with the stage on the window. It stays in the page for a screen reader and the keyboard. The gate opens for good when the last beat ends, and at once when focus moves past the demo, when a link names a section below it, or when the page is already scrolled past the stage as its script starts.
- **The lock.** While a beat plays on a held stage, and for a moment after the page has been stopped on it, the page's overflow is hidden, so no scroll that was already on its way moves it; the scroll bar's room is kept as padding.
- **Once.** When the last beat has ended the stage is an ordinary section for the rest of the visit: no gesture is taken, the page is never stopped on it again, and it keeps its last beat. A reload starts over.

**Consequences.** Until the demo has played through, the scroll bar and the End key reach no further than the stage; this is stated in R-27. A visitor who wants what is below has four gestures to make, or the keyboard's Tab.

**Evidence.** On 2026-11-14 against the dev server:

- One long synthesized wheel gesture from the hero (1600 px at 2400 px a second): before, the page's scroll position reached 676 to 699 px for a stage at 450; with the gate it never passes 450.
- `demo.spec.ts`, `home.spec.ts`, `intro.spec.ts`, `shell.spec.ts`, `expansion.spec.ts` and the overview case of `portfolio.spec.ts`: 35 passed, 3 skipped (ADR-0058 amendment 4). The cases now check that the page ends at the stage until the last beat, that the next band follows the stage once it has, that a swipe after the end is not taken, and that going down, back to the hero and down again plays nothing.
- A run that failed first: reserving the scroll bar's room with `scrollbar-gutter` moved the layout 15 px in the test browser, whose bars take no room; the room is now measured when the lock goes on.
- `npm test`: 300 tests, 299 passed, 1 skipped. `npx tsc --noEmit` clean.

UNVERIFIED: a real trackpad's coasting, which the synthesized gesture only stands for; Safari and Firefox; a phone's fling, which keeps its earlier handling.

## Amendment 8, 2026-11-14 (once the demo has played, the hero is an ordinary section above it)

**Context.** The lead, with a recording of scrolling up from the finished demo: "when it finishes and scrolling up, dont do the whole re-fade transition back to hero. just have it be directly block above it."

**Decision.** When the last beat ends the hand-over of amendments 4 to 6 is switched off for the rest of the visit (`data-played` on the two sections' wrapper): the hero is no longer sticky, dimmed or grown, and the stage no longer starts behind it. The hero stands whole, straight above the stage, and scrolling up brings it down as any section. Taking the overlap away moves the stage half a window down the page; the page is scrolled by the same amount in the same frame, so the stage does not move in the window. On the first way down the hand-over is as before.

**Evidence.** On 2026-11-14 against the dev server: `demo.spec.ts`, `home.spec.ts` and `intro.spec.ts`, 22 of 22. The play-once case now checks that at the end the stage is still on the window's top edge with the hero's foot on it, that the hero is in the page's flow at full strength, and that 300 px up from there the hero's foot is 300 px into the window with its clip in its box and nothing fading. `npx tsc --noEmit` clean. UNVERIFIED: a real trackpad; Safari and Firefox.

