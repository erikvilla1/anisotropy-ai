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
- `report.laminate_check` (the hand check of the model documents and the audit): a coupon whose Edge-Left and Edge-Right rows show a width that varies between the grips is a bar of varying width. The pull is shared along it by each width's compliance, R = pull / (a22 times the integral of dy / w(y)), and N_y is stated over the narrowest width. On the check it lies within 0.05 % of the kernel. A straight strip keeps its earlier path. `fields.classical_laminate_check` divides the reaction by the narrowest width. The model document's rebuild steps sketch the dog-bone from the spec and state an isotropic material and a homogeneous shell section (`docs/models/rebuild.py`).
- `fea/checks/d638-type-i-plastic/`: Type I at its least size, 3.2 mm thick, a nominal plastic (E = 3000 MPa, nu = 0.35, not a cited dataset). It has a 50 mm extensometer and a CalculiX 2.21 record.

## As built (2026-11-10, part 2)

- **The registry.** `standards/__init__.py` holds D638 in `PROFILES`, between D3039 and C1869, so the form's Standard row offers it for unnotched tension. `lib/source-rights.ts` lists ASTM D638-22 as a licensed reference.
- **The form (version 0.9).** `intake.py` adds two blocks of rows. The Dog-bone block has Narrow width, Narrow length, Fillet radius and Outer radius, for unnotched tension only; the first three come together. The material block has Material kind (`plies`, the default, or `isotropic`), Thickness, Own material: E and Own material: nu.
  - An isotropic material needs its thickness, E, nu, name and source. It refuses the ply rows, Symmetric, the ply thickness and every ply-material row (library, ply constants and strengths, G13, G23, f12*).
  - It is built for the pulled and pushed tests only. Its criterion may be none, all or blank, and it reads as none.
  - Symmetric, G13 and G23 stay required for plies, now by the check rather than the row.
  - Forms 0.7 and 0.8 still read.
- **The form's other paths.** `values_of_spec` reads a spec without a layup back into the rows. The coupon's name codes an isotropic material by its E and nu, and its stacking as none. `mesh_data` puts node rows at the grip lines, where the outline turns and at the extensometer's ends, and an even count across. The setup check and the package word a plastic as one material with no plies, and the material table derives G = E / (2 (1 + nu)).
- **D638's own words** (`test_quantities.Reduction`). The formulas are shared and each standard's words are its own.
  - D3039, C1869 and a coupon without a standard keep D3039's chord between 1000 and 3000 microstrain, over the gross area.
  - D638 reports the modulus of elasticity (§11.4), read between 500 and 2500 microstrain. §11.4 lets any segment of the initial straight line serve, and A3.9.8 names those strains for Poisson's ratio. It reads over the least original cross-section (§11.2), the narrow section of a dog-bone. Poisson's ratio cites A3.10.
  - Table 3 note B is D3039's alone. A dog-bone under any standard names its area as the narrow section's.
  - The package, the explanation and the studio's card print these words. An isotropic coupon's explanation names stresses along and across the coupon, not ply and fibre stresses, says no failure is modelled, and still gives the test method's sentences. Before, any coupon without a criterion lost them.
- **The studio.**
  - The Geometry step shows the dog-bone's rows for unnotched tension. The Layup step asks Material kind first, and an isotropic material replaces the ply editor with its thickness, E and nu.
  - D638's five types fill the dog-bone's rows and the gage length. They name the extensometer when no device is typed, and a type without an outer radius clears Type IV's.
  - The sketch extrudes the outline the engine meshes, from the same geometry (`lib/studio-sketch.ts`: `dogboneOutline`, `halfWidthAt`, `outlinePoints`), at the plastic's typed thickness.
  - The guided chat asks a plastic for its thickness, E, nu, name and source in place of the plies. Its wording for a plastic is a later part.
- **The public check** names `[test_method] id = "astm-d638"`, Type I. Its decks changed in their heading lines only. The CalculiX 2.21 record was rerun: the same numbers, new deck digests.

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
  - Our virtual extensometer reports D3039's chord range for D3039 and D638's modulus of elasticity for D638 (part 2). For a linear model both are the same slope; a plastic's nonlinear curve, where they differ, needs its yield, a later part.
- **We now depend on** the founder's D638-22 copy being read clause by clause, and on the "individual values" position (R-25).

## How we will know it was wrong

- A plastic's deck from us is read by the team as something other than their own isotropic shell model.
- A fillet's chords between rows move a result that a finer row spacing settles. The convergence study of ADR-0068 is the place to see it.
- A later edition of D638 changes a value of Fig. 1 that the profile holds.

## Amendment 1, 2026-11-09 (a review of parts 1 and 2: what the grips hold, what a model cannot know about the material, and a dog-bone's extensometer and grips)

