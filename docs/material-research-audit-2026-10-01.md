# Material library reference audit — 1 October 2026

## Subsequent textbook review

The user subsequently supplied Daniel and Ishai's second edition (2006). A full reading review and visual inspection of Appendix A now establish directly accessible textbook evidence for M10E/3783 in Tables A.5–A.6, pp. 379–380. The earlier statement below that this table had not been accessible describes the previous public-library release. The new evidence also exposes differences from the school import and conflicting printed unit pairs. See [the textbook review](textbook-review-daniel-ishai-2006.md) for page references, formula candidates, discrepancies and three independently reproduced problems. No public material release was changed by this reading review; the book's typical data are not statistical design allowables.

## Result and scope

The public lookup now contains eight explicitly cited datasets (82 property rows). Every number has a source page, units, direction, data basis, and method or model description. Fourteen imported entries are excluded from the public lookup. The original 22-record import and its transcription tests remain in the repository; those tests establish agreement with the supplied appendix, not physical accuracy or qualification.

This is a source and transcription audit, not independent laboratory validation, an engineering sign-off, or a certification of every material system. Public datasets support the uses and conditions stated on their individual records. No statistical design-allowable dataset has been released. Some records intentionally contain only the properties substantiated by the selected source; missing properties are not filled from another resin, weave, cure process, or textbook example.

## Published datasets

