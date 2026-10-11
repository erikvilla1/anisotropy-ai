# Material release: Toray TC380 / T1100GC and Syensqo EP2190 / IMS65 — 10 October 2026

Fourth and fifth records from the [public sources research](material-research-public-sources-2026-10-10.md), after the [8552 / IM7](material-release-im7-8552-2026-10-10.md) and [5320-1 and BT250E-6](material-release-ncamp-5320-1-bt250e-6-2026-10-10.md) releases. Two new materials, one dataset each, 20 property entries each. Rights class: open publisher data ([ADR-0018](decisions/ADR-0018-source-rights-classes.md)).

## Sources

| Record | Document | Number | Date | Fingerprint (SHA-256) | Checked |
| --- | --- | --- | --- | --- | --- |
| T1100GC / TC380 | Qualification material property data report | CAM-RP-2025-021 Rev – | 2025-09-24 | `e8297c64…bd446b` | Cover, p. 10, Table 2-1 (p. 32), pp. 24, 31, 39 to 44 |
| T1100GC / TC380 | Material allowables statistical analysis report | NCP-RP-2025-010 Rev – | 2025-10-03 | `7d334c58…cabc82` | Cover, p. 10, Table 3-1 (p. 36) |
| IMS65 / EP2190 | Qualification material property data report, phases 1 to 3 | CAM-RP-2022-001 Rev – | 2025-09-18 | `99a3d371…c5dfc` | Cover, p. 9, Table 2-1 (p. 33), pp. 26, 30, 39 to 45, 53 |
| IMS65 / EP2190 | Material allowables statistical analysis report, phases 1 to 3 | NCP-RP-2022-002 Rev – | 2025-08-28 (cover; the file name says 26 September) | `d8dfdfe8…bcf8e60` | Cover, p. 11, Table 3-1 (p. 37) |

All four covers carry "Distribution Statement A. Approved for public release; distribution is unlimited." and each report states the data "is intended for general distribution to the public" on the cited page. The PDFs were downloaded directly from the publisher with a browser user agent; the two data reports match the research copies byte for byte. Every page listed was read from a rendered image.

## What the records hold, and two differences from the earlier records

- Measured room-temperature means from the individual test summaries, each with page, layup, specimen count and method edition; nominal cured ply thickness with the measured average; longitudinal-tension panel density, fibre volume and resin content; dry and wet Tg by ASTM D7028.
- **EP2190 was tested at ambient condition, not dried.** The report defines RTA as 75 ± 5°F after at least 48 h at 60 to 80°F and 65% RH maximum (p. 26). The record says "ambient" in its conditions and every property row, and its dataset id ends in `rta` instead of `rtd`. Do not treat it as interchangeable with the dried RTD records.
- **EP2190 compression was measured directly** on [0]8 and [90]8 specimens by SACMA SRM 1R-94, so its longitudinal compressive strength is keyed `F1c` with basis "Measured mean". TC380, like the earlier records, derives it from [90/0/90]7 cross-ply tests with a back-out factor (§2.5.4, p. 41) and keeps the `F1c-derived` key. The test checks that neither record carries the other key.
- TC380 reports a compressive Poisson ratio; EP2190 reports a minor tensile Poisson ratio instead. Both are recorded as printed.
- The EP2190 dry Tg carries the report's own caveat: ambient moisture before DMA testing lowered the 337.71°F value, against a batch-release history of 377 to 406°F (p. 33).
- The NMS 380/1, NPS 83800, NMS 219/1 and NPS 82190 specifications are named; their links were not confirmed. Normalized columns and B-basis values are not copied; the statistical reports are linked as supporting references.

## Checks

- `npm test`: 64 passed, 0 failed. The new test pins the measured values, fingerprints, dates, rights class, one-record-per-report monitor adapters, the environment wording on every row, the compression key per record and the absence of normalized values from the exports.
- `npm run typecheck`: exit 0. `npm run build`: static export completed.
- Browser specs material-analysis, provenance and textbook-materials against the export: 12 passed. Both records render 20 entries with the open-publisher badge; the EP2190 summary line reads "75°F (23.9°C), ambient" and E1t displays as 22.04 Msi / 151.96 GPa; TC380 E1t displays as 22.97 Msi / 158.373 GPa.

## Not a design allowable

Values are test means for one material, process and environment. Each report states the data is not applicable when the material is not procured to its NMS specification and that applicability must be evaluated case by case.
