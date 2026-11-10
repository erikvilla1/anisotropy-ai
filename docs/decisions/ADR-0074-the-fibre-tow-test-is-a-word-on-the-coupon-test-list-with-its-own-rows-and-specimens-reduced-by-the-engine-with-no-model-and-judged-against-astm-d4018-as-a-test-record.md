# ADR-0074: The fibre tow test is a word on the coupon form's Test list with its own rows and specimens, reduced by the engine with no model, and judged against ASTM D4018 as a test record

- Status: Proposed
- Date: 2026-11-09
- Decided by: Founder, 2026-11-08 (asked how to treat ASTM D4018: "Tow calculator, no FEA (Recommended)", as its own part) and 2026-11-09 (asked where it lives: "Inside the coupon Test list") | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/tow.py`, `engine/docs/theory.md` (section 11), `fea/src/anisotropy_fea/standards/astm_d4018.py`, `fea/src/anisotropy_fea/tow_test.py`, `fea/tools/studio_tool.py` (`tow`), `api/src/anisotropy_api/main.py` (`POST /v1/tow-tests`), `lib/studio-tow.ts`, `components/workspace/tow-rail.tsx`, `components/studio/tow-stage.tsx`, [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0018](ADR-0018-source-rights-classes.md) (amendment 1), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (amendment 8), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0072](ADR-0072-a-coupons-test-standard-is-a-profile-of-clause-tagged-requirements-the-specimen-is-checked-against-and-a-deviation-is-reported-never-refused.md), risks R-24 and R-25

## Context

ASTM D4018-23 is the third standard the founder supplied for ADR-0072, in a copy licensed to UC San Diego and stamped "No further reproductions authorized"; it is kept in `.local/sources/astm/` since 2026-11-09. It covers the tension test of a resin-impregnated, consolidated carbon or graphite fibre tow (§1.1): a strand pulled to failure over a 150 mm ± 5 mm gauge (§8.3). The strength and chord modulus come from the measured forces and the fibre's mass per unit length (MUL) and density (Eqs 4 and 5); the standard also gives MUL from a weighed length (Eq 1), a sized fibre's density corrected for its sizing (Eq 2), the resin content (Eq 3), the statistics of a series (Eqs 6 to 8), the largest preload (Table 1) and the chord's strains (Table 2), both by the product's typical strain at failure, and a three-letter failure code (Fig. 1).

A tow has no laminate, no layup and no geometry beyond its gauge length. ADR-0072's profiles judge a coupon's spec, and a coupon has a spec kind, a mesh and a model; a tow has none of them.

Eq 5 multiplies by B = 10⁻³ for a load in newtons to report GPa and lists the strains in microstrain. With the force P in N, the fibre density in g/cm³ and MUL in g/m, P times the density over MUL is in MPa (Eq 4 with A = 1), so B = 10⁻³ gives GPa only when the strain difference is absolute (0.005, not 5000); with microstrain the result is 10⁶ times too small.

## Options considered

Where the tow lives (asked of the founder on 2026-11-09):

1. **A word on the coupon form's Test list** (chosen by the founder): one place for every test the engineer runs; picking it swaps the rail's panels for the tow's. It forks the reading and the check of the coupon form.
2. A workspace of its own at `/workspace/tow`: a cleaner separation, but another product to keep and a second place to look for a test. Not chosen.
3. A panel of the laminate workspace: a tow is no laminate under loads per unit width. Not chosen.

Where its numbers are computed:

1. **The engine** (`anisotropy_engine.tow`): every number in a result is the engine's (ADR-0001), and these are closed forms, not finite element results.
2. The page: refused, the page computes nothing (ADR-0051).
3. The fea package: refused for the formulas, which are not finite element results; fea reads the record and judges it, as it does a coupon's.

How the API reaches the D4018 profile, which lives with the others in the fea package:

1. **`POST /v1/tow-tests`, answered by `fea/tools/studio_tool.py tow`** through the runner the setup check already uses: the API keeps depending on the engine alone; the run is recorded under its own endpoint.
2. The API imports the fea package: a new dependency (gmsh among its extras) for one route. Rejected.
3. A fork inside `POST /v1/coupon-jobs/check`: a tow's answer is a result, not a setup check, and the run record would name the wrong endpoint. Rejected.

Eq 5's strains:

1. **Absolute strains in the engine, no factor**: SI throughout (ADR-0002), and the arithmetic the units allow.
2. Microstrain with B = 10⁻³ as printed: 10⁶ times too small. Rejected.

## Decision

- **The Test row lists "fibre tow tension".** In the studio, picking it swaps the rail's panels for the tow's (Project, The fibre tow, Mass per unit length and density, The impregnated strand, The tensile test, Specimens tested, Calculate) and the centre for a sketch of the strand and the result. The Standard row offers none and ASTM D4018-23 for it. The Excel form lists the word and refuses it with a pointer to the studio, as it does a plate's lists; the coupon check refuses a tow values file with the same pointer; the assistant hands over to the tow's panels.
- **The record** is one values object: the tow's rows in the standard's units (SI only, §1.5: N, g, m and mm, g/m, g/cm³, microstrain, mm/min, MPa, GPa), five rows shared with the coupon form (test, standard, who, date, notes), and the specimens as a list (name, maximum force, the forces at the chord's two strains, Fig. 1 code, valid or rejected, note). It is no spec kind and has no mesh.
- **The engine computes** Eqs 1 to 8, Tables 1 and 2 and the planning loads (the force at the preload and chord strains from a datasheet's modulus and the fibre's area, and at failure from its strength; §11.3.6), in SI with absolute strains. A rejected specimen's values are computed and listed, never counted (§11.3.12).
- **The fea package** (`tow_test.py`) reads the record, refuses every problem by its row at once (ADR-0003), judges it against the profile `standards/astm_d4018.py` on a `TowSubject`, and writes the checklist and, when nothing blocks, the result in the standard's report units.
- **The judgement** is of the record as entered, never of a witnessed test: 14 requirements with a rule (scope, mandatory, recommended, note) and 10 laboratory clauses, each with its clause, in our words. A deviation warns and never blocks; nothing says "conforms" (ADR-0072).
- **Our readings**, recorded as readings: several bundles in one specimen (allowed for 3000 filaments or fewer, §8.3) carry the bundles' summed MUL; "a significant fraction" of failures near the grips (§11.5) has no number, so the count of coded failures at, in or within one width of a tab or grip is shown as a note, never as a deviation; the identification of the samples (§13.1.3.1) needs the fibre and its lot; Eq 5's strains are absolute.
- **The API** answers `POST /v1/tow-tests` at once, with the run recorded by its actor and the values' digest (ADR-0026), never the rows.
- **The form version stays 0.8**: 0.8 is not released (it arrives with ADR-0072's first pull request), and no coupon row changed (ADR-0046 amendment 8).

## As built (2026-11-09)

- Engine: `engine/src/anisotropy_engine/tow.py` (`mass_per_unit_length`, `fibre_density`, `resin_content`, `fibre_area`, `tow_strength`, `tow_chord_modulus`, `preload_strain`, `chord_strains`, `sample_statistics`, `planning_loads`), section 11 of `engine/docs/theory.md`, `tow` among the manual's engine modules, and a card "Fibre tow strength & chord modulus" in the website's physics library (41 cards).
- fea: `standards/astm_d4018.py` (the profile, the `TowSubject`, the Fig. 1 letters in our words, the §13.1.3 report items), `tow_test.py`, `spec.TOW_TEST` and `spec.test_name`, the Test row's word, `studio_tool.py tow`, the `tow` block of `lib/coupon-form-definition.json`. `Conformance` gained `checked` and `judged_by` so its sentence reads "test record checked against ASTM D4018-23: 7 of 7 requirements the record shows are met".
- API: `TowTestRequest`, `TowTestResponse`, `CouponJobs.tow`, `POST /v1/tow-tests`.
- Page: `lib/studio-tow.ts` (rows, values object, row errors, panel states, specimens pasted from a spreadsheet), `components/workspace/tow-rail.tsx`, `components/studio/tow-stage.tsx`, the project keeping `specimens` (in this browser and on the server, absent from a coupon's upload), and the assistant's hand-over.
- Differences from the plan: the engine's checks are constructed cases in `engine/tests/test_tow.py`, each value worked by hand in the standard's units, because `engine/validation/cases/` holds laminate problems only; the browser fixture `tests/fixtures/studio-tow/` is written by the tool and checked against it by `fea/tests/test_tow_test.py`.

## Why (evidence)

- The units of Eq 5, worked both ways on one constructed case: `engine/tests/test_tow.py::test_eq_5_as_printed_gives_gpa_only_with_absolute_strains`.
- On the constructed 12K carbon tow of the fixture (0.800 g/m, 1.80 g/cm³, five specimens, one rejected; round numbers, not test data) the engine gives a mean strength of 4857 MPa (s 131.3 MPa, CV 2.704 %) and a chord modulus of 229.9 GPa over 1000 to 6000 microstrain, and the profile finds 7 of 7 judged requirements met with one grip failure as a note (`tests/fixtures/studio-tow/tow.json`).
- Test runs on 2026-11-09, in the worktree of this branch: see the pull request for the output of every suite; the tow's own tests are `engine/tests/test_tow.py` (20), `fea/tests/test_tow_test.py` (53), `api/tests/test_tow_test_api.py` (6, the recorded run against the test database included), `tests/studio-tow.test.ts` (10) and the browser scenario "the fibre tow test swaps the panels for the tow's ..." in `tests/browser/studio.spec.ts`.
- The publisher's page: https://store.astm.org/d4018-23.html (found by search, 2026-11-09). Legal review of the "individual values" position: no evidence yet (R-25).

## Consequences

- **Easier:** a laboratory enters its tow record where it enters a coupon and gets the standard's numbers, each specimen's and the series', with every clause the record shows judged; the planning loads size a test before it is run.
- **Harder:** the coupon form has two readers and the rail two sets of panels; a new shared row must be added to both; the project carries a list a coupon never uses.
- **We now depend on** our reading of Eq 5, the licensed copy read clause by clause, and the "individual values" position (R-25).

## How we will know it was wrong

- A laboratory's own D4018 reduction of the same record differs from ours by more than rounding.
- ASTM corrects Eq 5 (for example B = 10³ with microstrain): the reading changes, the numbers do not.
- An engineer reads a tow's "7 of 7 met" as a witnessed or conforming test (R-24), or cannot find the tow because it hides behind the coupon's Test row.
