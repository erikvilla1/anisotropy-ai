# ADR-0077: The home hero follows PhysicsX: the material photo full-bleed, a twelve-column grid, the 3D stack in a lens, and the header over it

- Status: Proposed
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07; Founder, 2026-11-12 ("accept": "Composites. Calculated." and "Closed beta", amendment 16) | Drafted by: Claude Code
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

## Amendment 12, 2026-11-10 (the inner pages on the section kit)

**Context.** About, Industries, Services, its five pages and Contact were still in the old dark style: a 1,440 px container with 64 px side padding, so nothing lined up with the header's 32 px; small eyebrows above the headings; 13 px body text; gradient cards. Their rules sit in `app/expansion.css`, `app/globals.css` and `app/research.css`, which other pages share, and Next keeps a page's stylesheet loaded after navigation.

**Decision.**
- **The opening.** Each page opens on the dark page ground under the header: a monospace label with a tick, the h1 in the hero's type (DM Sans 400, `clamp(44px, 5vw, 72px)`, -0.03em) across the page, then the introduction at 18/26 px from column 7 and the page's short note in columns 1 to 4.
- **The bands.** Every section after it is a kit band, light first, then alternating. The old eyebrow is the band's label; the h2 and its paragraph are the statement.
- **The content.** It sits on the twelve columns: rows on the head's columns (name 1 to 3, text 4 to 9, link or state 10 to 12), cards of three columns, and halves for a picture beside a list.
- **States and pictures.** A service's state is the home page's mark (full dot, half dot, ring) with the word; no colour carries it. An empty media slot is the band's panel colour with a hatch and a label. The coupon illustration stays a dark viewport on a light band.
- **The rules.** They are in a new `app/inner-pages.css` under new class names (`kit-`, `page-opening`, `industry-`), and `<main>` is `kit-page`, so nothing here restyles a class another page uses.
- **Copy.** Every word, link, id and label is unchanged. One browser test's two selectors on the Industries page follow the renamed elements; the counts it checks are the same.

**Option not chosen.** The h1 beside the introduction in columns 1 to 6, as the home hero has it: at 1440 px six columns are 672 px, and "From an engineering question" at 72 px measures about 930 px.

