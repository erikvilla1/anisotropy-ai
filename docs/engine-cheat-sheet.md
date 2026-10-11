# Engine cheat sheet

How to put a problem into the engine and read the answer. One case file per problem; keep personal files in `.local/questions/`, which git ignores. The full format is in [engine/validation/README.md](../engine/validation/README.md); the equations are in [engine/docs/theory.md](../engine/docs/theory.md).

## Run

From the repository root, in the VS Code terminal (Ctrl + `):

```powershell
cd engine
uv run python examples/laminate_calculator.py ../.local/questions/my-problem.toml
```

Send the printout to a file to read it beside the case: append `> ../.local/questions/my-problem.out.txt`. Press the up arrow to rerun after editing. A file name with a space must be quoted; better, use hyphens.

If the inputs are wrong, the only output is one line naming the field, for example `applied: needs exactly one of (...)`. The engine never guesses a value.

## The five parts of a case

```toml
title = "One line: what is asked"
source = "Book and problem number, or course, homework and problem; numbers only"
units = "SI"        # or "US" or "psi"; see the table below
f12_star = -0.5     # only for Tsai-Wu; stays above [material]

[material]          # or:  library = "im7-8552"  (optional dataset = "...")
E1 = 135
E2 = 10
G12 = 5
nu12 = 0.30
F1t = 1500          # strengths only for failure; compressive as positive magnitudes
F1c = 1200
F2t = 40
F2c = 200
F6 = 70
strain_limits = "from-strengths"   # maximum strain limits = strength / modulus; or give eps1t, eps1c, eps2t, eps2c, gamma12
alpha1 = -0.3e-6    # expansion only with delta_T
alpha2 = 28e-6

[laminate]
layup = [0, 45, -45, 90, 90, -45, 45, 0]   # bottom ply first; write [..]s out in full
ply_thickness = 0.125

[applied]           # exactly one of the forms below, plus delta_T if the problem has one
loads = [800, 200, 100, 0, 0, 0]
delta_T = -100

[failure]           # optional: which loads grow until a ply fails; the rest and delta_T stay fixed
fixed = [0, 0, 0, 0, 0, 0]
variable = [800, 200, 100, 0, 0, 0]

[expected]          # optional: the answer you trust; the run ends with agrees / DIFFERS per value
tolerance = 0.005
A11 = 57.995
```

## Units: what each number means

| Quantity | `SI` | `US` | `psi` |
| --- | --- | --- | --- |
| Moduli E, G, Q, Q̄ | GPa | Msi | psi |
| Strengths, stresses | MPa | ksi | psi |
| Thickness, z | mm | in | in |
| N (force per width) | N/m | lb/in | lb/in |
| M (moment per width) | N·m/m | lb·in/in | lb·in/in |
| Curvature | 1/m | 1/in | 1/in |
| A | MN/m | 10⁶ lb/in | lb/in |
| B | kN | 10³ lb | lb |
| D | N·m | lb·in | lb·in |
| α, ΔT | 1/°C, °C | 1/°F, °F | 1/°F, °F |
| Compliance S, S̄ | 1/GPa | 1/Msi | 1/psi |

Watch for: a book that gives N in **N/mm** means ×1000 for `SI`; thickness in metres means ×1000; A printed in lb/in means ÷10⁶ for `US`. A mid-plane strain above about 0.01 for carbon/epoxy is a sign the loads are a factor of 1000 off.

## Applied: pick the form the problem is posed in

| The problem gives | Write |
| --- | --- |
| Force and moment resultants | `loads = [Nx, Ny, Nxy, Mx, My, Mxy]` |
| Average stress on the laminate or lamina | `stress = [sx, sy, txy]` |
| Mid-plane strains and curvatures | `strains = [ex, ey, gxy, kx, ky, kxy]` |
| Stresses in the fibre axes of one lamina | `local_stress = [s1, s2, t12]` |
| Strains in the fibre axes of one lamina | `local_strain = [e1, e2, g12]` |
| Some loads and some deformations known | `[applied.mixed]` with one entry per pair, e.g. `Nx = 100` and `eps_y = 0` |
| Known forces and prescribed curvatures | `forces_curvature = [Nx, Ny, Nxy, kx, ky, kxy]` |
| A temperature change on top of any of these | `delta_T = -100` (needs alpha1, alpha2) |

## Failure: what `fixed` and `variable` mean

The engine finds R such that a ply first fails at `fixed + R × variable`, with the temperature change always fixed.

- "By what factor can these loads grow?" `variable` = the applied loads, `fixed` = zeros. R < 1 means already failed. Omitting `[failure]` does the same.
- "Find Nx at failure while Mx and ΔT stay": `fixed = [0, 0, 0, Mx, 0, 0]`, `variable = [1, 0.5, 0, 0, 0, 0]` for Ny = Nx/2; then R is Nx itself.

R is a strength ratio, not a failure index. For maximum stress, maximum strain and Tsai-Hill FI = 1/R (Tsai-Hill: FI = 1/R²); for Tsai-Wu the two are not reciprocals. Four criteria run when their inputs exist: maximum stress and Tsai-Hill with the five strengths; maximum strain with five strain limits (`eps1t … gamma12` as fractions) or `strain_limits = "from-strengths"` for the course's strength-over-modulus allowables; Tsai-Wu with `f12_star` (−0.5 is the textbook assumption, Eq. 6.40).

## Reading the printout, in order

1. Library material block (if `library` was used): dataset, citation, page of every value.
2. `Q, fiber axes` and `S`: the ply in its own axes. `Q-bar` and `S-bar` per distinct angle: rotated to laminate axes; the 16 and 26 terms are the shear coupling.
3. Ply positions z, then `A`, `B`, `D`. A symmetric stack gives B = 0; entries like 1e-16 are floating-point noise.
4. Thermal resultants N_T, M_T and free thermal strains, when ΔT is given.
5. Mid-plane strains and curvatures.
6. Ply strains and stresses, bottom and top face of every ply, in laminate axes and in fibre axes. With ΔT, stresses use mechanical strain = total strain − free thermal strain.
7. Engineering constants Ex, Ey, Gxy, ν, η.
8. Strength ratios per ply face and first-ply failure (ply, face, z, mode, loads at failure), when strengths are given.
9. `Answer key vs engine`, when `[expected]` is given.

## Expected: keys you can check

`Q11 Q12 Q22 Q66`, `S11 … S66`, `Qbar11 … Qbar66`, `Sbar11 … Sbar66` (one angle); `A11 A12 A16 A22 A26 A66` and the same for `B`, `D`, `a`, `b`, `d`; `strain_global`, `curvature`, `strain_local`, `stress_global`, `stress_local`; `ply_strain_global`, `ply_stress_local` and the `_bottom` / `_top` faces, as a full list or `[expected.ply_stress_local_top]` with `9 = [s1, s2, t12]`; `N_T`, `M_T`; `Nx … Mxy`, `sigma_x …`, `eps_x …`, `kappa_x …`; `Ex Ey Gxy nu_xy nu_yx`; `fpf_ratio_max_stress`, `fpf_ratio_max_strain`, `fpf_ratio_tsai_hill`, `fpf_ratio_tsai_wu`, `fpf_ply_…`, `fpf_z_…`, `fpf_forces_…`, `fpf_moments_…`.

## What the engine does not do

Maximum strain, Tsai-Hill and Hashin criteria; buckling; moisture; progressive failure after the first ply; through-thickness and free-edge stresses; holes; fatigue. A problem that asks for one of these is a gap, not an input mistake: tell the team.

## Other ways in

- The course Excel template runs directly: `uv run python examples/laminate_calculator.py path/to/input.xlsx`.
- The API: `uv run uvicorn anisotropy_api.main:app --port 8000` from `api/`, then http://127.0.0.1:8000/docs. Accepts `material: {"library_id": "im7-8552"}`.
- The website calculator with the library picker: stiffness and deformation only.
