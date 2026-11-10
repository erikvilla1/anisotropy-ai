# ADR-0077: The home hero follows PhysicsX: the material photo full-bleed, a twelve-column grid, the 3D stack in a lens, and the header over it

- Status: Proposed
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0076](ADR-0076-the-home-page-opens-on-the-hero-and-the-laminate-calculator-follows-it-as-the-demonstration.md) (the hero first; this is its option 3 in part), [ADR-0001](ADR-0001-deterministic-engine.md), the CEO's website audit of 2026-10-31 (item 7), `app/page.tsx`, `app/home.css`, `components/home/hero-lens.tsx`, `components/site-shell.tsx`, `tests/browser/home.spec.ts`

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
- Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped. Against the built site, `home.spec.ts` 7 passed, including the new hero test; `portfolio`, `research` and `expansion` had the same 3 failures as `main` (ADR-0076).

## Consequences

- Easier: the hero matches the reference, and the 3D stack is up front as audit item 7 asked, with the calculator still under it (ADR-0076).
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

**Evidence.** The copy restates what the repository already says: `docs/brain/company.md` ("analyze composite laminates and test coupons, with results they can trace to equations, material sources and tests") and the audit's item 8 ("grounded in composite theory and real mechanical test data"; "Less time on repetitive setup and documentation, more time optimizing the structure"). It quotes no number and makes no AI claim (`docs/brain/voice.md`, ADR-0028). Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped. Against the built site, `home`, `portfolio`, `research` and `expansion` gave 17 passed and 2 failed; both failures also fail on `main` (ADR-0076). Screenshots at 1920, 1440, 820 and 390 px: no horizontal scroll, no console errors.

## Amendment 2, 2026-11-07 (PhysicsX's header space, Workspace top right)

**Context.** The UI/UX lead asked: "use same header space as physics X, but have the workspace button in the top right". PhysicsX's header, measured the same day, is about 56 px tall with 32 px margins and a 28 px logo; its links start at x = 736 of 1440, the halfway line, which is also where its copy starts (column 7), at 17 px.

**Decision.** On the home page from 1201 px: the header is 56 px tall on a three-column grid whose second column starts on the halfway line; the logo is 28 px and only as wide as itself; the links start on that line at up to 17 px (1.1 % of the width below 1545 px, so they always end before the button); Workspace sits in the top-right corner; the version label is hidden. To keep the links and the copy on one line, as PhysicsX does, the copy moves back to column 7, the headline to columns 1 to 6 at 5.2 % of the width (48 to 100 px), and the lens left to 28 %.

**Evidence.** Measured at 1201, 1280, 1440, 1600 and 1920 px: the header is 56 px; the links and the copy start at the same x; the links end at least 32 px before Workspace; the headline keeps two lines and ends before column 7; the lens clears the copy by 40 to 54 px; no horizontal scroll. Against the built site, `home`, `portfolio`, `research` and `expansion`: 17 passed, and the same 2 failed as on `main`.

## Amendment 3, 2026-11-07 (the lens leaves the hero)

**Context.** The UI/UX lead asked: "why is there still a 3d model randomly here on the hero page?" Amendment 1 kept the lens because PhysicsX's hero has one and it was not on the list of removals; on the lead's screen it also crowded the header.

**Decision.** The lens and its caption leave the hero, and `components/home/hero-lens.tsx` is deleted. The hero holds the photo, the headline and the two paragraphs. The calculator under it still draws the stack, so option 4 now lives there only. Tablets stack the headline and the copy in one column.

