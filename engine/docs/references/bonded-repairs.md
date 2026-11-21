# Bonded repairs

How a bonded patch takes up load, why its numbers move as they do when a repair is changed, and what the repair's page does and does not say (ADR-0130, ADR-0131, ADR-0132, ADR-0136). The repair's assistant answers a question of why, how or what a thing is from these sections, and takes every number from the repair's own report or its solved slice, never from this page.

Status: a draft of 2026-11-21, awaiting the founder's review. Written in our own words. Each section ends with its sources. The three NASA contractor reports of Hart-Smith (1973) are public and were found in NASA's report server under the numbers given; a source marked UNVERIFIED was seen only in a search excerpt or is stated from general knowledge of the field, not read at its section and page.

The page explains a model. The hand calculation is elastic and holds shear in the adhesive only; the solved slice is elastic and adds the peel stress and every ply's stresses. Neither gives the repair's strength.

## Why the shear stress peaks at the ends of a step

<!-- also: shear lag, stress concentration, peak shear, largest shear, highest, end of the step, ends, edge, why at the end, where is the shear, middle of the step, trough, load transfer -->

The adhesive moves load from the laminate into the patch. It can only do that where the two stretch by different amounts, since the adhesive shears by the difference of their displacements. At the end of a step one side has just changed: a ply has ended, so the stack on that side is suddenly less stiff and stretches more than the stack across the bondline. The difference is largest right there, and so is the adhesive's shear stress.

Moving into the step, the load passed across evens the two strains out, and the shear stress falls away. In the model it falls like a hanging chain between the two ends: high at each end, low in the middle. That is why the largest value is always at an end of a step and never inside one, and why the page names the step and the end with the number.

How quickly the stress falls away is set by one length, which grows with the adhesive's thickness and with the stiffness of the two stacks, and shrinks as the adhesive's shear modulus rises. A stiff, thin adhesive between soft stacks moves its load over a very short distance at each end.

Sources: Laminate theory, stepped lap bond. Volkersen, O. (1938), Luftfahrtforschung 15, from p. 41: the shear-lag model of a lap, in which the adherends only stretch and the adhesive only shears. Hart-Smith, L. J. (1973), Adhesive-bonded scarf and stepped-lap joints, NASA CR-112237, public release: the model applied step by step.

## Why a longer step stops helping

<!-- also: step length, longer step, long step, overlap length, longer overlap, how long should a step be, plateau, flat, levels off, no longer changes, stops mattering, short step, minimum step length -->

A step moves its load near its two ends, over the length described above. Once a step is several of those lengths long, its middle carries almost no shear, and the two ends no longer feel each other. Making the step longer then only makes the quiet middle longer: the stresses at the ends stay as they were, and so does the load at which the adhesive reaches its elastic limit. A sweep of the step length shows it as a curve that rises and goes flat, and the page says from which value on it stays within one percent.

A shorter step than that does raise the peak, because the two ends overlap and the middle is still loaded.

This is the elastic model's answer, and it is not a rule for choosing a step length. A repair is given longer steps than the model asks for, for reasons the model does not hold: the adhesive yields at the ends before it fails and needs room to do so; a lightly loaded middle resists creep under a sustained load; a step cut by hand is never exactly its drawn length; and a bond may hold a flaw. The step length of a real repair comes from the repair's design data or the structure's repair manual.

Sources: Laminate theory, stepped lap bond. Hart-Smith, L. J. (1973), Adhesive-bonded double-lap joints, NASA CR-112235, public release: beyond a certain overlap the strength of a lap between uniform adherends no longer grows. The reasons of practice in the last paragraph are stated from general knowledge of the field: UNVERIFIED.

## Why more steps lower the peak

<!-- also: number of steps, how many steps, more steps, fewer steps, one step, plies per step, ply per step, regroup, stiffness jump, scarf, taper, more steps lower the shear, steps and shear -->

Each end of a step is a place where a ply, or a group of plies, ends. The load the adhesive must move there grows with the jump in stiffness: how much the stack on one side changes at that end. Cut the same plies in more steps, with fewer plies ending at each, and every jump is smaller. The same total load crosses the bondline, but it is handed over at more places, a little at each, and the largest shear stress falls.

One step with every ply ending together is the bluntest case. One ply a step is the gentlest a stepped repair can be. A scarf, a smooth taper with no ledges, is where ever more and ever shorter steps lead, which is why a stepped lap behaves partly like a scarf and partly like a plain lap.

