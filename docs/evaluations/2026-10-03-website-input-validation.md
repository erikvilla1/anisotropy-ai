# Website input and citation review | 2026-10-03

Base: `e8bacf7`. This work retains the static preview; it adds no solver connection or material loader.

## Chunk 3: preserve user input

- Before: the two new parser regression tests failed. `Apply -20 kN` produced +20; a Unicode-minus dimension was missed.
- Decision: preserve signed numbers, zero, decimals and exponent-form values, then use the existing scope validator. Negative loads remain unsupported by this tension preview and are shown as errors. An explicit hole dimension is not overwritten by the D3039 no-hole inference.
- After the parser fix: `node --import tsx --test tests/demo.test.ts` produced 11 passed, 0 failed.
- Full website, type and browser checks: UNVERIFIED until the source-viewer cleanup is complete.
- This enforces ADR-0003; no new analysis or input-unit convention was introduced.
