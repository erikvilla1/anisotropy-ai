# ADR-0066: The home hero follows PhysicsX: the material photo full-bleed, a twelve-column grid, the 3D stack in a lens, and the header over it

- Status: Proposed
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0065](ADR-0065-the-home-page-opens-on-the-hero-and-the-laminate-calculator-follows-it-as-the-demonstration.md) (the hero first; this is its option 3 in part), [ADR-0001](ADR-0001-deterministic-engine.md), the CEO's website audit of 2026-10-31 (item 7), `app/page.tsx`, `app/home.css`, `components/home/hero-lens.tsx`, `components/site-shell.tsx`, `tests/browser/home.spec.ts`

## Context

The UI/UX lead asked on 2026-11-07, with a screenshot of the PhysicsX hero: "lets recreate this homepage for anisotropy. same style, keep the copy and material the same as current." This chunk is the hero and the header over it; the sections below follow in later chunks.

Measured on www.physicsx.ai on 2026-11-07 at 1440 by 900: the hero fills the screen; the `h1` is 85 px with an 85 px line height, -2.55 px tracking and weight 400, at x = 32; the copy is 18/24 px at x = 736, 437 px wide; the page declares a 12-column grid (`--px-cols: 12`), which puts that copy on column 7 with 32 px gutters and margins; the header is transparent over the hero, with 17 px white links, and scrolls away with it; a framed "lens" shows a second video aligned with the background, with monospace readouts under it. Its typefaces are its own ("Physics X", "Physics X Mono"). Audit item 7 asks for "a cool graphic up front (kind of what I want to do with the 3D laminate visual)".

## Options considered

