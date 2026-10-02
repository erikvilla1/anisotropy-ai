import { foundationTopics, maximumStrain, bookReference, coreReferences } from "./physics-foundations";
export type Method = { name: string; equation: string; detail: string;
  reference?: { title: string; url: string; location: string }; units?: string };
export type PhysicsTopic = {
  id: string;
  title: string;
  subtitle: string;
  assumptions: string;
  source: string;
  url: string;
  methods: Method[];
};
const m = (name: string, equation: string, detail: string): Method => ({
  name,
  equation,
  detail,
});
const existingPhysicsTopics: PhysicsTopic[] = [
  {
    id: "clt",
    title: "Classical Laminate Theory",
    subtitle: "From a single ply to laminate response",
    assumptions:
      "Thin, perfectly bonded, linearly elastic orthotropic plies; small deformation and plane stress. Engineering shear strain γ is used. Angles rotate global x–y into local fiber axes 1–2; z is measured from the laminate mid-plane.",
    source: "NASA RP-1351 · Basic Mechanics of Laminated Composite Plates",
    url: "https://ntrs.nasa.gov/citations/19950009349",
    methods: [
      m(
        "Reciprocity & compliance S",
        "ν₂₁ = ν₁₂ E₂/E₁\nS = [[1/E₁, −ν₁₂/E₁, 0],\n     [−ν₁₂/E₁, 1/E₂, 0],\n     [0, 0, 1/G₁₂]]",
        "Inputs: E₁, E₂, G₁₂, ν₁₂. Maps local stress [σ₁, σ₂, τ₁₂] to strain [ε₁, ε₂, γ₁₂]. Check positive stiffness and 1 − ν₁₂ν₂₁ > 0.",
      ),
      m(
        "Reduced stiffness Q",
        "Δ = 1 − ν₁₂ν₂₁\nQ₁₁ = E₁/Δ    Q₂₂ = E₂/Δ\nQ₁₂ = ν₁₂E₂/Δ    Q₆₆ = G₁₂\nQ = [[Q₁₁,Q₁₂,0],[Q₁₂,Q₂₂,0],[0,0,Q₆₆]]",
        "Inverts the plane-stress compliance. Q₁₆ and Q₂₆ vanish in orthotropic material axes. All moduli must use consistent units.",
      ),
      m(
        "Stress transformation Tσ",
        "m = cos θ; n = sin θ\nTσ = [[m², n², 2mn],\n      [n², m², −2mn],\n      [−mn, mn, m²−n²]]\nσ₁₂ = Tσ σxy",
        "Transforms global stress to the local fiber/transverse system. The stress and engineering-strain transformations differ in their shear terms.",
      ),
      m(
        "Strain transformation Tε",
        "Tε = [[m², n², mn],\n      [n², m², −mn],\n      [−2mn, 2mn, m²−n²]]\nε₁₂ = Tε εxy",
        "Transforms [εx, εy, γxy] to [ε₁, ε₂, γ₁₂]. Using a stress matrix for engineering shear strain would give incorrect off-axis results.",
      ),
      m(
        "Transformed stiffness Q̄",
        "Q̄ = Tσ⁻¹ Q Tε\nσxy = Q̄ εxy",
        "Produces each ply’s global stiffness, including Q̄₁₆ and Q̄₂₆ coupling. At θ = 0°, Q̄ = Q; the inverse transform corresponds to −θ.",
      ),
      m(
        "Ply interfaces & thickness",
        "h = Σ tₖ    z₀ = −h/2\nzₖ = zₖ₋₁ + tₖ",
        "Builds the through-thickness coordinates from an ordered layup and each cured ply thickness. Record which physical face is first in the stack.",
      ),
      m(
        "Extensional stiffness A",
        "Aᵢⱼ = Σ Q̄ᵢⱼ⁽ᵏ⁾ (zₖ − zₖ₋₁)",
        "Integrates ply stiffness over thickness. Units: force/length. Maps mid-plane strain to in-plane force resultants when coupling is absent.",
      ),
      m(
        "Extension–bending coupling B",
        "Bᵢⱼ = ½ Σ Q̄ᵢⱼ⁽ᵏ⁾ (zₖ² − zₖ₋₁²)",
        "Units: force. An exactly symmetric stiffness distribution about the mid-plane gives B = 0; numerical checks should allow roundoff.",
      ),
      m(
        "Bending stiffness D",
        "Dᵢⱼ = ⅓ Σ Q̄ᵢⱼ⁽ᵏ⁾ (zₖ³ − zₖ₋₁³)",
        "Units: force × length. Accounts for the greater bending contribution of plies farther from the mid-plane.",
      ),
      m(
        "Laminate response · ABD solve",
        "[N; M] + [Nʰ; Mʰ] = [[A,B],[B,D]] [ε⁰; κ]",
        "Solve the six coupled equations for mid-plane strains and curvatures. N and M are mechanical force and moment resultants per unit width; superscript h denotes equivalent thermal/moisture loads.",
      ),
      m(
        "Thermal & moisture resultants",
        "εʰₖ = ᾱₖ ΔT + β̄ₖ Δc\nNʰ = Σ ∫ Q̄ₖ εʰₖ dz\nMʰ = Σ ∫ z Q̄ₖ εʰₖ dz",
        "Transform expansion coefficients with the strain convention. Integrate over each ply. State the stress-free reference temperature and moisture concentration units; supplied coefficients need a reviewed basis.",
      ),
      m(
        "Global strain recovery",
        "εxy(z) = ε⁰ + zκ\nεxy,mech(z) = εxy(z) − εʰₖ",
        "Recover the total and mechanical strains at each ply’s upper and lower surface. Adjacent plies share total strain at an interface under CLT assumptions.",
      ),
      m(
        "Local strains & local stresses",
        "ε₁₂,mech = Tε εxy,mech\nσ₁₂ = Q ε₁₂,mech\nσxy = Tσ⁻¹ σ₁₂",
        "Recover fiber, transverse, and shear stress for failure assessment. Stress can jump between dissimilar plies even when the interface strain is continuous.",
      ),
      m(
        "Laminate engineering constants",
        "a = A⁻¹\nEx = 1/(h a₁₁)    Ey = 1/(h a₂₂)\nGxy = 1/(h a₆₆)    νxy = −a₁₂/a₁₁",
        "These membrane expressions assume B = 0 and unrestrained lateral response. For coupled laminates, derive effective compliance from the full ABD system and state the loading constraints.",
      ),
    ],
  },
  {
    id: "failure",
    title: "Ply failure criteria",
    subtitle: "Evaluate local stresses against a defined strength basis",
    assumptions:
      "Use positive strength magnitudes Xₜ, X꜀, Yₜ, Y꜀ and S with tension-positive local stresses. Appendix compressive values are signed source values and require explicit sign normalization before calculation. Failure indices indicate initiation, not residual strength or fracture location certainty.",
    source: "COMSOL · Failure prediction in a laminated composite shell",
    url: "https://doc.comsol.com/6.4/doc/com.comsol.help.models.compmat.failure_prediction_in_a_laminated_composite_shell/failure_prediction_in_a_laminated_composite_shell.html",
    methods: [
      m(
        "Maximum stress",
        "r₁ = σ₁/Xₜ (σ₁ ≥ 0); −σ₁/X꜀ (σ₁ < 0)\nr₂ = σ₂/Yₜ (σ₂ ≥ 0); −σ₂/Y꜀ (σ₂ < 0)\nFI = max(r₁, r₂, |τ₁₂|/S)",
        "Checks fiber, transverse, and shear limits separately. FI ≥ 1 indicates initiation; this criterion does not model interaction between stress components.",
      ),
      m(
        "Tsai–Hill",
        "FI = (σ₁/X)² − σ₁σ₂/X²\n     + (σ₂/Y)² + (τ₁₂/S)²",
        "This documented plane-stress convention selects X = Xₜ or X꜀ by the sign of σ₁ and Y similarly by σ₂. Mixed-sign conventions differ between implementations; record the convention before comparisons. FI ≥ 1 indicates initiation.",
      ),
      m(
        "Tsai–Wu coefficients",
        "F₁ = 1/Xₜ − 1/X꜀    F₂ = 1/Yₜ − 1/Y꜀\nF₁₁ = 1/(XₜX꜀)    F₂₂ = 1/(YₜY꜀)\nF₆₆ = 1/S²    F₁₂ = f₁₂ √(F₁₁F₂₂)",
        "The biaxial interaction coefficient f₁₂ needs experimental evidence or an explicitly recorded assumption. It cannot be inferred from uniaxial strengths alone. Require |f₁₂| < 1 for a positive-definite normal-stress quadratic.",
      ),
      m(
        "Tsai–Wu failure index",
        "FI = F₁σ₁ + F₂σ₂ + F₁₁σ₁²\n     + F₂₂σ₂² + 2F₁₂σ₁σ₂ + F₆₆τ₁₂²",
        "FI ≥ 1 marks the chosen failure envelope. The scalar index does not identify fiber versus matrix failure; report it alongside mode-sensitive criteria and the input strength basis.",
      ),
      m(
        "Hashin · fiber modes",
        "Tension (σ₁ ≥ 0):\nFIft = (σ₁/Xₜ)² + α(τ₁₂/Sᴸ)²\nCompression (σ₁ < 0):\nFIfc = (σ₁/X꜀)²",
        "Plane-stress initiation formulation for unidirectional plies. α weights shear participation in fiber tension and must be specified; α = 1 is a common choice. Sᴸ is longitudinal shear strength.",
      ),
      m(
        "Hashin · matrix modes",
        "Tension (σ₂ ≥ 0):\nFImt = (σ₂/Yₜ)² + (τ₁₂/Sᴸ)²\nCompression (σ₂ < 0):\nFImc = (σ₂/2Sᵀ)² + [(Y꜀/2Sᵀ)² − 1]σ₂/Y꜀\n       + (τ₁₂/Sᴸ)²",
        "Sᵀ is transverse shear strength, distinct from Sᴸ. Missing strength data must remain unresolved. A woven architecture needs an applicable, validated failure formulation rather than automatic reuse of UD criteria.",
      ),
      m(
        "Strength ratio & safety margin",
        "FI(Rσ) = 1\nTsai–Wu: aR² + bR − 1 = 0\nMS = R/FS − 1",
        "Find the smallest positive load multiplier R reaching initiation; a and b are the quadratic and linear stress terms. For homogeneous quadratic criteria, R = 1/√FI. FS is the specified safety factor. Handle zero stress and the linear limiting case explicitly.",
      ),
    ],
  },
  {
    id: "fea",
    title: "CAD, FEA & verification",
    subtitle: "Geometry, boundary conditions, and independent checks",
    assumptions:
      "The relations below describe a small-displacement linear elastic analysis. Solver choice, element formulation, geometry tolerances, units, and acceptance thresholds belong in the analysis record.",
    source: "Anisotropy AI · Analysis workflow",
    url: "/services",
    methods: [
      m(
        "Parametric geometry & mesh",
        "Geometry = g(length, width, thickness, hole, fillets)\nMesh = discretize(Geometry, element type, size)",
        "Define a reproducible CAD model; check dimensions, hole/edge distances, ply thickness, and mesh quality. STEP geometry and mesh exports are planned product deliverables.",
      ),
      m(
        "Finite element equilibrium",
        "K u = f\nε = Bₑ uₑ    σ = C εmech",
        "Apply supports and loads, solve nodal displacements, and recover strain/stress using the element strain–displacement matrix Bₑ. Do not confuse Bₑ with laminate coupling B.",
      ),
      m(
        "Mesh convergence",
        "δq = |qfine − qcoarse| / |qfine|",
        "Track relevant quantities across mesh refinements against an agreed tolerance. Use an absolute scale if qfine is near zero. A stress singularity may not converge; investigate its cause before accepting a peak.",
      ),
      m(
        "CLT–FEA & test comparison",
        "Δq = qmodel − qreference\nRelative discrepancy = |Δq| / |qreference|",
        "Compare equivalent loads, axes, units, regions, and boundary conditions. CLT comparison applies away from 3D/local effects. Physical-test discrepancies must include uncertainty; thresholds are defined for the study.",
      ),
      m(
        "Verification gate",
        "release = inputs reviewed ∧ MS ≥ 0\n          ∧ convergence passed ∧ cross-checks passed",
        "A planned gate for reporting a passing design. Failed or unresolved checks produce an investigation record with the failure reason, rather than an approved result. An engineering review remains part of the workflow.",
      ),
    ],
  },
  {
    id: "open-hole",
    title: "Open-hole strength & damage",
    subtitle: "Local fields, calibrated models, and future development",
    assumptions:
      "A hole introduces nonuniform stress. Unnotched lamina strength alone does not validate open-hole strength. Coupon geometry, laminate architecture, characteristic length, and test evidence must match the chosen model.",
    source: "Anisotropy AI · Research scope",
    url: "/services",
    methods: [
      m(
        "Stress concentration",
        "Kt = σlocal,max / σnominal",
        "Record whether nominal stress uses gross or net section area. Extract local fields from an applicable solution or a converged model; isotropic infinite-plate factors are not general laminate solutions.",
      ),
      m(
        "Point-stress criterion",
        "σyy(x = a + d₀, y = 0) = Xlaminate",
        "For tension in y and a hole of radius a, compare stress on the transverse ligament at a calibrated characteristic distance d₀. Requires matching unnotched laminate strength and open-hole calibration; it is not a universal material constant.",
      ),
      m(
        "Progressive failure · future",
        "σ = C(d) εmech;    0 ≤ d ≤ 1",
        "Research direction only. Initiation must be paired with a calibrated damage-evolution law, energy regularization, and independent tests. Residual-strength and damage-evolution analysis are outside this preview.",
      ),
    ],
  },
  {
    id: "optimization",
    title: "Layup design & optimization",
    subtitle: "Search candidates, then verify the proposed stack",
    assumptions:
      "An optimization result is conditional on its material basis, load cases, constraints, and model validity. Candidate ranking alone does not qualify a design.",
    source: "Anisotropy AI · Design exploration",
    url: "/services",
    methods: [
      m(
        "Mass objective",
        "minimize mass = Area × Σ ρₖ tₖ",
        "For a constant-area laminate, compare discrete ply counts, orientations, and materials. A variable CAD geometry requires volume integration instead of this constant-area expression.",
      ),
      m(
        "Layup constraints",
        "θₖ ∈ permitted angles;    min MS ≥ 0\nSymmetry: θₖ = θₙ₊₁₋ₖ\nBalance: matched +θ / −θ plies",
        "Symmetry and balance also require matching material and thickness. Include manufacturing limits, stiffness, displacement, and other project-specific constraints. Balanced laminates do not necessarily have zero bending–twisting coupling.",
      ),
      m(
        "Candidate verification",
        "Candidate → CLT → FEA → verification → test",
        "Screen stacks, then verify the shortlisted designs using the same material basis and engineering checks. Document the objective, constraints, rejected cases, and reproducible inputs.",
      ),
    ],
  },
];

