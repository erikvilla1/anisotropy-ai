# ADR-0126: A wing's margins use the B-basis strengths of the material's public qualification report, kept as a dataset of their own beside its means

- Status: Proposed
- Date: 2026-11-20
- Decided by: Founder, 2026-11-20 ("B-basis from public reports", his choice on the card "Which strengths should the wing's margins use?": add B-basis values for the wing's material from public qualification reports, each with table and page, and the wing's margins use them, labelled B-basis). The B-estimates for two strengths, the dataset of its own, the example's weight and the wording are the drafter's | Drafted by: Claude Code
- Related: [ADR-0018](ADR-0018-source-rights-classes.md), [ADR-0020](ADR-0020-material-library-as-engine-input.md), [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0118](ADR-0118-the-wing-workspace-works-the-engines-hand-calculation-through-the-api-on-every-settled-change-draws-what-the-engine-returns-and-keeps-the-wing-as-its-wing-file.md), [ADR-0119](ADR-0119-a-wings-finite-element-check-runs-from-the-wing-workspace-as-a-background-job-like-a-coupon-run-and-sets-the-model-beside-the-hand-calculation.md), `lib/qualification-materials.ts` (`qualifiedCarbonIM7BBasis`), `engine/src/anisotropy_engine/library.py` (`strength_dataset`), `engine/src/anisotropy_engine/wing/wing_file.py` (`_material`, `wing_material`), `fea/src/anisotropy_fea/wing_check.py` (`check_report`), `components/workspace/wing-rail.tsx` (`MaterialPanel`, `StrengthsUsed`), `lib/wing.ts` (`strengthWords`), the wing chat plan (Claude Doc "Wing chat: tools and references plan")
- Area: data, engine, fea, website

## Context

