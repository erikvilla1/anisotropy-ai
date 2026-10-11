# Material release: NASA 2023 IM7 / 8552 characterization — 10 October 2026

Sixth entry from the [public sources research](material-research-public-sources-2026-10-10.md). Not a new material: a second dataset of the existing [IM7 / 8552 record](material-release-im7-8552-2026-10-10.md), selectable through the dataset picker the library already uses for AS4 / 3501-6 and 7781 / E-765. The material count stays at 20. Rights class: open publisher data ([ADR-0018](decisions/ADR-0018-source-rights-classes.md)).

## Source

| Document | Number | Date | Fingerprint (SHA-256) | Checked |
| --- | --- | --- | --- | --- |
| Experimental Tests to Characterize the Behavior and Properties of IM7-8552 Composite (Maurya, Tanneru, Rajan, Pereira, Miller) | NASA/TM-20230001560 · E-20097 | February 2023 | `8720e1dc…7e7eeb` | Cover, notice page, Table 1 (p. 2), Tables 6, 8, 10, 12, 14, 16, 18, 20, 22 (pp. 12 to 38) and Table 31 (p. 52) |

The NASA Technical Reports Server citation page states "Public Use Permitted" with public distribution. The report notice page says it is available in electronic form at sti.nasa.gov and ntrs.nasa.gov. Contractor authors are listed and no copyright notice appears, so the report is linked from the publisher, not copied. The PDF was downloaded from the publisher and every table listed was read from a rendered page image. Printed page equals PDF page minus six; the record stores both, and reference links open the PDF page.

## What the dataset holds

- 24 entries: tensile modulus, Poisson ratio and strength in all three directions; compressive modulus and strength in all three directions; shear modulus and strength in the 1–2, 2–3 and 1–3 planes; nominal ply thickness and resin content; specific gravity.
- Values are the printed averages in psi. The record stores Msi and ksi and keeps the printed psi number as the source value, so the source viewer shows what the report prints.
- **Why it is a separate dataset.** One panel set, three replicates per test (five for longitudinal tension modulus), no prepreg lots, no statistics beyond mean and standard deviation, and no stated test temperature or conditioning. The record repeats the report's own wording, room temperature and quasi-static, instead of assuming the NCAMP 70°F dry condition. The two datasets are never merged.
- **Longitudinal compression is not comparable with NCAMP.** Measured directly on 16-ply [0] specimens in a combined loading compression fixture (ASTM D6641 geometry); the report records end-crushing and matrix splitting in the gage area. The 116.7 ksi mean is far below the 251 ksi NCAMP cross-ply back-out. The entry is keyed `F1c` with basis "Measured mean" and its conditions say why.
- **Shear.** Moduli are on an engineering shear strain basis. The 1–2 and 1–3 plane tests ran beyond 5% strain without failure, so those strengths are the stress at 5% strain (`F12-5pct`, `F13-5pct`). The 2–3 plane specimens failed at about 2% strain, so `F23` is a failure value.
- **Through-thickness tests** used geometries the report says depart from the ASTM standards: tension specimens sized by the 120-ply panel, compression cuboids adapted from ASTM D7291. The entries carry that caveat.
- Nominal ply thickness and resin content are quoted by the report from the NCAMP specification (NMS 128/2 Rev B), not measured in this program.

## Corrections to the research summary

- The longitudinal tensile strength average is 392,337 psi. The research table had 391,111 psi, which is the last replicate. Two of the five specimens debonded their tabs before failure, so the strength mean covers three specimens.
- Table 1 is on printed page 2, not page 1.
- Through-thickness compression, through-thickness tensile strength, ν31, the 2–3 and 1–3 plane shear strengths and the specific gravity were not in the research table and were added from the checked pages.

## Checks

- `npm test`: 65 passed, 0 failed. The new test pins the printed averages and source values, the page offset on every entry, the absence of the NCAMP condition wording and keys, the fingerprint, date, rights class, the monitor adapter mapped to the IM7 / 8552 record, elastic-input consistency, and that the export contains neither the mis-copied replicate nor NCAMP values.
- `npm run typecheck`: exit 0. `npm run build`: static export completed.
- Browser specs material-analysis, provenance and textbook-materials against the export: 13 passed. The new spec checks that the IM7 / 8552 card shows the NCAMP values by default, the dataset picker switches to the NASA dataset, E1t, G23 and F1c render from the new dataset, no derived compression key appears, and the E1t reference link opens page 18 of the NASA PDF.

## Not a design allowable

Small-sample means for one panel set at an unstated room temperature. The report was written to feed an impact material model, and says so on its first page.
