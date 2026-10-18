# Finite element theory

Every equation the finite element layer uses, and the function that computes it (ADR-0029). The element formulation follows K.-J. Bathe, *Finite Element Procedures*, 2nd edition (2014), Chapter 5 (formulation and calculation of isoparametric finite element matrices); the laminate stiffness comes from the engine ([engine theory](../../engine/docs/theory.md), Section 3). The kernel works in SI units throughout; a deck's units are converted once on entry (ADR-0002).

## Conventions

- The laminate x axis is the deck's global x axis: the only orientation the reader accepts is the global one, so ply angles are measured from global x, counterclockwise, as in ADR-0004.
- Each node has two degrees of freedom, $`u`$ along x and $`v`$ along y. Abaqus dofs 1 and 2. There are no out-of-plane or rotational degrees of freedom.
- Strain is the membrane (midplane) strain $`\boldsymbol{\varepsilon} = [\varepsilon_x, \varepsilon_y, \gamma_{xy}]^T`$ with engineering shear.
- Section forces are resultants per unit width, $`\mathbf{N} = [N_x, N_y, N_{xy}]^T`$ in N/m, what Abaqus reports as SF.
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

In natural coordinates $`(\xi, \eta) \in [-1, 1]^2`$ the four nodes sit at $`(\xi_i, \eta_i) = (\mp 1, \mp 1)`$ counterclockwise. The shape functions (Bathe Eq. 5.18 for the two-dimensional case), computed by `shape_functions`:

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

## 7. First-ply failure

The strength ratio $`R`$ of a ply is the factor on its stress at which the chosen criterion is met; the engine defines it for maximum stress, maximum strain, Tsai-Hill and Tsai-Wu ([engine theory](../../engine/docs/theory.md), Section 5) and exposes the per-face dispatch as `face_strength_ratio`, which the kernel calls with the ply's stress as the scaled part and nothing held. Over the mesh the smallest ratio is the first-ply-failure factor: the problem is linear, so the applied displacement or load multiplied by this factor fails that ply of that element first,

```math
\lambda_{\mathrm{FPF}} = \min_{e,\,k} R^{(e,k)} ,
```

computed by `strength_ratios`, which also returns every ratio and governing mode and the element and ply that govern. Identical plies in a uniform state tie exactly; ratios within a relative $`10^{-9}`$ of the minimum count as tied and the first element in deck order, then the bottom-most ply, is reported, so the location is decided by position and not by roundoff. The Tsai-Wu interaction term $`f_{12}^*`$ comes from the deck's `*Fail Stress` sixth value when every material states the same one, computed by `deck_f12_star`; without it Tsai-Wu is refused, as the engine refuses it (ADR-0021). Maximum strain is refused when no strain limits exist, since an Abaqus deck carries none. First-ply failure is the onset of damage in one ply, not the coupon's ultimate strength.

<!-- code: strength_ratios, deck_f12_star -->

## Checks

- Shape functions sum to one and take the value one at their own node; their derivatives sum to zero; $`\mathbf{B}`$ on the unit square matches hand values.
- A uniform strain field is recovered exactly from nodal displacements at every Gauss point of a skewed element.
- $`\mathbf{k}`$ is symmetric with three zero eigenvalues; rigid translations and rotation give zero force; clockwise and bow-tie elements are refused.
- Engine equality (validation cases `patch-1x1-im7-engine-equality`, `patch-2x2-im7-engine-equality`, `patch-1x1-cload-im7-engine-equality`): one element and a 2 by 2 mesh of an IM7/8552 [0/45/-45/45/0]s coupon under prescribed edge displacement and under edge load reproduce the engine's midplane strain, section force and reaction; a generated 4 by 8 mesh agrees to 1e-12.
- Isotropic closed forms (`isotropic-uniaxial-plane-stress`, `isotropic-simple-shear`): $`\varepsilon_x = -\nu\varepsilon_y`$, $`N_y = E h \varepsilon_y`$; $`N_{xy} = G h \gamma_{xy}`$.
- A coupled edge driven by a reference node gives the same displacements as the same edge prescribed node by node, and the reference node's reaction equals the summed edge reactions.
- The gripped 2 by 8 coupon: reactions in equilibrium, top and bottom reference reactions equal and opposite, the finer 4 by 16 mesh no stiffer than the coarse one.
- Ply stresses in material axes equal the engine's `ply_surfaces` on the uniform cases for all ten plies; the first-ply-failure factor, governing ply and mode equal the engine's `first_ply_failure` for maximum stress, Tsai-Hill and Tsai-Wu; the factor halves when the imposed displacement doubles; the gripped coupon fails first in an end row next to a grip; missing strengths, strain limits or $`f_{12}^*`$ are refused by name.

## Not modeled yet

- Bending and the $`\mathbf{D}`$ matrix; unsymmetric layups; transverse shear
- Rotated laminate axes (an `*Orientation` other than the global axes)
- Triangles, higher-order shells, solids, membranes (M3D4)
- Distributed loads and pressure; thermal strain
- Abaqus-style failure indices (MSTRS, TSAIH, TSAIW) as numbers to compare against (comparison chunk); progressive failure
- Finite element buckling; holes meshed by us (Gmsh chunk)