**Evidence.** On 2026-11-10, against the dev server:
- **Measured at 1440 px:** label and h1 at x = 32, the logo's x; the introduction at x = 736, where the header's links start; band headings computed 38/41 px, weight 400.
- **Overflow:** none sideways on any of the nine pages at 390, 768, 1100, 1440 and 1860 px.
- **Copy:** a comparison of each page's text and non-class attributes with the previous commit shows no change.
- **Checks:** `npm run typecheck` clean, also on this commit's tree alone.
- **Browser specs: no clean run.** `expansion.spec.ts` and `portfolio.spec.ts` gave 9 passed and 1 failed before (the workspace chat test), and 6 to 8 passed afterwards across three runs. Every new failure started on the home page, which other work in progress was changing at the same time (a header link clicked from `/` not navigating in time, the home page's own screenshot timing out). The checks those specs make about these nine pages were run directly: 25 of 25 held.
- **UNVERIFIED:** the full browser suite and the production build, which are to be run when the home page's work in progress is finished; phones; hover and focus states.

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

## Amendment 14, 2026-11-10 (a supporters' strip; Impact removed; the team section becomes About with face cards)

**Context.** The lead asked for a logo strip like PhysicsX's with UC San Diego's The Basement mark, a mention of the Launchpad programme there and in an About section, the Impact section hidden ("kinda useless"), and the team section turned into About, with face cards to be linked to LinkedIn with photos later. The only fact stated about the programme is that Anisotropy is part of the Fall 2026 Launchpad cohort at The Basement, UC San Diego (ADR-0081).

**Decision.**
- **Order under the demo.** Mission dark, the supporters' strip light, Platform dark, About light, What is new dark. The labels are renumbered 01 to 04.
- **The strip.** It is fed from `lib/supporters.ts` and drawn by `components/home/logo-strip.tsx`, under the label "SUPPORTED BY".
  - One logo stands beside its sentence. Several take the row.
  - A set wider than the row drifts as a marquee at 40 px a second, stops under the pointer and on focus, and wraps onto rows for reduced motion.
  - The mark keeps its colours and proportions, 40 px tall, and is not a link.
- **Impact.** Its markup is deleted from the home page. Two browser tests that read it now check that it is absent.
- **About.** It keeps `id="working"`, the heading and the paragraph, and states the programme as one small monospace line, without a third copy of the mark. Each person has a 4:5 frame holding their initials, ready for a portrait.
- **Portraits and profiles.** `Person` in `lib/team.ts` gains optional `photo` and `linkedin`, both unset. Each is added only with that person's consent (ADR-0057 amendment 1). `tests/team.test.ts` checks that a set photo is a file under `public/` and a set profile is a LinkedIn profile address.

**Options not chosen.** Repeating the one logo to fill a moving row: it would fake a row of supporters. A logo in About as well: the hero and the strip already show it. Hiding Impact with CSS: it would stay in the page.

**Evidence.** On 2026-11-10, against the dev server:
- **PhysicsX's strip, measured at 1440 px:** white; a 16/20 px monospace capitals label at x = 32; logos 22 to 44 px tall, 112 px apart, drifting left at about 40 px a second.
- **Ours at 1440 px:** the mark 135.4 by 40 px at x = 32; the sentence at x = 384 on one line; no animation with one logo.
- **The marquee path,** checked with the logo listed eight times and then restored: two sets of eight, the copy hidden from assistive technology, 40.00 px a second, paused under the pointer and with focus, two rows and no animation for reduced motion.
- **A face card with a stand-in photo and profile link,** then restored: the photo fills the frame, and the name links out in a new tab with `rel="noopener noreferrer"`.
- **Overflow:** none sideways at 1860, 1440, 1100, 900 and 390 px.
- **Checks:** `npm run typecheck` clean and `tests/team.test.ts` 2 of 2, both also on this commit's tree alone. `home.spec.ts`, `portfolio.spec.ts` and `research.spec.ts`: 13 passed, 2 failed; the failures are the workspace chat test and a count on the library's physics page, neither of which loads the home page.
- **UNVERIFIED:** the production build; phones and tablets beyond the overflow check; several different real logos in the row; real portraits in the 4:5 frame; UC San Diego's rules for the mark.

## Amendment 15, 2026-11-10 (the Workspace button's hover: a white fill, black words, the arrow turned)

**Context.** The lead showed a recording of another site's button: a darker chip around its arrow grows across the whole button on hover, and shrinks back on leave. The lead asked for the same on the header's Workspace button, "but obv just white when you hover over it (like inverted) text to black box to white and arrow switch directions or something".

**Decision.** On hover, and on keyboard focus, a white fill sweeps across the Workspace button from the arrow's side in 0.35 s. The words and the arrow turn near-black, the border turns white, and the arrow turns 45°, from up-right to right. It runs back when the pointer leaves. The fill is a pseudo-element under the words, scaled from the right edge, so the markup is unchanged. The button no longer lifts 2 px on hover. Reduced motion gets the same end state with no movement.

**Evidence.** In the browser on 2026-11-10 at 1440 px, on the dev server: at rest the button is outlined with white words and an up-right arrow; hovered, its words are rgb(13, 13, 13), its border white, the fill at full width and the arrow turned 45°; after the pointer leaves it returns to the rest state. Screenshots of each state were looked at. UNVERIFIED: touch screens, where there is no hover.

## Amendment 16, 2026-11-12 (the header and footer after the site audit; the tagline and the stage confirmed by the founder)

**Context.** The site audit of 2026-11-12 found in the shell: two taglines, "Engineered from evidence." in the footer and "Composites. Calculated." on the home, and two names for the stage, "Research preview v.01" in the footer and in a header label hidden at every width, and "closed beta" on the home (shell-16, decision D11); header links of 9 to 10 px from 641 to 900 px, with "Services +" about 5 px low (shell-7); a phone menu whose button came after its links in the page's order, with no Escape and no close on a press outside (shell-6); the current page marked by colour alone (shell-21); ↗ on links that stay on the site (shell-8); "Back to top" leaving the focus in the footer (shell-9); a masked logo that would vanish in forced colours (shell-15, from how forced colours work, not observed); and a 70 px workspace header on a 48 px gutter over a toolbar on 20 px, with no way back to the projects from CAD and the viewer (shell-22, shell-J1-1, shell-J1-2).

**Options.** From 641 to 900 px: (1) the row of links at 13 px or more; not chosen: an estimate from the type sizes, not a measurement, puts the five links, the logo and the Workspace button wider than a 768 px header. (2) The menu button up to 900 px, the audit's alternative: chosen.

**Decision.**
- **Tagline and stage:** "Composites. Calculated." and "Closed beta", with no version: the founder's answer to D11 on 2026-11-12, "accept". The header's hidden version label and its rules are gone.
- **The menu** folds the links up to 900 px (640 before; `components/services-menu.css` follows). Its button comes before it in the page and names it (`aria-controls`); opening moves the focus to the first link; Escape closes it and returns the focus to the button; a press outside the header, the focus leaving the header or a new page closes it; each row is at least 44 px tall. From 901 px the links sit on one centre line.
- **Arrows:** the shell has no ↗: → for Workspace in the header, the menu and the footer; ← for "Back to website" and "All projects". Amendment 15's hover keeps its fill and colours, and its arrow no longer turns. Beyond the shell, a library property's link to its source page on this site drops its ↗, which stays on the external one with "(opens in a new tab)" in its name, and a job's "Open results in a new window" takes ↗ for the new window. ↗ is meant only for a link that opens a new tab, but this change does not reach the pages' own links: they follow in their fix groups (the home, about, industries, services and contact pages: audit finding uiux-home-about-12; the library's "Discuss this material": library-27; the library's "View source details", its source titles and supporting references, the physics cards' references, the library page's source links and the source viewer's links, and the coupon studio's "Open results in a new window": handed on with shell-8). Until then some same-site links keep ↗.
- **The current page** is underlined, 1 px at 6 px, in the header and the footer, and in the folded menu the current service's row too (from 901 px the panel's 1 px rule marks it); on a service page the Services item says `aria-current="true"`, the section, not the page.
- **Back to top** scrolls to the top and moves the focus to the logo; without a script it goes to `#main`.
- **Forced colours:** the masked parts of the logo draw in the system's text colour.
- **The workspace header** is 56 px tall on a 20 px gutter. On CAD and the viewer, which have no toolbar of their own, it links to All projects; on a phone that link takes the place of "Back to website", and the logo still leads home. Its links are 13 px on phones. On phones the workspace toolbar puts the project's name on a row of its own and keeps the kind on one line.

**Evidence.** `npm run build` on 2026-11-12: every page lists the menu button before `id="site-menu"`; `out/workspace/cad.html` has the header's All projects link and `out/workspace/fea.html` does not; no page holds "Research preview" or `header-version`; the folded menu's underline for the current service row is in the shared stylesheet. `npm test` on 2026-11-13, rebased on main after #199: 255 tests, 254 passed, 0 failed, 1 skipped; `tests/site-metadata.test.ts`, 6 of 6, checks which addresses get the workspace header, where All projects shows, and that in the shell, the property table and a job's files ↗ sits only on a link with `target="_blank"` that says it opens a new tab or window (its check, run by hand on main's versions, flags four links in `site-shell.tsx` and two in `property-table.tsx`). `tests/browser/shell.spec.ts` (new: the menu's order, focus, Escape, outside press, Tab out and 44 px rows, the current service's row underlined in it, Back to top, the CAD header, the 404 page under an old address) and the existing site-wide specs: UNVERIFIED, not run in this change. No screenshots were taken: the header from 641 to 900 px, forced colours and the workspace header on a phone are UNVERIFIED.

## Amendment 31, 2026-11-11 (the supporters' strip removed)

Numbered 16 on its branch; renumbered when the branch took in main, where an amendment of 2026-11-12 had the number.

**Context.** Going through the draft, the lead showed the "Supported by" strip and asked: "also get rid of this".

**Decision.**
- The strip leaves the home page. Under the demo the order is Mission and Platform, both dark with a hairline between them, About light, What is new dark. The labels stay 01 to 04.
- Its component (`components/home/logo-strip.tsx`), its list (`lib/supporters.ts`) and its styles are deleted. They are in commit `a220d18` if a row of logos is wanted later.
- The Launchpad cohort is still named twice: by the white mark in the hero (ADR-0081) and by About's line.

