# ADR-0014: Thermal analysis uses separate functions and an explicit temperature change

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/thermal.py`, `engine/tests/test_thermal.py`, [evaluation](../evaluations/2026-10-03-thermal-analysis.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md)

## Context

Course Reader Problem 5.9 asks for curing stresses after a temperature change. The engine modeled mechanical loads only. Thermal analysis needs expansion coefficients, a temperature change, thermal resultants and a different ply stress equation. The mechanical functions already have many callers: the API, failure checks, cases, the calculator and the tests.

## Options considered

1. Add `delta_T=0.0` to `midplane_response` and `ply_surfaces`. Fewer functions, but every existing result would rest on a hidden "no temperature change" assumption, against ADR-0003.
2. Store alpha on each ply rather than on the material. Matches no current input; every ply in a stack already shares its material's other properties.
3. Store alpha as an optional `ThermalExpansion` group on `Lamina` (like `Strengths`), and put thermal analysis in separate functions that require `delta_T`.

## Decision

Option 3. `Lamina.thermal_expansion` holds `alpha1` and `alpha2` in 1/K, either of which may be negative. `thermal.py` provides `thermal_expansion_xy`, `thermal_resultants`, `thermomechanical_response` and `thermal_ply_surfaces`. Each requires a finite `delta_T` and rejects plies without coefficients. Mechanical functions are unchanged.

Case files give `alpha1` and `alpha2` in `[material]`, both or neither, and `delta_T` in `[applied]` next to exactly one mechanical entry. `delta_T` requires the coefficients. Without `delta_T` the case is a mechanical analysis, and the calculator prints that no temperature change was given. US and psi cases use degF: 1/degF converts to 9/5 per K, and a 1 degF change converts to 5/9 K. A change needs no offset.

Prescribed strains and curvatures report mechanical loads as total resultants minus the thermal ones. Failure ratios are not reported with a temperature change, because `first_ply_failure` scales all stress with the load and residual stress does not scale.

## Why (evidence)

- The engine reproduces 46 values from the Course Reader 5.9 answer key for two materials (two validation cases). The key's own printed equations match the engine's. Two printed key values contradict the key's other numbers and are not recorded; see the case files.
- `test_thermal.py` checks physics that does not depend on the ABD solve: a free single ply expands without stress; equal alpha1 and alpha2 leave any layup stress-free; a balanced cross-ply matches a closed form; an unsymmetric laminate warps but its integrated face stresses carry no net force or moment; thermal and mechanical responses superpose; and SI and US inputs agree.
- The 228 existing engine tests pass unchanged.
- The equations are Daniel and Ishai (2006) Chapter 8, checked against the founder's local copy: transformed expansion coefficients Eq. 8.11, ply stress Eq. 8.16, thermal force and moment resultants Eqs. 8.18 and 8.20, total load-deformation relation Eq. 8.25, and laminate expansion coefficients Eq. 8.33 (printed pp. 212-217). The engine omits the moisture terms.
- Accepted after further course validation (ADR-0015): seven thermal cases agree with their answer keys, covering curing stresses (Course Reader 5.9, two materials), an unsymmetric cure (5.13), laminate expansion coefficients (two layups), a hybrid woven/tape laminate under load and bending, and combined biaxial, bending and thermal loading.

## Consequences

Thermal results are available in the engine, the case format and the terminal calculator. The API and the website calculator do not accept a temperature change yet. Strength ratios with residual stress, moisture and temperature-dependent properties are not modeled. The comparison cannot judge an expected zero when every value in its group is rounding noise, so such zeros (for example M_T of a symmetric laminate) are not recorded in cases.

## How we will know it was wrong

Revisit if a problem needs a temperature that varies through the thickness, moisture, or a temperature change in a mechanical-only function's callers. The earlier trigger, alpha that differs between plies, occurred in the course's hybrid laminate (Homework 4 Problem 4). Per-material alpha (ADR-0015) handled it without changing this decision.
