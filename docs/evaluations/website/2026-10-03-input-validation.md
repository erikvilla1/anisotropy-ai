# Website input and citation review | 2026-10-03

Base: `e8bacf7`. This work retains the static preview; it adds no solver connection or material loader.

## Chunk 3: preserve user input

- Before: the two new parser regression tests failed. `Apply -20 kN` produced +20; a Unicode-minus dimension was missed.
- Decision: preserve signed numbers, zero, decimals and exponent-form values, then use the existing scope validator. Negative loads remain unsupported by this tension preview and are shown as errors. An explicit hole dimension is not overwritten by the D3039 no-hole inference.
- After the parser fix: `node --import tsx --test tests/demo.test.ts` produced 11 passed, 0 failed.
- Final checks after the source-viewer cleanup: `npm test` 51 passed, 0 failed; `npm run typecheck` exited 0; `npm run build` completed successfully; `npm run test:e2e` against the production export produced `25 passed (30.9s)`.
- This enforces ADR-0003; no new analysis or input-unit convention was introduced.

## Chunk 4: public citations, local evidence

- The unfinished source viewer now shows recorded values, conversions, exact table/page citations and publisher links. It does not publish original page images.
- Four page scans were moved from public assets to ignored `.local/textbook-evidence/daniel-ishai-2006/`. All four SHA-256 fingerprints still match the original manifest.
- The rendering script writes only to that local directory. Rendering was not rerun; fresh image generation is UNVERIFIED in this change.
- Unit tests reject a public scan directory. The browser suite checks exact source locations, values, invalid citation links, mobile overflow and a 404 response from the former scan URL. The production export contains no textbook scan directory.
- Original source values and dataset identities are retained; no new source qualification is claimed. See [ADR-0010](../../decisions/ADR-0010-public-citations-local-page-evidence.md).
- Website-only evaluations live in this subdirectory so the engine manual's latest-report selection continues to use an engine evaluation.