| Original entry | Current public dataset | Original reference and location | Data basis and limits |
|---|---|---|---|
| AS4 / 3501-6 | Unidirectional thermoelastic model; 7 properties | [Maddocks, MIT / NASA-CR-199802, May 1995](https://ntrs.nasa.gov/api/citations/19960008935/downloads/19960008935.pdf#page=95), Table 6.2, p. 95 | Published model inputs. The study assumes these constants are temperature-independent; they are not new coupon measurements or strength allowables. |
| AGP370-5H / 3501-6S | Five-harness fabric through-thickness results; 8 properties | [Daniel, Abot, Luo and Schubel, ICF11, 2005](https://www.gruppofrattura.it/ocs/index.php/ICF/ICF11/paper/download/10515/9871#page=4), Figures 3–5, PDF pp. 4–5; identity in §2.1 | Experimental figure annotations, not digitized curve estimates. Source §2.1 says 3501-6; some figure labels use 3501-6S. Public name follows §2.1. No complete in-plane dataset is asserted. |
| 7781 / E-765 | NCAMP room-temperature, dry, measured means; 12 properties | [NIAR / NCAMP CAM-RP-2023-010, Rev N/C, 25 February 2025](https://www.wichita.edu/industry_and_defense/NIAR/Documents/Park-Aerospace-Corp-7781-E765-Glass-CAM-RP-2023-010-Rev-NC-MPDR-2-25-25.pdf#page=17), summary p. 17 and individual summaries pp. 18–23 | Exact specification and process are part of the dataset. Measured and normalized columns are separate; the library uses measured means. Offset shear, shear at 5% strain and short-beam strength remain separate properties. |
| M55J | Toray M55J / EX-1515 autoclave dataset; 6 properties | [Toray EX-1515 PDS, version 5.1, 28 January 2020](https://www.toraytac.com/media/57c4813d-ce39-4b11-a5f4-11c3aaeeeef4/14xkyg/TAC/Documents/Data_sheets/Thermoset/UD%20tapes%20and%20prepregs/EX-1515_Cyanate-Ester_PDS.pdf#page=3), p. 3 | Typical values, 121°C autoclave at 85 psi, normalized to 60% fiber volume. Different from the imported vacuum-oven record. The conflicting tensile-modulus unit pair is excluded. |
| Nomex aramid core | HexWeb HRH10-1/8-1.8; 11 properties | [Hexcel HRH-10 US datasheet](https://www.hexcel.com/wp-content/uploads/2026/01/HexWeb_HRH10_DataSheet_us.pdf#page=4), p. 4 | Exact cell size and density row, L/W directions and 0.500 in specimen thickness. Supplier typical/minimum values. Access date displayed because copyright/upload dates do not establish a revision date. |
| Aluminum core | HexWeb CR III 1/8-5052-3.1; 14 properties | [Hexcel CR III datasheet](https://www.hexcel.com/wp-content/uploads/2025/12/HexWeb_CRIII_DataSheet.pdf#page=4), Table I, p. 4 | New exact supplier record, not proof that the unidentified classroom core is this product. Includes nominal density/cell size; mechanical tests use 0.625 in thickness. Minimum averages are not statistical allowables. |
| Divinycell H45 | Diab H45; 12 properties | [Diab Divinycell H, May 2026, revision 26](https://diab-media.azureedge.net/eyajkrhd/diab-divinycell-h-may-2026-rev26-si.pdf#page=1), p. 1 | Exact H45 column, nominal/minimum rows, stated directions, temperature and methods. |
| Divinycell H250 | Diab H250; 12 properties | Same Diab source, p. 1 | Exact H250 column; kept distinct from H45. |

The NASA, ICF, CR III and NCAMP source pages were visually checked using locally rendered originals. NCAMP initially returned an access challenge, but a subsequent normal monitor download succeeded. Its summary and all individual-property tables on pp. 17–23 were visually cross-checked and the actual file fingerprint is now pinned. Existing four supplier releases retain their prior checked source fingerprints. Source audit metadata is included in exports.

## Disposition of the other fourteen records

| Original entry | Reason withheld | Evidence needed to restore it |
|---|---|---|
| E-glass / 3783 | A generic E-glass/epoxy textbook dataset does not establish this resin designation. | Exact material definition and an accessible matching property table. |
| M10E / 3783 | Book/research citation leads exist, but the original baseline table was not independently accessible and checked. | Authorized original table, page and edition; establish reinforcement/resin nomenclature and conditions. |
| CF0302 / MTM49LT | Exact primary table not found. MTM46/CF0302 and MTM49-1L are different systems. The school table also contains suspect strength units/signs. | Original supplier or experimental table for CF0302/MTM49LT, including process and units. |
| BALTEK | An 8 lb/ft³ density does not identify an SB/SBC product grade. | Product series, grade, density band and finish, then the matching supplier table. |
| Carbon UD · nominal | Resin and reinforcement product unspecified. | Fiber/prepreg part number, resin, cure and fiber volume. |
| Carbon UD · wet layup | Exact fiber/resin/process unspecified. | Purchasing and manufacturing specification plus matching tests. |
| Carbon weave · nominal | Fabric and resin unspecified. | Fabric part number/weave, resin, cure and fiber volume. |
| Carbon weave · wet layup | Exact fabric/resin/process unspecified. | Purchasing and manufacturing specification plus matching tests. |
| Carbon weave · VaRTM | VaRTM alone does not identify a material system. | Fabric, resin/hardener, infusion/cure process and test basis. |
| Glass UD · nominal | Generic label; original density is also suspect. | Exact reinforcement/resin/process and original property table. |
| Glass UD · wet layup | Exact fiber/resin/process unspecified. | Purchasing and manufacturing specification plus matching tests. |
| Glass weave · nominal | Fabric and resin unspecified. | Fabric part number/weave, resin, cure and fiber volume. |
| Glass weave · wet layup | Exact fabric/resin/process unspecified. | Purchasing and manufacturing specification plus matching tests. |
| Glass weave · VaRTM | VaRTM alone does not identify a material system. | Fabric, resin/hardener, infusion/cure process and test basis. |

These entries are not silently mapped to a similar commercial composite. Their values remain preserved in `lib/materials.ts` for investigation.

## Textbooks and recent papers

Textbooks can be legitimate property references when edition, page/table, material definition and data lineage are available. [Daniel and Ishai, Engineering Mechanics of Composite Materials, second edition (2006)](https://global.oup.com/academic/product/engineering-mechanics-of-composite-materials-9780195150971) is an important lead for the imported tables. Publisher bibliography alone does not verify the numerical table. Unauthorized mirrors were not used to establish the production values.

The recent paper [An Invariant-Based Constitutive Model for Composite Laminates, Materials 19(2), 409 (2026)](https://doi.org/10.3390/ma19020409) reproduces literature constants with textbook lineage. A 2026 article date does not make those constants new 2026 measurements. The paper remains a research lead, not an independently tested replacement dataset in this release. Work on z-pinned M10E composites and other modified systems likewise cannot validate an unmodified material merely because the names overlap.

Another tempting source, [NASA/TM-2000-210252](https://ntrs.nasa.gov/citations/20000060843), tests eight-harness AS4/3501-6 fabric for a nose cap. It cannot replace unidirectional AS4 or five-harness AGP370 data. The cure and moisture conditioning also differ. This is why title matching and recent publication dates are insufficient selection rules.

## Meaning of standards and engineering use

Test standards describe procedures. They do not assign one universal elastic modulus to “carbon fiber,” and an updated standard does not retroactively change a measured value. The material system, fiber architecture, direction, cure, fiber/resin content, environment and statistical basis matter.

For NCAMP, the methods reported are ASTM D3039/D3039M-17, ASTM D3518/D3518M-18, ASTM D2344/D2344M-16 and SACMA SRM 1R-94. These historical editions stay attached to the data. The report requires the specified material procurement and process; general aircraft/design approval is not inferred from using its means.

An engineer can use the library as a traceable property reference and select inputs consistent with their analysis. A dataset that lacks required independent constants is not a complete solver material card. Strength design, qualification and certification require the applicable allowable basis and material/process equivalency. The current application is still an engineering scope preview, not a validated solver.

## Updating and remaining operational work

- Six manufacturer sources and eight ASTM catalogs remain scheduled daily while the local worker runs. Three fixed publication URLs were added: NASA AS4, ICF AGP370 and NCAMP E765. Fixed-publication checks detect replacement bytes at those URLs; they do not discover every newly published paper or a new filename elsewhere.
- Changes create review records. Downloads cannot overwrite accepted values. Four manufacturer datasets can receive separately published, immutable reviewed releases through the existing console; public adoption additionally checks material/source, units, methods, direction and conditions. Other research and CR III datasets currently require a reviewed code/data release after an update is investigated.
- All three new publication checks succeeded during the final live check. NCAMP access was intermittent during research; failed downloads are retained as failures and retried. Automated discovery of future NCAMP editions at different URLs still needs a reliable publisher index/API or authorized access.
- Source dates, access dates and library-release dates have distinct meanings. Missing publication dates are not fabricated from copyright or URL timestamps. Exported datasets retain source identifiers and hashes where actual bytes were obtained.
- The local worker must remain running. OS startup, an always-on production host, authenticated engineering reviewers, production alert delivery, commercial source-access terms and backup/recovery are still required for a production service. No claim of full autonomous updating, physical validation, ITAR compliance or certification is made by this release.

## Verification

Automated tests cover the 22-record disposition, mandatory property evidence, conversions (including signed thermal expansion), measured versus normalized NCAMP values, distinctions among shear properties, excluded conflicting Toray data, immutable export identity, replacement-release guards and rejected access-challenge HTML. Browser checks cover original-source links, dates, mobile layout, export evidence and preservation of accepted values during a source change or monitor outage.
