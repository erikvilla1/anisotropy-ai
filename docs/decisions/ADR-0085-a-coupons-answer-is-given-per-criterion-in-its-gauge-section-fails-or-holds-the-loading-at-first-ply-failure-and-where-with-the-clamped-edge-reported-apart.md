# ADR-0085: A coupon's answer is given per criterion in its gauge section: fails or holds, the loading at first-ply failure and where, with the clamped edge reported apart

- Status: Proposed
- Date: 2026-11-10
- Decided by: Founder, 2026-11-10 ("the analysis of the specimen is given everything important such as max stress, where it will fail if it will fail ... if it doesn't fail how what is the load factor that causes the failure and where"; the plan of that day, PR 1, approved) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/fields.py` (`answer_of`, `verdict_of`, `ply_extremes`), `fea/src/anisotropy_fea/explain.py`, `fea/docs/theory.md` (section 7), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md), [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md), [ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md)
- Area: fea

## Context

The kernel already computes, per criterion, the strength ratio of every ply of every element, the first-ply-failure factor over the whole model (`summary.fpf`) and over the gauge section (`summary.fpf_gauge`), with the ply, mode, element, place and position. A result did not say plainly what an engineer asks: does a ply fail at the loading I applied, and if not, at what loading and where. The explanation and the viewer read the whole model, whose first failure on a gripped coupon is usually at the clamped edge of a tab, a stress that grows as the mesh is refined (ADR-0066), not the gauge section a test coupon is accepted on. The largest ply stresses were the largest magnitudes over the whole model, tension and compression not apart.

## Options considered

Where the answer is read:

1. **The gauge section when the coupon has one, the whole model otherwise; an earlier failure outside it reported apart** (chosen). The gauge section is what a test coupon breaks in; the clamped edge is a modelling singularity that still deserves a word.
2. The whole model. Rejected: on a gripped coupon it answers with the clamped edge, which moves with the mesh.
3. Both as equals. Rejected: two answers to one question.

When a ply "fails":

1. **At a factor at or below one** (chosen): the failure index 1/R has reached one at the applied loading.
2. Below one only. Rejected: a failure index of exactly one meets the criterion.

The loading at failure:

1. **The factor times the applied value and times the reaction** (chosen): a linear model scales every quantity with the loading, the same reading `recovery.strength_ratios` already gives the factor.
2. A second solve at the failure loading. Rejected: the same numbers at twice the cost.

## Decision

- Every entry of `summary.fpf` and `summary.fpf_gauge` gains `fails` (factor at most one) and `at_failure` = {the factor times the applied value in its unit, the factor times the reaction in the force unit, and whether every load scales together, as on a plate}.
- `summary.verdict` = {basis "gauge" or "whole", the earliest criterion on that basis, its factor, whether it fails, and `outside_earlier`: the whole model's earliest failure when it comes before the gauge section's, with its place and whether it touches a grip}.
- `summary.ply_extremes`: over the same elements, each ply's sigma_1 and sigma_2 at their largest tension and largest compression apart, tau_12 and von Mises at their largest magnitude, each with element, centroid and face; and the same over every ply. A sign never reached is none. `max_ply` and `ply_peaks` stay as they are for the solver comparison (ADR-0066).
- The explanation's facts and sentences read the verdict's basis: by each criterion, the laminate fails or holds at the applied loading in the gauge section (or the whole model), the first ply to fail, its element and position, its place and mode, the factor and the loading at that factor; the earlier failure outside it in a sentence of its own; the largest ply stresses with their sign and position. Every number is a fact (ADR-0052).

## As built (2026-11-10)

- Part 1 (fea): `answer_of`, `verdict_of` and `ply_extremes` in `fields.py`; the explanation in `explain.py`; fea theory section 7. The plan's `grip_earlier` is named `outside_earlier`, since an earlier failure outside the gauge section need not touch a grip; it says whether it does.
- Part 2 (page): the answer card under the viewer (`components/studio/results-view.tsx` `AnswerCard`, picked and labelled by `lib/studio-answer.ts` `answerOf` and `extremeRows`, which compute nothing): fails or holds by each criterion in the gauge section, R, the loading at first-ply failure, the ply and mode in words, the element and position, the clamped edge apart with its own show button, and the largest ply stresses with their sign. The viewer frames the answer's element and colours its criterion; the per-criterion tables of the whole model and the gauge section fold under it. An older job without the package's answer shows the tables as before.

## Why (evidence)

- `fea/tests/test_fields.py`: `test_each_criterion_says_whether_a_ply_fails_and_at_what_loading`, `test_the_answer_reads_the_gauge_section_and_reports_the_grip_edge_apart`, `test_the_largest_ply_stresses_come_with_their_sign_and_place`, `test_a_coupon_without_a_gauge_section_answers_on_the_whole_model`, and the sentences' facts in `test_every_number_in_a_sentence_is_a_fact` (a number inside a place is a fact, as the API's guard already reads it).
- The browser fixtures were written again by `studio_tool.py fixtures`.

## Consequences

- **Easier:** the page and the assistant can answer "does it fail, at what load, where" from one place; the clamped edge stops being read as the answer.
- **Harder:** the explanation's sentences changed wording; a reader of the old wording ("does not exceed") meets "holds".
- **We now depend on** the gauge set and grip detection of `gauge_elements` for the basis.

## How we will know it was wrong

- A test coupon breaks first at the grip while the answer, read in the gauge section, said it holds there at that load: the basis would then need the grip region too.
- An engineer reads `at_failure` as an ultimate strength. It is the onset of damage in one ply of a linear model.
