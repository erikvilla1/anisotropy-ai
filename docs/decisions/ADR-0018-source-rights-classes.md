# ADR-0018: Every cited source carries a rights class that decides what the website shows

- Status: Proposed
- Date: 2026-10-10
- Decided by: pending founder review | Drafted by: Claude Code
- Related: `lib/source-rights.ts`, `tests/source-rights.test.ts`, [evaluation](../evaluations/website/2026-10-10-source-rights.md), [ADR-0007](ADR-0007-validation-cases-store-numbers-only.md), [ADR-0010](ADR-0010-public-citations-local-page-evidence.md), risks R-05, R-06 and R-14

## Context

The founders asked whether the website could offer the CMH-17 handbook and the course textbooks, and found that it could not. ADR-0010 settled one case, the Daniel and Ishai page scans, but nothing recorded, source by source, what the website may do with each document. On 2026-10-10 a check of the public assets found the course handout "SE143AB Appendix F: Material Properties" (6 pages, February 2026) being served from the website and linked from the exported analysis packets. AGENTS.md forbids committing course material. Two locally held handbooks are also in play: MIL-HDBK-17-2F (2002), a US Department of Defense work with Distribution Statement A, and CMH-17 Volume 2 Revision G (2012), which is copyrighted and sold by SAE International.

## Options considered

1. Decide each source by hand when it is added, as ADR-0010 did. Simple, but the Appendix F case shows that a rule nobody has to remember gets missed.
2. Publish only values and citations for every source, no matter its rights. Safe for copyrighted works, but it needlessly hides public-domain material such as MIL-HDBK-17F, which may be quoted and even hosted.
3. A rights class on every source record, with one policy table that says what the website may show for each class. The website components read the policy; tests check that every public dataset has a class with evidence and that nothing copied is served.

## Decision

Option 3. Four classes in `lib/source-rights.ts`:

| Class | Examples | Website shows |
| --- | --- | --- |
| Public domain | MIL-HDBK-17F, NASA reports | Values, quotes, tables; a hosted copy is allowed |
| Open publisher data | NCAMP and AGATE reports, NASA Technical Reports Server, manufacturer datasheets | Values with citation and a link to the publisher's copy; no copy hosted |
| Licensed reference | Daniel and Ishai, CMH-17, the course appendix, a conference paper without a license statement | Individual recorded values with table and page; readers consult their own copy; no scans, text, tables or PDFs |
| User supplied | A customer's own allowables or handbook extracts | Nothing public; private workspace only |

Every source record has `rights` and `rightsEvidence`. The library shows the class next to each dataset and lists the classes on the references panel. Licensed references currently show the individual values the library recorded, as ADR-0010 accepted; the policy's `showValues` flag turns that off for a class in one line, and the component then shows the citation only.

The course appendix moves to ignored `.local/course/`. It is no longer served, linked or exported, and its transcription check runs only where that local copy exists. The two unused components that rendered it are removed. No PDF may exist under `public/`.

## Why (evidence)

- CMH-17 is copyrighted (notice in the Volume 1 to 6 table of contents published by NIAR, and sold at SAE: https://saemobilus.sae.org/content/R-423). MIL-HDBK-17-1F carries Distribution Statement A and is hosted by DTIC: https://apps.dtic.mil/sti/pdfs/ADA426516.pdf. NCAMP states its documents are intended for general distribution to the public: https://www.wichita.edu/industry_and_defense/NIAR/Research/ncamp.php.
- `tests/source-rights.test.ts`: every public dataset and supporting reference has a class with evidence; no class other than public domain allows a hosted copy; the course appendix is absent from public assets and not linked from exports; no PDF, scan or extracted text exists under `public/`; `.gitignore` carries the rules.
- The browser suite's asset check now expects a 404 for the former appendix URL.
- Legal review of the classes and of the "individual values" position for licensed references: no evidence yet. The founders should confirm with counsel before launch.

## Consequences

Adding a source means stating its rights class and evidence, or the tests fail. Public-domain data such as MIL-HDBK-17F can be added with full tables. CMH-17 can be cited by section but never reproduced; showing its numbers publicly needs a licence from SAE. The appendix's cell-by-cell transcription check is skipped in CI, where the local copy does not exist. The appendix remains in git history; removing it from history needs a rewrite the founder must decide on.

## How we will know it was wrong

Revisit if counsel advises that recorded values from a licensed reference must not be shown (flip `showValues` for that class), if a publisher objects, or if a customer's licensed data must be computed on without ever being stored by us.
