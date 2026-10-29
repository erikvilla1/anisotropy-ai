# Finite element theory

Every equation the finite element layer uses, and the function that computes it (ADR-0029, ADR-0053). The element formulation follows K.-J. Bathe, *Finite Element Procedures*, 2nd edition (2014), Chapter 5 (formulation and calculation of isoparametric finite element matrices, and the mixed-interpolated plate elements); the plate theory follows J. M. Whitney, *Structural Analysis of Laminated Anisotropic Plates* (1987), Chapters 5 and 10; the laminate stiffness comes from the engine ([engine theory](../../engine/docs/theory.md), Section 3). The kernels work in SI units throughout; a deck's units are converted once on entry (ADR-0002).

## Conventions

- The laminate x axis is the deck's global x axis: the only orientation our deck reader accepts is the global one, so ply angles are measured from global x, counterclockwise, as in ADR-0004.
- In the membrane kernel (Sections 1 to 7) each node has two degrees of freedom, $`u`$ along x and $`v`$ along y, Abaqus dofs 1 and 2; there are no out-of-plane or rotational degrees of freedom. The flat shell kernel (Section 8) adds $`w`$ along z and the rotations $`\theta_x`$, $`\theta_y`$ about the x and y axes, Abaqus dofs 3 to 5; the drilling rotation, dof 6, is never carried.
- Strain is the membrane (midplane) strain $`\boldsymbol{\varepsilon} = [\varepsilon_x, \varepsilon_y, \gamma_{xy}]^T`$ with engineering shear; the shell adds the curvature $`\boldsymbol{\kappa}`$ and the transverse shear strain $`\boldsymbol{\gamma} = [\gamma_{xz}, \gamma_{yz}]^T`$, engineering too.
- Section forces are resultants per unit width, $`\mathbf{N} = [N_x, N_y, N_{xy}]^T`$ in N/m, what Abaqus reports as SF; the shell adds the moments $`\mathbf{M}`$ in N (Abaqus SM) and the transverse shear forces $`\mathbf{Q}`$ in N/m.
- A uniform pressure (`*Dload`, label P) is positive against the element normal, which is $`+z`$ for counterclockwise nodes: a positive pressure pushes the plate toward $`-z`$.
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

A membrane state has no curvature, so every ply of an element carries the element's strain $`\boldsymbol{\varepsilon}`$. Each ply's stress in laminate axes and its strain and stress in material axes follow from the engine's ply recovery with $`\boldsymbol{\kappa} = \mathbf{0}`$ ([engine theory](../../engine/docs/theory.md), Section 4, ply surface recovery):

```math
\boldsymbol{\sigma}_{xy}^{(k)} = \bar{\mathbf{Q}}^{(k)} \boldsymbol{\varepsilon}, \qquad
\boldsymbol{\varepsilon}_{12}^{(k)} = \mathbf{T}_\varepsilon(\theta_k)\, \boldsymbol{\varepsilon}, \qquad
\boldsymbol{\sigma}_{12}^{(k)} = \mathbf{T}_\sigma(\theta_k)\, \boldsymbol{\sigma}_{xy}^{(k)} ,
```

with the bottom and top faces of a ply equal, so one value per ply is kept, bottom ply first. This is computed by `element_ply_states`, which calls the engine's `ply_surfaces`. Abaqus writes three section points per layer (Simpson); in a membrane state all three equal this one value, which is itself a check on a comparison.

<!-- code: element_ply_states -->

The von Mises stress of a ply's in-plane state, $`\sigma_\mathrm{M} = \sqrt{\sigma_1^2 - \sigma_1\sigma_2 + \sigma_2^2 + 3\tau_{12}^2}`$, is an invariant, the same in material or laminate axes, and is what Abaqus reports as S-Mises at a shell section point. It is computed by `ply_mises` for comparison records only; the engine's failure criteria, not Mises, judge a ply.

