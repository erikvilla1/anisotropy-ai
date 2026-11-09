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

The stack itself, before any load, as the response endpoint reports it beside the matrices (ADR-0059). Nothing here is new physics: each statement follows from the definitions of Section 3 and the textbook's classes of laminates (Daniel & Ishai Chapter 7). The thickness is the sum of the ply thicknesses, computed by `total_thickness`:

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

First-ply failure under the one loading given, every load scaling together with nothing held fixed and no temperature change, is computed by `first_ply_failure_summary` and `face_of`: maximum stress and Tsai-Hill whenever the plies have strengths, maximum strain only with strain limits and Tsai-Wu only with an explicit $`f_{12}^*`$ (Section 5, ADR-0021), the others reported as not computed with the reason; each result names the criterion, the strength ratio $`R`$, the ply (1 at the bottom), the face of that ply, the governing mode and the loads at failure $`R\,[\mathbf{N}; \mathbf{M}]`$. Without a load, or with a ply that has no strengths, nothing is evaluated and the reason is stated.

<!-- code: first_ply_failure_summary, face_of -->

## 11. Fibre tow tension (`tow.py`)

The tension test of a resin-impregnated, consolidated carbon or graphite fibre tow, ASTM D4018-23 (ADR-0073). A tow is a strand, not a laminate: the resin holds the filaments together so they load evenly (§4.5), and the area that carries the force is the fibre's. Nothing in this section uses Sections 1 to 10. The standard is read in the licensed copy; its text is not in this repository (ADR-0018 amendment 1), so each equation below names its number for a reader with their own copy.

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

The strains in $`E`$ are absolute. The standard multiplies Eq 5 by $`B = 10^{-3}`$ for a load in newtons to report GPa and lists $`\varepsilon_u`$ and $`\varepsilon_l`$ in microstrain; the two do not agree. With $`P`$ in N, $`\rho_f`$ in g/cm³ and MUL in g/m, $`P\rho_f/\mathrm{MUL}`$ is in MPa (Eq 4 with its factor $`A = 1`$); divided by a strain difference and multiplied by $`10^{-3}`$, it is in GPa only when the strains are absolute (0.005, not 5000). With microstrain the result is $`10^{6}`$ times too small. This is our reading, recorded in ADR-0073; `engine/tests/test_tow.py` works one case both ways.

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

## Not modeled yet

- Moisture effects, and elastic properties that change with temperature
- Progressive ply failure and ultimate laminate strength
- Through-thickness and interlaminar stresses
- Holes and other geometry that needs finite element analysis
- Hashin failure criteria
- Buckling with clamped or free edges, of unsymmetric laminates, or after the critical load (postbuckling); transverse shear deformation in thick plates
