# D3039 IM7/8552 tension coupon: the comparison with Abaqus, round (a)

Round (a) of ADR-0089 compares our own deck, `decks/d3039-im7-8552-abaqus.inp`, solved in Abaqus/Standard, with our kernel on the same deck, element by element and ply by ply. This note says how the comparison is made and what it is held to. The numbers of the comparison are kept privately (ADR-0045).

## The deck's element: S4 (ADR-0089 amendment 2)

On 2026-11-11 the founder chose S4 for the tension coupon's deck and for the coupon built in CAE: full integration, as our kernel's element is. S4R has one reduced-integration point and hourglass control, so outside the gauge the small transverse and shear components of the 0° and 90° plies differ from a fully integrated element's. That difference is one of formulation, not of code, and S4 removes it. With S4 the committed deck meets every criterion of ADR-0089's acceptance for round (a).

## How it is compared

- `abaqus python tools/abaqus_every_output.py` reads the ODB: for each of the 1488 elements and each of the 8 layers, at the layer's middle section point and the element's centroid, with no averaging, S11, S22, S12 in the layer's material axes, then Mises, Tresca, the pressure and the maximum, middle and minimum principal stresses as odbAccess gives them (what Abaqus/CAE shows), then E11, E22, E12; and the reaction at every node.
- `uv run python tools/abaqus_compare.py` puts our kernel's values beside them by zone: the gauge (the 25 mm extensometer's length), the free length beyond one width (25 mm) from a tab line, the band within that width, the elements on a tab line (the clamped edge, reported, not judged: ADR-0066), and the gripped tabs.
- A value agrees when it is within the stated percentage of Abaqus's, or of 2 % of that quantity's largest magnitude in the gauge for a small one (the floor of ADR-0066's records).
- `uv run python tools/abaqus_beside.py` reads the same job's `.dat` for the validation table's rows.

## Reading

- Mises, Tresca, the principal stresses and the pressure follow the definitions of `recovery.ply_invariants` (`fea/checks/abaqus-conventions.toml`); E12 is the engineering shear strain; CFAILURE's MSTRS, TSAIH and TSAIW are each 1/R.
- Beside the clamped tab lines two element formulations differ, as on every record (ADR-0066): the stress there grows as the mesh is refined, and is not a validation quantity.

## ADR-0089's acceptance

| Criterion | Round (a), S4 |
|---|---|
| Reaction within 1 % | met |
| Gauge, every quantity, every ply, within 1 % (floor 2 %) | met |
| Free length within 3 % | met |
| Band and tab lines | reported, not judged |
| Laminate theory at the gauge centre | the D3039 record's |

Still open: round (b), the coupon built by hand in Abaqus/CAE with the same seeds and S4; TSHR (the transverse shear of a layer) read and judged against a floor.
