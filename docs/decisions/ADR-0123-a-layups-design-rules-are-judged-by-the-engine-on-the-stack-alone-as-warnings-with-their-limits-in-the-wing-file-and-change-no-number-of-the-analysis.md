# ADR-0123: A layup's design rules are judged by the engine on the stack alone, as warnings, with their limits in the wing file, and change no number of the analysis

- Status: Proposed
- Date: 2026-11-20
- Decided by: Founder, 2026-11-19 ("Plan order: project, rules, caps, chat", his choice on the order of the wing chat's plan, whose second step is this; the rules and their default limits are the plan's, and the limits stay open until he sets others) | Drafted by: Claude Code
- Related: [ADR-0059](ADR-0059-the-engine-describes-the-stack-and-evaluates-first-ply-failure-on-the-response-endpoint-for-the-home-calculator.md), [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0118](ADR-0118-the-wing-workspace-works-the-engines-hand-calculation-through-the-api-on-every-settled-change-draws-what-the-engine-returns-and-keeps-the-wing-as-its-wing-file.md), [ADR-0122](ADR-0122-a-wing-is-a-project-of-its-own-kind-kept-like-a-coupon-or-a-laminate-with-its-versions-in-the-browser.md), `engine/src/anisotropy_engine/layup_rules.py`, `engine/src/anisotropy_engine/wing/wing_file.py`, `components/workspace/wing-rail.tsx`
- Area: engine, website

## Context

The founder asked on 2026-11-19 that the wing's chat answer questions about the wing being analysed with design rules in hand, naming the 10 % rule and the most plies of one angle in a row among them. Nothing in the repository judged a stack by such rules: `summary.py` states whether a stack is symmetric and balanced (ADR-0059), and nothing else. The wing chat's plan (its step 2) puts the rules in the engine before the chat, so a chat answer, the page and a tool all read one judgment by lookup and never by a search over text. The example wing's skin is $`[0/45/-45/0]_s`$ about a core, its spar web $`[45/-45/0/0]_s`$ and its ribs $`[45/-45]_s`$; none has a 90° ply.

## Options considered