**Context.** The founder asked for the D638 work to be checked for bugs before everything was merged. A review read every value of Fig. 1 and every clause against the D638-22 and D638-14 copies and found no wrong number. It found judgements and words that misled:
- A coupon gripped on its end rows only (grip region "line") with a tab length was judged as if its grips held the tabs: "115 mm between the grips: met" for a model whose grips are 165 mm apart. `Subject.tab_length` already said "0 when only the end rows are held"; `subject_of` did not.
- One isotropic material was judged as a 0° unidirectional laminate by D3039's Table 2 and as balanced and symmetric by C1869, and C1869 asked for it to be stated a ceramic composite.
- D638's scope was "met" for any isotropic material, though the form offers one for a plastic or a metal sheet.
- Any isotropic E below 1 GPa, and any isotropic deck's derived shear modulus below 1 GPa, was flagged as a possible unit slip, though D638 covers soft plastics.
- An extensometer longer than the narrow section, or grips reaching into it, was accepted.
- Smaller items: Type IV without its outer radius was called "a straight strip"; the page wrote "Specimen I" for D638's Type I; a Size from written by one standard's size stayed after another standard was picked; a D638 size kept bonded tab rows and a strip's size kept the dog-bone rows; the extensometer clause missed §5.2.2 and the grip distance note J.

**Options.**
- What the grips hold:
  - (1) Carry the gripped length beside the tab length (chosen). D638's D, C1869's grip length and the free length read what the model holds, and D3039 Table 2's tab length stays the tab's.
  - (2) Set the tab length to 0 for end-row grips. Rejected: it would also judge D3039's bonded tab length as none.
  - (3) Refuse end-row grips with a tab length. Rejected: the form allows it, and it is a model the engineer may want.
- D638's scope for an isotropic material:
  - (1) Not judged, and the engineer states in the notes whether it is a plastic (chosen). The model cannot tell a plastic from a metal.
  - (2) Judged from E. Rejected: a rule of ours, not the standard's.
  - (3) A new row, plastic or metal. Rejected for now: a new form version for one word.
- A dog-bone's extensometer and grips:
  - (1) Refused when the extensometer is longer than the narrow section, or a grip reaches into it (chosen). Over the fillets the strain is not the narrow section's while the stress is read on it, so the modulus would be wrong (ADR-0003).
  - (2) A warning. Rejected: the result would still be wrong.
- A coupon stated in inches:
  - (1) Held to the millimetre values, as before, with a note under §1.5 saying so (chosen). The standard's inch values in parentheses are for information only, and some fall just outside the millimetres (Type II's 7.2 in is 182.88 mm against 183).
  - (2) Accept the parenthetical inch values. Rejected: not the standard.

**Decision.**
- **What the grips hold.** `Subject` carries `grip_length`, and `gripped` is what the model's grips hold: the tab length, or 0 for grips on the end rows.
- **One isotropic material:**
  - D3039 gives it no Table 2 class, and its laminate is not judged.
  - C1869 finds it no ceramic composite, and does not judge its architecture.
  - D638 leaves its scope to the engineer.
- **Plausible moduli.** The plausible range for one isotropic material's E is 1 MPa to 1000 GPa (ASTM D883 calls a plastic below 70 MPa nonrigid). An isotropic deck is checked on E alone.
- **Refusals.** The spec refuses a dog-bone's extensometer longer than its narrow section, and grips over the tabs that reach the narrow section.
- **Words and clauses:**
  - D638 gains the note "si-values" (§1.5).
  - The grip distance cites note J.
  - The extensometer clause cites §5.2.2.
  - Type IV without its outer radius reads "none: the fillet meets the full width at a corner".
- **The page:**
  - It names the specimen in the standard's own word (`variant_noun`, exported with the profiles).
  - A standard's Size from leaves with that standard.
  - A dog-bone size clears the tab rows, and a strip's size clears the dog-bone rows.
- **Unchanged:** the coupon card in the deck heading still reads "Specimen I". Changing it would rewrite the public check's decks.
- Both copies are now named by edition in `.local/sources/astm/`: `D638-14.pdf` and `D638-22.pdf`.

**Evidence.**
- `fea/tests/test_dogbone.py`:
  - `test_grips_on_the_end_rows_hold_no_length_whatever_the_tab_length`
  - `test_an_isotropic_material_is_no_d3039_class_no_ceramic_composite_and_d638s_scope_is_the_engineers_to_state`
  - `test_type_iv_without_its_outer_radius_says_the_fillet_meets_the_width_at_a_corner`
  - `test_an_inch_coupon_is_told_that_the_millimetres_govern`
  - `test_an_isotropic_deck_is_checked_on_e_alone_from_1_mpa`
  - `test_a_soft_plastic_is_no_unit_slip_on_the_checklist`
  - `test_grips_that_reach_the_narrow_section_are_refused`
  - the extensometer case of `test_the_spec_refuses_what_this_version_does_not_build`
- `tests/studio-standards.test.ts`, "a size is a whole shape ...", and the sketch test's "Type I".
- The public Type I check: 14 requirements met, none missed. The scope now reads "state in the notes".
