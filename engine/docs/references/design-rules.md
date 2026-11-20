# Design rules for laminates

What the common rules for stacking a laminate ask, why, and how the wing checks them (ADR-0123, ADR-0125). The wing's assistant answers a question about a rule from these sections, and takes the limit and the result from the wing's own check, never from this page (ADR-0127).

Status: a draft of 2026-11-20. The founder kept the four default limits on 2026-11-20 (ADR-0123 amendment 1). Written in our own words. Each section ends with its sources; MIL-HDBK-17-3F, Volume 3 (2002, public release) was read at the sections and pages named; a source marked UNVERIFIED was seen only in a search excerpt, not read at its section and page.

The rules are rules of practice, not physics. A rule not met is a warning: no margin and no verdict changes with it. The limits are the designer's to set in the Design rules box of the Layup step; the defaults are the common ones named below.

## The 10 % rule

<!-- also: ten percent rule, minimum percentage, minimum share, fibre dominated, fiber dominated, each direction, 0 45 90, quasi-isotropic, directions -->

Each of the four directions 0°, +45°, −45° and 90° should hold at least a tenth of the plies. A laminate built this way is carried by its fibres in every direction. Loads the design did not foresee, such as a secondary bending, the load around a fastener hole or a local impact, then meet fibres and not the matrix alone, which is weak across the fibres and in shear.

The wing counts plies, not thickness, as the rule is stated. A ply at any other angle counts in the total but in none of the four directions, and a ply at 135° is the ply at −45°. A wing layup with no 90° plies misses the rule, as the example wing's skin does. Adding a 90° ply to meet it is not always the better wing: the 90° ply carries little of the spanwise load, so it adds weight and can lower a margin, since the other plies then work harder and the 90° ply itself sees the stretch across its fibres.

The default is 10 %, set per wing up to 25 %, since four directions cannot each hold more than a quarter.

Sources: MIL-HDBK-17-3F, Volume 3 (2002), public release: at least 10 % of the plies at each of 0°, +45°, −45° and 90°, section 4.4.1.1 item 5 (p. 4-7); at least four ply angles with 10 % of the plies at each, section 5.6.5.2.1 strong recommendation 2 (p. 5-69); 10 % of the fibres in each direction, section 12.3.1 lesson A-18 (p. 12-13). Laminate theory, design rules of a stack.

## Plies of one angle in a row

<!-- also: consecutive plies, same angle, plies together, stack together, stacking, grouping, clustering, blocking, ply block, how many plies, maximum plies, max plies in a row -->

No more than a few plies of the same angle should lie next to each other. Plies of one angle together act as one thick ply. A crack in the matrix across a thick ply opens wider and releases more energy than one in a thin ply, so a block of plies cracks earlier and starts delaminations more readily, and the stresses between plies at a free edge grow with the block's thickness.

The wing counts the run across the middle of a solid laminate, where the two middle plies touch, since they act together there; it does not count across a sandwich core, which keeps the two faces apart. The default is 4 plies, the handbook's number for tape, which it also states as a group no thicker than 0.8 mm. Thicker plies call for fewer in a row, so a fabric or a heavy tape may need 2 or 3.

Sources: MIL-HDBK-17-3F, Volume 3 (2002), public release: for tape, no more than four plies of one orientation together, a group no thicker than 0.03 in (0.8 mm), and 0.015 in (0.38 mm) for plies running across a free edge, section 5.6.5.2.1 strong recommendation 3 (p. 5-69); no more than 4 plies of one orientation grouped, section 12.3.1 lesson A-21 (p. 12-13). A DLR report on laminate design rules (DLR-IB-FA-BS-2016-173) gives fewer for thicker plies; seen in a search excerpt: UNVERIFIED.

## Balance

<!-- also: balanced, balanced laminate, plus minus pairs, +45 -45, angle pairs, shear coupling, extension shear coupling, A16, A26 -->