1. **Where a rule is judged.**
   - (a) In the engine, on the stack: `anisotropy_engine.layup_rules`, one result per rule with whether it is met, one plain sentence, its source and the numbers behind it; the wing's report lists them for every layup. Chosen: the page, the chat and the tools of the later steps read the same judgment.
   - (b) In the page. Rejected: the chat and the tools would need a copy of their own.
   - (c) As text in the reference pages, for a language model to apply. Rejected: a limit and its judgment are values, which come by lookup, never by search (the wing chat's plan).
2. **Which rules now.**
   - (a) Four on one stack: the 10 % rule, plies of one angle in a row, balance and symmetry. Chosen: each needs only the stack.
   - (b) The ply drop rules (taper ratio, plies dropped per step, plies covering a drop). Later, with the zones along the span of step 3: a wing's stack does not change along the span yet.
   - (c) A largest angle between neighbouring plies. Left out: the plan named 60°, one secondary source names 45°, and no primary source was read.
   - (d) ±45° plies on the outside. Left out: no primary source was read.
3. **A rule not met.**
   - (a) A warning: the Layup panel shows "warning", and no margin, verdict or other number changes. Chosen: these are rules of practice, which a designer may set aside with a reason (a rib of ±45° plies carries shear only).
   - (b) A failure of the wing. Rejected: a wing that passes every flight case would read as failed.
4. **The limits.**
   - (a) The least share of each direction, 10 %, and the most plies of one angle in a row, 4, each set per wing by an optional `[design_rules]` table (`min_percent`, `max_in_a_row`) and the Layup panel; left out, the defaults. Chosen: thicker plies call for fewer in a row, and the founder may set his own.
   - (b) Fixed limits. Rejected for the reason above.
5. **What is counted.**
   - (a) Plies by count, a fiber at θ the fiber at θ + 180°; a run counts across the middle of a solid laminate and not across a core; balance and symmetry are `summary.py`'s facts, so material and thickness count there too. Chosen: the rules are stated by ply count, and balance and symmetry stay one definition in the engine.
   - (b) Plies weighed by thickness. Rejected: not how the rules are stated.

## Decision

Options 1(a), 2(a), 3(a), 4(a) and 5(a). `layup_rules(plies, limits, core_after)` judges the four rules on a stack listed from one face to the other; `Layup.rules` gives a wing layup's, both halves with the core between them. `Wing.design_rules` holds the limits (`RuleLimits`: `min_share` above 0 and at most 0.25, `max_in_a_row` a whole number of at least 1). `wing_report` adds `rule_limits` and `rules`, one entry per rule of the skin, the spar web and the rib, each with `part`, `rule`, `met`, `words`, `source` and `detail`. The wing page shows them under each layup, the Layup step's badge a warning while one is not met ("3 design rules not met") and "rules met" when none is, and the two limits in a Design rules box of the same step.

## As built (2026-11-20)

- `engine/src/anisotropy_engine/layup_rules.py`: `RuleLimits`, `RuleCheck`, `ten_percent_rule`, `in_a_row_rule`, `balance_rule`, `symmetry_rule`, `layup_rules`, `angle_words`; `engine/docs/theory.md` section 14; the module joins the manual's engine modules (`docs/manual/build.py`).
- `Layup.rules` and `Wing.design_rules` in `engine/src/anisotropy_engine/wing/description.py`; `[design_rules]`, `wing_rules` and the report's `rule_limits` and `rules` in `engine/src/anisotropy_engine/wing/wing_file.py`; `tests/fixtures/wing/example-answer.json` written again by `scripts/wing-choices.py`.
- `DESIGN_RULE_FIELDS`, `WingRule`, `RULE_NAMES` and `ruleTitle` in `lib/wing.ts`; the limits' labels in a version's changes (`lib/wing-versions.ts`); `LayupRules` and the Layup step's badge in `components/workspace/wing-rail.tsx`; `.wing-rules` in `app/workspace/workspace.css`.
- The example wing: every layup misses the 10 % rule (no 90° ply; the ribs no 0° ply either) and meets the other three; its spar web has four 0° plies in a row across the middle, the default limit.

## Why (evidence)

- The 10 % rule: MIL-HDBK-17-3F, Volume 3 (17 June 2002), a public-domain handbook, states that a laminate should be fiber-dominated, with at least 10 % of its plies in each of 0°, +45°, -45° and 90°. Seen in a web search's excerpt of a public copy, 2026-11-20; its section and page were not read here (the copy could not be fetched from this machine): UNVERIFIED.
- Plies of one angle in a row: a DLR report on design rules (DLR-IB-FA-BS-2016-173, elib.dlr.de/107894) gives no more than 4 plies of one angle together for 0.127 mm plies and fewer for thicker plies, seen in a search excerpt, 2026-11-20. Whether the handbook states a number was not checked: UNVERIFIED.
- Balance and symmetry: $`A_{16} = A_{26} = 0`$ for a balanced stack and $`\mathbf{B} = 0`$ for a symmetric one (Daniel and Ishai, Sections 7.7 and 7.8, as `summary.py` cites them).
- `cd engine && uv run pytest -q tests/test_layup_rules.py tests/test_wing.py tests/test_wing_validation.py`: 90 passed, 2026-11-20. The rule tests count stacks by hand, among them one 90° ply in twelve (8.3 %) short of 10 % and one in ten meeting it, four 0° plies across the middle of $`[\pm 45/0_2]_s`$, the same run broken by a core, unpaired +45° plies, partners of another thickness and a core off the middle; the example wing with other limits gives every case, margin and design number unchanged.
- `cd api && uv run pytest -q tests/test_wings_api.py tests/test_wing_checks_api.py`: 29 passed (the answer fixture with the rules). `npx tsx --test tests/wing.test.ts tests/wing-versions.test.ts`: 8 passed. `npx playwright test --config playwright.studio.config.ts wing.spec.ts` (Chromium): 11 passed, the new spec included: the rules under each layup, the Layup step's warning, a limit typed going with the wing, and "rules met".

## Consequences

- The chat of step 5 can say which rule a layup misses and why, from the wing's answer, and the same sentence shows on the page.
- The example wing shows a warning on its Layup step until its layups get 90° plies or the limit changes; nothing else about it changes.
- The rules read the stack alone. Ply drops wait for zones along the span (step 3), and their rules with them.
- Two sources are not yet read at their section and page. The reference pages of step 4 must read them, and correct a source line here if it differs.

## How we will know it was wrong

- The founder, or a professor using it in a class, gives other rules or limits than these: then the defaults or the rules change.
- People read a warning as a failed wing.
- The handbook, once read at its section, words a rule differently (for example ±45° counted together): then the rule follows it.
