# ADR-0087: Optional physics is a condition the engineer calls up; the first is a temperature change in the laminate calculator, which alone grows itself to failure

- Status: Proposed
- Date: 2026-11-10
- Decided by: Founder, 2026-11-10 ("if the user request, 'there is temperature change' on the structure then it gives the option to the user to add temperature change"; the plan of that day, part 5, approved; asked why temperature comes first, then "ok sounds good continue") | Drafted by: Claude Code
- Related: `lib/conditions.ts`, `lib/laminate-chat.ts` (`readTemperature`, the `temperature` step), `components/workspace/laminate-rail.tsx`, `components/studio/laminate-chat.tsx`, `components/workspace/panels/laminate-fields.tsx` (`TemperatureFields`), `api/src/anisotropy_api/laminate_problems.py`, `engine/src/anisotropy_engine/failure.py` (`first_ply_failure_thermal`), `engine/src/anisotropy_engine/cases.py` (`thermal_only`), `engine/src/anisotropy_engine/units.py`, [ADR-0014](ADR-0014-explicit-temperature-change.md), [ADR-0017](ADR-0017-failure-with-fixed-and-variable-loads.md), [ADR-0060](ADR-0060-the-chat-solves-laminate-problems-through-the-case-solver-with-every-value-in-its-own-unit.md), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md)
- Area: engine

## Context

The founder wants the page to offer an input only when the engineer asks for it: say "there is a temperature change" and a temperature panel appears, as in PhysicsX. The workspaces' panels were fixed, filtered only by the test, the material kind and the standard.

The engine has handled a uniform temperature change since ADR-0014:
- the thermal resultants and the residual ply stress;
- failure with the change held while loads grow (ADR-0017);
- `POST /v1/cases/solve` takes `applied.delta_T`.

The laminate calculator and its chat could not state a change. Its typed-unit table had no temperature or expansion units. A change with no load gave no first-ply-failure answer at all: nothing mechanical scales, and `cases.failure_loads` returned none.

## Options considered

How the page offers optional physics:

1. **A condition the engineer calls up** (chosen). It comes from a word in the chat, from an "Add a condition" menu on the panels, or with a value typed in a message; it is never shown before. The panels stay short for the problems that do not need it.
2. Every optional row always shown. Rejected: every engineer would read rows most problems never use.
3. The model alone decides what to show. Deferred to part 6, where the model proposes and the engineer confirms; words come first, and they need no model.

Which condition first:

1. **A temperature change, in the laminate calculator** (chosen). It is the founder's own example, and the engine computes it already. The coupon's temperature change needs the finite element path (parts 7 to 9).
2. Turning the coupon's existing optional rows (bonded tabs, the strain measurement) into conditions. Rejected for now: it changes the setup's flow and the standards' requirements, for no physics the engineer lacks today.

A temperature change with no load:

1. **R scales the change itself** (chosen). With no load the laminate is free, and every ply's stress is the residual stress of the change, proportional to it. So the strength ratio of that stress is the factor on the change, and the first ply fails at R times the change.
2. No answer, as before. Rejected: "cooled 150 °C after cure, does it crack?" is a question engineers ask.

## Decision

- **Conditions.** `lib/conditions.ts` lists each condition: its id, title, detail, product, the words that call it up, and its panel.
  - The laminate draft keeps the conditions that are on, and a project saved before reads as none on.
  - A condition's step is asked only once it is on.
  - The rail shows its panel only when it is on. "Add a condition" offers those that are off, and the panel can remove it.
  - In the chat, words that name a condition without a value offer it with a button and open nothing. A value turns it on with the value, echoed back.
