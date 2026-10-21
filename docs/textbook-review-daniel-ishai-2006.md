# Daniel and Ishai textbook review

Reviewed 1 October 2026 for the Composite_AI material and formula libraries.

## Source and scope

Isaac M. Daniel and Ori Ishai, *Engineering Mechanics of Composite Materials*, second edition, Oxford University Press, 2006. ISBN 978-0-19-515097-1.

Source: user-supplied PDF of *Engineering Mechanics of Composite Materials*, Daniel and Ishai, second edition. The full PDF is retained locally and is not included in Git.

- 463 PDF pages, including front matter, ten chapters, three appendices and indexes.
- SHA-256: `8c46dbb6cc5d485aaa5a256b9e10c93fd4ee40eb86dc9973ecdb833b4ec729d2`.
- Publication year is 2006. The PDF creation timestamp and the date of this review are not material revision dates.
- Read the extracted text throughout the book in sequential batches, including references and problems. Visually inspected the material appendix, transformation appendix, pages without usable text, selected equations, sparse figure pages and selected answer pages. OCR drops symbols, fractions and subscripts; extracted mathematics is not a verified transcription.
- This is a complete reading review with selected numerical checks, not an independent proof of every equation, a solution of every exercise, an exhaustive errata search or experimental qualification of its materials.
- This turn adds research documentation. No textbook dataset or equation was released into the public application. The complete textbook and extracted text remain local rather than becoming public website assets.

Page references below distinguish **printed page** from **PDF page**. The offset changes because the PDF includes blank pages.

## Findings that change the library work

1. **The book is a useful, identifiable engineering reference.** It supplies named composite datasets, definitions, derivations, experimental context and checkable examples. An older publication date does not by itself invalidate a mechanics equation or historical measurement.
2. **The book does not qualify all its tabulated values for final structural design.** Appendix A, printed p. 373 / PDF 393, explicitly describes a compilation from different sources without complete verification and recommends educational and preliminary design use pending further checks. Printed p. 42 / PDF 59 specifies ambient 24°C (75°F), dry conditions for Tables A.4–A.7 and explains batch variation.
3. **M10E/3783 now has a directly inspected textbook table.** Tables A.5 and A.6 establish a citable historical dataset. The previous audit's statement that the table was inaccessible has been superseded by this supplied file. This does not establish a current supplier specification, cure process or statistical allowable basis.
4. **The school import has differences that cannot be erased by attaching this citation.** Examples include AS4 and M10E out-of-plane Poisson ratios and AS4/AGP moisture coefficients. Keep the imported transcription and a new textbook dataset separate while resolving those differences.
5. **Several printed unit pairs conflict.** A reliable library must verify conversions and preserve source discrepancies. A published book is evidence, not a reason to skip checking numbers.
6. **Most core CLT and failure formulas already exist in `lib/physics.ts`.** The immediate gain is equation-level references, assumptions and benchmarks. New topics include micromechanics, maximum strain, explicit hygrothermal load scaling, selected test reductions and fracture mechanics.

## Reading map and chapter findings