**Options not chosen.** Hiding the strip with CSS: it would stay in the page. Recolouring the bands to keep dark and light in turn: Platform, About and What is new would each change ground, which the lead did not ask for.

**Evidence.** On 2026-11-11, in the browser against the dev server at 1440 px: the page's sections are the hero, the calculator, Mission, Platform, About, What is new and the closing band; no page errors. A screenshot of Mission into Platform was looked at.
- **Checks:** run on the same tree as ADR-0080 amendment 1 and recorded there, with the two browser tests that failed and what their re-runs showed.

## Amendment 17, 2026-11-13 (a black page with the clip in a round box, after Scale)

**Context.** The lead showed Scale's home page, where the hero's video plays in a box with round corners under the header, and asked: "make the homepage this style, keep same fonts and arrangements, just use the black background and rounded corners interior box for the hero vid."

**Decision.**
- **The page is black and the clip plays in a box.** The box starts under the header and stands on the page's margin at the sides and the foot, so its edges line up with the logo above and the sections below. Its corners are 20 px (16 px on phones).
- **The header lies on the black strip above the box,** no longer over the picture. It is still placed over the hero and scrolls away with it.
- **The words keep their arrangement inside the box:** the headline on columns 1 to 6 and the copy from the halfway line, where the header's links start; the badge bottom left and "Scroll to explore" bottom right, each as far from the box's edge as the headline is (32 px; 24 px under 1024 px; 16 px on phones).
- **The shades are lighter and stop short of black.** The fade into the page at the foot and the shade under the header are gone, since neither is over the picture now. A 1 px hairline inside the edge marks the box where the clip is dark.
- **The scroll tour takes the clip from the box** (ADR-0084): the hand-over starts from the box's place and corner radius, and the hero's black ground fades first so the shrinking clip uncovers the stage.

**Options not chosen.**
- Scale's 16 px frame with the logo moved to it: the logo and the box would leave the 32 px line the sections below stand on.
- The words on the page's own columns, 16 px inside the box: too close to its round corners.
- No hairline: where the clip is dark, the box's left and top edges were lost against the black page.

**Evidence.** On 2026-11-13, in the browser against the production build with the committed clip:
- **Measured.** At 1440 by 900 the header is 56 px tall and the box runs from x = 32 to 1408 and y = 64 to 868; the headline starts at x = 64, and the copy and the header's first link both at x = 736. At 1100 px the box starts at y = 86, at 900 px at x = 24 and y = 75, on a 390 px phone at x = 20 and y = 70 with 16 px corners. No sideways scroll and no page errors at any of the four.
- **Looked at.** Screenshots of the hero at 1860, 1440, 1100, 900 and 390 px, and of the hand-over at five moments of the scroll: the box shrinks into the card with round corners throughout and lands on the top ply; back at the top the hero is as at rest.
- **Checks.** `npm run typecheck` clean. `npm test`: 248 passed, 1 skipped, with a new case for the hand-over from the box. The whole browser suite against the build: 82 passed, 2 failed, 1 skipped, with a new case for the box and its margins in `home.spec.ts`.
- **The two failures** are `portfolio.spec.ts` "the chat keeps a coupon across messages" and "mobile navigation and workspaces fit the screen". Both ask the workspace's assistant for the open-hole coupon, which ADR-0089 no longer offers; neither loads the home page, and CI does not run that file. They are left for a change to the workspace's tests.
- **A stale test fixed on the way.** Two lines of `expansion.spec.ts` expected the workspace assistant's first question to be the test; since ADR-0089 offers one test it is the material, as `workspace.spec.ts` already reads it. Before the fix those two failed; after it the file passed 6 of 6. CI does not run this file either.
- **UNVERIFIED:** the look on the lead's screen and on a real graphics card (the container draws WebGL in software), Safari and Firefox, and real phones and tablets.

## Amendment 18, 2026-11-13 (the box is taken back: the clip fills the screen again)

**Context.** Having seen amendment 17 on the page, the lead said: "I also dont like the whole scale ai background change I suggested, revert back to whole screen."

**Decision.** Amendment 17 is undone in the code. The clip fills the hero again with the header over it, the shades and the paddings are as before amendment 17, and the scroll tour's hand-over starts from the whole window again (ADR-0084 amendment 2). The browser and unit cases written for the box go with it.

**Evidence.** On 2026-11-13, in the browser against the dev server: at 1440 by 900 the clip's box is the whole window (0, 0, 1440 by 900) and the header lies over it; the same on a 390 px phone; no sideways scroll, no page errors. A screenshot of the hero was looked at. `npm run typecheck` clean; `npm test` 247 passed, 1 skipped; `home.spec.ts`, `intro.spec.ts`, `tour.spec.ts` and `expansion.spec.ts` against the dev server with the local API: 26 of 26.

## Amendment 19, 2026-11-13 (the home page in the arrangement of Anduril's)

**Context.** Minutes after amendment 18 the lead showed Anduril's home page and asked: "lets copy this exact same layout for our homepage too", "fonts and all", "arrangement, layout, etc...". There the header lies on a black strip with its links in the middle; under it a video plays in a box with square corners on the page's margin; one statement in large capitals stands in the middle of the box, and under it a row of a two-line tagline, the mark and two short monospace lines.

**Decision.** The arrangement is followed; the words and the mark are ours.
- **Header, on every page.** From 1201 px it is 84 px tall with the logo at the left, the links in the middle of the page in semibold 16 px, and Workspace at the right. On the home page it lies on the hero's black ground.
- **The box.** The clip plays in a box with square corners from the header's foot to 32 px above the hero's foot, 32 px from each side (24 px under 1024 px, 20 px under 641 px). One even shade lies over it for the words.
- **The statement** is the level-one heading, in capitals of medium weight set tight: "Anisotropy / bringing composite theory / and real test data into / one engineering platform". It is the hero's earlier first paragraph, shortened; nothing is claimed that the paragraph did not say. The second paragraph leaves the hero.
- **The row under it.** "Composites. Calculated.", the earlier headline, is the tagline at the left; the triangle stands in the middle of the page; at the right, in monospace, "Fall 2026 Launchpad cohort" (ADR-0081) and under it "Explore" with a down arrow, which is the Scroll to explore button.
- **The Basement's mark** stays in the box's bottom left corner, without its line of text, which the row now carries.
- **Type.** The site's typeface changes with it (ADR-0093), and the logo's name is set in it (ADR-0080 amendment 4).
- **The tour's hand-over** starts from the box again (ADR-0084 amendment 3).
- **Under 761 px** the statement breaks where it needs to and the row stacks.
- **Sizes.** Seeing it, the lead asked to "keep the logo the same size, but make the font lil smaller": the statement is 4.1 % of the window's width (59 px at 1440 px, where the reference's proportion gave 66 px), the tagline and the two small lines a tenth smaller, and the mark in the row as it was.

