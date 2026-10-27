# ADR-0034: Lamina constants from fiber and matrix use the rule of mixtures, the series models, Halpin-Tsai and the square-array combination model, each named by the caller

- Status: Accepted
- Date: 2026-10-19
- Decided by: Founder, accepted 2026-10-26 ("FEA method (7)", choosing which groups of the proposed records to accept) | Drafted by: Claude Code
- Related: ADR-0003 (no silent defaults), ADR-0007 (validation cases), ADR-0019 (theory with code markers and website cards), `engine/src/anisotropy_engine/micromechanics.py`, `engine/docs/theory.md` section 9, `engine/tests/test_micromechanics.py`, the course's two cases (local, ADR-0042), `constructed-micromechanics-eglass-epoxy-halpin-tsai`

## Context

Every engine calculation started from given lamina constants. A course problem asks for the lamina constants of a carbon/epoxy from the fiber and matrix constants at two fiber volume ratios with the course's "hybrid Voigt-Reuss" model, and an engineer asking what the engine covers would find micromechanics missing. The founder asked on 2026-10-19 to model it. Daniel and Ishai chapter 3 (2nd ed., 2006, pp. 46-57) gives the mechanics-of-materials models, the Halpin-Tsai interpolation and the combined series-parallel model, and Appendix Tables A.2 and A.3 (pp. 375-376) give the fiber and matrix constants. The course's Lecture Pack 2, which defines its model and tables, is not in the repository.

## Options considered

1. Implement the standard models and make the caller name them: the rule of mixtures for E1 and nu12 (the only model in common use for them), and for E2 and G12 a choice among the series model, the series model with the constrained matrix modulus (E2 only), Halpin-Tsai with a stated xi, and the combined series-parallel model for a square array. Pro: a case records exactly what produced its numbers; the course key can be matched by naming a model; new models slot in by name. Con: more inputs for the user.
2. One default model (Halpin-Tsai with xi = 1 for E2 and G12). Rejected: a silent default (ADR-0003), and the course key does not match it.
3. Only the rule of mixtures and the series models. Rejected: Daniel and Ishai show the series model far below measured E2 and G12, and Halpin-Tsai is what the field uses.

## Decision

Option 1. `micromechanics.py` holds `Fiber` (transversely isotropic), `Matrix` (isotropic, shear modulus derived), the model functions and `lamina_from_constituents`, which refuses an unnamed model, a Halpin-Tsai model without xi, an xi given for another model, and a volume ratio outside (0, 1). A case states a material as `fiber`, `matrix`, `Vf`, `E2_model`, `G12_model` and the xi values, and may add measured strengths and expansion coefficients; the results `E1, E2, G12, nu12, nu21` join the compared keys. The square-array closed form is this repository's derivation from the book's Eqs. 3.33-3.34, labelled so in the theory. Strengths and expansion coefficients are not predicted.

## Why (evidence)

- The course key (two cases): with the Table A.2 and A.3 constants, the rule of mixtures for E1 and nu12, the series model for G12 and the constrained series model for E2 agree with it at both fiber volume ratios, within the tolerance the key's two to three significant figures allow; the plain series model for E2 and the combination model do not. The cases are local since ADR-0042 and the numbers are in a local note (ADR-0042). Which of these the course calls hybrid Voigt-Reuss is UNVERIFIED until its lecture notes are on hand.
- Hand check: `constructed-micromechanics-eglass-epoxy-halpin-tsai` reproduces five-figure values computed by hand from the equations (first hand value for G12 was wrong by 0.1 % and corrected after the engine disagreed; the second computation agreed with the engine).
- `test_micromechanics.py`: every model lies between the series and parallel bounds; Halpin-Tsai with xi = 0 is the series model, with large xi the parallel one, and with xi = 1 equals the book's closed form Eq. 3.37; every model returns the constituent at Vf near 0 and 1; the refusals by name.

## Consequences

Easier: a problem that starts from constituents is one case file; the website cards for these estimates now name the engine functions. Harder: a user must choose and justify a model; the course's own model stays unidentified until its lecture notes are available. We now carry a derived closed form (square-array combination) that no source prints; its test is the derivation itself.

## How we will know it was wrong

Lecture Pack 2 names a model whose numbers differ from the constrained series model by more than the key's rounding, or a measured lamina record in the library disagrees with every offered model by a margin the reading cannot explain.