| Section | Printed pages | PDF pages | Findings relevant to this product |
|---|---|---|---|
| Front matter | Roman-numbered pages | 1–16 | Edition, publication, intended audience and scope. The first-edition preface describes an older chapter structure; use the second-edition contents. |
| 1: Introduction | 1–17 | 17–33 | Composite definitions, reinforcement arrangements, applications and design opportunities. Historical aircraft/application examples are context, not current market evidence. |
| 2: Basic concepts, materials, processes and characteristics | 18–42 | 35–59 | Constituent versus composite properties, material symmetry, fiber arrangements, manufacturing and representative behavior. Processing and fiber volume are part of material identity. Typical appendix conditions are stated on p. 42. |
| 3: Elastic behavior of unidirectional lamina—micromechanics | 43–62 | 61–80 | Rule of mixtures, bounds, transverse/shear predictions, Halpin–Tsai and short-fiber effects. These calculate estimates from constituent inputs; they do not turn an unidentified resin/fabric into a measured material system. |
| 4: Elastic behavior of composite lamina—macromechanics | 63–97 | 81–115 | General and orthotropic elasticity, plane stress, stiffness/compliance, reciprocity, axis transformations and engineering constants. Essential distinction between tensor shear strain and engineering shear strain. |
| 5: Strength of unidirectional lamina—micromechanics | 98–119 | 117–138 | Fiber/matrix failure, load transfer, fragmentation, compression microbuckling/kinking and transverse/shear mechanisms. Idealized constituent models need their stated assumptions; composite strength is not generally fiber strength multiplied by fiber fraction. |
| 6: Strength of composite lamina—macromechanics | 120–157 | 139–176 | Maximum stress/strain, Tsai–Hill, Tsai–Wu, mode-dependent criteria, transformed strength and load multipliers. Failure criteria can disagree; a scalar index does not establish the physical failure mode. |
| 7: Elastic behavior of multidirectional laminates | 158–203 | 177–222 | CLT, ABD assembly, coupled compliance, symmetry/balance, effective properties, quasi-isotropy, shear-deformation theory and sandwich response. Balanced does not imply zero bending–twisting coupling; extensional quasi-isotropy does not imply isotropic strength. |
| 8: Hygrothermal effects | 204–242 | 223–261 | Temperature/moisture dependence, expansion coefficients, free strains, equivalent loads, residual stresses and warpage. Thermal and moisture coefficients have different dimensions and concentration conventions. |
| 9: Stress and failure analysis of multidirectional laminates | 243–302 | 263–322 | Ply stress recovery, first-ply failure, progressive damage, ultimate failure, delamination/fracture and design examples. Fixed residual stress must be separated from scaled mechanical loading. First-ply failure and final collapse are different predictions. |
| 10: Experimental methods for characterization and testing | 303–371 | 323–391 | Constituent tests; tensile, compressive, shear and through-thickness testing; environmental measurements; fracture and notched/textile tests. Test geometry, data reduction, failure validity and material architecture determine what a reported property means. |
| Appendix A | 373–383 | 393–403 | Nine material tables covering fibers, matrices, cured composites, metals and sandwich cores. All pages visually inspected; incomplete entries and conflicting unit pairs retained as issues. |
| Appendix B | 385–387 | 405–407 | Three-dimensional elastic transformations. Compact notation embeds shear scaling factors; do not feed this table straight into engineering-shear matrices without reconciling conventions. |
| Appendix C | 389–396 | 409–416 | Selected problem answers suitable for numerical comparisons after checking problem inputs and rounding. Three problems independently recalculated below. |
| Author and subject indexes | Electronic index pagination | 417–463 | Reviewed for navigation and terminology; index references are not separate material evidence. PDF 434 is blank. |

Blank pages 4, 12, 34, 60, 116, 262, 392, 404, 408 and 434 were visually confirmed. PDF 290–291 and 354–355 contain substantive scanned pages despite having no extracted text and were read from images. PDF 226 and 406–407 also required image review to recover their content.

### What the testing chapter adds

- A tensile modulus, tangent/secant shear modulus, proportional limit, ultimate strength and short-beam apparent shear strength are different quantities. Preserve those definitions rather than collapsing them into one modulus or strength field.
- A ±45° laminate shear test and an off-axis lamina test require their own transformations and limitations. Off-axis loading is not generally pure shear.
- Short-beam and double-notch results depend on actual failure mode; a nominal shear calculation alone does not prove shear failure.
- Textile specimens and strain measurements must account for the repeating fabric unit cell. UD test assumptions do not transfer automatically to woven materials.
- Mode I, Mode II and mixed-mode fracture toughness are energy quantities, separate from interlaminar strength.
- Notched strength depends on laminate, geometry and calibrated damage/fracture behavior. The book's characteristic-distance examples are not universal material constants.
- The chapter cites historical standard editions. Its descriptions should not be presented as the current ASTM procedures without separately checking the official current documents.
- Fatigue, creep, impact and nondestructive evaluation receive limited treatment or references; the book alone is not a comprehensive basis for those product capabilities.

