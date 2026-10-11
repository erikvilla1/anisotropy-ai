# Physics reference foundation — 2 October 2026

Superseded in part by [the 10 October 2026 completion note](physics-library-completion-2026-10-10.md), which adds nine cards for the operations the engine implements (ADR-0019). As of 2 October the public catalog contained 29 equation/method cards across classical laminate theory, ply failure, constituent estimates, and thermal/moisture effects. It is an equation reference, not an interactive component solver.

## Source basis and conventions

Daniel and Ishai, *Engineering Mechanics of Composite Materials*, second edition (Oxford University Press, 2006), is the equation source. Each current card has a printed-page, equation or section locator, explicit units, and scope notes. Publisher links identify the book; the supplied PDF is not publicly hosted. Original PDF fingerprint and full reading review are recorded in `docs/textbook-review-daniel-ishai-2006.md`.

The prior CLT and basic failure cards were retained with specific citations. Ten cards were added: six constituent/micromechanical relations, maximum strain, and three thermal/moisture relations. The previous CAD/FEA, open-hole and optimization workflow cards are no longer presented as current researched equations. Hashin implementation variants also remain a separate research topic; they are not silently substituted with the textbook's Hashin–Rotem variant.

Original equation pages were inspected for Halpin–Tsai, mixture estimates, maximum strain, thermal coefficients and the moisture definition. Existing CLT references were checked against the textbook review and source locations; stress/strain transformation passages and ply-recovery locations were revisited. Formulas use engineering shear γ rather than the book's tensor-shear vector convention where applicable. Angle is positive counterclockwise from global x to local axis 1; strains satisfy ε(z) = ε0 + zκ. A, B and D dimensions are stated explicitly.

Important distinctions retained:

- Constituent estimates do not create measured material-library values.
- Maximum strain needs applicable compression and shear strain limits, not invented strength/modulus ratios.
- Tsai–Wu's interaction coefficient is measured or explicitly assumed. The selected Tsai–Hill sign convention is stated.
- Thermal-mixture relations assume isotropic constituents; coefficient rotation uses engineering shear and its factor of two.
- The moisture card uses a stated dry mass/volume reference and distinguishes mass gain from volume concentration.
- Coupled laminate effective compliance cannot generally be replaced by A inverse.

## Reproducible checks

`lib/physics-reference-checks.ts` provides small numerical kernels for reference checks only. `tests/physics-reference.test.ts` compares three results with the book's independently printed answers:

| Case | Computed | Printed answer |
|---|---|---|
| Problem 5.2, longitudinal modulus | 154.199 GPa | 154.2 GPa |
| Problem 7.11, Axx/Axy/Ayy/Ass | 60.24465 / 17.52687 / 26.42767 / 20.55928 MN/m | 60.24 / 17.53 / 26.43 / 20.56 MN/m |
| Problem 8.1, α1/α2 | 8.18646 / 55.78273 microstrain/K | 8.19 / 55.8 microstrain/K |

Additional checks cover stress–strain work invariance, inverse rotations, 90-degree interchange, stiffness symmetry, symmetric B = 0, nonzero unsymmetric coupling, thickness scaling, constituent limits and invalid-input rejection. These checks do not validate every displayed criterion or a future FEA solver. Worked-example summaries appear in an expandable section of the physics library.

## Resource sufficiency and later work

The textbook is sufficient for this initial mechanics reference. Supplied MIL-HDBK-17-2F (2002) and CMH-17-3G (2012) provide material and design context; their entire contents have not been promoted to reviewed equation cards. Formula-specific handbook review remains necessary.

Future phases need appropriate element theory, solver documentation and independent benchmarks for FEA, CAD geometry/mesh research, and application-specific evidence for damage, fatigue, fracture, impact, nonlinear response and thick/sandwich structures. Verification starts with current equation checks; component validation and manufacturing applicability are separate tasks.
