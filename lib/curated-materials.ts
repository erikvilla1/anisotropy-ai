import publishedReferences from "./published-material-references.json";
import type { MaterialFeed } from "./material-evidence";
import { dualUnits, propertyDisplayValue } from "./property-units";
import { qualifiedCarbon, qualifiedCarbonIM7, nasaCarbonIM7, qualifiedT650, qualifiedBT250, qualifiedTC380, qualifiedEP2190, qualifiedAS4PW, qualifiedT650PW, qualifiedTC250, handbookT650976, handbookEA9396, qualifiedGlass, glassSupportingReferences } from "./qualification-materials";
import { modernGlassAdditions, supplierAdditions } from "./material-property-additions";
import { textbookMaterials } from "./textbook-materials";
import type { SourceRights } from "./source-rights";

export type CitedProperty = {
  key: string; label: string; value: number; valueEnd?: number; valueQualifier?: ">"; unit: string; symbol?: string;
  basis: string; direction: string; method: string; conditions: string;
  sourcePage: number; evidence: string; printedPage?: number; sourceValue?: number; sourceUnit?: string;
};
export type CitedMaterial = {
  id: string; name: string; family: string; architecture: string;
  datasetId: string; dataset: string; application: string; conditions: string;
  source: { id: string; title: string; publisher: string; authors?: string; url: string;
    date: string | null; revision: string; accessed: string; sha256: string | null;
    verification: string; page: number; kind?: "book"; printedPage?: number;
    // What the website may show for this source and the evidence for that class (ADR-0018).
    rights: SourceRights; rightsEvidence: string };
  properties: CitedProperty[];
  supportingReferences?: (CitedMaterial["source"] & { role: string })[];
  recordDetails?: string[];
  reviewedOn?: string;
  recordRevision?: string;
  elasticInputs?: { E1: string; E2: string; G12: string; nu12: string };
};

const accessed = "2026-10-01";
const prop = (key: string, label: string, value: number, unit: string, basis: string, direction: string,
  method: string, conditions: string, sourcePage: number, evidence: string, symbol?: string): CitedProperty =>
  ({ key, label, value, unit, basis, direction, method, conditions, sourcePage, evidence, symbol });

const modelConditions = "Constants used in the published laminate model; assumed temperature-independent in that study.";
export const as4Model: CitedMaterial = {
  id: "as4-3501", name: "AS4 / 3501-6", family: "Carbon / epoxy", architecture: "Unidirectional",
  datasetId: "maddocks-1995-table-6-2", dataset: "Published thermoelastic model",
  application: "Elastic laminate analysis using the assumptions of this study. These are model inputs, not strength allowables.",
  conditions: modelConditions,
  source: { id: "nasa-maddocks-as4", title: "Microcracking in Composite Laminates Under Thermal and Mechanical Loading",
    authors: "Jason R. Maddocks", publisher: "MIT · NASA Technical Reports Server", date: "1995-05", revision: "NASA-CR-199802 · Table 6.2",
    url: "https://ntrs.nasa.gov/api/citations/19960008935/downloads/19960008935.pdf", accessed,
    sha256: "170f13db27c1bb30902e11ac2454edca2748aacd3236705e14ea77c87ea53653",
    verification: "Table 6.2 visually checked against the original PDF; assumptions checked on p. 94.", page: 95,
    rights: "open-publisher", rightsEvidence: "Public download from the NASA Technical Reports Server. Contractor-report copyright not checked, so the report is linked, not copied." },
  properties: [
    ["E1", "Longitudinal modulus", 142, "GPa", "Fiber direction"],
    ["E2", "Transverse in-plane modulus", 9.81, "GPa", "Transverse direction"],
    ["nu12", "Poisson ratio", .30, "—", "Longitudinal–transverse"],
    ["G12", "In-plane shear modulus", 6, "GPa", "1–2 plane"],
    ["alpha1", "Longitudinal thermal expansion", -.36, "10⁻⁶/K", "Fiber direction"],
    ["alpha2", "Transverse thermal expansion", 28.8, "10⁻⁶/K", "Transverse direction"],
    ["tply", "Ply thickness", .134, "mm", "Through thickness"],
  ].map(([key, label, value, unit, direction]) => prop(String(key), String(label), Number(value), String(unit), "Model input", String(direction),
    "Published model constants; Table 6.2", modelConditions, 95, "Table 6.2; printed p. 95", String(key))),
};

