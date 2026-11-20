# Engine theory

Every equation the engine uses, and the function that computes it. Equations follow I. M. Daniel and O. Ishai, *Engineering Mechanics of Composite Materials*, 2nd edition (Oxford University Press, 2006). The engine works in SI units throughout.

## Conventions

- Axis 1 is the fiber direction and axis 2 is transverse, in the ply's plane.
- Shear strain is engineering shear: $`\gamma_{12} = 2\varepsilon_{12}`$.
- The ply angle $`\theta`$ is positive counterclockwise from the laminate x axis to fiber axis 1.
- Plies are listed from the bottom face up; $`z`$ is measured from the mid-plane, positive upward.
- Compressive strengths are positive magnitudes.

Input models reject unknown field names. Direct stress, strain and curvature vectors must contain exactly three finite components. Zero stress is valid; NaN and infinity are not measurements and are rejected before calculation. A strength ratio of positive infinity remains valid for an unstressed ply, while a factor of safety must be finite and at least one.

## 1. Ply stiffness (`lamina.py`)

Reciprocity, computed by `Lamina.nu21`:

```math
\nu_{21} = \nu_{12}\,\frac{E_2}{E_1}
```

<!-- code: Lamina.nu21 -->

Positive strain energy requires the following, checked by `Lamina._positive_compliance`, which rejects inputs that break it:

```math
1 - \nu_{12}\nu_{21} > 0 \quad\Longleftrightarrow\quad \nu_{12}^2 < \frac{E_1}{E_2}
```

<!-- code: Lamina._positive_compliance -->

Plane-stress reduced stiffness (Eq. 4.56), computed by `reduced_stiffness`:

```math
\begin{bmatrix}\sigma_1\\ \sigma_2\\ \tau_{12}\end{bmatrix} = \mathbf{Q}\begin{bmatrix}\varepsilon_1\\ \varepsilon_2\\ \gamma_{12}\end{bmatrix},
\qquad
\mathbf{Q} = \begin{bmatrix}
\dfrac{E_1}{1-\nu_{12}\nu_{21}} & \dfrac{\nu_{12}E_2}{1-\nu_{12}\nu_{21}} & 0\\[12pt]
\dfrac{\nu_{12}E_2}{1-\nu_{12}\nu_{21}} & \dfrac{E_2}{1-\nu_{12}\nu_{21}} & 0\\[12pt]
0 & 0 & G_{12}
\end{bmatrix}
```

$`Q_{66} = G_{12}`$ because shear is engineering shear. $`Q_{16} = Q_{26} = 0`$ because, in fiber axes, stretching produces no shear.

<!-- code: reduced_stiffness -->

Plane-stress compliance, the inverse of $`\mathbf{Q}`$, written directly from the engineering constants and computed by `reduced_compliance`:

```math
\begin{bmatrix}\varepsilon_1\\ \varepsilon_2\\ \gamma_{12}\end{bmatrix} = \mathbf{S}\begin{bmatrix}\sigma_1\\ \sigma_2\\ \tau_{12}\end{bmatrix},
\qquad
\mathbf{S} = \begin{bmatrix}
\dfrac{1}{E_1} & -\dfrac{\nu_{12}}{E_1} & 0\\[12pt]
-\dfrac{\nu_{12}}{E_1} & \dfrac{1}{E_2} & 0\\[12pt]
0 & 0 & \dfrac{1}{G_{12}}
\end{bmatrix}
```

<!-- code: reduced_compliance -->

## 2. Rotation (`rotation.py`)

With $`m = \cos\theta`$ and $`n = \sin\theta`$, computed by `stress_transformation` and `strain_transformation` (Eqs. 4.57–4.62):

```math
\mathbf{T}_\sigma = \begin{bmatrix} m^2 & n^2 & 2mn\\ n^2 & m^2 & -2mn\\ -mn & mn & m^2-n^2 \end{bmatrix},
\qquad
\mathbf{T}_\varepsilon = \begin{bmatrix} m^2 & n^2 & mn\\ n^2 & m^2 & -mn\\ -2mn & 2mn & m^2-n^2 \end{bmatrix}
```

Both map laminate-axis values (x, y) to fiber-axis values (1, 2). The factor of 2 sits in the third column of $`\mathbf{T}_\sigma`$ and in the third row of $`\mathbf{T}_\varepsilon`$, because shear is engineering shear.

<!-- code: stress_transformation, strain_transformation -->

Transformed stiffness (Eq. 4.67), computed by `transformed_reduced_stiffness`:

```math
\bar{\mathbf{Q}} = \mathbf{T}_\sigma^{-1}\,\mathbf{Q}\,\mathbf{T}_\varepsilon,
\qquad
\mathbf{T}_\sigma^{-1}(\theta) = \mathbf{T}_\sigma(-\theta)
```

<!-- code: transformed_reduced_stiffness -->

Transformed compliance: rotate stress into fiber axes, apply $`\mathbf{S}`$, and rotate the strain back. Computed by `transformed_compliance`:

```math
\bar{\mathbf{S}} = \mathbf{T}_\varepsilon^{-1}\,\mathbf{S}\,\mathbf{T}_\sigma,
\qquad
\mathbf{T}_\varepsilon^{-1}(\theta) = \mathbf{T}_\varepsilon(-\theta),
\qquad
\bar{\mathbf{S}} = \bar{\mathbf{Q}}^{-1}
```

It is built from $`\mathbf{S}`$ rather than by inverting $`\bar{\mathbf{Q}}`$, so $`\bar{\mathbf{S}}\,\bar{\mathbf{Q}} = \mathbf{I}`$ is an independent check.

<!-- code: transformed_compliance -->

## 3. Laminate stiffness (`laminate.py`)

Ply boundaries, computed by `ply_interfaces`:

```math
h = \sum_{k=1}^{N} t_k, \qquad z_0 = -\frac{h}{2}, \qquad z_k = z_{k-1} + t_k
```

<!-- code: ply_interfaces -->

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

<!-- code: abd_matrices -->

## 4. Response to loads (`response.py`)

Loads are per unit width. For a coupon of width $`w`$ carrying a load $`P`$ along $`x`$, $`N_x = P/w`$.

Mid-plane strain and curvature, computed by `abd_matrix` and `midplane_response`. The system is solved directly, without forming the inverse:

```math
\begin{bmatrix}\mathbf{A} & \mathbf{B}\\ \mathbf{B} & \mathbf{D}\end{bmatrix}
\begin{bmatrix}\boldsymbol{\varepsilon}^0\\ \boldsymbol{\kappa}\end{bmatrix}
= \begin{bmatrix}\mathbf{N}\\ \mathbf{M}\end{bmatrix}
```

<!-- code: abd_matrix, midplane_response -->

The inverted ABD matrix gives deformation directly from loads. Its blocks are computed by `abd_compliance` (Eqs. 7.27-7.28, where the lower-left block $`\mathbf{c} = \mathbf{b}^{T}`$); some texts write them as $`\boldsymbol{\alpha}`$, $`\boldsymbol{\beta}`$ and $`\boldsymbol{\delta}`$:

```math
\begin{bmatrix}\boldsymbol{\varepsilon}^0\\ \boldsymbol{\kappa}\end{bmatrix}
= \begin{bmatrix}\mathbf{a} & \mathbf{b}\\ \mathbf{b}^{T} & \mathbf{d}\end{bmatrix}
\begin{bmatrix}\mathbf{N}\\ \mathbf{M}\end{bmatrix},
\qquad
\begin{bmatrix}\mathbf{a} & \mathbf{b}\\ \mathbf{b}^{T} & \mathbf{d}\end{bmatrix}
= \begin{bmatrix}\mathbf{A} & \mathbf{B}\\ \mathbf{B} & \mathbf{D}\end{bmatrix}^{-1}
```

Units: a in m/N, b in 1/N, d in 1/(N·m). Here the inverse is the result itself, so it is formed explicitly. For a symmetric laminate $`\mathbf{b} = 0`$, $`\mathbf{a} = \mathbf{A}^{-1}`$ and $`\mathbf{d} = \mathbf{D}^{-1}`$.

<!-- code: abd_compliance -->

### Known forces and prescribed curvature

When all three force resultants and all three curvatures are known, the moments
are unknown. Rearranging the same constitutive equations gives:

```math
\mathbf{A}\,\boldsymbol{\varepsilon}^0 = \mathbf{N} - \mathbf{B}\,\boldsymbol{\kappa},
\qquad
\mathbf{M} = \mathbf{B}\,\boldsymbol{\varepsilon}^0 + \mathbf{D}\,\boldsymbol{\kappa}
```

Computed by `prescribed_curvature_response`, using a direct linear solve rather
than an explicit inverse. Setting every curvature to zero enforces flatness in
this CLT model. The result is the moment resultant applied to the laminate, not
the opposite reaction on a fixture. No specimen width is needed for resultants
per unit width. Zero curvature alone does not fix rigid-body displacement or
rotation, and this operation does not design supports. Mechanical loading only.

