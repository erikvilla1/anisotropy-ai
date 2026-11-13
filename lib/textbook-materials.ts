import type { CitedMaterial, CitedProperty } from "./curated-materials";
import { textbookSource } from "./textbook-source";
import { propertySymbol } from "./property-symbols";

const conditions = "Ambient 24 °C (75 °F), dry. Typical cured-laminate properties.";
type Values = {
  id: string; name: string; family: string; architecture: string; printedPage: number; table: string;
  // SI columns: Vf, density in g/cm³, E1, E2, G12 in GPa, ν12, strengths in MPa, strains as fractions.
  values: [number, number, number, number, number, number, number, number, number, number, number, number, number];
  alpha1?: number; alpha2?: number; beta1?: number; beta2?: number; nu21: number;
};
const rows: Values[] = [
  { id: "as4-3501", name: "AS4 / 3501-6", family: "Carbon / epoxy", architecture: "Unidirectional", table: "A.4", printedPage: 377,
    values: [.63, 1.60, 147, 10.3, 7, .27, 2280, 57, 76, .015, .006, 1725, 228], nu21: .02, alpha1: -.9, alpha2: 27, beta1: .01, beta2: .20 },
  { id: "im6g-3501-6", name: "IM6G / 3501-6", family: "Carbon / epoxy", architecture: "Unidirectional", table: "A.4", printedPage: 377,
    values: [.66, 1.62, 169, 9, 6.5, .31, 2240, 46, 73, .013, .005, 1680, 215], nu21: .02, alpha1: -.9, alpha2: 25, beta1: 0 },
  { id: "im7-977-3", name: "IM7 / 977-3", family: "Carbon / epoxy", architecture: "Unidirectional", table: "A.4", printedPage: 378,
    values: [.65, 1.61, 190, 9.9, 7.8, .35, 3250, 62, 75, .016, .006, 1590, 200], nu21: .02, alpha1: -.9, alpha2: 22, beta1: 0 },
  { id: "as4-apc2", name: "AS4 / APC2", family: "Carbon / PEEK", architecture: "Unidirectional · thermoplastic", table: "A.4", printedPage: 378,
    values: [.58, 1.57, 138, 8.7, 5, .28, 2060, 78, 157, .016, .009, 1100, 196], nu21: .02, alpha1: -.2, alpha2: 24, beta1: 0, beta2: .4 },
  { id: "m10e-3783", name: "M10E / 3783", family: "Glass / epoxy", architecture: "Woven", table: "A.5", printedPage: 379,
    values: [.50, 1.90, 24.5, 23.8, 4.7, .11, 433, 386, 84, .022, .021, 377, 335], nu21: .10 },
  { id: "agp370-3501-6s", name: "AGP370-5H / 3501-6S", family: "Carbon / epoxy", architecture: "Woven · five-harness satin", table: "A.5", printedPage: 379,
    values: [.62, 1.60, 77, 75, 6.5, .06, 963, 856, 71, .013, .012, 900, 900], nu21: .06, alpha1: 3.4, alpha2: 3.7, beta1: .05, beta2: .05 },
  { id: "7781-5245c", name: "7781 / 5245C", family: "Glass / epoxy", architecture: "Woven", table: "A.5", printedPage: 379,
    values: [.45, 2.20, 29.7, 29.7, 5.3, .17, 367, 367, 97.1, .025, .025, 549, 549], nu21: .17, alpha1: 10, alpha2: 10, beta1: .06, beta2: .06 },
];

// β is strain per unit moisture concentration c, a pure number; its row says so beside the direction.
const moisture = (direction: string) => `${direction} · per unit moisture concentration c (water volume / composite volume)`;

