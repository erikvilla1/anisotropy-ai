# Shear test (end-notched flexure): the model of test_bond_solver.py, for an independent run in MOOSE (see README.md)
# Shear test (end-notched flexure): the same model as the prototype's, for an independent run
L = 100
Ls = 50
h = 1.98
a0 = 35
nx = ${NX}
[Mesh]
  [msh]
    type = GeneratedMeshGenerator
    dim = 2
    xmin = 0
    xmax = ${L}
    ymin = ${fparse -h}
    ymax = ${h}
    nx = ${nx}
    ny = 8
    elem_type = QUAD8
  []
  [lower]
    type = SubdomainBoundingBoxGenerator
    input = msh
    bottom_left = '0 ${fparse -h} 0'
    top_right = '${L} 0 0'
    block_id = 1
    block_name = lower
  []
  [upper]
    type = SubdomainBoundingBoxGenerator
    input = lower
    bottom_left = '0 0 0'
    top_right = '${L} ${h} 0'
    block_id = 2
    block_name = upper
  []
  [split]
    type = BreakMeshByBlockGenerator
    input = upper
  []
  [bond]
    type = ParsedGenerateSideset
    input = split
    included_boundaries = lower_upper
    combinatorial_geometry = 'x > ${a0}'
    new_sideset_name = bond
  []
  [crack]
    type = ParsedGenerateSideset
    input = bond
    included_boundaries = lower_upper
    combinatorial_geometry = 'x < ${a0}'
    new_sideset_name = crack
  []
  [left_support]
    type = ExtraNodesetGenerator
    input = crack
    coord = '0 ${fparse -h} 0'
    new_boundary = left_support
  []
  [right_support]
    type = ExtraNodesetGenerator
    input = left_support
    coord = '${L} ${fparse -h} 0'
    new_boundary = right_support
  []
  [load_point]
    type = ExtraNodesetGenerator
    input = right_support
    coord = '${Ls} ${h} 0'
    new_boundary = load_point
  []
[]

[GlobalParams]
  displacements = 'disp_x disp_y'
[]

[Problem]
  extra_tag_vectors = 'ref'
[]

[Physics]
  [SolidMechanics]
    [QuasiStatic]
      [all]
        strain = SMALL
        add_variables = true
        extra_vector_tags = 'ref'
      []
    []
    [CohesiveZone]
      [bond]
        boundary = 'bond'
        strain = SMALL
        base_name = bond
      []
      [crack]
        boundary = 'crack'
        strain = SMALL
        base_name = crack
      []
    []
  []
[]

[AuxVariables]
  [resid_y]
    order = SECOND
    family = LAGRANGE
  []
[]

[AuxKernels]
  [resid_y]
    type = TagVectorAux
    variable = resid_y
    v = disp_y
    vector_tag = ref
    remove_variable_scaling = true
  []
[]

[BCs]
  [press]
    type = FunctionDirichletBC
    boundary = load_point
    variable = disp_y
    function = '-t'
    preset = true
  []
  [supports]
    type = DirichletBC
    boundary = 'left_support right_support'
    variable = disp_y
    value = 0
    preset = true
  []
  [hold]
    type = DirichletBC
    boundary = 'left_support'
    variable = disp_x
    value = 0
    preset = true
  []
[]

[Materials]
  [stress]
    type = ComputeLinearElasticStress
  []
  [elasticity_tensor]
    type = ComputeElasticityTensor
    fill_method = symmetric9
    C_ijkl = '152542.3729 5084.745763 5084.745763 13962.59497 6376.388077 13962.59497 3700 6000 6000'
  []
  [numbers]
    type = GenericConstantMaterial
    prop_names = 'bond_gc bond_s crack_gc crack_s'
    prop_values = '1.0 ${SIGMA} 1e-12 1e-6'
  []
  [czm]
    type = BiLinearMixedModeTraction
    boundary = 'bond'
    base_name = bond
    penalty_stiffness = 1e5
    GI_c = gc
    GII_c = gc
    normal_strength = s
    shear_strength = s
    eta = 2
    viscosity = ${VISC}
  []
  [open]
    type = BiLinearMixedModeTraction
    boundary = 'crack'
    base_name = crack
    penalty_stiffness = 1e5
    GI_c = gc
    GII_c = gc
    normal_strength = s
    shear_strength = s
    eta = 2
    viscosity = 0
  []
[]

[Postprocessors]
  [force]
    type = NodalSum
    variable = resid_y
    boundary = load_point
  []
[]

[Preconditioning]
  [smp]
    type = SMP
    full = true
  []
[]

[Executioner]
  type = Transient
  solve_type = NEWTON
  line_search = none
  petsc_options_iname = '-pc_type -pc_factor_mat_solver_type'
  petsc_options_value = 'lu superlu_dist'
  automatic_scaling = true
  nl_max_its = 25
  nl_rel_tol = 1e-8
  nl_abs_tol = 1e-8
  start_time = 0
  end_time = 2.6
  dtmin = 1e-7
  [TimeStepper]
    type = IterationAdaptiveDT
    dt = 0.02
    optimal_iterations = 8
    growth_factor = 1.5
    cutback_factor = 0.5
  []
  dtmax = 0.02
[]

[Outputs]
  csv = true
  file_base = ${OUT}
[]
