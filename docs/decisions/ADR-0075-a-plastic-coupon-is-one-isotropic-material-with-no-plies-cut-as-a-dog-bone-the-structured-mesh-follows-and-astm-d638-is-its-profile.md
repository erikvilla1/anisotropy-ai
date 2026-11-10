# ADR-0075: A plastic coupon is one isotropic material with no plies, cut as a dog-bone the structured mesh follows, and ASTM D638 is its profile

- Status: Proposed
- Date: 2026-11-10
- Decided by: Founder, 2026-11-10 ("how about if you learn about D638", choosing ASTM D638 next over the composite standards D6641, D3518, D7264 and D5766; the founder supplied the D638-14 copy the same day, and the active D638-22 copy soon after) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/dogbone.py`, `fea/src/anisotropy_fea/mesher.py` (`structured_dogbone`), `fea/src/anisotropy_fea/spec.py`, `fea/src/anisotropy_fea/write_abaqus.py`, `fea/src/anisotropy_fea/write_calculix.py`, `fea/src/anisotropy_fea/standards/astm_d638.py`, `fea/checks/d638-type-i-plastic/`, `fea/tests/test_dogbone.py`, [ADR-0018](ADR-0018-source-rights-classes.md) (amendment 1), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0065](ADR-0065-coupon-ply-angles-are-counted-from-the-coupons-length-axis.md), [ADR-0072](ADR-0072-a-coupons-test-standard-is-a-profile-of-clause-tagged-requirements-the-specimen-is-checked-against-and-a-deviation-is-reported-never-refused.md)

## Context

- ASTM D638 measures the tensile properties of plastics, unreinforced and reinforced, on a dumbbell specimen (§1.1). Fig. 1 names five flat types by thickness: I and II up to 7 mm, III over 7 to 14 mm, IV and V up to 4 mm. Each has a narrow section (width W, length L) joined to the overall width WO by a fillet of radius R; Type IV adds an outer radius RO. A resin-matrix composite with oriented fibres stiffer than 20 GPa is sent to D3039/D3039M (Note 4).
- The founder supplied two copies on 2026-11-10, both kept in `.local/sources/astm/`: D638-14, read first, and D638-22, the active edition. The profile is written to D638-22. Every clause and value it holds is the same in D638-14. D638-22's summary of changes names Sections 3, 13 and A3.12 only, and none of those is a requirement here. The SI values are the standard; the inch-pound values are for information only (§1.5).
- Until now every coupon was a straight strip of plies. The spec required a `[layup]` and a `[material.transverse]`, and the decks wrote a composite shell section. An isotropic plate was stated as one ply with E1 = E2 and transverse isotropy (`fea/checks/open-hole-isotropic-kirsch/`).
- Under ADR-0072 a test standard is a profile of clause-tagged requirements. The tests require every row a profile names to be a form row (`fea/tests/test_standards.py`).

## Options considered

1. **A plastic as one ply of equal constants**, as the Kirsch check does. Rejected: a plastic is not a laminate. The team would read a composite section with a layup in the deck, and the form would ask for ply angles that mean nothing.
2. **A plastic as an isotropic material with no plies.** The spec states `material.E`, `material.nu` and `geometry.thickness`, and has no `[layup]` or `[material.transverse]`. Inside, it is one layer of itself at 0°, so the kernel, the fields and the reports keep their shape. The decks write `*Elastic` (E, nu) and a homogeneous shell section. Chosen.
3. **The dog-bone meshed by Gmsh**, as the open hole is. Rejected for now: the coupon's node rows (the grip lines, the extensometer's ends, the seeded segments) are the structured mesher's, and its quadrilaterals in rows suit a coupon pulled along its length.
4. **The dog-bone as the structured grid with each node row squeezed to the outline's width.** The columns follow the outline. Every element edge across a fillet is a chord between two rows, and rows on the outline's own lines keep its corners. Chosen.
5. **Register D638 in the Standard list now, without the form's rows.** Rejected: the studio would offer a dog-bone standard whose sizes no row can hold.

## Decision

Options 2 and 4, delivered in two parts.

- **The outline** (`dogbone.py`) is symmetric about both axes. A straight narrow section is joined by a fillet tangent to it. Without an outer radius, the fillet meets the full width at a corner (Types I, II, III and V). With one, it meets an arc tangent to the full width where the two arcs share their tangent (Type IV). Sizes that make no dog-bone are refused.
- **The spec** gains `[geometry.dogbone] narrow_width, narrow_length, radius, outer_radius` (unnotched tension only, structured mesher), `geometry.thickness`, and `material.E`, `material.nu`. An isotropic material refuses a layup, ply constants, a library record, a transverse table and first-ply-failure criteria. Its failure, by yield for a plastic, is a later part. `[layup]` and `[material.transverse]` become optional for it alone.
- **The quantities** read the load over the narrow section: the area is W times the thickness.
- **The D638 profile** (`standards/astm_d638.py`) holds Fig. 1's five types with their tolerance bands, and 17 judged requirements and 16 laboratory clauses, each with its clause, in our words (ADR-0018 amendment 1). It holds every value in SI, so a coupon stated in inches is held to the millimetre values converted exactly. D3039's profile now calls a dog-bone a deviation of its constant cross-section, and an isotropic material outside its scope.
- **Our readings**, written in the profile's docstring:
  - WO is held from its minimum to the minimum plus its plus tolerance.
  - A size inside a band meets it.
  - A material given as plies is a reinforced composite (§6.1.3), so it is judged as Type I.
- **Part 2:**
  - D638 joins the registry and the Standard list for unnotched tension.
  - The form gains its rows (thickness, E and nu, the dog-bone's four sizes; form 0.9).
  - `lib/source-rights.ts` lists D638.
  - The studio draws the dog-bone and offers Fig. 1's types as sizes.
  - The public check gains `[test_method]`.
  - That part follows the open studio layout change (#167), which touches the same Test list and panels.

## As built (2026-11-10, part 1)

- `fea/src/anisotropy_fea/dogbone.py`: `dogbone_outline`, `Outline` (`half_width`, `width_at`, `lines`).
- `fea/src/anisotropy_fea/mesher.py`: `structured_dogbone`. Edge-Left and Edge-Right are each row's first and last nodes.
- `fea/src/anisotropy_fea/spec.py`: `Dogbone`, `geometry.thickness`, `material.E` and `nu`, `is_isotropic`, `outline_of`, `section_width`. For an isotropic material, `full_angles` gives [0] and `spec_ply_thickness` the thickness. The card says "Layup: none: one isotropic material".
- `femodel.py`: the dog-bone mesh and the deck heading lines. `SectionDefinition.homogeneous` and `MaterialDefinition.isotropic` make `write_abaqus` write `*Elastic` and `*Shell Section, material=` with three section points, and `write_calculix` write `*ELASTIC, TYPE=ISO` and `*SHELL SECTION, MATERIAL=` with the 0° orientation.
- `standards/astm_d638.py`: not yet in `PROFILES`. `Profile.variant_noun` names "Type I" where C1869 says "Specimen A".
- `fea/checks/d638-type-i-plastic/`: Type I at its least size, 3.2 mm thick, a nominal plastic (E = 3000 MPa, nu = 0.35, not a cited dataset). It has a 50 mm extensometer and a CalculiX 2.21 record.

## Why (evidence)

- **The closed form.** In the narrow section the stress is F / (W t), so an extensometer there reads E. On the public check the kernel's modulus is 3000.5 MPa against 3000 MPa (0.02 %), and Poisson's ratio 0.35006 against 0.35. CalculiX's displacements and reaction give 3000.5 MPa too (`fea/tests/test_dogbone.py`).
- **CalculiX.** The record agrees on 19 of 19 values within its 3 % tolerance, the reaction to 0.05 % (595.275 N against 594.972 N). It was run in a cloud container with CalculiX 2.21 (`fea/checks/d638-type-i-plastic/records/`).
- **The mesh.** Its area meets the outline's within 1e-4, and every row's outer nodes lie on the outline. The Type IV arcs meet with one tangent, and each type's fillet meets the full width where the circle says (sqrt(447) mm past the narrow section for Type I).
- **The profile.** The Type I check meets 15 of 15 judged requirements that apply. A fibre laminate is outside its scope and is held to Type I. Each band and range misses where Fig. 1 says.
- **Test runs.** `cd fea && uv run pytest -q -ra tests ../engine/tests` on 2026-11-10 gave 1208 passed and 9 skipped before this change. After it, see the pull request.
- **The publisher's page** for the copy read: https://store.astm.org/d0638-22.html.
- **Not yet checked:**
  - D638-22 against D638-14: every clause the profile cites and Fig. 1's and Table 1's values compared on 2026-11-10, and found the same;
  - any test data for a plastic coupon: none;
  - the legal review of individual values (R-25): no evidence yet.

## Consequences

- **Easier:**
  - A plastic, or any isotropic sheet, is a coupon of its own, written as the team would build it in Abaqus.
  - Other dumbbell standards (ISO 527-2, D412) reuse the outline.
- **Harder:**
  - Every reader of a spec must allow for no `[layup]`. The intake's values-from-spec is extended in part 2, before any such coupon can reach it.
  - Our virtual extensometer reports D3039's chord range. For a linear model this is the same slope as D638's initial modulus. The document's words for D638 are part 2.
- **We now depend on** the founder's D638-22 copy being read clause by clause, and on the "individual values" position (R-25).

## How we will know it was wrong

- A plastic's deck from us is read by the team as something other than their own isotropic shell model.
- A fillet's chords between rows move a result that a finer row spacing settles. The convergence study of ADR-0068 is the place to see it.
- A later edition of D638 changes a value of Fig. 1 that the profile holds.
