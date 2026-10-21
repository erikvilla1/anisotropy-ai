# Material release: Hexcel 8552 / IM7 unidirectional — 10 October 2026

First record added from the [public sources research](material-research-public-sources-2026-10-10.md). One new material, one dataset, 21 property entries. Rights class: open publisher data ([ADR-0018](decisions/ADR-0018-source-rights-classes.md)).

## Source

| Document | Number | Date | Fingerprint (SHA-256) | Checked |
| --- | --- | --- | --- | --- |
| Qualification material property data report | CAM-RP-2009-015 Rev B | 2019-04-16 | `640c215e…211387` | Cover, p. 9, Table 2-1 (p. 28), pp. 22, 26, 30 to 34, 37 read from rendered page images |
| Qualification statistical analysis report | NCP-RP-2009-028 Rev B | 2019-04-16 | `6313ba07…9628d` | Cover, p. 10, Table 3-1 (p. 35) |

Both covers carry "Distribution Statement A. Approved for public release; distribution is unlimited." Page 9 of the data report states the data "is intended for general distribution to the public, either freely or at a price that does not exceed the cost of reproduction". The publisher's site blocks automated downloads; the copies came from a browser-equivalent fetch and are kept in ignored `.local/sources/ncamp/`, never in the repository.

## What the record holds

- Measured room-temperature dry means from the individual test summaries: E1t, E2t, ν12 (p. 30, 31), G12 and both shear strengths (p. 34), E1c, ν12c (p. 32), E2c, ν21c, F2c (p. 33), F1t, F2t, short-beam strength (p. 37).
- Longitudinal compressive strength from Table 2-1 (p. 28), which the report derives from cross-ply tests with a back-out factor; basis "Derived lamina mean".
- Nominal cured ply thickness 0.0072 in (p. 28, explained p. 26), longitudinal-tension panel density, fibre volume and resin content (p. 30), dry and wet Tg (p. 28).
- The normalized column and the B-basis values are not copied; the statistical report is linked as a supporting reference. The NMS 128 base specification and NPS 81228 process specification already in the library are linked; the NMS 128/2 detail specification link could not be confirmed and is named only.

## Checks

- `npm test`: 62 passed, 0 failed. The new test pins the measured values, the fingerprint, the rights class, the monitor adapters (the two IM7 reports attach to the IM7 record, not to AS4/8552, which shares the "8552" name) and the absence of normalized values from the export.
- `npm run typecheck`: exit 0.
- `npm run build`: static export completed. Browser specs material-analysis, provenance and textbook-materials against the export: 12 passed. The rendered record shows 21 entries with the open-publisher badge; E1t displays as 23.51 Msi / 162.096 GPa.

## Not a design allowable

Values are test means for one material, process and environment. NCAMP states the data is not applicable when the material is not procured to NMS 128/2 (p. 9) and that applicability must be evaluated case by case.