// Only referenced analytical foundations are presented as current equation cards.
export const physicsTopics: PhysicsTopic[] = [
  ...existingPhysicsTopics.filter(t => ["clt", "failure"].includes(t.id)).map(topic => ({
    ...topic, source: bookReference.title, url: bookReference.url,
    assumptions: topic.id === "failure"
      ? "Use positive tensile/compressive strength magnitudes and tension-positive local stresses. Match the criterion to the material architecture and strength basis. Failure indices estimate initiation; they do not predict damage evolution or final component failure."
      : topic.assumptions,
    methods: topic.methods.filter(m => !m.name.startsWith("Hashin")).map<Method>(method => ({
      ...method, units: coreReferences[method.name].units,
      reference: { ...bookReference, location: coreReferences[method.name].location },
    })).concat(topic.id === "failure" ? [maximumStrain] : []),
  })),
  ...foundationTopics,
];

export const deferredPhysicsTopics = [
  { title: "CAD & finite elements", detail: "Geometry, elements, meshing, boundary conditions and solver-specific validation need a separate research and implementation phase." },
  { title: "Open-hole strength & progressive damage", detail: "Requires local-field models, applicable failure formulations and calibrated damage or characteristic-length data." },
  { title: "Layup optimization", detail: "Requires a verified analysis model, explicit constraints and candidate checks before ranking designs." },
  { title: "Mode-specific failure models", detail: "Hashin variants, required shear strengths and applicability to UD or woven materials need their own formulation review." },
];
