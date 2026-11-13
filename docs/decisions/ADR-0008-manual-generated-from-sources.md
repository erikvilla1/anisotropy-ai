# ADR-0008: The LaTeX manual is generated from the repository's sources

- Status: Accepted; the manual prints only the engine's and the finite element layer's decision records, chosen by an Area line on every record, since amendment 1
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Claude Code. Amendment 1: Founder, 2026-11-12 ("accept", which decision records the engine manual prints)
- Related: `docs/manual/`, `docs/manual/README.md`
- Area: docs

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

## Amendment 1, 2026-11-13 (the manual prints the engine's and the finite element layer's decision records, chosen by an Area line; confirmed by the founder)

**Context.** `decisions()` printed every record in `docs/decisions`. The package audit of 2026-11-12 found the engine manual, which goes to outside engineers, carrying the website's styling records (a licensed clip, pages built "after" named companies, a university mark whose permission is unverified) and a team member's own tooling. These records add pages and say nothing about the engine.

**Options.**
1. Print every record, as before: rejected for the reasons above.
2. A list of the records to print, kept in `docs/manual/build.py`: rejected. A new record is left out, or put in, by whoever remembers the list.
3. Mark the internal records, and print every record without the mark: rejected. A new record that is not marked prints by default.
4. **An `- Area:` line on every record (engine, fea, website, api, assistant, data, docs, process, hosting; one or more), and the manual prints the records whose Area names engine or fea (chosen).** A record says where it belongs when it is written, and a record without the line fails a test instead of printing.

**Decision.** Option 4, the audit's recommendation ("Engine and fea ADRs only, by an Area tag"), which the founder accepted on 2026-11-12 ("accept"). `docs/decisions/_template.md` and the decision-records skill carry the line; `decisions()` skips a record whose Area names neither; the website's, the API's and the project's own records stay in `docs/decisions`.

**Evidence.** `fea/tests/test_coupon_document.py::test_the_manual_prints_the_engines_and_the_finite_element_layers_records_only` checks that every record has an Area line with known areas only, and that the printed chapter holds ADR-0001 and ADR-0065 and leaves out ADR-0069 and ADR-0082.
