# ADR-0076: The home page opens on the hero, and the laminate calculator follows it as the demonstration

- Status: Proposed; reverses items 4 and 5 of the CEO's website audit of 2026-10-31 (built under ADR-0058) until the CEO confirms; superseded for the home page by ADR-0095 on 2026-11-13 (the calculator is archived)
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0058](ADR-0058-one-name-anisotropy-five-service-pages-under-a-services-menu-the-calculator-on-the-home-page-and-a-contact-page.md) (the home page as built), the CEO's website audit of 2026-10-31, revised 2026-11-01 (kept outside the repository), `app/page.tsx`, `tests/browser/home.spec.ts`
- Area: website

## Context

The UI/UX lead started a redesign of the website's look and brand on 2026-11-07, with the PhysicsX and Cursor home pages as references. The first step asked for: "swap the second page, which is the hero page, to the first, and then put the demo below it."

The home page built under ADR-0058 shows the laminate calculator first, then the hero ("From material to understanding." with the chat block), then the blurbs. The audit asked for that order. Item 4: "the Home page will now show the Calculator up front, as a visual hook". Item 5: the hero "will appear right under the 3D laminate". Item 7 names PhysicsX's home page as the structure to follow: "a cool graphic up front", then short blurbs.

The page's only `h1` is in the hero; the calculator's title is an `h2`, so that order put an `h2` before the `h1`. The 3D scene pauses its animation when off screen but still renders (`components/home/laminate-scene.tsx`), and the calculator asks the engine for its numbers when it loads, wherever it sits.

## Options considered

1. Keep the calculator first, as audit items 4 and 5 ask. Rejected by the UI/UX lead for the redesign.
2. The hero first, the calculator directly under it, everything else unchanged. Chosen.
3. Merge the two: the 3D laminate as the hero's picture, with the headline and the chat over it. Not built now: it redesigns both sections, which is the next chunk of the redesign. It may answer audit item 4's "graphic up front" and this record's request together.

## Decision

Option 2. `app/page.tsx` renders the hero (`#overview`) first and the calculator (`#laminate`) after it. The principles strip, the five blurbs and the news follow as before. The hero's "Scroll to discover" link points to `#laminate` instead of `#mission`. No style, copy or component changes.

## Why (evidence)

- The UI/UX lead's request of 2026-11-07, quoted above, and a screenshot of the PhysicsX hero shared the same day (kept outside the repository). It opens on a full-bleed picture with the headline "Engineering. Reengineered."
- cursor.com, loaded on 2026-11-07 at 1440 by 900: the `h1` "Cursor is your coding agent for building ambitious software." and two buttons, then a framed product window, the demonstration, starting about 350 px from the top; then customer logos and feature sections.
- www.physicsx.ai, loaded the same day: the `h1` "Engineering. Reengineered.", then the `h2`s "Build beyond", "Platform", "More than faster simulation.", "Impact", "About us", "Careers", "Customer story", "What's New" and "Talk to an engineer". Its images come from a host this session could not reach, so the shared screenshot is the visual evidence.
- Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped. Against the built site, `home.spec.ts` 6 passed, including the new order test. `portfolio`, `research` and `expansion` had 3 failures, and the same 3 fail on `main` without this change: two expect the old chat at `/chat` (ADR-0058 amendment 1 moved it), and one is the physics search count.
- Screenshots at 1440 and 390 px wide: the hero first, the calculator second, no horizontal scroll.

## Consequences

- Easier: a visitor reads what Anisotropy is before meeting the tool, and the page's first heading is its `h1`.
- Harder: the calculator, the audit's "visual hook", now starts at the bottom edge of a 1440 by 900 screen instead of filling it.
- We depend on: the CEO accepting the reversal of audit items 4 and 5.

## How we will know it was wrong

- The CEO or the founder asks for the calculator back up front.
- Beta testers report not finding the calculator on the home page.