// Only additional A.6 cells; overlapping entries retain their A.4/A.5 citations.
// F4 and F5 denote the 2–3 and 1–3 shear planes, respectively.
type Extra = [string, string, number, string, string];
const outOfPlane: Record<string, Extra[]> = {
  "as4-3501": [
    ["E3", "Transverse out-of-plane modulus", 10.3, "GPa", "3 direction"],
    ["G23", "Out-of-plane shear modulus · 2–3", 3.7, "GPa", "2–3 plane"],
    ["G13", "Out-of-plane shear modulus · 1–3", 7, "GPa", "1–3 plane"],
    ["nu23", "Poisson ratio · 2–3", .54, "—", "2–3 directions"],
    ["nu13", "Poisson ratio · 1–3", .27, "—", "1–3 directions"],
    ["F3t", "Out-of-plane tensile strength", 57, "MPa", "3 direction"],
    ["F3c", "Out-of-plane compressive strength", 228, "MPa", "3 direction"],
    ["alpha3", "Out-of-plane thermal expansion", 27, "10⁻⁶/K", "3 direction"],
    ["beta3", "Out-of-plane moisture expansion", .20, "—", moisture("3 direction")],
  ],
  "m10e-3783": [
    ["E3", "Transverse out-of-plane modulus", 11.6, "GPa", "3 direction"],
    ["G23", "Out-of-plane shear modulus · 2–3", 3.6, "GPa", "2–3 plane"],
    ["G13", "Out-of-plane shear modulus · 1–3", 2.6, "GPa", "1–3 plane"],
    ["nu23", "Poisson ratio · 2–3", .20, "—", "2–3 directions"],
    ["nu13", "Poisson ratio · 1–3", .15, "—", "1–3 directions"],
    ["F3t", "Out-of-plane tensile strength", 27, "MPa", "3 direction"],
    ["F3c", "Out-of-plane compressive strength", 237, "MPa", "3 direction"],
    ["F23", "Out-of-plane shear strength · 2–3", 44, "MPa", "2–3 plane"],
    ["F13", "Out-of-plane shear strength · 1–3", 41, "MPa", "1–3 plane"],
  ],
  "agp370-3501-6s": [
    ["E3", "Transverse out-of-plane modulus", 13.8, "GPa", "3 direction"],
    ["G23", "Out-of-plane shear modulus · 2–3", 4.1, "GPa", "2–3 plane"],
    ["G13", "Out-of-plane shear modulus · 1–3", 5.1, "GPa", "1–3 plane"],
    ["nu23", "Poisson ratio · 2–3", .37, "—", "2–3 directions"],
    ["nu13", "Poisson ratio · 1–3", .50, "—", "1–3 directions"],
    ["F3t", "Out-of-plane tensile strength", 60, "MPa", "3 direction"],
    ["F3c", "Out-of-plane compressive strength", 813, "MPa", "3 direction"],
    ["F23", "Out-of-plane shear strength · 2–3", 65, "MPa", "2–3 plane"],
    ["F13", "Out-of-plane shear strength · 1–3", 75, "MPa", "1–3 plane"],
    ["alpha3", "Out-of-plane thermal expansion", 52, "10⁻⁶/K", "3 direction"],
    ["beta3", "Out-of-plane moisture expansion", .27, "—", moisture("3 direction")],
  ],
};