**Not copied.** Anduril's "©" before the name, its own words, and its typeface, which is licensed.

**Evidence.** On 2026-11-13, in the browser against the dev server with the committed clip:
- **Measured at 1440 by 900:** the header is 84 px tall; the box runs from x = 32 to 1408 and y = 84 to 868; the statement, the mark and the header's links are each centred on x = 720. At 1880, 1100, 900 and 390 px the box follows the header and the margin (on the phone from x = 20 and y = 70). No sideways scroll and no page errors at the five sizes.
- **Looked at:** screenshots of the hero at the five sizes, of the hand-over at three moments, and of About and the laminate workspace in the new typeface.
- **Checks:** `npm run typecheck` clean; `npm test` 248 passed, 1 skipped. `home.spec.ts`, `intro.spec.ts`, `tour.spec.ts` and `expansion.spec.ts` against the dev server: 26 passed, 1 failed. The failure is `home.spec.ts` "typing a layup", the calculator's timing case that has failed before in this container; run alone twice, it passed twice.
- **The whole browser suite on a production build,** run after the commit: 81 passed, 3 failed, 1 skipped. One failure was this change's: `portfolio.spec.ts` "overview" still looked for "Calculated" in the heading; it now reads the statement and the tagline, and passed when run again. The other two are the workspace's open-hole cases that ADR-0089 left stale (amendment 17's evidence names them).
- **UNVERIFIED:** real phones and tablets, Safari and Firefox, and the lead's screen.

## Amendment 20, 2026-11-13 (the hero's words leave five seconds after they load in)

**Context.** The lead sent a recording of Anduril's hero, where the words are taken away after a few seconds and the video plays alone, and asked: "after it loads in, keep it there for like 5 seconds and have it disappear with this style animation". In the recording every line loses its characters from the end, the last few as random letters, the upper lines a little ahead; the block is gone in about half a second and the mark goes last.

**Decision.**
- Five seconds after the load-in has ended, with the page still at its top, the statement, the tagline and the two small lines are untyped that way, then the mark in the row fades. The clip then plays alone, with The Basement's mark still in its corner.
- The five seconds count only while the page is at its top, so a visitor who has scrolled into the tour finds the words on the way back; they leave five seconds after that.
- The words stay in the page, invisible, so a screen reader still reads the heading. The Explore button leaves the tab order with them.
- A visitor who asked for reduced motion keeps the words.
- It reuses the load-in's copies and windows, run backwards (`prepareOutro` in `components/intro-text.ts`; `components/home/hero-outro.tsx` starts it; ADR-0070 amendment 3).

**Evidence.** On 2026-11-13, in the browser against the dev server at 1280 by 720: the load-in ended 2.5 s after the page was asked for, the words began to leave 5.1 s later and were gone 1.0 s after that. Afterwards five elements carried `data-outro-done` at opacity 0, the heading still held its text, the Explore button was hidden and The Basement's mark was at opacity 1; no page errors. A contact sheet of the exit at ten frames a second was looked at beside the lead's recording. `npm run typecheck` clean; `npm test` 248 passed, 1 skipped; `intro.spec.ts` (with a new case for this), `home.spec.ts` and `tour.spec.ts` against the dev server: 22 of 22. UNVERIFIED: the motion on a real graphics card and on phones.

## Amendment 21, 2026-11-13 (the Explore button leaves; the statement is reworded)

**Context.** Seeing amendments 19 and 20 on the page, the lead asked to "get rid of the explore button now" and, of the statement, "can we also change this to something else ... I like the message tho."

**Decision.**
- **The Explore button is removed** from the hero, with its component, its styles and its two browser cases. The row's right side is the one monospace line.
- **The statement reads** "Anisotropy / one engineering platform / for composite theory / and real test data". It says what the earlier one said, without "bringing ... into". The wording is one proposal; three others were given to the lead to choose from.

**Evidence.** On 2026-11-13 against the dev server: the hero holds no button; a screenshot at 1440 px was looked at; no page errors at 1440 and 390 px. `npm run typecheck` clean; `npm test` 248 passed, 1 skipped; `intro.spec.ts`, `home.spec.ts`, `tour.spec.ts` and the overview case of `portfolio.spec.ts`: 22 of 22.

## Amendment 22, 2026-11-13 ("Scroll to explore" comes back, after the words have left)

**Context.** Amendment 21 removed the Explore button from the hero's row. With the exit of amendment 20 in place the lead asked: "after it all disappears have the scroll to explore button appear at the bottom of the carbon fiber video centered".

**Decision.** `components/home/scroll-to-explore.tsx` is a button, "Scroll to explore" over a down arrow, in the row's monospace capitals, at the foot of the clip in its middle, on the line the Basement's mark stands on. It cannot be seen, pointed at or focused while the words stand; when the hero carries `data-words="gone"` it fades in, and its arrow dips now and then. A press scrolls the page to the tour, whose first step plays when its stage fills the window (ADR-0084 amendment 5). A visitor who asked for reduced motion keeps the words and has the button from the start, with a still arrow.

**Evidence.** On 2026-11-13 against the dev server at 1440 px: a frame taken after the exit shows the button alone at the foot of the clip, in its middle. `intro.spec.ts`: hidden while the words stand; after the exit visible, within 1 px of the clip's middle and in its lowest quarter; a press brings the tour's stage to the window's top and its first step plays; visible from the start with reduced motion: 4 of 4. `home.spec.ts`, which now counts the hero's one hidden button: 10 of 10. UNVERIFIED: phones, where the button and the Basement's mark share the foot of the clip.

## Amendment 23, 2026-11-13 (the site's pages stand on pure black)

**Context.** With a screenshot of the hero's frame and header the lead asked: "why isnt the background black black?" The page ground was the site's near-black, `#0d0d0d`, since the first dark design; Anduril's pages, which this hero follows, stand on pure black.

**Decision.** On every page with the site's header the page ground, `--bg`, is `#000000`: the header, the hero's frame, the dark bands and the footer. The Services panel's ground becomes `#000000` with it, so the open panel is one surface with the page. Not changed: the workspace, an app whose panels were drawn for `#0d0d0d`; the tour's stage, which continues the 3D view's own lit ground (about `#0b0b0b` at its edges); cards and panels (`#141414` and lighter); the load veil (`#010101`).

**Options considered.** Changing `--bg` for the whole site at `:root`: rejected, it would reach the workspace's panels without a look at each. Only the home hero's frame: rejected, the header and the next dark bands would then differ from it.

**Evidence.** On 2026-11-13 on the dev server at 1440 px: the body's computed ground is `rgb(0, 0, 0)` on `/`, `/about`, `/library` and `/services`, and `rgb(13, 13, 13)` on `/workspace`; screenshots of the home hero, the Mission and Platform bands and the About page were looked at. `home.spec.ts` (which reads the hero's ground as `rgb(0, 0, 0)`), `expansion.spec.ts` and `intro.spec.ts`: 20 of 20. UNVERIFIED: the step from the hero's black frame to the tour stage's ground on a display that shows it, and every inner page beyond the three looked at.

