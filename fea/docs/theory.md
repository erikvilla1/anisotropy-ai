# Finite element theory

This file states every equation the finite element layer uses and names the function that computes it (ADR-0029, ADR-0053). The element formulation follows K.-J. Bathe, *Finite Element Procedures*, 2nd edition (2014), Chapter 5 (formulation and calculation of isoparametric finite element matrices, and the mixed-interpolated plate elements); the plate theory follows J. M. Whitney, *Structural Analysis of Laminated Anisotropic Plates* (1987), Chapters 5 and 10; the laminate stiffness comes from the engine ([engine theory](../../engine/docs/theory.md), laminate stiffness). The kernels work in SI units throughout; a deck's units are converted once on entry (ADR-0002).

## Conventions

- The laminate x axis is the deck's global x axis, and the engine's ply angle is counted from it, counterclockwise, as in ADR-0004. A coupon states its ply angles from its length axis, global y (ADR-0065): the load axis in tension and compression, the span in bending, the length of a plate, so a stated 0-degree ply has its fibres along the pull. A spec's `fibre_angles` are therefore its stated angles plus 90 degrees, brought into (-90, 90]; the deck we write carries the stated angles on its layer lines under an `*Orientation` whose local direction 1 is +y. Our deck reader accepts any right-handed frame in the plate's plane (a unit `a` in the x-y plane, `b` the normal crossed with `a`, a rotation about axis 3 only) and records the angle from global x to local 1 as the section's `rotation_deg`; the engine ply of a layer is at the layer angle plus that rotation (`model.fibre_angles`), and every label prints the layer angle as the deck states it (`Section.angles_deg`). A deck without an orientation counts from x, as the hand-made check decks do.
- In the membrane kernel (the sections from what the membrane model represents to first-ply failure) each node has two degrees of freedom, $`u`$ along x and $`v`$ along y, Abaqus dofs 1 and 2; there are no out-of-plane or rotational degrees of freedom. The flat shell kernel (the flat shell section below) adds $`w`$ along z and the rotations $`\theta_x`$, $`\theta_y`$ about the x and y axes, Abaqus dofs 3 to 5; the drilling rotation, dof 6, is never carried.
- Strain is the membrane (midplane) strain $`\boldsymbol{\varepsilon} = [\varepsilon_x, \varepsilon_y, \gamma_{xy}]^T`$ with engineering shear; the shell adds the curvature $`\boldsymbol{\kappa}`$ and the transverse shear strain $`\boldsymbol{\gamma} = [\gamma_{xz}, \gamma_{yz}]^T`$, engineering too.
- Section forces are resultants per unit width, $`\mathbf{N} = [N_x, N_y, N_{xy}]^T`$ in N/m, what Abaqus reports as SF; the shell adds the moments $`\mathbf{M}`$ in N (Abaqus SM) and the transverse shear forces $`\mathbf{Q}`$ in N/m.
- A uniform pressure is positive against the element normal, which is $`+z`$ for counterclockwise nodes: a positive pressure presses on the top face and pushes the plate toward $`-z`$. A deck states it in its solver's own sign (Section 8).
- Element nodes are listed counterclockwise, as Abaqus S4-family elements list them.

## 1. What the membrane model represents, and when it refuses

Classical laminate theory couples membrane and bending through $`\mathbf{B}`$: $`\mathbf{N} = \mathbf{A}\boldsymbol{\varepsilon} + \mathbf{B}\boldsymbol{\kappa}`$. For a symmetric layup $`\mathbf{B} = \mathbf{0}`$, so an in-plane problem with no transverse load and no prescribed rotation has the trivial bending solution and reduces to plane stress of a plate with stiffness $`\mathbf{A}`$. The kernel therefore requires

```math
\lVert \mathbf{B} \rVert \le 10^{-9}\, \lVert \mathbf{A} \rVert\, h ,
```

with $`h`$ the laminate thickness, and refuses a section whose layup breaks it; the plies and $`\mathbf{A}`$ of a section are computed by `section_stiffness`, which calls the engine's `abd_matrices`.

<!-- code: section_stiffness -->

The flat arrays the kernel works on, the nodes of every instance followed by the assembly's reference nodes, each element's node indices and its section, are computed by `mesh_from_deck`.

<!-- code: mesh_from_deck -->

The reference solver is not a membrane. CalculiX expands a composite S8R shell into one twenty-node brick with the layers as integration-point materials, and its law is three-dimensional: the ply's thickness strain is $`\varepsilon_{33} = -\nu_{13}\sigma_{11}/E_1 - \nu_{23}\sigma_{22}/E_2 + \sigma_{33}/E_3`$. Plies at different angles want different $`\varepsilon_{33}`$ under the same in-plane state, but one brick has one quadratic displacement across the whole thickness, so the difference is taken up by a through-thickness stress $`\sigma_{33}`$ that feeds back into $`\sigma_{11}`$ and $`\sigma_{22}`$. Plane stress has no such term. A CalculiX deck meant to be compared with the kernel, or with an Abaqus LAMINA model, therefore states `plane_stress = true`, which writes $`\nu_{13} = \nu_{23} = 0`$ and makes the brick's in-plane response the plane-stress one; $`E_3`$, $`G_{13}`$ and $`G_{23}`$ stay as stated (ADR-0030, amendment 1).

## 2. The bilinear quadrilateral (`membrane.py`)

In natural coordinates $`(\xi, \eta) \in [-1, 1]^2`$ the four nodes sit at $`(\xi_i, \eta_i) = (-1, -1), (1, -1), (1, 1), (-1, 1)`$, counterclockwise. The shape functions (Bathe Eq. 5.18 for the two-dimensional case), computed by `shape_functions`:

```math
N_i(\xi, \eta) = \tfrac14 (1 + \xi_i \xi)(1 + \eta_i \eta), \qquad i = 1, \dots, 4 .
```

<!-- code: shape_functions -->

Their derivatives with respect to the natural coordinates, computed by `shape_derivatives`:

```math
\frac{\partial N_i}{\partial \xi} = \tfrac14 \xi_i (1 + \eta_i \eta), \qquad
\frac{\partial N_i}{\partial \eta} = \tfrac14 \eta_i (1 + \xi_i \xi).
```

<!-- code: shape_derivatives -->

The geometry is interpolated with the same functions, $`x = \sum_i N_i x_i`$, $`y = \sum_i N_i y_i`$, so the Jacobian of the map from natural to physical coordinates, computed by `jacobian`, is

```math
\mathbf{J} = \begin{bmatrix} \partial x / \partial \xi & \partial y / \partial \xi \\ \partial x / \partial \eta & \partial y / \partial \eta \end{bmatrix}
= \begin{bmatrix} \partial N_i / \partial \xi \\ \partial N_i / \partial \eta \end{bmatrix} \begin{bmatrix} x_i & y_i \end{bmatrix}.
```

<!-- code: jacobian -->

Physical derivatives follow from $`[\partial N_i / \partial x,\ \partial N_i / \partial y]^T = \mathbf{J}^{-1} [\partial N_i / \partial \xi,\ \partial N_i / \partial \eta]^T`$, and the strain-displacement matrix for the element displacement vector $`\mathbf{u}_e = [u_1, v_1, \dots, u_4, v_4]^T`$ is

```math
\boldsymbol{\varepsilon} = \mathbf{B}\,\mathbf{u}_e, \qquad
\mathbf{B} = \begin{bmatrix}
\partial N_1 / \partial x & 0 & \cdots & \partial N_4 / \partial x & 0 \\
0 & \partial N_1 / \partial y & \cdots & 0 & \partial N_4 / \partial y \\
\partial N_1 / \partial y & \partial N_1 / \partial x & \cdots & \partial N_4 / \partial y & \partial N_4 / \partial x
\end{bmatrix},
```

computed by `strain_displacement`, which also returns $`\det \mathbf{J}`$ and refuses an element where $`\det \mathbf{J} \le 0`$ at an integration point (nodes listed clockwise, or a degenerate shape).

<!-- code: strain_displacement -->

The element stiffness is the plane-stress integral with the laminate membrane stiffness in place of a thickness times a material matrix (Bathe Eq. 5.27 with $`\mathbf{C} \to \mathbf{A}`$ and unit thickness, since $`\mathbf{A}`$ already integrates through the thickness), evaluated with the 2 by 2 Gauss rule, points $`\pm 1/\sqrt{3}`$ and unit weights (Bathe Section 5.5.3):

```math
\mathbf{k} = \int_{-1}^{1}\!\int_{-1}^{1} \mathbf{B}^T \mathbf{A}\, \mathbf{B}\, \det\mathbf{J}\; d\xi\, d\eta
\approx \sum_{g=1}^{4} w_g\, \mathbf{B}_g^T \mathbf{A}\, \mathbf{B}_g\, \det\mathbf{J}_g ,
```

computed by `element_stiffness`. The integration is exact for a rectangular element. $`\mathbf{k}`$ is symmetric and has exactly three zero eigenvalues, the two translations and the rotation.

<!-- code: element_stiffness -->

## 3. Constraints and assembly

Degrees of freedom are numbered $`2i`$ and $`2i + 1`$ for node $`i`$. A kinematic coupling with the reference node's rotations fixed makes every coupled node translate with the reference node:

```math
u_s = u_r, \qquad v_s = v_r \quad \text{for every coupled node } s,
```

so each coupled dof is aliased to the reference dof before assembly and the reference node's reaction is the sum over the coupled region, as Abaqus reports RF at a reference node. Prescribed displacements from `*Boundary` on dofs 1 and 2 and concentrated loads from `*Cload` are collected on the aliased (reduced) dofs; two prescriptions that reach the same reduced dof with different values are refused, as is a node that belongs to no element and drives no coupling. All of this is computed by `constraint_map`.

<!-- code: constraint_map -->

The global stiffness is the sum of the element matrices scattered through the reduced dof numbers, stored sparse, computed by `assemble`:

```math
\mathbf{K} = \sum_e \mathbf{L}_e^T \mathbf{k}_e \mathbf{L}_e .
```

<!-- code: assemble -->

## 4. Solution and reactions

With dofs partitioned into free ($`f`$) and prescribed ($`p`$), the linear system $`\mathbf{K}\mathbf{u} = \mathbf{f}`$ gives

```math
\mathbf{K}_{ff}\, \mathbf{u}_f = \mathbf{f}_f - \mathbf{K}_{fp}\, \mathbf{u}_p ,
```

solved by a sparse LU factorization; a singular $`\mathbf{K}_{ff}`$ means a free rigid-body motion or a disconnected region and is refused. The reactions are the residual at the prescribed dofs,

