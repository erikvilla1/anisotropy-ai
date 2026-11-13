import type { Method, PhysicsTopic } from "./physics";
import type { SourceRights } from "./source-rights";
import { textbookSource } from "./textbook-source";

// A card shows the equation, its units and where it is printed. Which engine function computes it is kept off the
// page, in lib/physics-code-map.ts (ADR-0019 amendment 1).
export const bookReference = { title: textbookSource.fullCitation, url: textbookSource.url, rights: textbookSource.rights };
const method = (name: string, equation: string, detail: string, location: string, units: string): Method => ({
  name, equation, detail, units, reference: { title: bookReference.title, url: bookReference.url, location },
});
const stressUnits = "E, G, Q and stress: Pa (or one consistent stress unit). Strain, γ and ν: dimensionless fractions.";
const laminateUnits = "Using Q in Pa and z in m: A in N/m, B in N, D in N·m. N in N/m, M in N, curvature in 1/m.";

// Printed-page citations; formulas are expressed in this product's engineering-shear notation.
export const coreReferences: Record<string, { location: string; units: string }> = {
  "Reciprocity & compliance S": { location: "Chapter 4, §§4.2–4.3; plane-stress relations, pp. 75–77", units: stressUnits + " Compliance S: 1/Pa." },
  "Reduced stiffness Q": { location: "Eq. 4.56, p. 77", units: stressUnits },
  "Stress transformation Tσ": { location: "Eqs. 4.57–4.60, pp. 77–78; global-to-local direction", units: "θ in degrees or radians consistently; transformation entries dimensionless. Stress unit unchanged." },
  "Strain transformation Tε": { location: "Eqs. 4.58–4.62, pp. 77–78; global-to-local form adapted from tensor shear to engineering γ", units: "Strain and γ dimensionless; γ = 2ε₁₂ (tensor component)." },
  "Transformed stiffness Q̄": { location: "Eqs. 4.63–4.67, pp. 79–80; engineering-shear matrix form", units: stressUnits },
  "Ply interfaces & thickness": { location: "Chapter 7, through-thickness coordinates and resultants, pp. 160–164", units: "Each ply thickness, interface z and total h use the same length unit; tₖ > 0." },
  "Extensional stiffness A": { location: "Eqs. 7.23–7.24, p. 164", units: laminateUnits },
  "Extension–bending coupling B": { location: "Eqs. 7.23–7.24, p. 164", units: laminateUnits },
  "Bending stiffness D": { location: "Eqs. 7.23–7.24, p. 164", units: laminateUnits },
  "Laminate response · ABD solve": { location: "Eqs. 7.20–7.24, p. 164; Chapter 8 for equivalent hygrothermal loads", units: laminateUnits },
  "Thermal & moisture resultants": { location: "Chapter 8, §§8.4–8.5, pp. 212–220; integrated eigenstrain form", units: laminateUnits + " α: 1/K; β and concentration must share the same moisture definition." },
  "Global strain recovery": { location: "Chapter 7, §7.2, pp. 160–164; Chapter 8, §8.4 for free strains", units: "ε and γ: fractions; κ: 1/m; z: m; αΔT and βΔc: fractions." },
  "Local strains & local stresses": { location: "Chapters 4 and 7, §§4.4 and 7.3 (pp. 160–161); Chapter 8, §8.4 for mechanical strain", units: stressUnits },
  "Laminate engineering constants": { location: "Eq. 7.84, pp. 183–184; §7.12.3 general laminates use the extensional block of the full ABD inverse", units: "a in m/N, h in m; effective E and G in Pa; ν and η dimensionless." },
  "Maximum stress": { location: "Chapter 6, §6.3, pp. 124–125; plane-stress restriction", units: "Stresses and positive strength magnitudes use one stress unit; FI dimensionless." },
  "Tsai-Hill": { location: "Eqs. 6.16–6.17, p. 129; sign-selected strengths", units: "Stresses and strengths use one stress unit; FI dimensionless." },
  "Tsai-Wu coefficients": { location: "Eqs. 6.29–6.40, pp. 131–133; normalized interaction notation", units: "F₁, F₂: 1/Pa; F₁₁, F₂₂, F₁₂, F₆₆: 1/Pa²; f₁₂ dimensionless." },
  "Tsai-Wu failure index": { location: "Eqs. 6.29–6.40, pp. 131–133; plane stress", units: "Use stress units consistent with the coefficients; FI dimensionless." },
  "Strength ratio & safety margin": { location: "Eqs. 6.56–6.60, p. 139; margin convention MS = R/FS − 1 stated here", units: "R, FI, specified factor FS and margin MS are dimensionless. FS > 0." },
};

