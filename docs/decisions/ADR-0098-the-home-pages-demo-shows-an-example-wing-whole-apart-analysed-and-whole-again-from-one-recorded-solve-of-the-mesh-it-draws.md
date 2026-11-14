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

## Amendment 3, 2026-11-14 (beside a beat's words the wing fills the room they leave)

**Context.** The lead, of the second and third beats on a window of 1873 by 866: "now the part is too small and like theres too much space between the part and the left components. same situation when it moves to next animations." Amendment 1 had sized the wing by the window's height on a wide window, so that it stayed in it; on a wide, low window that left it small, with a wide empty strip between it and the words.

**Decision.** In the two beats whose words stand at one side, the wing is no longer a fixed share of the window. Its size and place are found on each frame so that its box on the screen, measured from the mesh's own nodes as the pose turns them, apart and bent as drawn, just fills the room the words leave: from a gap past the words' column to near the stage's far edge, and from 12 % to 90 % of its height (`components/home/product-demo-fit.ts`). So it is as large as the window allows, stands a fixed gap from the words, and cannot leave the window, whatever the window's shape. The poses carry a new measure, `beside`, and the move from the middle to the side eases from the one sizing to the other. The beats with the words under the wing keep amendment 1's sizing.

**Options considered.** A larger fixed share: rejected, it is right for one window's shape only, which is how the wing came to be too small here and out of the window before. Measuring the words' column in the page: not done; the room is computed from the same numbers as the stylesheet's, kept in step by hand and said so in both files.

**Evidence.** On 2026-11-14 against the dev server the two beats and a frame in the middle of each move were captured at 1873 by 866, 1796 by 710 and 1440 by 900 and looked at: the wing fills the room beside the words, the gap to the card is some 45 to 95 px, and it is whole in the window in every frame. `tests/product-demo-fit.test.ts`, 3 of 3: the room's numbers, and that a fitted box lies inside its room, fills it one way and stands in its middle. `demo.spec.ts` and `home.spec.ts`, 18 of 18. `npm test`: 303 tests, 302 passed, 1 skipped. `npx tsc --noEmit` clean. UNVERIFIED: a real graphics card, Safari and Firefox; whether the lead finds the wing too large now on a wide window.

## Amendment 4, 2026-11-14 (the wing is fitted into a room in every beat, over the words as well as beside them)

**Context.** Amendment 3 fitted the wing into the room beside the words in the two side beats and left the two beats with the words under the wing on amendment 1's fixed sizes. The lead then asked for a winglet at the tip (in work, a later amendment): a wing that also rises at its tip would leave the window at a fixed size and place.

**Decision.** A pose no longer carries a size or a place. It names its room: `under`, how far the room is the one over words that stand under the wing, and `beside`, where the room beside words at one side stands, which slides across the stage between the two sides. The view fits the wing's box on the screen into the room on each frame and eases from one room's fit to the next between beats. The room over the words is in the stage's middle, 0.6 of the stage wide (of 1.6 times its height on a wider stage), from a tenth down to a little above where the words begin, which the page measures from the words' blocks themselves. Where no words stand on the stage (reduced motion, a small window) the room is the stage, less a margin, so the wing is larger there than it was.

**Evidence.** On 2026-11-14 against the dev server the four beats were captured at 1873 by 866, 1796 by 710, 1440 by 900 and 1100 by 640, and the stage with reduced motion and at 390 px, and looked at: in each the wing is whole in the window, clear of the words, and about the size it was in the two middle beats. `tests/product-demo-fit.test.ts`, 4 of 4; `tests/product-demo.test.ts` checks which room each pose names and that the pose never jumps. `npm test`: 304 tests, 303 passed, 1 skipped. `demo.spec.ts`, 11 of 11. `npx tsc --noEmit` clean. UNVERIFIED: a real graphics card, Safari and Firefox; a phone in the hand.

## Amendment 5, 2026-11-14 (held: the axes stand beside the wing in white, and only the line that says it can be turned goes)

**Context.** The lead, of amendment 2 running on their machine: "why does the xyz appear so far away I want it near the wing. also, why does the report text and box disappear upon hold? that should stay. also make the xyz all white." Amendment 2 had read "the text" of the first request as the line, the beat's words and its card together; the lead meant the line.