## Amendment 24, 2026-11-13 ("Scroll to explore" as Scale sets it, in the bottom right corner)

**Context.** With a screenshot of Scale's home page the lead asked to "make the scroll to explore button appear in the same position as here and with the same type of box".

**Decision.** The button of amendment 22 moves from the middle of the clip's foot to its bottom right corner, as far in from the right and the foot as the Basement's mark is from the left and the foot. It is set as Scale's: "Scroll to explore" in the site's typeface at 14 px, then a down arrow in a 34 px square with a 1 px white outline and 5 px corners. The arrow no longer dips. On hover or keyboard focus the square fills white and the arrow turns black. When it shows, and what a press does, are unchanged.

**Evidence.** On 2026-11-13 against the dev server at 1440 px: a frame taken after the exit shows the button in the clip's bottom right corner; `intro.spec.ts` reads its distance from the clip's right edge and foot as equal to the mark's from the left edge and foot, the square as 34 by 34 px with a 1 px border and 5 px corners, and a press as bringing the tour's stage to the window's top: 4 of 4. UNVERIFIED: phones.

## Amendment 25, 2026-11-13 (the tour's stage and the 3D view stand on pure black too)

**Context.** Amendment 23 left the tour's stage on the 3D view's own ground, a dark grey that was lighter behind the stack. With a screenshot of it under the hero's black frame the lead asked: "should be all black too?"

**Decision.** The 3D view's backdrop (`Backdrop` in `components/home/laminate-studio.tsx`) draws pure black in place of its grey gradient, in the tour and in the calculator's view. The stage's ground (`--tour-stage-ground`) is `#000000` with only the view's faint pool of light under the stack continued over it, so the view still has no edge; the unpinned tour's ground and the view's card are `#000000` as well. The pool, at most 6% white under the stack, and the stack's contact shadow on it are kept: they are what the stack stands on.

**Evidence.** On 2026-11-13 on the dev server at 1440 by 900: in a screenshot of the stage at its first step the pixels at its four corners and the middle of each side read (0, 0, 0); in one taken part of the way down from the hero the frame under the clip and the stage's top are one black. `npm run typecheck` clean; `npm test` 249 passed, 1 skipped; the cases of `home.spec.ts` and `tour.spec.ts` that load the view and the stage: 13 of 13. UNVERIFIED: the view on a real graphics card, and whether the pool reads as light or as a grey patch on the lead's display.

## Amendment 26, 2026-11-13 (the words leave after three seconds)

**Context.** Of the five seconds the hero's words stood before leaving (amendment 20) the lead said: "lets have the main screen text animate after 3 seconds, it feels too long right now."

**Decision.** The hold is three seconds (`HOLD_MS` in `components/home/hero-outro.tsx`). How it is counted is unchanged: from the end of the load-in, only while the page is at its top, checked every 0.2 s.

**Evidence.** On 2026-11-13 against the dev server: `intro.spec.ts` has the page note when the load-in is over and when the exit's copies appear, and reads the time between them as at least 2.9 s and under 4.2 s: 4 of 4. The run was made while the tour was being rebuilt in the same tree; these cases do not load its new parts.

## Amendment 27, 2026-11-13 (the statement without the name; the name beside the mark)

**Context.** With a screenshot of the hero the lead asked to "get rid of ANISOTROPY above the ONE..." and to "replace where it says composites. calculated. with ANISOTROPY".

**Decision.** The statement is three lines: "one engineering platform / for composite theory / and real test data". The row under it reads the name, the triangle, then the cohort line: "Anisotropy" stands where "Composites. Calculated." stood, in the same setting. The tagline is no longer on the home page; the browser tab's title still carries it. The page's first heading no longer holds the name, which is in the header's logo and now beside the mark.

**Evidence.** On 2026-11-13 against the dev server at 1440 px: a screenshot of the hero was looked at. `intro.spec.ts`, `home.spec.ts` and the overview case of `portfolio.spec.ts`, which read the new words: 15 of 15.

## Amendment 28, 2026-11-13 (the row reads the year, the mark, the name; the cohort goes beside The Basement's mark)

**Context.** The lead: "Maybe lets move anisotropy to the right side of the penrose, and put ESTABLISHED 2026 on the left? I feel like the FALL 2026 LAUNCHPAD COHORT is out of place there... it doesnt say for what cohort nor do I think it should be a main description of the company. unless it goes by the logo in the bottom left right? which is uc san diego the basement, bc the reason I wanted to have it on the site was ... a good flex for credibility when someone first lands on the site."

**Decision.**
- The row under the statement reads "Established 2026" in the small monospace capitals on the triangle's left, and "Anisotropy" in the bold capitals on its right.
- "Fall 2026 Launchpad cohort" leaves the row and stands beside The Basement's mark in the clip's bottom left corner, behind a hairline, so the line says whose cohort it is (ADR-0081). It fades in and out with the mark. On a narrow screen it stands under the mark, and "Scroll to explore" keeps only its square there, its words left for a screen reader.

