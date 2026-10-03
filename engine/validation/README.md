# Validation cases

Each file in `cases/` is one solved problem: the inputs, and the answers from a source independent of this code (a textbook, an answer key, and later our own lab measurements). `tests/test_validation_cases.py` runs every case on each `uv run pytest`. A case fails when the engine and the source disagree by more than the case's tolerance.

Together these cases are the evidence that the engine gives the right numbers, and they show which kinds of problems it can already solve.

## Add a case

1. Copy `cases/_template.toml` to a new file named after the problem, for example `homework-3-problem-2.toml`. Files starting with `_` are ignored.
2. Fill in `title`, `source` and `units`, then the material, layup and one `[applied]` entry.
3. Under `[expected]`, give only the values the source states, in the case's units. Set `tolerance` to suit how the source rounds: 0.001 (0.1%) for four significant figures, 0.005 for three.
4. Run `uv run pytest tests/test_validation_cases.py -v`.

## Inputs and results

| `[applied]` key | Values |
| --- | --- |
| `loads` | Nx, Ny, Nxy, Mx, My, Mxy |
| `stress` | sigma_x, sigma_y, tau_xy averaged through the thickness |
| `strains` | eps_x, eps_y, gamma_xy, kappa_x, kappa_y, kappa_xy |
| `local_stress` | sigma_1, sigma_2, tau_12 (single-angle layups) |
| `local_strain` | eps_1, eps_2, gamma_12 (single-angle layups) |
| `forces_curvature` | Nx, Ny, Nxy, kappa_x, kappa_y, kappa_xy; calculate the required moments |

| `[expected]` key | Meaning |
| --- | --- |
| `A11` ... `A66`, `B..`, `D..` | Laminate stiffness entries (indices 1, 2, 6) |
| `strain_global`, `curvature` | Mid-plane strains and curvatures |
| `moments` | Applied Mx, My, Mxy resultants, in the case's moment-per-width units |
| `strain_local`, `stress_global`, `stress_local` | Ply state, for single-angle layups without bending |
| `Ex`, `Ey`, `Gxy`, `nu_xy`, `nu_yx` | Laminate engineering constants |
| `fpf_ratio_max_stress`, `fpf_ratio_tsai_wu` | First-ply-failure strength ratio (Tsai-Wu needs `f12_star`) |

Shear strains are engineering shear. Layups are listed from the bottom face up. Units follow `src/anisotropy_engine/units.py`.

Case inputs reject unknown fields, partial strength sets and incomplete vectors. `loads`, `strains` and `forces_curvature` require all six components, including explicit zeros. Other applied vectors require three finite components. The calculator accepts this same format; `expected` is optional for calculation and required for an automated comparison. Tsai-Wu runs only when all strengths and an explicit `f12_star` are present.

`forces_curvature` converts the first three components as force/width and the last three as curvature; the moments are outputs, never zero-filled inputs. Its forward check must pass before results are returned. The two `constructed-*.toml` cases use independently evaluated scalar formulas with synthetic inputs. They check implementation, not experimental validity. The generic engineering constants still describe free bending (ADR-0005). Any failure ratio scales all solved force/moment resultants proportionally; it does not maintain a fixed nonzero curvature while increasing only the forces.

Use `units = "SI"` for moduli in GPa, stresses in MPa and thickness in mm. For example, 140 GPa is entered as `E1 = 140`. `US` uses Msi/ksi/inches, and `psi` uses psi/inches. The engine still calculates in SI base units.

New result keys are added when a problem needs them.

## When a case fails

The failure message lists each value that disagrees. Check, in this order:

1. **Input typo or units.** For example, 2.13 entered where the source means 2.13e7 psi.
2. **Convention.** Ply order, tensor versus engineering shear, or angle direction.
3. **Source error.** Answer keys and textbooks contain mistakes; confirm with a second method.
4. **Engine bug.** Fix the code; the case then guards against the bug permanently.
5. **Missing feature.** For example, a temperature change. The problem becomes the next feature to build.

## Sources and copyright

Store only the numbers and a short source reference. Course problem statements, solution files and textbook pages stay out of the repository; keep them in `.local/`, which Git ignores.