A balanced laminate has a −θ ply for every +θ ply, of the same material and thickness. Pulled or pushed in its plane, it does not shear: the terms of its in-plane stiffness that couple stretching to shear, A16 and A26, are zero. An unbalanced skin shears and twists under the bending load of a wing, which may be used on purpose (aeroelastic tailoring) but is otherwise a load the design did not ask for.

Plies at 0° and 90° need no partner. The pair need not sit next to each other for balance; placing them near each other also keeps the bending-twist coupling small.

Sources: Laminate theory, stiffness of a laminate and design rules of a stack; MIL-HDBK-17-3F, Volume 3 (2002), public release: balanced and symmetric where possible, any imbalance near the middle, section 5.6.5.2.1 strong recommendation 4 (p. 5-70), and section 12.3.1 lesson A-17 (p. 12-12); a +θ and −θ pair as close as possible, section 5.6.5.2.2 recommendation 5 (p. 5-70).

## Symmetry

<!-- also: symmetric, symmetric laminate, midplane, mid-plane, mirror, bending coupling, extension bending coupling, B matrix, warp, warping, curing distortion -->

A symmetric laminate mirrors about its middle surface: the ply at a given distance above the middle matches the one at the same distance below in angle, material and thickness. Pulled in its plane it does not bend, since its coupling stiffness B is zero. An unsymmetric laminate also warps as it cools after the cure, because the plies shrink differently across and along their fibres.

In a sandwich, the core must sit in the middle with matching faces on each side. The wing checks every layup this way, the core included.

Sources: Laminate theory, stiffness of a laminate and design rules of a stack; MIL-HDBK-17-3F, Volume 3 (2002), public release: symmetric where possible, plies at equal distances above and below the middle identical in material, thickness and angle, section 5.6.5.2.1 strong recommendation 4 (p. 5-70), and section 12.3.1 lesson A-17 (p. 12-12).

## Ply drops

<!-- also: ply drop, ply drop-off, drop off, dropoff, taper, tapering, run-out, runout, ramp, ply termination, terminating plies, thickness change, change of thickness, zone edge, stagger, staggered -->

Where a layup changes along the span, some plies end. That place is a ply drop. The thicker side carries more load, and the load of the plies that end must pass into the plies that run on, through the matrix between them. At the end of a ply the load path steps, so the matrix there carries a concentration of shear and peel. A drop that is too abrupt starts a delamination there, often under repeated load before any static failure.

Three rules keep a drop gentle, each a warning on the wing's Layup step at every change of layup.

Sources: each rule below names its own.

### How long the run-out is

<!-- also: ply drop ratio, drop ratio, taper ratio, ramp ratio, slope, 20 to 1, 20:1, length per thickness, how gradual -->

The thickness that ends should taper over a run-out many times its height. The wing asks for 20 to 1 by default: dropping 0.5 mm of plies needs 10 mm of run-out, and that length must fit in the thicker side's stretch before the next change. A drop across the main load can be steeper than one along it; some guides allow 10 to 1 there.

Sources: MIL-HDBK-17-3F, Volume 3 (2002), public release: each drop no thicker than 0.010 in (0.25 mm), drops at least 0.20 in apart in the major load direction, which is 20 to 1, section 12.3.1 lesson A-26 (p. 12-13); the millimetres the handbook prints beside the spacing, 0.51 mm, are a slip by a factor of ten, since 0.20 in is about 5 mm. A NASA contractor report of composite laminate design guidelines (contract NAS1-19347, 1997) gives 10 to 1 across the load; seen in a search excerpt, not read: UNVERIFIED.

### How many plies end at one place

<!-- also: plies dropped, dropped at once, plies per drop, at one station, same place, staggering, stagger distance -->

End only a few plies at one place, and stagger the next ones a little further along. A large step concentrates the load the dropped plies shed. The wing allows 2 plies at one place by default, both halves of the laminate counted, which is one ply each side for a symmetric drop. Where the stack drops more, end them in steps, each with its own run-out. The handbook also asks that two plies dropped at one place do not lie next to each other; the wing does not check that yet.

