# Public material data sources — 10 October 2026

Research record for the question "where can the website get lamina property values it is allowed to show?" Rights classes follow [ADR-0018](decisions/ADR-0018-source-rights-classes.md). Nothing here is a design allowable, and nothing has been entered in the library yet; each candidate still needs the visual table check the existing records had.

Three sources were searched: NCAMP qualification reports, the public-domain MIL-HDBK-17F handbook, and NASA reports, open-access papers and manufacturer datasheets. All page numbers are PDF pages unless printed pages are stated. Units are as printed.

## Summary

| Source class | What it offers | Rights | Recommendation |
| --- | --- | --- | --- |
| NCAMP qualification reports (NIAR, Wichita State) | Measured room-temperature means for 20 current prepreg systems; B-basis in separate statistical reports | Open publisher data: "intended for general distribution to the public" (quoted below) | Best source. Add the best-documented unitape systems first |
| MIL-HDBK-17-2F (2002) | Interim and screening data for 1980s to 1990s systems; four systems extracted | Public domain (Distribution Statement A); canceled 26 March 2013 | Historical only; label as canceled. Useful for T650-35/976 and 7781/EA9396 |
| NASA Technical Reports Server | Seven reports with lamina tables: IM7/8552 (two, 2020 and 2023), T300/5208, AS4/APC-2, AS4/PEEK, IM7/977-2 with T800/3900, AS4/3501-6 | Open publisher data: citation pages state "Public Use Permitted"; the older ones "Work of the US Gov." | Add the 2023 IM7/8552 report first; it is the most complete measured set |
| Open-access papers (CC BY) | Three papers with measured values, several with compiled values | CC BY 4.0 (quoted licence tags); one CC BY-NC-ND paper excluded | Low priority: mostly partial sets or non-Western systems |
| Manufacturer datasheets | Hexcel 8552 (US and EU), M21, IM7 fibre; Toray T700S, T800S, 2510, 3900 | Open publisher data; "typical" values with no-warranty disclaimers | Good for ply thickness, fibre volume and cross-checks, not as primary records |

## 1. NCAMP qualification reports

Index page: https://www.wichita.edu/industry_and_defense/NIAR/Research/ncamp.php. MPDR is the Material Property Data Report, SAR the Statistical Analysis Report. Thirteen reports were downloaded and text-extracted; the library already holds the 2011 Hexcel 8552/AS4 unitape report (CAM-RP-2010-002), which was not redone.

### Rights and distribution

- Cover of the newer reports (8552/IM7 Rev B, 5320-1 T650 unitape and plain weave, BT250E-6 IM7, EP2190 IMS65, TC380, 3960, SAR NCP-RP-2009-028 Rev B): "Distribution Statement A. Approved for public release; distribution is unlimited." The older covers (8552 AS4 plain weave 2011, NCT4708 2011, TC250 2016, MTM45-1 HTS40 2016, MTM45-1 IM7 Rev C 2024) do not carry it.
- Body statement (8552/IM7 MPDR p. 9; same sentence in SAR p. 10 and in the 5320-1, BT250E-6, EP2190, TC380, NCT4708, TC250 and MTM45-1 HTS40 reports): "The data contained in this report is intended for general distribution to the public, either freely or at a price that does not exceed the cost of reproduction (e.g. printing) and distribution (e.g. postage)." The Hexcel reports add that export-controlled data, if any, is withheld and available on request.
- Exception: MTM45-1/IM7 Rev C (CAM-RP-2008-007, February 2024) carries neither sentence in the extracted text. Its public posting on wichita.edu is the only evidence; treat redistribution of its numbers as UNVERIFIED.
- Use condition (5320-1 T650 MPDR p. 8, repeated in every scope section): "The applicability of NCAMP material property data, material allowables, and specifications must be evaluated on case-by-case basis by aircraft companies and certifying agencies. NCAMP assumes no liability whatsoever." MPDR values are test means; B-basis values are in the SARs and are "recommended" only when they meet all CMH-17-1G requirements (NCP-RP-2009-028 Rev B pp. 9, 34).
- No ITAR, EAR or ECCN marking was found in any of the 13 reports. No copyright notice or licence text was found either.
- NCAMP's standard operating procedure NSP 100 Rev G (27 March 2017) is a web page: https://www.wichita.edu/industry_and_defense/NIAR/Research/nsp100-sop.php. FAA memo AIR100-2010-120-003 (20 September 2010) describes NCAMP as "a source of non-proprietary" specifications and allowables.

### Systems with published reports