// RP-1351 and Whitney have no recorded rights class; a source whose class is unknown counts as a licensed reference until
// one is recorded (project rules). No evidence yet.
// `listed` is how the references list names a work: its title as the link, the author or series beside it.
type PhysicsReference = { title: string; url: string; rights: SourceRights; listed?: { title: string; detail: string } };
const nasaReference: PhysicsReference = { title: "NASA RP-1351 · Basic Mechanics of Laminated Composite Plates", url: "https://ntrs.nasa.gov/citations/19950009349", rights: "licensed-reference",
  listed: { title: "Basic Mechanics of Laminated Composite Plates", detail: "NASA RP-1351" } };
const nasaMethod = (name: string, equation: string, detail: string, location: string, units: string): Method => ({
  name, equation, detail, units, reference: { title: nasaReference.title, url: nasaReference.url, location },
});
const whitneyReference: PhysicsReference = { title: "Whitney · Structural Analysis of Laminated Anisotropic Plates · Technomic, 1987 (ISBN 0-87762-518-2)", url: "https://www.worldcat.org/isbn/0877625182", rights: "licensed-reference",
  listed: { title: "Structural Analysis of Laminated Anisotropic Plates", detail: "Whitney · Technomic, 1987 (ISBN 0-87762-518-2)" } };
const whitneyMethod = (name: string, equation: string, detail: string, location: string, units: string): Method => ({
  name, equation, detail, units, reference: { title: whitneyReference.title, url: whitneyReference.url, location },
});

const towReference = { title: "ASTM D4018-23 · Properties of Continuous Filament Carbon and Graphite Fiber Tows",
  url: "https://store.astm.org/d4018-23.html", rights: "licensed-reference" as SourceRights };

/** Every reference a physics card cites, with its rights class, for the references list. */
export const physicsReferences: PhysicsReference[] = [bookReference, nasaReference, whitneyReference, towReference];

