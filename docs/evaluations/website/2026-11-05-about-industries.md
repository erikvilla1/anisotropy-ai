# About and Industries after the website audit (2026-11-05)

Part 4 of the plan behind the founder's website audit of 2026-10-31, on `feat/about-industries` stacked on `feat/site-map`
(pull request #118): the About page says what is being built, holds the workflow steps and the roadmap moved from the home
page, keeps the lab sections and ends with the team; every Industries card has a media slot. No decision record: no choice
between alternatives (the audit's items 8 to 11 state the structure).

## Unit tests, types and the build

| Check | Command | Result |
| --- | --- | --- |
| website unit tests | `npm test` | 115 passed, 0 failed, 1 skipped (1 new: `tests/team.test.ts` holds every name and seat in `lib/team.ts` to `docs/brain/people.md` and refuses a contact detail) |
| types | `npm run typecheck` | `tsc --noEmit` clean |
| the static export | `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000 npm run build` | 19 routes prerendered |

## Browser tests

Edge channel on this machine, the built site served by `npx serve out -l 3001`.

| Suite | Command | Result |
| --- | --- | --- |
| expansion and research | `npx playwright test tests/browser/expansion.spec.ts tests/browser/research.spec.ts` | 8 passed, 1 failed, 28.7 s |

The navigation scenario now also asserts, on About, the heading "The team.", five `.team-card`s and the roadmap heading
"Start small. Prove it. Build forward."; the research scenario still finds no machine-learning pitch on About and counts
2 priority and 4 potential cards on Industries, each now with a media slot. The overflow scenario passes at 390 and 768 px
for every route, About and Industries included.

The one failure is `tests/browser/research.spec.ts:27` (4 "Tsai" entries expected in the physics search, 5 found), the
same failure as in [the site-map note](2026-11-05-site-map.md): the search reads fields neither branch changes; not in CI;
UNVERIFIED on `main`.

## What the page says and what backs it

- The intro is the audit's own paragraph (item 8).
- The five parts (design, analysis, testing, fabrication, repair) carry the status of the matching service page in
  `lib/services.ts`; repair has no page and is labelled planned.
- The workflow steps and the roadmap are the home page's text as of `main` 6704f78 (`lib/about-content.ts`); the roadmap's
  first stage now names compression, shear and bending, which the studio supports (ADR-0053); the validation gate no
  longer quotes "10–20 lab coupons", a count no record backs.
- The team cards state the five seats of `docs/brain/people.md` and nothing else; the portraits are empty slots.

## Not checked

- The founder's confirmation that each of the five agrees to appear on the site (ADR-0057 amendment 1) is pending; a card
  is one line of `lib/team.ts`.
- No photo or clip was added; every slot is a labelled placeholder except the two existing lab images.