const textileConditions = "Through-thickness specimens and loading described in §2.3; results apply to the tested five-harness fabric laminate.";
const agp: CitedMaterial = {
  id: "agp370", name: "AGP370-5H / 3501-6", family: "Carbon / epoxy", architecture: "Woven · five-harness satin",
  datasetId: "daniel-icf11-2005-v2", dataset: "Through-thickness experimental properties",
  application: "Through-thickness response of the tested laminate. This dataset does not supply a complete in-plane material model.",
  conditions: textileConditions, reviewedOn: "2026-10-02", recordRevision: "2026-10-02.1",
  source: { id: "icf11-agp370", title: "Three-dimensional characterization of constitutive behavior and failure of textile composites",
    authors: "I. M. Daniel, J. L. Abot, J.-J. Luo and P. M. Schubel", publisher: "International Conference on Fracture · ICF11", date: "2005", revision: "Figures 3–5",
    url: "https://www.gruppofrattura.it/ocs/index.php/ICF/ICF11/paper/download/10515/9871", accessed,
    sha256: "04f0f86f489afc863e3f4c84bbeb5b121646c04e528b7a0fa85471e9886b9cd1", page: 4,
    verification: "Numeric figure annotations visually checked in the original PDF; no curve digitization. Material identity in §2.1.",
    rights: "licensed-reference", rightsEvidence: "Conference paper downloadable from the ICF proceedings site; no license statement found. Figure values are cited; the paper is not copied." },
  properties: [
    prop("epsilon3t", "Ultimate out-of-plane tensile strain", .5, "%", "Reported experimental result", "Through thickness", "Waisted-block tension; §2.3", textileConditions, 4, "Figure 3 numeric annotation", "ε3t"),
    prop("epsilon3c", "Ultimate out-of-plane compressive strain", 6.6, "%", "Reported experimental result", "Through thickness", "Bonded-block compression; §2.3", textileConditions, 4, "Figure 4 numeric annotation", "ε3c"),
    { ...prop("gamma31", "Ultimate out-of-plane shear strain", 7, "%", "Reported lower bound", "3–1 plane", "Modified Iosipescu V-notch; §2.3", textileConditions, 5, "Figure 5: ultimate shear strain > 7%; not equality", "γ31"), valueQualifier: ">" },
    prop("E3t", "Through-thickness tensile modulus", 12.8, "GPa", "Reported experimental result", "Through thickness", "Waisted-block tension; §2.3", textileConditions, 4, "Figure 3", "E3t"),
    prop("F3t", "Through-thickness tensile strength", 59.8, "MPa", "Reported experimental result", "Through thickness", "Waisted-block tension; §2.3", textileConditions, 4, "Figure 3", "F3t"),
    prop("E3c", "Through-thickness compressive modulus", 13.4, "GPa", "Reported experimental result", "Through thickness", "Bonded-block compression; §2.3", textileConditions, 4, "Figure 4", "E3c"),
    prop("F3c", "Through-thickness compressive strength", 812.8, "MPa", "Reported experimental result", "Through thickness", "Bonded-block compression; §2.3", textileConditions, 4, "Figure 4", "F3c"),
    prop("nu31", "Poisson ratio · 3–1", .085, "—", "Reported experimental result", "3–1", "Bonded-block compression; §2.3", textileConditions, 4, "Figure 4", "ν31"),
    prop("nu32", "Poisson ratio · 3–2", .064, "—", "Reported experimental result", "3–2", "Bonded-block compression; §2.3", textileConditions, 4, "Figure 4", "ν32"),
    prop("G31", "Through-thickness shear modulus", 5.1, "GPa", "Reported experimental result", "3–1 plane", "Modified Iosipescu V-notch; §2.3", textileConditions, 5, "Figure 5", "G31"),
    prop("F31", "Through-thickness shear strength", 74.8, "MPa", "Reported experimental result", "3–1 plane", "Modified Iosipescu V-notch; §2.3", textileConditions, 5, "Figure 5", "F31"),
  ],
};