```math
\mathbf{r} = \mathbf{K}\mathbf{u} - \mathbf{f} ,
```

reported at the representative node of each prescribed dof (the reference node for a coupled region) and zero elsewhere; the residual at free dofs is roundoff and is returned so a test can bound it. In equilibrium the sum of all reactions equals minus the applied loads. The solve is computed by `solve_membrane`.

<!-- code: solve_membrane -->

## 5. Recovery

The membrane strain of an element is $`\boldsymbol{\varepsilon} = \mathbf{B}(\xi, \eta)\, \mathbf{u}_e`$. It is evaluated at the centroid $`(0, 0)`$, which is where a reduced-integration S4R element carries its single in-plane integration point, and at the four Gauss points; both are computed by `element_strains`. Because the model is a membrane, the midplane strain is the strain at every through-thickness position (Abaqus SE).

<!-- code: element_strains -->

The section forces are $`\mathbf{N} = \mathbf{A}\boldsymbol{\varepsilon}`$ at the centroid, computed by `section_forces`.

<!-- code: section_forces -->

## 6. Ply stresses in material axes

A membrane state has no curvature, so every ply of an element carries the element's strain $`\boldsymbol{\varepsilon}`$. Each ply's stress in laminate axes and its strain and stress in material axes follow from the engine's ply recovery with $`\boldsymbol{\kappa} = \mathbf{0}`$ ([engine theory](../../engine/docs/theory.md), response to loads, ply surface recovery):

```math
\boldsymbol{\sigma}_{xy}^{(k)} = \bar{\mathbf{Q}}^{(k)} \boldsymbol{\varepsilon}, \qquad
\boldsymbol{\varepsilon}_{12}^{(k)} = \mathbf{T}_\varepsilon(\theta_k)\, \boldsymbol{\varepsilon}, \qquad
\boldsymbol{\sigma}_{12}^{(k)} = \mathbf{T}_\sigma(\theta_k)\, \boldsymbol{\sigma}_{xy}^{(k)} ,
```

with the bottom and top faces of a ply equal, so one value per ply is kept, bottom ply first. This is computed by `element_ply_states`, which calls the engine's `ply_surfaces`. Abaqus writes three section points per layer (Simpson); in a membrane state all three equal this one value, which is itself a check on a comparison.

<!-- code: element_ply_states -->

The von Mises stress of a ply's in-plane state, $`\sigma_\mathrm{M} = \sqrt{\sigma_1^2 - \sigma_1\sigma_2 + \sigma_2^2 + 3\tau_{12}^2}`$, is an invariant, the same in material or laminate axes, and is what Abaqus reports as S-Mises at a shell section point. It is computed by `ply_mises` for comparison records only; the engine's failure criteria, not Mises, judge a ply.

<!-- code: ply_mises -->

The other invariants Abaqus prints at a shell section point are taken from the same plane state, with the stress through the thickness zero. The in-plane principal stresses are $`\sigma_\mathrm{I,II} = \tfrac{1}{2}(\sigma_1 + \sigma_2) \pm \sqrt{\tfrac{1}{4}(\sigma_1 - \sigma_2)^2 + \tau_{12}^2}`$; with the zero beside them they are ordered as the maximum, middle and minimum principal stresses. Tresca is the largest of the three less the smallest, so it reaches the zero when both in-plane principals have the same sign, and the pressure is $`p = -\tfrac{1}{3}(\sigma_1 + \sigma_2)`$. They are computed by `ply_invariants` as comparison quantities beside Mises (ADR-0066 amendment 2), never as a ply's failure; Abaqus 2025 orders them the same way at a shell section point, the zero among them, and its Tresca, pressure and Mises at a layer are these (`fea/checks/abaqus-conventions.toml`).

<!-- code: ply_invariants -->

## 7. First-ply failure

The strength ratio $`R`$ of a ply is the factor on its stress at which the chosen criterion is met; the engine defines it for maximum stress, maximum strain, Tsai-Hill and Tsai-Wu ([engine theory](../../engine/docs/theory.md), failure) and exposes the per-face dispatch as `face_strength_ratio`, which the kernel calls with the ply's stress as the scaled part and nothing held. Over the mesh the smallest ratio is the first-ply-failure factor: the problem is linear, so the applied displacement or load multiplied by this factor fails that ply of that element first,

```math
\lambda_{\mathrm{FPF}} = \min_{e,\,k} R^{(e,k)} ,
```

computed by `strength_ratios`, which also returns every ratio and governing mode and the element and ply that govern. Identical plies in a uniform state tie exactly; ratios within a relative $`10^{-9}`$ of the minimum count as tied and the first element in deck order, then the bottom-most ply, is reported, so the location is decided by position and not by roundoff. The Tsai-Wu interaction term $`f_{12}^*`$ comes from the deck's `*Fail Stress` sixth value when every material states the same one, computed by `deck_f12_star`; without it Tsai-Wu is refused, as the engine refuses it (ADR-0021). Maximum strain is refused when no strain limits exist, since an Abaqus deck carries none. First-ply failure is the onset of damage in one ply, not the coupon's ultimate strength.

<!-- code: strength_ratios, deck_f12_star -->