**Evidence.** On 2026-11-13 against the dev server: screenshots at 1440 px and at 390 px were looked at; the first 390 px one showed the cohort's line running into the button's words, which the narrow-screen rule above removes. `home.spec.ts` (the row's order and words, the cohort beside the mark), `intro.spec.ts` and the overview case of `portfolio.spec.ts`: 10 of 10. UNVERIFIED: "Established 2026" is the lead's statement; the repository holds no record of when the company was established. Permission to show The Basement's mark, as before.

## Amendment 29, 2026-11-13 (the five portraits, a new order, and LinkedIn's mark under the pointer)

**Context.** The lead uploaded five portraits to `public/assets/brand/Headshots/` on `main` and asked, with a recording of another site's card: "put the respective headshots in here ... when hover over it, have the linkedin icon appear circularly in the bottom right. we'll route the links later", and then "put tabassum in the middle, me on the right too".

**Decision.**
- **Portraits.** Each card's frame shows the person's portrait in place of the initials. `scripts/team-photos.py` cuts each original to the frame's 4 by 5 around the person, 800 by 1000 px and 59 to 78 KB, into `public/assets/team/`, the files `lib/team.ts` names. The originals are left where the lead put them; one is 10 MB, and a deploy serves them all.
- **Whose is whose.** Four files carry a first name. The fifth, `IMG_7003.JPG`, is taken to be the lead's own by elimination.
- **Order.** Christopher Valerio, Erik Villa, Tabassum Zaman, Jusung Park, Kai Saucedo. The About page lists the team from the same list, so its order changes too; it does not show the portraits yet.
- **LinkedIn's mark.** A round black badge with the "in" in white comes up in the frame's bottom right corner while the pointer is over a card or the keyboard's focus is in it. No profile address is set yet, so the badge is only drawn and is hidden from a screen reader; when a person's address is put in `lib/team.ts` it becomes the link. Where there is no pointer to hover with, only a badge that is a link is shown.

**Evidence.** On 2026-11-13 against the dev server at 1440 px: the five portraits load at 800 px wide in the new order, and the badge's opacity is 1 on the card under the pointer and 0 on the others; screenshots of the row and of one card under the pointer were looked at. `tests/team.test.ts` (each photo is a file under `public/`): 2 passed. `npm run typecheck` clean.

**UNVERIFIED.**
- **Consent.** Each portrait is added only with that person's consent (the rule in amendment 14's "Portraits and profiles"). The lead supplied the five; whether each person agreed to their portrait on a public site and in a public repository is the lead's to confirm before this is merged.
- That `IMG_7003.JPG` is the lead's portrait.
- LinkedIn's rules for showing its mark; phones and tablets.

## Amendment 30, 2026-11-13 (the year reads "Est. 2026")

**Context.** Seeing amendment 28's row, the lead asked: "maybe just put EST. 2026 to get more symmetry here?"

**Decision.** The line on the triangle's left reads "Est. 2026" in place of "Established 2026", and is set wide (0.27 em between letters) so that it is as long as the name on the other side. The space the tracking leaves after the last figure is taken back, so both sides stand as far from the triangle.

**Evidence.** On 2026-11-13 against the dev server at 1440 px: "Est. 2026" alone measured 101 px beside the name's 138 px; set wide it measures 138 px, and each side stands 34 px from the triangle. A screenshot was looked at. `home.spec.ts` and `intro.spec.ts`: 10 of 10. UNVERIFIED, as before: the year is the lead's statement.

## Amendment 32, 2026-11-13 (the year reads "Est 2026")

**Context.** The lead: "lets try change from est. 2026 to est 2026".

**Decision.** The full stop goes. The space between letters grows from 0.27 em to 0.44 em, so the shorter line is still as long as the name on the triangle's other side (amendment 30).

**Evidence.** On 2026-11-13 against the dev server: at 1440 px the year measures 138.6 px beside the name's 138.3 px, each 34.5 px from the triangle; at 1280 px, 123.3 and 123.5; at 1920 px, 181.6 and 176.8. A screenshot at 1440 px was looked at. `home.spec.ts` and `intro.spec.ts` read "Est 2026" and pass. UNVERIFIED: the year is set in the visitor's own monospace typeface, so its length on Windows and macOS was not measured; and, as before, the year is the lead's statement.

## Amendment 33, 2026-11-14 (after the demo the page is white)

**Context.** The lead, with screenshots of the demo's last beat and of the Mission and Platform bands under it: "the page after the final step of the demo animation should transition to a white background now."

**Decision.** Mission, Platform and What is new take the kit's light ground (`is-light`), as About already had, so every band from the demo to the closing band is white; the footer stays black. The black stage meets the first white band at a plain edge as the page scrolls on from the last beat. This replaces amendment 14's alternation of dark and light bands on the home page.

**Evidence.** On 2026-11-14 against the dev server: screenshots of the three bands at 1440 px were looked at; the cards, tags and rules follow the light variables with no other change. The browser suites listed in ADR-0095 amendment 6: 34 passed, 3 skipped. UNVERIFIED: whether the lead meant an animated change from black to white at the end of the demo, which this does not do.

## Amendment 34, 2026-11-14 (Mission and Services are two short blocks set as the demo's words are; the principles' strip goes)

**Context.** The lead, on the bands under the demo: "I also dont like the layout we're using here. it seems like out of place in terms of theme, font, layout, arrangement type from the previous two pages. I like the blocks: mission, and then the link from there going to the about. 'Learn more about us' instead of what we are building. I dont really know what purpose that | physics at the core... etc... banner is serving, so... the second should be like a stepping stone to the services."

**Decision.**

- On the home page a band's head is no longer the kit's label column and ruled statement. It is set as the demo's words are: a small monospace label, the heading in the demo's weight and tracking, a paragraph, all in the middle of the page. The numbers before the labels go ("Mission", "Services", "Team", "What is new"). The kit itself and the other pages are unchanged.
- Mission keeps its statement; its link reads "Learn more about us" and goes to About. The strip of four principles is removed.
- The second block is the step to the services: the five by name, each a link to its page, and "Explore the services". The five cards with their status marks are removed from the home page; the sentence that says how many are built stays, and each service's page still says which.
- Team and What is new keep their content under the same kind of head.

