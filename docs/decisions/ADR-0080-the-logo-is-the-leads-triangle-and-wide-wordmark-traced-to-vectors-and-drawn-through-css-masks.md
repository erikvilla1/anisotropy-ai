# ADR-0080: The logo is the lead's triangle and wide wordmark, traced to vectors and drawn through CSS masks

- Status: Proposed; the name is set in Archivo again, as outlines (amendment 1)
- Date: 2026-11-10
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-10 ("swap the current logos … triangle first then anisotropy") | Drafted by: Claude Code
- Related: [ADR-0079](ADR-0079-the-wordmark-is-set-in-archivo-at-weight-800-the-nearest-open-licence-match-to-physicsx-s-lettering.md) (the wordmark this replaces), [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the header), `app/brand.css`, `components/site-shell.tsx`, `public/assets/brand/`, `app/layout.tsx`

## Context

The lead supplied a new logo as three images: an outlined impossible triangle, the name ANISOTROPY in wide capitals, and the two stacked on a dark ground. Each is 2000 by 1125 px; the triangle's artwork is 257 by 211 px and the name's 588 by 46 px, on transparent grounds. The lead asked for the current logos to be swapped for them, in the current orientation (the mark, then the name, on one line), "aesthetically aligned … symmetrically (in height and center)".

The site's sections now alternate dark and light, so the logo has to read on both.

## Options considered

1. The supplied images as they are. Rejected: at 46 px tall the name blurs above three times its header size, and a light-grey image cannot be used on a light ground.
2. The artwork traced to vector files and placed inline in every page. Rejected: the name's outline is 14 KB, twice per page (header and footer), in HTML that is not cached.
3. The artwork traced to vector files and drawn through CSS masks. Chosen: the files are cached, stay sharp at any size, and the logo takes the colour of the text around it, light on dark and dark on light.

## Decision

Option 3.

- **The files.** The two images' transparency was scaled up eight times, cut at half coverage and traced with potrace into `public/assets/brand/anisotropy-triangle.svg` (614 bytes; its outlines straightened to 44 corners, each within 0.7 px of the trace) and `anisotropy-wordmark.svg` (14 KB).
- **The lockup.** `app/brand.css` draws the triangle, then the name, centred on one line. One number, the triangle's height, sets the size: 28 px in the desktop header, 24 px elsewhere, 22 px on phones. The name's letters are half the triangle's height, and the gap between the two is the same half.
- **The word.** The link still holds the text "Anisotropy", hidden from view, for screen readers, search engines and the header's browser test.
- **The tab icon.** `anisotropy-icon.svg` is the triangle in the site's light grey on its near-black ground with rounded corners; `anisotropy-touch-icon.png` is the same at 180 px for phones' home screens. The old mark and logo files are deleted.
- **Archivo.** The name is no longer set in type, so the Archivo font is no longer loaded. This record replaces ADR-0079.

## Why (evidence)

- Rendered at three times size beside the supplied images on 2026-11-10, the traced triangle and name match them in shape and are sharper.
- Measured in the browser at 1440 px: the triangle is 34.1 by 28 px from x = 32; the name is 179 by 14 px from x = 80.1; both are centred on y = 27.5 in the 56 px header. On a 390 px phone: 26.8 by 22 px and 140.6 by 11 px, both centred on y = 34.5.
- `npm run typecheck` clean. `expansion.spec.ts` against the dev server: 6 of 6 passed, including the check that the header's logo link reads "Anisotropy".
- UNVERIFIED: how the hairline triangle reads on a low-resolution screen, and the logo on a light band (no page puts it on one yet).

## Consequences

- Easier: one size number per place; the logo follows the ground's text colour without a second set of files.
- Harder: the vector files are traces of small images. If the lead has the original vector artwork, it should replace them.
- The `@fontsource-variable/archivo` package is no longer imported, and has left `package.json`.

## How we will know it was wrong

- The lead supplies the original vector files and they differ visibly from the traces.
- The triangle's lines break up or vanish at header size on a common screen.

## Amendment 1, 2026-11-11 (the name in heavy capitals again: Archivo at weight 800, as outlines)

**Context.** Going through the draft on a real screen, the lead asked to "switch the ANISOTROPY text to either the one before or like these", showing Anduril's and PhysicsX's logos: heavy, compact capitals beside the mark. "The one before" is ADR-0079's Archivo at weight 800, chosen there as the nearest open-licence match to PhysicsX's lettering.

**Options.**
1. Load the Archivo font again and set the name as text, as ADR-0079 did. Not chosen: a font file for ten letters, and the name can show in the fallback font until it arrives.
2. The same lettering as outlines in a vector file, drawn through the mask the triangle already uses. Chosen.

**Decision.**
- `scripts/brand-wordmark.py` sets ANISOTROPY in Archivo at weight 800 with the font's own kerning and -0.01 em tracking (ADR-0079's setting) and writes the outlines to `public/assets/brand/anisotropy-wordmark.svg`: 3.3 KB, where the trace was 14 KB.
- The font file comes from the npm package `@fontsource/archivo` 5.3.0 (SIL Open Font License 1.1). It is not in the repository and the site does not load it.
- The triangle is unchanged. The name's capitals are two thirds of the triangle's height, and the gap between the two is 0.4 of it.
- The wide wordmark's trace is no longer used; it is in commit `cde1f69`.

**Evidence.** On 2026-11-11, in the browser against the dev server:
- **Header at 1440 px:** the triangle 34.1 by 28 px from x = 32, the name 186.4 by 19.3 px from x = 77.3, both centred on y = 27.5, where the header's links are centred.
- **Footer at 1440 px:** 29.2 by 24 px and 159.7 by 16.5 px, on one centre line.
- **A 390 px phone:** 26.8 by 22 px and 146.4 by 15.2 px, both centred on y = 34.5; no sideways scroll.
- Screenshots of the header over the hero, on the About page and on the phone were looked at. The link's text still reads "Anisotropy".
- **Checks:** `npm run typecheck` clean; `npm test` 221 passed, 1 skipped; the production build without the hero clip exit 0. The browser suite against that build, on the tree that also holds ADR-0077 amendment 16: 77 passed, 2 failed, 1 skipped. The failures were `home.spec.ts` "typing a layup" (two quick fills of the layup were posted separately) and `studio.spec.ts` "the studio checks a setup" (the job still read "running" at the test's 30 s limit); neither test reads the logo or the strip. Re-run, the first passed twice; the second passed alone in 21.7 s and failed twice more beside other tests. UNVERIFIED: that both are only slow in this container; the pull request's CI run decides.
- UNVERIFIED: the logo on a light ground (no page puts it on one), and the lead's own screen.
