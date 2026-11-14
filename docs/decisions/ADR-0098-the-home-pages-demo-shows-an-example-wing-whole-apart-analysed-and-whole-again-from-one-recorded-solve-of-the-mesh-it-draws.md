# ADR-0098: The home page's demo shows an example wing, whole, apart, analysed and whole again, from one recorded solve of the mesh it draws

- Status: Proposed, with amendment 1
- Date: 2026-11-14
- Decided by: Kai Saucedo, software and UI/UX lead, 2026-11-14 (the words are quoted below) | Drafted by: Claude Code
- Related: [ADR-0095](ADR-0095-the-home-page-demonstrates-the-product-the-coupon-workspace-in-a-white-box-under-the-hero-with-one-recorded-run-the-laminate-calculator-and-its-tour-are-archived.md), whose stage, beats, hand-over and scroll rules stay and whose centre model and cards this replaces; ADR-0001 (the engine computes every number in a result); ADR-0067 (new physics comes from CalculiX under our composite layer); ADR-0091 (the product view's words)

## Context

The demo of ADR-0095 showed the coupon workspace: one tension coupon, described, meshed, analysed, reported. On 2026-11-14 the lead wrote: "great concept, but instead of the coupon we'll do an aerospace wing. have it start out as an aerospace wing part, then it expands to multiple parts, shows the fea stresses on each, and then combines into whole again (finish)", with a public news story of a student class's carbon wings as reference. On a first, straight wing: "use a wing like this. right now the shape is hard to even tell its a wing", with pictures of a tapered, swept wing whose ribs and spars show; and "also make the FEA analysis colors like that, not current", of the rainbow those pictures use.

The product analyses coupons today. It does not take a wing.

## Options considered

1. **Draw an example wing from a mesh, solve that very mesh once with CalculiX, and record the answer.** Chosen. Every colour is a computed value on the face it colours.
2. **Paint a stress-like pattern on a drawn wing.** Rejected: a colour on a result is a number, and ADR-0001 allows none that was not computed.
3. **Solve each part alone as a flat plate with our own kernel.** Rejected: a wing's skins and webs carry load together as a box, so loads made up for each part would be invented; the kernel solves flat plates only (ADR-0067).
4. **Keep the coupon.** The lead decided against it.

## Decision

- **The wing** is an example made for the demo, not a design of ours or of anyone's (`scripts/demo-wing.py`): one side of a wing 2133.6 mm long (7 ft, the one number taken from the public story), 450 mm of chord at the root and 225 mm at the tip, the tip's leading edge 400 mm aft of the root's, the NACA 2412 aerofoil, two skins over two spar webs at 25 % and 65 % of the chord and nine ribs. Every part is a laminate of the library's IM7 / 8552.
- **The analysis** is one linear static step of CalculiX 2.21 on the mesh the page draws, as eight-node composite shells: the root held, 500 N pushed up at the sixteen points where the spars meet the upper skin at the ribs. Recorded in `lib/demo-wing.json`: for every face the largest max-stress index over its plies ("strength used"), every node's displacement, and the summary. The script prints its checks on every run.
- **The page** (`components/home/product-demo*.tsx`) draws the wing from that mesh in the four beats of ADR-0095: whole, with its skins seen through; apart into its five parts; coloured by the analysis and bent by the recorded displacement, drawn five times its size and said so; whole again. The colours are a blue-to-red rainbow over the recorded range, not the workspace's scale. The cards name the wing, its parts and layups, the run's stages with the legend and what was found, and the files.
- The coupon's recorded run (`lib/demo-run.json`, `scripts/demo-run.py`) is removed.

## Why (evidence)

Recorded on 2026-11-14 (`python3 scripts/demo-wing.py --solve`; the output is the script's own):

- 1875 nodes and 2084 faces stored; 5827 nodes solved in 7.3 s.
- Governing: the lower skin 26.7 mm from the root, 0.0564 of its strength used, ply 5 (90°) in transverse tension. Tip deflection 33.14 mm, 1.55 % of the span.
- Balance: the span cell beside the root carries 500.62 N for 500 N applied; the other 39 cells are within 0.04 % of the load outboard of them.
- Signs: 80 mm from the root the upper skin is at -28.43 MPa along the span and the lower at +23.76 MPa, averaged through the laminate. A beam estimate with the whole section gives -27.86 and +22.84 MPa.
- Ply axes: the script's ply-axis stresses differ from CalculiX's own local print by at most 5.0e-05 MPa at 120,448 points; patches with unsymmetric layups match the engine's laminate theory to 4.1e-05 MPa.
- The load: one linear buckling step on this mesh put the upper skin's first buckling at 1099 N; the example load is the largest of 250, 500, 750 and 1000 N under 0.6 of that.
- Page: `npm test` 300 tests, 299 passed, 1 skipped (the record whole and consistent, the clock, the words against the banned terms); `demo.spec.ts`, `home.spec.ts` and `intro.spec.ts` against the dev server, 22 of 22; screenshots of the four beats at 1440 px were looked at.

UNVERIFIED: the buckling factor (the mesh was not refined for it); mesh convergence of the peak values, which sit beside the held root; G13 and G23, taken from the public coupon example because the primary dataset has none (the library's second dataset changes no part's largest value in its first three figures); a real graphics card, Safari and Firefox.

## Consequences

- **The demo is ahead of the product.** It shows a wing analysed part by part; the workspace takes coupons. Since ADR-0095 amendment 6 the page also does not say that what it shows is a recorded example. Both are the lead's choices and are for the founder to weigh with the pull request (R-29).
- The step does not cover buckling, large deflection, the bonds between parts, interlaminar failure or damage after first ply failure. Strengths are test means, not allowables. The page states none of this.
- In the skins, 0° runs along the span, so it crosses the swept spars at about 9° and 7°.
- The record can fall behind the script or the library (R-28). Recording needs CalculiX and `uv`; CI does not re-record it.
- The rainbow is the demo's alone; the workspace keeps its own scale.

## How we will know it was wrong

A visitor or a reviewer takes the wing for something the workspace does today; an engineer finds a number on the page that the recorded analysis does not support; or the founder prefers the product's own coupon.

## Amendment 1, 2026-11-14 (the wing is drawn as a part, it stays in the window, and once the demo has played it can be turned by hand)

**Context.** The lead, on the demo running on their machine: "this part needs to look more realistic and less cartoon-y / low quality"; "It is frequently out of the frame"; "also why the grid boxes?", of the faces each drawn in one colour with the mesh's lines over them; and "when on this final step after animation demo complete, can we make the part rotate-able by clicking and rotating."

**Decision.**

- **Drawn as one surface.** A node's normal and its colour are the averages of the faces of its part that meet there, so a skin is lit as a curved surface and the colours run smoothly from face to face, as analysis programs draw an averaged field. The record itself still holds one value a face, and the stated numbers are unchanged. The mesh's lines show only while the wing is apart and bare.
- **Lit as a part.** A key light, a soft fill, a highlight and a sheen at glancing angles, all in the shader; the bare carbon dark and glossy, the colours matt. The view's angle is 27° in place of 20°, so the near end is larger than the far one.
- **In the window.** The wing's size follows the window's width up to a window 1.6 times as wide as tall, and its height beyond that; the poses are a little smaller and lower.
- **Turned by hand.** Once the demo has played through (and where it does not play, with reduced motion or on a small window), a drag that starts on the stage, not on a card or the words, turns the wing about its upright axis and tips it. A small line says so. A finger's drag scrolls the page as before.

**Evidence.** On 2026-11-14 against the dev server: the four beats were captured at 1440 by 900 and at 1894 by 831, the shape of the lead's window, and looked at: the wing is whole in the window in each, and no face's edge shows under the colours. `demo.spec.ts`, 11 of 11: its analysis case now drags on the finished stage and checks that the drawing changes and that the stage cannot be turned before the last beat. `npm test`: 300 tests, 299 passed, 1 skipped. `npx tsc --noEmit` clean. UNVERIFIED: a real graphics card (the container draws in software), Safari and Firefox; whether the lead finds it realistic enough.

## Amendment 2, 2026-11-14 (while the wing is held, its axes show and the words step back)

**Context.** The lead, of the finished stage: "when I click and drag this, have a x-y-z coord fade in for the duration of the hold, and fade out upon release. also when holding, have the text fade out and disappear for the duration of the hold, have it refade back in when let go of click."

**Decision.**

- **Axes while held.** From the press to the release a small triad stands in the stage's lower left corner and turns with the wing: x along the chord, y along the span, z up, the record's own axes (`scripts/demo-wing.py`). It comes in over about 0.2 s and leaves over about 0.3 s. It is a drawing aid only and states no number.
- **The words step back.** For the same time the line that says the wing can be turned, the beat's words and its card fade out, and they come back on release. "The text" was read as all three; the head above the stage stays. Where the demo does not play (reduced motion, a small window) only the line fades, as the beats there lie under the stage, not over the wing.

**Options considered.** Axes that always show once the demo has played: rejected, the lead asked for the hold only. Axes at the wing's root: rejected, they would cover the most loaded place.

**Evidence.** On 2026-11-14 against the dev server: the stage was captured at 1600 by 1000 while held and after release and looked at: held, the triad is in the corner and the words, the card and the line are gone; released, the triad is gone and they are back. `demo.spec.ts`, 11 of 11: its analysis case now holds the stage and checks that the line and the words are hidden while held and shown again after. `npx tsc --noEmit` clean. UNVERIFIED: a real graphics card, Safari and Firefox.