Sources: MIL-HDBK-17-3F, Volume 3 (2002), public release: avoid abrupt ply ends, drop no more than 2 plies per step, and not two plies that lie next to each other, section 12.3.1 lesson A-25 (p. 12-13).

### The outside ply runs on

<!-- also: cover ply, covering ply, outer ply over the drop, internal drop, external drop, plies that run on, continuous ply -->

The thinner stack should be the thicker one with plies taken out from inside, and the outside ply of each face should run on over the ends of the dropped plies. A ply that runs over the drop holds the ends down, protects them from peeling, and keeps the surface smooth. An end on the outside is exposed to peel and to damage. Angle pairs, a +θ with its −θ, are usually dropped together so the thinner stack stays balanced.

Sources: MIL-HDBK-17-3F, Volume 3 (2002), public release: when plies are added, the outside plies should be continuous, section 12.3.1 lesson A-15 (p. 12-12); drops symmetric about the middle, with the shortest ply nearest the outside faces, lesson A-26 (p. 12-13). The NASA contractor report above (angle pairs dropped together): UNVERIFIED.

## Spar caps and webs

<!-- also: spar cap, spar caps, cap layup, web, shear web, spar web, web layup, 0 degree plies in the caps, 45 degree plies in the web, bending, shear flow, where to add plies -->

A wing box carries its bending as spanwise tension in one skin and compression in the other, and its shear and torsion as shear flow round the box. Each part is laid up for the load it carries.

The spar caps, the strips of skin over the webs, are where the box is deepest and its walls stiffest, so most of the bending passes through them. They are rich in 0° plies, whose fibres run along the span. Adding 0° plies to the caps near the root, where the bending is largest, is the usual way to raise the lowest margin of a skin in bending, and every place where those plies end is a ply drop.

The webs carry the vertical shear. Shear in a wall is tension along one diagonal and compression along the other, so ±45° plies, whose fibres lie on those diagonals, carry it best. A thin web buckles in shear before it fails, so its thickness is usually set by buckling, not strength.

The skin between the caps carries the torsion's shear flow and must not buckle under the bending's compression. ±45° plies stiffen it in shear and twist, and a core between two faces raises its bending stiffness, so its buckling load, at little weight.

Sources: Laminate theory, the wing as a thin-walled box and spar caps and layups that change along the span.

## ±45° plies on the outside

<!-- also: outer plies, surface plies, outside plies, face plies, damage tolerance, impact damage, 45 on the outside, bending stiffness, D66 -->

Many designers put a ±45° pair on each face of a skin. The outer plies set most of the laminate's bending stiffness, and ±45° plies there raise the twist stiffness D66 that resists buckling under shear and compression. They also shield the 0° plies, which carry the main load, from impact and surface damage, and an outer ±45° ply splits along its fibres without cutting the load path.

The price is a larger bending-twist coupling, D16 and D26, which keeping the + and − plies close together reduces. The wing does not check this rule yet (ADR-0123).

Sources: MIL-HDBK-17-3F, Volume 3 (2002), public release: at least one ±45° pair at each surface, section 12.3.1 lesson A-24 (p. 12-13); 90° and ±45° plies towards the outside where buckling is critical, lesson A-14 (p. 12-12); shield the main load plies from the surface, section 5.6.5.2.2 recommendation 6 (p. 5-70).

## The angle between neighbouring plies

<!-- also: angle change, adjacent plies, neighbouring plies, ply angle jump, 90 degree change, interlaminar stress between plies -->

Some guides limit how far the angle of one ply may differ from the next, often to 45° or 60°, because the stresses between two plies grow with the difference between them, and a 0° ply on a 90° ply is the worst case at a free edge. The wing does not check this rule: the plan named 60°, one secondary source names 45°, and no primary source was read (ADR-0123).

Sources: common practice; not read in a primary source. MIL-HDBK-17-3F, Volume 3, names no such limit in its laminate guidelines (section 5.6.5.2) or its lessons learned on design (section 12.3.1).
