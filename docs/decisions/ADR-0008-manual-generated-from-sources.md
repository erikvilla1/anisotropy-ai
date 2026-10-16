# ADR-0008: The LaTeX manual is generated from the repository's sources

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Claude Code
- Related: `docs/manual/`, `docs/manual/README.md`

## Context

The team wants typeset LaTeX documentation that is as easy to read as the equations page, and that follows the documentation structure in `docs/`. A second, hand-maintained copy of the same content would drift from the Markdown documents and from the code.

## Options considered

1. **Write the manual by hand in LaTeX.** Full control over layout. Every change must be made twice, and numbers and code listings go stale.
2. **Convert the Markdown with pandoc.** Little code to maintain. Adds a dependency, and still leaves code listings and engine results to be copied by hand.
3. **A build script that assembles the manual from the sources:** prose and equations from the Markdown documents, code listings from the engine source, and every number from running the engine during the build. Compiled with Tectonic.

## Decision

Option 3. `docs/manual/build.py` writes LaTeX fragments; `docs/manual/main.tex` holds only layout and framing text. Tectonic compiles the PDF, as the v1 technical specification proposed for reports.

Amended 2026-10-15 (ADR-0029): the same build also reads the finite element layer, `fea/docs/theory.md` with its code markers, `fea/validation/cases` solved by the kernel during the build, and the newest report in `docs/evaluations/fea`, and runs from the `fea` environment, which holds both packages. One rule, two packages.

## Why (evidence)

- The first build reproduced all 5 validation cases and the worked coupon example by running the engine, with code listings carrying their real source line numbers.
- The build refuses to run when engine tests fail, when a validation case disagrees with its source, or when `theory.md` names a function without a code marker.
- The CI workflow builds the PDF on every pull request.

## Consequences

- Source documents must use the Markdown subset the converter supports (listed in `docs/manual/README.md`).
- Tectonic is needed to build locally; CI downloads it.
- The same approach can produce customer reports later: templates plus values from a run record.

## How we will know it was wrong

If the converter keeps needing new Markdown features, or layout fixes take more time than writing the content, switch the conversion step to pandoc.
