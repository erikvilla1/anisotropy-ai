# Evaluation: lamina constants from fiber and matrix (micromechanics, ADR-0034) | 2026-10-19

- Scope: `engine/src/anisotropy_engine/micromechanics.py` (Fiber, Matrix, the rule of mixtures, the series model, the constrained matrix modulus, Halpin-Tsai, the square-array combination model, `lamina_from_constituents`), the case format for a material stated by constituents and the results `E1, E2, G12, nu12, nu21` (`cases.py`), theory section 9 with code markers, three validation cases, `engine/tests/test_micromechanics.py`, Step 0 in the solved-problem documents, the manual's module list, the website's micromechanics cards naming the engine functions and the card test.
- Environment: Windows 11, uv 0.13, Python 3.12; `engine/uv.lock` and `fea/uv.lock` unchanged; Node 24 for the website tests.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job; the engine suite is included)

```text
676 passed in 71.95s (0:01:11)
```

(26 new: 23 in `test_micromechanics.py`, 3 validation cases in `test_validation_cases.py`; the theory-marker test paired every new marker with its sentence.)

From the root: `npm test` and `npm run typecheck`

```text
tests 71, pass 71, fail 0; typecheck clean
```

Validation cases (part of the suite above; the engine's values beside the source's):

| Case | Source value | Engine | Model |
| --- | --- | --- | --- |
| A course answer key, two cases (rule of mixtures, series model with the constrained matrix modulus) | local, ADR-0042 | agree within each case's tolerance | the numbers stay in a local note |
| E-glass/epoxy, Vf 0.55, Halpin-Tsai xi = 1: E1, nu12, E2, G12 | 42.085, 0.284, 12.524, 4.7091 (by hand) | agree to 0.05 % | rule of mixtures, Halpin-Tsai |

The constituent constants are Daniel and Ishai (2006) Table A.2 p. 375 and Table A.3 p. 376. The first hand value of the E-glass G12 (4.7147) was wrong by 0.1 %; recomputing by hand gave 4.7091, which the engine had given, and the case was corrected.

From the root: `uv run --project fea python docs/problems/build.py engine/validation/cases/constructed-micromechanics-eglass-epoxy-halpin-tsai.toml`

```text
4 numbers compared, 4 agree; Document written (Step 0 with the theory section, the listings and the numbers; read as rendered pages)
```

## Reading

- The homework key is reproduced by naming the models; the course's own model definition (Lecture Pack 2, "hybrid Voigt-Reuss") is not on hand, so the choice of the constrained series model for E2 is the one that fits, not one that was read from the course. The plain series model (7.97 GPa) and the combination model (9.60 GPa) do not fit.
- The models are bounded and limit-checked rather than validated against measurements; Daniel and Ishai's own comparison (Fig. 3.10) shows Halpin-Tsai with xi between 1 and 2 bracketing measured E2 of glass/epoxy, which is why xi is an input.

## Not run, and UNVERIFIED

- Not run: the manual PDF (its theory chapter gains section 9; CI builds it); the API suite (unchanged).
- UNVERIFIED: the course's model and tables (Lecture Pack 2); the square-array combination closed form is this repository's derivation and no source prints a number for it; strengths and expansion coefficients from constituents are not modeled.