// Operations beyond the foundation cards (ADR-0019); lib/physics-code-map.ts names the function behind each.
export const laminateExtensions: Method[] = [
  method("Laminate compliance · ABD inverse",
    "[ε⁰; κ] = [[a, b], [bᵀ, d]] [N; M]\n[[a, b], [bᵀ, d]] = [[A, B], [B, D]]⁻¹\nSymmetric: b = 0, a = A⁻¹, d = D⁻¹",
    "Deformation directly from loads. The lower-left block is the transpose of b. For an unsymmetric laminate a is not A⁻¹: extension and bending stay coupled. Solve the 6×6 system directly; form this inverse only when the compliance itself is the result.",
    "Eqs. 7.27–7.28, p. 166", "a: m/N; b: 1/N; d: 1/(N·m), with A in N/m, B in N and D in N·m."),
  nasaMethod("Known forces & prescribed curvature",
    "A ε⁰ = N − B κ\nM = B ε⁰ + D κ",
    "When all three force resultants and all three curvatures are known, the moments are the unknowns: solve the first system for the mid-plane strain, then recover M. Zero curvature enforces flatness in this model. The result is the moment applied to the laminate, not a fixture reaction. The forward problem is solved again as a check; a result that does not recover the inputs is rejected.",
    "Section III.D, Eqs. 48–51, constitutive relation, rearranged for known curvatures", laminateUnits),
  nasaMethod("Mixed load & deformation conditions",
    "F + Fᵀ = K d,  d = [ε⁰; κ],  K = [[A, B], [B, D]]\nK_LL d_L = F_L + Fᵀ_L − K_LD d_D\nF_D = K_DL d_L + K_DD d_D − Fᵀ_D",
    "For each of the six load–deformation pairs exactly one quantity is known. Split the rows into known-load (L) and known-deformation (D) sets, solve the first system for the unknown deformations, then recover the unknown resultants. All loads known is the forward solve; forces plus curvatures is the prescribed-curvature case. Fᵀ is the thermal resultant, zero without a temperature change.",
    "Section III.D, Eqs. 48–51, constitutive relation, partitioned into known-load and known-deformation rows", laminateUnits + " A force given as an average stress is σ = N/h."),
  whitneyMethod("Plate buckling · simply supported",
    "Specially orthotropic (D₁₆ = D₂₆ = 0), αₘ = mπ/a, βₙ = nπ/b:\nλₘₙ = [D₁₁αₘ⁴ + 2(D₁₂ + 2D₆₆)αₘ²βₙ² + D₂₂βₙ⁴] / (−Nₓαₘ² − N_yβₙ²)\nλ_cr = min over m, n ≥ 1\nGeneral symmetric laminate: K w = λ G w with a double sine series",
    "Critical load factor on reference resultants (tension positive, so compression is negative) for a midplane-symmetric laminate on four simply supported edges. The closed form is exact when D₁₆ = D₂₆ = 0 and there is no shear; otherwise a Ritz double sine series handles the coupling and shear, converging from above as terms are added, with the orthotropic value shown beside it because it is nonconservative for angle-ply plates. Unsymmetric laminates, other edge conditions and postbuckling are not covered.",
    "Section 5.5, Eq. 5.72 (closed form); Sections 6.5–6.6, Eq. 6.38 (series)", "D in N·m, a and b in m, N in N/m; λ dimensionless; m, n integers."),
  method("Laminate symmetry, balance & areal mass",
    "h = Σ tₖ\nSymmetric (ply k mirrors ply n−1−k in material, angle and thickness): B = 0\nBalanced (every +θ has a −θ partner): A₁₆ = A₂₆ = 0\nQuasi-isotropic: A₁₁ = A₂₂, A₁₆ = A₂₆ = 0, A₆₆ = (A₁₁ − A₁₂)/2\nm_A = Σ ρₖ tₖ",
    "The stack described before any load: its thickness, whether it is symmetric, antisymmetric or balanced, its kind (unidirectional, cross-ply, angle-ply, quasi-isotropic or general, judged on A first), which couplings A, B and D show, and its mass per area from each ply's recorded density. An entry counts as zero when it is within 10⁻⁹ of its matrix's largest entry, B judged against max|A| h/2, so roundoff in a symmetric stack is not coupling. A material without a recorded density leaves the areal mass out with the reason.",
    "Chapter 7, §§7.7–7.10 (symmetric, balanced, orthotropic and quasi-isotropic laminates)", "t and h in m; A in N/m, B in N, D in N·m; ρ in kg/m³ and m_A in kg/m²; angles compare modulo 180°."),
];

