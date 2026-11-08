# ADR-0066: Solver results are compared as one set of quantities, in the ply axes, at stated places, and peaks are reported apart

- Status: Accepted (2026-11-08: the founder agreed to the record and asked for the stack #153 to #155 to be merged; the quantities, the page and the package tables are as written here; amendment 1 (2026-11-08) takes the Abaqus column off the page's tables and keeps Abaqus as a command-line check)
- Date: 2026-11-08
- Decided by: Founder, 2026-11-08 (direction: "why is everything different ... plan on how to fix this"; "i agree with the record") | Drafted by: Claude Code
- Related: [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md) amendment 6 (the `.frd` read beside ours), [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md) (`equivalence`, `side_by_side`), [ADR-0045](ADR-0045-abaqus-without-the-gui-odbaccess-reports-and-an-optional-second-reference.md) (`tools/abaqus_extract_fields.py`, `tools/run_abaqus.py`), [ADR-0065](ADR-0065-coupon-ply-angles-are-counted-from-the-coupons-length-axis.md), [ADR-0004](ADR-0004-sign-and-stacking-conventions.md); `fea/src/anisotropy_fea/frd.py`, `fea/src/anisotropy_fea/calculix_summary.py`, `fea/src/anisotropy_fea/compare.py`, `components/studio/results-view.tsx`, `docs/abaqus-export-recipe.md`

## Context

On 2026-11-08 the founder put three views of the hosted coupon `AS48552-UNT-L1` (AS4/8552 [45/0/-45/90]s, 250 by 25 mm, 56 mm tabs, 0.5 mm pull) side by side and found no two numbers alike: the studio's Summary said the largest σ₁ is 536.6 MPa in ply 2 (0°) at element 1164; PrePoMax on the CalculiX `.frd` said von Mises 630.1 and S22 633 MPa at node 68288, S11 from -167.4 to 159.7 and S12 from -174.9 to 165.6 MPa; Abaqus/Standard 2025 on `Job-1.odb` said S11 332.8, S22 25.72 and Mises 328.0 MPa for "SNEG, Layer = 1, Avg 75 %". His words: as an engineer he would be confused, validation is hard to explain and the result looks untrustworthy.

Read from the two decks he sent (`AS48552-UNT-L1-abaqus.inp`, `AS48552-UNT-L1-nodal-ccx.inp`) and from runs of both in a container (CalculiX 2.21; our kernel on the Abaqus deck), the three sources are one model solved three ways, and every visible difference is a difference of presentation:

- **Ply.** Abaqus shows Layer 1, the bottom 45° ply. PrePoMax shows the node that holds the model-wide maximum, node 68288 at z = -0.254 mm: the laminate is 1.016 mm thick, so that is the top of ply 2, the 0° ply. The Summary shows the ply where each component peaks, a different ply per row.
- **Frame.** The Summary's values are in each ply's fibre axes (σ₁, σ₂, τ₁₂). The `.frd` is in the global axes, so PrePoMax's "S11" is σxx across the width and its "S22" is σyy along the pull; for the 0° ply alone σyy equals σ₁. Abaqus prints a composite section point in the layer's axes, so its S11 is σ₁ of the 45° ply.
- **Point.** The Summary reads element centroids. PrePoMax reads values extrapolated to the corner nodes of the expanded bricks. Abaqus/CAE reads the bottom face of the layer, averaged over the elements at a node at 75 %.
- **Invariant.** PrePoMax's von Mises is the three-dimensional invariant of the brick state; Abaqus's is the plane-stress invariant of one layer; neither is a composite quantity.
- **Place.** All three maxima sit at the free-edge corner where a gripped tab ends, a clamped edge whose stress grows as the mesh is refined. The same place is read three ways, and a singular place at that.

Not a difference, checked: the grips. A kinematic coupling whose reference node has every dof fixed clamps the tab nodes as the `-nodal` deck does; CalculiX on the converted coupled deck gives the same nodal peaks to four figures. The two decks carry the same layup, material, orientation (`Ori-1`, local 1 along y) and load, card for card. The team's own earlier deck `Tension-test-print.inp` counts its angles from global x, so a team-built deck of this coupon would also differ by 90° in every layer; the comparison tool must say so when it happens (ADR-0065).

ADR-0030 amendment 6 put CalculiX's numbers beside ours on the page, but as the viewer shows them: global axes, nodal, a 3D von Mises, next to our fibre-axis centroid values. It told the engineer that the two differ and why, in prose, instead of showing them the one quantity they agree on. `docs/abaqus-export-recipe.md` tells the team what to print but not how to read a composite result in CAE.

## Options considered

1. Keep the Summary as it is and explain the differences in prose. Rejected: the founder read that prose and still asked why everything is different. A sentence does not make 536.6 and 633 the same number.
2. Show gauge values only and drop the peaks. Rejected (already in ADR-0030 amendment 6): the peaks are what an engineer looks for, and the stress concentration at the grip is real, only its value is not.
3. Report only what a viewer shows (nodal, global) so the page equals PrePoMax. Rejected: a composite result in the global axes is not what a laminate engineer or a failure criterion reads, and Abaqus would then disagree with both.
4. **One comparison contract: a fixed set of quantities, each defined once (ply, frame, point, place), reported for every solver in the same table, with peaks reported apart and labelled as singular.** Chosen (proposed here).

## Decision

### The quantities

Every comparison of this project's solvers with each other, with a reference solver, with the team's models and with classical laminate theory uses these quantities and no others as its validation set:

1. **Reaction force** at the moving grip, N.
2. **Gauge-centre strain** εx, εy, γxy at the centroid of the gauge-centre element (the spec's `centre` probe).
3. **Per ply, every ply**, σ₁, σ₂, τ₁₂ in the ply's fibre axes at the gauge-centre element: the element centroid for our kernel and for an Abaqus S4R (`position=CENTROIDAL`, section point at the ply's middle), the average of the ply's integration points for CalculiX (`*EL PRINT`, as `compare.reference_quantities` already does). Plies are numbered from the bottom face (ADR-0004); angles are stated from the length axis (ADR-0065).
4. **Classical laminate theory** for the same gauge state (the engine's A matrix under the gauge-centre strain) as the analytical column.

Peaks are reported in a second table, apart from the validation set: for every ply, the largest σ₁, σ₂ and |τ₁₂| in the fibre axes over the elements that touch a tab line, at the element centroid for every solver that has one, with the element named, and labelled "stress concentration at the clamped edge; grows as the mesh is refined; not a validation quantity". A nodal peak is shown only as a viewer's number, named as such, with its node and position, so the engineer who opens PrePoMax finds it.

Von Mises is not reported for a composite anywhere this project controls (it was already dropped from the Summary's ply rows; the `.frd`'s 3D von Mises stays only as "what PrePoMax shows").

### The table on the page and in the package

The Summary's three stress blocks (gauge table, peaks list, `.frd` list) become two tables. The validation table has one row per quantity above and one column per source: CLT, Anisotropy, CalculiX, Abaqus (when its fields were uploaded for this coupon; `-` otherwise), and a difference column against Anisotropy. Each column header says in one line how its value was taken ("centroid", "integration-point average", "CENTROIDAL, section point at the ply middle"). Each cell that a viewer can show carries a hint of where to find it ("PrePoMax: open ply 2's part, S22, element 751"; "Abaqus: Layer 2, MID, no averaging"). The peaks table follows, collapsed by default, with the same plies in every column. The PDF package prints the same two tables, from the same fields file, so the page and the report cannot say different things.

### The files

- `anisotropy_fea.frd` gains a per-ply read: each brick's ply from its nodes' z (the plies are unconnected layers, so a node belongs to one ply), the nodal state rotated by the ply's fibre angle (`stress_transformation`, ADR-0065), and the per-ply peaks in the fibre axes beside the global ones the record already holds. The record's `[frd]` block gains `ply_s1_max`, `ply_s2_max`, `ply_t12_max_abs` per ply with their nodes.
- A second results block in the `.frd`, or a `.vtu` beside it, carrying each ply's σ₁, σ₂, τ₁₂ in the fibre axes at the nodes, so an engineer sees the page's quantity in a viewer. Which of the two PrePoMax reads is UNVERIFIED until tried; `examples/export_vtk.py` already writes the kernel's per-ply material-axis stresses for ParaView.
- `docs/abaqus-export-recipe.md` gains the reading recipe for the validation set: `*El Print, position=CENTROIDAL` of S at the gauge-centre element with a section point per layer, or `tools/abaqus_extract_fields.py --layer-point middle` on the `.odb`; and for CAE: the layer, section point MID, "Quantity to plot: Discontinuities" off, averaging off, the material axes.
- `side_by_side` (ADR-0035) already pairs Abaqus field reports with the kernel element by element; the Abaqus column of the table is filled from its output when the reports are in the coupon's folder.
- The decision whether a team deck's orientation differs from ours is already judged by `equivalence`; the table's Abaqus column header names the deck's stated axis.

### The validation record

A record for `AS48552-UNT-L1` with all four columns is written once the Abaqus fields are exported, kept under the coupon (ADR-0042) and summarised in a public note without the team's numbers. The public check coupon `unnotched-im7-8552` gets the same table in its records, with the CLT column computed, as the test that holds this contract.

## Why (evidence)

The runs of 2026-11-08, in a cloud container, `apt` CalculiX 2.21, `anisotropy_fea` at `f05bedf`, on the two decks the founder sent (scratch script, not committed; the numbers are in the thread's document):

- `examples/convert_to_calculix.py` on `AS48552-UNT-L1-abaqus.inp` (nu13 = nu23 = 0, E3 = E2): CalculiX total grip force 4690.66 N, kernel 4706.78 N (0.34 %); centre-element strain [-0.001127, 0.003641, ~0] in both.
- `frd_peaks` on the `-nodal` `.frd`: von Mises 630.05 at node 68288 (0, 57, -0.254), SYY 632.99 at the same node, SXX 159.69 / -167.42, |SXY| 174.94, gauge SYY 488.23: PrePoMax's numbers to the digit.
- The `.frd` rotated per ply into the fibre axes, gauge-section median against the kernel's centre element: ply 1 (45°) 169.9 / 15.2 / -23.0 against 170.1 / 15.2 / -23.0 MPa; ply 2 (0°) 479.1 / -0.3 / 0.0 against 479.2 / -0.3 / 0.0; ply 4 (90°) -139.0 / 30.7 against -139.0 / 30.7.
- The same per-ply peaks: ply 2 σ₁ 633.0 at the corner node against 536.6 at the centroid of element 1164 (the Summary's number); ply 1 σ₁ 363.8 at node 68850 against 357.8 at the centroid of element 348, and Abaqus's screen 332.8 for Layer 1 at 75 % averaging; ply 1 σ₂ 27.2 at the centroid against Abaqus's 25.72.
- The converted coupled deck's nodal per-ply peaks equal the `-nodal` deck's to four figures (633.0, 363.8, 350.6).
- The team's earlier deck `Tension-test-print.inp` (local, ADR-0042): `*Orientation, name=Ori-1` / `1., 0., 0., 0., 1., 0.`, axis 1 along global x.
- Not yet seen: the `Job-1.odb` fields as numbers (the screenshots only), so the Abaqus column above is read off a legend; UNVERIFIED until `tools/abaqus_extract_fields.py` runs on it.

## Consequences

- An engineer reads one table in which the same quantity sits in every column, and a second table that says in its title why its numbers are not expected to agree. The prose that explained the differences goes.
- The `.frd` read grows a per-ply rotation; the fields file and the record grow the per-ply peaks; the Summary component and the package's summary page change; the Abaqus recipe gains a reading section. No solver changes.
- A team deck counted from global x shows up as a 90° layer difference in the table's header, not as a silent mismatch.
- The page depends on the Abaqus fields being exported with `tools/abaqus_extract_fields.py` for its last column; without them it shows `-`.

## How we will know it was wrong

- An engineer with PrePoMax or Abaqus/CAE open beside the page cannot find a cell's value in their viewer with the cell's hint within a minute.
- The validation table's Anisotropy and CalculiX columns disagree by more than the record's tolerance in the gauge rows on a public check coupon, which would mean a solver or a rotation is wrong, not the presentation.
- The team asks again why the page and their viewer differ after the table is live.

## Amendment 1, 2026-11-08 (the Abaqus column leaves the page; an Abaqus run is read on the command line; decided by the founder)

**Context.** The tables shipped the same evening with the Abaqus column empty: no Abaqus is reachable from the hosted solvers (the install is the
founder's Windows machine under a teaching licence, ADR-0045), so the column could only fill from files a person brings. A drop zone for the run's
`.dat` was started, then an agent on the founder's machine was proposed to make it automatic. The founder stopped both: "we want it to be easy for the
user, should be automatic"; then "don't put abaqus in table, open source calculix is enough".

**Decision.** The page's validation table has three columns, Laminate theory | Anisotropy | CalculiX, and the peaks table two; the coupon document prints an
Abaqus column only where the team's exported fields fill it (a team coupon with a comparison manifest), never an empty one. CalculiX stays the one
reference the site runs. An Abaqus run of our own deck, when the founder makes one, is read by `fea/tools/abaqus_beside.py`: `anisotropy_fea.abaqus_dat`
parses the `.dat`'s printed tables (the layout read from `AS48552-UNT-L1-abaqus-plies.dat`, Abaqus 2025), `anisotropy_fea.abaqus_summary` puts the reaction
(the `RF` TOTAL at the moving grip's reference node), the gauge strain (`SE2, SE1, -SE3`: the layup's axis 1 runs along the coupon, so the section strains
turn by a quarter) and every ply's σ₁ σ₂ τ₁₂ at the middle section point of each layer beside the kernel's on the same deck, with the record's tolerance
and floor; a `.dat` that prints the faces (an older deck) is refused with the points it printed. The `.dat` reader replaces nothing: the CSV field reports of
`tools/abaqus_extract_fields.py` remain the route for a team's model and for whole-field comparisons (`side_by_side`).

**Evidence.** On the founder's second run of 2026-11-08 the tool read 28 of 28 values within 3 %: reaction 4705 against 4706.8 N (+0.04 %), ply 2 (0°) σ₁
479.1 against 479.2 MPa, every ±45° and 90° ply's three components alike; the first run, without the section-point list, is refused as printing points 1
and 24 only. The validation record for the coupon stays the comparison note in the project files, since the coupon is a hosted job and not a folder under
`.local` (ADR-0042).

**Consequences.** "The page depends on the Abaqus fields being exported" above no longer holds: the page depends on CalculiX alone. The Summary's footnote
says where the Abaqus check lives. No API endpoint and no agent were added.