<!-- code: ply_mises -->

## 7. First-ply failure

The strength ratio $`R`$ of a ply is the factor on its stress at which the chosen criterion is met; the engine defines it for maximum stress, maximum strain, Tsai-Hill and Tsai-Wu ([engine theory](../../engine/docs/theory.md), Section 5) and exposes the per-face dispatch as `face_strength_ratio`, which the kernel calls with the ply's stress as the scaled part and nothing held. Over the mesh the smallest ratio is the first-ply-failure factor: the problem is linear, so the applied displacement or load multiplied by this factor fails that ply of that element first,

```math
\lambda_{\mathrm{FPF}} = \min_{e,\,k} R^{(e,k)} ,
```

computed by `strength_ratios`, which also returns every ratio and governing mode and the element and ply that govern. Identical plies in a uniform state tie exactly; ratios within a relative $`10^{-9}`$ of the minimum count as tied and the first element in deck order, then the bottom-most ply, is reported, so the location is decided by position and not by roundoff. The Tsai-Wu interaction term $`f_{12}^*`$ comes from the deck's `*Fail Stress` sixth value when every material states the same one, computed by `deck_f12_star`; without it Tsai-Wu is refused, as the engine refuses it (ADR-0021). Maximum strain is refused when no strain limits exist, since an Abaqus deck carries none. First-ply failure is the onset of damage in one ply, not the coupon's ultimate strength.

<!-- code: strength_ratios, deck_f12_star -->

## 8. The flat shell: bending, transverse shear and pressure (`shell.py`)

The membrane of Sections 1 to 7 stays the kernel for the in-plane coupons; every result it gives is pinned by the cases and records above. A deck that bends, carries a pressure, prescribes or loads a degree of freedom out of the plane, or has an unsymmetric layup goes to the flat shell of this section (ADR-0053), which keeps the same mesh, the same four-node element and the same engine laminate law. Which kernel a deck gets is computed by `needs_shell`, the dispatch is computed by `solve_deck`, and what the membrane refuses when it is asked directly is checked by `membrane_limits`.

<!-- code: needs_shell, solve_deck, membrane_limits -->

### 8.1 Kinematics and the laminate law

Each node carries five degrees of freedom, $`u, v, w, \theta_x, \theta_y`$: the translations along x, y, z and the rotations about the x and y axes, Abaqus dofs 1 to 5. The drilling rotation, dof 6, has no stiffness in a flat plate and is dropped (a boundary on it is noted, a load on it refused). The displacement through the thickness is that of the first-order shear deformation theory (Whitney, *Structural Analysis of Laminated Anisotropic Plates*, 1987, Eq. 10.1, written with the rotations about the axes, $`\psi_x = \theta_y`$ and $`\psi_y = -\theta_x`$):

```math
u(x, y, z) = u_0 + z\,\theta_y, \qquad v(x, y, z) = v_0 - z\,\theta_x, \qquad w(x, y, z) = w ,
```

so the in-plane strain is $`\boldsymbol{\varepsilon} = \boldsymbol{\varepsilon}_0 + z\,\boldsymbol{\kappa}`$ with the membrane strain of Section 2 and the curvatures (Whitney Eqs. 10.2 and 10.3)

```math
\boldsymbol{\kappa} = \begin{bmatrix} \kappa_x \\ \kappa_y \\ \kappa_{xy} \end{bmatrix}
= \begin{bmatrix} \partial \theta_y / \partial x \\ -\,\partial \theta_x / \partial y \\ \partial \theta_y / \partial y - \partial \theta_x / \partial x \end{bmatrix},
\qquad
\boldsymbol{\gamma} = \begin{bmatrix} \gamma_{xz} \\ \gamma_{yz} \end{bmatrix}
= \begin{bmatrix} \partial w / \partial x + \theta_y \\ \partial w / \partial y - \theta_x \end{bmatrix}
```