const ncampConditions = "70°F (21.1°C), dry as fabricated. 7781 glass, 293 g/m², nominal 38% prepreg resin content; E-765 MS1001 Rev 5 Type 1 Grade A / NMS 765/5. PS1000 Rev 5, bagging Option 2, cure equivalent to NPS 81765 cycle O.";
const ncamp: CitedMaterial = {
  id: "7781-e765", name: "7781 / E-765", family: "Glass / epoxy", architecture: "Woven · eight-harness satin",
  datasetId: "ncamp-e765-2025-rtd-measured-v2", dataset: "NCAMP · room-temperature measured means",
  application: "Measured properties from the 2025 test program. For an in-plane elastic set including Poisson’s ratio, select the 2001 qualification dataset. The displayed means are not statistical design allowables.",
  supportingReferences: glassSupportingReferences,
  reviewedOn: "2026-10-02", recordRevision: "2026-10-02.1",
  conditions: ncampConditions,
  source: { id: "ncamp-e765-2025", title: "Park Aerospace Corp. 7781 E765 Glass · Material Property Data Report",
    publisher: "Wichita State University · NIAR / NCAMP", date: "2025-02-25", revision: "CAM-RP-2023-010 · Rev N/C",
    url: "https://www.wichita.edu/industry_and_defense/NIAR/Documents/Park-Aerospace-Corp-7781-E765-Glass-CAM-RP-2023-010-Rev-NC-MPDR-2-25-25.pdf",
    accessed, sha256: "1eefc09bc58939ef84806bcb00b60c2e282a9db628352b38de66c03930d52816", page: 17,
    verification: "Original publisher PDF visually checked: Table 2-1 measured RTD column and individual summary tables on pp. 18–23; immutable monitor snapshot retained.",
    rights: "open-publisher", rightsEvidence: "NCAMP documents are intended for general distribution to the public (NCAMP, NIAR). Linked, not copied." },
  properties: [
    ["E1t", "Warp tensile modulus", 3.700, "Msi", "Warp", "ASTM D3039/D3039M-17", 18],
    ["E2t", "Fill tensile modulus", 3.472, "Msi", "Fill", "ASTM D3039/D3039M-17", 19],
    ["E1c", "Warp compressive modulus", 3.868, "Msi", "Warp", "SACMA SRM 1R-94", 20],
    ["E2c", "Fill compressive modulus", 3.691, "Msi", "Fill", "SACMA SRM 1R-94", 21],
    ["G12", "In-plane shear modulus", .6857, "Msi", "1–2 plane", "ASTM D3518/D3518M-18", 22],
    ["F1t", "Warp tensile strength", 70.19, "ksi", "Warp", "ASTM D3039/D3039M-17", 18],
    ["F2t", "Fill tensile strength", 64.34, "ksi", "Fill", "ASTM D3039/D3039M-17", 19],
    ["F1c", "Warp compressive strength", 77.99, "ksi", "Warp", "SACMA SRM 1R-94", 20],
    ["F2c", "Fill compressive strength", 64.35, "ksi", "Fill", "SACMA SRM 1R-94", 21],
    ["F12-offset", "Shear strength · 0.2% offset", 5.002, "ksi", "1–2 plane", "ASTM D3518/D3518M-18", 22],
    ["F12-5pct", "Shear strength · at 5% strain", 8.962, "ksi", "1–2 plane", "ASTM D3518/D3518M-18", 22],
    ["SBS", "Short-beam strength", 8.850, "ksi", "Interlaminar test", "ASTM D2344/D2344M-16", 23],
  ].map(([key, label, value, unit, direction, method, page]) => prop(String(key), String(label), Number(value), String(unit),
    "Measured mean", String(direction), String(method), ncampConditions, Number(page), "RTD (70°F), measured mean; also Table 2-1, p. 17", String(key))).concat(modernGlassAdditions),
};

