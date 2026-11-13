# ADR-0095: The home page demonstrates the product, the coupon workspace, in a white box under the hero with one recorded run; the laminate calculator and its tour are archived

- Status: Proposed, with amendments 1 to 3
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