export const failureExtensions: Method[] = [
  method("Hashin–Rotem (1973) criteria",
    "Fibre: σ₁ = F₁t (σ₁ > 0);  −σ₁ = F₁c (σ₁ < 0)\nInterfibre: (σ₂/F₂)² + (τ₁₂/F₆)² = 1\nF₂ = F₂t (σ₂ > 0);  F₂c (σ₂ < 0)",
    "Two separate criteria, one for fibre failure and one for interfibre (matrix) failure, as the textbook prints them. They are not the later Hashin fibre and matrix mode equations with shear in the fibre mode. With nonlinear shear the strengths may be proportionality limits rather than ultimate values.",
    "Eqs. 6.49–6.50 and 6.52, p. 136", "Stresses and positive strength magnitudes in one stress unit; each criterion dimensionless."),
  method("First-ply failure load",
    "R_FPF = min over plies and faces of R(σ₁₂)\nN_FPF = R_FPF N,  M_FPF = R_FPF M",
    "Evaluate the strength ratio on both faces of every ply from the recovered local stresses and take the smallest; the loads at failure follow. First-ply failure is the onset of cracking in one ply, not the ultimate laminate strength.",
    "§9.4, pp. 251–253; minimum over plies, Eq. 9.9", "R dimensionless; N in N/m and M in N, the same units as the applied loads."),
  method("Strength ratio with fixed & variable loads",
    "σ(R) = σ_s + R σ_v\nTsai-Wu: aR² + bR + c = 0\na = q(σ_v, σ_v)\nb = f₁σ_v1 + f₂σ_v2 + 2 q(σ_s, σ_v)\nc = f₁σ_s1 + f₂σ_s2 + q(σ_s, σ_s) − 1\nR = −2c / (b + √(b² − 4ac))",
    "Residual stress from a temperature change, and any loads held fixed, stays constant while the variable loads scale by R. q(x, y) is the bilinear Tsai-Wu form f₁₁x₁y₁ + f₂₂x₂y₂ + f₆₆x₆y₆ + f₁₂(x₁y₂ + x₂y₁). With c < 0 this is the single positive root; c ≥ 0 means the fixed stresses alone reach the envelope, R = 0. Maximum stress: R = (F_t − σ_s)/σ_v for σ_v > 0 and (−F_c − σ_s)/σ_v for σ_v < 0.",
    "§9.8, Eqs. 9.26–9.28, p. 256; hygrothermal stresses held fixed", "Stresses and strengths in one unit; f coefficients in reciprocal stress units; R dimensionless."),
];

export const thermalExtensions: Method[] = [
  method("Thermal resultants · uniform ΔT",
    "Nᵀ = ΔT Σ Q̄ₖ αₖ (zₖ − zₖ₋₁)\nMᵀ = ½ ΔT Σ Q̄ₖ αₖ (zₖ² − zₖ₋₁²)\n[[A, B], [B, D]] [ε⁰; κ] = [N + Nᵀ; M + Mᵀ]",
    "Closed form of the thermal resultants for a uniform temperature change with constant coefficients; αₖ is the rotated expansion vector with engineering shear. They are the resultants that would hold every ply at its free thermal strain, not applied loads. With no mechanical load a symmetric laminate has Mᵀ = 0 and stays flat; an unsymmetric one warps.",
    "Eqs. 8.18 and 8.20, pp. 213–214; Eq. 8.25, p. 215; moisture terms omitted", laminateUnits + " α: 1/K; ΔT: K."),
  method("Residual ply stress after ΔT",
    "σₖ(z) = Q̄ₖ (ε⁰ + z κ − αₖ ΔT)",
    "A ply is stressed only by the strain it is forced to take beyond its free thermal strain. Reported strains are total strains ε⁰ + zκ, as a gauge reads them. A free laminate can carry residual ply stresses with zero net force and moment.",
    "Eq. 8.16, p. 213", stressUnits + " α: 1/K; ΔT: K; z: m; κ: 1/m."),
  method("Laminate expansion coefficients",
    "ᾱ = ε⁰ at ΔT = 1 with N = M = 0",
    "Solve the thermomechanical system with a unit temperature change and no load; the mid-plane strains are the laminate's in-plane expansion coefficients. The book gives the closed form for balanced symmetric laminates; here they come from the general solve, so unsymmetric laminates also report their curvature per kelvin.",
    "Eq. 8.33, p. 217, balanced symmetric form", "ᾱ: 1/K; the corresponding curvature: 1/(m·K)."),
  method("First-ply failure under ΔT alone",
    "N = M = 0: σₖ ∝ ΔT\nR = min over plies and faces of the ratio of σₖ(ΔT)\nΔT_FPF = R ΔT",
    "With no load the laminate is free and every ply carries only the residual stress of the temperature change, which scales with ΔT; so the strength ratio of that stress is the factor on the change itself, and the first ply fails at R ΔT. With loads, the change is held and the loads scale instead. A laminate whose plies all expand alike is unstressed and is refused, not given a factor.",
    "Eq. 8.16, p. 213, the residual stress; the ratio as for a single loading, Eqs. 6.57–6.59", "ΔT and ΔT_FPF: K (or °C, °F as stated); R: dimensionless."),
];