const aluminumConditions = "HexWeb CR III 1/8-5052-3.1; tests on 0.625 in thick core.";
const aluminum: CitedMaterial = {
  id: "aluminum-core", name: "HexWeb CR III · 1/8-5052-3.1", family: "Sandwich cores", architecture: "5052 aluminum · hexagonal honeycomb",
  datasetId: "hexcel-criii-table-I-3-1", dataset: "Manufacturer mechanical properties",
  application: "Core analysis for this exact Hexcel grade and thickness. Minimum values are supplier minimum averages for the product type.",
  conditions: aluminumConditions,
  source: { id: "hexcel-criii", title: "HexWeb CR III · Corrosion Resistant Specification Grade Aluminum Honeycomb",
    publisher: "Hexcel", date: null, revision: "ATA361USDC17–DS2100 · Table I", accessed, page: 4,
    url: "https://www.hexcel.com/wp-content/uploads/2025/12/HexWeb_CRIII_DataSheet.pdf",
    sha256: "0467f718f7d9d3a175635718573f94f58baea1d753e83db4be8edcba9f374034",
    verification: "Table I visually checked, exact 1/8 in / 3.1 pcf / 5052 row. Copyright and URL dates are not treated as revision dates.",
    rights: "open-publisher", rightsEvidence: "Manufacturer datasheet published on the manufacturer's website. Linked, not copied." },
  properties: [
    ["compression-modulus", "Compressive modulus", 75, "ksi", "Typical", "Through thickness"],
    ["shear-L-modulus", "Plate shear modulus · L", 45, "ksi", "Typical", "L direction"],
    ["shear-W-modulus", "Plate shear modulus · W", 22, "ksi", "Typical", "W direction"],
    ["bare-compression-typ", "Bare compressive strength", 285, "psi", "Typical", "Through thickness"],
    ["bare-compression-min", "Bare compressive strength", 200, "psi", "Minimum average", "Through thickness"],
    ["stabilized-compression-typ", "Stabilized compressive strength", 300, "psi", "Typical", "Through thickness"],
    ["stabilized-compression-min", "Stabilized compressive strength", 215, "psi", "Minimum average", "Through thickness"],
    ["crush-strength", "Crush strength", 130, "psi", "Typical", "Through thickness"],
    ["shear-L-typ", "Plate shear strength · L", 210, "psi", "Typical", "L direction"],
    ["shear-L-min", "Plate shear strength · L", 155, "psi", "Minimum average", "L direction"],
    ["shear-W-typ", "Plate shear strength · W", 130, "psi", "Typical", "W direction"],
    ["shear-W-min", "Plate shear strength · W", 90, "psi", "Minimum average", "W direction"],
    ["density", "Density", 3.1, "lb/ft³", "Nominal", "Bulk"],
    ["cell-size", "Cell size", .125, "in", "Nominal", "Hexagonal cell"],
  ].map(([key,label,value,unit,basis,direction]) => prop(String(key),String(label),Number(value),String(unit),String(basis),String(direction),
    "Manufacturer Table I; 0.625 in test thickness", aluminumConditions, 4, "Table I; 1/8 in cell, 3.1 pcf, 5052 row")),
};

const supplierMetadata: Record<string, Pick<CitedMaterial, "name" | "family" | "architecture" | "application"> & { title: string; publisher: string }> = {
  "divinycell-h45": { name: "Divinycell H45", family: "Sandwich cores", architecture: "Closed-cell PVC foam", title: "Divinycell H · SI technical data", publisher: "Diab", application: "Core property comparisons and analysis at the reported temperature. Nominal and minimum values remain separate." },
  "divinycell-h250": { name: "Divinycell H250", family: "Sandwich cores", architecture: "Closed-cell PVC foam", title: "Divinycell H · SI technical data", publisher: "Diab", application: "Core property comparisons and analysis at the reported temperature. Nominal and minimum values remain separate." },
  "nomex-aramid": { name: "Nomex · HRH10-1/8-1.8", family: "Sandwich cores", architecture: "Aramid / phenolic · hexagonal honeycomb", title: "HexWeb HRH-10 · Aramid Fiber/Phenolic Resin Honeycomb", publisher: "Hexcel", application: "Core analysis for HRH10-1/8-1.8 at the specified test thickness; keep L and W directions separate." },
  m55j: { name: "M55J / EX-1515", family: "Carbon / cyanate ester", architecture: "Unidirectional · autoclave cured", title: "EX-1515 · Cyanate Ester Prepreg System", publisher: "Toray Advanced Composites", application: "Typical properties of the specified autoclave laminate at 60% fiber volume. Short-beam strength is distinct from in-plane shear strength." },
};

