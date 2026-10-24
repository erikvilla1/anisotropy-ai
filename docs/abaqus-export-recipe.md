# What to export from Abaqus for a comparison with anisotropy_fea | 2026-10-15

Written for: the team member who builds the Abaqus coupon models (ADR-0029). Our solver reads your `.inp` and solves on your mesh; to compare, we need the numbers Abaqus computed. Today your job writes only `PRESELECT` field output to the `.odb`, and the `.dat` has no result tables, so there is nothing to compare yet. Either route below works; the first needs no Abaqus/CAE steps.

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

Open questions for you to settle on your machine (each is UNVERIFIED by us):

1. Section points: for a composite layup, which section points does `*El Print` write by default, and how is the list of section points given (we believe the first data line of `*El Print` can list them)? We need `S` and `E` for every ply, or at least for plies 1, 2, 3 and the top ply, and we need to know which section point belongs to which ply.
2. Axes: are `S11`, `S22`, `S12` at a layer's section point in that ply's material axes (what we expect) or in the section orientation? A 45 degree ply under axial tension answers this at a glance.
3. Shear strain: is `E12` the tensor shear strain or the engineering shear strain (twice the tensor value)? Our engine uses engineering shear (ADR-0004).
4. `*Fail Stress`: if you add strengths so Abaqus reports `MSTRS`, `TSAIH` and `TSAIW`, are `Xc` and `Yc` entered as negative numbers or as magnitudes?
5. The reaction: `RF` at the loaded reference node with `totals=YES`; we will compare the sum.

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
