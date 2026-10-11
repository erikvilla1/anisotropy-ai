# Material release: library completion — 10 October 2026

Last entries from the [public sources research](material-research-public-sources-2026-10-10.md): three NCAMP plain weave fabric records and two historical records from the canceled MIL-HDBK-17-2F. With these the public library holds 25 materials and the research document is closed out. Rights classes per [ADR-0018](decisions/ADR-0018-source-rights-classes.md): open publisher data for NCAMP, public domain for the handbook.

## NCAMP plain weave records

| Record | Document | Number | Date | Fingerprint (SHA-256) | Checked |
| --- | --- | --- | --- | --- | --- |
| AS4 PW / 8552S | Qualification material property data report | CAM-RP-2010-006 N/C | 2011-04-14 | `76fdace8…efec7a` | Cover, p. 9, Table 2-1 (p. 29); pp. 22, 27, 31 to 35 by text |
| AS4 PW / 8552S | Qualification statistical analysis report | NCP-RP-2010-011 Rev B | 2012-11-15 | `91b135a8…fb3c69` | Cover, Table 3-1 (p. 33) |
| T650 PW / 5320-1 | Qualification material property data report | CAM-RP-2012-017 N/C | 2015-10-13 | `edcf939a…9438b0` | Cover, p. 8, Table 2-1 (p. 21); pp. 9, 20, 23 to 27 by text |
| T650 PW / 5320-1 | Material allowables statistical analysis report | NCP-RP-2012-023 N/C | 2015-10-13 | `38bf7101…5b6f91` | Cover, Table 3-1 (p. 34) |
| HTS40 PW / TC250 | Material property data report | CAM-RP-2011-005 Rev A | 2016-09-26 | `ccd1717a…68a8c1` | Cover, p. 9, Table 2-1 (p. 26); pp. 19, 24, 28 to 32 by text |
| HTS40 PW / TC250 | Statistical analysis report | NCP-RP-2010-076 N/C | 2016-09-26 | `4d63b50b…5e79e` | Cover, Table 3-1 (p. 32) |

Each data report states the data "is intended for general distribution to the public" on the page cited. The 5320-1 covers also carry Distribution Statement A; the 2011 Hexcel and 2016 TenCate covers do not, as the research noted. All PDFs were downloaded from the publisher with a browser user agent. Table 2-1 of each data report was read from a rendered page image and every entered value was taken from its measured RTD column; the individual test pages supplied the method editions, layups and panel properties.

What the fabric records hold, and how they differ from the tape records:

- Warp is axis 1 and fill is axis 2, as each report's symbol list states. Entries: warp and fill tensile and compressive moduli and strengths, tensile Poisson ratio, in-plane shear modulus and strengths, short-beam strength, nominal cured ply thickness, warp-tension panel density, fiber volume and resin content, dry and wet Tg.
- **Compression is measured directly** on [0] and [90] fabric specimens by ASTM D6641, so warp and fill compressive strengths are keyed `F1c` and `F2c` with basis "Measured mean". No cross-ply back-out is involved.
- The 8552S / AS4 report prints no 5% strain shear strength for the RTD condition, so only the 0.2% offset value is recorded. The other two carry both.
- The TC250 report prints a composite density of 1.207 g/cm³ on every test summary. That is inconsistent with the fiber volume and resin content printed beside it, could not be verified, and was not entered. UNVERIFIED. The record says so.
- TC250's elevated-temperature condition is 180°F and its dry Tg is 259°F; the record's application text points this out.

## MIL-HDBK-17-2F historical records

| Document | Source | Date | Fingerprint (SHA-256) | Checked |
| --- | --- | --- | --- | --- |
| MIL-HDBK-17-2F, Volume 2 of 5 | DLA ASSIST, ident 53882 (529 pages) | 2002-06-17 | `a0368e32…58ff8b` | Cover, foreword, p. 17, pp. 299 to 304, pp. 429 to 437 |
| MIL-HDBK-17-2F Notice 1, cancellation | DLA ASSIST, ident 53882 (1 page) | 2013-03-26 | `f488d0c0…e69e1af` | Whole page |

The official copies came from the Defense Logistics Agency ASSIST database, not from a mirror. ASSIST stamps every page with the download time, so the fingerprints identify this dated copy rather than a stable file; the page numbering matches the everyspec copy used for the research (Table 4.2.29(c) on PDF page 303, Table 6.2.4(d) on 434). Rights: the cover carries Distribution Statement A and the document is a Department of Defense handbook. The foreword records that the secretariat work was performed by Materials Sciences Corporation under an Army contract, which counsel should look at; the records say so. The cancellation notice is linked as a supporting reference of both records, and every record, condition line and dataset label says the handbook was canceled on 26 March 2013.

What the handbook records hold:

- **T650-35 / 976 unidirectional tape, Section 4.2.29 (12 entries).** Longitudinal tension (B30 strength, Mean modulus), transverse tension and compression (B18 strengths, Screening moduli), in-plane shear (B30 strength, Mean modulus), nominal ply thickness and fiber volume, dry and wet Tg. The handbook prints no Poisson ratio and no longitudinal compression, so the record has no elastic input set and says why.
- **E-glass 7781 / EA 9396 8-harness satin, wet lay-up, Section 6.2.4 (15 entries).** Warp and fill tension and compression (Interim), both tensile Poisson ratios (Screening), in-plane shear (Interim), nominal ply thickness, fiber volume and density. Every table of this material carries the handbook's warning that required documentation was not supplied; the record's condition line repeats it. This is a different material and process from the 7781 / E-765 prepreg record and stays separate.
- **Data classes are the basis.** The handbook prints a class for every value (Table 1.4.2(c): A75, A55, B30, B18, Mean, Interim, Screening). The record keeps that class as the value's basis instead of "Measured mean", and the test checks that only those classes appear. B-basis values and normalized columns stay in the handbook; the measured column is used where the handbook normalizes.
- Condition A is 72°F with ambient moisture and no stated drying. The records say "72°F, ambient" and never claim the NCAMP dry condition.
- The policy for public-domain sources allows hosting a copy. None is hosted: the repository rule against PDFs under public assets stands, and the official ASSIST record is linked instead.

## Checks

- `npm test`: see the pull request for the count. New tests pin the measured values, fingerprints, dates, rights classes, warp and fill directions, the direct compression basis, the absence of normalized values and of the unverified TC250 density from the exports, the handbook data classes as the only bases, the cancellation wording, and the monitor adapters (one record per NCAMP report; both handbook records on the ASSIST entry).
- `npm run typecheck` and `npm run build`: see the pull request.
- Browser spec: the TC250 card shows warp direction, measured compression and a page link into the publisher PDF; the T650-35 / 976 card shows the public-domain badge, the cancellation wording, the B30 basis and a page link to the ASSIST record.

## Not entered, and why

MTM45-1 / IM7 (its Rev C report carries no distribution sentence), MTM45-1 / HTS40, NCT4708 / MR60H and 3960 / T1100GC (values read from extracted text only and not visually checked), the NASA 2020 Boeing coupon report (backed-out values that would duplicate the two IM7 / 8552 datasets), the older NASA reports and the open-access papers (partial property sets). They remain listed in the research document for a future phase.

## Not a design allowable

Values are test means, or handbook means with their printed data class, for one material, process and environment. The handbook itself says it is for guidance only and that verifying statistical properties is the user's responsibility.