function supplierMaterial(release: MaterialFeed["releases"][number]): CitedMaterial {
  const meta = supplierMetadata[release.materialId];
  const original = publishedReferences.find(r => r.materialId === release.materialId);
  const additions = original?.fingerprint === release.fingerprint ? supplierAdditions[release.materialId] || [] : [];
  return { id: release.materialId, name: meta.name, family: meta.family, architecture: meta.architecture,
    datasetId: additions.length ? `${release.releaseId}-properties-v2` : release.releaseId, dataset: "Manufacturer properties", application: meta.application,
    conditions: [...new Set(release.properties.filter(p => !p.review).map(p => p.conditions))].join("; "),
    source: { id: release.sourceId, title: meta.title, publisher: meta.publisher, url: release.documentUrl,
      date: release.sourceRevisionDate, revision: release.sourceRevision || "Manufacturer product datasheet",
      accessed: release.approvedAt.slice(0,10), sha256: release.fingerprint, page: release.properties[0].sourcePage,
      verification: "Exact grade, units, conditions and table cells checked against manufacturer document. Conflicting rows omitted.",
      rights: "open-publisher", rightsEvidence: "Manufacturer datasheet published on the manufacturer's website. Linked, not copied." },
    properties: release.properties.filter(p => !p.review).map(p => ({ ...p,
      basis: p.basis === "minimum" ? "Supplier minimum" : "Nominal / typical" })).concat(additions),
    reviewedOn: additions.length ? "2026-10-02" : release.approvedAt.slice(0, 10),
    recordRevision: additions.length ? "2026-10-02.1" : release.releaseId,
    recordDetails: release.materialId === "m55j" ? ["The supplier prints tensile modulus as both 354 GPa and 50 Msi, which are inconsistent. That row remains excluded pending supplier clarification; other entries retain their own source basis."] : [],
  };
}
// Cytec X840 Z60 plain weave 6K fabric, as tabulated in a UC San Diego dissertation that used manufacturer-provided
// lamina properties for its impact models. The team's coupon decks use exactly these constants.
const chenConditions = "Not stated in the dissertation; linear-elastic lamina properties and in-plane strengths as provided by the material manufacturer (§3.2.1, printed p. 78). Out-of-plane shear moduli were supplemented from AGP370-5H/3501-6S (Daniel and Ishai), as the dissertation states.";
const chenSource: CitedMaterial["source"] = {
  id: "chen-2015-ucsd-x840", title: "Experimental and Numerical Investigation of Wide Area Blunt Impact Damage to Composite Aircraft Structures",
  authors: "Zhi Ming Chen", publisher: "University of California, San Diego · PhD dissertation in Structural Engineering (chair Hyonny Kim)", date: "2015",
  revision: "Tables 3.1 and 3.2, §3.2.1", url: "https://escholarship.org/search?q=%22Wide%20Area%20Blunt%20Impact%20Damage%20to%20Composite%20Aircraft%20Structures%22",
  accessed: "2026-10-18", sha256: "90c28413213c8c76a96befed174d019b39648b1b5cadb21affdae551e89f0233", page: 99, printedPage: 79,
  verification: "Tables 3.1 and 3.2 read from the PDF text layer and checked against the rendered page (PDF p. 99, printed p. 79) on 2026-10-18; the fabric row matches the team's Abaqus deck constants exactly.",
  rights: "licensed-reference",
  rightsEvidence: "Copyright Zhi Ming Chen, 2015, all rights reserved (title verso). A public copy on eScholarship could not be confirmed on 2026-10-18 (the search link is recorded, not a document link). Individual values cited by table and page; the dissertation is not copied. Founder to confirm the class.",
};
const chenProp = (key: string, label: string, value: number, unit: string, direction: string, table: string, symbol?: string): CitedProperty => ({
  key, label, value, unit, direction, symbol: symbol ?? key, basis: "Manufacturer-provided value, as reported in the dissertation",
  method: `Dissertation Table ${table}; test method not stated`, conditions: chenConditions, sourcePage: 99, printedPage: 79,
  evidence: `Table ${table}, Fabric row, printed p. 79 (PDF p. 99)`,
});
export const chenX840PW: CitedMaterial = {
  id: "x840-z60-pw", name: "X840 / Z60 plain weave 6K", family: "Carbon / epoxy", architecture: "Woven · plain weave, 6K tow",
  datasetId: "chen-2015-x840-z60-pw-v1", dataset: "Dissertation reference · manufacturer-provided lamina properties",
  application: "Elastic ply and laminate analysis of the plain weave fabric with E1, E2, G12 and ν12; in-plane strengths are the reported values, not design allowables. Fracture energies (Table 3.3) are not recorded here.",
  conditions: chenConditions, reviewedOn: "2026-10-18", recordRevision: "2026-10-18.1",
  elasticInputs: { E1: "E1", E2: "E2", G12: "G12", nu12: "nu12" },
  source: chenSource,
  recordDetails: [
    "Table 3.1 (elastic) and Table 3.2 (in-plane strengths), printed p. 79, PDF p. 99. The tape row of the same tables (X840 Z60 12K unidirectional tape) is not recorded in this dataset.",
    "The dissertation states that basic material characterization tests were not conducted and that the majority of the linear-elastic, strength and fracture-energy properties were provided by the material manufacturer (§3.2.1, printed p. 78). Supplier, datasheet and test conditions are therefore not known from this source.",
    "E1 = E2 and ν12 = 0.06 describe a balanced fabric. F12 is the in-plane shear strength the dissertation labels F12.",
    "No ply thickness, fiber volume or thermal expansion is given; a spec that uses this material must state the ply thickness.",
  ],
  properties: [
    chenProp("density", "Density", 1.61, "g/cm³", "Bulk", "3.1", "ρ"),
    chenProp("E1", "Warp in-plane modulus", 80.0, "GPa", "1 direction", "3.1"),
    chenProp("E2", "Fill in-plane modulus", 80.0, "GPa", "2 direction", "3.1"),
    chenProp("nu12", "Poisson ratio", .06, "—", "1–2 directions", "3.1", "ν12"),
    chenProp("G12", "In-plane shear modulus", 6.48, "GPa", "1–2 plane", "3.1"),
    chenProp("G13", "Out-of-plane shear modulus · 1–3", 5.10, "GPa", "1–3 plane", "3.1"),
    chenProp("G23", "Out-of-plane shear modulus · 2–3", 4.07, "GPa", "2–3 plane", "3.1"),
    chenProp("F1t", "Warp tensile strength", 993, "MPa", "1 direction", "3.2"),
    chenProp("F1c", "Warp compressive strength", 772, "MPa", "1 direction", "3.2"),
    chenProp("F2t", "Fill tensile strength", 855, "MPa", "2 direction", "3.2"),
    chenProp("F2c", "Fill compressive strength", 896, "MPa", "2 direction", "3.2"),
    chenProp("F12", "In-plane shear strength", 71.0, "MPa", "1–2 plane", "3.2"),
  ],
};

