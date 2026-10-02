# Textbook material release — 1 October 2026

Six named materials and 87 properties added to the lookup, bringing it to 15 materials. Source: Daniel and Ishai, *Engineering Mechanics of Composite Materials*, second edition, Oxford University Press, 2006, ISBN 978-0-19-515097-1. These are typical reference properties for preliminary analysis, not a supplier specification or statistical allowable release.

| Material | Table | Printed page / supplied PDF page | Properties |
|---|---|---|---|
| IM6G / 3501-6 | A.4 | 377 / 397 | 14 |
| IM7 / 977-3 | A.4 | 378 / 398 | 15 |
| AS4 / APC2 | A.4 | 378 / 398 | 15 |
| M10E / 3783 | A.5 | 379 / 399 | 13 |
| AGP370-5H / 3501-6S | A.5 | 379 / 399 | 15 |
| 7781 / 5245C | A.5 | 379 / 399 | 15 |

All three original table pages were visually inspected for this release. Ambient 24°C (75°F), dry conditions follow the book's printed p. 42. The source PDF fingerprint is retained from the prior complete textbook review: `8c46dbb6cc5d485aaa5a256b9e10c93fd4ee40eb86dc9973ecdb833b4ec729d2`.

## Decisions affecting use

- The SI column is the numerical basis. Imperial equivalents are calculated from SI instead of copying potentially inconsistent rounded pairs. Density is normalized from g/cm³ to kg/m³; fiber volume and ultimate strain from fractions to percent. Exports preserve original source values and units as well as display values.
- E1, E2, G12 and ν12 form each record's in-plane elastic input set. The separately rounded ν21 column is not treated as an independent model input; the record explains reciprocity. This release does not create a 3D model.
- Blank cells remain absent. In particular, IM6G longitudinal thermal expansion and both M10E thermal coefficients are absent. No process, ply thickness, individual test-method edition or moisture basis has been invented.
- AGP's A.5 in-plane values stay separate from the existing ICF through-thickness record. The suffix 3501-6S is preserved. M10E's book record replaces its archived disposition in the public lookup, but the original school import remains intact. No school ν23 value is carried into this in-plane record.
- 7781/5245C is a distinct resin system from 7781/E765. AS4/APC2 is carbon/PEEK and has its own family filter.
- References open the official publisher's book listing, not a purported PDF page. Printed page, table, edition, authors and ISBN identify the source within the user's copy. The supplied textbook is not republished as a website asset. The publisher page presented an access challenge to the research tool; no claim of full-text access there is made.
- Reference-document monitoring does not compare the textbook PDF fingerprint with the publisher's catalog HTML. Book records remain pinned to their edition.

## Notifications

Updated the existing `material-publication-updates` heartbeat from weekly Monday checks to a six-month interval, on the first day of the scheduled month at 09:00 local time. Meaningful new publications trigger a notification and official link. The user obtains updated publications; properties are not automatically replaced. This is the notification/research schedule, separate from the existing local byte-check service.

## Validation

TypeScript and production build passed. Unit checks cover all active records, source/display normalization, omitted fields, book citations, elastic consistency and exports. Browser checks cover the new book record and PEEK filter alongside existing qualification records and update notices.
