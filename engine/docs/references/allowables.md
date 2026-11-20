# Allowables and design values

What a mean strength, a B-basis value and an A-basis value are, which one a wing's margins use, and how a margin is formed from it (ADR-0126, ADR-0127). The values themselves are in the material record, each with its basis, table and page; an answer reads them from the record, never from this page.

Status: a draft of 2026-11-20, not yet reviewed by the founder. Written in our own words. Each section ends with its sources; a source marked UNVERIFIED was not read at its section and page.

## Mean, B-basis and A-basis

<!-- also: allowable, allowables, basis, basis value, B-basis, A-basis, statistically based, statistical basis, 90/95, 99/95, probability, confidence, design allowable, mean strength, average, typical value, test mean, scatter, variability -->

The mean strength is the average of the specimens tested. Half of a material's production would be weaker, so a mean is a description of the material, not a value to design with.

An allowable is set on a probability basis instead. A B-basis value is a strength that at least 90 % of the material's production is expected to exceed, said with 95 % confidence; an A-basis value, 99 % with 95 % confidence, so it is lower. Both are worked out as the mean less a number of standard deviations. The number depends on how many specimens and batches were tested and on the shape of the scatter: few specimens give a larger factor, so a small program is penalized, not trusted more.

Sources: FAA AC 20-107B, Appendix 2, definition 1 (p. A2-1); NCAMP statistical report NCP-RP-2009-028 Rev B, section 1.3 (p. 12), the basis value as the mean less k times the standard deviation.

## Which basis to use where

<!-- also: which allowable should I use, A or B basis, single load path, redundant structure, fail-safe, multiple load paths, primary structure, design basis, design strength -->

Airworthiness guidance ties the basis to the structure. A part whose failure alone would lose the structure, a single load path, is designed to A-basis values. Structure with more than one load path, where a failed member's load passes safely to the others, may use B-basis values. Composite structure is expected to give the same fail-safe, multiple load path assurance as metal structure when B-basis static strength allowables are used.

The wing's margins use the B-basis strengths of the material's public qualification report (ADR-0126): the founder's choice for the wing. A material whose record holds no B-basis strengths offers its test means only, and the page says those are not design values.

Sources: FAA AC 20-107B, paragraph 8.a(4)(b) (p. 17), on fail-safe multiple load path structure and B-basis allowables, and paragraph 7.e (p. 10), on allowables or design values derived in compliance with 14 CFR 2x.613; the A-basis and B-basis split by load path is the rule of 14 CFR 23.613 and 25.613, not read here: UNVERIFIED.

## B-basis values and B-estimates

<!-- also: estimate, B-estimate, estimates, recommended values, recommended B-basis, insufficient data, CMH-17 requirements, shaded values, two batches, too few batches, modified CV, coefficient of variation, ANOVA -->

A qualification report calls a basis number a value when its data meet the statistical requirements of the handbook it follows, and an estimate when they do not, for instance when too few batches were tested. The values the report recommends are never estimates.

Where a report recommends no value for a strength a design needs, its own estimate is the next best number from the same tests, labelled as such. The wing does this for two strengths of IM7/8552 at room temperature and dry, compression along the fibres and the shear strength at 5 % strain, and the page shows "B-estimate" beside them.

The modified coefficient of variation is a correction used while a material is new: a measured scatter below 8 % is raised before the basis value is worked out, since a qualification program made in a few weeks shows less scatter than years of production will. It lowers the basis value; it never raises it. The recommended values use it where the data allow.

Sources: NCAMP statistical report NCP-RP-2009-028 Rev B, section 1 (p. 9), values and estimates; section 1.4 (pp. 12 and 13), the modified coefficient of variation; section 2.3 (p. 30), estimates from one or two batches; section 3.1 (p. 34), the rules for recommended values; Table 3-1 (p. 35), the recommended values.

## Normalized and as-measured strengths

<!-- also: normalized, normalised, as measured, fibre volume, fiber volume, cured ply thickness, CPT, nominal ply thickness, resin content -->

Panels of one material come out a little thicker or thinner, with more or less resin. A strength carried by the fibres is therefore normalized: scaled to a nominal cured ply thickness, as if every panel held the same fibre in the same thickness. A strength carried by the matrix, across the fibres or in shear, is given as measured, since resin content does not scale it the same way.

A normalized strength belongs with the nominal ply thickness it was normalized to. The material record keeps that thickness, and the wing's plies use it.

Sources: NCAMP statistical report NCP-RP-2009-028 Rev B, section 3.1 (p. 34), only normalized basis values for normalized properties, and Table 3-1 (p. 35).

## Environment: hot, wet and cold

<!-- also: environmental knockdown, knockdown, hot wet, hot/wet, ETW, ETD, CTD, RTD, room temperature dry, elevated temperature wet, moisture, humidity, temperature, conditioning, environmental factor -->

A polymer matrix softens when hot and when it has absorbed water, and it is more brittle when cold. Strengths carried by the matrix fall most, compression and shear above all; strengths carried by the fibres change less. Qualification programs therefore test each property at room temperature and dry, cold and dry, hot and dry, and hot after soaking in moisture.

Airworthiness guidance asks that the design values hold at the worst temperature and moisture the part will see in service, and that a margin of safety be positive with design values that include the effects of environment and repeated load.

The wing's strengths today are room temperature, dry only. Its margins say nothing about a hot and wet day; that check is not built (ADR-0126).

Sources: FAA AC 20-107B, paragraph 6.d (p. 6), environmental design criteria, and paragraph 7.a(2) (p. 8), margins with design values that include environment; NCAMP statistical report NCP-RP-2009-028 Rev B, Table 1-3 (p. 11), the four test environments.

## Design values and the margin of safety

<!-- also: margin, margin of safety, MS, design value, design values, ultimate load, limit load, factor of safety, ultimate factor, proof factor, strength ratio, reserve factor, how is the margin worked out, negative margin -->

A design value is an allowable adjusted to the real structure: for holes, joints, damage or the environment it will meet. A margin of safety compares the structure's strength with the load it must carry at that factor.

The wing works its margins this way. For each ply, flight case and station it finds the strength ratio, the factor by which the limit load could grow before the ply fails by the chosen criterion with the material's strengths. A margin is that ratio over the factor of safety, less one, at the ultimate factor and at the proof factor when the wing file gives one. A margin of zero means the ply just carries ultimate load; a positive margin is spare strength, a negative one a failure. The lowest margin over every ply, case and station is the wing's verdict, and the page names the strengths' basis beside it.

Sources: FAA AC 20-107B, Appendix 2, definition 12 (p. A2-2), design values; Laminate theory, the wing's margins.

## Which strengths a wing used

<!-- also: what allowables are you using, which allowables, what strength did you use, strengths used, source of the allowable, which dataset, which report -->

The wing's answer lists the strengths it used: the material, the dataset, the basis of each strength (B-basis, B-estimate or test mean), the report with its table and page, and which strengths are estimates. The Material step of the wing page shows the same list with a link to each page. An answer to "what allowables are you using?" reads that list and names the basis first.

Sources: the material library's record of the material; NCAMP statistical report NCP-RP-2009-028 Rev B for IM7/8552.
