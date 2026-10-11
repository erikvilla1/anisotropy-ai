# Evaluation report 2026-10-11: material loader, four failure criteria, plate buckling

- Release tested: engine 0.1.0 at commit `1402c46` (main after PRs #29, #30, #32, #34)
- Scope: the engine changes merged on 10 and 11 October: library materials as engine inputs (ADR-0020), maximum strain and Tsai-Hill criteria (ADR-0021), plate buckling (ADR-0022). The API case endpoint has its own report in `evaluations/api/2026-10-11-case-endpoint.md`.
- Test set: 32 validation cases (textbook problems, course answer keys, constructed analytical checks; sources in each file) and 408 engine unit tests.
- Method: engine output against the case's expected values within its stated tolerance; unit tests against closed forms, independent bisection and published numeric results.

## Recorded checks

| Command | Observed output |
| --- | --- |
| `cd engine; uv run pytest -q` | `408 passed in 25.75s` |
| `cd api; uv run pytest -q` | `92 passed in 1.03s` |
| `npm test` | `tests 71, pass 71, fail 0` |
| `npm run typecheck` | exit 0, no output |
| `git diff --check` | no whitespace errors |
| CI on main at `1402c46` (run for PR #34) | api, calculator-browser, engine, manual, website: pass |

## Results

| Metric | Result | Threshold | Pass? |
| --- | --- | --- | --- |
| Validation cases within tolerance | 32/32 | 100% | Yes |
| New validation cases this release | 4 (library axial check; max-strain biaxial lamina; Tsai-Hill 45° shear; cross-ply plate buckling) | | |
| Whitney (1987) worked buckling results reproduced (Eqs. 5.76, 5.81, 5.84, 5.87) | 4/4 to machine precision | 4/4 | Yes |
| Ritz series vs closed form, specially orthotropic | agree to 1e-10 on 4 geometries and load ratios | 1e-8 | Yes |
| Tsai-Hill fixed-plus-variable root vs independent bisection | 4/4 paths to 1e-9, including two with a sign change | 1e-6 | Yes |
| Library conversions vs exact inch and pound-force | 23.51 Msi → 162.0957 GPa, 0.0072 in → 0.18288 mm, exact to 1e-12 | 1e-9 | Yes |
| Course answer key, Homework 5 Problem 1 (maximum stress) | 25/25 values within 0.2% | 25/25 | Yes |

## Founder sessions with the calculator (11 October)

Three problems were put through the calculator from a blank template by the founder, with the engineer assisting. They are evidence of usability as much as of correctness:

1. A [45/−45/90/02]s laminate under loads and cooling, first-ply failure: the course key's 25 values agreed, including Nx at failure 568.25 lb/in, ply 3, bottom face, matrix tension. Two input mistakes surfaced and were fixed in the file (unit suffixes on numbers; the "s" layup shorthand); the key's A matrix had to be entered in millions of lb/in.
2. A [0/±45/90]s quasi-isotropic laminate: A11 = A22 and A66 = (A11 − A12)/2 as theory requires; B was pure roundoff and now prints as zeros.
3. The same laminate against another tool's strains: the engine reproduced that tool's numbers exactly once the loads were read as N/mm rather than N/m. No engine fault; a units reading, now in the cheat sheet.

## Failures and what we did

- The B matrix of a symmetric laminate printed entries of order 1e-16 kN because the noise threshold was relative to B itself. The calculator now judges B against max|A|·h. Display only.
- Two of the founder's expectations turned out to be about criteria the engine lacked (maximum strain) or inputs it lacked (buckling). Both were built in this release.
- The committed library export acquired Windows line endings on checkout and failed its drift test; the test now compares content and the file is pinned to LF (`.gitattributes`). A first fix wrote literal line-break characters into the regular expression and broke the website suite on main for one commit; corrected in PR #31.

## Not checked, stated plainly

- No course or textbook answer key for plate buckling has been checked. The anisotropic (Ritz) branch rests on the closed-form agreement, the upper-bound and convergence properties and Whitney's description of the method. UNVERIFIED against an external number.
- Maximum strain has no external answer key yet; its validation case is analytical.
- Hashin criteria, clamped or free plate edges, unsymmetric plate buckling, moisture and progressive failure remain unmodeled.

## Decision

Approved for the founder's course and textbook checks and for internal use. Not approved for design decisions (see the risk register, R-03).
