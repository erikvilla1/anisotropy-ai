# Evaluation: finite element chunk F, Abaqus field reports as a record source and the first Abaqus comparison (ADR-0030, amendment 2) | 2026-10-18

- Scope: `fea/` gains `abaqus_report.py` (`read_field_report`, `report_quantities`), `recovery.ply_mises`, the record grammar's `ply_mises` group and `nan` components (skipped by the comparison), `source = "csv"` on records, `tools/record_from_report.py` (`--elements` or `--within` a box), the fixture `tests/fixtures/field-report-S22.csv`, `tests/test_abaqus_report.py`, and a local test of the team's record in `tests/test_local_tension_deck.py`. Theory section 6 states the Mises invariant with a code marker; the export recipe gains Route 3 (what the team did and what would complete it).
- Why: the team exported their coupon's Abaqus results as CAE CSV field reports (S11, S22, Mises at the element centroids, outer section points). These are the first Abaqus numbers for any coupon.
- Environment: Windows 11; CalculiX 2.22 from the PrePoMax v2.6.0 bundle on `ANISOTROPY_CCX` (not used by this chunk's code, present for the suite); `fea/uv.lock` unchanged.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests`

```text
611 passed in 50.18s
```

(596 before this chunk; 14 new tests in `test_abaqus_report.py` and the local record test; `-ra` listed no skips, so the team's record was present and checked.)

From `fea/`, the record of the team's coupon (numbers in the local record and note, material not public):

```text
uv run python tools/record_from_report.py ../.local/abaqus/Tension-test.inp --units mm-MPa --reports <S11.csv> <S22.csv> <Mises.csv> --within 0 10 25 55 --tolerance 0.01 --floor 0.02 ... --out ../.local/abaqus/comparisons/tension-test-abaqus.toml
written ..\.local\abaqus\comparisons\tension-test-abaqus.toml | (element, ply) rows per group: {'ply_stress_local': 600, 'ply_mises': 600}
```

`compare_record` on it: 1800 numbers (300 elements, two outer plies, S11 and S22 with S12 as `nan`, Mises), zero disagreements at 1 %, worst 0.43 % (S11 at y = 25 mm). Three boxes were tried before settling on y 25 to 55 mm of the 15 to 65 mm gauge:

| box (y, mm) | elements | numbers | outside 1 % | worst |
| --- | --- | --- | --- | --- |
| 30 to 50 | 200 | 1200 | 0 | 0.20 % |
| 25 to 55 | 300 | 1800 | 0 | 0.43 % |
| 20 to 60 | 400 | 2400 | 88 | 2.33 %, all S11 within 5 mm of a tab line |

The full-field reading (all 800 elements, `.local/abaqus/notes/abaqus-csv-vs-kernel-2026-10-18.md`): gauge centre S11, S22, Mises within 0.07 %; over the gauge S22 and Mises within 0.4 %, S11 within 2.2 % of its maximum; the element row at each tab-line corner differs by up to 24 % of the S11 maximum and 7 % of the Mises maximum. That corner is a stress singularity (rigid tab meeting the free edge) where Abaqus's S4R and our full-integration bilinear element resolve the field differently and neither converges with the mesh; Abaqus's peak Mises sits in that corner element, the kernel's two elements away. Difference maps: `.local/fea-plots/abaqus-vs-kernel-{S11,S22,Mises}-layer10.png`.

Settled by the reports (previously UNVERIFIED in the export recipe): values are at the element centroid (`IntPt` 1 throughout, X and Y equal to our centroids within 5e-5 mm), `Layer = 1` with `SNEG` is the bottom ply, and the outer-ply S11, S22 are in the ply's material axes (the 0-degree plies cannot distinguish material from laminate axes, so the 45-degree plies remain to be seen). The file quirks the reader handles: three identical report blocks in the S11 file and two in the S22 file, each with its own header line; instance names upper-cased by CAE.

## Not run, UNVERIFIED

- Inner plies, S12, strains, RF and U: not in the export; asked for in the export recipe's Route 3.
- The manual build after the new theory paragraph and marker (the marker test passes; the PDF was not rebuilt).
- CI with `calculix-ccx` from apt (unchanged since chunk B).
