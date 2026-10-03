# Course problem validation and inputs | 2026-10-03

Base: `380a0ef`; branch: `feat/course-inputs-and-comparison`. The engine was run on every SE142/253A course problem that has an answer key. Inputs can now come from the course Excel files and describe several materials, and the calculator compares results with an answer key (ADR-0015).

## Recorded checks

| Command | Observed output |
| --- | --- |
| `cd engine; uv run pytest` (before the change) | 270 passed |
| Answer-key comparison of the 18 course cases (17 new, 1 updated) | 313 of 313 values agree |
| `cd engine; uv run pytest -q tests/test_course_inputs.py` | 38 passed |
| `cd engine; uv run pytest` | 325 passed in 28.37s |
| `cd api; uv run pytest -q tests ../engine/tests` | 402 passed in 30.37s |
| `uv run --project engine python docs/manual/build.py` | Manual written; TeX reported only underfull-line warnings |
| `git diff --check` | No whitespace errors |

## What the course problems cover

| Homework | Content | Result |
| --- | --- | --- |
| 1 | 3D stress transformation and orthotropic stiffness C | Outside the plane-stress engine; not checked |
| 2 | Lamina transformations, S, Q-bar, S-bar, strains | All recorded values agree |
| 3 | A, B, D and their inverse, coupled bending, local strain and stress on every ply face, flattening moments | All recorded values agree, including 48 ply-face values |
| 4 | Curing stresses, laminate expansion coefficients, a hybrid woven/tape laminate | All recorded values agree |
| 5, Problem 1 | Thermal, bending and biaxial loading | All recorded values agree |
| 5, Problem 2 | Micromechanics | Not modeled, and the fiber and matrix inputs are not in the course files |

Values the engine cannot produce yet are noted in the case files rather than recorded. They need mixed load and deformation conditions (Homework 2 Problems 1 and 2, Homework 4 Problem 2) or first-ply failure with some loads held fixed (Homework 5 Problem 1 part D). A separate local calculation matched those answers too (for example Nx_fail = 568.26 against the key's 568.25), but that calculation is not engine code.

## Course input files

All 13 course input files were read. Six load and solve. The rest stop with a message naming a gap in the file: no material (Homework 2 Problem 3), no ply thickness (Homework 2 Problem 4), "No Load" or "TBD" loads (Homework 3 Problems 3a and 4), or a repeated ply number 9 (Homework 4 Problem 4). The Homework 3 files list Boron/Epoxy G12 = 7,800,000 psi. The course table and the key's A66 both require 780,000 psi; the reader cannot detect this kind of typo.

## Meaning and limits

These checks verify the engine against one course's answer keys and constructed tests. They are not experimental validation. Answer keys round to three to five significant figures, so case tolerances are 0.1 to 0.5%.
