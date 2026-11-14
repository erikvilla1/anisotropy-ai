# ADR-0069: The licensed hero clip stays out of the public repository; a script makes its web copy, and the page plays it when present

- Status: Proposed; amendment 1 lets the web copy and its poster be committed (the lead's decision)
- Date: 2026-11-07
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-07 | Drafted by: Claude Code
- Related: [ADR-0077](ADR-0077-the-home-hero-follows-physicsx-the-material-photo-full-bleed-a-twelve-column-grid-the-3d-stack-in-a-lens-and-the-header-over-it.md) (the hero), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md) (what stays out of the repository), `scripts/hero-video.sh`, `app/page.tsx`, `app/home.css`, `.gitignore`
- Area: website

## Context

The UI/UX lead bought an iStock clip on 2026-11-07 for the hero: a slow close-up slide over carbon fiber, iStock 2253430777, 4096 by 2160, 22 s, under iStock's standard licence. The receipt stays with the lead.

The licence lets the clip be used in the website. Its section 3, "No Standalone File Use", forbids uses that let others download or redistribute the file on its own ([iStock Content License Agreement](https://www.istockphoto.com/legal/license-agreement)). This repository is public, so any file committed to it can be downloaded on its own. `AGENTS.md` also keeps originals in `.local/`. The clip is too large to send to a cloud session, so the conversion has to run where the file is.

## Options considered

1. Commit the clip, or a compressed copy, to `public/`. Rejected: the public repository would offer it as a standalone download.
2. Make the repository private. Not this record's decision: the repository is public by design.
3. Keep the clip out of the repository. A script writes its web copy into a git-ignored folder, and the page plays it only when present. Chosen: the clip works on any machine that has it, and the public repository never holds it.
4. Serve the web copy from storage outside the repository, such as the hosted tier's R2 bucket, for the live site. Deferred to a later change: it touches the deploy, which the founder runs.

## Decision

Option 3.

- `scripts/hero-video.sh <original>` copies the original into `.local/media/`. It writes `public/media/hero.mp4`, 1920 px wide, greyscale, silent and in H.264 with fast start. Its last second cross-fades into its first, so the loop has no jump. It also writes `public/media/hero.jpg`, the first frame, as the poster. `/public/media/` is git-ignored.
- `app/page.tsx` checks at build time whether `public/media/hero.mp4` exists. If it does, the hero plays it muted, looping and inline, over the still and under the same shades. The `<video>` is plain HTML, so the browser sees `muted` before scripts run, which autoplay requires. Visitors who ask for reduced motion get no source, only the poster.
- If it does not exist, as in every build from the public repository, the hero shows the still photo, as before.
- The clip loops by its `loop` attribute. `components/home/hero-video-keeper.tsx` also restarts it if a browser ends it anyway, or
  pauses it (as phones can in power saving), and when the tab comes back, at most once a second. Checked on 2026-11-07: the clip
  played past its end 12 s in a row without pausing or ending; a forced pause resumed; with `loop` turned off, the ended clip
  restarted from 0.
- The clip is darker footage than the still, so while it plays the hero's shades are lighter (the left at 65 % rather than 95 %, the
  right at 25 %) and the clip is lifted (`contrast(1.05)`, and `brightness(1.17)`: 1.3 at first, then 10 % darker at the lead's request). The still keeps its shades. Checked on 2026-11-07
  against a stand-in made from the clip's preview frame: with the still's shades the weave was barely visible, as the lead saw on
  the real clip; with these it reads clearly and the headline stays legible.

## Why (evidence)

- The licence's section 3, quoted above.
- On 2026-11-07, a stand-in clip (an 8 s, 4096 by 2160 pan over the hero photo) went through the script. It came out 1920 by 1012, greyscale, 7 s and 549 KB, with a poster. Git saw neither file.
- In the browser, with the web copy present, the clip played muted and looping (`paused` false, its time advancing). With reduced motion, it had no source and stayed paused on the poster.
- A build without the web copy rendered no `<video>` and no `out/media/`, and `home.spec.ts` passed 7 of 7. `npm run typecheck` was clean; `npm test` 165 passed, 1 skipped.
- The real clip has not been through the script yet: its size, its framing and how its loop looks are UNVERIFIED.

## Consequences

- Easier: anyone with the clip runs one command and sees the hero as designed, and the repository holds nothing licensed.
- Harder: the live site shows the still until the web copy is served from outside the repository (option 4). Each machine needs ffmpeg and the original.

## How we will know it was wrong

- The team wants the clip on anisotropy.dev and option 4 is still not built.
- The clip's licence or source changes, for example to footage the team shot itself, which could live in the repository.

## Amendment 1, 2026-11-11 (the web copy and its poster may be committed, so the deployed site plays the clip)

**Context.** The redesign went live on 2026-11-11 and its hero showed the still photo, because the deploy builds from this repository, which does not hold the clip. The lead asked for the clip to be committed: "i bought the license so put it in the public repo, no ones using it and we can make it private later. the website is not even public."

**Decision (the lead's).** `public/media/hero.mp4` and `public/media/hero.jpg`, the web copy and its poster, may be committed. `.gitignore` ignores every other file in `public/media/`, so the original stays out; it stays in `.local/media/`. This takes option 1, rejected on 2026-11-07, for the web copy only. Option 4, storage outside the repository, was offered again and not taken.

**What the lead was told first.**
- Section 3 of the licence, quoted above, has not changed. As the drafter reads it, a file in a public repository is offered as a download on its own, which that section forbids. This is a reading, not legal advice.
- Making the repository private later does not recall copies already cloned, forked or cached.
- The repository is under Erik Villa's account, so a takedown notice would arrive there.

**Evidence.** The clip is not on the drafter's machine; the lead commits the two files from their own. On 2026-11-11, with a stand-in clip in `public/media/` as the committed files will be, the production build exit 0 and its home page holds the video; `home.spec.ts`, `intro.spec.ts`, `tour.spec.ts` and `expansion.spec.ts` against that build: 26 of 26 passed. With the new ignore rule git lists `hero.mp4` and `hero.jpg` as untracked and no other file in the folder. UNVERIFIED: the real clip's size and look on the deployed site.

**How we will know it was wrong.** iStock, Getty Images or GitHub sends a notice about the file. The two files then leave the repository and its history, and option 4 serves the clip.
