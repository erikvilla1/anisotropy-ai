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

Loads are per unit width. For a tension coupon of width $`w`$ carrying load $`P`$, $`N_x = P/w`$.

Mid-plane strain and curvature, computed by `abd_matrix` and `midplane_response`. The system is solved directly, without forming the inverse:

```math
\begin{bmatrix}\mathbf{A} & \mathbf{B}\\ \mathbf{B} & \mathbf{D}\end{bmatrix}
\begin{bmatrix}\boldsymbol{\varepsilon}^0\\ \boldsymbol{\kappa}\end{bmatrix}
= \begin{bmatrix}\mathbf{N}\\ \mathbf{M}\end{bmatrix}
```

<!-- code: abd_matrix, midplane_response -->

The inverted ABD matrix gives deformation directly from loads. Its blocks are computed by `abd_compliance` (Eqs. 7.27-7.28, where the lower-left block $`\mathbf{c} = \mathbf{b}^{T}`$); the course reader writes them as $`\boldsymbol{\alpha}`$, $`\boldsymbol{\beta}`$ and $`\boldsymbol{\delta}`$:

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

These are the equations of Daniel and Ishai Chapter 8 (printed pp. 212-217) with the moisture terms omitted; Eq. 8.20 writes the moment integral as the ply's mid-plane height times its thickness, which equals $`(z_k^2 - z_{k-1}^2)/2`$. With $`\Delta T = 1`$ and no load, the mid-plane strains are the laminate expansion coefficients (Eq. 8.33). The engine reproduces the course answer keys for curing stresses (Course Reader 5.9), an unsymmetric cure (5.13), laminate expansion coefficients, a hybrid woven/tape laminate and combined thermal and mechanical loading (validation cases `course-reader-5-9-*` and `se142-hw4-*`, `se142-hw5-*`).

Failure ratios with a temperature change hold the residual stress fixed and scale only the mechanical loads, as described under "Fixed and variable loading" (ADR-0017).

## Not modeled yet

- Moisture effects, and elastic properties that change with temperature
- Progressive ply failure and ultimate laminate strength
- Through-thickness and interlaminar stresses
- Holes and other geometry that needs finite element analysis
- Maximum strain, Tsai-Hill and Hashin failure criteria (maximum strain is what the course's failure strain allowables are for)
- Buckling: no plate dimensions, edge conditions or stability equation. The specially orthotropic simply supported plate under in-plane compression has a closed form from D and would be the first step
