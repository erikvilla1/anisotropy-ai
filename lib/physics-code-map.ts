/**
 * Which engine functions compute the equation on each physics card, and the decision that added them (ADR-0019 amendment 1).
 * The cards a customer reads carry no function names or decision numbers; this map keeps the link for the repository. Only
 * tests import it: tests/physics-reference.test.ts checks that every card named here exists and that every function is
 * defined in engine/src.
 */
export const physicsCodeMap: Record<string, { functions: string[]; decision?: string }> = {
  "Laminate compliance · ABD inverse": { functions: ["abd_compliance"] },
  "Known forces & prescribed curvature": { functions: ["prescribed_curvature_response", "forward_verification"], decision: "ADR-0013" },
  "Mixed load & deformation conditions": { functions: ["mixed_response"], decision: "ADR-0016" },
  "Laminate engineering constants": { functions: ["engineering_constants"] },
  "First-ply failure load": { functions: ["first_ply_failure"] },
  "Strength ratio with fixed & variable loads": { functions: ["tsai_wu_ratio_combined", "max_stress_ratio_combined"], decision: "ADR-0017" },
  "Laminate symmetry, balance & areal mass": { functions: ["laminate_summary", "is_symmetric", "is_balanced", "laminate_kind", "coupling_flags", "areal_mass"], decision: "ADR-0059" },
  "Thermal resultants · uniform ΔT": { functions: ["thermal_resultants", "thermomechanical_response"], decision: "ADR-0014" },
  "Residual ply stress after ΔT": { functions: ["thermal_ply_surfaces"] },
  "First-ply failure under ΔT alone": { functions: ["first_ply_failure_thermal"] },
  "Maximum strain": { functions: ["max_strain_ratio", "strain_limits_from_strengths"], decision: "ADR-0021" },
  "Tsai-Hill": { functions: ["tsai_hill_index", "tsai_hill_ratio"] },
  "Plate buckling · simply supported": { functions: ["navier_buckling", "ritz_buckling", "plate_buckling"], decision: "ADR-0022" },
  "Longitudinal rule of mixtures": { functions: ["rule_of_mixtures", "lamina_from_constituents"] },
  "Transverse inverse-mixture estimate": { functions: ["series_model", "constrained_matrix_modulus"] },
  "In-plane shear inverse-mixture estimate": { functions: ["series_model"] },
  "Halpin–Tsai estimate": { functions: ["halpin_tsai"] },
  "Fibre tow strength & chord modulus": { functions: ["tow_strength", "tow_chord_modulus", "resin_content", "sample_statistics"], decision: "ADR-0074" },
};