| # | System | MPDR | SAR | Opened |
| --- | --- | --- | --- | --- |
| 1 | Hexcel 8552 / IM7 12k UD tape, 190 gsm, 35% RC | CAM-RP-2009-015 Rev B, 16 Apr 2019 | NCP-RP-2009-028 Rev B, 16 Apr 2019 | Both |
| 2 | Hexcel 8552S / AS4 3k plain weave, 193 gsm, 38% RC | CAM-RP-2010-006 N/C, 14 Apr 2011 | NCP-RP-2010-011 Rev B, 15 Nov 2012 | MPDR |
| 3 | Hexcel 8552S / AS4 3k 8HS (Spirit) | Spirit-CAM-RP-2019-057 Rev 7, 16 Jan 2025 | NCP-RP-2019-013 Rev 6, 2 Dec 2025 | No |
| 4 | Solvay Cycom 5320-1 / T650 unitape Gr 145, 33% RC | CAM-RP-2013-002 Rev A, 27 Jan 2017 | NCP-RP-2013-001 Rev A | MPDR |
| 5 | Cytec 5320-1 / T650 3k plain weave | CAM-RP-2012-017 N/C, 13 Oct 2015 | NCP-RP-2012-023 N/C | MPDR |
| 6 | Solvay (ACG) MTM45-1 / IM7 12k UD, 145 gsm, 32% RW | CAM-RP-2008-007 Rev C, 12 Feb 2024 | NCP-RP-2008-006 Rev B, 26 Jan 2024 | MPDR |
| 7 | Cytec MTM45-1 / HTS40 12k UD, 145 gsm, 32% RW | CAM-RP-2009-010 Rev B, 25 Mar 2016 | NCP-RP-2009-008 N/C | MPDR |
| 8 | MTM45-1 with AS4 UD, AS4 PW, G30-500 PW, 7781 E-glass, 6781 S2-glass | Mixed; some values-only sheets | Several | No |
| 9 | TenCate TC250 / HTS40 12k fabric, 42% RC | CAM-RP-2011-005 Rev A, 26 Sep 2016 | NCP-RP-2010-076 N/C | MPDR |
| 10 | TenCate BT250E-6 / IM7 GP 12k unitape, 148 gsm, 33% RC | CAM-RP-2015-038 N/C, 25 Oct 2017 | NCP-RP-2015-019 N/C, 20 Oct 2017 | MPDR |
| 11 | BT250E-6 / AS4C 3k PW; BT250E-6 / S2 glass unitape | CAM-RP-2015-039 N/C; S2 report | NCP-RP-2015-020; NCP-RP-2015-021 | No |
| 12 | Newport NCT4708 / MR60H 300 gsm UD, 38% RC | CAM-RP-2010-041 Rev A, 19 Aug 2011 | NCP-RP-2010-074 N/C | MPDR |
| 13 | Syensqo EP2190 / IMS65 24k unitape Gr 145, 35% RC | CAM-RP-2022-001, 18 Sep 2025 | NCP-RP-2022-002, 26 Sep 2025 | MPDR |
| 14 | EP2190 / T650 3k PW | CAM-RP-2022-002, 18 Sep 2025 | NCP-RP-2022-003, 3 Sep 2025 | No |
| 15 | Toray TC380 / T1100GC 24K unitape, 120 gsm, 35% RC | CAM-RP-2025-021, 24 Sep 2025 | NCP-RP-2025-010, 3 Oct 2025 | MPDR |
| 16 | TC380 / T800HB 6K 2x2 twill | CAM-RP-2025-023, 29 Sep 2025 | NCP-RP-2025-011, 3 Oct 2025 | No |
| 17 | Toray CMA 3960 / T1100GC 24K UD, 192 gsm, 33.5% RC | CAM-RP-2024-004 Rev A, 4 Sep 2025 (file name says DRAFT; listing page says 2024-002) | NCP-RP-2024-004 Rev A, 18 Sep 2025 | MPDR |
| 18 | Toray 3960 / T1100GC slit tape (AFP) | CAM-RP-2023-002 Rev B, 2 Jan 2026 | NCP-RP-2023-002 Rev B, 5 Jan 2026 | No |
| 19 | Toray Cetex TC1225 (LM-PAEK) / T700GC UD | CAM-RP-2019-036 Rev A, 10 May 2021 | NCP-RP-2019-011 Rev A, 14 May 2021 | No |
| 20 | Renegade RM-2014 / 4581 8HS quartz | CAM-RP-2024-007 Rev A, 8 Oct 2025 | NCP-RP-2024-002 Rev A, 8 Oct 2025 | No |

