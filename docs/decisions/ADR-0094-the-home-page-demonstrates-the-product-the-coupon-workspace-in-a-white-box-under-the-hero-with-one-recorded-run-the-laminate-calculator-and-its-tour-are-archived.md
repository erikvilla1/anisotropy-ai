# ADR-0094: The home page demonstrates the product, the coupon workspace, in a white box under the hero with one recorded run; the laminate calculator and its tour are archived

- Status: Proposed
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
