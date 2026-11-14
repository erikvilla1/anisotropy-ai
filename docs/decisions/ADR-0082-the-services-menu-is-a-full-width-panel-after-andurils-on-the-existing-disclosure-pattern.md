# ADR-0082: The Services menu is a full-width panel after Anduril's, on the existing disclosure pattern

- Status: Proposed
- Date: 2026-11-10
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-10 | Drafted by: Claude Code
- Related: [ADR-0058](ADR-0058-one-name-anisotropy-five-service-pages-under-a-services-menu-the-calculator-on-the-home-page-and-a-contact-page.md) (the Services menu), [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the header), [ADR-0078](ADR-0078-the-site-drops-its-green-accent-every-green-tinted-interface-colour-becomes-the-neutral-grey-of-the-same-lightness.md), `components/services-menu.tsx`, `components/services-menu.css`, `tests/browser/expansion.spec.ts`
- Area: website

## Context

The Services disclosure was a small rounded card under the header item, with five links in 12 px type. The lead: "we need to make the drop down menu part here more cleaner … either we can use something very clean and minimalist … we could use how anduril does it", with a screenshot of anduril.com's "Air" item open. The header is transparent and lies over the home hero.

Anduril's menu, measured at 1440 by 900 on 2026-11-10:
- **Layout.** One opaque black ground behind the header and a full-width panel under it, with 64 px by 32 px padding. A label and a paragraph sit in the left three columns. A list of 18 px links starts at the first nav item's x.
- **The page under it.** A fixed layer blurs it 8 px.
- **Motion.** The panel's height grows in 500 ms, its content fades in over 500 ms after 100 ms, and the layer takes 600 ms in and 300 ms out, all eased `cubic-bezier(0.215, 0.61, 0.355, 1)`. It opens 108 to 172 ms after the pointer arrives and closes 173 to 219 ms after it leaves.
- **Keyboard.** Tab does not enter the panel, and Escape does not close it.

## Options considered

1. Restyle the small card. Rejected: the lead asked for Anduril's kind of menu.
2. A full-width panel that copies Anduril's markup and behaviour as they are. Rejected: its keyboard behaviour, above.
3. A full-width panel with Anduril's layout and timing on the existing disclosure pattern. Chosen.

Within option 3:
- Each row carries the service's status (`statusLabel`), not Anduril's "+". The paragraph beside the list says two are built, two exist in part and one is planned, and the rows show which. The "+" marks the button, and turns into a minus when open.
- The layer over the page is dimmed 55 %, not Anduril's 10 %, because this site has white bands.

## Decision

Option 3, as built in `components/services-menu.tsx` and `components/services-menu.css`.

- **The pattern stays.** The "Services" link to `/services`, a button with `aria-expanded` and `aria-controls`, and a plain list of ordinary links. Each link's status is tied to it with `aria-describedby`, so link names are unchanged.
- **The panel, from 641 px.** Full width under the header, near-black (#080808), with the same ground behind the header while it is open. The page under it is blurred 8 px and dimmed, and a click there closes the menu.
- **Its content, from 1024 px.** On the 12 columns with 32 px margins: a monospace label "SERVICES" with the kit's tick and one paragraph in columns 1 to 4 (the home page's Platform introduction, word for word); the five links at 22/28 px from column 7, where the header's links start; each status in monospace at the right.
- **States.** Hover or keyboard focus fades the other rows to 60 %. The current page has a 1 px rule beside its row.
- **Opening and closing.** It opens on hover after 120 ms and on click, Enter, Space or ArrowDown. It closes 150 ms after the pointer leaves, on Escape, on a click outside, on navigation, and when focus moves elsewhere. Touch pointers never trigger hover.
- **Motion.** Anduril's durations and easing, with a clip in place of the height. None for reduced motion.
- **Up to 640 px.** The five rows sit in place under "Services" in the open mobile navigation, as before, without the card.
- The old `.nav-disclosure` and `.nav-sublist` rules leave `app/globals.css`.