**Evidence.** On 2026-11-14 against the dev server: screenshots at 1440 px and 390 px were looked at. `home.spec.ts` has a new case for the white ground, the two blocks' links and the heads' place; with `shell.spec.ts`, `expansion.spec.ts`, `intro.spec.ts` and the overview case of `portfolio.spec.ts`: 24 passed, 3 skipped (ADR-0058 amendment 4). `npm test`: 299 tests, 298 passed, 1 skipped. UNVERIFIED: whether the lead wants Team and What is new kept on the home page at all; they were not mentioned.

## Amendment 35, 2026-11-14 (the team's cards lift under the pointer, and the badge and the name go to each person's LinkedIn profile)

**Context.** The lead, with a recording of another site's portrait card and an image of LinkedIn's round logo: "see how it animates like that when hovering over it and also how the linkedin logo appears, use this image and make b&w like that", and gave a profile address for each of the five.

**Decision.**

- Under the pointer, or with the keyboard's focus in the card, the portrait lifts 4 px, grows by a fiftieth and takes a soft shadow, in 0.28 s. Reduced motion keeps it still.
- The round badge of amendment 29 stays black with the mark in white, and is now a link to that person's profile, in a new tab; under the pointer itself it turns white with the mark in black. The name links to the same address.
- The image the lead supplied is not added to the repository: its file name is a stock library's, and the same round mark is drawn from the letters the page already had. LinkedIn's mark is LinkedIn's; it is used only to point at a LinkedIn profile.
- The five addresses are in `lib/team.ts`. The repository's rule is that a profile link is added only with that person's consent (ADR-0057 amendment 1); the lead supplied them, and whether each person agreed is the lead's to confirm before the merge.

**Evidence.** On 2026-11-14 against the dev server: a screenshot of the card under the pointer was looked at. `home.spec.ts` checks the lift, the badge's place, its two states and the five addresses on the badge and the name: 7 of 7. A run that failed first: the name's link covers the whole card and lay over the badge, so the pointer could not reach it; the frame now lies over that link and lets the pointer through everywhere but on the badge. `tests/team.test.ts` checks each address is a LinkedIn profile address. UNVERIFIED: each person's consent; that the five addresses are the right people's (they were not opened).

## Amendment 36, 2026-11-14 (What is new is a feed on light grey)

**Context.** The lead, on the What is new band: "lets make the what is new, feel more like a news feed type of thing. make this section light gray too."

**Decision.** The band's ground is light grey (#f3f3f4). Its three items are white cards, three to a row and one under another below 1024 px, each with its month and what it is about ("Release", "Analysis", "Workspace") on one line, then its title and text. The words of the items are unchanged.

**Evidence.** On 2026-11-14 against the dev server: a screenshot at 1440 px was looked at; `home.spec.ts` checks the ground, the three cards and their lines. `home.spec.ts`: 7 of 7. The other suites of the home page (`demo.spec.ts`, `intro.spec.ts`, `shell.spec.ts`, `expansion.spec.ts`, the overview case of `portfolio.spec.ts`) passed on the run before the badge's last change: 28 passed, 3 skipped (ADR-0058 amendment 4); they were not run again after it. `npm test`: 300 tests, 299 passed, 1 skipped; `npm run build`: exit 0.

## Amendment 37, 2026-11-14 (Mission and Services side by side with a picture each; the team's names without an arrow)

**Context.** The lead, on the two blocks of amendment 34: "lets move the mission to the left and add a placeholder space for an image on the right (rounded corners) and lets also add services to the right and add a placeholder image to the left of it", then "for the placeholder images I was talking about just use the carbon fiber pic for now." On the team's cards: "lets also get rid of the arrow by names; get rid of the 'The team on the About page' button".

**Decision.**

- Mission and Services are each two halves: the words, set from the left edge of their half, and a picture with 20 px corners, 4 to 3. Mission's words are at the left and its picture at the right; Services the other way round. Under 1024 px the picture goes under the words.
- Both pictures are the carbon weave the site already holds (`public/assets/images/carbon-weave.jpg`), in grey, standing in for pictures still to come.
- The team's names keep their links to the profiles and lose the arrow. The link to the About page under the cards is removed; Mission's "Learn more about us" goes there.

**Evidence.** On 2026-11-14 against the dev server: screenshots at 1440 px and 390 px were looked at. `home.spec.ts` checks which side the words and the picture stand on, the corners and the picture's file, and that the names carry no arrow and no link to About follows the cards. `home.spec.ts`, `shell.spec.ts`, `expansion.spec.ts`, `intro.spec.ts`, `demo.spec.ts` and the overview case of `portfolio.spec.ts`: 35 passed, 3 skipped (ADR-0058 amendment 4). `npm test`: 300 tests, 299 passed, 1 skipped. UNVERIFIED: which pictures will replace the stand-ins.


## Amendment 38, 2026-11-14 (the feed's cards are stand-ins: no official items)

**Context.** The lead, on the feed of amendment 36: "there shouldnt be any official items in the what is new newsletter here".

**Decision.** The three items that reported the closed beta, the bending coupons and the chat are taken out of the home page. In their place stand three cards that announce nothing: "Company news", "Product updates" and "Research notes", each marked "Coming soon" with one line saying what will be posted there. The band's sentence reads "News from the team, as it happens." The changelog still records the three changes.

**Evidence.** `home.spec.ts` checks the three stand-ins and that the band names none of the three earlier items; with the overview case of `portfolio.spec.ts`: 8 of 8 against the dev server on 2026-11-14. `npm test`: 300 tests, 299 passed, 1 skipped. UNVERIFIED: whether the lead wanted stand-ins or an empty band; who will decide what is posted there.

## Amendment 39, 2026-11-14 (the two pictures are links and lift as the portraits do; LinkedIn's mark is the lead's picture, in black and white)

**Context.** The lead, of the pictures of amendment 37: "have these images be clickable as well and send to the respective link: about us and services. make this images animate just like our headshots when hovering over them". And of the badge of amendment 35, naming a picture they had uploaded to `public/assets/brand/`: "use this for the linkedin logo (in repo) but make it b&w like how it is in the screenshot".

**Decision.**

