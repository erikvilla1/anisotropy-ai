# Peel test (double cantilever beam): the model of test_bond_solver.py, for an independent run in MOOSE (see README.md)
# Peel test (double cantilever beam): the same model as the prototype's, for an independent run
L = 100
h = 1.98
a0 = 30
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
  [upper_end]
    type = SideSetsAroundSubdomainGenerator
    input = bond
    block = upper
    normal = '-1 0 0'
    new_boundary = upper_end
  []
  [lower_end]
    type = SideSetsAroundSubdomainGenerator
    input = upper_end
    block = lower
    normal = '-1 0 0'
    new_boundary = lower_end
  []
  [far_low]
    type = ExtraNodesetGenerator
    input = lower_end
    coord = '${L} ${fparse -h} 0'
    new_boundary = far_low
  []
  [far_up]
    type = ExtraNodesetGenerator
    input = far_low
    coord = '${L} ${h} 0'
    new_boundary = far_up
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
  [open_up]
    type = FunctionDirichletBC
    boundary = upper_end
    variable = disp_y
    function = '0.5*t'
    preset = true
  []
  [open_down]
    type = FunctionDirichletBC
    boundary = lower_end
    variable = disp_y
    function = '-0.5*t'
    preset = true
  []
  [hold]
    type = DirichletBC
    boundary = 'far_low far_up'
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
  [czm]
    type = BiLinearMixedModeTraction
    boundary = 'bond'
    penalty_stiffness = 1e5
    GI_c = 0.352
    GII_c = 0.352
    normal_strength = ${SIGMA}
    shear_strength = ${SIGMA}
    eta = 2
    viscosity = ${VISC}
  []
[]

[Postprocessors]
  [force]
    type = NodalSum
    variable = resid_y
    boundary = upper_end
  []
  [force_stress]
    type = SidesetReaction
    direction = '0 1 0'
    stress_tensor = stress
    boundary = upper_end
  []
  [mid_y]
    type = PointValue
    variable = disp_y
    point = '50 ${h} 0'
  []
  [tip_y]
    type = PointValue
    variable = disp_y
    point = '0 ${h} 0'
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
  end_time = 5.3
  dtmin = 1e-7
  [TimeStepper]
    type = IterationAdaptiveDT
    dt = 0.05
    optimal_iterations = 8
    growth_factor = 1.5
    cutback_factor = 0.5
  []
  dtmax = 0.05
[]

[Outputs]
  csv = true
  file_base = ${OUT}
[]
