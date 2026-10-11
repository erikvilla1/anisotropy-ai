# Anisotropy engine

Python laminate analysis. It has no web or database code, so it can be tested on its own and called from the API, scripts or notebooks.

## Run the tests

Requires [uv](https://docs.astral.sh/uv/).

```sh
cd engine
uv sync
uv run pytest
```

## Conventions

- SI base units everywhere: Pa, m, N, N/m. Conversion to MPa, GPa, ksi or Msi happens only for display.
- Axis 1 is the fiber direction and axis 2 is transverse in-plane.
- Shear strain is engineering shear: gamma12 = 2 * epsilon12.
- Ply angle theta is in degrees, positive counterclockwise from laminate axis x to fiber axis 1.
- Plies are listed from the bottom face up. z is measured from the mid-plane, positive upward, so the first ply starts at z = -h/2.
- Compressive strengths are entered as positive magnitudes.
- Strength ratio R is the factor on all applied loads at which a criterion predicts failure (Daniel & Ishai's safety factor S_f). Margin of safety is MS = R / FS - 1 for a required factor of safety FS.
- First-ply failure is the onset of damage in one ply, not the ultimate strength of the laminate. Residual thermal stress and any loads held fixed stay constant while the remaining loads scale (Daniel & Ishai Section 9.8).
- Invalid input raises an error. The engine never substitutes a default value; the Tsai-Wu interaction term `f12_star` must be given explicitly.
- Unknown material, strength, ply and load fields are rejected. Stress, strain and curvature vectors need three finite components. Safety factors must be finite and at least one; an unstressed ply can still have an infinite strength ratio.

## Modules

The equations behind each module, and the function that computes each one, are in [docs/theory.md](docs/theory.md).

| Module | Contents |
| --- | --- |
| `lamina.py` | Ply elastic constants, optional `Strengths` and `ThermalExpansion` (`Lamina`), and the plane-stress stiffness `Q` and compliance `S` |
| `rotation.py` | Stress and strain transformations, and the rotated ply stiffness `Q_bar` and compliance `S_bar` |
| `laminate.py` | Ply stack (`Ply`), ply interface heights and the laminate `A`, `B`, `D` matrices |
| `response.py` | Applied `Loads`, the inverted ABD blocks a, b, d, the full ABD response, required moments for prescribed curvature with a forward check, and ply surface stress/strain |
| `failure.py` | Maximum-stress and Tsai-Wu strength ratios, margin of safety, and first-ply failure of a laminate, also with fixed loads and residual thermal stress |
| `mixed.py` | Mixed conditions: one known load or deformation per pair, the rest solved and verified |
| `thermal.py` | Rotated expansion coefficients, thermal force and moment resultants, the response to loads plus a temperature change, and residual ply stresses |
| `engineering.py` | Effective laminate constants Ex, Ey, Gxy, Poisson ratios and shear coupling, the moduli a D3039 test measures |
| `units.py` | SI, US (Msi, ksi) and psi unit systems for entering and reporting values |
| `buckling.py` | Buckling of a simply supported symmetric laminated plate: Navier closed form for specially orthotropic laminates, Ritz double sine series otherwise (ADR-0022) |
| `library.py` | Loads a cited dataset of the website's material library (`data/material-library.json`) as a `Lamina` in SI with the page of every value used (ADR-0020) |
| `cases.py` | Reads cases (one material, or several named materials per ply), solves them with `solve_case`, and compares expected values with engine results |
| `course_excel.py` | Reads the course Excel input template into a case |

For a one-page guide to writing a case and reading the printout, see [docs/engine-cheat-sheet.md](../docs/engine-cheat-sheet.md).

## Validation and examples

- `validation/cases/` holds solved problems from textbooks and answer keys; `tests/test_validation_cases.py` checks the engine against all of them. See [validation/README.md](validation/README.md).
- `examples/laminate_calculator.py` prints every intermediate result from a TOML case, for checking hand or homework answers. Without an argument it runs the unchanged Problem 7.11 reference case.
- `examples/coupon_check.py` summarizes stiffness, ply stresses and first-ply failure for a tension coupon.

Run either example with `uv run python examples/<name>.py`.

The calculator also reads the course Excel input template, including several materials and ply thicknesses: `uv run python examples/laminate_calculator.py path/to/HW4_P4b.Input.xlsx`. When a TOML case has `[expected]` answers, the calculator ends with an "Answer key vs engine" table.

For another problem: `uv run python examples/laminate_calculator.py validation/cases/as4-zero-degree-axial-check.toml`. Put personal cases and original homework files in the repository's ignored `.local/` directory. See [the case format](validation/README.md).

Input scales are explicit: `SI` means GPa, MPa and mm; `US` means Msi, ksi and inches; `psi` means psi and inches. For 140 GPa, enter `E1 = 140` with `units = "SI"`, not `140e9`. Conversion to Pa happens inside the calculator. Moduli outside the example's existing 0.5-1000 GPa plausibility screen now stop the calculator; `--allow-unusual-moduli` explicitly overrides that screen after review. This screen is not a physical validity criterion or an engine restriction.

For a temperature change, give `alpha1` and `alpha2` in `[material]` and `delta_T` in `[applied]`, for example `uv run python examples/laminate_calculator.py validation/cases/course-reader-5-9-as4-curing.toml`. The calculator then prints the thermal resultants and free thermal strains, and ply stresses include the residual thermal stress. Without `delta_T` it states that no temperature change was given.

Failure checks always include maximum stress when all five strengths are supplied. A temperature change stays fixed while the mechanical loads scale; a `[failure]` table holds chosen loads fixed as well. Tsai-Wu also requires `f12_star` in the case file; it is skipped when the assumption is absent.

For required moments under a curvature constraint, run `uv run python examples/laminate_calculator.py validation/cases/constructed-flat-cross-ply.toml`. The new `forces_curvature` case mode accepts known force resultants and prescribed curvature; zero curvature requests flatness. See the [chunk 3 walkthrough](../docs/walkthroughs/chunk-3-constrained-analysis.md) for the matching API operation and numerical verification policy.