More steps also make the repair wider, since each step adds a ledge all round, so more sound laminate is cut away. That is the trade a sweep of the number of steps shows.

Sources: Laminate theory, stepped lap bond and stepped patch repair. Hart-Smith, L. J. (1973), Adhesive-bonded scarf and stepped-lap joints, NASA CR-112237, public release: the stepped lap between the scarf joint and the double lap.

## Why a thicker bondline lowers the peak shear

<!-- also: bondline thickness, adhesive thickness, glue line, thicker adhesive, thinner adhesive, thick bondline, thin bondline, bond line -->

The adhesive's shear stress is its shear modulus times its shear strain, and the strain is the difference of the two stacks' displacements divided by the adhesive's thickness. A thicker layer shears less for the same difference, so it is a softer spring between the two. A softer spring spreads the handing over of load along a longer stretch of each step, and the peak at the ends falls. In the model the peak falls roughly with the square root of the thickness.

The model stops there, and practice does not follow it far. A thick bondline is harder to make without voids, it bends the load path more and so raises the peel stress, and adhesives are qualified at the thickness they are tested at. A bondline thicker than the plies of one step is refused by the repair's reader, since the slice's ledges could not be drawn.

Sources: Laminate theory, stepped lap bond. The limits of practice are stated from general knowledge of the field: UNVERIFIED.

## Peel stress

<!-- also: peel, peeling, through the thickness, through-thickness, normal stress, cleavage, lifts, edge of the patch, tip of the patch, bending, eccentric, no peel in the hand calculation, peel by hand -->

Peel is the adhesive pulled apart across its thickness, not sheared along it. It arises because the load does not run in a straight line through a repair: it steps from the laminate up into the patch, and that offset bends the patch and the laminate. The bending pulls the bondline open near the ends of the patch and of each step. Adhesives carry far less in peel than in shear, and so does a laminate between its plies, so a bond can open in peel at a load the shear stress alone would allow.

The hand calculation has no peel stress: its adherends only stretch and its adhesive only shears. The solved slice does, and reports the largest peel stress and where it is, as a mean over a small square of adhesive, since the stress at a sharp corner of the model grows without limit as the mesh is refined. Where the adhesive's peel strength is stated, the slice also gives the load at which the peel stress reaches it, and says which comes first.

Thin ends lower peel: plies that end one at a time, a patch whose outer plies are its shortest, and cover plies that end alone on the laminate.

Sources: Finite element theory, the repair's slice, what is read back. Goland, M. and Reissner, E. (1944), The stresses in cemented joints, Journal of Applied Mechanics 11, pp. A17 to A27: the bending of a lap whose load path is offset, and the stress across the bond it brings. MIL-HDBK-17-3F, Volume 3 (2002), public release, Chapter 6, adhesive joints: tapering the adherends to lower peel; seen in a search excerpt: UNVERIFIED.

## The load at the adhesive's elastic limit is not the strength

<!-- also: strength, strong enough, failure load, ultimate, how strong, will it fail, fail, break, yield, plastic, ductile, capacity, margin, margin of safety, safe, allowable, restore, restores, design load, limit load, elastic limit -->

The model is linear, so every stress grows in step with the load. The load at the adhesive's elastic limit is the applied load times the adhesive's shear strength over the largest shear stress: the load at which the most stressed point of the bondline first reaches the stress the adhesive yields at.

That is where yielding starts, not where the bond fails. A structural adhesive is ductile in shear. Past its elastic limit the end of the step goes on straining at about the same stress, the yielded zone spreads inward, and the bond keeps taking more load until the adhesive at the end has no strain left to give. The failure load of the bond is therefore higher than this number, and it depends on the adhesive's strain to failure, which the elastic model does not hold.

Nor is the adhesive's shear the only way a repair can fail. The bond can open in peel, a ply of the patch or the laminate can fail, and the laminate can fail between its plies at a ledge. The solved slice reports which of the limits the repair states is reached first as the load grows.

So the page gives the largest bondline shear, the load at the adhesive's elastic limit and what comes first in the slice, and no strength, verdict or margin. A sweep's pick is worded the same way: the adhesive is still elastic at the load named.

Sources: Laminate theory, stepped lap bond. Hart-Smith, L. J. (1973), Adhesive-bonded double-lap joints, NASA CR-112235, public release: the strength of a bond whose adhesive yields, from its elastic and plastic shear strains.

## Cover plies

<!-- also: cover ply, overply, over-ply, extra ply, extra plies, sealing ply, cover overlap, overlap of the cover, doubler -->

