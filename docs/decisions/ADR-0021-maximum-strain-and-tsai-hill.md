# ADR-0021: Maximum strain and Tsai-Hill join the failure criteria; strain limits are explicit or derived only by a stated choice

- Status: Proposed
- Date: 2026-10-11
- Decided by: Erik Villa (founder) | Drafted by: Claude Code
- Related: `engine/src/anisotropy_engine/failure.py`, `engine/src/anisotropy_engine/lamina.py`, `engine/src/anisotropy_engine/cases.py`, `engine/tests/test_failure_criteria.py`, `engine/validation/cases/constructed-max-strain-biaxial-lamina.toml`, `engine/validation/cases/daniel-ishai-sample-problem-6-1-tsai-hill.toml`, [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0017](ADR-0017-failure-with-fixed-and-variable-loads.md)

## Context

The engine had maximum stress and Tsai-Wu. The founder's course states failure strain allowables as strength divided by modulus and uses the maximum strain criterion; the course formula sheet also defines maximum stress and maximum strain failure indices. Tsai-Hill is on the website's physics page and in every textbook the team uses. Neither was implemented, so course and textbook strength problems could not be checked.

## Options considered

For the strain limits:

1. Always derive the five limits from strengths and moduli. Simple, but it silently assumes linear behavior to failure, which is wrong for shear in most composites and contradicts ADR-0003.
2. Accept only measured strain limits. Honest, but no library dataset holds a complete set, and the course problems would be unanswerable.
3. Accept explicit limits, and derive them from strengths only when the case states `strain_limits = "from-strengths"`. The assumption is recorded in the case and printed with the result.

For Tsai-Hill with mixed-sign stresses:

1. One fixed pair of strengths. Simple and wrong for compression.
2. Select X by the sign of sigma1 and Y by the sign of sigma2, as Daniel and Ishai Eq. 6.16 is applied in the textbook and on the physics card. With fixed and variable loads the signs at failure are unknown in advance, so solve the quadratic for each sign choice and keep the roots consistent with their assumption.

## Decision

Option 3 for strain limits and option 2 for Tsai-Hill. Both criteria run through the same fixed-plus-variable machinery as maximum stress and Tsai-Wu (ADR-0017). Maximum strain uses the mechanical strain in fiber axes, the strain the stresses produce, so a temperature change's free strain is excluded. The case runner runs every criterion whose inputs exist and reports each under its own key.

## Why (evidence)

- `constructed-max-strain-biaxial-lamina.toml`: a 0° ply under sigma1 = 1000 MPa and sigma2 = 20 MPa gives R = 2.28 by maximum stress and 2.2924 by maximum strain, the closed-form F1t/(sigma1 − nu12sigma2); Tsai-Hill gives 1.7913 from Eq. 6.16 by hand.
- `daniel-ishai-sample-problem-6-1-tsai-hill.toml`: the book's 45° shear strength by Tsai-Hill, 1/sqrt(2/F1t^2 + 1/F2c^2) = 225.75 MPa, next to the existing maximum-stress case (228 MPa).
- `test_failure_criteria.py`: the combined Tsai-Hill root agrees with an independent bisection on the index for four paths including two where a stress changes sign; maximum strain reduces to maximum stress for uniaxial fiber stress and differs by the Poisson term otherwise; a case with half a set of limits, a misspelled policy, or the policy without strengths is rejected.
- The course answer key for Homework 5 was reproduced by maximum stress (25 of 25 values); the maximum strain value for the same problem is not in the key, so it is not claimed.

## Consequences

Easier: course and textbook strength problems in all four criteria; the course's strain allowables are one line in a case. Harder: a case must say where its strain limits come from, and a reader must know that the two interactive criteria report the strength ratio, not the failure index. Hashin remains deferred.

## How we will know it was wrong

A course or textbook answer by maximum strain that the engine misses by more than the key's rounding, or a measured strain-limit dataset that the `from-strengths` choice contradicts badly enough that the choice should be withdrawn from the template.
