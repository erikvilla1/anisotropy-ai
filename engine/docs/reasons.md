# Reasons behind a result

Short reasons, in words, for why a coupon's result looks the way it does. The assistant answers a question of why from these sections and the result's own numbers (ADR-0102). Each reason follows from an equation in the theory pages, named at its end; nothing here is computed.

Status: a draft of 2026-11-16, not yet reviewed by the founder.

Ply angles are counted from the coupon's length, the direction of the pull: the fibres of a 0-degree ply lie along the pull, and those of a 90-degree ply lie across the width. Each ply's stresses are given in its own fibre axes: σ₁ along the fibres, σ₂ across them, τ₁₂ in shear.

## Why plies at different angles carry different stresses

The plies are bonded, so in the gauge section they stretch together: every ply of an element has the same strain. The stress a ply carries is its own stiffness times that strain, and a ply is far stiffer along its fibres than across them. A 0-degree ply meets the pull with its fibres, so it carries a large stress along the fibres. A 90-degree ply meets the same stretch across its fibres, where it is soft, so it carries a small stress across the fibres. A 45-degree ply sees the stretch partly along, partly across and partly as shear.

This is why the largest tension along the fibres is found in a 0-degree ply when the layup has one, and why the 0-degree plies carry most of the coupon's load.

From: Finite element theory, ply stresses in material axes; Laminate theory, ply stiffness and rotation.

## Why a 90-degree ply is in compression along its fibres when the coupon is pulled

A coupon that is pulled along its length gets narrower. This is the Poisson contraction of the laminate. The fibres of a 90-degree ply lie across the width, so the narrowing shortens them. Fibres are stiff, so a small shortening gives a large compressive stress along the fibres of that ply.

The stretch along the pull also acts on the 90-degree ply, across its fibres, and through the ply's own small Poisson coupling it adds a little tension along the fibres. The contraction wins whenever the laminate contracts more than the ply would on its own across its fibres, which is the usual case and is strongest when the layup has plies near 45 degrees, since they raise the laminate's Poisson ratio.

The compression is not a sign of bending or of an error. Across the width the coupon carries no net force in the gauge section, so this compression is balanced by tension across the width in the other plies.

From: Laminate theory, ply stiffness, rotation and response to loads; Finite element theory, ply stresses in material axes.

## Why a 90-degree ply usually fails first in a tension coupon

The stretch along the pull acts across the fibres of a 90-degree ply. Across the fibres the load is carried by the matrix and by the bond between fibre and matrix, and the strength there, the transverse tensile strength, is a small fraction of the strength along the fibres. All plies share the same strain, so the 90-degree ply reaches its transverse strength while the 0-degree plies are still far from their fibre strength.

The mode is tension across the fibres, a matrix-dominated mode: cracks in the matrix that run along the fibres of that ply. In a layup with no 90-degree ply, the plies furthest from the direction of the pull are usually the first, by tension across the fibres or by shear.

First-ply failure is the onset of damage in one ply. The 0-degree plies still carry most of the load, so it is not the coupon's ultimate strength.

From: Laminate theory, failure; Finite element theory, first-ply failure.

## Why plies at plus and minus 45 degrees carry shear

In the axes of a ply at 45 degrees, the coupon's stretch along the pull and its contraction across the width appear together as a shear strain between the fibre direction and the direction across it. The ply's shear stress is its in-plane shear stiffness times that strain. This is why the largest in-plane shear is found in the plies at plus or minus 45 degrees, and why plies at 0 and 90 degrees carry almost none in the gauge section.

The sign of the shear follows from the ply's axes, not from a different loading: under tension it is negative in a ply at plus 45 degrees and positive in a ply at minus 45 degrees, with the same size in the gauge section. Shear between fibre and matrix is a matrix-dominated mode, judged against the in-plane shear strength.

From: Laminate theory, rotation; Finite element theory, ply stresses in material axes.

## Why the failure criteria give different factors