- **The pictures are links.** Mission's picture goes to About and Services' to Services, where each band's worded link goes. Under the pointer a picture lifts 4 px, grows by 2 % and takes a shadow, the portraits' own movement; with reduced motion it stays still. The keyboard and a screen reader meet the worded link only (the picture's link is out of the tab order and hidden from assistive technology), so the same place is not offered twice.
- **The badge is the uploaded picture.** The round badge on a portrait is drawn from `round-linkedin-logo-isolated-white-background_469489-985.png`, a blue disc with the white letters on a white square: a little larger than the badge, so the badge's round edge cuts the white away, and through a greyscale and contrast filter, so the disc is black and the letters white. Under the pointer itself it is inverted, white with black letters, as before. The letters drawn by the page until now are removed.

**Evidence.** On 2026-11-14 against the dev server: the hovered picture, the badge and the badge under the pointer were captured and looked at; a press on Mission's picture arrived at `/about`. `home.spec.ts` checks each picture's address, that it is out of the tab order, that it lifts under the pointer, and that the badge is drawn from the uploaded file in greyscale and inverts under the pointer; `home.spec.ts` and `demo.spec.ts`: 18 of 18. UNVERIFIED: where the uploaded picture comes from and under what licence it may be used and kept in a public repository (its name is the kind a stock library gives its files; R-30); whether LinkedIn's brand rules allow its mark to be redrawn in black and white, which was not looked up. The picture reached `main` as commit 1fe1034, uploaded by the lead outside a pull request.

## Amendment 40, 2026-11-14 (each time the clip starts again, the hero's words come in again)

**Context.** The lead, with a recording of the hero's clip playing alone and starting again: "when the hero vid restarts, bring in the text animation sequence again." Since amendment 20 the words were typed in once, at the load, stood and were taken away for good.

**Decision.** Each time the clip starts again (its time is reported earlier than it last was; the clip is 21.5 s long), the words come back the way they first came: typed in by the load-in's copies, the mark rising, the Basement's mark fading in. They stand three seconds and are untyped again, as at the load. This happens only while the words are away, the page is at its top and the tab is showing; a round the visitor was not at the top for is left out, and the next one plays. "Scroll to explore" stays up through the later rounds: the hero keeps `data-words="gone"` from the first time the words leave, and counts the rounds in `data-words-round`. A visitor who asked for reduced motion keeps the words standing, as before.

**Options considered.** Hiding "Scroll to explore" again for each round, as at the load: rejected, the page's one prompt to scroll would come and go every 21 s. Timing the rounds by a clock in place of the clip: rejected, the words would drift from the clip's start when the clip stalls or the tab is away.

**Evidence.** On 2026-11-14 against the dev server: the clip was moved to 1 s before its end and left to start again by itself; the words came back within a frame of its start (the clip at 0.03 s), and the round was captured coming in, standing and gone and looked at. `intro.spec.ts`, 5 of 5: its new case checks that a start of the clip away from the page's top brings nothing, that at the top the words are typed in, stand about three seconds with "Scroll to explore" still up and leave, and that the next start brings them again. `npx tsc --noEmit` clean. UNVERIFIED: Safari and Firefox, and a phone that pauses the clip to save power.

## Amendment 41, 2026-11-14 (the team's head stands on grey and its portraits on white; the feed is empty)

**Context.** The lead, of the page under the demo: "its too much white after mission and services, something needs to change at team. Maybe can just make the screenshotted section gray and the background behind the headshots still white?", with the team band's head in the picture. And of the feed's stand-in cards of amendment 38: "I already asked, this needs to be empty as of right now; we have no published updates for the newsfeed."

**Decision.**

- **The team band.** Its head (the label, the heading, the paragraph and the cohort's line) stands on the feed's light grey, `#f3f3f4`, from one edge of the window to the other; the five portraits under it stay on white. So after two white bands the page goes grey, white, grey.
- **The feed is empty.** The three stand-in cards are removed. The band keeps its label and heading and says "Nothing posted yet. News from the team will appear here."; it holds no card. The list the cards are drawn from is still in `app/page.tsx`, empty: an item added there gets a card and the sentence goes back to "News from the team, as it happens." Amendment 38 had read "no official items" as stand-ins; the lead meant none.

**Evidence.** On 2026-11-14 against the dev server the two bands were captured at 1873 px and at 390 px and looked at. `home.spec.ts`, 7 of 7: it checks the head's grey and that it reaches both edges of the window, that the portraits lie under it on the white band, and that the feed holds no card and says nothing is posted. `npm test`: 304 tests, 303 passed, 1 skipped. UNVERIFIED: whether the one sentence in the empty band is wanted, or the band should say nothing at all.

## Amendment 42, 2026-11-14 (the team band's label stands over the portraits)

**Context.** The lead, with a red circle on the white strip between the grey head of amendment 41 and the first portrait, at the left: "move TEAM to where the red circle is."

**Decision.** The label "Team" leaves the band's grey head and stands on the white under it, over the portraits, at their left edge. The head keeps the heading, the paragraph and the cohort's line.

**Evidence.** On 2026-11-14 against the dev server the band was captured at 1873 px and looked at. `home.spec.ts`, 7 of 7: it checks that the head holds no label, and that "Team" starts at the first portrait's left edge, below the head and above the portraits. `npx tsc --noEmit` clean.

## Amendment 43, 2026-11-14 (one short line under each name)

**Context.** The lead, of the two-seat sentences under the names, with a company's officers page as the reference (a name and a title of a few words): "these descriptions are bad, we just need quick one liners like the reference bios here".

**Decision.** Under each name the home page's card shows one short line: "Co-founder and CEO", "Co-founder, AI architecture", "Fabrication and testing", "Modeling and validation", "Software and UI/UX". Each is the person's role or their technical seat cut short; none is a new title. `lib/team.ts` holds the line (`title`), and `tests/team.test.ts` checks that every word of it is one of the role's or the technical seat's as `docs/brain/people.md` words them. The About page still states both seats in full.

**Evidence.** On 2026-11-14 against the dev server the cards were captured at 1873 px and looked at. `tests/team.test.ts`, 2 of 2. `home.spec.ts`, 7 of 7: it checks the five lines and that each takes one line of text. `npx tsc --noEmit` clean. UNVERIFIED: whether each person is content with their line; they are the drafter's cuts of the recorded seats, for the lead and each person to change.

