# Engine theory

Every equation the engine uses, and the function that computes it. Equations follow I. M. Daniel and O. Ishai, *Engineering Mechanics of Composite Materials*, 2nd edition (Oxford University Press, 2006). The engine works in SI units throughout.

## Conventions

- Axis 1 is the fiber direction and axis 2 is transverse, in the ply's plane.
- Shear strain is engineering shear: $`\gamma_{12} = 2\varepsilon_{12}`$.
- The ply angle $`\theta`$ is positive counterclockwise from the laminate x axis to fiber axis 1.
- Plies are listed from the bottom face up; $`z`$ is measured from the mid-plane, positive upward.
- Compressive strengths are positive magnitudes.

## 1. Ply stiffness (`lamina.py`)

Reciprocity, computed by `Lamina.nu21`:

```math
\nu_{21} = \nu_{12}\,\frac{E_2}{E_1}
```

Positive strain energy requires the following; otherwise `Lamina` rejects the input:

```math
1 - \nu_{12}\nu_{21} > 0 \quad\Longleftrightarrow\quad \nu_{12}^2 < \frac{E_1}{E_2}
```

Plane-stress reduced stiffness (Eq. 4.56), computed by `reduced_stiffness`:

```math
\begin{bmatrix}\sigma_1\\ \sigma_2\\ \tau_{12}\end{bmatrix} = \mathbf{Q}\begin{bmatrix}\varepsilon_1\\ \varepsilon_2\\ \gamma_{12}\end{bmatrix},
\qquad
\mathbf{Q} = \begin{bmatrix}
\dfrac{E_1}{1-\nu_{12}\nu_{21}} & \dfrac{\nu_{12}E_2}{1-\nu_{12}\nu_{21}} & 0\\
\dfrac{\nu_{12}E_2}{1-\nu_{12}\nu_{21}} & \dfrac{E_2}{1-\nu_{12}\nu_{21}} & 0\\
0 & 0 & G_{12}
\end{bmatrix}
```

$`Q_{66} = G_{12}`$ because shear is engineering shear. $`Q_{16} = Q_{26} = 0`$ because, in fiber axes, stretching produces no shear.

## 2. Rotation (`rotation.py`)

With $`m = \cos\theta`$ and $`n = \sin\theta`$, computed by `stress_transformation` and `strain_transformation` (Eqs. 4.57–4.62):

```math
\mathbf{T}_\sigma = \begin{bmatrix} m^2 & n^2 & 2mn\\ n^2 & m^2 & -2mn\\ -mn & mn & m^2-n^2 \end{bmatrix},
\qquad
\mathbf{T}_\varepsilon = \begin{bmatrix} m^2 & n^2 & mn\\ n^2 & m^2 & -mn\\ -2mn & 2mn & m^2-n^2 \end{bmatrix}
```

Both map laminate-axis values (x, y) to fiber-axis values (1, 2). The factor of 2 sits in the third column of $`\mathbf{T}_\sigma`$ and in the third row of $`\mathbf{T}_\varepsilon`$, because shear is engineering shear.

Transformed stiffness (Eq. 4.67), computed by `transformed_reduced_stiffness`:

```math
\bar{\mathbf{Q}} = \mathbf{T}_\sigma^{-1}\,\mathbf{Q}\,\mathbf{T}_\varepsilon,
\qquad
\mathbf{T}_\sigma^{-1}(\theta) = \mathbf{T}_\sigma(-\theta)
```

## 3. Laminate stiffness (`laminate.py`)

Ply boundaries, computed by `ply_interfaces`:

```math
h = \sum_{k=1}^{N} t_k, \qquad z_0 = -\frac{h}{2}, \qquad z_k = z_{k-1} + t_k
```

Classical laminate theory assumes strain varies linearly through the thickness, so the stress in ply $`k`$ is:

```math
\boldsymbol{\varepsilon}(z) = \boldsymbol{\varepsilon}^0 + z\,\boldsymbol{\kappa},
\qquad
\boldsymbol{\sigma}_k(z) = \bar{\mathbf{Q}}_k\left(\boldsymbol{\varepsilon}^0 + z\,\boldsymbol{\kappa}\right)
```

Integrating stress and stress times $`z`$ through the thickness gives the force and moment per unit width:

```math
\mathbf{N} = \mathbf{A}\,\boldsymbol{\varepsilon}^0 + \mathbf{B}\,\boldsymbol{\kappa},
\qquad
\mathbf{M} = \mathbf{B}\,\boldsymbol{\varepsilon}^0 + \mathbf{D}\,\boldsymbol{\kappa}
```

Each ply contributes through the integrals of 1, $`z`$ and $`z^2`$, which give the $`\tfrac12`$ and $`\tfrac13`$ factors. Computed by `abd_matrices` (Eq. 7.20):

```math
\mathbf{A} = \sum_{k=1}^{N} \bar{\mathbf{Q}}_k\,(z_k - z_{k-1}),
\qquad
\mathbf{B} = \frac12\sum_{k=1}^{N} \bar{\mathbf{Q}}_k\,(z_k^2 - z_{k-1}^2),
\qquad
\mathbf{D} = \frac13\sum_{k=1}^{N} \bar{\mathbf{Q}}_k\,(z_k^3 - z_{k-1}^3)
```

Units: A in N/m, B in N, D in N·m. The code counts plies from 0, so ply `k` spans `z[k]` to `z[k + 1]`.

## 4. Response to loads (`response.py`)

Loads are per unit width. For a tension coupon of width $`w`$ carrying load $`P`$, $`N_x = P/w`$.

Mid-plane strain and curvature, computed by `abd_matrix` and `midplane_response`. The system is solved directly, without forming the inverse:

```math
\begin{bmatrix}\mathbf{A} & \mathbf{B}\\ \mathbf{B} & \mathbf{D}\end{bmatrix}
\begin{bmatrix}\boldsymbol{\varepsilon}^0\\ \boldsymbol{\kappa}\end{bmatrix}
= \begin{bmatrix}\mathbf{N}\\ \mathbf{M}\end{bmatrix}
```

Strain and stress on the bottom and top face of every ply, computed by `ply_surfaces`:

```math
\boldsymbol{\varepsilon}_{xy} = \boldsymbol{\varepsilon}^0 + z\,\boldsymbol{\kappa},
\qquad
\boldsymbol{\sigma}_{xy} = \bar{\mathbf{Q}}_k\,\boldsymbol{\varepsilon}_{xy},
\qquad
\boldsymbol{\varepsilon}_{12} = \mathbf{T}_\varepsilon\,\boldsymbol{\varepsilon}_{xy},
\qquad
\boldsymbol{\sigma}_{12} = \mathbf{T}_\sigma\,\boldsymbol{\sigma}_{xy} = \mathbf{Q}\,\boldsymbol{\varepsilon}_{12}
```

Strain is continuous across ply interfaces; stress jumps between plies. Stress is linear through each ply, so its largest value is on a face. That is why both faces are reported.

## 5. Failure (`failure.py`)

The strength ratio $`R`$ is the factor on all applied loads at which a criterion is first reached. Daniel and Ishai call it the safety factor $`S_f`$. The analysis is linear, so stresses scale with the load.

Maximum stress, computed by `max_stress_ratio`. A component that is zero or of the other sign sets no limit:

```math
R = \min\left\{ \frac{F_{1t}}{\sigma_1}\Big|_{\sigma_1>0},\; \frac{F_{1c}}{-\sigma_1}\Big|_{\sigma_1<0},\; \frac{F_{2t}}{\sigma_2}\Big|_{\sigma_2>0},\; \frac{F_{2c}}{-\sigma_2}\Big|_{\sigma_2<0},\; \frac{F_6}{|\tau_{12}|} \right\}
```

Tsai-Wu (Eqs. 6.29–6.40), computed by `tsai_wu_ratio`:

```math
f_1\sigma_1 + f_2\sigma_2 + f_{11}\sigma_1^2 + f_{22}\sigma_2^2 + f_{66}\tau_{12}^2 + 2f_{12}\sigma_1\sigma_2 = 1
```

```math
f_1 = \frac{1}{F_{1t}} - \frac{1}{F_{1c}}, \quad
f_2 = \frac{1}{F_{2t}} - \frac{1}{F_{2c}}, \quad
f_{11} = \frac{1}{F_{1t}F_{1c}}, \quad
f_{22} = \frac{1}{F_{2t}F_{2c}}, \quad
f_{66} = \frac{1}{F_6^2}, \quad
f_{12} = f_{12}^{*}\sqrt{f_{11}f_{22}}
```

The interaction term $`f_{12}^{*}`$ must be measured or explicitly assumed, and must lie between −1 and 1. Eq. 6.40 suggests $`-\tfrac12`$. Scaling every stress by $`R`$ gives a quadratic (Eqs. 6.57–6.59):

```math
aR^2 + bR - 1 = 0, \qquad
a = f_{11}\sigma_1^2 + f_{22}\sigma_2^2 + f_{66}\tau_{12}^2 + 2f_{12}\sigma_1\sigma_2, \qquad
b = f_1\sigma_1 + f_2\sigma_2
```

```math
R = \frac{-b + \sqrt{b^2 + 4a}}{2a} = \frac{2}{b + \sqrt{b^2 + 4a}}
```

The code uses the second form, which avoids losing digits when $`b`$ is large and negative.

Margin of safety for a required factor of safety $`FS \ge 1`$, computed by `margin_of_safety`:

```math
MS = \frac{R}{FS} - 1, \qquad \text{pass when } MS \ge 0
```

First-ply failure, computed by `first_ply_failure`:

```math
R_{\text{FPF}} = \min_{k,\ \text{faces}} R\big(\boldsymbol{\sigma}_{12}\big),
\qquad
\mathbf{N}_{\text{FPF}} = R_{\text{FPF}}\,\mathbf{N},
\qquad
\mathbf{M}_{\text{FPF}} = R_{\text{FPF}}\,\mathbf{M}
```

First-ply failure is the onset of cracking in one ply, not the laminate's ultimate strength.

## 6. Laminate engineering constants (`engineering.py`)

The in-plane compliance $`\mathbf{a}`$ is the top-left 3×3 block of the inverted ABD matrix, so an unsymmetric laminate is free to bend as it stretches (Section 7.12.3). For a symmetric laminate $`\mathbf{a} = \mathbf{A}^{-1}`$. Computed by `engineering_constants` (Eq. 7.84):

```math
\bar E_x = \frac{1}{h\,a_{11}}, \quad
\bar E_y = \frac{1}{h\,a_{22}}, \quad
\bar G_{xy} = \frac{1}{h\,a_{66}}, \quad
\bar\nu_{xy} = -\frac{a_{21}}{a_{11}}, \quad
\bar\nu_{yx} = -\frac{a_{12}}{a_{22}}, \quad
\bar\eta_{xs} = \frac{a_{61}}{a_{11}}, \quad
\bar\eta_{ys} = \frac{a_{62}}{a_{22}}
```

## Not modeled yet

- Temperature and moisture effects, including curing residual stresses
- Progressive ply failure and ultimate laminate strength
- Through-thickness and interlaminar stresses
- Holes and other geometry that needs finite element analysis
- Maximum strain and Hashin failure criteria