The answer a result gives is read from these factors (ADR-0085). By each criterion a ply fails at the applied loading when its factor is at most one, the failure index $`1/\lambda_{\mathrm{FPF}}`$ having reached one; otherwise the loading at first-ply failure is the factor times what is applied, and the force the grip carries then is the factor times its reaction, since every quantity of a linear model scales with the loading (a plate's every load together),

```math
u_{\mathrm{FPF}} = \lambda_{\mathrm{FPF}}\,u_{\mathrm{applied}}, \qquad F_{\mathrm{FPF}} = \lambda_{\mathrm{FPF}}\,F_{\mathrm{reaction}} ,
```

computed by `answer_of`. The answer is read over the gauge section when the coupon has one, since a test coupon is accepted when it breaks there. The gauge section is read where the mesh does not set the value (ADR-0108): the elements of the `Gauge` set whose centroid is at least a stand-off $s = \tfrac{1}{4}\min(W, L_g)$ from each tab line, with $W$ the coupon's width and $L_g$ the length between the tab lines, computed by `gauge_reading`. A tab line is the innermost row of the nodes a grip moves as one body, whether its coupling is moved a set distance or pushed by a force (ADR-0108 amendment 1). The corner where a tab line meets a free edge is a point where the model's stress has no finite value, so an element beside it reads higher on every finer mesh; a quarter width is past the zone where that corner sets the smallest strength ratio, and the convergence study of Section 6.4 reports on every run whether the gauge factor has settled. A failure that comes earlier at the clamped edge of a grip or inside the stand-off, where the stress grows as the mesh is refined, is reported beside the answer, never as the answer. A coupon without a gauge section, a plate or a bending coupon, is answered over the whole model. The basis and its earliest criterion, and the largest ply stresses on the same basis, each ply's in its fibre axes with tension and compression apart, are computed by `verdict_of` and `ply_extremes`.

<!-- code: gauge_reading, answer_of, verdict_of, ply_extremes -->

The working behind the answer (ADR-0103) is this chain written out for the first ply to fail by maximum stress and by Tsai-Hill, on the answer's basis: the ply's strain in its fibre axes, its stress as $`\boldsymbol{\sigma} = \mathbf{Q}\,\boldsymbol{\varepsilon}`$ with the engine's reduced stiffness, the criterion's ratio, and the loading at first-ply failure. Each step holds its formula, the formula with the values in place and the result; values are put in to six significant figures and results are written to four, so a step repeated by hand meets its result. It is no second calculation of the answer. A chain is written only when the stiffness times the stored strain gives the stored stress and the engine's criterion, called again on that stress, gives the stored factor, each to a relative $`10^{-9}`$; this is checked by `working_of`. A stress that is zero to roundoff is written as zero and sets no limit.

<!-- code: working_of -->

## 8. The flat shell: bending, transverse shear and pressure (`shell.py`)

The membrane of the sections above stays the kernel for the in-plane coupons; every result it gives is pinned by the cases and records above. A deck that bends, carries a pressure, prescribes or loads a degree of freedom out of the plane, or has an unsymmetric layup goes to the flat shell of this section (ADR-0053), which keeps the same mesh, the same four-node element and the same engine laminate law. Which kernel a deck gets is computed by `needs_shell`, the dispatch is computed by `solve_deck`, and what the membrane refuses when it is asked directly is checked by `membrane_limits`.

<!-- code: needs_shell, solve_deck, membrane_limits -->

### 8.1 Kinematics and the laminate law

Each node carries five degrees of freedom, $`u, v, w, \theta_x, \theta_y`$: the translations along x, y, z and the rotations about the x and y axes, Abaqus dofs 1 to 5. The drilling rotation, dof 6, has no stiffness in a flat plate and is dropped (a boundary on it is noted, a load on it refused). The displacement through the thickness is that of the first-order shear deformation theory (Whitney, *Structural Analysis of Laminated Anisotropic Plates*, 1987, Eq. 10.1, written with the rotations about the axes, $`\psi_x = \theta_y`$ and $`\psi_y = -\theta_x`$):

```math
u(x, y, z) = u_0 + z\,\theta_y, \qquad v(x, y, z) = v_0 - z\,\theta_x, \qquad w(x, y, z) = w ,
```

so the in-plane strain is $`\boldsymbol{\varepsilon} = \boldsymbol{\varepsilon}_0 + z\,\boldsymbol{\kappa}`$ with the membrane strain of the bilinear quadrilateral and the curvatures (Whitney Eqs. 10.2 and 10.3)

```math
\boldsymbol{\kappa} = \begin{bmatrix} \kappa_x \\ \kappa_y \\ \kappa_{xy} \end{bmatrix}
= \begin{bmatrix} \partial \theta_y / \partial x \\ -\,\partial \theta_x / \partial y \\ \partial \theta_y / \partial y - \partial \theta_x / \partial x \end{bmatrix},
\qquad
\boldsymbol{\gamma} = \begin{bmatrix} \gamma_{xz} \\ \gamma_{yz} \end{bmatrix}
= \begin{bmatrix} \partial w / \partial x + \theta_y \\ \partial w / \partial y - \theta_x \end{bmatrix}
```

the transverse shear strains (Whitney Eq. 10.4), constant through the thickness. The section forces follow the engine's laminate law with $`\mathbf{B}`$ kept ([engine theory](../../engine/docs/theory.md), laminate stiffness; Whitney Eq. 10.5) and the shear law of Whitney Eqs. 10.6 and 10.7:

```math
\mathbf{N} = \mathbf{A}\boldsymbol{\varepsilon}_0 + \mathbf{B}\boldsymbol{\kappa}, \qquad
\mathbf{M} = \mathbf{B}\boldsymbol{\varepsilon}_0 + \mathbf{D}\boldsymbol{\kappa}, \qquad
\mathbf{Q} = \mathbf{H}\boldsymbol{\gamma}, \qquad
\mathbf{H} = k \sum_{\text{plies}} t_k \begin{bmatrix} \bar{Q}_{55} & \bar{Q}_{45} \\ \bar{Q}_{45} & \bar{Q}_{44} \end{bmatrix}_k ,
```

with $`\bar{Q}_{55} = G_{13} c^2 + G_{23} s^2`$, $`\bar{Q}_{44} = G_{13} s^2 + G_{23} c^2`$, $`\bar{Q}_{45} = (G_{13} - G_{23})\, c\, s`$ for a ply at angle $`\theta`$ ($`c = \cos\theta`$, $`s = \sin\theta`$) and the shear correction factor $`k = 5/6`$, Reissner's value (Whitney Section 10.4 lists 5/6, $`\pi^2/12`$ and 2/3 as the values in use; 5/6 is a stated choice, applied to every laminate alike). $`\mathbf{M}`$ is the moment per unit width in N and $`\mathbf{Q}`$ the transverse shear force per unit width in N/m. A lamina must state $`G_{13}`$ and $`G_{23}`$; an isotropic material takes both equal to $`G`$. The transverse shear stiffness is computed by `transverse_shear_stiffness`, and the section with $`\mathbf{A}`$, $`\mathbf{B}`$, $`\mathbf{D}`$ and $`\mathbf{H}`$ is computed by `shell_section_stiffness`.

<!-- code: transverse_shear_stiffness -->

<!-- code: shell_section_stiffness -->

### 8.2 The MITC4 element

The element is the bilinear quadrilateral of the membrane with the five dofs per node, and the element dof vector is $`\mathbf{u}_e = [u_1, v_1, w_1, \theta_{x1}, \theta_{y1}, \dots, \theta_{y4}]^T`$. With the physical derivatives $`\partial N_i / \partial x`$ and $`\partial N_i / \partial y`$ of the bilinear quadrilateral, the membrane strain is $`\boldsymbol{\varepsilon}_0 = \mathbf{B}_m \mathbf{u}_e`$ and the curvature $`\boldsymbol{\kappa} = \mathbf{B}_b \mathbf{u}_e`$, with the rows of $`\mathbf{B}_m`$ computed by `membrane_rows` and the rows of $`\mathbf{B}_b`$ computed by `bending_rows`:

```math
\mathbf{B}_{b,i} = \begin{bmatrix} 0 & 0 & 0 & 0 & \partial N_i / \partial x \\ 0 & 0 & 0 & -\partial N_i / \partial y & 0 \\ 0 & 0 & 0 & -\partial N_i / \partial x & \partial N_i / \partial y \end{bmatrix}.
```

<!-- code: membrane_rows -->

<!-- code: bending_rows -->

A displacement-based bilinear plate element locks as the plate gets thin, because the bilinear $`w`$ cannot make $`\boldsymbol{\gamma}`$ vanish while bending. The MITC4 element of Bathe and Dvorkin (K.-J. Bathe, *Finite Element Procedures*, 2nd ed., 2014, Chapter 5, the mixed-interpolated plate elements) interpolates the transverse shear strains from their values at the edge midpoints instead. In natural coordinates the covariant shear strains of the bilinear fields are

```math
\gamma_\xi = \frac{\partial w}{\partial \xi} + \frac{\partial x}{\partial \xi}\theta_y - \frac{\partial y}{\partial \xi}\theta_x, \qquad
\gamma_\eta = \frac{\partial w}{\partial \eta} + \frac{\partial x}{\partial \eta}\theta_y - \frac{\partial y}{\partial \eta}\theta_x ,
```

computed by `covariant_shear_rows` at a point. The assumed field takes $`\gamma_\xi`$ at the midpoints A $`(0, 1)`$ and C $`(0, -1)`$ and $`\gamma_\eta`$ at D $`(1, 0)`$ and B $`(-1, 0)`$, and interpolates each linearly across the element,

```math
\gamma_\xi(\xi, \eta) = \tfrac12 (1 + \eta)\, \gamma_\xi^A + \tfrac12 (1 - \eta)\, \gamma_\xi^C, \qquad
\gamma_\eta(\xi, \eta) = \tfrac12 (1 + \xi)\, \gamma_\eta^D + \tfrac12 (1 - \xi)\, \gamma_\eta^B ,
```

and the Cartesian strains follow from $`[\gamma_\xi, \gamma_\eta]^T = \mathbf{J}\,[\gamma_{xz}, \gamma_{yz}]^T`$ with the Jacobian of the bilinear quadrilateral. The rows of the resulting $`\mathbf{B}_s`$, $`\boldsymbol{\gamma} = \mathbf{B}_s \mathbf{u}_e`$, are computed by `shear_rows`. On a pure bending field $`w = -\kappa x^2 / 2`$, $`\theta_y = \kappa x`$, the tied strains vanish at every point, which the displacement-based element cannot do.

<!-- code: covariant_shear_rows -->

<!-- code: shear_rows -->

The element stiffness, with the 2 by 2 Gauss rule of the bilinear quadrilateral and the laminate matrices of the shell's kinematics and laminate law above, is computed by `element_stiffness_shell`:

```math
\mathbf{k}_e = \sum_{g} w_g\, \det \mathbf{J}_g \left( \mathbf{B}_m^T \mathbf{A} \mathbf{B}_m + \mathbf{B}_m^T \mathbf{B} \mathbf{B}_b + \mathbf{B}_b^T \mathbf{B} \mathbf{B}_m + \mathbf{B}_b^T \mathbf{D} \mathbf{B}_b + \mathbf{B}_s^T \mathbf{H} \mathbf{B}_s \right).
```

It is symmetric and has exactly six zero eigenvalues: three translations, the two tilts and the in-plane rotation; no spurious mode.

<!-- code: element_stiffness_shell -->

A uniform pressure $`p`$ on an element (`*Dload` with the P label) becomes the consistent nodal forces on $`w`$, computed by `pressure_loads`:

```math
f_{w,i} = -\,p \sum_g w_g\, \det \mathbf{J}_g\, N_i(\xi_g, \eta_g) ,
```

the sign being positive against the element normal, which is $`+z`$ for counterclockwise nodes: the pressure presses on the top face, as Abaqus's `*Dsload` P on a shell's SPOS face does. The P label of `*Dload` on a shell element is positive along the normal in Abaqus and in CalculiX alike (Abaqus 2025, ADR-0053 amendment 1; CalculiX, run on 2026-10-28, `fea/checks/calculix-conventions.toml`, `pressure_direction`), so both decks write $`-p`$ and the deck reader takes a `*Dload` P as $`-p`$.

<!-- code: pressure_loads -->

### 8.3 Constraints, assembly and solution

Degrees of freedom are numbered $`5i`$ to $`5i + 4`$ for node $`i`$. A kinematic coupling aliases every coupled dof the coupling names (dofs 1 to 5; dof 6 is dropped) to the reference node's, so a coupled edge translates and tilts with its reference node and the reference node's reaction carries the summed forces and moments. Prescribed values on dofs 1 to 5, concentrated loads on dofs 1 to 5 (forces in N, moments in N m) and the pressure forces are collected on the reduced dofs, with the same conflict and detachment refusals as the membrane's constraints and assembly; all of this is computed by `constraint_map_shell`, and the sparse global stiffness is computed by `assemble_shell`. The partition, the singularity checks and the reactions as the residual at the prescribed dofs are those of the membrane's solution. $`\mathbf{K}_{ff}`$ is symmetric and positive definite once the plate is held, so its sparse LU factors are taken with the ordering for a symmetric pattern and each pivot kept on the diagonal (SuperLU's symmetric mode, ADR-0073 amendment 2), which fills the factors less than the general ordering; they are computed by `factor_stiffness`. Every element's rows and stiffness are formed at once on stacked arrays, by the operations of the single-element functions above in the same order (ADR-0073 amendment 2). A plate whose translation along z or whose tilts are nowhere held is refused with that message. The solve is computed by `solve_shell`.

<!-- code: constraint_map_shell -->

<!-- code: assemble_shell -->

<!-- code: factor_stiffness -->

<!-- code: solve_shell -->

### 8.4 Recovery with faces

At every element's centroid the membrane strain, the curvature and the transverse shear strain are $`\mathbf{B}_m \mathbf{u}_e`$, $`\mathbf{B}_b \mathbf{u}_e`$ and $`\mathbf{B}_s \mathbf{u}_e`$, computed by `element_states`; the section forces, moments and shear forces follow from the shell's laminate law above. Because the curvature is not zero, each ply's strain differs between its bottom and top face, $`\boldsymbol{\varepsilon}(z) = \boldsymbol{\varepsilon}_0 + z\,\boldsymbol{\kappa}`$, so the ply recovery of the membrane (ply stresses in material axes) keeps both faces of every ply (the engine's `ply_surfaces` with the element's curvature) and the strength ratios of first-ply failure are evaluated on each face; the first ply to fail is named with its face, and ties are broken by element, then ply, then the bottom face. A membrane state keeps one value per ply as before.

<!-- code: element_states -->

## 9. The quantities of a test standard (`test_quantities.py`)

A coupon that names a test standard, or states a strain measurement, gets the numbers the standard reduces a test to (ADR-0072), each from the solved model by the standard's own formula. The cross-section the standards divide by disregards a hole, computed by `gross_area`, and through the hole of an open-hole coupon it is the net section, computed by `net_area`:

```math
A = w\,h \quad\text{(D3039 §11.2.2, C1869 Eq. 2)}, \qquad A_{\mathrm{NS}} = (w - D)\,h \quad\text{(C1869 Eq. 5)} ,
```

with $`h`$ the plies times the ply thickness. The stress is the force the coupon carries along its length over that area, computed by `engineering_stress` (D3039 Eq. 6, C1869 Eq. 1); the force is the moving grip's reaction under a displacement and the applied total under a force. The strain measurement is modelled by two nodes on the coupon's centre line at its two ends, $`y = L/2 \mp L_g/2`$, where the form's mesh puts a node row; its strain is their change of distance over their distance, computed by `extensometer_strain` (D3039 Eq. 7):

```math
\varepsilon = \frac{v_{\mathrm{top}} - v_{\mathrm{bottom}}}{y_{\mathrm{top}} - y_{\mathrm{bottom}}} .
```

The chord modulus between the strains $`\varepsilon_1 = 1000`$ and $`\varepsilon_2 = 3000`$ microstrain (D3039 Table 3, Eq. 8) is computed by `chord_modulus`. The model is linear, so the stress at a strain is the solved stress scaled by the ratio of the strains, and the chord equals $`\sigma/\varepsilon`$ whatever the range; the stresses and forces at the two ends are reported for the laboratory's load range. Poisson's ratio is minus the transverse strain over the longitudinal one, computed by `poisson_ratio` (D3039 Eq. 9), the transverse strain from the edge nodes across the width at mid-length; an open-hole coupon has none, its mid-length section being the hole's:

```math
E^{\mathrm{chord}} = \frac{\sigma(\varepsilon_2) - \sigma(\varepsilon_1)}{\varepsilon_2 - \varepsilon_1}, \qquad \nu = -\frac{\varepsilon_t}{\varepsilon_l} .
```

ASTM D638 reduces the same record by the same formulas in its own words, the standard's words computed by `reduction_of` from the standard the coupon names (ADR-0075): its modulus of elasticity is the slope of the initial straight line over any segment of it (§11.4), read here between $`\varepsilon_1 = 500`$ and $`\varepsilon_2 = 2500`$ microstrain, the axial strains of its A3.9.8; its area is the least original cross-section (§11.2), on a dog-bone the narrow section's width times the thickness; its Poisson's ratio is A3.10's, the same ratio. On a linear model the slope is $`\sigma/\varepsilon`$ whichever standard reads it. Both are set beside the laminate's $`E_y`$ and $`\nu_{yx}`$ from the engine's ABD, where the coupon's length is $`y`$ (ADR-0065); for an isotropic material these are its own $`E`$ and $`\nu`$. The first-ply-failure factor of the first-ply failure section scales the force, the stresses and the strain to the load at which the first ply fails; that stress on the gross and the net area is a first-ply-failure stress, never the ultimate strength the standards take at a test's maximum force (D3039 Eq. 5, C1869 Eq. 3 and 4), which a linear model does not reach. The block, in the stated units, is computed by `method_summary`.

<!-- code: gross_area, net_area, engineering_stress, extensometer_strain, chord_modulus, poisson_ratio, reduction_of, method_summary -->

## 10. The wing in CalculiX (`wing_model.py`)

The wing generator's finite element check (ADR-0117) builds a CalculiX model of a whole half wing from the same description as its hand calculation (the engine's theory, "Wing analysis"). CalculiX solves it; this package writes the deck, puts the loads on and reads the plies' stresses back through the engine's strength ratios, so every margin is still the engine's (ADR-0001, ADR-0067).

### 10.1 The model

The shape's quadrilateral shell mesh (ADR-0116) becomes eight-node S8R shells, CalculiX's only composite shell (ADR-0030), each carrying its part's whole layup as layers: the face plies, the core, the face plies again. CalculiX 2.21 in the solver image stops on a section of more than 13 layers, so a longer stack has its neighbouring plies of one angle joined into one layer of their summed thickness, the same stiffness with its stresses read at two points through the pair (ADR-0117 amendment 1). A skin's and a web's 0 degree direction is the span and a rib's is the chord; a ply at $`\theta`$ turns from it about the element's normal. The skins are curved, so the elements are grouped by the direction of their normal in steps of 2 degrees and each group gets its own orientation, which keeps every fibre within one degree of where it should lie; the groups are computed by `orientation_groups`. The ply's out-of-plane constants follow ADR-0090 ($`E_3 = E_2`$, $`G_{13} = G_{12}`$, $`G_{23} = E_2/3`$, $`\nu_{13} = \nu_{23} = 0`$); the core's in-plane modulus is its through-thickness one, a thousand times below the faces', so it does not change the answer.

The skins run round the whole airfoil, as the shape draws them, or only between the spars (`skins = "box"`), the hand calculation's box. The root is clamped: every node at $`y = 0`$ in all six freedoms.

### 10.2 The loads by superposition

The model is solved once for each of four load patterns: the hand calculation's spanwise lift for 1 N on the half wing, a uniform pitching moment of 1 N·m per metre, and the aileron's lift and moment of 1 N and 1 N·m per metre over its span. The spanwise lift is Schrenk's, the mean of a uniform and an elliptical load, computed by `schrenk_lift`:

```math
\ell(y) = \frac12\left(\frac{4}{\pi L}\sqrt{1 - (y/L)^2} + \frac1L\right) ,
```

with $`L`$ the half span. Across the chord, the load on a strip from $`x_0`$ to $`x_1`$ (the airfoil's ends, or the spars' for the box) is linear, with its resultant $`\ell`$ at the aerodynamic center $`x_{ac}`$ and its moment $`m`$ about it, nose up positive; with $`w = x_1 - x_0`$ and $`\bar x = (x_0 + x_1)/2`$, computed by `strip_pressure`:

```math
p(x) = \frac{\ell}{w} + \beta\,(x - \bar x), \qquad \beta = \frac{12\left[\ell\,(x_{ac} - \bar x) - m\right]}{w^3} .
```

Half of it goes on each skin, as consistent nodal forces $`f_i = \tfrac12\int N_i\,p\,dA`$ over each element's plan area with a three-point Gauss rule (twelve by twelve cells where an element straddles the aileron's end), computed by `load_patterns`. A flight case is then the sum of the four solutions with the hand calculation's factors, computed by `case_factors`:

