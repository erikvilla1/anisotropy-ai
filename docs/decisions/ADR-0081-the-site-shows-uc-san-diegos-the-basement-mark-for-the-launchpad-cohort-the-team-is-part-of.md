# ADR-0081: The site shows UC San Diego's The Basement mark for the Launchpad cohort the team is part of

- Status: Proposed; the mark is shown once, in white on the hero (amendment 1); the mark is replaced by words until written permission is recorded (amendment 2)
- Date: 2026-11-10
- Decided by: Kai Saucedo, software and UI/UX lead (marketing and communications), 2026-11-10; Founder, 2026-11-12 (the audit's decision D14, "accept": the mark is named in words until written permission is recorded here) | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the home page), [ADR-0018](ADR-0018-source-rights-classes.md) (rights of what we publish), `app/page.tsx`, `app/home.css`, `public/assets/partners/`

## Context

The lead states that Anisotropy is part of the Fall 2026 Launchpad cohort at The Basement, UC San Diego, and wants the site to show it: "that's our biggest flex rn in trying to show off this to customers". The lead supplied The Basement's mark (navy and gold on a transparent ground) and asked for it, all white, in the bottom left corner of the home hero, and in a strip of supporters after the Mission section.

The mark belongs to UC San Diego. Whether its use on our site, and in one colour, has been cleared with The Basement has not been checked.

## Options considered

1. The programme named in words only. Not chosen: the lead wants the mark, which visitors recognise at a glance.
2. The mark in its own colours on the dark hero. Rejected: navy on near-black cannot be read.
3. The mark in white on the hero, and in its own colours on a light ground elsewhere. Chosen.

## Decision

Option 3.

- **Files.** `public/assets/partners/uc-san-diego-the-basement.png` is the supplied mark, trimmed (684 by 202 px). `uc-san-diego-the-basement-white.png` is the same shape in white.
- **The hero.** The white mark sits in the hero's bottom left corner, 40 px tall on the page's 32 px margin (32 px tall on phones), under one monospace line: "Part of the Fall 2026 Launchpad cohort". It is an image with the alternative text "UC San Diego, The Basement", and it is not a link.
- **The words.** The site says only that the team is part of the cohort. It does not describe the programme or imply that the university endorses the product.
- **Elsewhere.** The supporters strip and the About section, which also show the mark, are recorded in ADR-0077 amendment 14.

## Why (evidence)

- The cohort: the lead's statement on 2026-11-10. No document is linked here.
- Measured in the browser on 2026-11-10: at 1440 by 900 the badge is at x = 32, its foot 32 px above the hero's foot, and the mark is 135 by 40 px; on a 390 px phone the mark is 108 by 32 px at x = 20. No sideways scroll at either size, and no page errors.
- UNVERIFIED: permission to show the mark, and to show it in white. UC San Diego's brand rules have not been read for this.

## Consequences

- Easier: a visitor sees the programme on the first screen.
- Harder: a third party's mark is now in the public repository and on the site. It must come down, or change, if The Basement or the university asks.

## How we will know it was wrong

- The Basement or UC San Diego asks for the mark to be removed or shown differently.
- The team leaves the programme, or the cohort ends and the line is no longer true as worded.

## Amendment 1, 2026-11-11 (the mark is shown once, in white on the hero)

**Context.** The lead asked for the supporters' strip to be removed (ADR-0077 amendment 31). It was the only place that showed the mark in its own colours.

**Decision.** The mark is shown once, in white, in the hero's bottom left corner. `public/assets/partners/uc-san-diego-the-basement.png`, the colour copy, is deleted because nothing shows it; it is in commit `c28de06`. The About section still names the cohort in words.

**Evidence.** After the change, a search of `app/`, `components/` and `lib/` finds only the white file in use. UNVERIFIED, as before: permission to show the mark, and to show it in white.

## Amendment 2, 2026-11-13 (words in place of the mark until permission is recorded; confirmed by the founder)

**Context.** Permission to show the mark, and to show it in white, was never recorded (the Evidence above and amendment 1 both say UNVERIFIED), and the professional audit of 2026-11-12 found the recoloured mark on the home page's first screen.

**Options.** (1) Ask The Basement for written permission and keep the mark meanwhile: rejected, it would stay on the page without the permission. (2) Name the programme in words until the permission is recorded here: chosen.

**Decision.** Erik's answer of 2026-11-12 to the audit's recommendation "Use words until written permission is recorded in ADR-0081": "accept". The hero's bottom left corner reads "The Basement, UC San Diego" in the hero's small monospace type, in the clip's bottom left corner, with the cohort line beside it (ADR-0077 amendment 28); it fades in and out as the mark did. `public/assets/partners/uc-san-diego-the-basement-white.png` is deleted because nothing shows it; it is in the repository's history. The home page's team band no longer repeats the cohort, so the page names it once. The mark returns only with an amendment here that records the permission.

**Evidence.** `tests/marketing-pages.test.ts` searches `app/`, `components/` and `lib/` and finds no reference to the mark's file; its output is in the pull request. UNVERIFIED: `home.spec.ts` and `intro.spec.ts`, which read the words in place of the image, were updated and not run in this change.