**Evidence.** The browser test checks that the hero holds no 3D view, text box or link. Against the built site, `home`, `portfolio`, `research` and `expansion`: 17 passed, and the same 2 failed as on `main`. `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. Screenshots at 1920, 1440, 820 and 390 px: no horizontal scroll, no console errors.

## Amendment 4, 2026-11-07 (the wordmark in capitals; links fade on hover)

**Context.** The UI/UX lead asked: "can you make the Anisotropy all caps?" and then for the header links to look "imprinted" on hover, as PhysicsX's do. Measured on www.physicsx.ai the same day, a hovered nav link keeps its colour and drops to opacity 0.6, with `transition: opacity 0.15s`.

**Decision.** Site-wide, on every page:

- The wordmark shows the name in capitals with 0.04 em tracking, through CSS. The text stays "Anisotropy", so page titles, the link's label and screen readers do not change (ADR-0058).
- A hovered header link, the Services chevron and a dropdown entry fade to 60 % in 0.15 s instead of turning the accent colour. The chevron keeps its circle only for keyboard focus and while the menu is open; a dropdown entry keeps its highlight for keyboard focus and for the current page.

**Evidence.** In the browser, the "Industries" link reads opacity 1 at rest and 0.6 on hover, its colour unchanged; a dropdown entry reads 0.6 on hover. The wordmark's text content is still "Anisotropy" and it renders "ANISOTROPY" in the header and the footer. Against the built site, `home`, `expansion`, `portfolio` and `workspace`: 18 passed, 1 failed, the stale chat test of ADR-0076.

## Amendment 5, 2026-11-07 (a shorter headline at PhysicsX's size)

**Context.** The UI/UX lead found "Composite analysis. Traced to evidence." far wider than PhysicsX's "Engineering. Reengineered.". It also grew with the screen to about 97 px on a wide monitor, while PhysicsX's stays at 85 px. Set in our headline font at 85 px, PhysicsX's headline measures 522 px wide and ours measured 736 px.

**Options.** Four headlines rendered side by side at 85 px: "Composites. Calculated." (466 px), "Composites. Understood." (466 px), "Every ply. Accounted for." (542 px) and "Composites. Traced." (466 px). The lead chose the first: it says plainly what the software does, in PhysicsX's two-word rhythm. The paragraphs beside it already say that every number traces back to its source.

**Decision.** The headline reads "Composites. / Calculated.". Its size is `clamp(48px, 5.9vw, 85px)`, which is 85 px at 1440 px wide and never larger, like PhysicsX's. On phones it is `clamp(40px, 12.3vw, 52px)`, 48 px on a 390 px screen, which is PhysicsX's phone size.

**Evidence.** Measured in the browser: 85 px at 1440 and 1920 px wide, 48 px on a 390 px phone, no horizontal scroll. `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. Against a build without the hero clip, `home`, `portfolio` and `expansion`: 16 passed, 1 failed, the stale chat test of ADR-0076.

## Amendment 6, 2026-11-07 (the demo section on white)

**Context.** The UI/UX lead asked for the section after the hero, the laminate calculator, to have a white background. PhysicsX's sections after its hero are white (measured on 2026-11-07: `body` background `rgb(255, 255, 255)`).

**Decision.** The calculator section (`#laminate`) redefines the site's colour variables for itself: white page, light grey panels, white fields, dark text and a dark accent. The few colours written out for a dark page are corrected there: the headings' grey, the panels' and the matrix headers' fills, the field borders, the error colours and the button text. The 3D view stays a dark viewport card, since its axes and dust are drawn for a dark ground, and the axis legend's light swatches get a thin outline so they show on white. The sections after it stay dark for now.

**Evidence.** Screenshots at 1440 px and on a phone, with the local engine answering: the matrices, the stack and the button read on white; no console errors; no horizontal scroll. `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. Against a build without the hero clip, with the local API for the calculator cases, `home`, `calculator`, `portfolio` and `expansion`: 24 passed, 1 failed, the stale chat test of ADR-0076.

## Amendment 7, 2026-11-07 (the demo section's head set as PhysicsX sets its white sections)

**Context.** The UI/UX lead pointed to PhysicsX's white "Build beyond" section as the reference for type. Measured there the same day at 1440 px: the section has 88 px padding; the label is 16/20 px monospace capitals with 0.02 em tracking and a 1 px tick before it, at x = 32; the statement is 38/41 px, weight 400, -0.01 em tracking, from column 4 (x = 384), behind a 1 px rule in the middle of the gutter (x = 368), spanning columns 4 to 10; its paragraphs are a line apart.

**Decision.** The calculator section's head takes that arrangement. "Laminate calculator / Live" is the label, with a tick in place of the status dot. "Your layup, calculated." and the paragraph under it form the statement, both at 38/41 px in the section's dark text, a line apart. The section has 88 px padding and the hero's 32 px margins. Tablets put the label above the statement at 30/34 px; phones use 24/28 px. The copy is unchanged.

**Evidence.** Measured in the browser at 1440 px: the label at (32, 988), the rule at x = 368, the statement's text from x = 384, 38/41 px, the same as PhysicsX's. On a phone: no horizontal scroll, no console errors. `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. Against a build without the hero clip, with the local API, `home`, `calculator`, `portfolio` and `expansion`: 24 passed, 1 failed, the stale chat test of ADR-0076.

## Amendment 8, 2026-11-07 (the home header on every page; the demo's instructions as a caption)

**Context.** The UI/UX lead asked for the header "the same from the home page across all the pages", and found the demo section's 38 px instructions "out of place" beside the label.