## Why (evidence)

- The Anduril measurements above.
- **Ours, measured on the dev server on 2026-11-10:** the menu opens 126 to 132 ms after the pointer arrives and is fully shown by about 700 ms; it closes 153 to 157 ms after the pointer leaves; at 1440 px the list's x = 736 equals the first header link's x.
- **Behaviour:** 32 scripted checks passed (hover delay, pointer paths, click, keyboard, Escape, the layer click, scrolling, reduced motion, a narrow window), and an emulated touch run at 820 px passed.
- **Screenshots** at 390, 768, 820, 1024, 1440 and 1860 px were looked at.
- **Checks:** `npm run typecheck` clean, also on this commit's tree alone. `tests/browser/expansion.spec.ts` against the dev server: 6 of 6 before the change and 6 of 6 on the final run.
- **Flaky under load:** four other runs of that spec failed while several other jobs loaded the machine (load average 13 to 19). Each failure was a page that had not arrived 5 s after a click on a header link, or a 30 s timeout, including in tests that do not use the menu.
- **UNVERIFIED:** Safari and Firefox; a production build; a real touch device; screen-reader output of the status descriptions; the spec on a quiet machine.

## Consequences

- Easier: the five services read at a glance, with their state, from every page.
- Harder: the panel's sentence is written twice, here and on the home page, and counts the statuses, so both must change together.
- From 641 to 1200 px the header keeps its older, smaller type, so the 22 px panel sits under a much smaller nav.

## How we will know it was wrong

- The lead rejects it at the walkthrough.
- The two menu tests of `expansion.spec.ts` fail on a quiet machine.
- A keyboard or screen-reader user cannot reach or leave the panel.

## Amendment 1, 2026-11-13 (Anduril's panel more closely: no rule under it, no statuses, a plus before each link)

**Context.** With a screenshot of the open panel the lead asked to "get rid of that white line under the black top header box, its faint but visible", then, with a screenshot of Anduril's Lattice panel, "this is also how it should look like, so get rid of the in part, planned, etc..."

**Decision.**
- **No rule under the panel.** Its 1 px bottom border is removed; the panel ends where its ground ends.
- **No status beside a link**, at any width, and no `aria-describedby`. How much of a service exists is still stated on its page and counted in the panel's paragraph, which is unchanged.
- **Anduril's arrangement.** A label, "SERVICES", over each side, in the site's typeface in small semibold capitals without the kit's tick; the paragraph in the text colour at 15/20 px; the links at 20/30 px in medium weight with a plus before each, which is drawn and not read. The list is named by its label.
- **Where the list starts.** From 1201 px, under the header's first link, as Anduril's does. The header's links sit in the middle of the page since ADR-0077 amendment 19, so that place depends on their width: the script measures it when the panel opens and when the window changes, and gives it to the stylesheet as `--services-list-x`. From 1024 to 1200 px the list stays on column 7.

**Options considered.** Keeping the list on the halfway line at every width: rejected, it no longer lines up with the header's links, which is the point of Anduril's panel. Placing the list by a fixed share of the width: rejected, the links' width changes with the typeface loading and the viewport.

**Evidence.** On 2026-11-13 against the dev server, with the panel open on `/about`: at 1440 px the header's first link and the list both start at x = 437, at 1880 px at x = 644; at 1100 px the list is on column 7 (x = 566); at 800 px the two sides stack; the panel's bottom border is 0 px at all four. Screenshots at 1440 px and of the open mobile navigation at 390 px were looked at. `npm run typecheck` clean; the two menu cases of `expansion.spec.ts`, the first with new checks for the border, the statuses, the list's name and its place: 2 of 2, after one failure of the new status check, which had read the paragraph's own words and now reads only the list. UNVERIFIED: a screen reader's reading of the plus (`content: "+" / ""`), Safari and Firefox.

