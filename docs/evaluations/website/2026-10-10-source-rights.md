# Website source rights review | 2026-10-10

Base: `5f3e735` (main after pull request #15). Branch `feat/source-rights`. See [ADR-0018](../../decisions/ADR-0018-source-rights-classes.md).

## What was found

- `public/assets/documents/material-properties-2026-v2.pdf`, the course handout "SE143AB Appendix F: Material Properties" (6 pages, version 2, 1 February 2026), was tracked in git, served from the website and linked from exported analysis packets through `schoolCitation`. The two components that rendered it were not used by any page.
- No source record said what the website may do with its document. ADR-0010 covered the Daniel and Ishai scans only.
- `.local/cmh17/` holds page dumps of MIL-HDBK-17-2F and CMH-17-3G. They are git-ignored and were not served.

## What changed

- The appendix moved to ignored `.local/course/`. It is no longer tracked, served, linked or exported. The cell-by-cell transcription check reads the local copy and is skipped where it is absent. The unused appendix components were removed. `.gitignore` now rejects any PDF under `public/`.
- `lib/source-rights.ts` defines four rights classes and one policy table. Every dataset source and supporting reference carries `rights` and `rightsEvidence`. The library shows the class beside each dataset, the source viewer shows it for the textbook, and the references panel explains the classes and links MIL-HDBK-17-2F (public domain), CMH-17 Volume 2 (licensed, at SAE) and Daniel and Ishai (licensed, at the publisher).
- Classification: NCAMP and AGATE reports, the NASA report and manufacturer datasheets are open publisher data. Daniel and Ishai, the course appendix and the ICF11 conference paper (no license statement found) are licensed references. No public-domain or user-supplied dataset exists yet.

## Checks

- `npm test`: 61 passed, 0 failed, 0 skipped (the transcription check ran because the local appendix copy exists on this machine; in CI it is skipped).
- `npm run typecheck`: exit 0 after updating `scripts/build-reference-archive.ts` to the local path.
- `npm run build`: static export completed, 11 routes. `find out -iname "*.pdf"` returned nothing.
- Preview server on port 3001: `/library` returned HTTP 200; `/assets/documents/material-properties-2026-v2.pdf` returned HTTP 404.
- `npx playwright test` for the material-analysis, textbook-materials, portfolio, provenance and physics-foundations specs: 17 passed (13.7 s). The portfolio asset check now expects the 404.
- Rendered badge text on `/library`, first dataset: "Licensed reference · Individual values cited by table and page; consult your own copy. No pages or tables are reproduced here."

## Not checked

- Legal review of the four classes and of showing individual values from licensed references: UNVERIFIED, no evidence yet.
- Git history still contains the appendix (commit `18d6615`). Removing it requires a history rewrite, which the founder must decide on.
- The engine manual build was not rerun; this change touches no engine source.