- The library's IM7/8552 record holds the measured means of NCAMP's data report (CAM-RP-2009-015 Rev B, RTD column). Its record already said that Table 3-1 of the statistical report (NCP-RP-2009-028 Rev B, p. 35) gives the B-basis values, left in the report.
- The wing's margins (ADR-0115) were formed on those means. AC 20-107B, Appendix 2, item 1, defines allowables on a probability basis: A-basis 99 % with 95 % confidence, B-basis 90 % with 95 % confidence; its paragraph 7.e asks that the scatter in strength be covered by such allowables. A margin on means is not a design margin.
- Table 3-1 (p. 35) recommends B-basis values at room temperature, dry, for longitudinal tension (323.09 ksi, normalized), transverse tension (7.59 ksi), transverse compression (36.45 ksi), in-plane shear at 0.2 % offset (6.87 ksi) and short beam strength (15.10 ksi). It recommends none at room temperature for longitudinal compression from the cross-ply tests (two batches, Table 4-6, p. 46) or for shear strength at 5 % strain (Table 4-10, p. 50). Those tables give B-estimates: 218.20 ksi and 11.47 ksi (modified CV).
- The wing's ply check needs five strengths (F1t, F1c, F2t, F2c, F6); the library reads F1c from the cross-ply back-out and F6 at 5 % strain.
- The statistical report was read from the copy the founder sent on 2026-11-20 (the publisher's site refuses automated downloads); its SHA-256 on 2026-10-10 is in `lib/source-provenance.ts`.

## Options considered

1. **A dataset of B-basis strengths beside the means, picked by the wing file's `strengths = "B-basis"`** (chosen). The library already keeps several datasets per material; the engine reads one by its id. The moduli stay the means', so only the margins move.
2. A basis column on every property of the means record. Rejected: every reader of the library (coupons, the calculator, the laminate solver) would have to choose a column, for a need only the wing has today.
3. Knock the means down by a factor (for example the B-basis over mean of tension). Rejected: a number of our own where the report gives one; the founder asked for the reports' values.
4. Recommended values only, with the 0.2 % offset shear strength (6.87 ksi) as F6 and no F1c. Rejected: no longitudinal compression at all, which the wing's upper skin needs. The 0.2 % offset value stays in the record for a check that wants it.

## Decision

- The library gains the dataset "NCAMP 2019 · B-basis" (`ncamp-im7-8552-2019-rtd-bbasis-v1`) for IM7/8552, sourced from the statistical report, marked `strengthBasis: "B-basis"`. Each strength has its table and page; F1c and F6 are marked "B-estimate", the others "B-basis". Fibre-dominated values are normalized to the 0.0072 in ply, as Table 3-1 gives them; matrix-dominated values are as measured. The moduli are the measured means of Table 3-3 (p. 37), equal to the means record's. Only room temperature, dry, is entered.
- A wing file's `[material]` takes `strengths = "B-basis"` (or `"mean"`, the default): the strengths come from the material's B-basis dataset, everything else from its means. A material without one is refused by name, and `dataset` with `strengths` is refused.
- The wing's answer carries `material`: the basis, the dataset, the report, each strength with its basis, page and link, and which are estimates. The finite element check's report carries `strength_basis`. The page's verdict says "on B-basis strengths" (or "on test-mean strengths, not design values"); the Material step offers B-basis or test means and lists the strengths used with a link to each page. Picking a library material picks its B-basis strengths where the library holds them.
- The example wing uses B-basis strengths. On them its skin at 3000 N failed by 4.7 % (−0.047, case 6); its weight became 2700 N, a round value, and it passes (+0.059 by hand at the root; +0.114 by hand and +0.106 by the model outboard of the root zone).

## As built (2026-11-20)

- `lib/qualification-materials.ts`, `lib/curated-materials.ts` (`materialDatasets`, `CitedMaterial.strengthBasis`), `scripts/export-material-library.ts`, the exported `material-library.json`; `tests/curated-materials.test.ts`.
- `library.strength_dataset`; `WingMaterial.strength_basis` and its sources; `wing_material` and `wing_report["material"]`; `examples/wing_calculator.py` prints the strengths with their basis and page.
- `check_report["strength_basis"]`; the fixture `tests/fixtures/wing/example-check.json` written again from the example.
- `scripts/wing-choices.py` lists each material's bases; the Material step's Strengths choice and table; the verdict and the check's headline name the basis.

## Why (evidence)

- `cd engine && uv run pytest`: 691 passed, among them the example's strengths equal to the dataset's, each below its mean, with pages 35, 46 and 50, and the refusals (2026-11-20).
- `npx tsx --test tests/curated-materials.test.ts tests/material-library-export.test.ts tests/wing.test.ts`: passed; the browser test of the strengths in `tests/browser/wing.spec.ts` passed on Chromium.
- The example at 3000 N: −0.047 on B-basis, +0.097 on means, the same ply (upper skin, 0° ply, longitudinal compression, case 6). The B-estimate of F1c is 13 % below its mean.
- Values read from Table 3-1 (p. 35), Table 3-3 (p. 37), Table 4-3 (p. 42), Table 4-4 (p. 44), Table 4-6 (p. 46), Table 4-8 (p. 48), Table 4-10 (p. 50) and Table 4-12 (p. 52) of NCP-RP-2009-028 Rev B, in a text copy of the report; the column order of Table 3-1 was confirmed against Table 3-3's labelled rows.

## Consequences

- Every margin of the example and of any wing that asks for B-basis is lower; the example's own numbers in earlier lessons and records are on means at 3000 N.
- Two of the five strengths are estimates that do not meet CMH-17-1G's requirements for publication; the page says so beside them.
- Hot wet strengths are lower for the matrix-dominated properties (Table 3-1 gives elevated wet values), and a wing should be checked there too: not built.
- Only IM7/8552 has B-basis strengths; another material offers its means, labelled as not design values.

## How we will know it was wrong

- The founder or a class asks for the stricter 0.2 % offset shear strength, or for no estimates: then the choice of F6 and F1c becomes a key of the wing file.
- A wing's governing check is a matrix-dominated one in service at elevated temperature: then the hot wet column is needed before its margins are trusted.
