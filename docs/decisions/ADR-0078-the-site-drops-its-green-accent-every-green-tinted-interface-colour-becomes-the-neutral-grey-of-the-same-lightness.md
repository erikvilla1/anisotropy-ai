# ADR-0078: The site drops its green accent: every green-tinted interface colour becomes the neutral grey of the same lightness; data colours keep theirs

- Status: Proposed
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the monochrome hero), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md) (the studio's colours), [ADR-0018](ADR-0018-source-rights-classes.md) (source rights), `app/globals.css`, `lib/studio-colors.ts`
- Area: website

## Context

The UI/UX lead asked on 2026-11-07: "lets get rid of the green accent". The CEO's website audit of 2026-10-31 says nothing about colour, and the kickoff deck uses no green. The redesign's reference, PhysicsX's hero, is monochrome.

The green was more than one variable. On 2026-11-07, `--accent` (#c1deb5) had 93 uses in 9 stylesheets, and a scan found 307 distinct green-hued colours written out by hand, used 404 times. The base greys (`--bg`, `--panel`, `--line`, `--text`, `--muted`) carried a faint green tint too.

## Options considered

1. Keep the green. Rejected: the lead asked to remove it.
2. Replace it with another hue, such as the deck's orange. Not chosen now: the request is to remove the green, and a new brand colour is a separate decision.
3. Choose a grey for each of the 300 colours by hand. Rejected: slow and error-prone.
4. Turn every green-hued colour (hue 55° to 175°, saturation at least 2 %) into the neutral grey of the same OKLab lightness, keeping its transparency. Chosen: one rule for every colour, and each layer keeps its lightness, so the contrast between layers stays about the same.

## Decision

Option 4, applied to every stylesheet under `app/` and to the interface colours written in eight components (the 3D scenes' axes, edges, dust, backgrounds and lighting, the presentation material, the coupon drawing's outline, mesh and labels, the calculator's axis legend). 532 colour values changed. The root palette is now `--bg` #0d0d0d, `--panel` #141414, `--raised` #1b1b1b, `--line` #2d2d2d, `--text` #efefef, `--muted` #a0a0a0 and `--accent` #d4d4d4.

These keep their colours, because they carry meaning:

- Data: the plies' categorical slots and the field ramps in `lib/studio-colors.ts`, the field gradients in the coupon drawing and on the services pages, and the ply colour fallback.
- The "public domain" rights chip, which is green beside the amber "licensed" chip (ADR-0018).

The studio's pass, ready, done and OK marks used the accent, so they are now light grey; their labels and icons still name the state. The sequential field ramp in the workspace viewer is still green: it is a data colour, and changing it is left open.

## Why (evidence)

- The request, and the counts above from a scan of every stylesheet, component and library file. A second scan after the change finds green only in the kept colours listed above.
- Screenshots of the home page, About, the finite element service page, the materials library and the workspace at 1440 by 900, before and after: no green in the interface, no console errors.
- Checks of 2026-11-07: `npm run typecheck` clean; `npm test` 166 tests, 165 passed, 1 skipped. The whole browser suite against the built site, with the local API for the calculator cases: 52 passed, 1 skipped (the hosted live test), 5 failed. Two are the stale tests of ADR-0076. Three are stale counts on pages this change does not touch: the physics page now says "40 reference cards" where its test expects 39, and the materials tests look for "25 materials".

## Consequences

- Easier: one neutral palette across the site and the workspace, matching the hero; a later brand colour can go into `--accent` alone.
- Harder: states that were green (pass, ready, available) now rely on their labels and icons. The workspace's green field ramp is the one large green left.
- The conversion script is not in the repository; the rule above is enough to repeat it.

## How we will know it was wrong

- The team asks for a brand colour back, or picks a new one.
- Users report missing pass or ready states in the workspace.
