# Material property expansion — 2 October 2026

15 materials now expose 17 distinct datasets with 286 property entries, up from 194. The default datasets contain 262 entries. A property entry can be a scalar, an observed range, or an explicitly qualified lower bound. This is a source-transcription and unit-conversion release, not material qualification or an allowable release.

## Reviewed source coverage

| Material / dataset | Entries | Source coverage and additions |
|---|---:|---|
| AS4 / 3501-6, textbook | 27 | A.4 p. 377 and A.6 p. 380; all populated cells for this material, including 3D elastic, strength, density, volume, strains, thermal and moisture data |
| AS4 / 3501-6, NASA model | 7 | Original Table 6.2 retained as a separate selectable dataset; no textbook values mixed in |
| AS4 / 8552, NCAMP 2011 | 21 | Existing RTD lamina means plus minor compression Poisson ratio, curved-beam ILT, LT-panel physical properties, dry/wet DMA Tg; pp. 23, 30, 32, 35, 63 |
| AGP370 / 3501-6, ICF11 | 11 | All numerical material-property annotations in Figures 3–5, including failure strains; gamma31 > 7% remains an inequality |
| 7781 / E765, AGATE 2001 | 19 | Existing RTD means plus warp-panel density, fiber/resin/void ranges, actual ply-thickness range and three Tg conditions; pp. 27, 29 |
| 7781 / E765, NCAMP 2025 | 17 | Existing RTD means plus warp-panel physical properties and dry/wet Tg; pp. 17–18 |
| M55J / EX-1515 | 7 | All nonconflicting entries in the named laminate table plus explicit 60% volume normalization basis; p. 3 |
| HRH10 / 1/8 / 1.8 | 13 | Entire named mechanical row plus nominal grade density and cell size; p. 4 |
| CR III / 1/8-5052-3.1 | 14 | Entire named Table I row already present; visually rechecked p. 4 |
| Divinycell H45 | 14 | Entire H45 mechanical table column, adding 48 kg/m³ density and 12% shear strain; p. 1 |
| Divinycell H250 | 14 | Entire H250 mechanical table column, adding 250 kg/m³ density and 45% shear strain; p. 1 |
| IM6G / 3501-6 | 17 | All populated A.4 p. 377 cells |
| IM7 / 977-3 | 17 | All populated A.4 p. 378 cells |
| AS4 / APC2 | 18 | All populated A.4 p. 378 cells |
| M10E / 3783 | 23 | All populated A.5 p. 379 / A.6 p. 380 cells |
| AGP370-5H / 3501-6S | 29 | All populated A.5 / A.6 cells; separate from the ICF experimental dataset |
| 7781 / 5245C | 18 | All populated A.5 p. 379 cells |

Source fingerprints and original publication dates remain attached to the records. Textbook pages 397–400 of the supplied PDF were visually checked. All added qualification and manufacturer values were visually checked in the original source tables/figure annotations. Cited report dates are not replaced by today's library-review date.

## Corrections and definitions

- IM6G alpha1 is -0.9 microstrain/K. The previous import erroneously treated it as blank.
- 7781/5245C fiber volume is 0.45 (45%), not 0.43.
- A prior review note misidentified M10E nu23 as 0.11. Original A.6 confirms nu23 = 0.20, nu13 = 0.15, and nu12 = 0.11; the earlier review note is corrected.
- Book nu21 entries are retained as rounded tabulated reference values. Constitutive inputs remain E1, E2, G12, nu12; reciprocal ratios should be computed from those inputs.
- Moisture expansion coefficients use water-volume concentration, as defined in the book's Eq. 10.19, p. 314; they are not thermal coefficients or coefficients per percentage point. Printed zeros remain zero; dashes are absent data.
- Full orthotropic compliance is positive definite for the three expanded A.6 records. No extra transverse-isotropy equality is imposed on AS4.
- Report physical ranges describe the identified test panels, not universal lot acceptance limits. Physical data in qualification summary headers are panel-specific and must not be presented as identical across all tested panels.
- Tg dry/wet states and methods are preserved. Tg is not a maximum service temperature.
- The NCAMP 2011 minor compressive Poisson ratio follows the nu21 notation in summary Table 2-1; p. 35's differently labeled transverse-test ratio is not silently used as nu12.

## Deliberate boundaries

The lookup exposes source-covered material properties; it does not flatten every raw specimen result, statistical distribution, test environment, laminate layup, open-hole or bearing test into a single material card. Current qualification mechanical datasets remain RTD. Such other conditions and laminate configurations require their own datasets. Nominal prepreg data and thickness-normalization references are not substituted for measured cured-material properties.

The supplied 2002 MIL-HDBK-17-2F index was screened for current names. AS4/3501-6 bleed/no-bleed and fabric programs are separate manufacturing-specific datasets, not missing cells to copy into the textbook record. Indexed IM7/977-2, IM6/APC-2, M55J/954-3 and 7781/EA9396 are different from this catalog's IM7/977-3, AS4/APC2, M55J/EX-1515 and 7781/E765. No new handbook numerical dataset is claimed in this release. Volume 3 is design context, not a substitute for a named material's measured properties.

The Toray M55J tensile-modulus row still conflicts internally (354 GPa versus 50 Msi). It is not released as a verified scalar. Missing cells, unrelated grades and the 13 previously archived school records are not filled with estimates. This release does not claim every material has a full 3D model or design allowables.

## Software and release integrity

- Expanded records get new dataset IDs or record revisions. NASA model values remain selectable separately; the textbook AS4 dataset is the default.
- Supplier supplements apply only to their exact reviewed PDF fingerprint; they cannot silently follow a changed supplier document.
- JSON export schema 2 explicitly labels scalar, range and lower-bound values and retains endpoints/qualifiers, sources and units.
- Absolute-temperature conversion applies the Fahrenheit offset; expansion coefficients use temperature-increment scaling. Range endpoints and the > qualifier survive both display and export.
- Strength-group filters now include failure strains; Tg is grouped with thermal properties.
- Six-month publication notifications remain unchanged. Numerical publication still requires review.

## Verification

Source cells, citations, elastic compliance, unit conversions, source identity separation, ranges, lower bounds and fingerprint pinning are covered by data tests. Production build and browser/export checks are run for this release; results are recorded in the task completion.

Release checks completed: 48 unit/data tests passed; 10 targeted browser tests passed; production build passed. Desktop tables, physical ranges and the 390px mobile strength view were visually inspected. The final export-schema checks were rerun after schema 2 was added.
