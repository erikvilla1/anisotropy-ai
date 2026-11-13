import { foundationTopics, maximumStrain, bookReference, coreReferences, laminateExtensions, failureExtensions } from "./physics-foundations";
// A card says what an equation is, its units and where it is printed; which engine function computes it is kept off the
// page, in lib/physics-code-map.ts (ADR-0019 amendment 1).
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
      "Thin, perfectly bonded, linearly elastic orthotropic plies; small deformation and plane stress. Engineering shear strain γ is used. Angles rotate global x–y into local fibre axes 1–2; z is measured from the laminate mid-plane.",
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
        "Transforms global stress to the local fibre/transverse system. The stress and engineering-strain transformations differ in their shear terms.",
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
        "Recover fibre, transverse, and shear stress for failure assessment. Stress can jump between dissimilar plies even when the interface strain is continuous.",
      ),
      m(
        "Laminate engineering constants",
        "a = extensional block of [[A,B],[B,D]]⁻¹  (= A⁻¹ when B = 0)\nEx = 1/(h a₁₁)    Ey = 1/(h a₂₂)    Gxy = 1/(h a₆₆)\nνxy = −a₂₁/a₁₁    νyx = −a₁₂/a₂₂\nηxs = a₆₁/a₁₁    ηys = a₆₂/a₂₂",
        "Effective in-plane constants of a laminate free to bend as it stretches. For a symmetric laminate a = A⁻¹; for a general laminate take the extensional block of the full ABD inverse (§7.12.3). The η terms are the shear coupling coefficients. Restrained bending gives different apparent constants.",
      ),
    ],
  },
  {
    id: "failure",
    title: "Ply failure criteria",
    subtitle: "Evaluate local stresses against a defined strength basis",
    assumptions:
      "Use positive strength magnitudes Xₜ, X꜀, Yₜ, Y꜀ and S with tension-positive local stresses. Appendix compressive values are signed source values and require explicit sign normalization before calculation. Failure indices indicate initiation, not residual strength or fracture location certainty.",
    source: bookReference.title,
    url: bookReference.url,
    methods: [
      m(
        "Maximum stress",
        "r₁ = σ₁/Xₜ (σ₁ ≥ 0); −σ₁/X꜀ (σ₁ < 0)\nr₂ = σ₂/Yₜ (σ₂ ≥ 0); −σ₂/Y꜀ (σ₂ < 0)\nFI = max(r₁, r₂, |τ₁₂|/S)",
        "Checks fibre, transverse, and shear limits separately. FI ≥ 1 indicates initiation; this criterion does not model interaction between stress components.",
      ),
      m(
        "Tsai-Hill",
        "FI = (σ₁/X)² − σ₁σ₂/X²\n     + (σ₂/Y)² + (τ₁₂/S)²",
        "This documented plane-stress convention selects X = Xₜ or X꜀ by the sign of σ₁ and Y similarly by σ₂. Mixed-sign conventions differ between implementations; record the convention before comparisons. FI ≥ 1 indicates initiation; for proportional loading R = 1/√FI.",
      ),
      m(
        "Tsai-Wu coefficients",
        "F₁ = 1/Xₜ − 1/X꜀    F₂ = 1/Yₜ − 1/Y꜀\nF₁₁ = 1/(XₜX꜀)    F₂₂ = 1/(YₜY꜀)\nF₆₆ = 1/S²    F₁₂ = f₁₂ √(F₁₁F₂₂)",
        "The biaxial interaction coefficient f₁₂ needs experimental evidence or an explicitly recorded assumption. It cannot be inferred from uniaxial strengths alone. Require |f₁₂| < 1 for a positive-definite normal-stress quadratic.",
      ),
      m(
        "Tsai-Wu failure index",
        "FI = F₁σ₁ + F₂σ₂ + F₁₁σ₁²\n     + F₂₂σ₂² + 2F₁₂σ₁σ₂ + F₆₆τ₁₂²",
        "FI ≥ 1 marks the chosen failure envelope. The scalar index does not identify fibre versus matrix failure; report it alongside mode-sensitive criteria and the input strength basis.",
      ),
      m(
        "Strength ratio & safety margin",
        "FI(Rσ) = 1\nTsai-Wu: aR² + bR − 1 = 0\nMS = R/FS − 1",
        "Find the smallest positive load multiplier R reaching initiation; a and b are the quadratic and linear stress terms. For homogeneous quadratic criteria, R = 1/√FI. FS is the specified safety factor. Handle zero stress and the linear limiting case explicitly.",
      ),
    ],
  },
];

// Only referenced analytical foundations are presented as equation cards.
export const physicsTopics: PhysicsTopic[] = [
  ...existingPhysicsTopics.filter(t => ["clt", "failure"].includes(t.id)).map(topic => ({
    ...topic, source: bookReference.title, url: bookReference.url,
    assumptions: topic.id === "failure"
      ? "Use positive tensile/compressive strength magnitudes and tension-positive local stresses. Strengths: Xₜ = F₁ₜ, X꜀ = F₁c, Yₜ = F₂ₜ, Y꜀ = F₂c and S = F₆, the shear strength the material tables list as F₁₂; the Tsai-Wu F terms are coefficients, not strengths. Match the criterion to the material architecture and strength basis. Failure indices estimate initiation; they do not predict damage evolution or final component failure."
      : topic.assumptions,
    methods: topic.methods.map<Method>(method => ({
      ...method, units: coreReferences[method.name].units,
      reference: { title: bookReference.title, url: bookReference.url, location: coreReferences[method.name].location },
    })).concat(topic.id === "failure" ? [maximumStrain, ...failureExtensions] : laminateExtensions),
  })),
  ...foundationTopics,
];

/** How many equation cards the library shows, for its headline. */
export const physicsCardCount = physicsTopics.reduce((n, t) => n + t.methods.length, 0);
