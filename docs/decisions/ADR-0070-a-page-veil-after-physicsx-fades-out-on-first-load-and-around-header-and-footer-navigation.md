# ADR-0070: A page veil after PhysicsX fades out on first load and around header and footer navigation

- Status: Proposed; the veil is black and the load-in follows Anduril's (amendment 1); only the home page's first load is veiled and nothing fades around navigation (amendment 3)
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07; Founder, 2026-11-12 ("accept": the veil on the home page's first load only, no navigation delay, amendment 3) | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the redesign after PhysicsX), `components/page-transition.tsx`, `app/layout.tsx`, `app/globals.css`

## Context

The UI/UX lead asked for PhysicsX's page transition: a slow pale flash over the whole screen when a header link is pressed, and on the first load. Read from PhysicsX's page on 2026-11-07: a fixed `.page-transition` layer, `rgb(248, 248, 248)`, above everything; a script on internal links cancels the click, plays the layer in and sets `window.location` 400 ms later, and the next page plays it out. PhysicsX reloads the whole page on each link. This site moves between pages without reloading (Next.js `Link`).

## Options considered

1. React's `<ViewTransition>` with the browser's View Transitions API, which Next.js 16 supports. Rejected for this: it animates between the old and the new page rather than holding a veil, and the Next.js guide notes Safari may animate differently and that without browser support nothing animates.
2. A veil layer in the root layout, faded by CSS: on the first load by CSS alone, and around navigation from a header or footer link by a small client component that delays the navigation by 400 ms. Chosen: it is PhysicsX's mechanism and behaves the same in every browser.
3. A veil on every internal link, as PhysicsX has. Not chosen: the lead asked for the header, and in-page links such as the calculator's would flash on every use.

## Decision

Option 2. `components/page-transition.tsx` renders one fixed layer, `#f8f8f8`, that never takes a click.

- **First load:** the layer fades out over 800 ms with CSS alone, so it works before any script runs. The workspace opens without it.
- **Header or footer links:** a click on one that goes to another page of the site is caught in the capture phase and cancelled. Next's `Link` still runs its own handler, which closes the mobile menu, but does not navigate. The layer fades in over 400 ms, the router moves to the page, and the layer fades out over 800 ms. If the page has not arrived after 4 s, the layer lifts anyway.
- **No veil:** modified clicks, new tabs, links with a `#`, links to the current page, back and forward, other links, and visitors who ask for reduced motion.

## Why (evidence)

- The PhysicsX mechanism quoted above, read from its page's script and stylesheet on 2026-11-07.
- Sampled in the browser every 100 ms on 2026-11-07:
  - First load: the layer is opaque at the first paint and gone by about 850 ms.
  - Clicking About in the header: the layer reaches 1.0 at 400 ms, the address becomes `/about` at about 600 ms, and the layer is gone by about 1.4 s.
  - Back, and the workspace's first load: no veil.
  - On a phone, the menu closes after navigating.
- `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. The whole browser suite against the built site, with the local API: 52 passed, 1 skipped, 5 failed. The five are the stale tests recorded in ADR-0076 and ADR-0078, on pages this change does not touch.

## Consequences

- Easier: the site's page changes feel like PhysicsX's.
- Harder: header and footer navigation now takes 400 ms longer, and every first load is veiled for its first 0.8 s.

## How we will know it was wrong

- Visitors or the team find navigation slow.
- The site's measured first-paint numbers suffer. No measurement yet.

## Amendment 1, 2026-11-10 (a black veil and a typed load-in, after Anduril)

**Context.** The lead asked: "upon initial load copy the same load in animations as anduril.com … black fade and text typing in", with a screen recording. The recording was measured frame by frame, and Anduril's script and stylesheet were read, on 2026-11-10.

What the recording shows:
- **The black.** The whole page is black for about 0.12 s, then lifts in about 300 ms, easing out. The brightness over time matches a 300 ms ease-out cubic.
- **The typing.** The first typed character appears about 0.14 s after the lift starts. Lines start about 100 ms apart and type at 34 to 40 characters a second, each on its own. The newest three or four characters show as random capitals for about 0.1 s before they settle. There is no cursor.

What Anduril's code does:
- **First load:** a fixed #010101 layer fades out over 300 ms.
- **Navigation:** it fades in over 350 ms and out over 350 ms.
- **Headings:** they rise from behind their own bottom edge over 1 to 1.5 s.

## Options considered (amendment 1)

1. Keep the pale veil and add typing. Rejected: the lead asked for the black fade.
2. Type the text by script, character by character. Rejected: on the home page the 3D demo blocks scripts for 300 to 460 ms just after load in headless Chromium, and the typing froze.
3. Replace each element's text with one span per character. Rejected: it changes text that React owns, and lines can re-wrap.
4. A copy laid over the page's own text, which is made transparent meanwhile, moved only by transform and opacity animations. Chosen.

## Decision (amendment 1)

- **The veil** is #010101. On first load the page stays black until the text is ready, then lifts in 300 ms. Around header and footer links it fades in over 350 ms and out over 350 ms on the new page, so nothing flashes white between pages.
- **If no script runs,** the stylesheet lifts the veil by itself: at once where scripting is off, after 2 s otherwise.
- **What moves** is marked with an attribute: `data-intro="rise"`, `"type"` or `"fade"`, with an optional `data-intro-delay`. `components/intro-text.ts` holds the timings.
  - `rise`: each line comes up from behind its bottom edge over 1.5 s.
  - `type`: lines start 150 ms after the lift, 100 ms apart, at 38 characters a second but at most 0.53 s a line; each character shows random letters for 110 ms first.
  - `fade`: the block fades in and comes up 15 % of its height.
- **The home hero.** The headline rises and the two paragraphs are typed. No other page is tagged yet.
- **The page's own text is never changed.** It stays in the served HTML, and the copy is hidden from assistive technology and removed when the moves end.
- **Unchanged:** no veil on the workspace and chat, on back and forward, or for reduced motion; a stuck veil still lifts after 4 s.

## Why (evidence, amendment 1)

- The measurements above, from the lead's recording and Anduril's own files.
- **Ours, on the dev server on 2026-11-10:**
  - First load: black from first paint until the lift at 0.58 s in one run and 1.03 s in another. The first typed character comes about 0.15 s after the lift, and typing completes about 1.4 s after it.
  - A header click to About: fully black about 0.33 s after the click, clear about 0.36 s after the page arrives.
  - Back and forward: no veil. With JavaScript off: the page is visible by about 1 s with its text complete.
  - At the end, the paragraph copies are pixel-identical to the page's own text at 1x and 2x.
- **Checks:** `npm run typecheck` clean, also on this commit's tree alone. `tests/browser/intro.spec.ts` 3 of 3 and `tests/browser/home.spec.ts` 9 of 9 against the dev server.
- **Flaky under load:** earlier runs failed while other jobs loaded the machine (load average 17 to 22), in the laminate demo's tests and twice in the load-in's own. The load-in test needs the page's scripts to start within 2 s of first paint.
- **UNVERIFIED:** a production build; a browser with a real graphics card; Safari and Firefox; smoothness at 60 frames a second; a real screen reader.

## Differences from Anduril, on purpose

- Our lines are 40 to 55 characters, not 17 to 21, so with the cap they type faster, at about 75 to 100 characters a second.
- Random letters sit in the real letters' places, so lines do not shift, and punctuation is not scrambled.
- Not copied: the slight scaling of the page during navigation, which would break fixed and sticky parts, and Anduril's yellow progress bar.

## Consequences (amendment 1)

- Every first load is black until the page's scripts and fonts are ready.
- A screenshot taken in the first two or three seconds shows the moves; tests that need the settled page wait for the veil to go idle or ask for reduced motion.

## Amendment 2, 2026-11-10 (the navigation waits for the fade to end)

**Context.** After a header or footer link was clicked, the next page was requested by a 350 ms timer running beside the veil's 350 ms fade to black. The timer could fire one frame before the fade's last frame. Repeating the load-in's browser test three times against the built site, the test failed twice: the veil's opacity was 0.998, not 1, on the last frame before the address changed.

**Decision.** The next page is requested when the veil's fade reports its end (`animationend`), so the old page is fully covered first. A timer 200 ms after the fade's length is the fallback for a browser that never reports the end.

**Evidence.** On 2026-11-10, against the built site: `intro.spec.ts`, `home.spec.ts` and `tour.spec.ts` repeated five times each, 100 of 100 passed.

## Amendment 3, 2026-11-12 (only the home page's first load is veiled; no fade around navigation; confirmed by the founder)

**Context.** The site audit of 2026-11-12 (finding shell-12, decision D10) read from the code: an opaque veil on every marketing page's first load, lifted after the fonts (up to 800 ms) plus 300 ms, or by the stylesheet after 2 s when no script takes over; every header or footer link held back 350 ms, up to 550 ms; the skip link and the focus rings under the veil while the focus is already live; and the veil on the 404 page and on the old `/studio`, `/chat/view` and `/studio/view` addresses.

**Options.** (1) Keep it on every page, add the old addresses to the pages without it, shorten the no-script fallback to 600 ms and raise the skip link over it: the audit's minimum; not chosen. (2) The veil on the home page's first load only, every other page shown from its first paint, and no delay on navigation: the audit's recommendation; chosen.

**Decision.** Option 2, the founder's answer to D10 on 2026-11-12: "accept" ("Keep the veil on the home first load only, and drop the 350 ms navigation delay"). `components/page-transition.tsx` starts in `enter` only when the first page is `/`; the click handler, the `leave` and `arrive` phases and their keyframes in `app/globals.css` are gone, so a link goes to its page at once, and amendment 2 no longer applies. The home's load-in moves (amendment 1) still play as the veil lifts, and reduced motion still gets neither. A focused skip link sits over the veil.

**Evidence.** `npm run build` on 2026-11-12: `out/index.html` carries `page-transition is-enter`; `out/404.html`, `out/about.html`, `out/studio.html` and `out/workspace/fea.html` carry `is-idle`. `tests/browser/intro.spec.ts` now expects no veil after a header link, after Back and on a direct load of `/about`: UNVERIFIED, not run in this change (the browser suites run after the audit's fix groups).

## Amendment 11, 2026-11-13 (the same moves run backwards take the hero's words away)

Numbered 3 on its branch; renumbered when the branch took in main, where an amendment of 2026-11-12 had the number.

**Decision.** `prepareOutro` in `components/intro-text.ts` takes the text of any element that carries `data-outro="type"` away line by line from the end of each line, with the typed line's windows run in reverse, and fades an element that carries `data-outro="fade"` after them. When it ends the elements carry `data-outro-done`, which the stylesheet makes invisible; their text stays in the page. The home hero uses it (ADR-0077 amendment 20).

**A fault found on the way.** The window that shows the random letters was sized with its padding inside its height, so the letters of a large line set tight were cut off below. `.intro-win` now keeps its padding outside (`box-sizing: content-box`); the typed load-in's letters are whole as well.

**Evidence.** Measured during the exit at 1280 px: the random letters' glyph box and the text's own were the same (top 237.1 px, 64 px tall) while the window ended 28 px above their foot; after the change a contact sheet shows the letters whole. The runs are in ADR-0077 amendment 20.

## Amendment 4, 2026-11-13 (the statement is typed too; a text cursor; the mark turns; the Basement's mark joins)

**Context.** After amendment 11 (the exit, written before this one) the lead asked, with a recording of a blinking text cursor: "can we make the inital animation same as the outro animation for the main center text and can we also add that blinking type line at the end", then "can we also make the triangle spin at the outro", and of The Basement's mark in the hero's corner, "this should also be a part of the animations".

**Decision.**
- **The home statement is typed in**, as the small lines are, in place of rising (`data-intro="type"`).
- **A text cursor.** `.type-caret` (`app/intro.css`) is an empty mark after the statement's last word that takes no room and draws a thin line just after the last letter, a little taller than the capitals. It blinks once every 1.06 s, lit for half of it. While a copy plays, `data-intro-caret` gives the copy its own cursor, placed on the page's, which steps with the end of the last line as it is typed or taken away and shows only while that line is on the way. A visitor who asked for reduced motion gets a steady line.
- **The triangle turns once as the words leave** (`data-outro="spin"`): one turn about its middle over the whole exit, slow at first and fast at the end, fading in the last part.
- **The Basement's mark** fades in with the load-in (`data-intro="fade"`) and out with the triangle (`data-outro="fade"`). It stays in the page for a screen reader.

**Options considered.** The cursor inside the typed line's window, which needs no placing: rejected, because the window cuts it off at the line's end, so it sat on the last letter. A typed move for the Basement's mark: not possible, it is an image.

**Evidence.** On 2026-11-13 against the dev server at 1440 px, a recording from first paint to after the exit was cut into contact sheets and looked at: the four lines of the statement are typed with random letters at their ends, the cursor steps along the last line, rests at its end and is lit then dark; at the exit it steps back, the triangle turns and fades, and the Basement's mark is gone with it. The triangle turns about 50% across and 61% down its box, which is the middle of its outline (50.1%, 60.8%) as computed from the path. `npm run typecheck` clean; `intro.spec.ts` (the cursor's place and blink, the copy's cursor, the turn's keyframes, the Basement's mark at opacity 0 after the exit), `home.spec.ts` and `tour.spec.ts`: 21 of 21, the last two after one case each was run again (see below). UNVERIFIED: the motion on a real graphics card, Safari, Firefox and phones.

**Runs.** First run of the three files: 19 of 21. One failure was this change's own test, which asked a visitor with reduced motion for a blinking cursor; corrected. The other, `home.spec.ts` "a load turns on first-ply failure", passed when run again alone and does not touch the hero.

## Amendment 5, 2026-11-13 (the triangle's turn is slower)

**Context.** Seeing amendment 4's recording, the lead asked to "make the triangle spin slower. just one rotation." The turn was one full turn in about 0.9 s that sped up towards its end; the triangle looks the same every third of a turn, so it read as several.

**Decision.** Still one full turn, now in 1.8 s, easing in and out (`cubic-bezier(0.45, 0, 0.55, 1)`), with the fade over its last part. It starts as the first character goes and takes its own time, so the words and the Basement's mark are gone about a second before it is.

**Evidence.** On 2026-11-13 against the dev server at 1440 px, a contact sheet of the exit at ten frames a second was looked at: the words are gone by 0.4 s, the triangle turns evenly until about 1.7 s and fades from about 1.2 s. `intro.spec.ts`: 4 of 4. UNVERIFIED: the motion on a real graphics card and on phones.

## Amendment 6, 2026-11-13 (the triangle fades in with the words)

**Context.** The lead asked: "can we also have the center triangle animate fade in with the other text".

**Decision.** The hero's triangle carries `data-intro="fade"`: it fades in over the load-in's 1.5 s, starting 100 ms after the black lifts, as the Basement's mark does. Until then it was on the page as the black lifted.

**Evidence.** On 2026-11-13 against the dev server: `intro.spec.ts` counts five elements waiting under the black (the three texts, the triangle and the Basement's mark): 4 of 4, run while the scroll tour was being reworked in the same tree, which these cases do not touch. UNVERIFIED: looked at only through that count, not on a recording.

## Amendment 7, 2026-11-13 (the triangle turns anticlockwise)

**Context.** Of amendment 5's turn the lead asked: "counter clockwise too."

**Decision.** The turn ends at -360° in place of 360°: one turn anticlockwise, with the same length, easing and fade.

**Evidence.** On 2026-11-13 against the dev server: `intro.spec.ts` reads the turn's keyframes as 0° to -360°: 4 of 4. A contact sheet of the triangle at ten frames a second was looked at: its top tips to the left first, and it has faded by about 1.4 s.

## Amendment 8, 2026-11-13 (a quarter turn; the first load's lift is longer)

**Context.** Of the triangle's turn the lead asked to "make it do 90º instead of 180º", and with a recording of the page loading, "the initial black fade in make a lil bit longer, its a tad bit too quick rn".

**Decision.**
- **The triangle makes a quarter turn**, 90° anticlockwise, in place of the full turn of amendments 5 and 7 (which the lead read as a half turn: the triangle looks the same every third of a turn). The length, 1.8 s, the easing and the fade are unchanged.
- **The first load lifts out of black in 600 ms** in place of Anduril's 300 ms, with the same easing; the fallback that lifts without a script takes the same. The fades around navigation keep their 350 ms.

**Evidence.** On 2026-11-13 against the dev server at 1440 px, contact sheets of a recording were looked at: the page comes out of black over about half a second, the first letters arriving as it clears; at the exit the triangle's top tips left through a quarter turn and it has faded by about 1.4 s. `intro.spec.ts`, which reads the turn's keyframes as 0° to -90°: 4 of 4. UNVERIFIED: a real graphics card, Safari, Firefox and phones.

## Amendment 9, 2026-11-13 (the triangle leaves first, and comes up as it fades in)

**Context.** With a recording of amendment 8's exit, in which the triangle was still turning after the words had gone, the lead asked: "the triangle should be the first thing to start animating out and should be gone by the time all of the other text is gone", and then "can we also have the triangle appear in an upward movement as it fades in".

**Decision.**
- **On the way out the triangle is first.** Where an element turns (`data-outro="spin"`), the lines begin to go 350 ms after it starts, and its turn ends 150 ms before the last character goes. On the home hero that is a turn of about 0.95 s in place of 1.8 s; the quarter turn, the easing and the fade over its last part are unchanged. The Basement's mark still fades after the lines.
- **On the way in the triangle comes up.** A fade may say how far below its place it starts (`data-intro-shift`), in place of 15% of its height; the hero's triangle starts its own height low.

**Options considered.** Keeping the 1.8 s turn and slowing the lines to outlast it: rejected, the lead did not ask for slower text. Ending the turn with the last character: rejected, "gone by the time" is safer with a margin.

**Evidence.** On 2026-11-13 against the dev server at 1440 px, contact sheets of a recording were looked at: at the exit the triangle is already turned when the first characters go, has faded by about 0.6 s, and the last characters go at about 0.8 s; on the way in it rises as it fades in. `intro.spec.ts` reads the animations' own timing (the triangle's starts at 0 and ends before the last line's; the first line starts 300 ms or more later) and the fade's first keyframe, `translateY(100%)`: 4 of 4; `home.spec.ts`: 10 of 10. UNVERIFIED: a real graphics card, Safari, Firefox and phones.

## Amendment 10, 2026-11-13 (a hitch at the start of the exit: every line lost its last character early)

**Context.** With a recording of amendment 9's exit the lead asked: "why is there like a stutter on the animation out". Cut frame by frame, the recording shows the last character of every line gone in the frame the triangle starts, then nothing for about a third of a second, then the lines leaving.

**Cause.** A leaving line plays the typed line's keyframes backwards after a wait. Each keyframe steps to the next at the end of its interval. While an animation waits, the browser reads a stepped keyframe from the side before its jump, so a waiting line was drawn at its second-to-last step, one character short. Before amendment 9 the waits were under 0.3 s and read as part of the move; the 350 ms the lines now wait for the triangle made it a hitch. Measured with the old keyframes: the seven waiting lines were drawn back 38, 51, 38, 39, 8, 8 and 12 px, their last characters' widths.

**Decision.** The whole line is held over the last thousandth of a typed line's keyframes (`WHOLE_HOLD` in `components/intro-text.ts`), so the end a waiting line is read from is the whole line whichever side it is read from. The load-in uses the same keyframes and ends as before.

**Evidence.** On 2026-11-13 against the dev server: `intro.spec.ts` holds a copy of each line's own animation at its first moment and reads how far the line is drawn back; with the old keyframes the case failed with the seven widths above, with the change every line reads 0. `intro.spec.ts` and `home.spec.ts`: 14 of 14. A contact sheet of a new recording at 25 frames a second was looked at: the lines are whole while the triangle starts to turn, and the first characters go about 0.35 s later. UNVERIFIED: Safari and Firefox, which may read a waiting stepped keyframe differently; the change is safe either way.
