# D3039 IM7/8552 tension coupon: every output against Abaqus, round (a)

Round (a) of ADR-0089: our own deck, `decks/d3039-im7-8552-abaqus.inp`, run in Abaqus/Standard 2025 on 2026-11-11 (the founder's machine and licence, over his VPN), compared element by element and ply by ply with our kernel on the same deck. The deck Abaqus ran is the committed deck, comments aside. Abaqus's own numbers stay with the run, `.local/fea/checks/d3039-im7-8552/runs/abaqus-detect-2026-11-11/` (the teaching licence, ADR-0045); this note gives only counts and differences.

## Our deck since the founder's choice: S4 (ADR-0089 amendment 2)

On 2026-11-11 the founder chose S4 for the tension coupon's deck and for the coupon built in CAE: full integration, as our kernel's element is. The committed deck, `decks/d3039-im7-8552-abaqus.inp`, run again in Abaqus/Standard 2025 the same day:

| Zone | Elements | Values | Within 1 % | Within 3 % | Worst | Worst quantity |
|---|---|---|---|---|---|---|
| gauge | 144 | 13824 | 13824 | 13824 | 0.0074 % | E11 |
| free length | 384 | 36864 | 36864 | 36864 | 0.65 % | E12 |
| band | 264 | 25344 | 23480 | 24664 | 72.7 % | Mid. Principal |
| tab line | 24 | 2304 | 1992 | 2224 | 11.1 % | Pressure |
| gripped | 672 | 64512 | 64512 | 64512 | 0 | |

Reaction at the moving grip: ours +0.007 % of Abaqus's. `tools/abaqus_beside.py` on the same run's `.dat`: 28 of 28 values within 3 %. Every criterion of ADR-0089's proposed acceptance is met for round (a). The S4R runs below are kept as the record of why.

## How it was compared

- `abaqus python tools/abaqus_every_output.py` read the ODB: for each of the 1488 elements and each of the 8 layers, at the layer's middle section point and the element's centroid, with no averaging, S11, S22, S12 in the layer's material axes, then Mises, Tresca, the pressure and the maximum, middle and minimum principal stresses as odbAccess gives them (what Abaqus/CAE shows), then E11, E22, E12; and the reaction at every node.
- `uv run python tools/abaqus_compare.py` put our kernel's values beside them by zone: the gauge (the 25 mm extensometer's length), the free length beyond one width (25 mm) from a tab line, the band within that width, the elements on a tab line (the clamped edge, reported, not judged: ADR-0066), and the gripped tabs.
- A value agrees when it is within the stated percentage of Abaqus's, or of 2 % of that quantity's largest magnitude in the gauge for a small one (the floor of ADR-0066's records).

## What it showed

**Abaqus S4R** (what our deck writes and what CAE offers by default). Reaction at the moving grip: ours +0.031 % of Abaqus's.

| Zone | Elements | Values | Within 1 % | Within 3 % | Worst | Worst quantity |
|---|---|---|---|---|---|---|
| gauge | 144 | 13824 | 13784 | 13824 | 1.61 % | Mid. Principal |
| free length | 384 | 36864 | 34904 | 36032 | 10.7 % | E12 |
| band | 264 | 25344 | 17792 | 21648 | 255 % | Mid. Principal |
| tab line | 24 | 2304 | 752 | 1344 | 86.5 % | Pressure |
| gripped | 672 | 64512 | 64512 | 64512 | 0 | |

In the gauge every quantity's worst difference is under 0.7 % (S11 0.068 %, Mises 0.064 %, Tresca 0.062 %, the maximum principal 0.048 %, E11 0.066 %) except the middle principal stress, whose 40 values above 1 % are the 0° ply's transverse stress of about 0.05 MPa.

**Abaqus S4** (the same deck with full-integration shells, a check of the cause). Reaction: ours +0.007 %.

| Zone | Elements | Values | Within 1 % | Within 3 % | Worst | Worst quantity |
|---|---|---|---|---|---|---|
| gauge | 144 | 13824 | 13824 | 13824 | 0.0074 % | E11 |
| free length | 384 | 36864 | 36864 | 36864 | 0.65 % | E12 |
| band | 264 | 25344 | 23480 | 24664 | 72.7 % | Mid. Principal |
| tab line | 24 | 2304 | 1992 | 2224 | 11.1 % | Pressure |
| gripped | 672 | 64512 | 64512 | 64512 | 0 | |

## Reading

- Our kernel and Abaqus solve the same model: against Abaqus S4, whose integration is our element's, every one of the 13824 gauge values agrees within 0.0074 % and every free-length value within 0.65 %. The differences against S4R outside the gauge (the small transverse and shear components of the 0° and 90° plies, about 0.1 MPa against a 45 MPa shear in the ±45° plies) come from S4R's one reduced-integration point and hourglass control, not from our code: they vanish with S4.
- Mises, Tresca, the principal stresses and the pressure follow the definitions of `recovery.ply_invariants` (`fea/checks/abaqus-conventions.toml`); E12 is the engineering shear strain; CFAILURE's MSTRS, TSAIH and TSAIW are each 1/R.
- Beside the clamped tab lines the two elements differ, as on every record (ADR-0066): the stress there grows as the mesh is refined, and is not a validation quantity.

## Against ADR-0089's proposed acceptance

| Criterion | S4R | S4 |
|---|---|---|
| Reaction within 1 % | +0.031 %, met | +0.007 %, met |
| Gauge, every quantity, every ply, within 1 % (floor 2 %) | 13784 of 13824; the 40 others are the middle principal stress of the 0° ply, within 1.61 % | 13824 of 13824, met |
| Free length within 3 % | 36032 of 36864; the others are the 0° and 90° plies' small components | 36864 of 36864, met |
| Band and tab lines | reported | reported |
| Laminate theory at the gauge centre | the D3039 record's | the D3039 record's |

Still open: round (b), the coupon built by hand in Abaqus/CAE with the same seeds and S4; TSHR (the transverse shear of a layer) read and judged against a floor.
