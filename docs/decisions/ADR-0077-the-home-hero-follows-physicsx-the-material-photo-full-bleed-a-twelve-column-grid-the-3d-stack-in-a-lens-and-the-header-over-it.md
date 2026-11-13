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