- **The temperature condition (laminate).**
  - The rows are the temperature change, in °C, K or °F, and, for a typed material, both expansion coefficients alpha1 and alpha2, in 1/°C, 1/K, 1/°F or their 1e-6 forms. A library dataset brings its own, and the engine's refusal says when it records none.
  - The chat reads "cooled by 150 °C", "a drop of 120 deg C", "delta T = -270 °F", "alpha1 = -0.9e-6 /°C" and "alpha2 27 x10^-6 per °C". Cooling and a drop are negative.
  - The problem sends `delta_T` and the material's `alpha1` and `alpha2`, each with its unit (amends ADR-0060).
- **The engine.**
  - `first_ply_failure_thermal`, used by the case solver when a case has a change and no load: R is the factor on the change, and each check's stress is the stress at failure.
  - A laminate whose plies all expand alike is unstressed and is refused.
  - The results add `fpf_delta_T_<criterion>`, R times the change in the case's units.
  - With a load, the change stays held (ADR-0017).
  - The typed-unit table gains temperature-change and expansion units (degC, K, degF; 1/degC, 1/K, 1/degF and the 1e-6 forms), always a change and never a temperature, with no offset.
- **The answer's words.** "By Tsai-Wu, ply 2 fails first ... when the temperature change reaches 1.93 times its value: -231.5 degC", or, with loads, "The temperature change of -120 degC is held at its value while the loads grow." The results table shows "Temperature change at failure".

## As built (2026-11-10)

- **Engine:**
  - `failure.first_ply_failure_thermal`, `cases.thermal_only`, the `fpf_delta_T_*` results;
  - the units table, and `data/units.json` written from it;
  - theory section 7, with its marker;
  - a constructed validation case, `constructed-cross-ply-cooling-alone-first-ply-failure`, with its closed form in `engine/validation/closed_forms.py`;
  - a physics card, "First-ply failure under the change alone" (42 cards).
- **API:** `LaminateProblem.delta_T`, `OwnMaterial.alpha1`/`alpha2` (both or neither), `case_of`, and the facts and sentences.
- **Page:** `lib/conditions.ts`; the draft's `conditions`, `delta_T` and `alphas`; `readTemperature`; the `temperature` step; `TemperatureFields`; the rail's menu and panel; the chat's offer; the results' column; °C, °F and 1e-6/°C printed.
- **Not built here:** the coupon's temperature condition (parts 7 to 9), and the model proposing conditions (part 6).

## Why (evidence)

- **The constructed case.** An AS4/3501-6 [0/90]s, cooled 120 °C, carries 29.006 MPa of transverse tension in every ply. Maximum stress gives R = 57 / 29.006 = 1.965, so the first ply fails at a cooling of 235.8 °C. The closed form and the engine agree: `engine/tests/test_constructed_references.py` and `test_validation_cases.py`.
- **Engine tests** (`engine/tests/test_thermal.py`):
  - `test_a_temperature_change_alone_fails_its_first_ply_at_r_times_the_change`
  - `test_a_temperature_change_alone_is_refused_when_zero_or_when_it_stresses_nothing`
  - `test_a_case_cooled_with_no_load_reports_the_temperature_at_failure`
- **API tests** (`api/tests/test_laminate_problems.py`):
  - the case runner agrees;
  - °F is the same change;
  - with a load, the change is held;
  - half an expansion, or one of the wrong dimension, is refused;
  - a change needs the material's expansion;
  - the guard passes on the new sentences.
- **Page tests:**
  - `tests/laminate-chat.test.ts`: the readers, the step, the problem, the words;
  - the browser scenario "a temperature change named in the laminate chat ...".

## Consequences

- **Easier:** an engineer asks about cooling after cure in their own words and gets the panel, the values read, and the temperature at which the first ply cracks. The next condition reuses the registry, the menu and the offer.
- **Harder:** the laminate draft carries optional fields every reader must treat as possibly absent.
- **We now depend on** the words of each condition being specific enough not to call it up by accident.

## How we will know it was wrong

- Engineers miss a panel they need because no word called it up, or are offered one they did not mean.
- A coupon's temperature change, once built (part 8), answers differently from the laminate's on the same laminate.