const baseline = (publishedReferences as MaterialFeed["releases"]).map(supplierMaterial);
const as4Textbook = textbookMaterials.find(m => m.id === "as4-3501")!;
export const curatedMaterials: CitedMaterial[] = [as4Textbook, qualifiedCarbon, qualifiedCarbonIM7, qualifiedT650, qualifiedBT250, qualifiedTC380, qualifiedEP2190, qualifiedAS4PW, qualifiedT650PW, qualifiedTC250, handbookT650976, agp, chenX840PW, qualifiedGlass, handbookEA9396,
  baseline.find(m => m.id === "m55j")!, baseline.find(m => m.id === "nomex-aramid")!, aluminum,
  baseline.find(m => m.id === "divinycell-h45")!, baseline.find(m => m.id === "divinycell-h250")!, ...textbookMaterials.filter(m => m.id !== "as4-3501")];

// A feed may advance a reviewed supplier dataset, never substitute classroom rows or
// silently change material, units, methods, directions or processing conditions.
export function currentMaterial(material: CitedMaterial, feed: MaterialFeed | null): CitedMaterial {
  const original = publishedReferences.find(r => r.materialId === material.id);
  const release = feed?.releases.find(r => r.materialId === material.id);
  if (!original || !release || release.sourceId !== original.sourceId ||
    !(Date.parse(release.approvedAt) > Date.parse(original.approvedAt)) ||
    !/^[a-f0-9]{64}$/.test(release.fingerprint) || !release.releaseId ||
    !Array.isArray(release.properties) || release.properties.length !== original.properties.length) return material;
  try {
    const url = new URL(release.documentUrl);
    if (url.protocol !== "https:" || url.username || url.password || url.host !== new URL(original.documentUrl).host) return material;
    if (new Set(release.properties.map(p => p.key)).size !== original.properties.length) return material;
    for (const p of release.properties) {
      const previous = original.properties.find(old => old.key === p.key);
      if (!previous || !Number.isFinite(p.value) || p.value <= 0 || !Number.isInteger(p.sourcePage) || p.sourcePage < 1 || !p.evidence ||
        (["unit", "label", "basis", "method", "conditions", "direction"] as const).some(k => p[k] !== previous[k])) return material;
      // A previously conflicting row needs a new curated release, not a removed flag.
      if ("review" in previous && previous.review && !p.review) return material;
    }
    return supplierMaterial(release);
  } catch { return material; }
}