export const maximumStrain = method("Maximum strain",
  "r₁ = ε₁/ε₁tᵘ (ε₁ ≥ 0); −ε₁/ε₁cᵘ (ε₁ < 0)\nr₂ = ε₂/ε₂tᵘ (ε₂ ≥ 0); −ε₂/ε₂cᵘ (ε₂ < 0)\nFI = max(r₁, r₂, |γ₁₂|/γ₁₂ᵘ)",
  "Use local mechanical strains and positive magnitudes for the five ultimate strain limits. FI ≥ 1 reaches a component limit. Strain limits need an applicable source; do not fill missing compression or shear limits by dividing strength by modulus unless linear behavior to failure is an explicit justified assumption. Explicit limits are used, or limits derived from strengths only when a case states that choice.",
  "Eq. 6.6, p. 126; plane-stress version using positive compressive limits", "All strains are fractions, including engineering shear γ. Convert percentages by dividing by 100; FI dimensionless.");

export const foundationTopics: PhysicsTopic[] = [
  { id: "micromechanics", title: "Constituents & material estimates", subtitle: "Relate fibre and matrix inputs to an idealized lamina",
    assumptions: "Predictions for idealized constituents, not measured material properties. f = fibre, m = matrix, v = void. Volume and mass fractions are different quantities. Continuous, aligned fibres and perfect bonding apply to the elastic estimates below; the two-phase models assume no voids.",
    source: bookReference.title, url: bookReference.url, methods: [
      method("Volume fractions & composite density", "Vf + Vm + Vv = 1\nρc = ρf Vf + ρm Vm  (negligible void mass)",
        "Vf, Vm and Vv are constituent volumes divided by total composite volume. Densities must describe the same state. Density alone does not establish elastic properties or a manufacturing process.",
        "Chapter 2, §2.7, p. 29; density relation derived by mass conservation", "Fractions: 0–1, not percent. All densities in the same unit, e.g. kg/m³."),
      method("Mass fraction to volume fraction", "Vf = (wf/ρf) / [(wf/ρf) + (1−wf)/ρm]\nVm = 1 − Vf",
        "For a void-free fibre/matrix composite, wf is fibre mass divided by total mass. Convert a reported weight percentage to a fraction first. Void-containing material needs a separate measured volume basis.",
        "Chapter 2, §2.7, p. 29; derived from mass and volume definitions", "wf, Vf and Vm: fractions. Constituent densities must share units."),
      method("Longitudinal rule of mixtures", "Vm = 1 − Vf\nE₁ = E₁f Vf + Em Vm\nν₁₂ = ν₁₂f Vf + νm Vm",
        "Equal axial strain in perfectly bonded continuous fibres and matrix. Use the fibre axial modulus and axial-to-transverse Poisson ratio. These estimates do not turn a generic fibre/resin combination into a measured material record.",
        "Eqs. 3.23–3.24, pp. 49–50", "E₁f, Em and E₁: same stress unit. Vf, Vm and ν: dimensionless."),
      method("Transverse inverse-mixture estimate", "1/E₂ = Vf/E₂f + Vm/Em",
        "Idealized equal-stress series model; use transverse fibre modulus E₂f. Local interactions are omitted and the approximation can be poor. It is separate from measured E₂ and from Halpin–Tsai predictions. A constrained-matrix variant uses Em/(1−νm²) in place of Em.",
        "Chapter 3, §3.5; Eq. 3.30, p. 52", "All moduli in the same stress unit; constituent volume fractions sum to one."),
      method("In-plane shear inverse-mixture estimate", "1/G₁₂ = Vf/G₁₂f + Vm/Gm",
        "Series shear model for continuous aligned reinforcement and matrix. Use the appropriate fibre shear modulus; an isotropic E/[2(1+ν)] relation is not valid for an arbitrary anisotropic fibre.",
        "Eqs. 3.48–3.49, p. 57", "All shear moduli in the same stress unit; volume fractions dimensionless."),
      method("Halpin–Tsai estimate", "η = (Pf/Pm − 1) / (Pf/Pm + ξ)\nP = Pm (1 + ξηVf) / (1 − ηVf)",
        "P is the particular elastic property being estimated; Pf and Pm are the corresponding constituent properties. ξ describes the selected reinforcement geometry and fitted response. Record its value and calibration; there is no universal ξ for all composites. ξ = 0 reduces to the series model.",
        "Eqs. 3.17–3.20, p. 48", "P, Pf and Pm share a stress unit. ξ, η and Vf dimensionless; denominator must be nonzero."),
    ] },
  { id: "thermal", title: "Thermal & moisture effects", subtitle: "Free strains, material axes and concentration definitions",
    assumptions: "Use a stated stress-free temperature and moisture reference. α denotes CTE; β denotes expansion per stated moisture concentration. Constant-coefficient equations apply over the range where that approximation is appropriate. Free expansion and restrained stress are different results.",
    source: bookReference.title, url: bookReference.url, methods: [
      method("Thermal expansion · constituent estimate", "E₁ = Ef Vf + Em Vm\nν₁₂ = νf Vf + νm Vm\nα₁ = (Ef αf Vf + Em αm Vm) / E₁\nα₂ = αf Vf(1+νf) + αm Vm(1+νm) − ν₁₂α₁",
        "Approximation for continuous fibres with isotropic fibre and matrix constituents, perfect bonding and no voids. Orthotropic fibres need a different constituent formulation. These coefficients are estimates rather than measurements.",
        "Eqs. 8.1–8.2, pp. 208–209", "E values use the same units; α in 1/K (multiply microstrain/K by 10⁻⁶); fractions and ν dimensionless."),
      method("Expansion coefficient transformation", "m = cos θ; n = sin θ\nαx = m²α₁ + n²α₂\nαy = n²α₁ + m²α₂\nαxy = 2mn(α₁ − α₂)\nεthermal = [αx, αy, αxy] ΔT",
        "Transforms a principal-axis expansion vector with zero local shear expansion into global axes. αxy multiplies engineering shear γxy, hence the factor of two. The same transformation applies to β when its concentration basis is unchanged.",
        "Eq. 8.6, p. 210; inverse of the global-to-local engineering-strain transformation", "α: 1/K; ΔT: K or °C temperature difference; ε and γ: dimensionless."),
      method("Moisture concentration basis", "M = (mwet − mdry) / mdry\nc = (ρdry composite / ρwater) M\nεmoisture = β Δc",
        "The book uses water volume per composite volume for c; M is relative mass gain. Density and volume references must match the coefficient definition. A coefficient based on mass fraction cannot be used with volume concentration without conversion. This defines expansion inputs; it is not a diffusion model.",
        "Eq. 10.19, p. 314", "M and c: fractions, not percentages; density ratio dimensionless. β is strain per unit c."),
      ...thermalExtensions,
    ] },
  { id: "tow", title: "Fibre tow tension", subtitle: "A resin-impregnated tow reduced to strength and chord modulus",
    assumptions: "A tow is a strand, not a laminate: the fibre carries the force over its own area, its mass per unit length over its density, and the resin only holds the filaments together. The chord is linear between its two strains. No finite element model; the standard's text is not reproduced, so read each clause in your own copy.",
    source: towReference.title, url: towReference.url, methods: [
      { name: "Fibre tow strength & chord modulus", equation: "A = MUL / ρf\nσ = P ρf / MUL\nE = (Pu − Pl) ρf / ((εu − εl) MUL)\nRC = 100 (1 − MUL / MULi)",
        detail: "MUL is a weighed length's mass over its length (W1/L); ρf a sized sample's density less its sizing correction kc. The chord strains follow from the product's typical strain at failure (Table 2) and are absolute here: the standard's factor B = 10⁻³ gives GPa only with absolute strains, not the microstrain it lists. Mean, s(n−1) and CV over the valid specimens (Eqs 6–8).",
        units: "SI units: P in N, MUL in kg/m, ρf in kg/m³, σ and E in Pa, strains absolute. In the standard's units, N with g/cm³ and g/m gives MPa directly; RC in % by weight.",
        reference: { title: towReference.title, url: towReference.url, location: "Eqs 1–8, §12; Tables 1–2" } },
    ] },
];

