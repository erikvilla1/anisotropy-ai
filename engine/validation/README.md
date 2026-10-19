# Validation cases

Each file in `cases/` is one solved problem: the inputs, and the answers from a source independent of this code (a textbook, an answer key, and later our own lab measurements). `tests/test_validation_cases.py` runs every case on each `uv run pytest`. A case fails when the engine and the source disagree by more than the case's tolerance.

Together these cases are the evidence that the engine gives the right numbers, and they show which kinds of problems it can already solve. Each case also has a generated document with every step, intermediate number and the source's answers: `uv run --project fea python docs/problems/build.py --all` from the repository root (`docs/problems/README.md`, ADR-0033).

## Add a case

1. Copy `cases/_template.toml` (one material) or `cases/_template-several-materials.toml` to a new file named after the problem, for example `homework-3-problem-2.toml`. Files starting with `_` are ignored.
2. Fill in `title`, `source` and `units`, then the material(s), plies and one `[applied]` entry.
3. Under `[expected]`, give only the values the source states, in the case's units. Set `tolerance` to suit how the source rounds: 0.001 (0.1%) for four significant figures, 0.005 for three.
4. Check it with the calculator, which ends with an "Answer key vs engine" table: `uv run python examples/laminate_calculator.py validation/cases/<file>.toml`.
5. Run `uv run pytest tests/test_validation_cases.py -v`.

## Course Excel input files

The calculator also reads the course's Excel input template directly: `uv run python examples/laminate_calculator.py path/to/HW_Input.xlsx`. It finds the units cell, the material table ("Matl ID", including alpha and strengths), the load row ("Nx" ... "Mxy", "DT", or "sigx" for an applied stress) and the ply table ("Ply No.", ply 1 at the bottom). The template enters compressive strengths as negative numbers; the reader stores them as positive magnitudes. Placeholder text such as "TBD", repeated ply numbers and missing thicknesses stop the calculator with a message instead of being guessed. Excel files have no `[expected]` answers; to compare with a key, write the case as TOML.

## One material or several

- **One material:** `[material]` with the elastic constants, and `[laminate]` with `layup` (angles, bottom first) and one `ply_thickness`.
- **Several materials or thicknesses:** a `[materials.<name>]` table for each material, and `[laminate]` with `plies`, a list of `{angle = ..., material = "<name>", thickness = ...}`, bottom ply first. See `se142-hw4-p4ab-hybrid-woven-thermal.toml`.

## Inputs and results

| `[applied]` key | Values |
| --- | --- |
| `loads` | Nx, Ny, Nxy, Mx, My, Mxy |
| `stress` | sigma_x, sigma_y, tau_xy averaged through the thickness |
| `strains` | eps_x, eps_y, gamma_xy, kappa_x, kappa_y, kappa_xy |
| `local_stress` | sigma_1, sigma_2, tau_12 (one angle and one material) |
| `local_strain` | eps_1, eps_2, gamma_12 (one angle and one material) |
| `forces_curvature` | Nx, Ny, Nxy, kappa_x, kappa_y, kappa_xy; calculate the required moments |
| `[applied.mixed]` | A table naming one known quantity per pair: `Nx` or `sigma_x` or `eps_x`; `Ny` or `sigma_y` or `eps_y`; `Nxy` or `tau_xy` or `gamma_xy`; `Mx` or `kappa_x`; `My` or `kappa_y`; `Mxy` or `kappa_xy`. The other quantity of each pair is solved |
| `delta_T` | Optional, next to one of the entries above: a uniform temperature change. Needs `alpha1` and `alpha2` in every material used |

| `[expected]` key | Meaning |
| --- | --- |
| `Q11`, `Q12`, `Q22`, `Q66`; `S11` ... `S66` | Ply stiffness and compliance in fiber axes (one material) |
| `Qbar11` ... `Qbar66`; `Sbar11` ... `Sbar66` | Ply stiffness and compliance in laminate axes (one material and one angle) |
| `A11` ... `A66`, `B..`, `D..` | Laminate stiffness entries (indices 1, 2, 6) |
| `a11` ... `a66`, `b..`, `d..` | Blocks of the inverted ABD matrix; the course reader calls them alpha, beta, delta. `b` is not symmetric: `b21` is row 2, column 1 |
| `strain_global`, `curvature` | Mid-plane strains and curvatures |
| `Nx` ... `Mxy`, `sigma_x`, `sigma_y`, `tau_xy`, `eps_x` ... `kappa_xy` | The same quantities one at a time, as answer keys state them: mechanical resultants, average stress N/h, mid-plane strains and curvatures |
| `moments` | Applied Mx, My, Mxy resultants, in the case's moment-per-width units |
| `strain_local`, `stress_global`, `stress_local` | Ply state, for one angle and material without bending |
| `ply_strain_global`, `ply_strain_local`, `ply_stress_global`, `ply_stress_local` | One [3-value] row per ply at mid-thickness, which is the ply's value when curvature is zero |
| the same keys ending `_bottom` or `_top` | One [3-value] row per ply on that face |
| `N_T`, `M_T` | Thermal force and moment resultants, when the case has `delta_T` |
| `Ex`, `Ey`, `Gxy`, `nu_xy`, `nu_yx` | Laminate engineering constants |
| `fpf_ratio_max_stress`, `fpf_ratio_max_strain`, `fpf_ratio_tsai_hill`, `fpf_ratio_tsai_wu` | First-ply-failure strength ratio R on the variable loads (maximum strain needs strain limits; Tsai-Wu needs `f12_star`) |
| `fpf_forces_...`, `fpf_moments_...` | Loads at first-ply failure, fixed + R * variable (suffix `max_stress`, `max_strain`, `tsai_hill` or `tsai_wu`) |
| `fpf_ply_...`, `fpf_z_...` | Ply number (1 at the bottom) and z of the face where the first ply fails |
| `buckling_factor`, `buckling_loads`, `buckling_mode`, `buckling_orthotropic_factor` | Plate buckling with `[plate]` and `[buckling]`: factor on the reference resultants, critical [Nx, Ny, Nxy], (m, n) half-waves for the closed form, and the orthotropic estimate beside a Ritz result |

