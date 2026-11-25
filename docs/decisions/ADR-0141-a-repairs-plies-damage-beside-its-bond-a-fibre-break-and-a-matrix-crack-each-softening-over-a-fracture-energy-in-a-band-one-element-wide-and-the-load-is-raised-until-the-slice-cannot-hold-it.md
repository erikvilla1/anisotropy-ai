# ADR-0141: A repair's plies damage beside its bond: a fibre break and a matrix crack, each softening over a fracture energy in a band one element wide, and the load is raised until the slice cannot hold it

- Status: Proposed
- Date: 2026-11-24
- Decided by: Founder, 2026-11-24 ("ok start it", the plan's seventh slice, read as damage in the plies of the same plane slice as the sixth, with the three-dimensional model left for later) ; Founder, 2026-11-24 (chose "Softens over a fracture energy" on the card asking how a ply loses its stiffness once it reaches a strength) | Drafted by: Claude Code
- Related: [ADR-0140](ADR-0140-a-repairs-bond-is-followed-to-failure-in-a-plane-solver-of-our-own-a-traction-separation-law-across-the-bondline-the-path-followed-by-the-energy-the-bond-spends-checked-against-exact-fracture-answers-and-moose.md), [ADR-0132](ADR-0132-a-repairs-slice-is-solved-in-calculix-as-a-plane-of-eight-node-elements-held-flat-with-the-laminates-far-field-width-strain-and-its-bondline-and-plies-are-read-back-as-means-by-the-engine.md), [ADR-0131](ADR-0131-a-stepped-patch-repair-is-one-description-of-a-few-numbers-in-the-engine-its-slice-is-a-set-of-rectangles-and-the-hand-calculation-the-mesh-and-the-step-file-are-all-made-from-them.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0003](ADR-0003-reject-invalid-input.md), `fea/src/anisotropy_fea/ply_damage.py`, `fea/src/anisotropy_fea/repair_plies.py`
- Area: fea, engine

## Context

ADR-0140 follows a repair's bond until it lets go, with every ply elastic. For the example repair that run gives 1,339.8 N per mm of width, and the elastic slice of ADR-0132 has the first ply of the same repair reach a strength at 466.1 N/mm. So the example's answer is not the bond's: the plies decide, and nothing in the product can say what the repair carries once they begin to fail. The record of ADR-0140 says so and leaves it to the plan's seventh slice.

Two facts set the shape of the work. The slice is a plane of eight-node elements with a width strain in proportion to the load (ADR-0132), so a ply's damage must be stated in three dimensions and read in that plane. And a softening material, unlike a softening bond, has no length of its own: the energy a crack spends depends on how wide the band of elements it forms in is, so a band width must be chosen and defended, or a finer mesh moves every answer.

## Options considered

How a ply loses its stiffness once it reaches a strength (put to the founder on a card, 2026-11-24):

1. **It softens over a fracture energy (chosen; the founder's card).** Each crack has an energy per unit area, and the ply's stress falls to nothing over the strain that spends it. Four more numbers for a ply material. With a band width it is the only one of the three whose answer a finer mesh does not move.
2. **It drops to a fraction of its stiffness at once (a ply discount).** No new numbers, and what most laminate tools do. The fraction is arbitrary, the answer moves with the mesh, and a run would report a load that a finer mesh changes.
3. **It keeps its stress (a plateau).** Right for a ductile matrix in shear, wrong for a fibre break, and it never lets a ply fail.

Which cracks a ply has:

1. **Two: a break across the fibres and a crack along them, each with its own onset and energy (chosen).** The two Hashin modes, which is what a composite damage model in Abaqus or in Ansys holds; it separates what the fibres do from what the matrix does, and the matrix crack is the bond's own two-line law with the strain times the band width as the opening.
2. **One damage for the whole ply, from a failure index.** Cheaper, but a ply with its matrix cracked and its fibres whole is most of what happens in a laminate, and one damage cannot hold it.
3. **Four or more (the fibre and matrix modes split into tension and compression, with the shears apart).** More than the repair file's numbers can feed.

How wide the band a crack softens in is:

1. **One element, cut at the ply's angle (chosen).** The crack band of Bažant and Oh: the energy a crack spends per unit area is held fixed by setting the strain at which the stress reaches zero from the band's width, so the answer does not move with the mesh. The width across a fibre break is the element's length along the load times the cosine of the ply's angle, across a matrix crack times the sine.
2. **Half an element (one column of integration points).** Tried first, with each integration point damaging on its own: the energy spent came out twice over or half under the fracture energy, depending on which of an element's four points happened to soften. Rejected; an element now damages as one, from its mean strains.
3. **A length the engineer gives.** One more number, and no engineer has it.

How the load is carried past first softening:

1. **Hold a load and let the damage grow until it stops; then raise the load until the slice cannot hold it (chosen).** At each turn the slice is solved as an elastic body with the stiffness its damage leaves, and every element and pair then takes the damage of the strains found; the damage never falls. Where it stops the state is one the slice can rest in under that load, which is what a load-carrying answer means. The load it does not hold is found by halving, so the answer is a bracket, not a point.
2. **The path followed by the energy the damage spends, as ADR-0140 follows the bond.** Tried first, on the cross-ply strip that has an exact answer: dozens of plies reach their strength in the same step, the iterations pass back and forth between two states and never settle, and the step is cut until the path stalls. Nothing short of a different method got past first ply failure. ADR-0140's own run keeps this method, untouched.
3. **Steps of displacement with Newton's method.** Rejected for the bond already (ADR-0140), for the same reason.

## Decision

1. **A ply's two cracks.** In the ply's own axes (1 along the fibres, 2 across them in the ply, 3 through the thickness): a **fibre break**, whose plane's normal is 1, begins where E1 ε1 reaches the tensile strength F1t or −E1 ε1 the compressive F1c, and lowers the ply's stiffness along 1 and in the shears 12 and 13. A **matrix crack**, whose normal is 2, begins on the line (E2 ⟨ε2⟩ / F2t)² + (G12 γ12 / F6)² = 1 and lowers the stiffness along 2, while it is pulled open, and in the shears 12 and 23. A crack pressed shut carries the pressure with the whole stiffness. Damage only grows.
2. **The softening.** Each crack's stress falls in a straight line with the strain, the bond's law of ADR-0140 with the strain times the band's width as the opening and the slip, so that the crack spends its fracture energy per unit of its own area whatever the mesh. The damage enters the ply's compliance: each damaged term is divided by what is left of it, so a ply pulled along one axis alone carries that fraction of its elastic stress and the ply's stiffness stays one an elastic solid may have.
3. **The band.** One element wide, cut at the ply's angle: the element's length along the load times |cos θ| for a fibre break and |sin θ| for a matrix crack. An element damages as one, from its mean strains. A crack whose plane holds the load's direction cannot form in a slice along the load and is not followed: the matrix crack of a 0° ply, the fibre break of a 90° ply.
4. **The element's length.** A crack can soften only where its fracture energy is above the energy the ply holds when it reaches its strength, which bounds the band and so the element: 2 G E / X² for each of the four cracks of each material. The run takes four fifths of the smallest of those bounds, or the length asked for if that is shorter, and a model built with elements longer than the bound is refused in words (ADR-0003).
5. **The numbers.** Four new ones for a ply material in the repair file, beside the five strengths it may already state: `fibre_tension_energy`, `fibre_compression_energy`, `matrix_tension_energy` and `matrix_shear_energy`, in the unit system's force per length as the adhesive's two are. All four or none. The run is refused without them and without the strengths, and the engine says what is missing (`ply_needs`). The example repairs get round numbers of their own.
6. **The run.** The slice, the bond and the holds of ADR-0140, with the load on the panel's end alone: the stress the width strain makes is now the plies' own and moves with their damage. The load is raised from the first softening of anything, bond or ply, by 15 % at a time while the slice holds it, then halved in until the load held and the load not held are within half a percent of each other.
7. **The answer.** The load at which anything first softens and what it was; the largest load the slice holds and the smallest it does not, so the load it carries lies between them; what had failed at the largest load held, in plain words (how much of the bond is past its strength and how much carries nothing, and how many elements of which ply are broken across the fibres, crushed or cracked along them, with the worst one's place); and the levels of load held, with the end's movement. Every load reported comes with a mesh study beside it.
8. **The wording.** It is "the load the repair carries in this model", with the bracket and the mesh study's spread beside it, never the repair's strength: no test of a repair has been compared (ADR-0140's rule, kept).
9. **The checks.** (a) The law alone: its stress integrated over the strain, times the band's width, is its fracture energy. (b) A bar of one ply with a weak element breaks at exactly its strength, and that load does not move with the mesh. (c) A cross-ply strip: first ply failure is laminate theory's, and the last ply's load lies between two hand bounds. (d) The run with only the bond able to damage gives ADR-0140's own two loads. (e) The plies' forces add up to the load at every station of the largest load held. (f) A mesh study of each example.

Not decided here: a ply parting from its neighbour (delamination), a ply crushing across its fibres (F2c is not used), a saturation of matrix cracking, the width strain following the damage, and what the page, the chat and the report show.

## Why (evidence)

All of these were run on 2026-11-24 with the code of this record; the first four are the tests of item 9.

- **The law** (`ply_damage.softening`, the bond's own): driven through a rising strain at one point of a 0° ply, the stress peaks at the strength and the stress integrated over the strain, times the band's width, is 1.000009 of the fracture energy.
- **A bar of one ply**, 10 mm long, with one element 1 % weaker: the load at which it breaks is 1.00076 of that element's strength with 10, 20, 40 and 80 elements along the bar, for a 0° ply and for a 90° ply (1.00076 is the bracket's own half-width, 0.2 %). With the path method of ADR-0140, before it was set aside, the same bar spent 0.9965 to 1.0066 of the fracture energy over nine arrangements of mesh, angle and Poisson's ratio.
- **A cross-ply strip** [0/90/90/0] of the library's IM7/8552, 0.2 mm plies, pulled along the 0° plies: first ply failure at 491.141 N/mm against laminate theory's 491.141 N/mm, written out fresh in the check and not taken from the engine. The largest load held is 1,028.5 N/mm and the smallest not held 1,033.1; the hand bound with the 90° plies whole is 1,034.98 N/mm and with their damage at the fibre's onset strain put in by hand 1,028.5 N/mm. Four other arrangements ([90/0/0/90], six plies, a finer mesh, a smaller matrix energy) land between their own two bounds the same way.
- **The ply rotation** this module uses gives the engine's own turned stiffness (`anisotropy_engine.repair.solid.turned_stiffness`) to 1.5 parts in 10^16 at 0, ±45, 90, 30 and −60 degrees.
- **The run with only the bond able to damage**, on the example repair's own mesh: first softening 184.02 N/mm against ADR-0140's 184.0, and the bond lets go between 1,342 and 1,345 N/mm against its 1,339.8 (0.2 % apart). The two methods are independent past onset, so this is the strongest check of the new one.
- **Equilibrium** at the largest load held on the example repair: the plies' forces along the load add up to the load at every station within 3.9 parts in 10^12.
- **Why the path method was set aside**: on the cross-ply strip above, at 0.7 % past first ply failure, its iterations settle to a residual of 2 parts in 10^4 of the load and then alternate between two states for ever, 60 of 160 elements taking and losing their damage each turn; halving the correction did not break the cycle. The tangent itself is right: the change of the forces matches it to 5 parts in 10^8 by finite differences, and so do the slopes with the load factor and the width reaction.

UNVERIFIED, and said so wherever it is used: no comparison with a test of a repair, with a published repair study, or with Abaqus or Ansys (Abaqus's own composite damage is for plane-stress elements, not the solid elements of this slice, so it cannot check this run directly). The run's time on the hosted container is not measured.

## Consequences

- The repair gets a fourth answer: the load it carries with its bond and its plies both able to fail. For the example that is below the bond's own, which is the point of the slice.
- Four numbers more are asked of the engineer, and they are harder to find than the adhesive's two. A repair without them keeps its three earlier answers.
- The elements must be short enough for a crack to soften in them, and the fracture energies decide how short. With the example's round numbers that is 0.72 mm, half the elastic slice's own 1.5625 mm, so this run's mesh is always finer than the elastic one's and its model larger.
- The run is slower than the bond's: about 220 s on four cores for the example at 4,075 elements, against 10 s for the bond. The route that serves it needs its own budget, or the run belongs in a job.
- Where the panel's far field itself cracks, the number of cracked elements grows with the mesh, because nothing in the model saturates matrix cracking. The mesh study is what says whether a load may be read, and a repair whose answer does not settle must be said to have none.
- The fea package now holds a damaging material beside its damaging bond. ADR-0140's path method stays for the bond alone, so there are two ways of carrying a load in one package, each with its own tests.

## How we will know it was wrong

- A load reported moves by more than 2 % between the mesh the run uses and a mesh with elements four fifths as long.
- A case with an exact answer is off by more than 2 %: the bar's break load, the strip's first ply failure, or the bond-only run against ADR-0140.
- A published repair test, when one is compared, lies outside the bracket the run gives by more than its own scatter.
- The run takes more than a few minutes on the hosted container for a repair an engineer would type.