the transverse shear strains (Whitney Eq. 10.4), constant through the thickness. The section forces follow the engine's laminate law with $`\mathbf{B}`$ kept ([engine theory](../../engine/docs/theory.md), Section 3; Whitney Eq. 10.5) and the shear law of Whitney Eqs. 10.6 and 10.7:

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

The element is the bilinear quadrilateral of Section 2 with the five dofs per node, and the element dof vector is $`\mathbf{u}_e = [u_1, v_1, w_1, \theta_{x1}, \theta_{y1}, \dots, \theta_{y4}]^T`$. With the physical derivatives $`\partial N_i / \partial x`$ and $`\partial N_i / \partial y`$ of Section 2, the membrane strain is $`\boldsymbol{\varepsilon}_0 = \mathbf{B}_m \mathbf{u}_e`$ and the curvature $`\boldsymbol{\kappa} = \mathbf{B}_b \mathbf{u}_e`$, with the rows of $`\mathbf{B}_m`$ computed by `membrane_rows` and the rows of $`\mathbf{B}_b`$ computed by `bending_rows`:

```math
\mathbf{B}_{b,i} = \begin{bmatrix} 0 & 0 & 0 & 0 & \partial N_i / \partial x \\ 0 & 0 & 0 & -\partial N_i / \partial y & 0 \\ 0 & 0 & 0 & -\partial N_i / \partial x & \partial N_i / \partial y \end{bmatrix}.
```

<!-- code: membrane_rows -->

<!-- code: bending_rows -->

A displacement-based bilinear plate element locks as the plate gets thin, because the bilinear $`w`$ cannot make $`\boldsymbol{\gamma}`$ vanish while bending. The MITC4 element of Bathe and Dvorkin (K.-J. Bathe, *Finite Element Procedures*, 2nd ed., 2014, the mixed-interpolated plate elements of Chapter 5; the section and equation numbers are not checked against a copy here) interpolates the transverse shear strains from their values at the edge midpoints instead. In natural coordinates the covariant shear strains of the bilinear fields are

```math
\gamma_\xi = \frac{\partial w}{\partial \xi} + \frac{\partial x}{\partial \xi}\theta_y - \frac{\partial y}{\partial \xi}\theta_x, \qquad
\gamma_\eta = \frac{\partial w}{\partial \eta} + \frac{\partial x}{\partial \eta}\theta_y - \frac{\partial y}{\partial \eta}\theta_x ,
```

computed by `covariant_shear_rows` at a point. The assumed field takes $`\gamma_\xi`$ at the midpoints A $`(0, 1)`$ and C $`(0, -1)`$ and $`\gamma_\eta`$ at D $`(1, 0)`$ and B $`(-1, 0)`$, and interpolates each linearly across the element,

```math
\gamma_\xi(\xi, \eta) = \tfrac12 (1 + \eta)\, \gamma_\xi^A + \tfrac12 (1 - \eta)\, \gamma_\xi^C, \qquad
\gamma_\eta(\xi, \eta) = \tfrac12 (1 + \xi)\, \gamma_\eta^D + \tfrac12 (1 - \xi)\, \gamma_\eta^B ,
```

and the Cartesian strains follow from $`[\gamma_\xi, \gamma_\eta]^T = \mathbf{J}\,[\gamma_{xz}, \gamma_{yz}]^T`$ with the Jacobian of Section 2. The rows of the resulting $`\mathbf{B}_s`$, $`\boldsymbol{\gamma} = \mathbf{B}_s \mathbf{u}_e`$, are computed by `shear_rows`. On a pure bending field $`w = -\kappa x^2 / 2`$, $`\theta_y = \kappa x`$, the tied strains vanish at every point, which the displacement-based element cannot do.

<!-- code: covariant_shear_rows -->

<!-- code: shear_rows -->

The element stiffness, with the 2 by 2 Gauss rule of Section 2 and the laminate matrices of Section 8.1, is computed by `element_stiffness_shell`:

```math
\mathbf{k}_e = \sum_{g} w_g\, \det \mathbf{J}_g \left( \mathbf{B}_m^T \mathbf{A} \mathbf{B}_m + \mathbf{B}_m^T \mathbf{B} \mathbf{B}_b + \mathbf{B}_b^T \mathbf{B} \mathbf{B}_m + \mathbf{B}_b^T \mathbf{D} \mathbf{B}_b + \mathbf{B}_s^T \mathbf{H} \mathbf{B}_s \right).
```

It is symmetric and has exactly six zero eigenvalues: three translations, the two tilts and the in-plane rotation; no spurious mode.

<!-- code: element_stiffness_shell -->

A uniform pressure $`p`$ on an element (`*Dload` with the P label) becomes the consistent nodal forces on $`w`$, computed by `pressure_loads`:

```math
f_{w,i} = -\,p \sum_g w_g\, \det \mathbf{J}_g\, N_i(\xi_g, \eta_g) ,
```

the sign being that of the Abaqus label, positive against the element normal, which is $`+z`$ for counterclockwise nodes. The CalculiX convention is not assumed; it is detected by a run and recorded in `fea/checks/calculix-conventions.toml` (Section 9 of that file once the detection run exists; UNVERIFIED until then).

<!-- code: pressure_loads -->

### 8.3 Constraints, assembly and solution

Degrees of freedom are numbered $`5i`$ to $`5i + 4`$ for node $`i`$. A kinematic coupling aliases every coupled dof the coupling names (dofs 1 to 5; dof 6 is dropped) to the reference node's, so a coupled edge translates and tilts with its reference node and the reference node's reaction carries the summed forces and moments. Prescribed values on dofs 1 to 5, concentrated loads on dofs 1 to 5 (forces in N, moments in N m) and the pressure forces are collected on the reduced dofs, with the same conflict and detachment refusals as Section 3; all of this is computed by `constraint_map_shell`, and the sparse global stiffness is computed by `assemble_shell`. The partition, the sparse LU solve, the singularity checks and the reactions as the residual at the prescribed dofs are those of Section 4; a plate whose translation along z or whose tilts are nowhere held is refused with that message. The solve is computed by `solve_shell`.

<!-- code: constraint_map_shell -->

<!-- code: assemble_shell -->

<!-- code: solve_shell -->

### 8.4 Recovery with faces

At every element's centroid the membrane strain, the curvature and the transverse shear strain are $`\mathbf{B}_m \mathbf{u}_e`$, $`\mathbf{B}_b \mathbf{u}_e`$ and $`\mathbf{B}_s \mathbf{u}_e`$, computed by `element_states`; the section forces, moments and shear forces follow from the law of Section 8.1. Because the curvature is not zero, each ply's strain differs between its bottom and top face, $`\boldsymbol{\varepsilon}(z) = \boldsymbol{\varepsilon}_0 + z\,\boldsymbol{\kappa}`$, so the ply recovery of Section 6 keeps both faces of every ply (the engine's `ply_surfaces` with the element's curvature) and the strength ratios of Section 7 are evaluated on each face; the first ply to fail is named with its face, and ties are broken by element, then ply, then the bottom face. A membrane state keeps one value per ply as before.

<!-- code: element_states -->

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

## Not modeled yet

- Rotated laminate axes (an `*Orientation` other than the global axes)
- Triangles, higher-order shells, solids, membranes (M3D4)
- Distributed loads other than a uniform pressure per element (surface tractions, gravity, line loads by `*Dload`); thermal strain
- Interlaminar stresses from equilibrium (the transverse shear stress is uniform through the thickness in the shell's law, Whitney Eq. 10.22, and is not reported per ply)
- Abaqus-style failure indices (MSTRS, TSAIH, TSAIW) as numbers to compare against; progressive failure
- Finite element buckling
