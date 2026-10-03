# ADR-0015: Cases read course Excel inputs and describe several materials per laminate

- Status: Proposed
- Date: 2026-10-03
- Decided by: pending founder review | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/course_excel.py`, `engine/src/anisotropy_engine/cases.py`, `engine/tests/test_course_inputs.py`, [evaluation](../evaluations/2026-10-03-validation-course-problems.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0009](ADR-0009-calculator-inputs-in-case-files.md)

## Context

The founder wants to enter their own problems and compare them with course and textbook answers. The course (SE142/253A) gives every laminate problem as an Excel input file: a material table, loads with a temperature change, and a ply list with ply 1 at the bottom. Homework 4 Problem 4 combines two materials and two ply thicknesses. Case files allowed one material and one thickness, answer keys could only be compared value by value or row by row, and the calculator duplicated the case solver.

## Options considered

1. Ask the founder to retype every Excel input as TOML. No new code; the course format and the case format drift apart, and retyping invites errors.
2. Read the course Excel format directly, mapped onto the existing case format. Adds the `openpyxl` dependency to the engine; the course template becomes a supported input.
3. Read Excel by unzipping its XML by hand. No dependency, but more parsing code to maintain and test.

For several materials:

1. One material per ply table entry, with properties repeated per ply. Simple, but long and error-prone.
2. Named `[materials.<name>]` tables and a `plies` list of `{angle, material, thickness}`, next to the existing one-material form.

## Decision

Option 2 in both cases. `load_case` reads `.xlsx` files through `course_excel.read_course_workbook`. The reader accepts only the course units cell ("lbf, in, psi, F", the case system `psi`), converts the template's negative compressive strengths to positive magnitudes, and rejects placeholder text ("TBD"), repeated ply numbers, missing thicknesses and conflicting thicknesses instead of guessing (ADR-0003). Template placeholder material rows are ignored unless a ply uses them.

A case has exactly one of `[material]` with `layup` and `ply_thickness`, or `[materials.<name>]` with `plies`. One function, `solve_case`, solves a case; the comparison and the calculator both use it. New results: `S`, `Qbar`, `Sbar`, the inverse ABD blocks `a`, `b`, `d`, and per-ply strain and stress at the bottom, top and mid-thickness of each ply. Per-ply answers may be given for only some plies, keyed by ply number with ply 1 at the bottom, as answer keys state them. The calculator ends with an answer-key comparison whenever the case has `[expected]` values.

## Why (evidence)

- All 13 course input files were read. Six load and solve; the rest stop with a message that names a real gap in the file: no material, no ply thickness, "TBD" or "No Load" loads, or a repeated ply number.
- 17 new validation cases from course Homeworks 2 to 5 agree with 313 of 313 answer-key values, including the hybrid laminate of Homework 4 Problem 4.
- `test_course_inputs.py` builds workbooks in the template layout and checks that the Excel and TOML forms of the hybrid laminate give identical results, along with each rejection.
- openpyxl 3.1.5 is pinned in `engine/uv.lock` and `api/uv.lock`. Its long-term maintenance outlook: no evidence yet (UNVERIFIED).

## Consequences

The engine now depends on openpyxl, and so does the API through the engine. Course files with typos produce wrong but valid-looking inputs. For example, the Homework 3 files list Boron/Epoxy G12 = 7,800,000 psi where the course table gives 780,000 psi; the reader cannot detect a plausible typo. Only the course template's layout and units cell are supported. Mixed load and deformation conditions and failure with fixed loads still cannot be expressed in Excel or TOML.

## How we will know it was wrong

Revisit if the course template changes layout, if another course or customer format needs reading, or if a problem needs a material property that varies within one named material.