Cover plies are laid over a flush patch and run past the repair's edge onto the sound laminate by the cover's overlap. They close the top of the bondline against the weather and against handling, and they give the load a first, gentle step into the repair: under the overlap only the thin cover is bonded to the whole laminate, so little load moves there.

In the model the overlap is one more step of the lap, the outermost. Its end on the laminate is a thin end, which keeps the shear there low, but it is also where the cover lifts: in the example repair the slice finds its largest peel stress in the adhesive under the cover plies. A longer overlap moves that end outward and makes the repair wider. In the hand calculation of the example repair it does not change the largest shear at all over the range a sweep tries, since that peak sits on the ledges and not under the cover.

A patch bonded on top of the laminate has no cover plies in the repair's description.

Sources: Laminate theory, stepped patch repair. Finite element theory, the repair's slice. What cover plies are for in practice is stated from general knowledge of the field: UNVERIFIED.

## Flush and external patches

<!-- also: flush, flush repair, external patch, patch on top, bonded on top, doubler, scarf repair, stepped repair, which kind, kind of repair, hole -->

A flush repair cuts the damage out in steps and lays the patch into the cut, ply for ply, so the surface is restored and each patch ply sits level with the laminate ply it replaces. The load passes across the ledges with only a small offset, so bending and peel stay low. It is the repair for a surface that must stay smooth and for a laminate that carries real load, and it costs the most sound material and work.

An external patch is made flat and bonded on top, over a hole cut through the damage. Nothing is cut in steps; the patch's own plies end in steps on its outside, longest on the bondline. It is quicker and removes less, but the whole load must climb out of the laminate into a patch that sits above it. That offset bends the patch and raises the peel stress at its edges, and beside the hole the laminate carries nothing.

In the description the two differ in what is stated. A flush patch takes the angles of the plies removed unless its own layup is listed; an external patch's layup is always listed, from the laminate upward, with its overlap past the hole's edge.

Sources: Laminate theory, stepped patch repair. Goland, M. and Reissner, E. (1944), The stresses in cemented joints, Journal of Applied Mechanics 11, pp. A17 to A27: the bending an offset load path brings. Where each kind is used is stated from general knowledge of the field: UNVERIFIED.

## A patch as stiff as the laminate

<!-- also: stiffness, stiffness match, matching, stiff patch, soft patch, stiffer, softer, patch layup, patch angles, own layup, imbalance, unbalanced -->

A bond works best when the two sides stretch alike. Where the patch and the laminate under it are equally stiff, the two ends of a step share its load evenly. Where one is stiffer, the load crowds to one end, the end where the softer side carries the most, and the peak there rises above what an even bond would see.

A flush patch that takes the angles of the plies removed puts back, ledge by ledge, the stiffness that was cut away, which is the even case. A patch with its own layup, softer or stiffer than what it replaces, shifts the peak. A much stiffer patch also draws load toward the repair from the laminate around it, which the slice, one line through the repair, does not see.

A ply at an angle counts in these stiffnesses for what it carries inside the bonded stack, held from shearing by the plies around it, not for what it would carry alone.

Sources: Laminate theory, stepped patch repair. Hart-Smith, L. J. (1973), Adhesive-bonded double-lap joints, NASA CR-112235, public release: the loss a stiffness imbalance between the adherends brings. That a stiffer patch draws load from the laminate around it is stated from general knowledge of the field: UNVERIFIED.

## What a sweep and its pick mean

<!-- also: sweep, smallest repair, pick, picked, optimise, optimize, best, best step length, vary, range, try values, compare values, table of values, what if -->

A sweep changes one quantity of the repair over a range, the step length, the number of steps the same plies are cut in, the bondline's thickness or an overlap, and works the whole repair by hand at every value. Each row is a complete repair: its width, its largest bondline shear and where, and the load at its adhesive's elastic limit. Values the repair cannot take are listed as refused, with the reason.

With a load named, the sweep marks the rows whose adhesive is still elastic at that load, and picks the smallest repair among them: the narrowest, and among equally wide ones the nearest to the repair as it stands. The pick is then solved as a slice, which adds the peel stress and the plies, and the page says whether the slice holds it: whether the first limit reached there is at or above the load named.

The pick is not a strength and not a design. It is the smallest repair in that table for which this elastic model finds no yielding of the adhesive at that load. For the step length in particular the model can pick a step far shorter than any repair is given, for the reasons under the longer step above.

Sources: Laminate theory, stepped lap bond and stepped patch repair. Finite element theory, the repair's slice.