## Material evidence and reconciliation

### Tables that matter

| Table | Printed / PDF pages | What it supplies |
|---|---|---|
| A.1–A.2 | 374–375 / 394–395 | Fiber properties. AS4 fiber stiffness here is not AS4/3501-6 cured-lamina stiffness. |
| A.3 | 376 / 396 | Typical polymer matrices. Matrix resin properties cannot substitute for cured composite properties. |
| A.4 | 377–378 / 397–398 | Two-dimensional UD properties, including AS4/3501-6, IM6G/3501-6, IM7/977-3 and AS4/APC2. Some other columns identify only a generic system. |
| A.5 | 379 / 399 | Two-dimensional fabric properties, including M10E/3783 and AGP370-5H/3501-6S. |
| A.6 | 380 / 400 | Three-dimensional UD/fabric constants and strengths, including the same M10E and AGP systems and AS4/3501-6. |
| A.7 | 381 / 401 | Selected high-temperature material systems. The category name does not mean every value was measured at elevated temperature. |
| A.8 | 382 / 402 | Typical structural metals for comparison. |
| A.9 | 383 / 403 | Named sandwich-core examples, including Divinycell H80/H100/H160/H250, CK57 balsa and PAMG 5052 honeycomb. |
| 8.1–8.3 | 208–211 / 227–230 | Temperature-dependent IM7/977-3 properties and thermal/moisture data. Conditions must remain attached to each row. |

### Relation to the existing 22-record import

| Imported material/group | What this book establishes | Remaining distinction |
|---|---|---|
| AS4 / 3501-6 UD | Exact named column in A.4 and A.6; many imported imperial values align. | Historical typical dataset. Out-of-plane Poisson ratio and moisture rows differ from the school import. Do not merge this with the existing NASA model-input dataset. |
| AGP370-5H / 3501-6S | Exact named fabric column in A.5 and A.6; three-dimensional properties available. | Keep book naming and data basis separate from the ICF experimental source. Moisture rows differ from the import. |
| M10E / 3783 | Exact named fabric column in A.5 and A.6. A.6 includes E1 = 24.5 GPa, E2 = 23.8 GPa, E3 = 11.6 GPa. | The table itself does not establish a present-day procurement specification or the imported eight-harness description. Out-of-plane Poisson ratio differs. Thermal/moisture entries are absent. |
| E-glass / 3783 UD | Generic E-glass/epoxy UD column numerically resembles the import. | The UD column does not name 3783. The fabric M10E/3783 label must not be borrowed to identify the UD column. |
| 7781 / E765 | Book supplies 7781/5245C, a different system. | Retain the existing exact E765/NCAMP evidence; no resin substitution. |
| M55J and CF0302 / MTM49LT | No exact replacement table identified. | Other carbon grades and resin systems cannot establish these records. |
| Divinycell H250 | Named historical H250 column in A.9. | Do not replace the existing supplier release with a 2006 compilation. H45 is not in A.9. |
| Nomex, unidentified aluminum core and BALTEK | Other named core examples appear. | Generic density or material-family similarity does not establish the imported product grade. CK57 and PAMG 5052 are not automatic matches. |
| Ten generic carbon/glass UD/weave nominal, wet-layup and VaRTM entries | Provides micromechanics and representative examples. | Still needs actual resin, reinforcement and process identity. Calculations cannot recover missing purchasing/manufacturing records. |

### Specific discrepancies to resolve before a material release