```math
\mathbf{u} = \tfrac12 n W\,\mathbf{u}_{\ell} + q c^2 c_m\,\mathbf{u}_m + q c\,\Delta c_l\,\mathbf{u}_{a\ell} + q c^2\,\Delta c_m\,\mathbf{u}_{am} ,
```

and the stresses likewise. The wing's own weight is left out, as in the hand calculation.

<!-- code: orientation_groups, schrenk_lift, strip_pressure, load_patterns, case_factors -->

### 10.3 Margins, deflection and twist

The tip twist is the difference of the two webs' vertical displacements at the tip over their distance, $`\theta = (w_f - w_r)/(x_r - x_f)`$, and the tip deflection is read at the shear center between them. Each ply's stresses at every integration point, printed by CalculiX in the ply's own axes, go through the engine's strength ratio by the envelope's criterion, and a core's transverse shear stress $`\sqrt{\tau_{13}^2 + \tau_{23}^2}`$ is set against its shear strength. The clamp is singular: it stops the plies' Poisson contraction and the box's warping, and the root's stresses keep rising as the mesh is refined (Saint-Venant). The checks are therefore read outboard of a root zone one web height long, the deeper web's, computed by `root_zone`, and the root's own values are kept beside them; the cases' tip deflection, twist and lowest ratios of the skins', webs' and ribs' plies and of the core are computed by `fe_cases`.

<!-- code: root_zone, fe_cases -->

### 10.4 Panel buckling

Each skin and web panel between two ribs buckles as a flat plate simply supported on its four edges, under the mean of its in-plane loads in the model. Each element's resultants in the ply axes of its layup ($`x`$ the 0 degree direction) are every layer's stress turned from its fibre axes at $`\theta_k`$ and summed over the layers' thicknesses $`t_k`$, with $`c = \cos\theta_k`$ and $`s = \sin\theta_k`$, computed by `element_loads`:

```math
\begin{aligned}
N_x &= \sum_k t_k\,(\sigma_1 c^2 + \sigma_2 s^2 - 2\tau_{12} s c), \qquad N_y = \sum_k t_k\,(\sigma_1 s^2 + \sigma_2 c^2 + 2\tau_{12} s c),\\
N_{xy} &= \sum_k t_k\,\big[(\sigma_1 - \sigma_2)\,s c + \tau_{12}\,(c^2 - s^2)\big] .
\end{aligned}
```

A panel's load is the area-weighted mean over its elements, and its buckling factor is the engine's Ritz double sine series with the laminate's $`D_{16}`$ and $`D_{26}`$ kept (engine theory, Section 7); a web panel is taken no longer than five times its height, as in the hand calculation. Under each of the cases that bend the wing hardest up and down (both maneuver corners at a load factor bend it equally and differ in torsion, so both are taken), the panel that buckles first is computed by `panel_buckling`, and its margin is the factor over the ultimate factor less one.

CalculiX's own eigenvalue buckling (`*BUCKLE`) is not used for the wing. On a flat plate alone it gives the closed form within 1 %, but on the joined skins, webs and ribs of the example wing with a $`[45/-45/0]_s`$ web its first four modes, from 2.26 times limit load, were each mostly the wing's own static deflection and none a web buckle, while a large-deflection static solution of the same model (`NLGEOM`) buckled the root bay's front web at about 1.6 (ADR-0117).

The panel check is not a lower bound for a web. The mean load leaves out the web's own bending stress, spanwise compression along one edge in a lift case, and on that wing it put the root bay's web at 1.82 times limit load, 8 to 14 % above the large-deflection solution's 1.60 to 1.68; the skins' firmer hold on the web's edges, which the simple supports leave out, did not make up for it. A web's margin therefore stands on the hand calculation's check (engine theory, Section 13, "Checks of every case"), which put the same web at 1.09.

<!-- code: element_loads, panel_buckling -->

### 10.5 The wing as a beam, and flutter

Two of the static solutions give the wing's torsion stiffness and shear center. A uniform moment of 1 N·m per metre twists the tip by $`\theta_m = L^2/(2GJ)`$. The lift pattern acts at the aerodynamic center, a distance $`e`$ ahead of the shear center, so it twists the tip nose up by $`\theta_\ell = e\,M_{root}/GJ`$, with $`M_{root} = \int_0^L \ell\,y\,dy`$ its root bending moment. Hence

```math
GJ = \frac{L^2}{2\,\theta_m}, \qquad x_{sc} = x_{ac} + \frac{\theta_\ell\,GJ}{M_{root}} .
```

The mass per unit span, its center $`x_{cg}`$ and its moment of inertia about the shear center come from every element's area times its layup's areal mass, $`\rho_A = t_f\,\rho_f + t_c\,\rho_c`$ (the structure only: no fuel, systems or paint); together with $`GJ`$ and $`x_{sc}`$ they are computed by `fe_section`. The vibration modes are CalculiX's `*FREQUENCY` step on the same model; a mode is called bending, torsion or fore and aft by what its two webs do at the tip, and local when the tip hardly moves. The first bending and first torsion modes, the shear center as the elastic axis and the mass properties make the typical section of the engine's flutter estimate (engine theory, "Flutter estimate"), computed by `typical_section`:

```math
a = \frac{x_{sc} - b}{b}, \qquad x_\theta = \frac{x_{cg} - x_{sc}}{b}, \qquad r^2 = \frac{I_{sc}}{m\,b^2}, \qquad b = \frac c2 .
```

<!-- code: fe_section, typical_section -->

### 10.6 What the tests check

Each load pattern sums to its stated lift and moment, and a strip's linear load has its resultant and its moment about the aerodynamic center; the box keeps only what lies between the spars, and every orientation group holds one layup whose elements face its normal; on a coarse box the bending and torsion stiffness meet an independent thin-walled beam of the same walls within 5 % and 7 % (1.5 % and 4 % at 40 mm elements), and the hand calculation's section (ADR-0115 amendment 3) meets that beam within 1 % and the model's shear center within 2 % (0.2 % at 40 mm); every case deflects the way the hand calculation's does and as far within 10 % (2 % at 40 mm), the panel that buckles is the compressed skin within 35 % of the hand calculation's skin buckling, the first mode is bending within 5 % of the hand calculation's frequency (0.3 % at 40 mm) and a torsion mode follows; the k method of the flutter estimate meets an independent p-k solution with Theodorsen's exact function, written in the test, within 1 % (`test_wing_model.py`). With spar caps, the capped box's bending and torsion stiffness meet the hand calculation's section within 2 % and 5 % and its shear center within 0.5 mm (0.3 %, 4.3 % and 0.34 mm at 40 mm, where the plain box gives 2.0 %, 4.2 % and 0.22 mm), and with zones every case deflects as the hand calculation's within 2 % (`test_wing_model.py`); each face of the shape carries its name, stack, offset and area, and the STEP file reads them back (`test_wing_shape.py`).

### 10.7 Spar caps and zones: faces of one layup on one surface

With spar caps or zones along the span (ADR-0125), a skin or a web is several faces, each of one layup: the shape cuts each skin at the caps' four edges and every face where its own stack changes along the span. All the skin and cap faces lie on one surface, the reference, at a depth $`r`$ inside the airfoil: half the thickness of the caps at the root, or of the skin at the root without caps. A face of thickness $`t`$ has its mid-surface at $`t/2`$ inside the airfoil, as the hand calculation places it, so its shells are offset by CalculiX's `OFFSET`, the nodes' surface lying $`o\,t`$ from the mid-surface along the outward normal, as in Abaqus:

```math
o = \frac{t/2 - r}{t}
```

A skin thicker than the caps has $`o > 0`$, its mid-surface deeper than the nodes; a stretch of cap thinner than the root's has $`o < 0`$. The webs run between the reference surfaces, the caps' mid-surfaces at the root, as the hand calculation's do; webs and ribs have no offset. Within one face the offset changes nothing (CalculiX ties each shell node to the mean of the expanded nodes); where two faces of different offset or thickness meet, CalculiX joins them with a knot, a rigid link that keeps the step between their mid-surfaces, the step the hand calculation joins with a wall that carries shear but no spanwise load. Each face's stack and offset make a shell section of its own, computed by `shell_sections`; a cap's plies count with the skin's in the checks.

The box (`skins = "box"`) keeps each cap whole, its outer half too, as the hand calculation counts it, and no skin outside the webs; the box's airload spreads from the front cap's fore edge to the rear cap's aft edge. A skin panel buckles between the caps' inner edges, and a rib bay that a zone's edge crosses is a panel per stretch, each of its own layup with the bay's length.

<!-- code: shell_sections -->

## 11. The repair's slice in CalculiX (`repair_model.py`)

A stepped patch repair's slice (the engine's theory, Section 17) is solved in CalculiX in its elastic state under the load (ADR-0132). The slice is one half of the cut along the load through the repair's middle, $`r`$ from the middle outward and $`z`$ up from the laminate's bottom face, every ply and every piece of adhesive a rectangle of its own. This package writes the deck and reads the result; every stiffness in the deck and every ply stress in the answer is the engine's (the engine's theory, Section 18; ADR-0001, ADR-0067). The solve adds to the hand calculation of the stepped lap (the engine's theory, Section 16) what that leaves out: the bondline's peel stress, the bending of the patch where it takes load, the adherends' shear through their thickness, and the stresses of each ply where a step ends.

### 11.1 The model

**Mesh.** The grid of `repair_shape.py`'s `slice_mesh`, graded along $`r`$: the elements beside every end of every rectangle (a step's end, a cut, the patch's edge, the hole's edge) are an eighth of the bondline's thickness long, each next one 1.3 times longer, up to an eighth of the step length. Through the thickness there are two elements in the bondline and one in each ply. Each four-node cell becomes an eight-node plane element with reduced integration (CalculiX's CPE8R) by a node at the middle of every edge.

**Materials.** Each ply is an orthotropic solid turned to its angle and the adhesive an isotropic one; a rectangle's stiffness in the slice's axes is computed by `region_stiffness`. The deck holds the nine terms CalculiX's `*ELASTIC, TYPE=ORTHO` takes. A turned ply has four more, which tie its shear in the laminate's plane and across the width to the rest; the slice has neither of those two shear strains, so they make no stress in the slice's plane, and the engine puts them back when it works out the ply's own stresses (Section 11.2).

**Across the width.** A plane-strain element has no strain across the width, which would hold the laminate from its Poisson contraction and put a stress across the width into every ply that the panel does not have. The slice is instead given the strain across the width the laminate has far from the repair, $`\varepsilon_y^{\infty}`$ of the engine's far field: every material gets a thermal expansion of $`-1`$ across the width and none in the plane, and the whole slice a temperature $`T = \varepsilon_y^{\infty}`$. The strain that makes stress across the width is the total less the thermal one,

```math
\varepsilon_y - \alpha_y T = 0 - (-1)\,\varepsilon_y^{\infty} = \varepsilon_y^{\infty} ,
```

everywhere in the slice. Far from the repair every ply's stress is then the laminate theory's, and the plies' stresses across the width cancel.

**Supports and load.** The middle is a plane of symmetry: no movement along $`r`$ there. The laminate's bottom face is held flat: no movement along $`z`$. The load is put on the panel's end as each ply's far-field stress $`\sigma_x^{(k)}`$, so the end is the laminate theory's and their sum is the load $`N`$ per unit width.

**The cut faces.** In a flush repair the adhesive also lies up each cut face, a butt joint one bondline wide between the end of a laminate ply and the patch ply that fills its place; whether a rectangle is one is computed by `is_cut_face`. By default those elements are left out (`cut_faces = "open"`): the butt joint carries nothing, as the hand calculation takes it and as a joint in tension across a thin layer of adhesive is the first thing to crack. With `cut_faces = "bonded"` they are solved as bonded and the mean stress across each is reported. The model is computed by `build_slice_model`.

<!-- code: region_stiffness, is_cut_face, build_slice_model -->

### 11.2 What is read back

CalculiX prints the stress and the strain at every integration point; each element's mean is taken, in the slice's axes, with CalculiX's tensor shear strain doubled to the engineering one, computed by `read_results`. Every quantity below is a sum or a mean of those over the elements of one column of the grid, a station $`r`$, with $`\Delta z`$ an element's height.

A bond is a flat stretch of adhesive with the patch or the cover plies on it and the laminate under it. The corner of adhesive under a cut face or over one joins nothing and is not read. The force per unit width along the load in a set of parts (the patch with the cover plies, the laminate, the adhesive), and at each station of a bond of thickness $`\eta`$ the adhesive's shear stress and its peel stress, are

```math
P(r) = \sum \sigma_x\,\Delta z, \qquad \bar\tau(r) = -\frac{1}{\eta}\sum \tau_{xz}\,\Delta z, \qquad \bar\sigma_{\text{peel}}(r) = \frac{1}{\eta}\sum \sigma_z\,\Delta z
```

The shear stress is positive when it passes tension into the patch: between the patch's edge at $`R`$ and a station, $`\int_r^R \bar\tau\,dr`$ is the force the patch carries there. The peel stress is positive when it pulls the patch off. Both are means through the bondline's thickness, and no single point's value is reported: the stress at the corner where a step ends has no upper bound in an elastic solution.

Where a bond ends at a square corner the mean through the thickness is itself steep within one bondline's thickness of the corner. On a laminate cut through, with its cut faces open, the peel stress read at 0.1, 0.5 and 1 bondline's thickness from the corner was 39, 18 and 5 MPa, the same on meshes from 8 to 64 elements to the bondline's thickness, so the value at the last station follows the mesh. The largest shear and the largest peel stress are therefore each the largest mean over a length $`\eta`$ of one bond, a square of adhesive:

```math
\tau_{\max} = \max_s \left| \frac{1}{\eta} \int_s^{s+\eta} \bar\tau\,dr \right|, \qquad \sigma_{\text{peel},\max} = \max_s \frac{1}{\eta} \int_s^{s+\eta} \bar\sigma_{\text{peel}}\,dr
```

The stresses are constant over each column of elements, so the mean over a moving length changes at a constant rate between the positions where one of its ends meets a column's end, and the largest is at one of those positions, computed by `BondLine.largest_mean`. These two settle: from 8 to 64 elements to the bondline's thickness, over seven solved repairs, the largest shear stress moved by 0.6 % at most and the largest peel stress by 1.7 % at most, that one beside the open cut face above (ADR-0132). The length $`\eta`$ is a choice: at a patch's free edge, where the mean through the thickness does settle at the last station, the square's mean is about a quarter below that value.

