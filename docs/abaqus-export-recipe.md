# What to export from Abaqus for a comparison with anisotropy_fea | 2026-10-15

Written for: the team member who builds the Abaqus coupon models (ADR-0029). Our solver reads your `.inp` and solves on your mesh; to compare, we need the numbers Abaqus computed. Today your job writes only `PRESELECT` field output to the `.odb`, and the `.dat` has no result tables, so there is nothing to compare yet. Either route below works; the first needs no Abaqus/CAE steps.

## Reading a composite result the way the page reads it (ADR-0066, 2026-11-08)

The page's validation table and the `.frd` in PrePoMax and a layer in Abaqus/CAE are one result read three ways, and the three only agree when the same ply, the same axes and the same point are read. What the page prints, and how to see the same number in each viewer:

| On the page | In Abaqus/CAE | In PrePoMax (the CalculiX `.frd`) |
| --- | --- | --- |
| Ply k, counted from the bottom face; its angle from the coupon's length axis | `Layer = k` (CAE counts layers from the bottom, SNEG side) | the k-th part of the expanded model: one layer of bricks per ply, the lowest z first |
| σ₁, σ₂, τ₁₂ in the ply's fibre axes | `S11`, `S22`, `S12` at a composite section point are in the layer's material axes already | the file is in the **global** axes: `S11` is σxx across the width, `S22` is σyy along the coupon; for a 0° ply (fibres along the pull) σ₁ = `S22`, for a 90° ply σ₁ = `S11`; a ±45° ply needs the rotation, which the page does for you |
| the element centroid, the ply's middle | `*El Print, position=CENTROIDAL` with a section point per layer, or in the viewer: section point **MID** of the layer, Result Options → Averaging off, Quantity to plot: Discontinuities off | the nodal values, extrapolated from the integration points: a corner node of the tab line reads above the centroid of the same element (on `AS48552-UNT-L1`: 633 against 537 MPa for the 0° ply) |
| no von Mises | `S, Mises` of a layer is the plane-stress invariant of that layer's state | `Mises` is the three-dimensional invariant of the brick's state; neither is a laminate quantity |
| the reaction force | `RF2` at the reference point of the moving grip (`*Node Print, nset=RF-Top, totals=YES`) | `*NODE PRINT, NSET=Grip-Top, TOTALS=YES` in the `.dat` |

Two things our own deck already does so the numbers can be read back: `*El Print, position=CENTROIDAL` of `S` at the probe elements writes every layer's centroid stress into the `.dat`, and `*Node Print` the reaction. **Abaqus/CAE drops both when a deck is imported and the job is re-exported** (`Job-1.inp` of 2026-11-08 kept only `*Output, field, variable=PRESELECT`, whose `.odb` holds the outer section points alone, `SNEG` of layer 1 and `SPOS` of the top layer). So run the deck as written, from the command line:

```
abaqus job=<coupon>-abaqus input=<coupon>-abaqus.inp interactive
abaqus python fea/tools/abaqus_extract_fields.py <coupon>-abaqus.odb --out <folder> --layer-point middle
```

The first fills the `.dat` with the reaction and every ply's centroid stresses at the probe elements, the validation table's Abaqus column; the second writes the field reports the peaks column reads. Both files go beside the coupon's run under `.local/fea/<coupon>/ours/runs/<attempt>/run/abaqus/` (ADR-0045).

## Route 1: print tables into the `.dat` (preferred)

Add named sets for the probe points, then print requests inside the step. Everything in this block is our understanding of the Abaqus keywords and is UNVERIFIED by us: please check the job runs and that the tables appear, and tell us what you had to change.

In the assembly, name what we will compare:

```
*Nset, nset=Probe-Nodes, instance=<your part instance>
<a few node labels along the axis and next to the grips>
*Elset, elset=Probe-Elements, instance=<your part instance>
<a few element labels: mid-length, next to a grip, at a corner>
```

Before `*End Step`:

