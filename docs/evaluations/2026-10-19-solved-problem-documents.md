# Evaluation: one generated document per solved problem (ADR-0033) | 2026-10-19

- Scope: `docs/problems/build.py` (the generator), `docs/problems/readings/` (reading notes for the course's homework sets, since moved to `.local/`, ADR-0040 amendment 1), `docs/problems/README.md`, the manual's validation chapter reduced to one summary table (`docs/manual/build.py::validation`), the CI step and artifact `problem-documents`, `fea/tests/test_problem_documents.py`. No engine code and no case file changed.
- Environment: Windows 11, uv 0.13, Python 3.12, the `fea` project environment (the generator loads the manual's converters, which import both packages); Tectonic for the PDFs.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job)

```text
650 passed in 61.04s (0:01:01)
```

(242 fea tests, 3 of them new in `test_problem_documents.py`; 408 engine tests; no skips.)

From the root: `uv run --project fea python docs/problems/build.py --all --no-pdf`

```text
32 documents written (one per case under engine/validation/cases, templates skipped)
Index written to docs/problems/build/index.md: 32 problems, 426 of 426 source values reproduced by the engine
```

From the root, with Tectonic: the documents of three course problems (a thermal bending failure, a mixed-condition lamina and a two-material laminate; the cases are local since ADR-0042) compiled to PDF; the title page, the problem tables, the step pages with theory and listings, the ply tables, the failure step and the comparison table were read as rendered pages.

The manual's validation chapter, rendered through `docs/manual/build.py::validation()` alone: "426 of 426 values from 32 cases agree", one table row per case.

## Reading

- The documents answer "what has the engine solved and how" without the problem statements: every number on a page is either copied from the case file (the source's answer, with its reference) or computed during the build, and the equations and code are the manual's own. A reader can rebuild any document with one command.
- The first builds showed two typesetting defects, both fixed before this note: a unit with a product (`lb*in/in`) printed raw LaTeX inside the vectors, and floating-point residue (a 1e-15 shear coupling of a balanced laminate) appeared in the tables. Residue below 1e-10 of the largest entry of the same matrix or table is now printed as 0; the comparison table still shows every value as computed.

## Not run, and UNVERIFIED

- Not run: all 32 PDFs on this machine (three were compiled; CI compiles all of them in the `manual` job); the website and API suites (unchanged).
- UNVERIFIED: whether an engineer outside the project finds a document sufficient without the problem statement beside it; that is the review ADR-0033 asks for.