1. Restyle the hero in place, keeping the sticky header and its layout. Rejected: the request is PhysicsX's style.
2. Use PhysicsX's typefaces or video. Rejected: they are PhysicsX's, and the request keeps our copy and material.
3. A lens showing the weave photo under a colour map, as PhysicsX's shows a simulated field. Rejected: it would look like a field the engine never computed (ADR-0001).
4. A lens holding the 3D stack the calculator already draws. Chosen: the scene and its default stack exist, and audit item 7 names the 3D laminate as the graphic.
5. The transparent header on every page. Deferred: other pages rely on the sticky header (scroll padding, the calculator view's sticky offset).

## Decision

Option 4.

- The hero fills the screen (at least 640 px). The carbon weave photo covers it in greyscale under dark gradients.
- A 12-column grid with 32 px gutters and margins: the eyebrow and the headline on columns 1 to 7, the copy, the chat and the footnote on columns 8 to 12. Our headline is longer than PhysicsX's, so the copy moves one column right to leave room for the lens.
- The headline in DM Sans, weight 400, 5.6 % of the screen width (48 to 104 px), line height 1, tracking -0.03 em, all white. The copy is 18/24 px. The small labels use the system's monospace font, 11 px, in capitals.
- The lens is a 4:3 frame with a thin light border holding the calculator's default stack, turning, drawn by the same scene. It is decoration: hidden from screen readers, not clickable, and it asks the engine for nothing. Its caption above it is the old annotation, "Carbon fiber / The material is the starting point."
- The chat box becomes dark glass with a thin light border and a white send button. Phones get 16 px text.
- On the home page only, the header is transparent over the hero and scrolls away with it. Its links stay on one line; the version label shows from 1600 px.
- Tablets set the copy and the lens side by side; phones stack them, with the lens at 58 % of the width.
- The old hero rules leave `app/globals.css` and `app/research.css`. The copy is unchanged, except that its one line break became two paragraphs.

## Why (evidence)

- The request and the PhysicsX measurements above, and the lead's screenshots of that hero (kept outside the repository).
- Screenshots at 1920, 1440, 820 and 390 px: no horizontal scroll, no console errors; the lens clears the headline's first line and touches the top of its second; "Scroll to discover" lands on the calculator.
- Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped. Against the built site, `home.spec.ts` 7 passed, including the new hero test; `portfolio`, `research` and `expansion` had the same 3 failures as `main` (ADR-0065).

## Consequences

- Easier: the hero matches the reference, and the 3D stack is up front as audit item 7 asked, with the calculator still under it (ADR-0065).
- Harder: the home page draws two 3D scenes. The photo is 1280 by 572 px, so it is enlarged to fill the screen and looks soft on large displays; a larger photo or a clip would fix it. The home header differs from the other pages until they are restyled. The green accent now shows only in the status dot and below the hero.

## How we will know it was wrong

- The CEO or the UI/UX lead asks for the green headline or the sticky header back.
- Phones report the home page slow or hot with two scenes. No measurement yet.

## Amendment 1, 2026-11-07 (only the words: a new headline and two paragraphs; the chat box and the small labels leave)

**Context.** After the first version the UI/UX lead asked: "get rid of the scroll to discover / get rid of the built to be tested. / get rid of chat box on hero page. / should just be the words (simple summary of what the software does) on the left and the words on the right (use similar style of copy writing as physicsx)". PhysicsX's hero holds a two-line headline, one "We're bringing ..." sentence, then three short imperatives.

**Options.** For the headline: (1) keep "From material to understanding.", rejected, it names a journey, not what the software does; (2) "Every layer. Accounted for." or "Composites. Calculated.", rejected, shorter but vaguer; (3) "Composite analysis. Traced to evidence.", chosen, it names the work and what sets it apart.

**Decision.** The hero holds the headline, two paragraphs and the lens with its caption, nothing else:

- Left: "Composite analysis. / Traced to evidence."
- Right: "We're bringing composite theory and real test data into one engineering platform, changing how laminates and coupons are set up, analyzed and documented." and "Spend less time on setup and reports. Spend more time on the structure. Trace every number back to its source."
- Removed: the eyebrow, the chat box, the "Coupons first" footnote and the bottom line ("01 — The first chapter", "Scroll to discover", "Built to be tested."). The status dot goes with the eyebrow, so the hero has no green.
- The lens moves above the headline: its bottom edge sits a quarter of a line into the first line's tops.
- The chat box component stays, because the workspace reads its hand-off key, but it is not on the page. Its browser test goes with it. This reverses audit item 5, the chat box under the 3D laminate, until the CEO confirms.

**Evidence.** The copy restates what the repository already says: `docs/brain/company.md` ("analyze composite laminates and test coupons, with results they can trace to equations, material sources and tests") and the audit's item 8 ("grounded in composite theory and real mechanical test data"; "Less time on repetitive setup and documentation, more time optimizing the structure"). It quotes no number and makes no AI claim (`docs/brain/voice.md`, ADR-0028). Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped. Against the built site, `home`, `portfolio`, `research` and `expansion` gave 17 passed and 2 failed; both failures also fail on `main` (ADR-0065). Screenshots at 1920, 1440, 820 and 390 px: no horizontal scroll, no console errors.

## Amendment 2, 2026-11-07 (PhysicsX's header space, Workspace top right)

**Context.** The UI/UX lead asked: "use same header space as physics X, but have the workspace button in the top right". PhysicsX's header, measured the same day, is about 56 px tall with 32 px margins and a 28 px logo; its links start at x = 736 of 1440, the halfway line, which is also where its copy starts (column 7), at 17 px.

**Decision.** On the home page from 1201 px: the header is 56 px tall on a three-column grid whose second column starts on the halfway line; the logo is 28 px and only as wide as itself; the links start on that line at up to 17 px (1.1 % of the width below 1545 px, so they always end before the button); Workspace sits in the top-right corner; the version label is hidden. To keep the links and the copy on one line, as PhysicsX does, the copy moves back to column 7, the headline to columns 1 to 6 at 5.2 % of the width (48 to 100 px), and the lens left to 28 %.

**Evidence.** Measured at 1201, 1280, 1440, 1600 and 1920 px: the header is 56 px; the links and the copy start at the same x; the links end at least 32 px before Workspace; the headline keeps two lines and ends before column 7; the lens clears the copy by 40 to 54 px; no horizontal scroll. Against the built site, `home`, `portfolio`, `research` and `expansion`: 17 passed, and the same 2 failed as on `main`.
