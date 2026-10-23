# ADR-0033: Every solved problem gets its own generated document; the manual keeps one summary table

- Status: Proposed; a homework set also has one document of its own, a chapter per problem, by [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md); a homework set's reading is local, `.local/homework/<set>/comparison/key-comparison.md`, not under `docs/problems/readings/`, by ADR-0040 amendment 1
- Date: 2026-10-19
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: ADR-0007 (validation cases are inputs, expected numbers and a source), ADR-0008 (the manual is generated from sources), ADR-0031 (one generated document per model comparison), `docs/problems/build.py`, `docs/problems/README.md`, `fea/tests/test_problem_documents.py`

## Context

The engine has been checked against 32 solved problems: 18 course homework problems, textbook problems from Daniel and Ishai, course reader problems and constructed checks, each a validation case file holding the inputs and the source's numbers. When an engineer asks what the engine has solved and how, the evidence so far was the case files, one summary line in the manual and, for every case, a table of source against engine values printed in the manual. None of that shows the steps: which equations were applied in which order, the intermediate matrices, where each number came from. The founder asked on 2026-10-19 for trustworthy per-problem documentation that shows the logic and the physics, kept separate from the general manual, which should describe the physics and the engine without every solved problem in it. The finite element side already has this form: one generated document per model comparison (ADR-0031).

## Options considered

1. One generated LaTeX document per case, built from the case file by running the engine, with the theory text and code listings taken from the same sources as the manual; the manual's validation chapter becomes one summary table. Pro: every number is recomputed at every build, the equations cannot drift from the code, 32 documents cost the same as one, and the case files need no change. Con: a reading note still has to be written by a person for each set.
2. Hand-written write-ups per homework, kept beside the case files. Rejected: the numbers would be typed once and drift from the engine, and a write-up of a course problem would quote the problem statement, which the repository never commits (AGENTS.md).
3. Put every problem's full solution in the manual. Rejected: the founder wants the manual general, and 32 problems of 20 to 40 pages each would bury it.

## Decision

Option 1. `docs/problems/build.py` builds one document per case under `engine/validation/cases/` (and for a local case, beside it): the problem as the case states it, every step the engine takes with the matching section of `engine/docs/theory.md` and the listing of the function it names, the numbers of each step, every compared number, the case runner's code, the reading, and the case file. `--all` also writes `index.md`, the one-page answer to "what has been solved". Reading notes live under `docs/problems/readings/`; a note whose file name is a prefix of a case's name covers that case, so one note serves a homework set. The manual's validation chapter is reduced to a table of cases with their counts and points at the documents. Documents are built, never committed; CI uploads them as the `problem-documents` artifact beside the manual and the model documents. Course problem statements and solution PDFs stay in `.local/homework/assignments`.

## Why (evidence)

No measured evidence yet. At the time of writing the generator builds all 32 cases (426 compared values, all reproduced; `index.md`) and the two documents compiled to PDF read correctly; the test builds two documents at every change. Whether an engineer finds the documents sufficient is for the first review to say.

## Consequences

Easier: answering "what have you solved and how" with a folder of documents and an index; adding a problem is adding a case file. Harder: a reading note is the only hand-written part and must be kept honest (it quotes numbers from the case, never from memory); a change to the theory text or a function signature changes every document, which is the point. We depend on the manual's converters and on Tectonic, as the model documents do.

## How we will know it was wrong

A reviewer needs the problem statement PDF beside the document to follow it, or the reading notes start to carry numbers the documents' tables do not show.