1. **AS4 ν23:** imported value 0.47; Table A.6 prints 0.54. A citation to A.6 does not support retaining 0.47 as that table's value.
2. **M10E ν23 — corrected 2 October 2026:** visual reinspection of Table A.6 confirms ν23 = 0.20 and ν13 = 0.15. The earlier audit incorrectly read 0.11 from the ν12 row. The school ν23 entry therefore agrees with this table.
3. **AS4 moisture expansion:** the import repeats thermal-looking values −0.50, 15, 15 under a moisture heading. A.6 gives β1 = 0.01, β2 = 0.20, β3 = 0.20. Section 10.3.5 defines the moisture concentration basis; these are not thermal coefficients or values to multiply blindly by 10⁻⁶.
4. **AGP moisture expansion:** the import repeats 1.90, 2.10, 29 from the thermal rows. A.6 and Table 8.3 give 0.05, 0.05, 0.27. This is evidence of a disagreement, not proof of the history of the school transcription.
5. **AGP density in A.5:** the image prints 1.60 g/cm³ and 0.58 lb/in³. A.6 prints 0.058 lb/in³. Dimensional conversion supports approximately 0.0578 lb/in³. Flag the A.5 pair rather than copying 0.58.
6. **Matrix table A.3:** the HY6010/HT917/DY070 CTE pair is printed 62 and 3.4 in micro-units per °C and °F. The vinylester CTE pair is printed 100–150 and 212–514; vinylester shear strength is 53 MPa and 29 ksi. These pairs do not convert consistently. Do not publish both or silently infer the intended experimental value.
7. **Elastic symmetry:** A.6's AS4 E2 = 10.3 GPa, G23 = 3.7 GPa and ν23 = 0.54 do not satisfy the exact transverse-isotropic relation G23 = E2/[2(1+ν23)] (which would give about 3.34 GPa). Treat the compiled constants as a set requiring model-consistency review; do not silently impose transverse isotropy or overwrite measurements.
8. **Missing cells and thickness:** blank/dash entries are absent data, not zero. These tables do not supply every required ply thickness or process condition. A fully populated solver material card cannot be assumed.
9. **Rounded equivalents:** printed SI and imperial values are often rounded separately. Select and record a canonical source value, calculate display conversions, and preserve source precision. Derive reciprocal Poisson ratios consistently when a constitutive model requires exact reciprocity.

## Formula-library candidates and reference map

These are implementation notes in the product's engineering-shear convention. They are not a verbatim equation transcription or a validated software module. The existing formula library contains 32 method cards across five topics; avoid duplicating those cards merely to add this source.

