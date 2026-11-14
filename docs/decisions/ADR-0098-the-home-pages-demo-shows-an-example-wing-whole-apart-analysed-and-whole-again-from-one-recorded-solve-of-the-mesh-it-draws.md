# ADR-0098: The home page's demo shows an example wing, whole, apart, analysed and whole again, from one recorded solve of the mesh it draws

- Status: Proposed
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
