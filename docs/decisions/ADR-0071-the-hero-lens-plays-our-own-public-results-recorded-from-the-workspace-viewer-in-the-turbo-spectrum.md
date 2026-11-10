# ADR-0071: The hero lens plays our own public results, recorded from the workspace's viewer in the Turbo spectrum

- Status: Proposed; the lens is hidden for now (amendment 1)
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 (the lens showing models of different applications; "try spectrum?" for its colours) | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) amendments 3 and 9 (the hero, the first lens and its removal), [ADR-0069](ADR-0069-the-licensed-hero-clip-stays-out-of-the-public-repository-a-script-makes-its-web-copy-and-the-page-plays-it-when-present.md) (the clip under it), [ADR-0045](ADR-0045-abaqus-without-the-gui-odbaccess-reports-and-an-optional-second-reference.md) (the Abaqus licence), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md) (what stays off the repository), [ADR-0063](ADR-0063-the-viewer-colours-fields-on-the-graphics-card-from-the-packages-values-and-ranges-unlit-for-results-and-lights-the-model-for-presentation-without-external-assets.md) (the viewer's shader), `scripts/hero-lens.ts`, `components/home/hero-lens.tsx`, `lib/hero-lens.ts`, `app/home.css`, `tests/hero-lens.test.ts`, `tests/browser/home.spec.ts`

## Context

After the 3D lens left the hero (ADR-0077 amendment 3), the lead found the hero "empty/spacious" and noted that PhysicsX's "lens is animated". The lead asked for "the abaqus models animated/appearing within the lens … showcasing like different applications", with Abaqus tutorial screenshots as the reference.

- Those screenshots belong to Dassault Systèmes and the tutorials' authors.
- The team's Abaqus licence is a teaching licence. ADR-0045 limits it to "the course and the team comparison only, never a customer deliverable", and the site is neither.
- The team's coupon models stay off this public repository (ADR-0042).
- The repository already holds three public results from our own solver, as browser fixtures:
  - `tests/fixtures/studio`: IM7-UNT-L1, unnotched tension, IM7/8552 [45/0/-45/90]s.
  - `tests/fixtures/studio-bending`: IM7-3PB-L1, three-point bending.
  - `tests/fixtures/studio-plate`: NOM-PLT-L1, a Nominal-Alloy plate under pressure on six supports.
- These were regenerated against an empty coupons root (ADR-0063), so they contain none of the team's models.

## Options considered

1. Abaqus renders or the tutorial images. Rejected: neither licence covers website marketing.
2. Live 3D: the viewer itself running in the hero. Rejected: a WebGL context and about 3 MB of field data on every visit to the home page, for decoration.
3. Pre-recorded clips of our own viewer drawing the three public results. Chosen: our own work and public, so the files can be committed to the repository (unlike the iStock clip, ADR-0069), and a small video is all a visitor loads.
4. For the colours:
   - a. the viewer's own green ramp, which ADR-0078 left behind as a data colour;
   - b. the site's blue-to-orange diverging scale;
   - c. Turbo, the classic blue-to-red spectrum. The lead chose c ("try spectrum?"). It reads as an FEA result at a glance, as in the references.
5. A solid frame showing the recording on its black ground. Tried and rejected on sight: the frame looked pasted on. Chosen instead: the frame dims and blurs the clip behind it like glass, and the recording is screen-blended so its black drops out and only the model shows in colour.

## Decision

Options 3, 4c and 5.

- **The recording.** `scripts/hero-lens.ts` runs against the dev server with Playwright.
  - It opens `/workspace/fea/view` and replays the API from each fixture, without the critical element's frame.
  - It chooses displacement magnitude with 10 contour bands.
  - It records 6 s at 30 frames a second on a 960 by 720 canvas. The camera turns 36° by one mouse drag, and the deformation eases from zero to the viewer's suggested scale over 2.5 s.
  - ffmpeg joins the three clips with 1 s cross-fades. The last clip fades into the first second of the first, so the loop has no jump.
  - It writes `public/assets/hero-lens/lens.mp4` (800 by 600, H.264, fast start, silent), the poster `lens.jpg`, and `components/home/hero-lens.json`, which holds when each model fills the lens. Frames go to the git-ignored `.local/hero-lens/`.
- **The colours.** Only the recording uses Turbo. The script swaps the viewer's two seven-stop ramps for seven Turbo stops, from t = 0.08 to 0.96, in the page's code as it loads. It stops with an error if they are not found. Turbo's near-black ends are left out because they would vanish on the dark ground. The workspace keeps its own colours. The stops come from Google's published polynomial fit of Turbo (Mikhailov, 2019).
- **The lens.** `components/home/hero-lens.tsx` shows the lens on screens 1024 px and wider.
  - It is a 4:3 window with its right edge on the gutter before the copy and its foot 12 px above the headline's middle, under the words.
  - Its width is a quarter of the screen, 240 to 440 px, and less on a short window, so the caption stays clear of the header.
  - Through it, the clip is blurred 6 px and dimmed to 40 %. The recording plays muted and looping on top with `mix-blend-mode: screen`.
  - The lens itself makes no stacking context, so the blend reaches the clip. Its glass, video and caption drift together, at most 14 px over 26 s.
  - The `<video>` is plain HTML for autoplay, as in ADR-0069. Its source is offered only to screens 1024 px and wider that have not asked for reduced motion; reduced motion gets the poster and no drift. The ADR-0069 keeper, now `keepPlaying`, keeps it playing.
- **The caption.** A monospace caption above the lens follows the video's time (`lib/hero-lens.ts`). It names the model on screen: "UNNOTCHED TENSION", "THREE-POINT BENDING" and "PLATE UNDER PRESSURE", with the material and layup or the supports, and "DISPLACEMENT". It shows no result values, because a number on the site needs a run record behind it. The lens is decorative, so it is hidden from assistive technology.
- **A viewer fix found by the recording.** The tension coupon's gripped tab, whose displacement equals the scale's top exactly, showed a speckle of isoline pixels in the workspace's viewer too. The shader now leaves the end lines off within 1/1000 of a band of either end (`components/studio/field-material.ts`). An interior isoline is at least one band from an end, so none is lost.

## Why (evidence)

- The licences: ADR-0045's limit, quoted above. Dassault's and the tutorials' images carry no licence for us.
- The fixtures' public status: ADR-0063 (regenerated against an empty coupons root) and ADR-0038 amendment 1 (IM7 and L1 are the public coupon's codes).
- On 2026-11-07:
  - `npx tsx scripts/hero-lens.ts` wrote a 15.0 s loop of 767 KB and a 19 KB poster in about 2 minutes. A contact sheet at one frame a second shows each model turning and the three cross-fades, the last one back to the first.
  - The speckle on the gripped tab showed in the viewer's Turbo stills before the shader fix and not after it. After the fix, the workspace's own green ramp also showed the tab clean. The workspace was not photographed before the fix; it runs the same shader.