The maximum stress criterion compares each stress of a ply with its own strength, one at a time: along the fibres, across them, and in shear. It names the mode that is reached first. The Tsai-Hill criterion puts the three stresses into one expression, so when a ply carries more than one of them at once, each one counts. Tsai-Hill is then usually reached a little earlier than maximum stress, and it names no single mode: the combined stresses govern.

When one stress of the governing ply is much larger than the others, compared with their strengths, the two criteria nearly agree. Neither is the truth. They are two models fitted to the same strengths, and the earliest of them is reported as the earliest.

From: Laminate theory, failure.

## What the factor at first-ply failure and the failure index mean

The model is linear, so every stress grows in proportion to the applied loading. The factor of a criterion is the multiple of the applied loading at which the first ply reaches that criterion. A factor above one means the laminate holds at the applied loading by that criterion. A factor of one or less means a ply has failed by it.

The failure index is one divided by the factor: it reaches one at failure. The loading at first-ply failure is the factor times the applied loading, and the force the grip carries then is the factor times its reaction.

From: Finite element theory, first-ply failure; Laminate theory, failure.

## Why the stress is highest at the grips and is reported apart from the answer

A grip clamps the tab, so the material under it cannot get narrower, while the free gauge section beside it does. This mismatch at the edge of a gripped tab adds stress there. In the model the clamp is ideal, a perfectly rigid edge, so the stress at that edge keeps growing as the mesh is refined and settles on no value.

A tension test is accepted when the coupon breaks in the gauge section. The answer is therefore read over the gauge section, from the elements that touch no gripped node. A failure that comes earlier at the edge of a grip is reported beside the answer, never as the answer.

From: Finite element theory, first-ply failure.

## Why the element size changes the numbers

Each element reports the ply stresses at its centre. In the gauge section the stress is nearly uniform, so the value at the centre is the same for a large element or a small one, and the answer moves little with the mesh. Near the edge of a grip the stress changes steeply over a short distance. A smaller element has its centre closer to the edge and reports more of the peak, so the values there rise as the mesh is refined.

The reaction at the grips depends on the stiffness of the whole coupon and changes little with the element size.

From: Finite element theory, recovery and first-ply failure.

## Why the grip's reaction is what it is

Under a stated displacement, the grip stretches the coupon by that amount, and the reaction is the force the laminate needs for that stretch. It grows with the laminate's stiffness along the pull, so with more 0-degree plies, with the width and the thickness, and with the displacement; it falls when the free length is longer, since the same displacement is then a smaller strain.

Under a stated force, the reaction is that force, by equilibrium, and the displacement is what the stiffness gives. The two grips carry equal and opposite forces.

From: Finite element theory, solution and reactions; Laminate theory, laminate stiffness.

## Why a symmetric layup does not bend when it is pulled

In a layup that reads the same from both faces, each ply has a twin at the same distance on the other side of the mid-plane. The pull of one is balanced by the pull of its twin, so an in-plane load causes no curvature: the coupling stiffness between stretching and bending is zero. Every ply then has the same strain through its thickness, and one value per ply describes it.

A layup that is not symmetric bends or twists as it is pulled.

From: Laminate theory, laminate stiffness; Finite element theory, what the membrane model represents.

## Why two plies tie

Plies at the same angle share the same strain in the gauge section, so they carry the same stresses and reach a criterion together. In a symmetric layup every ply has such a twin. The result names one of them, the one nearest the bottom face, and says which plies tie with it.

From: Finite element theory, first-ply failure.

## Why these stresses differ from the ones a general viewer shows

The stresses here are each ply's own, in its fibre axes, at the centre of an element. A general-purpose viewer usually shows a stress in the model's global axes, often at one point through the thickness, and may average it between elements. The two are the same state of stress written in different axes and places, so the numbers differ unless the ply's fibres lie along a global axis.

From: Finite element theory, ply stresses in material axes; Laminate theory, rotation.