export function referenceUrl(source: CitedMaterial["source"], page: number, context?: { datasetId: string; propertyKey?: string }) {
  if (source.kind !== "book") return `${source.url}#page=${page}`;
  const params = new URLSearchParams({ source: source.id, page: String(page) });
  if (context) {
    params.set("dataset", context.datasetId);
    if (context.propertyKey) params.set("property", context.propertyKey);
  }
  return `/sources?${params}`;
}

export function exportCitedMaterial(material: CitedMaterial) {
  return { schemaVersion: 2, materialId: material.id, material: material.name, datasetId: material.datasetId,
    dataset: material.dataset, application: material.application, conditions: material.conditions,
    designAllowables: false, source: material.source,
    recordRevision: material.recordRevision, reviewedOn: material.reviewedOn,
    elasticInputs: material.elasticInputs, recordDetails: material.recordDetails,
    supportingReferences: material.supportingReferences,
    properties: material.properties.map(p => ({ ...p,
      valueType: p.valueQualifier ? "lower-bound" : p.valueEnd === undefined ? "scalar" : "range",
      displayUnits: dualUnits(propertyDisplayValue(p),p.unit),
      referenceUrl: referenceUrl(material.source, p.sourcePage, { datasetId: material.datasetId, propertyKey: p.key }) })) };
}

export function materialDatasets(material: CitedMaterial): CitedMaterial[] {
  if (material.id === "as4-3501") return [as4Textbook, as4Model];
  if (material.id === "im7-8552") return [qualifiedCarbonIM7, nasaCarbonIM7];
  return material.id === "7781-e765" ? [qualifiedGlass, ncamp] : [material];
}

// Original import stays intact in materials.ts. This disposition is an audit, not
// an assertion that a separately published product matches an unidentified sample.
export const archivedMaterialReasons: Record<string, string> = {
  "eglass-3783": "Generic textbook E-glass/epoxy cannot establish the specific 3783 system.",
  cf0302: "Exact CF0302/MTM49LT primary table not located; related MTM46 and MTM49-1L are different resin systems. Original strength units also conflict.",
  baltek: "Density alone does not establish an SB/SBC product and grade.",
  ...Object.fromEntries(["carbon-ud-nominal", "carbon-ud-wet", "carbon-weave-nominal", "carbon-weave-wet", "carbon-weave-vartm",
    "glass-ud-nominal", "glass-ud-wet", "glass-weave-nominal", "glass-weave-wet", "glass-weave-vartm"]
    .map(id => [id, "Resin, reinforcement part number and manufacturing specification are required to match a published dataset."])),
};