| Topic | Book reference | Product action and conditions |
|---|---|---|
| Density and fiber/matrix fractions | Chapters 2–3 | Add constituent-based estimates with fraction units explicit. Include void assumptions. |
| Longitudinal rule of mixtures; transverse/shear estimates | Chapter 3 | Add separate predicted-property cards. E1 = Ef Vf + Em Vm for the stated continuous-fiber model; transverse inverse-mixture and Halpin–Tsai estimates are not interchangeable measurements. |
| Halpin–Tsai and short-fiber efficiency | Chapter 3 | Record reinforcement shape, aspect ratio and fitted parameter. Do not present a chosen parameter as an industry constant. |
| 3D orthotropic compliance and reciprocity | Chapter 4, §§4.1–4.3 | Extend beyond the current plane-stress card only with nine independent constants, νij/Ei = νji/Ej, units and positive-energy checks. |
| Plane-stress Q | Eq. 4.56, p. 77 / PDF 95 | Already present. Δ = 1 − ν12ν21; Q11 = E1/Δ, Q22 = E2/Δ, Q12 = ν12E2/Δ, Q66 = G12. |
| Stress/strain transformations | Eqs. 4.57–4.67, pp. 77–79 / PDF 95–97 | Already present. The book uses γ/2 in a tensor-strain vector; our γ vector needs a different strain matrix from the stress matrix. |
| 3D transformation | Appendix B, pp. 386–387 / PDF 406–407 | Candidate extension. Resolve contracted indices and factors of two/four before coding; verify against full tensor rotation. |
| Maximum stress and maximum strain | Chapter 6, §§6.3–6.4 | Maximum stress exists; maximum strain would be an addition. Actual strain limits require evidence, especially for nonlinear shear; do not assume strength/modulus always gives failure strain. |
| Tsai–Hill | Chapter 6, §6.5; Eq. 6.16 | Existing card. Keep tensile/compressive selection and mixed-sign convention explicit; fabric/3D variants need their own definitions. |
| Tsai–Wu | Eqs. 6.29–6.40, pp. 131–133 / PDF 150–152 | Existing cards. Interaction coefficient is measured or assumed; Eq. 6.40's −½√(f11 f22) is an approximation, not a measured universal property. |
| Hashin–Rotem | Eqs. 6.49–6.53, p. 136 / PDF 155 | Add only under this exact formulation name. These equations must not replace the existing Hashin fiber/matrix mode cards as if the variants were identical. |
| Load multiplier | Eqs. 6.56–6.60, p. 139 / PDF 158 | Existing card. Solve aR² + bR − 1 = 0 for an admissible positive loading factor. Tsai–Wu FI is not generally 1/R or 1/R². |
| CLT kinematics and ABD | Eqs. 7.20–7.24, p. 164 / PDF 183 | Existing cards. ε(z) = ε0 + zκ. Integrate Qbar over actual ply boundaries; A, B, D have units N/m, N, N·m in SI. |
| Coupled compliance and effective constants | Eqs. 7.27–7.28, p. 166 / PDF 185; §7.12 | Existing card states B = 0 limitation. General effective constants require the full ABD inverse and defined moment/curvature constraints. |
| Shear deformation and sandwich response | §§7.17–7.18 | Separate future model scope; CLT cannot represent every thick or soft-core sandwich response. Retain face/core and thickness assumptions. |
| Thermal expansion estimates and transformation | Eqs. 8.1–8.9, pp. 208–211 / PDF 227–230 | Add micromechanical estimates separately from measured CTE. Engineering shear expansion is 2mn(α1 − α2). |
| Thermal/moisture loads, residual stress and warpage | Chapter 8 | Existing general cards can gain explicit reference and examples. Integrate α(T) if variation matters; document stress-free reference conditions and restraint. |
| First-ply failure with fixed thermal/moisture stress | Eqs. 9.26–9.28, p. 256 / PDF 276 | Useful extension: evaluate σ(R) = R σmechanical + σresidual. Do not scale fixed residual stress with mechanical load. |
| Progressive stiffness reduction | Eq. 9.42 and procedure, pp. 270–271 / PDF 290–291 | Research scope. Reduction factors used in examples are not universal. Damage initiation, evolution, final-failure definition and numerical stability need separate verification. |
| Energy release rate and DCB | Chapter 9; §10.6.1, p. 335 / PDF 355 | Candidate educational cards. Linear-elastic compliance method: G = P²/(2b) dC/da. Record crack length, width and whether thickness is an arm thickness or full specimen thickness. |
| Moisture concentration | Eq. 10.19, p. 314 / PDF 334 | Essential data convention: c = Vwater/Vcomposite = (ρcomposite/ρwater) M, where M is relative mass gain as a fraction. Percentage input must be converted. |
| Experimental property reduction | Chapter 10 | Add only with test-specific geometry, strain definition, loading and failure-validity rules. The formula alone does not establish conformity with a test standard. |
| Orthotropic circular-hole stress concentration | Eq. 10.68, p. 349 / PDF 369 | Possible extension to current generic Kt card. Large-plate/principal-axis assumptions apply; not a finite-width, damaged-hole or general layup solution. |

### Implementation rules learned from the reading