Per-ply results can list every row, or only the plies an answer key reports, as a table keyed by ply number with ply 1 at the bottom:

```toml
[expected.ply_stress_local_top]
9 = [66040.0, 15970.0, -13320.0]
```

A case may add `[plate]` (`a`, `b` in the length unit, `edges = "simply-supported"`) and `[buckling]` (`loads = [Nx, Ny, Nxy]` reference resultants, compression negative, and `terms` for the Ritz series when the laminate has D16, D26 or the loads include shear) to get the plate buckling load (ADR-0022).

A `[material]` or `[materials.<name>]` table may name a library dataset instead of typing values: `library = "im7-8552"` with an optional `dataset = "..."`. The engine then takes E1, E2, G12, nu12, the strengths, the expansion coefficients and (for a one-material case) the ply thickness from the cited dataset, and the calculator prints the citation and page of every value (ADR-0020).

Shear strains are engineering shear. Layups are listed from the bottom face up. Units follow `src/anisotropy_engine/units.py`: compliances are in 1/GPa (`SI`), 1/Msi (`US`) or 1/psi (`psi`), so multiply a value in m^2/N by 1e9 for an `SI` case; `a`, `b` and `d` use the case's force and length units, for example in/lb, 1/lb and 1/(lb*in).

Case inputs reject unknown fields, partial strength sets and incomplete vectors. `loads`, `strains` and `forces_curvature` require all six components, including explicit zeros. Other applied vectors require three finite components. The calculator accepts this same format; `expected` is optional for calculation and required for an automated comparison. Tsai-Wu runs only when all strengths and an explicit `f12_star` are present. Maximum strain runs only when every material has strain limits: `eps1t`, `eps1c`, `eps2t`, `eps2c`, `gamma12` as positive fractions, or `strain_limits = "from-strengths"` to state the linear-to-failure assumption (strength divided by modulus, ADR-0021). Tsai-Hill runs whenever strengths are present.

`forces_curvature` converts the first three components as force/width and the last three as curvature; the moments are outputs, never zero-filled inputs. Its forward check must pass before results are returned. The two `constructed-*.toml` cases use independently evaluated scalar formulas with synthetic inputs. They check implementation, not experimental validity. The generic engineering constants still describe free bending (ADR-0005). Any failure ratio scales all solved force/moment resultants proportionally; it does not maintain a fixed nonzero curvature while increasing only the forces.

Mixed conditions: for example, a lamina between frictionless rigid walls is `eps_x = -0.01`, `eps_y = 0.0`, `tau_xy = 0.0`, `Mx = 0.0`, `My = 0.0`, `Mxy = 0.0`, and `sigma_x` is solved. Give every pair, including explicit zeros; see `se142-hw2-p2-cr-3-8-walls-30deg.toml` and `se142-hw4-p2-cr-5-13-unsymmetric-cure.toml`. Known loads are mechanical; `delta_T` adds the thermal resultants. Every solution must pass the forward check.

First-ply failure: by default every mechanical load scales with R, and a temperature change stays fixed (Daniel and Ishai Section 9.8). To hold some loads fixed, add a `[failure]` table with `fixed` and `variable`, six resultants each in the case's units; failure occurs at fixed + R * variable, and `delta_T` stays fixed. For example, Nx growing with Ny = 0.5 Nx while Mx = -4 stays fixed is `fixed = [0, 0, 0, -4, 0, 0]` and `variable = [1, 0.5, 0, 0, 0, 0]`, so R is Nx at failure. See `se142-hw5-p1-thermal-bending-laminate.toml`.

Thermal inputs: `alpha1` and `alpha2` are in 1/degC (`SI`) or 1/degF (`US`, `psi`), and `delta_T` is a change in degC or degF. Stresses then come from each ply's mechanical strain, total strain minus its free thermal strain. The comparison cannot judge an expected zero when every value in that result is rounding noise, such as `M_T` of a symmetric laminate; leave such values out.

Use `units = "SI"` for moduli in GPa, stresses in MPa and thickness in mm. For example, 140 GPa is entered as `E1 = 140`. `US` uses Msi/ksi/inches, and `psi` uses psi/inches. The engine still calculates in SI base units.

New result keys are added when a problem needs them.

## When a case fails

The failure message lists each value that disagrees. Check, in this order:

1. **Input typo or units.** For example, 2.13 entered where the source means 2.13e7 psi, or the course Excel files' Boron/Epoxy G12 = 7,800,000 psi where the course table gives 780,000.
2. **Convention.** Ply order, tensor versus engineering shear, or angle direction.
3. **Source error.** Answer keys and textbooks contain mistakes; confirm with a second method.
4. **Engine bug.** Fix the code; the case then guards against the bug permanently.
5. **Missing feature.** For example, a temperature change. The problem becomes the next feature to build.

## Sources and copyright

Store only the numbers and a short source reference. Course problem statements, solution files, Excel input files and textbook pages stay out of the repository; keep them in `.local/` or another ignored folder.