Document URLs are on the index page and its per-system pages; the scratch copies used for this review are not kept in the repository. Not found on the NCAMP page: Hexcel 8552/IM7 slit tape, Hexcel M21/IM7, Park E-752, Toray 3900-2/T800S and Toray T700/2510 (the last is an AGATE-era report on https://agate.niar.wichita.edu; its rights were not checked).

### Room-temperature dry lamina means

"N / M" is normalized / measured mean. A single value is measured only. F1cu marked "from UNC0" is backed out from a cross-ply laminate, as the report states. Shear is ASTM D3518 at 0.2% offset and at 5% strain. Values for systems 1, 4, 6 and 10 were cross-checked between Table 2-1 and the per-test summary pages; the rest were read from extracted text where the room-temperature column is the second pair, and need a visual check before entry.

**1. Hexcel 8552 / IM7 unitape, CAM-RP-2009-015 Rev B.** Table 2-1 p. 28; tests pp. 30 to 34; 70 °F dry.

| Property | Value | Unit | Page |
| --- | --- | --- | --- |
| F1tu | 362.69 / 371.08 | ksi | 28, 30 |
| E1t | 22.99 / 23.51 | Msi | 28, 30 |
| nu12t | 0.316 | — | 30 |
| F2tu | 9.29 | ksi | 31 |
| E2t | 1.30 | Msi | 31 |
| F1cu (from UNC0) | 248.94 / 251.13 | ksi | 28 |
| E1c | 20.04 / 20.44 | Msi | 32 |
| nu12c | 0.356 | — | 32 |
| F2cu | 41.44 | ksi | 33 |
| E2c | 1.41 | Msi | 33 |
| F12s 0.2% / 5% | 7.76 / 13.22 | ksi | 34 |
| G12s | 0.68 | Msi | 34 |
| SBS | 17.13 | ksi | 28 |
| CPT (normalization) | 0.0072 | in | 28 |
| Resin content, Vf (LT panels) | 35.33 % wt, 57.30 % | — | 30 |
| Tg dry (DMA) | 406.43 | °F | 28 |

**4. Solvay Cycom 5320-1 / T650 unitape, CAM-RP-2013-002 Rev A.** Table 2-1 p. 22; tests pp. 24 to 28; 70 °F dry.

| Property | Value | Unit | Page |
| --- | --- | --- | --- |
| F1tu | 299.093 / 299.004 | ksi | 24 |
| E1t | 20.082 / 20.077 | Msi | 24 |
| nu12t | 0.326 | — | 24 |
| F2tu | 10.096 | ksi | 25 |
| E2t | 1.331 | Msi | 25 |
| F1cu (from UNC0) | 237.098 / 237.875 | ksi | 22 |
| E1c | 18.301 / 18.356 | Msi | 26 |
| F2cu | 39.751 | ksi | 27 |
| E2c | 1.427 | Msi | 27 |
| F12s 0.2% / 5% | 8.121 / 13.501 | ksi | 28 |
| G12s | 0.718 | Msi | 28 |
| SBS | 15.639 | ksi | 22 |
| CPT | 0.0055 | in | 22 |
| Resin content, Vf (LT panels) | 30.66 % wt, 61.88 % | — | 24 |
| Tg dry (D7028) | 389.13 | °F | 22 |

**6. Solvay MTM45-1 / IM7 unitape, CAM-RP-2008-007 Rev C.** Table 2-1 p. 22; tests pp. 24 to 28; 75 °F dry. Rights sentence absent, see above.

| Property | Value | Unit | Page |
| --- | --- | --- | --- |
| F1tu (from UNT0) | 357.65 / 343.61 | ksi | 22 |
| E1t | 22.90 / 22.00 | Msi | 24 |
| F2tu | 7.59 | ksi | 25 |
| E2t | 1.11 | Msi | 25 |
| F1cu (from UNC0) | 181.54 / 177.80 | ksi | 22 |
| E1c | 20.24 / 19.84 | Msi | 26 |
| nu12c | 0.361 | — | 26 |
| F2cu | 27.96 | ksi | 27 |
| E2c | 1.22 | Msi | 27 |
| nu21c | 0.026 | — | 27 |
| F12s 0.2% / 5% | 6.386 / 10.45 | ksi | 28 |
| G12s | 0.566 | Msi | 28 |
| SBS | 14.47 | ksi | 22 |
| CPT | 0.0055 | in | 22 |
| Tg dry (DMA) | 349.06 | °F | 22 |

**10. TenCate BT250E-6 / IM7 GP unitape, CAM-RP-2015-038 N/C.** Table 2-1 p. 19; tests pp. 20 to 24; 70 °F dry.

| Property | Value | Unit | Page |
| --- | --- | --- | --- |
| F1tu | 346.642 / 355.785 | ksi | 20 |
| E1t | 22.015 / 22.603 | Msi | 20 |
| nu12t | 0.309 | — | 20 |
| F2tu | 5.701 | ksi | 21 |
| E2t | 1.248 | Msi | 21 |
| F1cu (from UNC0) | 205.905 / 213.784 | ksi | 19 |
| E1c | 19.426 / 20.228 | Msi | 22 |
| F2cu | 27.527 | ksi | 23 |
| E2c | 1.340 | Msi | 23 |
| F12s 0.2% / 5% | 6.709 / 10.084 | ksi | 24 |
| G12s | 0.629 | Msi | 24 |
| SBS | 9.874 | ksi | 19 |
| CPT | 0.0058 | in | 19 |
| Tg dry (D7028) | 281.24 | °F | 19 |

**Read from extracted text only (visual check required before entry).**

| System, report, table page | F1tu | E1t | nu12 | F2tu | E2t | F1cu | E1c | F2cu | E2c | F12s 0.2% / 5% | G12s | CPT in |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7. MTM45-1 / HTS40 UD, CAM-RP-2009-010 Rev B, p. 24 | 310.72 / 306.84 | 19.00 / 18.76 | 0.350 (c) | 8.72 | 1.20 | 193.30 / 195.27 | 17.02 / 17.20 | 28.29 | 1.26 | 6.07 / 10.18 | 0.57 | 0.0055 |
| 12. NCT4708 / MR60H UD, CAM-RP-2010-041 Rev A, p. 31 | 366.07 / 366.03 | 20.63 / 20.63 | 0.337 (t), 0.355 (c) | 5.75 | 1.12 | 191.78 / 196.12 | 18.45 / 18.80 | 23.98 | 1.23 | 6.10 / 7.80 | 0.55 | 0.0126 |
| 13. EP2190 / IMS65 UD, CAM-RP-2022-001, p. 33 (75 °F) | 430.6 / 415.8 | 22.81 / 22.04 | 0.3299 (t) | 11.14 | 1.255 | 218.1 / 207.7 | 20.56 / 19.72 | 41.31 | 1.503 | 6.187 / 10.63 | 0.6053 | 0.0056 |
| 15. TC380 / T1100GC UD, CAM-RP-2025-021, p. 32 | 472.6 / 475.3 | 22.84 / 22.97 | 0.3132 (t), 0.3621 (c) | 10.70 | 1.111 | 226.7 / 236.2 | 20.85 / 20.83 | 29.33 | 1.198 | 6.369 / 11.16 | 0.5740 | 0.0048 |
| 17. 3960 / T1100GC UD, CAM-RP-2024-004 Rev A, p. 30 | 547.7 / 544.8 (supplier knockdown of 18.4 ksi applied) | 24.94 / 24.82 | 0.3428 (t), 0.3751 (c) | 9.890 | 1.335 | 298.9 / 293.6 | 22.18 / 21.87 | 37.53 | 1.386 | 8.176 / 13.01 (5% UNVERIFIED column) | 0.7219 | 0.0072 |
| 2. 8552S / AS4 3k PW, CAM-RP-2010-006, p. 29 (warp / fill) | 109.02 / 111.52 | 9.36 / 9.58 | 0.046 | 107.62 / 109.19 | 9.51 / 9.66 | 115.13 / 122.37 | 8.65 / 9.20 | 109.12 / 113.31 | 8.67 / 9.01 | 8.11 / — | 0.72 | 0.0078 |
| 5. 5320-1 / T650 3k PW, CAM-RP-2012-017, p. 21 | 121.838 / 124.900 | 9.738 / 9.990 | 0.053 | 118.678 / 121.810 | 9.678 / 9.931 | 102.675 / 106.167 | 9.030 / 9.370 | 98.149 / 100.365 | 8.680 / 8.876 | 8.299 / 14.650 | 0.735 | 0.0077 |
| 9. TC250 / HTS40 fabric, CAM-RP-2011-005 Rev A, p. 26 | 130.41 / 126.33 | 8.94 / 8.66 | 0.040 (t), 0.051 (c) | 125.98 / 121.76 | 8.88 / 8.58 | 101.26 / 100.14 | 8.12 / 8.02 | 91.91 / 89.96 | 8.23 / 8.04 | 5.72 / 9.87 | 0.52 | 0.0085 |

Only the 3960 report gives thermal expansion (Section 10, p. 526): transverse 28.68, 31.57 and 33.69 and through-thickness 33.95, 38.24 and 47.58 for the ranges -55 to 20 °C, 20 to 70 °C and 70 to 120 °C, units printed as "m/(m C)" with symbols lost in extraction, presumed µm/(m·°C), UNVERIFIED. Fiber-direction expansion is "available upon request to Toray".

## 2. MIL-HDBK-17F (2002), public domain

Volumes 1 and 2 were downloaded from everyspec.com and read; the cover of each states "DISTRIBUTION STATEMENT A. Approved for public release; distribution is unlimited." and "This handbook is for guidance only. Do not cite this document as a requirement." DTIC blocked automated access, so the accession number ADA426516 (Volume 1) rests on search-result titles, UNVERIFIED. The official record for Volume 2 is ASSIST ident 53882 (https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=53882): Rev F, 17 June 2002, 529 pages, **canceled 26 March 2013**. The website must say so.

Rights: 17 U.S.C. § 105 bars US copyright in works of the United States Government. The handbook's acknowledgement states the secretariat work was performed under Army contract DAAL01-97-C-0140 by Materials Sciences Corporation, which is a nuance counsel should look at; the Distribution Statement A records the publisher's intent either way. A full-text search of Volume 2 for copyright, proprietary, permission, trademark and the © ® ™ symbols found nothing.

Data classes (Volume 2 Table 1.4.2(c), printed p. 1-8; definitions in Volume 1 Section 2.5.1, printed pp. 2-78 to 2-80): A75, A55, B30, B18, Mean, Interim, Screening. B-basis values are printed only for A and B classes. Volume 2 Section 1.2 (printed pp. 1-1 to 1-2): the data "allow initial assessments of material adequacy"; verification of statistical properties "is the responsibility of the user".

Volume 2 Chapter 4 lists 35 carbon/epoxy systems, but 11 of them (including IM7/8552, IM6/3501-6, T300/977-2 and IM7/977-2) say only "These data are presented in the MIL-HDBK-17-2F Annex A", which is not in the public PDF and was not found elsewhere, UNVERIFIED. Chapter 6 has four glass/epoxy systems. Chapter 5 (aramid) and Chapters 7 to 10 are placeholders.

Values extracted (all verified against rendered page images; strengths ksi, moduli Msi):

| System and section | Property | Normalized / measured | Class | Table (printed p. / PDF p.) |
| --- | --- | --- | --- | --- |
| T650-35 12k/976 UD tape, 4.2.29, 61% Vf nominal, CPT 0.0052 in | F1tu | 231 / 236 (B-value 202 / 200) | B30 | 4.2.29(a) (4-230 / 301) |
| | E1t | 22.0 / 22.5 | Mean | same |
| | F2tu | 5.71 (B-value 4.42) | B18 | 4.2.29(b) (4-231 / 302) |
| | E2t | 1.30 | Screening | same |
| | F2cu | 33.6 (B-value 28.1) | B18 | 4.2.29(c) (4-232 / 303) |
| | E2c | 1.38 | Screening | same |
| | F12su, [±45]4s D3518 | 14.9 (B-value 8.57) | B30 | 4.2.29(d) (4-233 / 304) |
| | G12s | 0.745 | Mean | same |
| | nu12, F1cu, E1c | no lamina data in the public PDF | | |
| AS4/3501-6 (bleed) UD tape, 4.2.12, 60% Vf nominal; documentation warning on every table | F1tu | 291 / 295 | Interim | 4.2.12(a) (4-113 / 184) |
| | E1t | 19.6 / 19.9 | Interim | same |
| | F2tu | 7.78 | Screening | 4.2.12(b) (4-114 / 185) |
| | E2t | 1.48 | Screening | same |
| | F1cu, SACMA SRM 1-88 | 210 / 214 | Interim | 4.2.12(c) (4-115 / 186) |
| | E1c | 17.8 / 18.8 | Screening | same |
| | SBS | 17.3 | Screening | 4.2.12(e) (4-117 / 188) |
| | nu12, G12, F12 | no data | | |
| T-300 3k/934 plain weave, 4.2.6, normalized to 57% Vf, CPT 0.0077 in; pre-1989 documentation warning | F1tu warp | 91 / 94 | Interim | 4.2.6(a) (4-44 / 115) |
| | E1t | 9.1 / 9.4 | Interim | same |
| | F2tu fill | 88 / 91 | Interim | 4.2.6(c) (4-46 / 117) |
| | E2t | 9.0 / 9.3 | Interim | same |
| | F1cu, SACMA SRM 1-88 | 95 / 98 | Interim | 4.2.6(e) (4-48 / 119) |
| | E1c | 8.4 / 8.8 | Interim | same |
| E-glass 7781/EA 9396 8HS wet lay-up, 6.2.4, normalized to 50% Vf, CPT 0.0085 in; documentation warning; high batch variability noted | F1tu warp | 48.3 / 51.8 | Interim | 6.2.4(a) (6-38 / 431) |
| | E1t | 3.39 / 3.62 | Interim | same |
| | nu12t | 0.115 | Screening | same |
| | F2tu fill | 50.5 / 54.3 | Interim | 6.2.4(b) (6-39 / 432) |
| | E2t | 3.41 / 3.67 | Interim | same |
| | nu21t | 0.127 | Screening | same |
| | F1cu, D3410B | 46.4 / 49.6 | Interim | 6.2.4(d) (6-41 / 434) |
| | E1c | 3.45 / 3.68 | Interim | same |
| | F2cu | 37.7 / 40.8 | Interim | 6.2.4(e) (6-42 / 435) |
| | E2c | 3.37 / 3.66 | Interim | same |
| | F12su, [±45f]s D3518 | 11.5 | Interim | 6.2.4(g) (6-44 / 437) |
| | G12s | 0.758 | Interim | same |

The everyspec copies carry a "Downloaded from everyspec.com" stamp on each page; the underlying document is the DoD handbook. Volumes 3, 4 and 5 were not opened.

## 3. NASA reports, open-access papers and manufacturer datasheets

### NASA Technical Reports Server

Each citation page on ntrs.nasa.gov states "Public Use Permitted" (newer records) or "Work of the US Gov. Public Use Permitted" (older ones) with "Public" distribution. Reports were downloaded and read; values are the printed averages. Units as printed (msi = 10⁶ psi).

**IM7/8552 UD tape, 190 gsm, 35% RC. NASA/TM-20230001560 (Maurya, Tanneru, Rajan, Pereira, Miller; February 2023).** https://ntrs.nasa.gov/citations/20230001560. Room temperature, three replicates per test.

| Property | Value | Unit | Table, page |
| --- | --- | --- | --- |
| Cured ply thickness (nominal) | 0.18 | mm | Table 1, p. 1 |
| E11 tension / nu12 / F1t | 23,105,148 / 0.3235 / 391,111 | psi / — / psi | Table 6, p. 12 |
| E22 tension / nu21 / F2t | 1,299,337 / 0.0208 / 11,742 | psi / — / psi | Table 8, p. 15 |
| E33 tension | 1,089,994 | psi | Table 10, p. 18 |
| E11 compression / F1c | 19,450,971 / 116,744 | psi | Table 12, p. 21 |
| E22 compression / F2c | 1,334,952 / 34,741 | psi | Table 14, p. 25 |
| G12 (D5379) / F12 at 5% strain | 650,712 / 14,492 | psi | Table 18, p. 31 |
| G23 | 414,695 | psi | Table 20, p. 34 |
| G13 | 763,931 | psi | Table 22, p. 38 |

The longitudinal compressive strength (116.7 ksi) is far below the NCAMP back-out value (249 ksi); the report's end-loaded specimens are the likely reason. Show it as reported with its method.

**IM7/8552, Boeing coupon programme. NASA/TM-2020-220498 (Justusson et al.; March 2020).** https://ntrs.nasa.gov/citations/20200002195. Backed-out UD F1t 394.34 ± 15.44 ksi and E11 27.77 msi (text, p. 10, back-out factor 2); E22 about 1.30 msi and F2t 13.64 ± 0.37 ksi (Table 6, p. 11); G12 0.66 msi and F12 at 5% 12.25 ksi (Table 7, p. 13); E22c 1.45 msi and F2c 41.59 ksi (Table 8, p. 15); E33 1.76 msi, nu31 0.023, nu32 0.353, F3t 5.85 ksi (Table 9, p. 16). The two IM7/8552 reports differ (E11 23.1 msi measured versus 27.8 msi backed out); show both, never merge.

**T300/5208. NASA-CR-173616 (Milkovich and Herakovich; April 1984).** https://ntrs.nasa.gov/citations/19840017699. At 301 K: E1 147.7 GPa, E2 11.1 GPa (Table 1, p. 32); XT 1,450 MPa, YT 28.3 MPa (Table 2, p. 33); nu12 0.2979 (Table 3, p. 34); G12 6.94 GPa (Table 4, p. 34). Also 116 K and 394 K columns. No compression, ply thickness or expansion. The "E1 = 181 GPa" T300/5208 set seen online is Tsai's textbook set, not this report.

**AS4/APC-2. NASA-CR-183145 (Sun and Yoon; August 1988).** https://ntrs.nasa.gov/citations/19880017858. Table 1, p. 15, at 75 °F: E1 18.52 msi, F1t 309.2 ksi, nu12 0.32; E2 1.49 msi, F2t 13.8 ksi, nu21 0.022. G12 is not tabulated.

**AS4/PEEK UD tape. NASA TM-102769 (Baker; April 1991).** https://ntrs.nasa.gov/citations/19910015030. Vf 61.9% (Table 2, p. 11). E1 tension 19.55 msi (Table 3, p. 12); E1 compression 17.62 msi, nu12 0.273, F2c 24.8 ksi, E2c 1.49 msi (Table 4, p. 13); in-plane shear modulus 0.99 msi (Table 5, p. 14). Longitudinal strengths not reported (end failures).

**IM7/977-2, IM7/F655 and T800/F3900. NASA TP-3102 (Smith and Dow; September 1991).** https://ntrs.nasa.gov/citations/19920000849. Room temperature dry averages (IM7/977-2 / IM7/F655 / T800/F3900): F1t 367.9 / 365.2 / 350.2 ksi, E1t 20.6 / 21.4 / 21.9 msi, nu12 0.32 / 0.32 / 0.33 (Table 3, pp. 8 to 9); F1c 131.7 / 156.0 / 133.1 ksi, E1c 20.4 / 21.2 / 21.1 msi, all longitudinal splitting (Table 4, pp. 10 to 11); F2t 10.4 / 5.5 / 10.2 ksi, E2t 1.33 / 1.34 / 1.31 msi (Table 5, pp. 12 to 13); G12 694 / 809 / 740 ksi (Table 6, pp. 14 to 15).

**AS4/3501-6. NASA-CR-187229 (Peimandis; October 1991).** https://ntrs.nasa.gov/citations/19920011242. Dry, 22 °C, low strain rate: E11 143 GPa, F1T 2410 MPa, nu12 0.27 (Table 5.7, p. 104; the printed ksi pairs in that table are inconsistent with the MPa values, so quote SI only); E22 10.0 GPa, F2T 64.2 MPa, nu21 0.012 (Table 5.1, p. 100); G12 7.2 GPa, F12 76 MPa (Table 5.4, p. 102).

Checked and not usable as lamina sources: NASA-CR-4610 (laminate data only), NASA-CR-189085 (angle-ply only), NTRS 20200002400 (laminates, conference paper), NTRS 20110016052 (no lamina table), AIAA 81-0541 (AIAA copyright, no download). No NASA glass/epoxy lamina table was verified; DTIC ADA575236 (S-2 glass/SC-15) could not be downloaded, UNVERIFIED.

### Open-access journal papers

Licence text was read from the Europe PMC full-text record of each article.

- **CCF300/BA9916-II carbon/epoxy, measured.** Polymers 2023, 15(24), 4699, DOI 10.3390/polym15244699, CC BY 4.0. Table 1: YT 55 MPa (D3039); E2c 9.2 GPa, YC 203 MPa, E1c 118.7 GPa, XC 1020 MPa (D6641); G21 4.9 GPa, S21 82 MPa (D7078). No XT, E1t, nu12 or ply thickness.
- **T700/PEEK UD, manufacturer-supplied values.** Materials 2024, 17(13), 3317, DOI 10.3390/ma17133317, CC BY. Table 2: E11 130 GPa, E22 10.1 GPa, G12 5.77 GPa, nu12 0.32, XT 2419 MPa, XC 1094 MPa, YT 50.2 MPa.
- **T800-grade UD, transverse only.** Materials 2025, 18(4), 816, DOI 10.3390/ma18040816, CC BY. Ply 0.14 mm; E2 8.7 GPa, YT 63.0 MPa; E2c 8.4 GPa, YC 197.1 MPa.
- **TP402/T700S thin-ply, full set with expansion.** Data in Brief 47 (2023) 108966, DOI 10.1016/j.dib.2023.108966. Licence CC BY-NC-ND: excluded because the ND term forbids derivative use. Listed so it is not searched again.
- **Compiled, not measured, CC BY tables** usable only as "values compiled from their references": Sci. Rep. 10 (2020) DOI 10.1038/s41598-020-57771-8 (AS4/PEEK, IM7/8552, T300/7901); Polymers 2021, 13(20), 3491 (IM7/977-3, source not stated); Materials 2024, 17(19), 4736 (AS4/8552 from NCAMP CAM-RP-2010-002 with alpha1 0 to -0.8 and alpha2 31.2 ppm/K; E-glass/MTM57 with alpha1 8.6 and alpha2 35 ppm/K).

No CC BY paper with a full measured set for a Western-named prepreg (8552, M21, 977-3, 3900-2) was found.

### Manufacturer datasheets

Typical supplier values. Hexcel's sheets state that performance values "do not and should not constitute a substitute for your own testing"; Toray's state "lot averages, for reference purposes only, offered AS-IS without warranty".

| Sheet | Revision | Key values (room temperature dry) |
| --- | --- | --- |
| Hexcel HexPly 8552 US, https://hexcel.com/wp-content/uploads/2026/01/HexPly_8552_us_DataSheet.pdf, p. 3 | FTA-072-2-MY20, 2020 | AS4: 0° tension 310 ksi / 19.6 msi, 90° tension 9.27 ksi / 1.39 msi, nu12 0.302 (t) 0.335 (c), ±45 shear 16.6 ksi, 0° compression 222 ksi / 18.6 msi. IM7: 395 / 23.8; 9.3 / 1.70; 0.316 / 0.356; 17.4; 245 / 21.7 |
| Hexcel HexPly 8552 EU, https://hexcel.com/wp-content/uploads/2025/12/HexPly_8552_eu_DataSheet1.pdf, p. 2 | FTA-072-MC23, 2023 | Cured ply thickness 0.130 mm (AS4), 0.131 mm (IM7); fibre volume 57.42% and 57.70%; same strengths in SI |
| Hexcel HexPly M21, https://hexcel.com/wp-content/uploads/2025/12/HexPly_M21_global_DataSheet.pdf, p. 4 | FTA-002-MY20, 2020 | M21/34%/UD194/IM7: tension 2860 MPa / 160 GPa, compression 1790 MPa / 148 GPa, ILSS 110 MPa, shear modulus 4.6 GPa; ply 0.184 mm; Vf 59.2%. AS7 and IMA columns also printed |
| Hexcel HexTow IM7, https://hexcel.com/wp-content/uploads/2025/12/IM7_HexTow_DataSheet.pdf | 2023 | Fibre 5670 MPa, 276 GPa, CTE -0.64 ppm/°C; 8552 composite at 60% Vf: 0° tension 2723 MPa / 164 GPa, compression 1689 MPa / 150 GPa |
| Toray T700S, https://www.toraycma.com/wp-content/uploads/T700S-Data-Sheet.pdf | 24 Nov 2025 | Fibre 4900 MPa, 230 GPa; composite at 60% Vf: tension 2860 MPa / 134 GPa, compression 1450 MPa, in-plane shear 136 MPa, 90° tension 81 MPa |
| Toray T800S, https://www.toraycma.com/wp-content/uploads/T800S-Data-Sheet.pdf | 13 Apr 2018 | Fibre 5880 MPa, 294 GPa; composite: tension 3290 MPa / 163 GPa, compression 1490 MPa, shear 135 MPa, 90° tension 79 MPa |
| Toray 2510, P707AG-15 (T700G UD, 150 gsm, 35% RC), https://www.toraycma.com/wp-content/uploads/2510-Prepreg-System.pdf, p. 2 | 5 Jun 2025 | At 72 °F: F1t 315 ksi, E1t 18.2 msi, F2t 6.42 ksi, E2t 1.22 msi, F1c 210 ksi, E1c 16.3 msi, F2c 28.8 ksi, E2c 1.23 msi, F12 22.4 ksi, G12 0.61 msi (D5379), nu12 0.31, SBS 12.5 ksi; Vf 54.4%, CPT 0.0060 in |
| Toray 3900, P2362W-19L (T800S UD, 191 gsm, 35.5% RC), https://www.toraycma.com/wp-content/uploads/3900-Prepreg-System.pdf, p. 2 | 30 Jul 2020 | At 72 °F: F1t 436 ksi, E1t 21.5 msi, F2t 8.82 ksi, E2t 1.47 msi, F1c 258 ksi, E1c 18.9 msi, F2c 31.3 ksi, E2c 1.24 msi, F12 at 5% 10.0 ksi, G12 0.571 msi, SBS 14.0 ksi; CPT 0.0075 in. No Poisson's ratio |

Not reachable by automated fetch, UNVERIFIED: Solvay CYCOM 5320-1 and 977-3 product pages (HTTP 406) and Park Aerospace E-752 sheets (Cloudflare challenge; four candidate URLs on parkaerospace.com). Open these in a browser and transcribe by hand.

## Excluded sources

Daniel and Ishai Appendix A, CMH-17 Revisions G and H, Tsai's "Theory of Composites Design" and Jones's "Mechanics of Composite Materials" are copyrighted compilations. The library keeps citing Daniel and Ishai by table and page as a licensed reference and does not reproduce the others.

## Recommended next entries

1. Hexcel 8552/IM7 unitape (NCAMP, system 1): complete elastic set with Poisson's ratio, strengths, ply thickness and the SAR for B-basis context. Pairs with the existing 8552/AS4 record. Done on 2026-10-10, see [the release note](material-release-im7-8552-2026-10-10.md).
2. Solvay 5320-1/T650 unitape (system 4) and TenCate BT250E-6/IM7 (system 10): complete sets, cross-checked, clear rights sentence.
3. Toray TC380/T1100GC (system 15) and EP2190/IMS65 (system 13): current high-strength systems, after a visual check of the tables.
4. NASA/TM-20230001560 IM7/8552 as a second, independent IM7/8552 dataset with through-thickness moduli, kept separate from the NCAMP record.
5. MIL-HDBK-17-2F T650-35/976 (B30 class) and 7781/EA9396 as public-domain historical records, labelled canceled handbook data.
6. MTM45-1/IM7 only after NCAMP confirms the Rev C report's distribution terms.

Each entry follows the existing record pattern: source with report number, revision, date, URL, SHA-256, page and rights class; properties with table page, method, conditions and basis; a monitor adapter so revisions are detected.
