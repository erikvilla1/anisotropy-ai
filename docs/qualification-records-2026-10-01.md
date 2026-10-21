# First carbon and glass engineering-reference records

Library release `2026-10-01.1`, reviewed 1 October 2026. These records supply coherent room-temperature, dry **in-plane elastic reference inputs** and separately defined strength results. They do not qualify a customer's manufactured material or release design allowables. Density, thermal response and a full 3D model are outside this release.

## Carbon: AS4 / 8552

14 properties transcribed from the measured RTD columns of [CAM-RP-2010-002 Rev A, 6 May 2011](https://www.wichita.edu/industry_and_defense/NIAR/Research/hexcel-8552/AS4-Unitape-2.pdf). Original PDF summary p. 30 and individual tables pp. 32–35, 38–39 were checked. The elastic set uses E1t = 19.09 Msi, E2t = 1.34 Msi, G12 = 0.70 Msi and ν12 = 0.302. Values normalized to 0.0074 in CPT are not substituted.

Identity: Hexcel AS4 / 8552 UD tape, 190 gsm, nominal 35% resin; NMS 128/1 Type 35 Class 1 Grade 190. The test program used original NMS 128/1 and NPS 81228 Rev A, cure M. Later listed NMS 128/1 Rev B (2013), NMS 128 Rev D (2022), and NPS 81228 Rev C (2022) are linked as supporting context, not retroactively applied to the test program. AS4/3501-6 remains a separate material.

- Longitudinal compression strength 215.29 ksi is the report's lamina value back-calculated from UNC0 cross-ply tests. It is explicitly labeled derived; the raw cross-ply strength is not used as a lamina strength.
- Offset shear strength (8.00 ksi), strength at 5% strain (13.28 ksi), and short-beam strength (16.63 ksi) remain separate quantities.
- Individual in-plane tables specify 75°F. Short-beam p. 39 specifies 70°F; its property-level conditions preserve this difference. The statistical report uses a 70°F RTD heading, so it is not used to overwrite temperatures in the measurement report.
- NCP-RP-2010-008 Rev D (26 October 2011) is linked for statistical analysis. Its recommended B-basis table has explicit exclusions; estimated/nonrecommended values are not promoted into this release.

## Glass: 7781 / E765

Default: 11 measured RTD properties from [AGATE-WP3.3-033051-105, September 2001](https://agate.niar.wichita.edu/Materials/WP3.3-033051-105.pdf). Summary p. 27 and individual tables pp. 29–33 were visually checked. The elastic set uses warp E1t = 3.73 Msi, fill E2t = 3.52 Msi, G12 = 0.70 Msi and ν12 = 0.157. The 0.0098 in normalization reference is not displayed as actual ply thickness.

Identity: FiberCote E765 / BGF 7781 E-glass, eight-harness satin. Original vacuum-bag cure 270–280°F for 110–130 minutes; 75°F, dry-as-fabricated measurements. The original manufacturing process is retained in the record.

The dataset selector also retains all 12 measured properties from [CAM-RP-2023-010 Rev N/C, 25 February 2025](https://www.wichita.edu/industry_and_defense/NIAR/Documents/Park-Aerospace-Corp-7781-E765-Glass-CAM-RP-2023-010-Rev-NC-MPDR-2-25-25.pdf). This later program does not report ν12. No 2001 Poisson's ratio has been silently combined with 2025 moduli. The later program specifies 70°F and bagging Option 2; the original baseline uses Option 1.

- Original shear strength 19.05 ksi is a D5379 V-notched-beam result. The newer D3518 ±45° tension offset and 5%-strain values are separate definitions, not direct replacements.
- Original apparent interlaminar strength p. 34 is expressly restricted to quality control. It is excluded from the 2001 analysis record.
- The 2025 statistical/equivalency report is linked, without claiming blanket equivalence of the two programs.
- NMS 765 and NMS 765/5 title pages are dated **10 March 2025**, despite filenames containing 2024. NPS 81765 is dated 9 February 2024. The library uses the documents' dates.

## Traceability and monitoring

`lib/qualification-references.json` records the 11 exact publisher URLs, source identifiers, publication precision, document revisions, page anchors and SHA-256 fingerprints. All original downloaded PDFs are preserved in the local monitor's immutable snapshot store; research copies and page renders remain under ignored `.local/research/qualification/`. Publisher PDFs are linked, not republished in the public site.

Every displayed property links to its exact PDF page. JSON exports preserve the dataset, original numeric values and units, English/SI displays, conditions, methods, basis, source fingerprint, supporting references, record revision and elastic-input mapping. A changed supporting specification also triggers the reference-details update notice. Exported records remain pinned.

All 11 documents are registered for daily byte-replacement checks while the local monitor runs. Ten passed fresh automatic checks. The historical AGATE endpoint failed Node TLS chain validation (`UNABLE_TO_VERIFY_LEAF_SIGNATURE` during investigation), although the original PDF downloaded successfully through Windows' trusted TLS stack. Its snapshot is preserved and failure/retry status is reported. TLS validation was not disabled.

These fixed-URL checks detect replacement of a listed document; they do not discover a newly named report on a publisher index. New publications require publisher-index discovery work or periodic manual review. Numerical releases from these qualification reports require reviewed code/data changes; the short-datasheet parser does not automatically publish them. No production scheduler or external notification service was deployed in this task.

## Validation

- 39 unit/data/monitor tests passed; 7 targeted browser tests passed.
- TypeScript check and production static build passed.
- Desktop carbon, desktop glass and 390px mobile glass previews inspected.
- Checks cover coherent elastic inputs, separate glass programs, exact source citations, conversion availability, export traceability, supporting-document changes and preserved values during monitor failures.