- Label axes and distinguish fiber, cured lamina, fabric ply, laminate and core quantities.
- Use positive magnitudes for tensile/compressive strengths and a separately defined signed stress convention.
- Keep a failure index, predicted failure mode, load multiplier, specified safety factor and safety margin as separate outputs.
- For an unsymmetric laminate, the extensional block of the full inverse is generally not A⁻¹. Coupling can change the apparent modulus depending on restraints.
- Symmetry implies B = 0 for a matching stiffness distribution. Balance removes extensional shear coupling when thickness/materials match; it does not generally remove bending–twisting coupling.
- A free laminate can have residual ply stresses even when net force and moment are zero.
- A formula for a prediction must identify calibration parameters and omitted effects. Do not manufacture measured-property rows from model outputs without labeling their basis.
- CLT does not resolve free-edge interlaminar stresses, delamination, local hole damage or arbitrary three-dimensional fields.
- Keep historical measured/model datasets immutable. An updated test-method publication is a review trigger, not permission to overwrite an old measurement.

## Independent numerical checks performed

Recalculated three problems using the printed SI inputs and independent arithmetic, then compared with Appendix C. These checks verify selected mathematical interpretations, not physical material validity or the application solver.

| Problem | Inputs and location | Recalculated result | Book answer |
|---|---|---|---|
| 5.2 | pp. 117–118 / PDF 136–137: Vf 0.65, Ef 235 GPa, Em 4.14 GPa, fiber tensile strength 3450 MPa; linear constituents and fiber failure first | E1 = 154.199 GPa; longitudinal strength = 2263.773 MPa | p. 391 / PDF 411: 154.2 GPa; 2264 MPa |
| 7.11 | p. 201 / PDF 220, using Problem 7.8 inputs: [0/+45/−45], 0.25 mm each, E1 145 GPa, E2 10.5 GPa, G12 7 GPa, ν12 0.28 | Axx = 60.24465, Axy = 17.52687, Ayy = 26.42767, Ass = 20.55928 MN/m | p. 393 / PDF 413: 60.24, 17.53, 26.43, 20.56 MN/m |
| 8.1 | p. 239 / PDF 258: isotropic glass/matrix inputs, Vf 0.55, Ef 69 GPa, Em 3.8 GPa, νf 0.22, νm 0.36, αf 4.5 and αm 90 microstrain/K | α1 = 8.18646; α2 = 55.78273 microstrain/K | p. 394 / PDF 414: 8.19; 55.8 microstrain/K |

All three agree within the precision of the printed answers. Local reproducibility files are `.local/sources/textbook-daniel-ishai/check-examples.py` and `example-checks.json`; they are ignored research artifacts, not shipped software tests.

Before a future solver release, build a broader test set covering axis rotations, reciprocity, stiffness positivity, symmetric/unsymmetric laminates, thermal restraint, zero-load failure evaluation and agreement with an independent implementation. This review did not execute the app's test suite because it made no app changes.

## Recommended use in the next library work

1. Introduce this edition as a bibliographic source with table/equation and printed-page locations. Public references should identify the book/publisher, not make the school classroom appendix the sole source or expose the supplied mirror filename.
2. Prepare a distinct historical textbook dataset for M10E/3783 and, where useful, AS4 and AGP. Attach ambient/dry conditions, typical-data basis and the actual table's missing fields. Resolve the listed discrepancies before release; do not relabel the school records in place.
3. Keep current supplier and NCAMP datasets alongside historical references as distinct choices where identities and conditions differ. A newer publication does not automatically supersede every earlier test.
4. Add equation-level citations to existing formula cards, then expand into micromechanics, maximum strain and test/property definitions. Use the three reproduced problems as the start of a numerical reference set.
5. Follow the chapter bibliographies for underlying experiments where final-use support is needed. The appendix does not consistently assign a specific original experiment, batch or method to each cell; do not fabricate that lineage.
6. Keep the user's lookup simple: property, direction, value, units, conditions and a clear reference. Details can expand to show source edition, table/page, data basis and review history. Simplicity must not turn typical data into certified allowables.

The book substantially improves traceability and provides a strong mechanics foundation. It does not establish missing product identities or make the full existing catalog qualified, current or statistically allowable by itself.
