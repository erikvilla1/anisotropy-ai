# Physics library completion — 10 October 2026

The public physics library now has a card for every operation the engine documents in `engine/docs/theory.md` ([ADR-0019](decisions/ADR-0019-physics-library-mirrors-engine-theory.md)). It stays an equation reference with sources, units and scope notes; it does not run a component analysis. The 2 October [foundation](physics-foundations-2026-10-02.md) left 29 cards; this release makes it 38.

## Cards added

| Topic | Card | Source location | Engine function |
| --- | --- | --- | --- |
| Classical laminate theory | Laminate compliance · ABD inverse | Daniel & Ishai Eqs. 7.27–7.28, p. 166 | `abd_compliance` |
| Classical laminate theory | Known forces & prescribed curvature | NASA RP-1351 §III.D Eqs. 48–51; engine theory §4 | `prescribed_curvature_response`, `forward_verification` |
| Classical laminate theory | Mixed load & deformation conditions | NASA RP-1351 §III.D; engine theory §4 (ADR-0016) | `mixed_response` |
| Ply failure criteria | Hashin–Rotem (1973) criteria | Eqs. 6.49–6.50 and 6.52, p. 136 | not implemented; reference only |
| Ply failure criteria | First-ply failure load | §9.4, pp. 251–253 | `first_ply_failure` |
| Ply failure criteria | Strength ratio with fixed & variable loads | §9.8, Eqs. 9.26–9.28, p. 256 (ADR-0017) | `tsai_wu_ratio_combined`, `max_stress_ratio_combined` |
| Thermal & moisture effects | Thermal resultants · uniform ΔT | Eqs. 8.18, 8.20, pp. 213–214; Eq. 8.25, p. 215 (ADR-0014) | `thermal_resultants`, `thermomechanical_response` |
| Thermal & moisture effects | Residual ply stress after ΔT | Eq. 8.16, p. 213 | `thermal_ply_surfaces` |
| Thermal & moisture effects | Laminate expansion coefficients | Eq. 8.33, p. 217 | general solve with ΔT = 1 |

Added on 11 October 2026: "Plate buckling · simply supported" (Whitney 1987, Eqs. 5.72 and 6.38; `navier_buckling`, `ritz_buckling`), making 39 cards and 18 in classical laminate theory.

The existing "Laminate engineering constants" card was rewritten: it now gives the general-laminate form (extensional block of the full ABD inverse, §7.12.3, Eq. 7.84, pp. 183–184) with both Poisson ratios and the shear coupling coefficients, matching `engineering_constants`. Its old text limited the card to B = 0.

Every new card has a plain-text equation (the search basis), a typeset KaTeX form, a units line and a source location. Cards that describe an engine operation name the function in their detail text so a reader can go from the card to `theory.md` and the validation cases.

## Choices worth knowing

- **Hashin–Rotem is presented only as the textbook prints it** (fiber criterion and interfiber criterion), under that exact name. The later Hashin fiber and matrix mode equations with shear in the fiber mode are not on the page and remain in the deferred list, which now says so.
- **Two operations have no textbook equation.** Prescribed curvature and mixed conditions are rearrangements of the constitutive relation; their cards cite NASA RP-1351 for the relation and the engine theory sections for the partitioning. Their source link is the NASA report, not the book.
- **Page citations were checked against the local extraction** of the second edition: Eq. 7.84 on PDF page 202 (printed 183), Eq. 8.16 on 232 (213), Eq. 8.25 on 234 (215), Eq. 8.33 on 236 (217), Eqs. 6.49–6.53 on 155 (136), Eqs. 9.26–9.28 on 276 (256), Eqs. 7.27–7.28 on 185 (166). The page offset is 19 throughout.
- The deferred topics (CAD and finite elements, open-hole strength, layup optimization) are unchanged.

## Checks

- `tests/physics-reference.test.ts`: the card count is pinned at 38; every card has a location, units, an https reference and a typeset equation; eight engine functions are matched to the card that names them; the topic counts are 17 (CLT), 9 (failure), 6 (micromechanics) and 6 (thermal). `npm test`: 68 passed, 0 failed.
- Browser spec `physics-foundations`: the intro says 38 cards; the fixed-and-variable card opens with its page citation and a rendered KaTeX equation; the CLT search finds the mixed-conditions card with its ADR reference; the thermal search finds the residual-stress card with its equation and page.
- `npm run typecheck`: exit 0. `npm run build`: static export completed. Browser specs physics-foundations and material-analysis against the export: 7 passed.

## What the library does not do

It does not compute. The engine does, and its 30 validation cases are the evidence for the equations on these cards. Progressive failure, interlaminar stress, moisture diffusion and finite elements are still outside both the engine and the library.