The constitutive basis is also given in [NASA RP-1351, Section III.D, equations 48-51](https://ntrs.nasa.gov/api/citations/19950009349/downloads/19950009349.pdf#page=29).
This operation uses the repository's sign and bottom-first stacking conventions;
source diagrams may choose a different positive thickness direction.

The engine applies the solved moments and known forces to `midplane_response`
and compares the recovered deformation with the target curvature and calculated
strain. This forward check is computed by `forward_verification`, which also
checks mixed conditions below. It rejects the result if any component fails
either check:

```math
|\varepsilon^{0,\mathrm{check}}_i-\varepsilon^0_i|
\le 10^{-12}+10^{-9}|\varepsilon^0_i|,
\qquad
|\kappa^{\mathrm{check}}_i-\kappa_i|
\le 10^{-9}\,\mathrm{m}^{-1}+10^{-9}|\kappa_i|
```

These are numerical acceptance tolerances (ADR-0013), not a bound on physical
model error. Reported residuals are recovered minus reference values. Both solves
share stiffness code; their agreement is a consistency check. Separate analytical
and stress-integration tests supply additional verification. Severe conditioning
and experimental accuracy remain unestablished.

<!-- code: prescribed_curvature_response, forward_verification -->

Two constructed analytical cases isolate this operation. For two equally thick
0/90 plies with zero major Poisson ratio, the in-plane matrices are diagonal:

```math
A_{11}=A_{22}=(E_1+E_2)t,\qquad A_{66}=2G_{12}t,
\qquad B_{11}=-B_{22}=\frac{(E_2-E_1)t^2}{2},\qquad B_{66}=0
```

At zero curvature, each strain is the corresponding force divided by its diagonal
A entry, and each moment is the corresponding B entry times strain. A second
case uses a single 0-degree ply: B is zero and
$`\mathbf{D}=\operatorname{diag}(E_1,E_2,G_{12})h^3/12`$ when the Poisson ratio is zero.
The case files record constructed constants and loading, not measured properties
or a course solution. Their expected values come from these scalar equations.

### Mixed load and deformation conditions

Many problems fix some loads and some deformations: a lamina kept rectangular
($`\gamma_{xy} = 0`$ under known normal stresses), a coupon between rigid walls
($`\varepsilon_y = 0`$), or a cured laminate held flat in one direction only. For each of
the six pairs $`(N_x, \varepsilon^0_x)`$, $`(N_y, \varepsilon^0_y)`$, $`(N_{xy}, \gamma^0_{xy})`$,
$`(M_x, \kappa_x)`$, $`(M_y, \kappa_y)`$ and $`(M_{xy}, \kappa_{xy})`$ exactly one quantity is
known. A force may be given as the average stress through the thickness, $`\sigma = N/h`$.

With $`\mathbf{K}`$ the 6×6 ABD matrix, $`\mathbf{d} = [\boldsymbol{\varepsilon}^0; \boldsymbol{\kappa}]`$,
$`\mathbf{F}`$ the mechanical resultants and $`\mathbf{F}^T`$ the thermal ones (zero without a
temperature change), the total relation is $`\mathbf{F} + \mathbf{F}^T = \mathbf{K}\,\mathbf{d}`$.
Splitting its rows into those with a known load (L) and those with a known
deformation (D) gives the unknowns, computed by `mixed_response`:

```math
\mathbf{K}_{LL}\,\mathbf{d}_L = \mathbf{F}_L + \mathbf{F}^T_L - \mathbf{K}_{LD}\,\mathbf{d}_D,
\qquad
\mathbf{F}_D = \mathbf{K}_{DL}\,\mathbf{d}_L + \mathbf{K}_{DD}\,\mathbf{d}_D - \mathbf{F}^T_D
```

All loads known is the forward solve above; known forces and curvatures is the
prescribed-curvature operation. The same forward check must recover the deformation
from the total loads before a result is returned (ADR-0016).

<!-- code: mixed_response -->

### Ply surface recovery

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

<!-- code: ply_surfaces -->

## 5. Failure (`failure.py`)

The strength ratio $`R`$ is the factor on all applied loads at which a criterion is first reached. Daniel and Ishai call it the safety factor $`S_f`$. The analysis is linear, so stresses scale with the load.

Maximum stress, computed by `max_stress_ratio`. A component that is zero or of the other sign sets no limit:

```math
R = \min\left\{ \frac{F_{1t}}{\sigma_1}\Big|_{\sigma_1>0},\; \frac{F_{1c}}{-\sigma_1}\Big|_{\sigma_1<0},\; \frac{F_{2t}}{\sigma_2}\Big|_{\sigma_2>0},\; \frac{F_{2c}}{-\sigma_2}\Big|_{\sigma_2<0},\; \frac{F_6}{|\tau_{12}|} \right\}
```

<!-- code: max_stress_ratio -->

Maximum strain, computed by `max_strain_ratio` (Daniel & Ishai Eq. 6.6), uses the mechanical strain in fiber axes, $`\boldsymbol{\varepsilon}_{12} = \mathbf{S}\,\boldsymbol{\sigma}_{12}`$, which with a temperature change excludes the free thermal strain, against five strain limits:

```math
R = \min\left\{ \frac{\varepsilon_{1t}^{u}}{\varepsilon_1}\Big|_{\varepsilon_1>0},\; \frac{\varepsilon_{1c}^{u}}{-\varepsilon_1}\Big|_{\varepsilon_1<0},\; \frac{\varepsilon_{2t}^{u}}{\varepsilon_2}\Big|_{\varepsilon_2>0},\; \frac{\varepsilon_{2c}^{u}}{-\varepsilon_2}\Big|_{\varepsilon_2<0},\; \frac{\gamma_{12}^{u}}{|\gamma_{12}|} \right\}
```

The limits are measured values given explicitly, or, by a stated choice in the case (`strain_limits = "from-strengths"`), strength divided by modulus, computed by `strain_limits_from_strengths` (ADR-0021). The engine never derives them on its own. Maximum strain and maximum stress differ in a laminate because $`\varepsilon_1 = (\sigma_1 - \nu_{12}\sigma_2)/E_1`$ couples the two normal stresses.

<!-- code: max_strain_ratio, strain_limits_from_strengths -->

Tsai-Hill (Eq. 6.16), computed by `tsai_hill_index` and `tsai_hill_ratio`:

```math
\mathrm{FI} = \left(\frac{\sigma_1}{X}\right)^2 - \frac{\sigma_1\sigma_2}{X^2} + \left(\frac{\sigma_2}{Y}\right)^2 + \left(\frac{\tau_{12}}{F_6}\right)^2,
\qquad X = \begin{cases} F_{1t} & \sigma_1 \ge 0 \\ F_{1c} & \sigma_1 < 0 \end{cases},\quad
Y = \begin{cases} F_{2t} & \sigma_2 \ge 0 \\ F_{2c} & \sigma_2 < 0 \end{cases},
\qquad R = \frac{1}{\sqrt{\mathrm{FI}}}
```

The index is a homogeneous quadratic, so scaling every load by $`R`$ scales it by $`R^2`$ and the sign selection does not change: $`R = 1/\sqrt{\mathrm{FI}}`$. This is the textbook's convention for the mixed-sign case; other implementations choose differently, as the Tsai-Hill card of our website's physics library also notes.

<!-- code: tsai_hill_index, tsai_hill_ratio -->

Tsai-Wu (Eqs. 6.29–6.40), computed by `tsai_wu_ratio`:

```math
f_1\sigma_1 + f_2\sigma_2 + f_{11}\sigma_1^2 + f_{22}\sigma_2^2 + f_{66}\tau_{12}^2 + 2f_{12}\sigma_1\sigma_2 = 1
```

```math
\begin{gathered}
f_1 = \frac{1}{F_{1t}} - \frac{1}{F_{1c}}, \qquad
f_2 = \frac{1}{F_{2t}} - \frac{1}{F_{2c}}, \qquad
f_{66} = \frac{1}{F_6^2},\\[6pt]
f_{11} = \frac{1}{F_{1t}F_{1c}}, \qquad
f_{22} = \frac{1}{F_{2t}F_{2c}}, \qquad
f_{12} = f_{12}^{*}\sqrt{f_{11}f_{22}}
\end{gathered}
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

The code uses the second form, which avoids subtraction in the numerator when $`b > 0`$. It is algebraically equivalent to the first form; extreme numerical conditioning is not established by the current reference cases.

<!-- code: tsai_wu_ratio -->

Margin of safety for a required factor of safety $`FS \ge 1`$, computed by `margin_of_safety`:

```math
MS = \frac{R}{FS} - 1, \qquad \text{pass when } MS \ge 0
```

<!-- code: margin_of_safety -->

First-ply failure, computed by `first_ply_failure`:

```math
R_{\text{FPF}} = \min_{k,\ \text{faces}} R\big(\boldsymbol{\sigma}_{12}\big),
\qquad
\mathbf{N}_{\text{FPF}} = R_{\text{FPF}}\,\mathbf{N},
\qquad
\mathbf{M}_{\text{FPF}} = R_{\text{FPF}}\,\mathbf{M}
```

First-ply failure is the onset of cracking in one ply, not the laminate's ultimate strength.

<!-- code: first_ply_failure -->

### Fixed and variable loading

Often only part of the loading grows: the residual stress of a temperature change stays,
and a problem may hold some loads fixed. The stress at failure is then
$`\boldsymbol{\sigma}_s + R\,\boldsymbol{\sigma}_v`$, where $`\boldsymbol{\sigma}_s`$ comes from the
fixed loads and the temperature change, and $`\boldsymbol{\sigma}_v`$ from the variable loads
(Daniel and Ishai Section 9.8, Eq. 9.25, which holds the hygrothermal stresses fixed).
Both parts are linear in their loads, so they superpose exactly.

Maximum stress, computed by `max_stress_ratio_combined`. For each component, with tensile
limit $`F_t`$ and compressive limit $`F_c`$ ($`F_6`$ for both in shear):

```math
R = \frac{F_t - \sigma_s}{\sigma_v}\ \ (\sigma_v > 0),
\qquad
R = \frac{-F_c - \sigma_s}{\sigma_v}\ \ (\sigma_v < 0),
\qquad
R = 0 \ \text{ when } \sigma_s \text{ alone reaches a limit}
```

and the smallest over the components governs.

<!-- code: max_stress_ratio_combined -->

Maximum strain with fixed and variable loading, computed by `max_strain_ratio_combined`, has the same form with the mechanical strains $`\boldsymbol{\varepsilon}_s + R\,\boldsymbol{\varepsilon}_v`$ in place of the stresses.

<!-- code: max_strain_ratio_combined -->

Tsai-Hill with fixed and variable loading, computed by `tsai_hill_ratio_combined`: substituting $`\boldsymbol{\sigma}_s + R\,\boldsymbol{\sigma}_v`$ gives $`aR^2 + bR + c = 0`$ with the bilinear form of Eq. 6.16, as for Tsai-Wu below. Because $`X`$ and $`Y`$ depend on the signs of the stresses at failure, which a fixed stress of one sign and a variable stress of the other can change along the path, the engine solves the quadratic for each of the four sign choices and keeps a root only when the stress at that root has the signs assumed; the smallest such root governs.

<!-- code: tsai_hill_ratio_combined -->

Tsai-Wu, computed by `tsai_wu_ratio_combined`. Substituting $`\boldsymbol{\sigma}_s + R\,\boldsymbol{\sigma}_v`$
into the criterion gives a quadratic (Eqs. 9.26-9.27):

```math
\begin{gathered}
aR^2 + bR + c = 0, \qquad
a = q(\boldsymbol{\sigma}_v, \boldsymbol{\sigma}_v),\\[6pt]
b = f_1\sigma_{v1} + f_2\sigma_{v2} + 2\,q(\boldsymbol{\sigma}_s, \boldsymbol{\sigma}_v), \qquad
c = f_1\sigma_{s1} + f_2\sigma_{s2} + q(\boldsymbol{\sigma}_s, \boldsymbol{\sigma}_s) - 1
\end{gathered}
```

```math
q(\mathbf{x}, \mathbf{y}) = f_{11}x_1y_1 + f_{22}x_2y_2 + f_{66}x_6y_6 + f_{12}(x_1y_2 + x_2y_1),
\qquad
R = \frac{-2c}{b + \sqrt{b^2 - 4ac}}
```

With $`c < 0`$ (the fixed stresses alone do not reach the criterion) and $`a \ge 0`$, this is the
single positive root; $`c \ge 0`$ gives $`R = 0`$. With no fixed stress, $`c = -1`$ and both
criteria reduce to the mechanical-only ratios above.

<!-- code: tsai_wu_ratio_combined -->

First-ply failure under fixed and variable loading, computed by `first_ply_failure_combined`,
checks both faces of every ply and reports the loads at failure:

```math
R_{\text{FPF}} = \min_{k,\ \text{faces}} R\big(\boldsymbol{\sigma}_{s}, \boldsymbol{\sigma}_{v}\big),
\qquad
\mathbf{N}_{\text{FPF}} = \mathbf{N}_s + R_{\text{FPF}}\,\mathbf{N}_v,
\qquad
\mathbf{M}_{\text{FPF}} = \mathbf{M}_s + R_{\text{FPF}}\,\mathbf{M}_v
```

Stress is linear through each ply in both parts. For maximum stress each limit's ratio is
then monotonic between the faces, so the faces govern. For Tsai-Wu, checking the faces
follows the mechanical-only check and common practice; it is not proven here that no
interior point is lower. When a case gives no fixed loads, its mechanical loads are
variable and only a temperature change stays fixed (ADR-0017).

<!-- code: first_ply_failure_combined -->

## 6. Laminate engineering constants (`engineering.py`)

The in-plane compliance $`\mathbf{a}`$ is the top-left 3×3 block of the inverted ABD matrix, so an unsymmetric laminate is free to bend as it stretches (Section 7.12.3). For a symmetric laminate $`\mathbf{a} = \mathbf{A}^{-1}`$. Computed by `engineering_constants` (Eq. 7.84):

```math
\begin{gathered}
\bar E_x = \frac{1}{h\,a_{11}}, \qquad
\bar E_y = \frac{1}{h\,a_{22}}, \qquad
\bar G_{xy} = \frac{1}{h\,a_{66}},\\[6pt]
\bar\nu_{xy} = -\frac{a_{21}}{a_{11}}, \qquad
\bar\nu_{yx} = -\frac{a_{12}}{a_{22}}, \qquad
\bar\eta_{xs} = \frac{a_{61}}{a_{11}}, \qquad
\bar\eta_{ys} = \frac{a_{62}}{a_{22}}
\end{gathered}
```

<!-- code: engineering_constants -->

## 7. Temperature change (`thermal.py`)

A uniform temperature change $`\Delta T`$ (in K, the same number as a change in °C) gives each ply a free thermal strain $`\boldsymbol{\alpha}\,\Delta T`$. The expansion coefficients $`\alpha_1`$ and $`\alpha_2`$ are strains per kelvin, so they rotate into laminate axes like strain (Eqs. 8.10-8.12). Computed by `thermal_expansion_xy`:

```math
\begin{bmatrix}\alpha_x\\ \alpha_y\\ \alpha_{xy}\end{bmatrix}
= \mathbf{T}_\varepsilon^{-1}\begin{bmatrix}\alpha_1\\ \alpha_2\\ 0\end{bmatrix}
= \begin{bmatrix}\alpha_1 m^2 + \alpha_2 n^2\\ \alpha_1 n^2 + \alpha_2 m^2\\ 2(\alpha_1 - \alpha_2)\,mn\end{bmatrix},
\qquad
\mathbf{T}_\varepsilon^{-1}(\theta) = \mathbf{T}_\varepsilon(-\theta)
```

$`\alpha_{xy}`$ is an engineering shear coefficient, like $`\gamma_{xy}`$.

<!-- code: thermal_expansion_xy -->

A ply is stressed only by the strain it is forced to take beyond its free thermal strain (Eq. 8.16):

```math
\boldsymbol{\sigma}_k(z) = \bar{\mathbf{Q}}_k\left(\boldsymbol{\varepsilon}^0 + z\,\boldsymbol{\kappa} - \boldsymbol{\alpha}_k\,\Delta T\right)
```

Integrating through the thickness, as for A, B and D, moves the thermal terms to the load side. The thermal force and moment resultants (Eqs. 8.18 and 8.20, without moisture) are computed by `thermal_resultants`:

```math
\mathbf{N}^T = \Delta T\sum_{k=1}^{N}\bar{\mathbf{Q}}_k\,\boldsymbol{\alpha}_k\,(z_k - z_{k-1}),
\qquad
\mathbf{M}^T = \frac{\Delta T}{2}\sum_{k=1}^{N}\bar{\mathbf{Q}}_k\,\boldsymbol{\alpha}_k\,(z_k^2 - z_{k-1}^2)
```

They are the resultants that would hold every ply at its free thermal strain, not applied loads.

<!-- code: thermal_resultants -->

Mid-plane strain and curvature under mechanical loads and a temperature change (Eq. 8.25), computed by `thermomechanical_response`:

```math
\begin{bmatrix}\mathbf{A} & \mathbf{B}\\ \mathbf{B} & \mathbf{D}\end{bmatrix}
\begin{bmatrix}\boldsymbol{\varepsilon}^0\\ \boldsymbol{\kappa}\end{bmatrix}
= \begin{bmatrix}\mathbf{N} + \mathbf{N}^T\\ \mathbf{M} + \mathbf{M}^T\end{bmatrix}
```

With no mechanical load, a symmetric laminate has $`\mathbf{M}^T = 0`$ and stays flat, while an unsymmetric one warps.

<!-- code: thermomechanical_response -->

Ply strain and stress on each face, computed by `thermal_ply_surfaces`, follow the stress equation above. The reported strains are total strains $`\boldsymbol{\varepsilon}^0 + z\,\boldsymbol{\kappa}`$, as a strain gauge would read them.

<!-- code: thermal_ply_surfaces -->

When strains or curvatures are prescribed instead of loads, the mechanical loads are the total resultants minus the thermal ones: $`\mathbf{N} = \mathbf{A}\boldsymbol{\varepsilon}^0 + \mathbf{B}\boldsymbol{\kappa} - \mathbf{N}^T`$ and $`\mathbf{M} = \mathbf{B}\boldsymbol{\varepsilon}^0 + \mathbf{D}\boldsymbol{\kappa} - \mathbf{M}^T`$. The mechanical-only functions are unchanged. A temperature change applies only where it is given explicitly (ADR-0014).

These are the equations of Daniel and Ishai Chapter 8 (printed pp. 212-217) with the moisture terms omitted; Eq. 8.20 writes the moment integral as the ply's mid-plane height times its thickness, which equals $`(z_k^2 - z_{k-1}^2)/2`$. With $`\Delta T = 1`$ and no load, the mid-plane strains are the laminate expansion coefficients (Eq. 8.33). The committed validation cases check this path against closed forms: a cooled cross-ply under a fixed and a growing load (`constructed-cross-ply-cooling-first-ply-failure`) and a two-material laminate under load and cooling (`constructed-two-material-laminate-cooling`). The course's answer keys for curing stresses, an unsymmetric cure and laminate expansion coefficients are checked on the founder's machine only, since they stay off the repository (ADR-0042).

Failure ratios with a temperature change hold the residual stress fixed and scale only the mechanical loads, as described under "Fixed and variable loading" (ADR-0017).

With a temperature change and no load at all, there is no mechanical load to scale. The laminate is free, and with $`\mathbf{N} = \mathbf{M} = \mathbf{0}`$ the mid-plane strain and curvature, the mechanical strain $`\boldsymbol{\varepsilon} - \boldsymbol{\alpha}\,\Delta T`$ in every ply and so its stress are all proportional to $`\Delta T`$. The strength ratio of that residual stress is then the factor on the temperature change itself, and the first ply fails at

```math
\Delta T_{\mathrm{FPF}} = R\,\Delta T ,
```

computed by `first_ply_failure_thermal`. A laminate whose plies all expand alike (one material at one angle) is free and unstressed; its stress, a round-off of some $`10^{-17}`$ of what a restrained ply would carry, is refused rather than read as a factor.

<!-- code: first_ply_failure_thermal -->

## 8. Plate buckling (`buckling.py`)

A midplane-symmetric laminate ($`\mathbf{B} = 0`$) as a rectangular plate $`0 \le x \le a`$, $`0 \le y \le b`$, simply supported on all four edges, under uniform in-plane resultants. The engine reports the load factor $`\lambda`$ on reference resultants $`(N_x, N_y, N_{xy})`$, tension positive, at which a slightly bent shape is first in equilibrium. Unsymmetric laminates are refused (Whitney, *Structural Analysis of Laminated Anisotropic Plates*, 1987, Chapter 7 treats specific classes; not implemented).

Specially orthotropic laminates ($`D_{16} = D_{26} = 0`$) without shear, computed by `navier_buckling` (Whitney Section 5.5, Eq. 5.72). With $`\alpha_m = m\pi/a`$ and $`\beta_n = n\pi/b`$, the mode $`w = W \sin\alpha_m x \sin\beta_n y`$ satisfies the governing equation and the simply supported conditions exactly, and

```math
\lambda_{mn} = \frac{D_{11}\alpha_m^4 + 2(D_{12} + 2D_{66})\alpha_m^2\beta_n^2 + D_{22}\beta_n^4}{-N_x\alpha_m^2 - N_y\beta_n^2},
\qquad \lambda_{cr} = \min_{m,n \ge 1} \lambda_{mn}
```

over the modes the load compresses (positive denominator). The course formula sheet writes the same with $`N_y = kN_x`$.

<!-- code: navier_buckling -->

General symmetric laminates, or shear, computed by `ritz_buckling` (Whitney Sections 6.5 and 6.6, Eq. 6.38; the Galerkin and Ritz forms coincide for this series). With $`w = \sum_{m,n=1}^{M} W_{mn}\sin\alpha_m x \sin\beta_n y`$, the bending energy $`\tfrac12\int \boldsymbol{\kappa}^T\mathbf{D}\boldsymbol{\kappa}\,dA`$ and the work of the in-plane loads give

```math
\mathbf{K}\,\mathbf{w} = \lambda\,\mathbf{G}\,\mathbf{w}
```

```math
\begin{aligned}
K_{ij} = \int \big[\, & D_{11}w_{i,xx}w_{j,xx} + D_{12}(w_{i,xx}w_{j,yy} + w_{i,yy}w_{j,xx}) + D_{22}w_{i,yy}w_{j,yy} + 4D_{66}w_{i,xy}w_{j,xy} \\
& + 2D_{16}(w_{i,xx}w_{j,xy} + w_{i,xy}w_{j,xx}) + 2D_{26}(w_{i,yy}w_{j,xy} + w_{i,xy}w_{j,yy})\,\big]\,dA
\end{aligned}
```

```math
G_{ij} = -\int \big[N_x w_{i,x}w_{j,x} + N_y w_{i,y}w_{j,y} + N_{xy}(w_{i,x}w_{j,y} + w_{i,y}w_{j,x})\big]\,dA
```

The integrals are products of one-dimensional sine and cosine integrals, which are closed forms; the $`D_{16}`$, $`D_{26}`$ and $`N_{xy}`$ terms couple modes whose $`m`$ or $`n`$ differ by an odd number. $`\mathbf{K}`$ is positive definite, so the problem is reduced by its Cholesky factor to a symmetric eigenproblem and the smallest positive $`\lambda`$ governs. The series satisfies only the geometric boundary conditions, so $`\lambda`$ converges from above and the case must state the number of terms (ADR-0022). With $`D_{16} = D_{26} = N_{xy} = 0`$ the equations uncouple and reproduce the closed form. The orthotropic closed form is reported beside the series result; it is nonconservative for angle-ply plates (Whitney Section 6.5). The choice between the closed form and the series, and the refusal of unsymmetric laminates, is computed by `plate_buckling`.

<!-- code: ritz_buckling, plate_buckling -->

Checks: Whitney's four numerical results for $`D_{11}/D_{22} = 10`$ and $`(D_{12} + 2D_{66})/D_{22} = 1`$ (Eqs. 5.76, 5.81, 5.84, 5.87); the series against the closed form; a hand-computed cross-ply plate (validation case `constructed-cross-ply-plate-buckling`). No course answer key for buckling has been checked yet.

## 9. Lamina constants from fiber and matrix (`micromechanics.py`)

Everything above starts from the lamina constants $`E_1, E_2, G_{12}, \nu_{12}`$. This section estimates them from the fiber, the matrix and the fiber volume ratio $`V_f`$ ($`V_m = 1 - V_f`$, no voids), for continuous aligned fibers with a perfect bond, a transversely isotropic fiber ($`E_{1f}, E_{2f}, G_{12f}, \nu_{12f}`$) and an isotropic matrix ($`E_m, \nu_m`$, $`G_m = E_m / 2(1 + \nu_m)`$). The models are those of Daniel and Ishai, chapter 3 (2nd ed., 2006, pp. 46-57); the caller names the model for $`E_2`$ and for $`G_{12}`$ and, for Halpin-Tsai, the parameter $`\xi`$, so a case records exactly what was used (ADR-0003). Strengths and expansion coefficients are not predicted; when a case gives them they are attached to the lamina as measured values.

The fiber-direction modulus and the major Poisson's ratio follow from equal strain in fiber and matrix, the parallel (Voigt) model or rule of mixtures (Daniel and Ishai Eqs. 3.23 and 3.24, pp. 49-50), computed by `rule_of_mixtures`:

```math
E_1 = V_f E_{1f} + V_m E_m, \qquad \nu_{12} = V_f \nu_{12f} + V_m \nu_m
```

<!-- code: rule_of_mixtures -->

The transverse modulus and the in-plane shear modulus are matrix dominated and the simplest model assumes equal stress in fiber and matrix, the series (Reuss) model (Eqs. 3.29-3.30 for $`E_2`$ with $`E_{2f}`$, Eqs. 3.48-3.49 for $`G_{12}`$ with $`G_{12f}`$ and $`G_m`$; pp. 52 and 57), computed by `series_model`:

```math
\frac{1}{P} = \frac{V_f}{P_f} + \frac{V_m}{P_m}
```

<!-- code: series_model -->

The series model underestimates both. Daniel and Ishai (Eq. 3.31, p. 52) usually replace the matrix modulus in the transverse series model by the modulus of a matrix the fibers keep from contracting along them, computed by `constrained_matrix_modulus`; the series model with it is the `series_constrained` choice for $`E_2`$ (Eq. 3.32):

```math
E'_m = \frac{E_m}{1 - \nu_m^2}
```

<!-- code: constrained_matrix_modulus -->

The Halpin-Tsai relation interpolates between the series and parallel models with a reinforcing-efficiency parameter $`\xi`$ (Eq. 3.17, p. 48; for $`E_2`$ Eqs. 3.35-3.36, p. 53; for $`G_{12}`$ Eq. 3.50, p. 57), computed by `halpin_tsai`. $`\xi = 0`$ gives the series model and $`\xi \to \infty`$ the parallel one (Eqs. 3.19-3.20). Daniel and Ishai quote $`1 \le \xi \le 2`$ for $`E_2`$ (1 for hexagonal arrays of glass and carbon at high $`V_f`$, 2 for square arrays) and $`\xi = 1`$ for $`G_{12}`$; the value is an input, never assumed:

```math
\eta = \frac{P_f - P_m}{P_f + \xi P_m}, \qquad P = P_m\,\frac{1 + \xi\,\eta\,V_f}{1 - \eta\,V_f}
```

<!-- code: halpin_tsai -->

Shaffer's combined series-parallel model (Daniel and Ishai Eqs. 3.33-3.34, p. 52, and Problems 3.9 and 3.18) puts the column that holds the fiber, fiber and matrix in series, in parallel with the pure-matrix columns beside it. For a square array of square fibers in a cell of side $`L`$ the fiber side is $`a`$ with $`V_f = (a/L)^2`$, so the fiber column takes the width fraction $`\sqrt{V_f}`$ and within it the fiber the height fraction $`\sqrt{V_f}`$; the derivation of the closed form below is this repository's, since the book asks for it as a problem and prints no answer. It is computed by `combination_square_array` and applies to $`E_2`$ (with $`E_{2f}, E_m`$) and to $`G_{12}`$ (with $`G_{12f}, G_m`$):

```math
P = P_m\,(1 - \sqrt{V_f}) + \sqrt{V_f}\;\frac{P_f P_m}{P_m \sqrt{V_f} + P_f\,(1 - \sqrt{V_f})}
```

<!-- code: combination_square_array -->

The lamina is assembled from the named models, computed by `lamina_from_constituents`, which refuses an unnamed model, a Halpin-Tsai model without its $`\xi`$, an $`\xi`$ given for another model, and a volume ratio outside $`(0, 1)`$:

<!-- code: lamina_from_constituents -->

Not estimated here: strengths, expansion coefficients, $`E_3`$, $`G_{23}`$ and $`\nu_{23}`$, void content, discontinuous fibers, and the self-consistent and bounding methods of the same chapter.

## 10. Laminate description (`summary.py`)

The stack itself, before any load, as the response endpoint reports it beside the matrices (ADR-0059). Nothing here is new physics: each statement follows from the definitions of the laminate stiffness above and the textbook's classes of laminates (Daniel & Ishai Chapter 7). The thickness is the sum of the ply thicknesses, computed by `total_thickness`:

```math
h = \sum_{k=1}^{n} t_k
```

<!-- code: total_thickness -->

Three properties of the stacking are checked by `is_symmetric`, `is_antisymmetric` and `is_balanced`. A laminate is symmetric when ply $`k`$ and ply $`n - 1 - k`$ (counted from the bottom, ADR-0004) have the same material, fiber angle and thickness, the middle ply of an odd count mirroring itself; then $`\mathbf{B} = 0`$. It is antisymmetric when every such pair has the same material and thickness and opposite angles, and at least one pair is off axis: the antisymmetric angle-ply $`[\theta/-\theta/\theta/-\theta]`$, which has $`B_{16}`$ and $`B_{26}`$ but $`D_{16} = D_{26} = 0`$. It is balanced when every off-axis ply at $`+\theta`$ has a partner at $`-\theta`$ of the same material and thickness anywhere in the stack, plies at $`0`$ and $`90`$ needing none; then $`A_{16} = A_{26} = 0`$. A fiber at $`\theta`$ is the fiber at $`\theta + 180°`$, so angles compare modulo $`180°`$.

<!-- code: is_symmetric, is_antisymmetric, is_balanced -->

The kind of laminate is judged first on $`\mathbf{A}`$ and then on the angles, computed by `laminate_kind`: quasi-isotropic when $`\mathbf{A}`$ is isotropic to the tolerance,

```math
A_{11} = A_{22}, \qquad A_{16} = A_{26} = 0, \qquad A_{66} = \tfrac{1}{2}\left(A_{11} - A_{12}\right),
```

which the stacks $`[0/\pm 60]_s`$ and $`[0/\pm 45/90]_s`$ satisfy; otherwise unidirectional (one fiber angle), cross-ply (only $`0`$ and $`90`$), angle-ply (only $`+\theta`$ and $`-\theta`$), or general.

<!-- code: laminate_kind -->

Which couplings the matrices show is computed by `coupling_flags`. An entry counts as zero when its magnitude is at most $`10^{-9}`$ of its matrix's largest entry, the relative tolerance of the forward verification (ADR-0013): $`A_{16}`$ and $`A_{26}`$ against $`\max|A_{ij}|`$ (extension-shear coupling), $`D_{16}`$ and $`D_{26}`$ against $`\max|D_{ij}|`$ (bending-twisting coupling), and $`\mathbf{B}`$ against $`\max|A_{ij}|\,h/2`$, the size $`\mathbf{B}`$ would have if the whole stiffness sat on one face (extension-bending coupling); $`\mathbf{B}`$ is roundoff for a symmetric stack, so its own largest entry would be no scale. The same tolerance decides the kind above.

<!-- code: coupling_flags -->

The mass per unit area needs a density for every ply, computed by `areal_mass`; a ply whose material records none is named, and the value is left out rather than guessed (ADR-0003):

```math
m_A = \sum_{k=1}^{n} \rho_k\, t_k
```

<!-- code: areal_mass -->

All of it together, with the tolerance it used, is computed by `laminate_summary`.

<!-- code: laminate_summary -->

First-ply failure under the one loading given, every load scaling together with nothing held fixed and no temperature change, is computed by `first_ply_failure_summary` and `face_of`: maximum stress and Tsai-Hill whenever the plies have strengths, maximum strain only with strain limits and Tsai-Wu only with an explicit $`f_{12}^*`$ (the failure section above, ADR-0021), the others reported as not computed with the reason; each result names the criterion, the strength ratio $`R`$, the ply (1 at the bottom), the face of that ply, the governing mode and the loads at failure $`R\,[\mathbf{N}; \mathbf{M}]`$. Without a load, or with a ply that has no strengths, nothing is evaluated and the reason is stated.

<!-- code: first_ply_failure_summary, face_of -->

## 11. Fibre tow tension (`tow.py`)

The tension test of a resin-impregnated, consolidated carbon or graphite fibre tow, ASTM D4018-23 (ADR-0074). A tow is a strand, not a laminate: the resin holds the filaments together so they load evenly (§4.5), and the area that carries the force is the fibre's. Nothing in this section uses the laminate sections above. The standard is read in the licensed copy; its text is not in this repository (ADR-0018 amendment 1), so each equation below names its number for a reader with their own copy.

Everything is SI: masses in kg, lengths in m, densities in kg/m³, mass per unit length in kg/m, forces in N, stresses and moduli in Pa, strains absolute. The standard states its equations in g, m, g/cm³ and N and its strain limits in microstrain; the fea package converts at the boundary (ADR-0002).

The mass per unit length of the sized fibre (Eq 1) is computed by `mass_per_unit_length` from a specimen of mass $`W_1`$ and length $`L`$:

```math
\mathrm{MUL} = \frac{W_1}{L}
```

<!-- code: mass_per_unit_length -->

A density measured on sized fibre, corrected for the sizing (Eq 2), is computed by `fibre_density`; the correction $`k_c`$ is the laboratory's, found from repeated tests of sized and desized fibre (§12.2.2), and a desized or unsized sample needs none:

```math
\rho_f = \rho_{sf} - k_c
```

<!-- code: fibre_density -->

The resin content by weight of the impregnated, consolidated strand (Eq 3) is computed by `resin_content`; a strand no heavier than its fibre is refused:

```math
RC = 100\left(1 - \frac{\mathrm{MUL}}{\mathrm{MUL}_i}\right)
```

<!-- code: resin_content -->

The fibre's area, computed by `fibre_area`, is the mass per unit length over the density. Eqs 4 and 5 divide by it, and §11.3.6 sizes the preload with it:

```math
A = \frac{\mathrm{MUL}}{\rho_f}
```

<!-- code: fibre_area -->

The tensile strength from the maximum force $`P`$ (Eq 4) and the chord modulus from the forces $`P_l`$ and $`P_u`$ read at the chord's lower and upper strain (Eq 5, §11.3.11) are computed by `tow_strength` and `tow_chord_modulus`:

```math
\sigma = \frac{P\,\rho_f}{\mathrm{MUL}}, \qquad E = \frac{(P_u - P_l)\,\rho_f}{(\varepsilon_u - \varepsilon_l)\,\mathrm{MUL}}
```

<!-- code: tow_strength, tow_chord_modulus -->

The strains in $`E`$ are absolute. The standard multiplies Eq 5 by $`B = 10^{-3}`$ for a load in newtons to report GPa and lists $`\varepsilon_u`$ and $`\varepsilon_l`$ in microstrain; the two do not agree. With $`P`$ in N, $`\rho_f`$ in g/cm³ and MUL in g/m, $`P\rho_f/\mathrm{MUL}`$ is in MPa (Eq 4 with its factor $`A = 1`$); divided by a strain difference and multiplied by $`10^{-3}`$, it is in GPa only when the strains are absolute (0.005, not 5000). With microstrain the result is $`10^{6}`$ times too small. This is our reading, recorded in ADR-0074; `engine/tests/test_tow.py` works one case both ways.

The strains of the chord (Table 2) and the largest preload (Table 1) depend on the product's typical strain at failure $`\varepsilon_f`$, and are computed by `chord_strains` and `preload_strain`:

For a typical failure strain of at least 12000 microstrain the chord runs from 1000 to 6000 microstrain and the preload is at most 200 microstrain; from 6000 up to 12000, from 1000 to 3000 and at most 100; below 6000, from 500 to 1500 and at most 100. A failure strain on a bound takes the higher row.

<!-- code: chord_strains, preload_strain -->

The forces to plan a test with are computed by `planning_loads`: $`P = \varepsilon E A`$ at the preload strain and at the two chord strains, and $`P = \sigma A`$ at the strength, from a datasheet's modulus and strength (linear to failure). §11.3.6 asks for the preload to be found this way. A datasheet value left out leaves the forces that need it out.

<!-- code: planning_loads -->

A series of $`n`$ specimens is summarised by its mean, its sample standard deviation and its coefficient of variation in percent (Eqs 6 to 8), computed by `sample_statistics`. The deviation is computed in the two-pass form, equal in exact arithmetic to Eq 7 as printed, $`\sqrt{(\sum x_i^2 - n\bar{x}^2)/(n-1)}`$, without its loss of digits to cancellation:

```math
\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i, \qquad s_{n-1} = \sqrt{\frac{\sum_{i=1}^{n}(x_i - \bar{x})^2}{n - 1}}, \qquad CV = 100\,\frac{s_{n-1}}{\bar{x}}
```

<!-- code: sample_statistics -->

The checks of the record against the standard's clauses (gauge length, number of specimens, resin strain, speed) are the fea package's profile `standards/astm_d4018.py`; the engine only computes.

## 12. Sandwich panel (`sandwich.py`)

Two thin laminated faces on a core that carries no in-plane load (Zenkert, *An Introduction to Sandwich Construction*, 1995, Chapter 3). The core's in-plane stiffness is taken as zero, so it adds distance between the faces and nothing else. The stiffnesses are the sums of Section 3 over the face plies only, with $`z`$ measured from the mid-plane of the whole panel, computed by `sandwich_abd`:

```math
A_{ij} = \sum_{k \in \text{faces}} \bar{Q}_{ij}^{k}\,(z_k - z_{k-1}), \qquad
B_{ij} = \frac{1}{2}\sum_{k \in \text{faces}} \bar{Q}_{ij}^{k}\,(z_k^2 - z_{k-1}^2), \qquad
D_{ij} = \frac{1}{3}\sum_{k \in \text{faces}} \bar{Q}_{ij}^{k}\,(z_k^3 - z_{k-1}^3)
```

For two faces that mirror each other, each of membrane stiffness $`\mathbf{A}_f`$ and with its mid-plane at a distance $`d`$ from the panel's, $`\mathbf{A} = 2\mathbf{A}_f`$, $`\mathbf{B} = 0`$ and $`\mathbf{D} \approx 2 d^2 \mathbf{A}_f`$: the core multiplies the bending stiffness and leaves the membrane stiffness as it was. With a core of zero thickness the result is the laminate of the two faces.

<!-- code: sandwich_abd -->

Not covered: transverse shear deformation of the core, which lowers a panel's buckling load and adds to its deflection; face wrinkling; crushing and shear failure of the core.

## 13. Wing (`wing/`)

One side of a straight wing of constant chord with two spars, worked as a beam (ADR-0115). Axes: $`y`$ along the span from the root, $`x`$ along the chord from the leading edge, $`z`$ up. A layup's 0° direction is the span. Layups are symmetric, given by their outer half; the skin may have a core between its halves (Section 12). Sources for the beam theory: Megson, *Aircraft Structures for Engineering Students*, 4th ed. (2007), Chapters 16 to 18; Bruhn, *Analysis and Design of Flight Vehicle Structures* (1973), Chapter A15.

### Airfoil

The height of the upper and lower surface at a chord position, as fractions of the chord, is computed by `Airfoil.surface_heights`: by straight lines between the points of an outline the engineer gives, or from the NACA four-digit formula (Jacobs, Ward and Pinkerton, NACA Report 460, 1933). For digits $`m\,p\,tt`$, with $`m`$ in hundredths, $`p`$ in tenths and the thickness $`t`$ in hundredths of the chord:

```math
y_t = 5t\left(0.2969\sqrt{x} - 0.1260x - 0.3516x^2 + 0.2843x^3 - 0.1015x^4\right)
```

```math
y_c = \begin{cases} \dfrac{m}{p^2}\left(2px - x^2\right) & x < p \\[2mm] \dfrac{m}{(1-p)^2}\left(1 - 2p + 2px - x^2\right) & x \ge p \end{cases}
\qquad
x_{u,l} = x \mp y_t\sin\theta, \quad z_{u,l} = y_c \pm y_t\cos\theta, \quad \tan\theta = \frac{dy_c}{dx}
```

The thickness is laid off at right angles to the camber line, so the surface point above a chord position belongs to a camber point slightly beside it; that point is found by repeating $`x_p = x \pm y_t(x_p)\sin\theta(x_p)`$.

<!-- code: Airfoil.surface_heights -->

### Air density and dynamic pressure

The density ratio $`\sigma = \rho/\rho_0`$ of the International Standard Atmosphere up to 11 km (ISO 2533:1975) is computed by `density_ratio`, with $`T_0 = 288.15`$ K, $`p_0 = 101\,325`$ Pa, a lapse rate $`\lambda = 6.5`$ K/km, $`R = 287.05287`$ J/(kg K), $`g_0 = 9.80665`$ m/s² and $`\rho_0 = p_0/(RT_0) = 1.2250`$ kg/m³:

```math
\sigma(h) = \left(1 - \frac{\lambda h}{T_0}\right)^{\frac{g_0}{R\lambda} - 1}
```

<!-- code: density_ratio -->

The dynamic pressure is computed by `dynamic_pressure`. An equivalent airspeed is the speed that gives the same dynamic pressure at sea-level density, so it loads the wing alike at every altitude; a true airspeed does not:

```math
q = \tfrac{1}{2}\rho_0 V_e^2 = \tfrac{1}{2}\rho_0\,\sigma(h)\,V^2
```

<!-- code: dynamic_pressure -->

### Load cases

The set of cases, each at every altitude of the envelope, is computed by `flight_cases` (14 CFR Part 23 as it stood before Amendment 23-64: 23.333, 23.337, 23.341, 23.349). With $`n_p`$ and $`n_n`$ the positive and negative limit load factors:

| Cases | Condition | Speed | Load factor |
| --- | --- | --- | --- |
| 1 to 5 | Level flight | stall with flaps, stall without, cruise, dive, flutter | 1 |
| 6, 7 | Positive maneuver, high and low angle of attack | positive maneuver speed, dive | $`n_p`$ |
| 8, 9 | Negative maneuver, high and low angle of attack | negative maneuver speed, dive | $`n_n`$ |
| 10 to 13 | Gust up and down | cruise, dive | stated, or $`1 \pm \Delta n`$ below |
| 14, 15 | Roll, aileron down and up | cruise | 1 |
| 16, 17 | Roll in a pull-up, aileron down and up | positive maneuver speed | a stated fraction of $`n_p`$ |

A case whose speed, gust entry or aileron the envelope does not state is not run and is listed with what it needs; nothing is assumed in its place (ADR-0003).

<!-- code: flight_cases -->

The change of load factor in a gust, when the gust load factors are not stated, is computed by `gust_load_factor_increment` from the derived gust speed $`U_{de}`$, the equivalent airspeed $`V_e`$, the lift curve slope $`a`$ per radian, the wing loading $`W/S`$ and the mean chord $`\bar{c}`$ (14 CFR 23.341(c)):

```math
\Delta n = \frac{K_g\,\rho_0\,U_{de}\,V_e\,a}{2\,(W/S)}, \qquad K_g = \frac{0.88\,\mu_g}{5.3 + \mu_g}, \qquad \mu_g = \frac{2\,(W/S)}{\rho\,\bar{c}\,a\,g}
```

The regulation prints the first as $`K_g U_{de} V a / (498\,(W/S))`$ with $`V`$ in knots, $`U_{de}`$ in ft/s and $`W/S`$ in lb/ft²; 498 is $`2/\rho_0`$ in those units, rounded.

<!-- code: gust_load_factor_increment -->

### Loads along the span

Running lift, shear, bending moment and torque at the stations of every case are computed by `span_loads`. One side of the wing carries $`P = nW/2`$ over its half span $`L`$. Schrenk's approximation (NACA TM 948, 1940) takes the mean of a load in proportion to the chord, uniform here, and an elliptical load of the same total, with $`\eta = y/L`$:

```math
w(y) = \frac{1}{2}\left[\frac{4P}{\pi L}\sqrt{1 - \eta^2} + \frac{P}{L}\right]
```

The shear and the bending moment are its exact integrals from the station to the tip:

```math
V(y) = \frac{1}{2}\left[\frac{2P}{\pi}\left(\frac{\pi}{2} - \arcsin\eta - \eta\sqrt{1-\eta^2}\right) + P\,(1-\eta)\right]
```

```math
M(y) = \frac{1}{2}\left[\frac{2PL}{\pi}\left(\eta\arcsin\eta - \frac{\pi}{2}\eta + \sqrt{1-\eta^2} - \frac{(1-\eta^2)^{3/2}}{3}\right) + \frac{PL}{2}(1-\eta)^2\right]
```

At the root $`V = P`$ and $`M = PL\,(1/4 + 2/(3\pi))`$: the lift of one side acts at the mean of $`L/2`$ and $`4L/(3\pi)`$. An aileron between $`y_1`$ and $`y_2`$ adds $`\Delta w = q\,c\,\Delta c_l`$ over its span, with $`\hat{y}`$ the station moved into $`[y_1, y_2]`$:

```math
\Delta V = \Delta w\,(y_2 - \hat{y}), \qquad \Delta M = \frac{\Delta w}{2}\left[(y_2 - y)^2 - (\hat{y} - y)^2\right] \ \ (y < y_2)
```

The torque about the shear center, nose up positive, has the lift at the aerodynamic center $`x_{ac}`$ acting ahead of the shear center $`x_{sc}`$, the airfoil's own moment on every unit of span, and the aileron's change of it over the aileron's span:

```math
T(y) = (x_{sc} - x_{ac})\,V(y) + q\,c^2 c_m\,(L - y) + q\,c^2\,\Delta c_m\,(y_2 - \hat{y})
```

Roll acceleration, the change of angle of attack in a roll and the wing's elastic twist are not modeled, and the wing's own weight is not subtracted.

<!-- code: span_loads -->

### Section

A symmetric layup under in-plane load strains alike through its thickness, so each ply angle has one stress state. A wall's own spanwise curvature $`k_x`$, its other moments free, adds a strain that grows through the thickness: with $`\mathbf{d} = \mathbf{D}^{-1}`$ (the core between the halves, Section 12), a point at $`\zeta`$ from the wall's mid-surface strains by $`\zeta\,\mathbf{d}_{\cdot 1} k_x / d_{11}`$, largest at the outer face of each angle's outermost ply, $`\zeta_\theta`$, on either side. The membrane moduli of a layup of plies of thickness $`t`$ (Section 6, with $`\mathbf{a} = \mathbf{A}^{-1}`$) and the stress in each ply angle are computed by `member_laminate`:

```math
E_x = \frac{1}{t\,a_{11}}, \qquad G_{xy} = \frac{1}{t\,a_{66}}, \qquad
\boldsymbol{\sigma}_{12}^{\theta} = \mathbf{T}_\sigma(\theta)\,\bar{\mathbf{Q}}(\theta)\left(\mathbf{a}\begin{bmatrix}N_x & 0 & N_{xy}\end{bmatrix}^T \pm \zeta_\theta\,\frac{\mathbf{d}_{\cdot 1}}{d_{11}}\,k_x\right)
```

<!-- code: member_laminate -->

The box is the part of the section between the spars, drawn as the shell model draws it (ADR-0116): each skin is the airfoil's surface moved inward along its outward normal $`\mathbf{n}`$ by half the skin's whole thickness $`h`$, plies and core, and each web is a straight wall at its chord position from the lower skin's mid-surface to the upper's. The skins' mid-surface heights are computed by `mid_surface_heights`:

```math
\begin{bmatrix}x_m \\ z_m\end{bmatrix} = \begin{bmatrix}x \\ z\end{bmatrix} - \frac{h}{2}\,\mathbf{n}
```

<!-- code: mid_surface_heights -->

The walls are cut into straight pieces, 32 on each skin and 8 on each web, and worked as one closed thin-walled cell (Megson, *Aircraft Structures for Engineering Students*, 4th ed., 2007, Chapters 16 to 18); its properties are computed by `box_section`. Each wall carries load in proportion to its stiffness per unit length, $`E_x t`$ and $`G_{xy} t`$ of its plies. The centroid and the second moments are taken round the cell, $`x`$ along the chord and $`z`$ up, from the modulus-weighted centroid:

```math
\bar{x} = \frac{\oint E t\,x\,ds}{\oint E t\,ds}, \quad \bar{z} = \frac{\oint E t\,z\,ds}{\oint E t\,ds}, \qquad
EI_{zz} = \oint E t\,(z - \bar{z})^2 ds, \quad EI_{xx} = \oint E t\,(x - \bar{x})^2 ds, \quad EI_{xz} = \oint E t\,(x - \bar{x})(z - \bar{z})\,ds
```

The lift's moment $`M`$ acts with no chordwise moment, so a cambered box bends about an inclined axis. With $`r = EI_{xz}/EI_{xx}`$, its curvature and the strain of a point are:

```math
\kappa = \frac{M}{EI}, \quad EI = EI_{zz} - \frac{EI_{xz}^2}{EI_{xx}}, \qquad \varepsilon = -\kappa\left[(z - \bar{z}) - r\,(x - \bar{x})\right], \qquad N_x = E_x t\,\varepsilon, \quad k_x = -\kappa\,(n_z - r\,n_x)
```

The walls' axis $`s`$ runs round the cell forward along the upper skin, down the front web, aft along the lower skin and up the rear web; it is the second axis of each wall's laminate, whose first is the span and whose third is the outward normal. Spanwise equilibrium of a wall, $`\partial N_x/\partial y + \partial q/\partial s = 0`$ with $`dM/dy = -V`$, gives the shear flow of a vertical shear $`V`$ in the cell cut where the upper skin meets the rear web, and the constant flow $`q_0`$ that closes the cell with no twist, so that the shear acts at the shear center $`x_{sc}`$:

```math
q_b(s) = -\frac{V}{EI}\int_0^s E t\left[(z - \bar{z}) - r\,(x - \bar{x})\right]ds, \qquad q = q_b + q_0, \quad q_0 = -\frac{\oint q_b\,ds/(G t)}{\oint ds/(G t)}, \qquad V x_{sc} = -\oint q\,(z\,e_x - x\,e_z)\,ds
```

with $`\mathbf{e}`$ the direction of $`s`$. The flow is quadratic along a straight piece and is integrated exactly by Simpson's rule. Part of the shear is carried by the skins where they slope; each web's share is the vertical force of its own flow. A torque $`T`$ about the shear center, nose up, adds a constant flow round the cell of enclosed area $`A_c`$ (inside the mid-surfaces) and twists it by $`T/GJ`$ (Bredt-Batho):

```math
q_T = -\frac{T}{2A_c}, \qquad GJ = \frac{4A_c^2}{\oint \dfrac{ds}{G\,t}}
```

The walls' own bending about their mid-surface is left out of $`EI`$: for a sandwich skin it is about $`(c/2)^2/z^2`$ of the skin's part, $`c`$ the core and $`z`$ the skin's height, 2 % on the example wing, and leaving it out raises the strains by as much. Mass is that of the walls of one side, their lengths round the cell times the plies' and the core's mass per area; the skin ahead of the front spar and behind the rear spar is in neither the stiffness nor the mass, but for the outer halves of the spar caps of Section 15. The first bending frequency is that of a uniform cantilever of mass per length $`m'`$ (Blevins, *Formulas for Natural Frequency and Mode Shape*, 1979, Table 8-1), with $`\beta_1 = 1.8751`$ the first root of $`1 + \cos\beta\cosh\beta = 0`$:

```math
f_1 = \frac{\beta_1^2}{2\pi}\sqrt{\frac{EI}{m' L^4}}
```

<!-- code: box_section -->

Each skin buckles as a flat, simply supported plate as wide as its length $`b`$ round the curve between the spars, computed by `skin_buckling_load` and `long_plate_buckling_load`: without ribs as a long plate, the lowest value of the closed form of Section 8 over the length of a half-wave (Whitney Eq. 5.80); with ribs, by the closed form of Section 8 with the rib spacing as the panel's length. $`D_{16}`$ and $`D_{26}`$ are dropped, which overstates the load of a skin with angle plies away from its mid-plane; the skin's curve, which raises the load, and the shear in the skin, which lowers it, are left out:

```math
N_{cr} = \frac{2\pi^2}{b^2}\left[\sqrt{D_{11}D_{22}} + D_{12} + 2D_{66}\right]
```

<!-- code: skin_buckling_load, long_plate_buckling_load -->

The load set against it is the skin's mean compression across the chord. For an isotropic plate whose compression falls linearly across its width to $`\psi`$ times its largest, the buckling coefficient of the largest is $`k_\sigma = 8.2/(1.05 + \psi)`$ (EN 1993-1-5, Table 4.1), so the mean compression at buckling, $`k_\sigma (1 + \psi)/2`$, stays between 3.9 and 4.0 for $`\psi`$ from 0 to 1: the mean of a varying compression buckles a plate as a uniform compression of the same size does, within 2.5 %.

### Checks of every case

The checks of every case at every station are computed by `analyze_wing`, on arrays over cases and stations; a case whose loads repeat another's is checked once. At every point of every wall, the corners and 31 points between them on each skin and 7 on each web, a wall carries the $`N_x`$ and $`k_x`$ of the moment, and the shear flow $`q(s)`$ of the shear and $`q_T`$ of the torque, added with their signs:

```math
N_{xy} = q(s) + q_T
```

Every ply angle is checked at the outer face of its outermost ply on both sides of the wall. The strength ratio $`R`$ of the weakest follows Section 5 by the criterion the envelope names. A skin's buckling ratio is its $`N_{cr}`$ over its mean compression; each web's buckling ratio is its bay's buckling shear flow over the size of the web's mean shear flow. Deflection and twist are integrated along the span by the trapezoid rule:

```math
\delta(y) = \int_0^y\!\!\int_0^{s} \kappa\,dr\,ds, \qquad \phi(y) = \int_0^y \frac{T}{GJ}\,ds
```

A margin is the ratio over a factor on the limit load, less one, at the ultimate factor and, when the envelope gives one, at the proof factor:

```math
MS = \frac{R}{FS} - 1
```

<!-- code: analyze_wing -->

A web bay between two ribs (the whole span without ribs) buckles in shear as a plate simply supported on its four edges, the web's height $`h`$ wide and the rib spacing long, but never taken longer than $`5h`$, beyond which an isotropic plate's load is within 3 % of the infinitely long one's. Its buckling shear flow is the lower of the two directions of the shear, computed by `web_shear_buckling_load`:

```math
q_{cr} = \min_{\pm}\,\lambda\!\left(\mathbf{D}_{web},\ \min(s, 5h),\ h,\ (0, 0, \pm 1)\right)
```

with $`\lambda`$ the Ritz double sine series of Section 7 (`ritz_buckling`, 14 terms a direction). A web's $`+45`$ and $`-45`$ plies are not alike in bending ($`D_{16}, D_{26} \ne 0`$), so one direction of the shear buckles the bay sooner, by about two on a $`[45/-45/0]_s`$ web, and the beam does not follow the shear's sign. Two things move a real web's buckle from this one, in opposite directions: the skins hold its top and bottom edges harder than simple supports, which raises it, and its own bending stress, spanwise compression along one edge in a lift case, is left out, which lowers it. On the example wing's former $`[45/-45/0]_s`$ web this check put the root bay's buckle at 1.09 times limit load and a large-deflection solution of the finite element model at about 1.6 (ADR-0115 amendment 2).

<!-- code: web_shear_buckling_load -->

Checks: `engine/validation/wing_cases/constructed-straight-sandwich-wing.toml`, a wing with a straight-sided airfoil worked by hand in `engine/validation/closed_forms.py` without the engine, its box one closed cell of four flat walls whose shear flow is integrated wall by wall in closed form, every face of every ply checked along each wall; the section's own sums in `engine/tests/test_wing.py` (the shear flow carries the shear at the shear center and the torque round the box, the bending load sums to the moment and to no force, a rectangular box shares the shear equally between its webs); the ply check against `first_ply_failure` of the whole laminate and, for a sandwich, ply by ply with the core between the faces; the gust formula against the regulation's printed form; the web's buckling shear flow against Timoshenko and Gere's $`k_s = 5.35 + 4(b/a)^2`$ for an isotropic plate within 2 %, and on one $`[45/-45/0]_s`$ web against CalculiX's buckling of the same flat plate within 1.2 % in both directions (ADR-0117). The finite element model of the same description is compared case by case in ADR-0117 and ADR-0115 amendment 3: on the example wing the section's bending and torsion stiffness are within 2 % and 4 % of the shell model's, its shear center within 0.3 mm, and the lowest skin margin outboard of the root +0.154 against +0.146.

### Divergence and aileron reversal

The wing's static aeroelastic checks treat it as a uniform cantilever in torsion with strip-theory lift: lift acts at the aerodynamic center, a distance $`e`$ ahead of the shear center, with the section's lift slope $`a`$. The elastic twist $`\theta(y)`$, nose up, obeys

```math
GJ\,\theta'' + q\,c\,e\,a\,\theta = -m(y), \qquad \theta(0) = 0, \quad \theta'(L) = 0
```

where $`m`$ is the moment per unit span of every other load about the shear center. The dynamic pressure at which the wing diverges, the lowest at which the equation has a solution with no load, $`\lambda L = \pi/2`$ with $`\lambda^2 = q c e a / GJ`$, is computed by `divergence_dynamic_pressure`:

```math
q_D = \left(\frac{\pi}{2L}\right)^2 \frac{GJ}{c\,e\,a}
```

A wing whose aerodynamic center is not ahead of its shear center ($`e \le 0`$) does not diverge. An aileron over $`[y_1, y_2]`$ adds $`q c\,\Delta c_l`$ of lift per unit span at the aerodynamic center and $`q c^2 \Delta c_m`$ of moment about it. The lift it adds to the flexible wing is computed by `aileron_lift`:

```math
\frac{\Delta L}{q c} = \Delta c_l\,(y_2 - y_1) - \frac{a\,q\,c\,(e\,\Delta c_l + c\,\Delta c_m)}{GJ}\int_{y_1}^{y_2}\psi\,dy
```

with $`\psi'' + \lambda^2\psi = 1`$, $`\psi(0) = 0`$, $`\psi'(L) = 0`$ the twist under a unit moment per unit span; by reciprocity of the torsion equation, the lift lost to the twist of a moment over $`[y_1, y_2]`$ is its integral there, computed by `twist_influence`:

```math
\int_{y_1}^{y_2}\psi\,dy = \frac{1}{\lambda^2}\left[y_2 - y_1 + g(y_2) - g(y_1)\right], \qquad g(y) = \frac{\sin\lambda(L - y)}{\lambda\cos\lambda L}
```

with $`\sin`$ and $`\cos`$ becoming $`\sinh`$ and $`\cosh`$ when $`\lambda^2 < 0`$, and a two-term series in $`\lambda^2`$ when $`|\lambda^2| L^2 < 10^{-6}`$. The reversal dynamic pressure, the lowest at which the aileron adds no lift, is computed by `reversal_dynamic_pressure`; it depends only on the ratio $`\Delta c_l / \Delta c_m`$, and does not occur below divergence when $`e\,\Delta c_l + c\,\Delta c_m`$ has the sign of $`\Delta c_l`$. Both are reported as equivalent airspeeds, $`V = \sqrt{2q/\rho_0}`$, beside the envelope's dive speed. Bisplinghoff, Ashley and Halfman, Aeroelasticity (1955), chapter 8; Hodges and Pierce, Introduction to Structural Dynamics and Aeroelasticity, 2nd ed. (2011), chapter 5. Not modeled: sweep, taper, the lift's drop toward the tip, and compressibility; flutter follows.

<!-- code: divergence_dynamic_pressure -->
<!-- code: aileron_lift -->
<!-- code: twist_influence -->
<!-- code: reversal_dynamic_pressure -->

Checks: `engine/tests/test_wing_aeroelastic.py` solves the same torsion equation by finite differences, written without these formulas: its lowest eigenvalue against $`q_D`$, its twist integral against `twist_influence` for $`\lambda^2`$ of both signs and near zero, and its aileron lift against `aileron_lift`, changing sign at the reversal dynamic pressure.

### Flutter estimate

Flutter is estimated on the typical section: one strip of the wing that plunges ($`h`$, down positive) and pitches ($`\theta`$, nose up) about its elastic axis, $`a\,b`$ aft of mid-chord with $`b`$ the semichord. Its mass per unit span $`m`$ has its center $`x_\theta b`$ aft of the axis and radius of gyration $`r b`$ about it; its springs are set by the wing's first bending and first torsion frequencies $`\omega_h`$ and $`\omega_\theta`$:

```math
m\ddot h + m b x_\theta \ddot\theta + k_h h = -L, \qquad m b x_\theta \ddot h + m b^2 r^2 \ddot\theta + k_\theta \theta = M
```

For harmonic motion at the reduced frequency $`k = \omega b / U`$, Theodorsen's lift and moment about the elastic axis, divided by $`\pi\rho b^3\omega^2`$ and $`\pi\rho b^4\omega^2`$ per unit $`h/b`$ and per unit $`\theta`$, are computed by `airload`:

```math
\begin{aligned}
\hat L_h &= -1 + \tfrac{2iC}{k}, & \hat L_\theta &= a + \tfrac{i}{k} + \tfrac{2C}{k^2} + \tfrac{iC(1 - 2a)}{k},\\
\hat M_h &= -a + \tfrac{2i(a + \frac12)C}{k}, & \hat M_\theta &= \tfrac18 + a^2 - \tfrac{i(\frac12 - a)}{k} + \tfrac{2(a + \frac12)C}{k^2} + \tfrac{i(a + \frac12)(1 - 2a)C}{k}
\end{aligned}
```

with Theodorsen's function $`C(k)`$ by R. T. Jones's approximation, computed by `theodorsen`, within 0.02 of the exact function:

```math
C(k) \approx 1 - \frac{0.165}{1 - 0.0455\,i/k} - \frac{0.335}{1 - 0.3\,i/k}
```

The k method gives both springs a structural damping, $`k(1 + ig)`$, and for each reduced frequency solves for $`Z = (\omega_\theta/\omega)^2(1 + ig)`$, with $`\mu = m/(\pi\rho b^2)`$ and $`\sigma = \omega_h/\omega_\theta`$:

```math
\begin{bmatrix} 1 - \hat L_h/\mu & x_\theta - \hat L_\theta/\mu \\ x_\theta + \hat M_h/\mu & r^2 + \hat M_\theta/\mu \end{bmatrix}
\begin{bmatrix} h/b \\ \theta \end{bmatrix} = Z \begin{bmatrix} \sigma^2 & 0 \\ 0 & r^2 \end{bmatrix} \begin{bmatrix} h/b \\ \theta \end{bmatrix}
```

Each root gives $`\omega = \omega_\theta/\sqrt{\operatorname{Re} Z}`$, the speed $`U = \omega b/k`$ and the damping $`g = \operatorname{Im} Z/\operatorname{Re} Z`$ the strip would need to hold that motion; the sweep runs $`k`$ from 4 down to 0.01, follows each root from one $`k`$ to the next, and the flutter speed, computed by `flutter_speed`, is the lowest at which a root's $`g`$ rises through zero. It is a true airspeed at the density given; the finite element model reads it at each altitude of the envelope as the envelope's kind of airspeed. Theodorsen, NACA Report 496 (1935); R. T. Jones, NACA Report 681 (1940); Bisplinghoff, Ashley and Halfman (1955), chapters 5 and 9; Hodges and Pierce (2011), chapter 5. An estimate only: two-dimensional air on one strip, the first bending and torsion modes alone, no compressibility, sweep or control surface, and only the mass the description holds.

<!-- code: theodorsen, airload, flutter_speed -->

Checks: `engine/tests/test_wing_flutter.py`: $`C(k)`$ at its limits and against the exact function at three reduced frequencies; the strip $`a = -1/5`$, $`x_\theta = 1/10`$, $`r^2 = 6/25`$, $`\sigma = 2/5`$, $`\mu = 20`$ flutters at $`U/(b\omega_\theta) = 2.170`$; mass moved forward, a heavier strip and thinner air each raise the speed. `fea/tests/test_wing_model.py` solves the same strip by the p-k method with the exact $`C(k)`$ from the Hankel functions, written without this module: 2.184, within 1 %.

## 14. Design rules of a stack (`layup_rules.py`)

Four rules a designer checks on a stack before any load (ADR-0123). They are rules of practice, not physics: a rule not met is a warning, nothing else in the engine reads the result, and no number of an analysis changes with it. Plies are counted, not weighed by thickness, as the rules are stated, and a fiber at $`\theta`$ is the fiber at $`\theta + 180°`$, so $`135°`$ counts as $`-45°`$ and $`-90°`$ as $`90°`$. The limits are the designer's: the least share $`s_{\min}`$ (default 10 %, at most 25 %, since four directions cannot each hold more) and the most plies of one angle in a row $`r_{\max}`$ (default 4).

The 10 % rule asks that the laminate be carried by its fibers in every direction (MIL-HDBK-17-3F, Volume 3). With $`n`$ plies and $`n_d`$ of them in direction $`d`$, it is met when

```math
\frac{n_d}{n} \ge s_{\min} \qquad \text{for each } d \in \{0°, +45°, -45°, 90°\},
```

a ply at any other angle counting only in $`n`$. It is checked by `ten_percent_rule`.

<!-- code: ten_percent_rule -->

Plies of one angle next to each other act as one thick ply, which cracks between plies more readily; the run counts across the middle of a solid laminate, where the two middle plies touch, but not across a core. The longest run, its angle and its first and last ply are computed by `in_a_row_rule`, and the rule is met when that run is at most $`r_{\max}`$. Thicker plies usually call for a smaller $`r_{\max}`$.

<!-- code: in_a_row_rule -->

Balance and symmetry are the stack's own facts of section 10 (`is_balanced`, `is_symmetric`): a balanced stack has $`A_{16} = A_{26} = 0`$, so stretching does not shear it, and a symmetric one has $`\mathbf{B} = 0`$, so stretching does not bend it. Their words, the plies at each off-axis angle without a partner and the first ply that does not mirror its own, are checked by `balance_rule` and `symmetry_rule`; a core must also sit in the middle, with as many plies on each side.

<!-- code: balance_rule, symmetry_rule -->

All four on one stack, listed from one face to the other with the core after a given ply, are checked by `layup_rules`. A wing judges its skins, spar webs and ribs this way, both halves of each with the core between them, by the limits of its file's `[design_rules]`; the wing's report lists every rule of every layup with one plain sentence and the numbers behind it.

<!-- code: layup_rules -->

Checks: `engine/tests/test_layup_rules.py`: stacks counted by hand, among them $`[0/\pm 45/90]_s`$ meeting every rule, one $`90°`$ ply in twelve (8.3 %) short of 10 % and one in ten meeting it, $`[\pm 45/0_2]_s`$ with four $`0°`$ plies across the middle, the same run broken by a core, unpaired $`+45°`$ plies, partners of another thickness, and a core off the middle; the example wing's limits changed with every analysis number the same.

## 15. Spar caps and layups that change along the span (`wing/`)

A spar cap is a strip of each skin centred on each web with a solid layup of its own, usually more plies at $`0°`$ to carry the bending (ADR-0125). Its width along the chord is the same from root to tip. Any layup, a skin, a spar web or the spar caps, may also change along the span: each zone is a stretch of the half span, from a start to an end as fractions of it, with a half stack of its own, and outside its zones the part keeps its own half stack. A rib stands at one station and has no zones. The wing is cut into stretches of constant layup wherever any part's stack changes, and each stretch has its own section, worked as in Section 13.

In a section with caps, each stretch of a skin, a cap, the panel between the caps and the other cap, lies at its own mid-surface: the airfoil's surface moved inward by half its own thickness, so a solid cap beside a cored skin lies nearer the surface. The webs run between the caps' mid-surfaces. Where a cap's mid-surface and the skin's differ, a straight step joins them, as the skin's faces close onto the cap: the shear flow goes on through it, with the skin's $`G t`$ in $`\oint ds/(G t)`$ and its line in the outline of $`A_c`$, and it carries no spanwise load, $`E t = 0`$ in the centroid and $`EI`$. The half of each cap outside the box is an open flange. It adds to the centroid and to $`EI`$, and its shear flow is nothing at its free edge and gathers along it to the corner where it meets the cell, where the whole of it joins the cell's open flow:

```math
q_f(s) = -\frac{V}{EI}\int_{\text{free edge}}^{s} E t\left[(z - \bar{z}) - r\,(x - \bar{x})\right]ds, \qquad q_b(\text{corner}^+) = q_b(\text{corner}^-) + q_f(\text{corner})
```

The cell's open flow then comes back to nothing at the cut, since the first moment of the whole section about its centroid is nothing. The flanges are open, so the closing flow $`q_0`$ and the torque's flow $`q_T`$ run round the cell only. Every point of every stretch of wall, the flanges included, is checked ply by ply as in Section 13; a step's plies are its neighbours', checked there. The skin panel that buckles is the skin between the caps' inner edges, $`b`$ its length round the curve. The mass counts each cap's whole width, both halves, while the skin outside the box is counted nowhere, so a wing with caps reads heavier than it is by the skin their outer halves replace.

The stations along the span are the equally spaced ones and every change twice, once with the section inboard of it and once with the one outboard, computed by `stations_of`. The loads of Section 13 do not depend on the section, except the torque, which each station takes about its own shear center (the stretches' shear centers differ by under a millimetre on the example). The curvature $`M/EI`$ and the rate of twist $`T/GJ`$ jump at a change, and the trapezoid rule over the two stations at one $`y`$ adds nothing, so the deflection and twist integrals of Section 13 take the jump as it is.

The first bending frequency of a wing whose section changes is that of a clamped-free beam of about 200 cubic (Hermite) elements with an edge at every change, each with its stretch's $`EI`$ and mass per length $`m'`$, the consistent mass matrix (Przemieniecki, *Theory of Matrix Structural Analysis*, 1968, Sections 5.3 and 11.3), solved as $`\mathbf{K}\mathbf{v} = \omega^2\mathbf{M}\mathbf{v}`$ for its lowest $`\omega`$; it is computed by `bending_frequency`. For an element of length $`h`$:

```math
\mathbf{k} = \frac{EI}{h^3}\begin{bmatrix}12 & 6h & -12 & 6h\\ 6h & 4h^2 & -6h & 2h^2\\ -12 & -6h & 12 & -6h\\ 6h & 2h^2 & -6h & 4h^2\end{bmatrix}, \qquad
\mathbf{m} = \frac{m' h}{420}\begin{bmatrix}156 & 22h & 54 & -13h\\ 22h & 4h^2 & 13h & -3h^2\\ 54 & 13h & 156 & -22h\\ -13h & -3h^2 & -22h & 4h^2\end{bmatrix}
```

A uniform wing keeps the closed form of Section 13, and the beam of a uniform wing cut at any station gives it again within $`2\times10^{-6}`$, the round-off of the eigenvalue. Divergence and reversal of Section 13 are worked with each stretch's section taken as the whole wing's, and the lowest dynamic pressure of each is kept, computed by `lowest_aeroelastic`. It is a simple estimate: on the safe side when one stretch is both the weaker in torsion and the one with the longer arm, and not a bound when those are different stretches.

<!-- code: stations_of, bending_frequency, lowest_aeroelastic -->

Where a stack changes, plies end: a ply drop. Three rules of practice judge it, warnings like those of Section 14, checked by `ply_drop_rules` on the two half stacks either side, listed from the outside. $`n_d`$ plies end, both halves counted, $`2\,(n_{\text{thick}} - n_{\text{thin}})`$ for half stacks of $`n_{\text{thick}}`$ and $`n_{\text{thin}}`$ plies; at most $`d_{\max}`$ should end at one place (default 2). The thickness tapers over a run-out, the drop ratio $`\rho`$ times the thickness that ends (default 20 to 1), which must fit in the thicker side's stretch of length $`L_{\text{thick}}`$, with $`t_p`$ the ply thickness:

```math
n_d \le d_{\max}, \qquad \rho\, n_d\, t_p \le L_{\text{thick}}
```

The plies that end are found by matching the thinner stack to the thicker one ply by ply from the outside, each ply of the thinner taken at the first ply of the thicker of the same angle; a stack that cannot be matched this way changes angle or order, not only ends, and is not a ply drop. The outside ply should run on over the ends of the others, so that no ply's edge is on the surface. A wing judges every change of its skins, spar webs and spar caps this way, by the limits of its file's `[design_rules]`, and lists the rules of every stretch of every part as in Section 14.

<!-- code: ply_drop_rules -->

Checks: `engine/tests/test_wing_caps.py`: a flat-sided box with caps summed by hand strip by strip (its $`EI`$, $`GJ`$ by Bredt-Batho with the steps in the loop, its enclosed area and its mass, each within $`10^{-12}`$); on NACA 2412 and 0012 boxes with caps, the shear flow with the steps put back carries a unit shear at the shear center and is nothing at every flange's free edge, and the bending load sums to the moment and to no force; zones in order, merged where alike, and the span cut where any part changes; the stations doubled at a change; the beam against the closed form; the same wing in US units. `engine/tests/test_layup_rules.py`: ply drops counted by hand, the run-out on whichever side is thicker, the outside ply ending, and a change of angle that is not a drop.

## Not modeled yet

- Moisture effects, and elastic properties that change with temperature
- Progressive ply failure and ultimate laminate strength
- Through-thickness and interlaminar stresses
- Holes and other geometry that needs finite element analysis
- Hashin failure criteria
- Ply drops in the stiffness: a change of layup is a step in the section, with no taper over the run-out; a drop's own stresses
- Buckling with clamped or free edges, of unsymmetric laminates, or after the critical load (postbuckling); transverse shear deformation in thick plates
- For a wing, in the beam: taper, sweep and twist; shear lag; ribs as load paths; the skin outside the two spars, beyond the caps; the walls' own bending stiffness and the core's in-plane stiffness; a skin's curve in its buckling; web buckling with the web's bending stress, and skin buckling under shear with compression; the core's transverse shear; relief from the wing's own weight; flaps; flutter beyond two modes on one strip, and divergence and reversal of a swept or tapered wing