export const textbookMaterials: CitedMaterial[] = rows.map(row => {
  const [vf, density, e1, e2, g12, nu12, f1t, f2t, f12, strain1, strain2, f1c, f2c] = row.values;
  const property = (key: string, label: string, value: number, unit: string, direction: string, sourceValue = value, sourceUnit = unit === "10⁻⁶/K" ? "10⁻⁶/°C" : unit): CitedProperty => ({
    key, label, value, unit, direction, symbol: propertySymbol(key), basis: "Typical textbook value", conditions,
    method: `Compiled reference data, Table ${row.table}; no row-specific test-method edition assigned`,
    sourcePage: row.printedPage + 20, printedPage: row.printedPage, sourceValue, sourceUnit,
    evidence: `Table ${row.table}, ${row.name} column`,
  });
  return {
    id: row.id, name: row.name, family: row.family, architecture: row.architecture,
    datasetId: `daniel-ishai-2006-${row.id}-v2`, dataset: "Daniel & Ishai 2006 · typical values",
    conditions, source: { ...textbookSource, page: row.printedPage + 20, printedPage: row.printedPage },
    reviewedOn: "2026-10-02", recordRevision: "2026-10-02.1",
    elasticInputs: { E1: "E1", E2: "E2", G12: "G12", nu12: "nu12" },
    application: "Reference values for preliminary elastic and strength analysis at the stated conditions. These typical values are not statistical design allowables or a current manufacturing specification.",
    recordDetails: [
      `Table ${row.table}, printed p. ${row.printedPage}. Ambient, dry conditions are stated on printed p. 42; Appendix A describes the compilation on p. 373.`,
      "Values use the printed SI column. Fibre volume and tensile strain are shown in percent; the book prints fractions. Exports keep the printed numbers and units.",
      "The four in-plane elastic inputs are E₁, E₂, G₁₂ and ν₁₂. The ν₂₁ shown is the book's own rounded entry. For a model, compute ν₂₁ = ν₁₂ E₂/E₁; it is not a fifth independent input.",
      "Moisture expansion β is strain per unit water-volume concentration c (water volume / composite volume), not per percent moisture or per degree. See §10.3.5, Eq. 10.19, printed p. 314. A printed zero is kept; a dash is omitted.",
      "Blank entries are omitted; nothing missing (ply thickness, cure process, test method, expansion coefficients) is inferred. Compressive strengths are positive magnitudes; map the sign to your analysis convention.",
      ...(outOfPlane[row.id] ? ["Additional properties come from Table A.6, printed p. 380. These are tabulated orthotropic constants; no transverse-isotropy relationship is imposed."] : []),
      ...(row.id === "as4-3501" ? ["This textbook dataset is separate from the NASA thermoelastic model. AS4 G₂₃, E₂ and ν₂₃ do not satisfy exact transverse isotropy; use the tabulated orthotropic description and check the assumptions of your model."] : []),
      ...(row.id === "m10e-3783" ? ["Table A.6 gives the through-thickness properties. No eight-harness architecture is inferred."] : []),
      ...(row.id === "agp370-3501-6s" ? ["The book lists the resin as 3501-6S. This record is separate from the AGP370-5H / 3501-6 through-thickness test dataset."] : []),
    ],
    properties: [
      property("E1", "Longitudinal modulus", e1, "GPa", "1 direction"),
      property("E2", "Transverse in-plane modulus", e2, "GPa", "2 direction"),
      property("G12", "In-plane shear modulus", g12, "GPa", "1–2 plane"),
      property("nu12", "Poisson ratio", nu12, "—", "1–2 directions"),
      { ...property("nu21", "Minor Poisson ratio · tabulated", row.nu21, "—", "2–1 directions"), basis: "Typical textbook value · rounded; use reciprocity in a model" },
      property("F1t", "Longitudinal tensile strength", f1t, "MPa", "1 direction"),
      property("F2t", "Transverse tensile strength", f2t, "MPa", "2 direction"),
      property("F12", "In-plane shear strength", f12, "MPa", "1–2 plane"),
      property("F1c", "Longitudinal compressive strength", f1c, "MPa", "1 direction"),
      property("F2c", "Transverse compressive strength", f2c, "MPa", "2 direction"),
      property("density", "Density", density, "g/cm³", "Bulk"),
      property("Vf", "Fibre volume fraction", Number((vf * 100).toPrecision(12)), "%", "Bulk", vf, "—"),
      property("epsilon1t", "Ultimate longitudinal tensile strain", Number((strain1 * 100).toPrecision(12)), "%", "1 direction", strain1, "—"),
      property("epsilon2t", "Ultimate transverse tensile strain", Number((strain2 * 100).toPrecision(12)), "%", "2 direction", strain2, "—"),
      ...(row.alpha1 === undefined ? [] : [property("alpha1", "Longitudinal thermal expansion", row.alpha1, "10⁻⁶/K", "1 direction")]),
      ...(row.alpha2 === undefined ? [] : [property("alpha2", "Transverse thermal expansion", row.alpha2, "10⁻⁶/K", "2 direction")]),
      ...(row.beta1 === undefined ? [] : [property("beta1", "Longitudinal moisture expansion", row.beta1, "—", moisture("1 direction"))]),
      ...(row.beta2 === undefined ? [] : [property("beta2", "Transverse moisture expansion", row.beta2, "—", moisture("2 direction"))]),
      ...(outOfPlane[row.id] || []).map(([key, label, value, unit, direction]) => ({
        ...property(key, label, value, unit, direction), sourcePage: 400, printedPage: 380,
        method: "Compiled reference data, Table A.6; no row-specific test-method edition assigned",
        evidence: `Table A.6, ${row.name} column`,
      })),
    ],
  };
});
