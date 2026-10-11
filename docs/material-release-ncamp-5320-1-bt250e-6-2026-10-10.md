# Material release: Solvay 5320-1 / T650 and TenCate BT250E-6 / IM7 — 10 October 2026

Second and third records from the [public sources research](material-research-public-sources-2026-10-10.md), following the [8552 / IM7 release](material-release-im7-8552-2026-10-10.md). Two new materials, one dataset each, 19 property entries each. Rights class: open publisher data ([ADR-0018](decisions/ADR-0018-source-rights-classes.md)).

## Sources

| Record | Document | Number | Date | Fingerprint (SHA-256) | Checked |
| --- | --- | --- | --- | --- | --- |
| T650 / 5320-1 | Qualification material property data report | CAM-RP-2013-002 Rev A | 2017-01-27 | `3f65281e…fc63ed` | Cover, p. 9, Table 2-1 (p. 22), pp. 18, 21, 24 to 28, 36 |
| T650 / 5320-1 | Qualification statistical analysis report | NCP-RP-2013-001 Rev A | 2017-04-14 | `1f90f7f2…896686` | Cover, Table 3-1 (p. 33) |
| IM7 / BT250E-6 | Qualification material property data report | CAM-RP-2015-038 N/C | 2017-10-25 | `304a088a…b82e83` | Cover, p. 6, Table 2-1 (p. 19), pp. 14, 18, 20 to 24, 26 |
| IM7 / BT250E-6 | Material allowables statistical analysis report | NCP-RP-2015-019 N/C | 2017-10-20 | `d0b9b3db…5cddbf` | Cover, Table 3-1 (p. 30) |

All four covers carry "Distribution Statement A. Approved for public release; distribution is unlimited." The data reports state (p. 9 and p. 6) that the data "is intended for general distribution to the public, either freely or at a price that does not exceed the cost of reproduction". Every page listed was read from a rendered image. The four PDFs were downloaded directly from the publisher with a browser user agent, and their fingerprints match the copies gathered during the research, so the recorded hashes are the publisher's. The 8552 / IM7 fingerprints from the previous release were re-downloaded and confirmed the same way.

## What the records hold

- Measured room-temperature dry means from the individual test summaries: E1t, E2t, ν12, G12 and both shear strengths, E1c, E2c, F1t, F2t, F2c and short-beam strength, each with its page, layup, specimen count and ASTM method edition.
- Longitudinal compressive strength from Table 2-1, which each report derives from cross-ply tests with a back-out factor; basis "Derived lamina mean".
- Nominal cured ply thickness: 0.0055 in for 5320-1 (p. 21) and 0.0058 in for BT250E-6, where the report explains the measured value was used at the supplier's request instead of the theoretical 0.0055 in (p. 18). Longitudinal-tension panel density, fibre volume and resin content; dry and wet Tg by ASTM D7028.
- Neither report gives a compressive Poisson ratio in Table 2-1, so none is recorded. The normalized columns and the B-basis values are not copied; the statistical reports are linked as supporting references. The NMS 532/5, NPS 85321, NMS 250/1 and NPS 81250 specifications are named; their links were not confirmed.
- The monitor source list now maps each NCAMP report to its own record through one table instead of the previous IM7-only loop.

## Checks

- `npm test`: 63 passed, 0 failed. The new test pins the measured values, fingerprints, dates, rights class, one-record-per-report monitor adapters, elastic-input consistency, and the absence of normalized values from the exports; it also checks every dataset id in the library is unique.
- `npm run typecheck`: exit 0.
- `npm run build`: static export completed. Browser specs material-analysis, provenance and textbook-materials against the export: 12 passed. Both records render 19 entries with the open-publisher badge; E1t displays as 20.077 Msi / 138.426 GPa (T650 / 5320-1) and 22.603 Msi / 155.842 GPa (IM7 / BT250E-6).

## Not a design allowable

Values are test means for one material, process and environment. Each report states the data is not applicable when the material is not procured to its NMS specification and that applicability must be evaluated case by case.