- In the browser on 2026-11-07, with the clip, at 1440 by 900, 1860 by 886 and 1280 by 760:
  - The lens was 360, 395 and 312 px wide, and its caption's top 123, 90 and 89 px from the top, under the 56 px header.
  - The lens played; the caption read "UNNOTCHED TENSION" at 1 s, "THREE-POINT BENDING" at 6.5 s and "PLATE UNDER PRESSURE" at 11.5 s.
  - At 900 px wide the lens was hidden and had no source. With reduced motion it had no source, was paused on its poster and did not drift.
- A build without the hero clip: the lens over the still photo looked as intended.
- Checks:
  - `npm run typecheck` clean.
  - `npm test`: 168 passed, 1 skipped, including `tests/hero-lens.test.ts` (3 of 3).
  - `home.spec.ts` and `studio.spec.ts` against that build: 21 of 21 passed.
- UNVERIFIED: Safari and Firefox, a real phone, and the look on the lead's screen with the real clip.

## Consequences

- Easier: the hero moves even where the licensed clip is missing, as on the live site today. A new application is one entry in `MODELS` and one caption, then one script run.
- Harder: the recording depends on the viewer's markup (the field and contours menus, the deformation scale input) and on the literal ramps in `lib/studio-colors.ts`. The script stops by name if the ramps change, and needs re-running when the viewer's look changes.
- 767 KB of binary in the repository, and again each time it is re-recorded.
- The caption over the lens sits on the clip, as PhysicsX's readouts do. The lens's lower left lies under the end of "Composites." in the headline, as in the mock the lead approved.

## How we will know it was wrong

- The lead or a visitor reads the lens's colours as a claim about a result. The caption would then need the values and a run record, or the lens would need to go.
- The home page's load time or its largest paint gets worse by more than the lens's 767 KB would explain.
- The team gets a licence that covers marketing renders, or results of its own it can publish, and prefers those.

## Amendment 1, 2026-11-10 (the lens hidden for now)

**Context.** The lead asked to "hide the lens thing for now".

**Decision.** The home page no longer renders the lens. Everything that makes it stays in the repository: the component, its styles, the recording, its poster, the timing file and the script. Adding `<HeroLens />` back to the hero in `app/page.tsx` brings it back. Its browser test now checks that the hero has no lens and that the recording is still served.

**Evidence.** On 2026-11-10, against a build without the hero clip and with the local engine running, `home.spec.ts`, `calculator.spec.ts` and `workspace.spec.ts` passed 19 of 19, including the new check. `npm run typecheck` was clean, and `npm test` passed 196 with 1 skipped (after merging main).
