# ADR-0079: The wordmark is set in Archivo at weight 800, the nearest open-licence match to PhysicsX's lettering

- Status: Superseded by ADR-0080. Its lettering returns in ADR-0080 amendment 1, as outlines in a vector file; the font is still not loaded
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (amendment 4, the wordmark in capitals), `app/layout.tsx`, `app/globals.css`, `app/home.css`, `package.json`

## Context

The UI/UX lead asked on 2026-11-07, with a picture of PhysicsX's logo: "use same font for anisotropy like this". PhysicsX's wordmark is not set in a font: its page draws it as SVG paths, so there is no typeface to license. It reads as a heavy grotesk in capitals, slightly wide, tightly spaced, with flat ends on the S and the C. In its header the letters are 19.5 px tall beside a 28 px mark, 16 px apart.

## Options considered

All rendered side by side as "ANISOTROPY" against PhysicsX's logo on 2026-11-07; every candidate is under the SIL Open Font License 1.1.

1. DM Sans at 800 or 900, already on the site. Rejected: its round, geometric capitals read softer than the reference.
2. Manrope at 800, already on the site. Rejected: lighter at its heaviest, and rounder.
3. Inter Tight at 800 or 900. Rejected: close, but narrower than the reference.
4. Hanken Grotesk or Schibsted Grotesk at 800. Rejected: Hanken is lighter; Schibsted's I and S have shapes of their own.
5. Archivo at 800. Chosen: the nearest in weight, width and terminals.
6. Draw our own lettering as SVG paths, as PhysicsX does. Not now: it needs a designer and is a later brand step.

## Decision

Option 5. The package `@fontsource-variable/archivo` (^5.3.0) is self-hosted with the site, like DM Sans and Manrope, so no request leaves the site. Its Latin subset is 36 KB, and browsers load only the subsets a page uses. Only the wordmark uses it: Archivo, weight 800, -0.01 em tracking, capitals. On the home header it is 27 px with a 16 px gap to the 28 px mark, which gives a 19 px cap height. Elsewhere it keeps the wordmark's existing sizes.

## Why (evidence)

- The comparison sheet described above (kept outside the repository).
- Measured in the browser on the home header at 1440 px: Archivo loaded, cap height 19 px, mark 28 px, gap 16 px. PhysicsX's are 19.5, 28 and 16.
- Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped; the build ships the Archivo files. Against the built site, `home`, `expansion`, `portfolio` and `workspace`: 18 passed, 1 failed, the stale chat test of ADR-0076.

## Consequences

- Easier: the wordmark has PhysicsX's weight and shape without copying their artwork.
- Harder: the site loads a third font family. The wordmark is live text in a font, not a drawn logo, so it changes if the font package does.

## How we will know it was wrong

- The team commissions drawn lettering for the logo, or picks another typeface.
- The font's download shows up as a problem in the site's load time. No measurement yet.