**Decision.** While the wing is held, the three axes are white and stand just to the left of the wing's box on the screen, level with its middle, in place of the stage's corner; they are a little smaller. Only the line "Drag the wing to turn it" fades for the hold. The beat's words and its card stay as they are. This replaces amendment 2's second point and its colours.

**Evidence.** On 2026-11-14 against the dev server at 1873 by 866, the lead's window: the held stage was captured and looked at: the white axes are beside the wing's root end, the report's words and card are there, the line is gone. `demo.spec.ts`: the case that holds and turns the wing now checks that the words and the report's block stay at full strength while held; it passes. `npx tsc --noEmit` clean. UNVERIFIED: a real graphics card, Safari and Firefox.

## Amendment 6, 2026-11-14 (beside the words the wing takes at most about half the stage's width)

**Context.** The lead, of amendment 3 on a window of about 1860 by 860: "this wing is now way too big. make smaller and not as IN UR FACE". Filling all the space the words leave made the wing some 1240 px wide there, against 745 px before amendment 3, which the lead had found too small.

**Decision.** The wing's room beside the words is at most 0.52 of the stage's width and 0.62 of its height, inside the space the words leave, and stands a little nearer the words than the far edge (0.35 of the free width on the words' side). On the lead's window the wing is about 940 px wide and some 150 px from the words' card; on a 1440 px window it is as wide as the space allows, as before. The fit itself, and the beats with the words under the wing, are unchanged.

**Evidence.** On 2026-11-14 against the dev server the two side beats were captured at 1873 by 866 and 1440 by 900 and looked at. `tests/product-demo-fit.test.ts`, 4 of 4: the room's width and height, that it lies in the space the words leave nearer the words, and that the two sides mirror. `npm test`: 304 tests, 303 passed, 1 skipped. UNVERIFIED: whether the lead finds this size right.

## Amendment 7, 2026-11-14 (the wing ends in a winglet, and the analysis view is turned)

**Context.** The lead, with a picture of an airliner's blended winglet for the look: "the wing we have is good, but can we add a wing tip to it like shown in the reference image I added". And of the analysis beat: "the directional angle its pointing in seems a lil weird. bring the far tip a lil closer in to viewer, and 'roll' long way a little bit away from viewer". The numbers in this record's body (nine ribs, 1875 nodes, 2084 faces, a tip deflection of 33.14 mm) are of the wing before the winglet.

**Decision.**

- **The winglet.** The wing inboard of its tip rib is unchanged. From the tip rib the two skins and the two spar webs carry on: the chord line turns up through an arc of 120 mm radius to 75° from the wing's plane (eight cells), then runs straight for 250 mm (eight cells), swept so that the fin's tip, 90 mm of chord, lies 300 mm aft of the wing tip's leading edge. It rises 330.4 mm and reaches 180.6 mm outboard. One rib stands where the bend ends and one closes the fin's tip: eleven ribs in all. The numbers are round ones chosen for the picture; none is measured from the picture or taken from an aircraft (`scripts/demo-wing.py`).
- **Its analysis.** The same linear static step on the mesh the page draws: 2581 stored nodes, 2860 faces. The load is unchanged, 500 N on the wing's own ribs, none on the winglet. The fin's faces are flat and treated as the wing's are. The bend's 352 faces are twisted, so each has its own section with its ply axes laid on the plane of its diagonals; they are allowed to leave that plane by 0.05 of their size under a tolerance of their own (`FLAT_BEND`; measured at most 0.018 in a skin and 0.036 in a web, the surface turning at most 3.43° from the ply axes), and the wing's tolerances are not loosened. A second guard, how near a face's normal may come to the axis its angles are counted from, went from cos 60° to cos 45° (`LEAN`): the winglet's swept faces reach 0.62, the wing's 0.16. The record gains `wing.winglet` (its numbers, each with what it measures, and every station) and `solve.tip_rib_deflection`; `lib/demo-wing.ts` checks the mesh against them.
- **The page's words.** The facts gain a sixth cell, "WINGLET: 0.33 m tall, canted 75°"; the span and the chords stay the wing's own, to the rib where the winglet begins. The ribs are counted from the record. The result's second line reads "pushed up at the wing's ribs; the winglet's tip rises 38 mm": the largest rise is at the fin's tip.
- **The views.** The drawing is centred on the whole mesh in plan. The two beats with the words under the wing are seen a little flatter (pitch 0.62 and 0.60, yaw -0.66 and -0.60) with a slightly larger room, so the wing with its fin is not smaller than before. The analysis beat is turned as the lead asked: yaw 0.98 to 0.76 (the far tip nearer the viewer), pitch 0.82 to 0.96 (rolled away about its length).

**Options considered.** A bend of flat faces, either a pure turn with all the sweep in the fin or alternating wedge and straight cells: both were built and looked at; the first shows a shoulder at the fin's base and the second stepped edges, so the smooth, twisted bend was kept and its exception named. Opening the fin's skins sideways in the view that stands the parts apart: not done; the skins still move straight up and down there, so in the fin they slide past the spars instead of opening.

**Why (evidence).** From the run of 2026-11-14 (CalculiX 2.21, 8013 solved nodes, 2860 elements, about 10 s), as the script prints it and as the work's report gives it:

- The wing is as it was: reaction 500.62 N for 500 N applied; the lower skin at the root governs at 0.05637 in ply 5, transverse tension; each part's largest value is the old record's; the tip rib rises 33.14 mm as before. Stored displacements of the wing's nodes changed by at most 0.01 mm.
- The fin's tip rises 37.98 mm: the tip rib's rise, its slope over the reach and the twist over the aft offset give 37.6 to 37.9 mm. The winglet rides the tip rib as a rigid body to 0.002 mm. Its largest value is 0.0037, in the rear spar just outboard of the tip rib.
- A beam estimate gives 31.46 mm at the tip rib against 32.62 mm solved at its middle.
- With the solver printing each layer's stress in its own axes, the script's ply-axis stresses agree to 9.2e-07 MPa at the bend's points, so the solver holds the axes fixed on the twisted faces too.
- The same deck with a buckling step, run by hand: first factor 1099 N as before, the first four modes all in the wing's upper skin by the root, none in the winglet; 500 N is still no more than 0.6 of it.
- Three runs gave the same record but for the solver's time.
- `npm test`: 314 tests, 313 passed, 1 skipped (a new case checks the winglet stands in the mesh where the record says, and that three kinds of wrong winglet are noticed). `demo.spec.ts` 12 of 12, `intro.spec.ts` 5 of 5, `home.spec.ts` 7 of 7 against the dev server (one case of `home.spec.ts` failed once while another change in the same folder was being reloaded, and passed twice after). `npx tsc --noEmit` clean. The four beats and the frames between them were captured at 1873 by 866, 1440 by 900 and 1100 by 640 and looked at.

UNVERIFIED: the buckling factor (the mesh was not refined for it, and it is run by hand and not recorded); mesh convergence; how much the faces' twist changes the bend's small stresses (no flat-faced bend was solved for comparison); the argument that a swept, tapered bend cannot be made of flat faces without a shoulder or steps, which was not checked by a second method; a real graphics card, Safari and Firefox; whether the lead finds the winglet and the new angle right.

## Amendment 8, 2026-11-14 (the axes stand at the wing's lower left, drawn thin; the way into the workspace is filled as the header's button is)

**Context.** The lead, of amendment 5's axes on the wing with its winglet: "put the xyz in the bottom left corner by the wing not top left corner. also make it thinner, rn it is too thick." With the winglet the wing's box on the screen is tall, so its middle, where the axes stood, lies above the wing's root. And of the last beat's link: "make the open the workspace button, turn white and the arrow change like how the top right header workspace button does."

**Decision.** The axes stand at the lower left corner of the wing's box, just outside it, by the root; their lines are less than half as thick, their heads and letters smaller. "Open the workspace" takes the header button's movement: under the pointer or the keyboard's focus it is filled with white from the right over 0.35 s while its words and arrow turn dark, and its arrow is the header's, pointing right.

**Evidence.** On 2026-11-14 against the dev server at 1873 by 866: the held stage, before and after a turn, and the link at rest, half filled and filled were captured and looked at. The case of `demo.spec.ts` that holds and turns the wing passes. `npx tsc --noEmit` clean. UNVERIFIED: a real graphics card, Safari and Firefox.

