# ADR-0093: The site's typeface is Inter, the nearest open-licence match to the Helvetica-like type on Anduril's site

- Status: Proposed
- Date: 2026-11-13
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-13 ("fonts and all") | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) amendment 19 (the home page after Anduril's), [ADR-0080](ADR-0080-the-logo-is-the-leads-triangle-and-wide-wordmark-traced-to-vectors-and-drawn-through-css-masks.md) amendment 4 (the logo's name), `app/globals.css`, `app/layout.tsx`, `package.json`

## Context

The lead asked for the home page to copy Anduril's "fonts and all". Anduril's site is set in a Helvetica-like grotesque: tight capitals of medium weight for the statement, semibold for the links, heavy for the logo's name. That typeface is commercial; its files are not ours to use. The site was set in DM Sans, with Manrope for some headings, both self-hosted.

## Options considered

1. Anduril's own typeface. Rejected: no licence.
2. The visitor's own Helvetica Neue, by name. Rejected as the only choice: it is on Apple devices and not on Windows or Android, so the page would differ by machine. It is kept as the fallback.
3. Inter, self-hosted. Chosen: an open licence (SIL OFL 1.1), every weight from 100 to 900 in one file, and a display cut for large sizes.
4. Other open grotesques (Archivo, used for the logo earlier; TeX Gyre Heros, a Helvetica clone with two weights). Not chosen: Archivo is further from the reference in its capitals, and two weights do not cover the statement, the links and the logo.

## Decision

Option 3. `--font` and `--heading` are both "Inter Variable", then Helvetica Neue, then Arial. `app/layout.tsx` loads `@fontsource-variable/inter/opsz.css`, whose file carries the optical-size axis, so the browser draws the display cut at large sizes by itself. The DM Sans and Manrope packages are removed.

## Why (evidence)

- On 2026-11-13 the home page, About and the laminate workspace were looked at in Inter at 1440 px on the dev server: no sideways scroll, no page errors, and the hero's statement beside the lead's reference screenshot reads as the same kind of type.
- The checks are in ADR-0077 amendment 19.
- No evidence yet: a side-by-side measurement of letter shapes against the reference, the whole browser suite on a production build, and pages not looked at.

## Consequences

- Easier: one family and one file for the whole site, where there were two.
- Harder: Inter is wider than DM Sans at the same size, so a tight row somewhere not yet looked at may wrap or grow.

## How we will know it was wrong

- A page or a workspace panel overflows or wraps badly in Inter.
- The lead finds the type further from the reference than expected on a real screen.