**Decision.**
- **Header.** The header rules of amendment 2 leave `app/home.css`, which only the home page loads, for `app/globals.css`, and apply to every page except the workspace's. The workspace keeps its own sticky app header. The header is transparent and scrolls away: over the hero on the home page, at the top of the page's flow elsewhere. Without a sticky header, `scroll-padding-top` is 0 and the two sticky panels that cleared it (the calculator's 3D view, the physics topic list) stick 32 px from the top. This settles option 5 of this record.
- **Demo heading.** "Your layup, calculated." stays at 38/41 px behind the rule. The instructions under it become an 18/26 px caption in the muted colour, at most 36 em wide, 16 px below.

**Evidence.** Measured at 1440 px on `/`, `/about`, `/industries`, `/library`, a service page and `/contact`: the header is 56 px, with the mark from 32 px, the links from 736 px and Workspace ending at 1408 px; no version label. The workspace header is unchanged. On a phone, the menu opens and nothing scrolls sideways. `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. The whole browser suite against the built site, with the local API: 52 passed, 1 skipped, 5 failed, the five stale tests of ADR-0078. The home test now checks that `/about`'s header is in the flow and 56 px tall.

## Amendment 9, 2026-11-07 (a lens returns, playing our own results)

**Context.** Without the lens the lead found the hero "empty/spacious", and asked for animated models of different applications in it.

**Decision.** A lens returns at amendment 3's place: the gutter before the copy, just above the headline's middle. It is no longer the calculator's live stack. It is a recorded loop of three of our public results in the Turbo spectrum, seen through glass over the clip, with a caption per model. ADR-0071 holds the decision and its evidence.

## Amendment 10, 2026-11-07 (the demo on its heading's columns)

**Context.** The lead found the demo section "wasting space", with the heading's ruled statement "not aesthetically arranged in relation to the demo". At 1440 px its three columns did not line up with the heading. They were the view (5 fr, sticky), the inputs with the ply list (3 fr) and the answer (4 fr). The view stood 473 px tall beside 1,023 px of inputs. Without the engine, the answer's panel was mostly empty.

**Decision.** From 1280 px, the demo takes the heading's 12 columns:
- **Inputs, columns 1 to 3, under the label.** The citation and hints are 12 px. The material's constants sit three to a row where they fit.
- **The 3D view, columns 4 to 9.** It starts where the heading's text starts, and the statement now spans the same columns.
- **The ply list, columns 10 to 12,** with the view's hover line and axis key under it.

The view fills the row's height, so no column leaves a gap. When the canvas is narrower than 4:3, the camera zooms out (`FitWidth`) so the stack keeps its width. The answer is one band under the row. It takes the same columns through CSS subgrid: the description under the inputs, the matrices under the view, and "Want to check the math?" with its scope under the plies. Without the engine, the band is one line.

Under 1280 px:
- the heading stacks;
- the view runs across the top, with the inputs and the plies side by side under it;
- the answer runs across the bottom, its description and next step side by side over the matrices.

On phones it is one column.

**Evidence.** Measured in the browser on 2026-11-07, with the local engine and without it:
- **At 1440 px:** the inputs start at x = 32 under the label; the view and the matrices at x = 384, where the heading's text starts; the plies and the next step at x = 1088. The three columns are each 584 px tall.
- **Section height at 1440 px:** 1,353 px with the engine (1,407 before) and 1,169 px without it (1,407 before).
- **At 1870, 1280, 1100 and 900 px and on a phone:** no horizontal scroll and no page errors.
- **Checks:**
  - `npm run typecheck` clean.
  - `npm test`: 168 passed, 1 skipped.
  - `home.spec.ts`, `calculator.spec.ts` and `workspace.spec.ts` against a build without the hero clip: 18 of 18 passed.
  - The new alignment test in `home.spec.ts` passed.

## Amendment 11, 2026-11-10 (one section kit; the home page's lower sections set on it)

**Context.** After the hero and the white demo, the home page went back to the old dark style: a principles strip in 8 px type, then five sections in a 1,440 px container with 64 px side padding, small eyebrows above two-line headings and 13 px body text. The lead asked for one design from top to bottom, after PhysicsX.

**Decision.**
- **The kit.** `app/sections.css` holds the parts every page's sections are set with:
  - a full-width band, 88 px above and below and 32 px at the sides, dark by default and light with `is-light`, which sets the colour variables for the band;
  - the demo's head, a monospace label with a tick in columns 1 to 3 and the statement from column 4 behind a 1 px rule;
  - a 12-column content grid and a plain card.
- **The home page.** Mission, Platform, Impact, Team and News are bands, dark and light in turn, starting dark after the white demo.
  - Each opens with the kit's head. The forced line breaks leave the headings; each fits one line at 38 px.
  - Content starts at column 4, under the statement, in cards three columns wide and three to a row. The news list is rows between 1 px rules, with the date in the label column and the words from column 4.
  - The four principles close the Mission band as a strip on all twelve columns.
  - A service's status is a monospace word with a dot (full, half or ring) in place of the coloured pill.
  - The copy, links and ids are unchanged.

**Options not chosen.** Cards four columns wide across the full width: five cards leave a larger gap, and the team cards are mostly empty at 1,860 px. Five cards in one row: their edges fall off the head's columns. The principles as a separate thin dark strip above Mission: two rows of monospace labels 88 px apart compete.

**Evidence.** On 2026-11-10, against the dev server:
- **Measured at 1440 px:** labels at x = 32; statements and card columns at 384, 736 and 1,088; the principles at 32, 384, 736 and 1,088; news dates at 32 and titles at 384.
- **Overflow:** none sideways at 1860, 1440, 1100, 900 and 390 px.
- **Checks:** `npm run typecheck` clean, also on this commit's tree alone. `home.spec.ts` and `portfolio.spec.ts`: 12 passed, 1 failed. The failure is the workspace chat test, which does not load the home page and failed before this change.
- **UNVERIFIED:** the production build of this commit alone, and the look on phones and tablets (rules are written; no visual check yet).

## Amendment 13, 2026-11-10 (the closing section as a light band; the footer with the site's navigation in columns)

**Context.** The closing section of the home and industries pages was a dark gradient panel in a 1,440 px container with 64 px padding and 7 to 10 px labels, and its markup was written twice, once per page. The footer was one row of 9 px text with no navigation. PhysicsX's footer, measured at 1440 px on 2026-11-10, has 48/32/24 px padding, the logo on the left, and columns of 17/22 px links behind 1 px rules set 16 px left of the grid column. Its copyright line is 14 px monospace capitals. Its closing heading and button start on column 7.

**Decision.**
- **One component.** The closing section is `ClosingBand` (`components/closing-band.tsx`), used by both pages, as a light band of the section kit.
- **Its parts.** The label sits above the statement, because both labels are longer than three columns. The statement is in columns 1 to 6 at `clamp(40px, 4.6vw, 64px)`, weight 400. The action starts on column 7. The optional links sit at 16 px on columns 7 and 10 under a 1 px rule.
- **The footer.** It is dark, with 32 px margins. The logo and tagline are in the left half. The header's navigation from `lib/site-nav.ts` forms two columns on columns 7 and 10: the plain pages and Workspace, then Services with its five pages. Each column sits behind a 1 px rule in the gutter. Links are 16/22 px and fade to 60 % on hover.
- **The bottom row.** Under a 1 px rule: the copyright line, "Research preview v.01" and "Back to top", in 14 px monospace capitals on the same columns.
- **Nothing invented.** No link, address, social account or legal page was added. The footer stays absent in the workspace.
- **Narrow screens.** Under 1024 px the halves stack. Under 520 px the link columns become one.
- **Tests.** Four tests in two spec files now find the header's links inside "Main navigation": the footer repeats those names, and a page-wide lookup matched two links. No assertion was removed.

**Evidence.** On 2026-11-10, against the dev server:
- **Measured at 1440 px:** the button, both link columns and the bottom row's items start at x = 736 and x = 1,088; the column rules are at x = 720 and x = 1,072.
- **Behaviour:** the footer is absent on `/workspace`, `/workspace/fea` and `/chat`; footer and closing links land on their addresses with no page errors; nothing extends past the viewport at 1200, 1024, 900, 768 and 390 px.
- **Checks:** `npm run typecheck` clean, also on this commit's tree alone. `npm test`: 196 passed, 1 skipped. `home.spec.ts`, `expansion.spec.ts` and `portfolio.spec.ts`: 18 passed, 1 failed, before and after; the failure is the workspace chat test of `portfolio.spec.ts`.
- **Flaky once:** one run also failed the Services disclosure test (`aria-expanded` stayed false after Enter). It then passed 2 of 2 and in the final run; the cause was not found.
- **UNVERIFIED:** the production build of this commit alone, and the look on phones.

## Amendment 15, 2026-11-10 (the Workspace button's hover: a white fill, black words, the arrow turned)

**Context.** The lead showed a recording of another site's button: a darker chip around its arrow grows across the whole button on hover, and shrinks back on leave. The lead asked for the same on the header's Workspace button, "but obv just white when you hover over it (like inverted) text to black box to white and arrow switch directions or something".

**Decision.** On hover, and on keyboard focus, a white fill sweeps across the Workspace button from the arrow's side in 0.35 s. The words and the arrow turn near-black, the border turns white, and the arrow turns 45°, from up-right to right. It runs back when the pointer leaves. The fill is a pseudo-element under the words, scaled from the right edge, so the markup is unchanged. The button no longer lifts 2 px on hover. Reduced motion gets the same end state with no movement.

**Evidence.** In the browser on 2026-11-10 at 1440 px, on the dev server: at rest the button is outlined with white words and an up-right arrow; hovered, its words are rgb(13, 13, 13), its border white, the fill at full width and the arrow turned 45°; after the pointer leaves it returns to the rest state. Screenshots of each state were looked at. UNVERIFIED: touch screens, where there is no hover.