Each ply's strains are averaged through its thickness at every station, the far-field width strain is put with them, and the engine turns them into the ply's stresses in its own axes (the engine's theory, Section 18). $`\sigma_1`$, $`\sigma_2`$ and $`\tau_{12}`$ go to the engine's strength ratio by maximum stress or Tsai-Hill (the engine's theory, Section 5), and a ply's weakest station is kept.

Three loads follow, each the applied load scaled, since the solution is linear. With $`\tau_p`$ the adhesive's shear strength, $`\sigma_p`$ the bond's peel strength when the description states one, and $`R_k`$ ply $`k`$'s lowest strength ratio:

```math
N_{\text{shear}} = N\,\frac{\tau_p}{\tau_{\max}}, \qquad N_{\text{peel}} = N\,\frac{\sigma_p}{\sigma_{\text{peel},\max}}, \qquad N_{\text{ply}} = N\,\min_k R_k
```

The lowest of the three is what happens first as the load grows. $`N_{\text{shear}}`$ is the load at the adhesive's elastic limit and not the repair's strength: a ductile adhesive yields there and carries more. The patch's force at each boundary of the stepped lap is read beside the hand calculation's. The answer is computed by `slice_answer`, and the same answer as plain numbers in a unit system is computed by `slice_report`.

<!-- code: read_results, BondLine.largest_mean, slice_answer, slice_report -->

### 11.3 Checks made on every solve

A solve is refused unless all three hold. CalculiX's stress in every element equals the engine's stiffness times CalculiX's strain, so the materials solved are the ones the answer is worked out with: within $`10^{-6}`$ of the largest product of a stiffness and a strain in its kind of part (the laminate, the patch, the cover plies, the adhesive). The products are the terms a stress is the sum of. For a ply they are the size of its largest stress; in a nearly incompressible adhesive, where they cancel, they are the size that the digits CalculiX prints of a strain can be held to. At every station the forces in the patch, the laminate and the adhesive add up to the load within $`10^{-4}`$ of it. Midway between the repair and the panel's end, every ply's strain along the load is the far field's within 1 %; a panel too short for that is refused with those words. A slice of more than 40,000 elements is refused before it is solved, with what makes it large: its elements are an eighth of a step long over half the panel's length. The solve itself, CalculiX run on the deck and its result read, is computed by `run_slice_model`.

<!-- code: run_slice_model -->

### 11.4 Against the hand calculation

The stepped lap assumes that each adherend strains alike through its thickness and that nothing moves through the thickness. The model is brought to those assumptions by three changes: every node is held from moving along $`z`$ (`hold = "everywhere"`), every Poisson's ratio is zero, and the plies' shear moduli through the thickness are ten thousand times their in-plane one. It then returns the lap's closed form for a strip patch bonded on top (case `constructed-external-strip-held-to-the-stepped-laps-assumptions` of `fea/checks/repair_cases/`, its numbers worked without the engine by `external_patch_repair` in `engine/validation/closed_forms.py`): the patch's force at every boundary within 0.5 % of the load and the adhesive's shear stress along the whole bondline within 0.5 % of its peak (0.16 % and 0.23 % on 2,744 elements), with no peel stress; its largest shear stress, a mean over a square, is the closed form's curve averaged over the same length within 0.5 %.

With the bottom face alone held, the answer differs from the lap's where the lap's assumptions do not hold. On that strip patch with its real constants the patch's forces at the boundaries stay within a tenth of the load of the lap's, but the largest shear stress, at the hole's edge, is about 0.6 of the lap's: the patch bends where it takes the whole load and its plies shear through their thickness, which spreads the transfer. The bondline is pressed together at the hole's edge and pulled apart at the patch's tip. On the flush example repair with its cut faces open, the patch's forces are within a hundredth of the load of the lap's and the largest shear stress, on the same ledge, is 0.91 of it. The lap's own largest is the value at one point of its curve; averaged over the same square it would be a few percent lower.

### 11.5 What the slice is not

The slice is the strip through the repair's middle, of unit width. It does not hold the laminate beside a hole narrower than the panel, which carries load past the hole, nor the load that flows around a round repair; both need the panel in three dimensions. It is elastic: past the adhesive's elastic limit and past the first ply's strength it says nothing. The laminate's bottom face is held flat, as a panel on its structure nearly is; a one-sided patch on a panel free to bend also bends the panel, which needs a large-deflection solution and is not solved. The strain across the width is the far field's everywhere, and the laminate is kept from shearing in its plane, so a laminate that is not balanced is stiffer here than free.

### 11.6 The same slice in Abaqus and in Ansys

The model of Section 11.1 is also written for two other solvers, node for node and element for element (ADR-0132 amendment 1). The two files check the solver and the way the model is stated to it; they share the model's assumptions, so they say nothing about those. This package runs neither program: it writes the files and reads what the programs wrote.

**Abaqus.** The input file holds the same eight-node elements (CPE8R), each material as `*Elastic, type=ORTHOTROPIC` with the nine terms of the CalculiX deck in an orientation that is the global axes, the expansion of $`-1`$ across the width with the temperature $`\varepsilon_y^{\infty}`$, the supports, and the load as `*Dload` P2 on the elements of the panel's end. It asks for the stresses and the strains at every integration point and for the reaction on the middle. The file is computed by `abaqus_file`.

**Ansys.** The Mechanical APDL input file holds the same elements as PLANE183 in plane strain, $`x`$ along the load, $`y`$ through the thickness and $`z`$ across the width. Mechanical APDL takes an orthotropic material by its engineering constants, so each material is stated by the nine constants of the same nine terms. With $`\mathbf{S}`$ the inverse of the three by three block of the stiffness that ties the three direct strains, in the order $`x, y, z`$,

```math
E_x = \frac{1}{S_{11}}, \quad E_y = \frac{1}{S_{22}}, \quad E_z = \frac{1}{S_{33}}, \qquad
\nu_{xy} = -\frac{S_{21}}{S_{11}}, \quad \nu_{yz} = -\frac{S_{32}}{S_{22}}, \quad \nu_{xz} = -\frac{S_{31}}{S_{11}} ,
```

and the three shear moduli are the three shear terms themselves. They are computed by `engineering_constants`. The width strain is an expansion of $`-1`$ along $`z`$ and a uniform temperature, and the load a pressure on face 2 of the elements of the panel's end. The file itself writes a table of every element's stresses and elastic strains, each the mean of the element's four integration points. The file is computed by `ansys_file`.

**Reading back.** What Abaqus printed and the table the Ansys file wrote are turned into the same element means CalculiX gives, computed by `read_abaqus` and `read_ansys`; each goes through the refusal of Section 11.3 (the program's stress is the engine's stiffness times the program's own strain) and then through the reading of Section 11.2, unchanged. Abaqus prints four or five figures and Mechanical APDL keeps an element table to seven, so the refusals are set to those figures: $`10^{-3}`$ of the largest stress for Abaqus, $`10^{-5}`$ for Ansys, and Ansys's elastic strain across the width must be the far-field width strain within $`10^{-6}`$ of it. Every reported number of the two answers, side by side with CalculiX's, and the largest gap in any element's stress and at any station of a bond, are computed by `compare_answers`.

<!-- code: abaqus_file, engineering_constants, ansys_file, read_abaqus, read_ansys, compare_answers -->

## 12. A repair's bond followed to failure (`repair_bond.py`)

The slice of Section 11 is elastic, and stops where the adhesive first reaches a strength. Here the same slice is solved with a bond that softens and parts, along its whole load path, by a plane solver of this package (`bond_solver.py`; ADR-0140). The answer is the load at which the bond first softens and the load at which it lets go in this model. Every ply stays elastic, so neither is the repair's strength.

### 12.1 The bond's law

A point of the bond has an opening $`\delta_n`$, positive when its two faces part, and a slip $`\delta_s`$ along the bond. Six numbers make its law: a stiffness, a strength and a fracture energy in peel ($`K_n`$, $`\sigma_c`$, $`G_{Ic}`$) and in shear ($`K_s`$, $`\tau_c`$, $`G_{IIc}`$). One number, the damage $`d`$ from 0 to 1, lowers both stiffnesses:

```math
t_n = (1 - d)\,K_n\,\delta_n \quad (\delta_n > 0), \qquad t_n = K_n\,\delta_n \quad (\delta_n \le 0), \qquad t_s = (1 - d)\,K_s\,\delta_s
```

A point pressed together carries the pressure with its whole stiffness. With $`\langle\delta_n\rangle`$ the opening when positive and zero otherwise, the size of the movement is $`\delta = \sqrt{\langle\delta_n\rangle^2 + \delta_s^2}`$ and its direction $`c_n = \langle\delta_n\rangle/\delta`$, $`c_s = |\delta_s|/\delta`$. Along that direction the point starts to soften at $`\delta_0`$ and has parted at $`\delta_f`$:

```math
\delta_0 = \left[\left(\frac{K_n c_n}{\sigma_c}\right)^2 + \left(\frac{K_s c_s}{\tau_c}\right)^2\right]^{-1/2}, \qquad
\delta_f = \frac{2}{\delta_0}\left[\frac{K_n c_n^2}{G_{Ic}} + \frac{K_s c_s^2}{G_{IIc}}\right]^{-1}
```

The first is the stresses, each over its strength and squared, adding to one. The second makes the energy spent along that direction, peel's share over $`G_{Ic}`$ plus shear's over $`G_{IIc}`$, add to one when the point parts. Between the two the stress falls in a straight line:

```math
d = \max\left(d_{\text{before}},\ \frac{\delta_f\,(\delta - \delta_0)}{\delta\,(\delta_f - \delta_0)}\right) \quad (\delta > \delta_0)
```

Damage only grows; unloaded, a point returns along a straight line to nothing. In pure peel the law is a triangle of height $`\sigma_c`$ that ends at $`2 G_{Ic}/\sigma_c`$, and in pure shear one of height $`\tau_c`$ that ends at $`2 G_{IIc}/\tau_c`$. A law whose fracture energy is below the elastic energy it holds at its strength, $`\sigma_c^2/2K_n`$ or $`\tau_c^2/2K_s`$, is refused. The stresses and the damage are computed by `BondLaw.traction`.

<!-- code: BondLaw.traction -->

### 12.2 The model

The grid, the eight-node elements with four integration points, the holds, the strain across the width and the load on the panel's end are those of Section 11.1. Two things differ. Along every flat bond the adhesive's elements are left out, and each node on the laminate's side is paired with the node over it on the patch's side, one bondline higher. Where the bondline is thicker than a ply the grid gives it more than one element through its thickness; the bond is the whole stack, from the laminate's top to the patch's bottom. A pair is one integration point of the bond, weighted by Simpson's rule along each element's edge (a sixth, four sixths and a sixth of the edge for its two corners and its middle). Its law has the adhesive's stiffness over the bondline's thickness $`\eta`$, computed by `bond_law`:

```math
K_s = \frac{G}{\eta}, \qquad K_n = \frac{\lambda + 2G}{\eta}, \qquad \lambda = \frac{2G\nu}{1 - 2\nu}
```

with the adhesive's two strengths and two fracture energies as the repair states them. The peel stiffness is that of a layer kept from straining in its own plane, as a thin adhesive between stiff plies is. The bondline's thickness stays in the mesh as the gap between the two nodes of a pair. The cut faces carry nothing, as in Section 11's default. The elements beside each edge are a quarter of the bondline's thickness long.

The load is not given. Every nodal force and the strain across the width are those of one newton per metre of width, times a load factor $`\lambda_N`$ the path finds, so the factor is the load per unit width. The model is computed by `build_bond_model`; the solids' stiffness matrix is computed by `solid_stiffness`.

<!-- code: bond_law, build_bond_model, solid_stiffness -->

### 12.3 The path

With $`\mathbf{K}`$ the solids' stiffness, $`\mathbf{f}_b(\mathbf{u}, d)`$ the bond's forces and $`\mathbf{F}`$ the unit load, each state satisfies

```math
\mathbf{K}\,\mathbf{u} + \mathbf{f}_b(\mathbf{u}, d) = \lambda_N\,\mathbf{F}
```

Up to the first pair at onset the answer is one linear solve, scaled. From there a step of load alone cannot be relied on: where the bond sheds load faster than the rest takes it up, the load must fall, and where the solids hold more energy than the bond can spend, the load and the end's movement both fall back. So the load factor is made an unknown of the step, and the step is given the energy $`\Delta W`$ the bond is to spend in it. For a law that unloads to the origin, the energy spent between a state $`(\mathbf{u}_0, \lambda_0)`$ and the next is

```math
\Delta W = \tfrac{1}{2}\left[\lambda_0\,\mathbf{F}\cdot(\mathbf{u} - \mathbf{u}_0) - (\lambda_N - \lambda_0)\,\mathbf{F}\cdot\mathbf{u}_0\right]
```

which is solved with the equilibrium equations by Newton's method, the damage of the step's start in the tangent. A step that must spend energy cannot stall at a peak or on a snap-back, and nothing is added to the equations to get through. The first steps after onset are steps of load, while the bond spends little; where nothing is softening, because what was has parted and nothing else has begun, the load leads again until something does. The step's energy grows when Newton converges quickly and is cut back when it does not. The path is computed by `follow`.

For a repair the path is followed until the load has fallen 10 % below the largest it reached, or the whole bond has parted, or 1,500 steps are taken. The load at which the bond lets go is the first peak after which the load falls by 5 % of it before rising above it again, computed by `Path.first_peak`; a path that ends before such a fall reports none and says why. The repair's path is computed by `follow_bond`.

<!-- code: follow, Path.first_peak, follow_bond -->

### 12.4 What is read back

At the load of first softening and at the load at which the bond lets go: the pair where it began, with its place and the part of the bond it is on, and its peel and shear stress there; the length of bond softening ($`0 < d < 1`$) and parted ($`d = 1`$), as sums of the pairs' weights; the largest shear and peel stress on each stretch of the bond; and the movement of the panel's end, $`\mathbf{F}\cdot\mathbf{u}`$ over the load. The curve of the path gives, state by state, the load, the end's movement and the length of bond past its strength. The answer is computed by `bond_answer`; the report in the file's units is computed by `bond_report`.

Two checks are made on every run, as on the elastic solve: midway between the repair and the panel's end every ply's strain along the load is the far field's within 1 %, and at every station the forces in the plies add up to the load within $`10^{-4}`$ of it. The first reads the elastic state alone, so it is made before the path is followed, and a panel too short round its repair is refused in the time of one solve.

<!-- code: bond_answer, bond_report -->

### 12.5 What the run leaves out

Every ply is elastic. A ply that reaches a strength before the bond lets go, or a laminate that splits between its plies at a ledge, is not seen, and from that load on the answer would change; the solved slice of Section 11 gives the first ply's load to set beside it. The law is two straight lines: an adhesive that yields at a steady stress before it softens has a plateau the law leaves out, which matters most where the bond is short against its softening zone. The energies add in a straight line; a rule fitted to mixed-mode tests is not used. The cut faces carry nothing. The slice is the strip of Section 11.5, held flat, with no load flowing round the repair. Fatigue, heat, moisture, cure stress and a flaw in the bond are left out. The numbers move with the adhesive's two strengths and two fracture energies as stated, which a datasheet seldom gives.

## 13. A repair's plies damaged beside its bond (`repair_plies.py`)

Section 12 follows the bond with every ply elastic, so a repair whose plies fail first is not caught. Here every ply may damage too (`ply_damage.py`; ADR-0141), and the answer is the load the slice carries with both able to fail. For the example repair that load is below the load at which its bond alone lets go, which is why the slice exists.

### 13.1 A ply's two cracks

In a ply's own axes, 1 along the fibres, 2 across them in the ply, 3 through its thickness, two cracks are followed. A **fibre break**, whose plane's normal is 1, begins where

```math
E_1\,\varepsilon_1 = F_{1t} \quad \text{(pulled apart)}, \qquad -E_1\,\varepsilon_1 = F_{1c} \quad \text{(crushed)}
```

and a **matrix crack**, whose normal is 2, where

```math
\left(\frac{E_2\,\langle\varepsilon_2\rangle}{F_{2t}}\right)^2 + \left(\frac{G_{12}\,\gamma_{12}}{F_6}\right)^2 = 1
```

with $`\langle\varepsilon_2\rangle`$ the strain across the fibres when it is positive and zero otherwise, so a crack pressed shut does not begin. Each crack has a damage $`d`$ from 0 to 1, which lowers the terms of the ply's compliance $`\mathbf{S}`$ that its own plane carries: $`S_{11}`$ and the shears 12 and 13 for a fibre break, $`S_{22}`$ and the shears 12 and 23 for a matrix crack. Each is divided by what is left of it:

```math
S_{11} \rightarrow \frac{S_{11}}{1 - d_f}, \qquad S_{22} \rightarrow \frac{S_{22}}{1 - d_m}, \qquad
G_{13} \rightarrow (1 - d_f)\,G_{13}, \qquad G_{23} \rightarrow (1 - d_m)\,G_{23}, \qquad G_{12} \rightarrow (1 - d_f)(1 - d_m)\,G_{12}
```

So a ply pulled along one axis alone carries $`(1 - d)`$ of its elastic stress there, and the stiffness stays one an elastic solid may have. Which way a crack is loaded is read from the stress on it, which has one sign whichever stiffness it is given: a crack pressed shut carries the pressure with the whole stiffness, and only $`S_{22}`$ changes with the sign. Damage only grows. The stiffness and the stresses are computed by `PlyDamage.stiffness` and `PlyDamage.stress`.

<!-- code: PlyDamage.stiffness, PlyDamage.stress -->

### 13.2 The band a crack softens in

After onset the stress falls in a straight line with the strain. A matrix crack is the bond's own law of Section 12.1 with the strain times a width $`b`$ as the opening and the slip, the stiffnesses $`E_2/b`$ and $`G_{12}/b`$, and the ply's two matrix energies; a fibre break is that law in one direction. The width $`b`$ is what makes the answer the same on any mesh: a crack spends

```math
\int \sigma \,\mathrm{d}\varepsilon \cdot b = G_c
```

per unit of its own area, so the strain at which the stress reaches nothing is set from $`b`$ and a wider band softens over less strain (the crack band of Bažant and Oh, 1983). The band is one element wide, cut at the ply's angle $`\theta`$: with $`\ell`$ the element's length along the load,

```math
b_f = \ell\,|\cos\theta| \quad \text{(a fibre break)}, \qquad b_m = \ell\,|\sin\theta| \quad \text{(a matrix crack)}
```

An element damages as one, from its mean strains, so its four integration points cannot soften apart and spend the energy twice over. A crack whose plane holds the load's direction cannot form in a slice along the load and is not followed: the matrix crack of a 0° ply, the fibre break of a 90° ply.

A crack softens only where its fracture energy is above the energy the ply holds when it reaches its strength, which bounds the band and so the element:

```math
\ell \le \frac{2\,G_c\,E}{X^2}
```

for each of the four cracks of each material, with $`E`$ the modulus and $`X`$ the strength of that crack. A model whose elements are longer is refused in words. The run takes two fifths of the smallest bound, because an element near the bound softens over almost no strain and the load the slice holds then falls far below where a finer mesh puts it. The bound and the band are computed by `longest_element` and `PlyDamage.setup`.

<!-- code: longest_element, PlyDamage.setup -->

### 13.3 How the load is carried

The slice, the bond, the holds and the strain across the width are Section 12.2's, with the load on the panel's end alone: the stress the width strain makes is the plies' own now and moves with their damage. The path of Section 12.3 cannot be used, because dozens of plies reach their strength in one step and its Newton iterations pass between two states without settling. Instead a load is held and the damage let grow until it stops. Under a load $`\lambda_N`$, from a damage $`d`$, each turn solves the slice as an elastic body with the stiffness that damage leaves,

```math
\mathbf{K}(d)\,\mathbf{u} = \lambda_N\,\mathbf{F}(d)
```

and every element and every pair then takes the damage of the strains found, never less than it had. Where the damage stops growing, the state is one the slice can rest in under that load, which is what carrying a load means; where the movement runs away, the slice cannot hold it. The load is raised from the first softening of anything, bond or ply, by 15 % while the slice holds it, and then halved in until the load held and the load not held are within half a percent of each other. The holding of one load and the raising of it are computed by `Holder.hold` and `largest_load`.

<!-- code: Holder.hold, largest_load -->

### 13.4 What is read back

The load at which anything first softens and what it was; the largest load the slice holds and the smallest it does not, so the load it carries lies between them; what had failed at the largest load held, as lengths of bond past its strength and parted and as counts of elements broken across the fibres, crushed or cracked along them with the worst one's place; and the loads held in order with the movement of the panel's end. One check is made on every run: at the largest load held the plies' forces along the load add up to the load at every station within $`10^{-3}`$ of it. A mesh study, the same repair on meshes each four fifths of the one before, is run beside the answer and its spread reported with the load. The answer, the study and the report in the file's units are computed by `run_plies`, `mesh_study` and `plies_report`.

<!-- code: run_plies, mesh_study, plies_report -->

### 13.5 What the run leaves out

A ply parting from its neighbour is not modelled, so a laminate that splits between its plies at a ledge is not seen. A ply crushing across its fibres is not followed ($`F_{2c}`$ is unused). Nothing saturates matrix cracking, so where the panel's far field itself cracks the number of cracked elements grows with the mesh; the mesh study is what says whether a load may be read, and a repair whose load does not settle has none to report. The strain across the width stays the undamaged laminate's. What the slice leaves out it still leaves out: the cut faces carry nothing, the slice is held flat, no load flows round the repair, and fatigue, heat, moisture and cure stress are absent. The load carried is "the load the repair carries in this model", never its strength: no test of a repair has been compared.

## Checks

Each check below is a test in `fea/tests/`, in the file named after it; the tests run on every change to our code, and their output is not printed here.

- Shape functions sum to one and take the value one at their own node; their derivatives sum to zero; $`\mathbf{B}`$ on the unit square matches hand values (`test_membrane_element.py`).
- A uniform strain field is recovered exactly from nodal displacements at every Gauss point of a skewed element (`test_membrane_element.py`).
- $`\mathbf{k}`$ is symmetric with three zero eigenvalues; rigid translations and rotation give zero force; clockwise and bow-tie elements are refused (`test_membrane_element.py`).
- Engine equality (validation cases `patch-1x1-im7-engine-equality`, `patch-2x2-im7-engine-equality`, `patch-1x1-cload-im7-engine-equality`): one element of a 25 by 100 mm IM7/8552 [0/30/-30/30/0]s coupon under prescribed edge displacement reproduces the engine's midplane strain, section force and reaction to a relative 1e-12, and generated 2 by 2, 4 by 8 and 3 by 5 meshes carry the same uniform state to a relative 1e-11; under edge load the coupon reproduces the engine's forward solve (`test_membrane_solve.py`).
- Isotropic closed forms (`isotropic-uniaxial-plane-stress`, `isotropic-simple-shear`): $`\varepsilon_x = -\nu\varepsilon_y`$, $`N_y = E h \varepsilon_y`$; $`N_{xy} = G h \gamma_{xy}`$ (`test_membrane_solve.py`).
- A coupled edge driven by a reference node gives the same displacements as the same edge prescribed node by node, and the reference node's reaction equals the summed edge reactions (`test_membrane_solve.py`).
- The gripped test coupon of 2 by 8 elements: reactions in equilibrium, top and bottom reference reactions equal and opposite; refined to 4 by 16 and 8 by 32 elements, its reaction does not grow and converges (`test_membrane_solve.py`).
- Ply stresses in material axes equal the engine's `ply_surfaces` on the uniform cases for all ten plies; the first-ply-failure factor, governing ply and mode equal the engine's `first_ply_failure` for maximum stress, Tsai-Hill and Tsai-Wu; the factor halves when the imposed displacement doubles; in the gripped 2 by 8 test coupon the first ply to fail sits within two element rows of a grip, a property of that test deck and not of every coupon; missing strengths, strain limits or $`f_{12}^*`$ are refused by name (`test_recovery.py`).
- The shell element: its strain rows match hand values on the unit square; $`\mathbf{k}_e`$ is symmetric with exactly six zero eigenvalues on a rectangle and on a skewed quadrilateral; the three rigid translations and three rigid rotations give no strain and no force; a pure bending field is carried with constant curvature and zero transverse shear at every point, and its nodal forces are the edge moments; pressure loads are consistent and sum to the load; a clockwise element is refused (`test_shell_element.py`).
- Engine equality under bending (validation case `bend-1x1-im7-engine-equality`): one unsymmetric IM7/8552 [0/30/-30/90] element under a prescribed uniform curvature reproduces the engine's $`\mathbf{N} = \mathbf{B}\boldsymbol{\kappa}`$, $`\mathbf{M} = \mathbf{D}\boldsymbol{\kappa}`$, both faces of every ply and the first-ply-failure factor, ply, face and mode to a relative 1e-12 (`test_shell_solve.py`).
- The shell reproduces the membrane on a symmetric in-plane deck, and through a kinematic coupling on the gripped coupon, to 1e-12 and 1e-10; the dispatch sends the in-plane decks to the membrane and a bending, pressure or unsymmetric deck to the shell; a plate free to move out of its plane and a load on the drilling rotation are refused by name; an unsymmetric layup under tension is refused by the membrane and solved, bending, by the shell (`test_shell_solve.py`).
- Closed forms (cases `plate-ss-isotropic-uniform-pressure-navier`, `plate-ss-isotropic-thin-no-locking`, `plate-ss-cross-ply-sinusoidal-navier`, `strip-cantilever-tip-load-timoshenko`): the simply supported isotropic square plate under uniform pressure reproduces Whitney's Navier series with transverse shear deformation within 0.5 % on 16 by 16 elements, and does so unchanged when the plate is a thousand times thinner than wide, where a displacement-based bilinear element would lock; the simply supported IM7/8552 [0/90]s plate under a sinusoidal pressure reproduces the one-term solution, both faces of every ply included, within 1 % on 32 by 32 elements; the cantilever strip with $`\nu = 0`$ reproduces the Timoshenko beam's tip deflection, shear part included, within 0.02 % and its tip rotation, root moment and shear force to 1e-9 (`test_fe_validation_cases.py`; the closed forms themselves are checked in `test_plate_closed_forms.py` against the tabulated 0.00406 coefficient, the Kirchhoff limit and the plate equation).

- The quantities of a test standard: the formulas reproduce hand values; on the public IM7/8552 coupon under ASTM D3039 the extensometer's chord modulus and Poisson's ratio meet the laminate's $`E_y`$ and $`\nu_{yx}`$ from the engine within a relative 1e-4, the open hole's net area and ratios follow its geometry, and the stated units convert the area and the modulus (`test_test_quantities.py`).
- The repair's slice in CalculiX (Section 11): the graded mesh has a line of nodes on every edge of every rectangle, fine elements beside it, no element much longer than its neighbour and the description's areas; the deck has one material for each ply angle and the adhesive, the far-field width strain as its temperature and the far-field stresses on its end, summing to the load; on a strip patch, the flush example and the example with bonded cut faces the forces add up at every station and, well outside the repair, every ply's stress is the laminate theory's with nothing through the thickness and nothing across the width in sum; held to the lap's assumptions the model returns the lap's closed form (case `constructed-external-strip-held-to-the-stepped-laps-assumptions`, Section 11.4); a patch bonded on top carries the whole load at the hole's edge, what its bondline's shear passes to it is the load within 1 %, it is pressed on at the hole's edge and pulled off at its tip; twice the load doubles every stress and compression changes every sign; the largest mean over a length of bond is found exactly on a bond worked by hand; elements half as long beside the edges change the largest shear stress by less than 0.5 %, the largest peel stress by less than 1 % and the patch's forces by less than 0.2 % on the strip patch and on the flush example, where the value at a bond's last station beside an open cut face grows by more than a fifth; on the flush example the adhesive's elastic limit comes before the first ply, which reaches its transverse tensile strength inside the repair at a lower load than a 90° ply does far from it; bonded cut faces take load off the ledges, so leaving them open is the lower reading; what a solve lacks is refused in words (`test_repair_model.py`).
- A repair's bond followed to failure (Section 12). The law alone: along any direction it peaks on the onset line and spends the failure line's energy; damage only grows; a pressed bond carries the pressure whole. The plane elements return an even stress and balance a stress inside them. Cases with exact answers: a block pulled off its bond reaches the strength times the length and spends the energy times the length, through a snap-back; the peel test's load is beam theory's within 2 % while the crack grows; the shear test's largest load is 7.8 % under beam theory's at 60 MPa, as the softening zone ahead of a crack of finite strength makes it, and is the one MOOSE gives for the same model within 0.3 % (729.5 N; the input file and the curve are in `fea/checks/bond_cases/`); a patch pulled off a strip held flat runs at the load its energy gives, $`\sqrt{2 G_c S_a (S_a + S_b)/S_b}`$, within 0.5 %, and between the two pure answers with unequal numbers (`test_bond_solver.py`). On the repair: on CalculiX's own nodes and elements the plane elements return CalculiX's strains; held to the stepped lap's assumptions the bond first softens at the lap's elastic limit load, and so does one with a bondline two and a half and four and a half plies thick; a refusal states its numbers in the repair file's units; a panel too short is refused before the path is followed; with the bond whole the patch carries midway along every step what it carries in CalculiX's slice within a third of a percent of the load; the example softens over a third of its bond and then lets go, and a mesh four times coarser beside each edge gives the same two loads; a path that ends before the load falls says so; a repair without the six numbers is refused in words (`test_repair_bond.py`).
- A repair's plies damaged beside its bond (Section 13). The law alone: it peaks at the strength, the stress integrated over the strain times the band's width is the fracture energy within a thousandth, damage only grows, and a crack pressed shut carries the pressure whole. A bar of one ply with a weak element breaks at that element's strength with 10, 20, 40 and 80 elements along it, for a 0° ply and a 90° ply, which is what the crack band is for. A cross-ply strip's first ply failure is laminate theory's, written out in the check, and the load it carries lies between the whole laminate's at the fibre's onset strain and its 0° plies' alone. A crack whose plane holds the load is not followed; an element too long to soften in is refused in words (`test_ply_damage.py`). On a repair: the element is cut to what a crack can soften in; a repair without the plies' strengths or fracture energies is refused with the list; the plies' forces add up to the load at every station; and on the example of a patch bonded over a hole, where the bond is the only way across, the load at which Section 12's own path method has the bond let go lies between the load this method holds and the load it does not, although the two share nothing past onset (`test_repair_plies.py`).
- The repair's slice for Abaqus and Ansys (Section 11.6): the Abaqus file holds the deck's nodes, elements, stiffness terms, supports, temperature and load, and solved by CalculiX, which reads the same keywords, it gives the deck's answer; the Ansys file's engineering constants give back the stiffness terms by an inverse written in the test, and its blocks hold the model's nodes, elements, materials, supports and load; stand-in output in each program's wording and figures is read back as the same answer, and a table with a row missing, of another model, with stresses that are not the stiffness times the strains, or with another width strain is refused (`test_repair_files.py`). Neither program runs in the tests.

## Not modeled yet

- An `*Orientation` out of the plate's plane, rotated about axis 1 or 2, or with `b` not the normal crossed with `a` (in-plane right-handed frames are read since ADR-0065)
- Triangles, higher-order shells, solids, membranes (M3D4)
- Distributed loads other than a uniform pressure per element (surface tractions, gravity, line loads by `*Dload`); thermal strain
- Interlaminar stresses from equilibrium (the transverse shear stress is uniform through the thickness in the shell's law, Whitney Eq. 10.22, and is not reported per ply)
- Abaqus-style failure indices (MSTRS, TSAIH, TSAIW) as numbers to compare against; progressive failure
- Eigenvalue buckling of joined shells (CalculiX's `*BUCKLE` misses a wing web's buckle; the wing's panels are flat Ritz plates on the model's mean loads, Section 10.4); a web panel's buckling under its own bending stress; buckling of a curved panel; the load after buckling
- For a repair's slice (Section 11): a panel free to bend under a one-sided patch (a large-deflection solution); a yielding adhesive (the followed bond of Section 12 softens in two straight lines, with no plateau); damage in the plies while the bond is followed, and a bond on the cut faces; the laminate beside a hole narrower than the panel and the load that flows around a round repair (the panel in three dimensions); a slice free to shear in the laminate's plane (generalized plane strain); thermal mismatch from the cure
