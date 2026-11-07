# ADR-0070: A page veil after PhysicsX fades out on first load and around header and footer navigation

- Status: Proposed
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0066](ADR-0066-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the redesign after PhysicsX), `components/page-transition.tsx`, `app/layout.tsx`, `app/globals.css`

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
- `npm run typecheck` clean; `npm test` 165 passed, 1 skipped. The whole browser suite against the built site, with the local API: 52 passed, 1 skipped, 5 failed. The five are the stale tests recorded in ADR-0065 and ADR-0067, on pages this change does not touch.

## Consequences

- Easier: the site's page changes feel like PhysicsX's.
- Harder: header and footer navigation now takes 400 ms longer, and every first load is veiled for its first 0.8 s.

## How we will know it was wrong

- Visitors or the team find navigation slow.
- The site's measured first-paint numbers suffer. No measurement yet.