```
*Node Print, nset=RF2, totals=YES
RF
*Node Print, nset=Probe-Nodes
U
*El Print, elset=Probe-Elements, position=CENTROIDAL
SF, SE
*El Print, elset=Probe-Elements, position=CENTROIDAL
S, E
```

Open questions, and what the run of 2026-11-08 (Abaqus/Standard 2025, S4R, our deck `AS48552-UNT-L1-abaqus.inp` run from the command line) settled:

1. Section points: **settled.** With no section-point list, `*El Print` of a composite writes two section points only, the bottom of ply 1 and the top of the last ply (points 1 and 24 for 8 layers at 3 Simpson points each). The middle of layer k is section point 3k − 1 (2, 5, 8, 11, 14, 17, 20, 23), and the list goes on the first data line of `*El Print`, before the variable; our writer will list them, so every ply's centroid stress is printed (UNVERIFIED until the deck is rerun).
2. Axes: **settled.** `S11`, `S22`, `S12` at a layer's section point are in that ply's material axes: the 45° ply of the gauge element read 170.0 / 15.22 / −23.00 MPa, the fibre-axis values our engine gives (170.1 / 15.2 / −23.0), not the section orientation's.
3. Shear strain: **settled.** `E12` is the engineering shear strain, twice the tensor value: 0.004767 for the 45° ply, which is ε_y − ε_x of the laminate. Our engine uses the same (ADR-0004).
4. `*Fail Stress`: if you add strengths so Abaqus reports `MSTRS`, `TSAIH` and `TSAIW`, are `Xc` and `Yc` entered as negative numbers or as magnitudes? Still UNVERIFIED.
5. The reaction: **settled.** `RF2` at the loaded reference node with `totals=YES` is the coupon's force (4705.40 N against our 4706.78 N, 0.03 %); the `TOTAL` line is the one node.

## Route 2: field reports from Abaqus/CAE

Request `S`, `E`, `SF`, `SE` as field output with "Output at shell section points: all plies" for the layup, run, then Report > Field Output at the element centroid for the probe element set and at nodes for `U` and `RF`, saved as `.rpt`. Tell us how the report labels the assembly-level reference nodes.

## Route 3: field reports saved as CSV

Report > Field Output saved as CSV, one file per quantity: one row per element and section point with the centroid coordinates. We read that format directly now (`fea/src/anisotropy_fea/abaqus_report.py`), so keep using it. The first such export, on 2026-10-16, settled three of the questions above: values are at the element centroid (`IntPt` 1), `Layer = 1` with `SNEG` is the bottom ply, and S11, S22 of the outer plies come in the ply's material axes. What the files did not carry, and what would complete the record:

- **All section points.** That export held only the outer faces (`SNEG` of the bottom layer, `SPOS` of the top one), CAE's default. In Report > Field Output choose all section points (or at least one per layer), so the 45-degree plies are compared too; they are the ones that answer question 2 beyond doubt.
- **S12** alongside S11 and S22, and **E** (strains) if the report dialog allows.
- **RF** at the two reference points and **U** at a few nodes (a node report, same dialog, position: nodal).
- The report blocks may repeat (one file held three identical copies); that is fine, we check they agree.

## What we need with the numbers

- The exact `.inp` that produced them (we check its SHA-256).
- Abaqus version, element type, section integration (Simpson or Gauss), number of section points per layer, output position, who ran it and when.
- The unit system of the deck (we assume mm and MPa unless told otherwise).

## What we do with them

A comparison record (numbers only, with the provenance above) under `.local/fea/<coupon>/ours/verification/`, where it stays private with the coupon's model (ADR-0032, ADR-0042). The first comparison note sets the agreement targets and states what did and did not match.

## A note on the imposed displacement

With `nlgeom=NO` the analysis is linear, so every result scales with the imposed displacement: a large pull still compares the solvers, but its numbers are not physical for a real coupon. A pull of about 1 % nominal strain makes the printed values read naturally; either is fine for us.
