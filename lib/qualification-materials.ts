import type { CitedMaterial, CitedProperty } from "./curated-materials";
import { carbonAdditions, legacyGlassAdditions } from "./material-property-additions";
import rawReferences from "./qualification-references.json";

// The JSON carries the rights class as a string; the record type narrows it (ADR-0018).
const references = rawReferences as unknown as Record<keyof typeof rawReferences, CitedMaterial["source"] & { role: string }>;

const reviewedOn = "2026-10-02";
const recordRevision = "2026-10-02.1";
const elasticInputs = { E1: "E1t", E2: "E2t", G12: "G12", nu12: "nu12" };
type Row = [key: string, label: string, value: number, unit: string, direction: string, method: string, page: number, basis?: string];
function properties(rows: Row[], conditions: string): CitedProperty[] {
  return rows.map(([key, label, value, unit, direction, method, sourcePage, basis = "Measured mean"]) => ({
    key, label, value, unit, direction, method, sourcePage, basis, conditions, symbol: key,
    evidence: basis === "Derived lamina mean" ? "Table 2-1; measured RTD column, lamina compression back-calculated from UNC0 cross-ply tests" : "RTD measured mean; normalized values and statistical limits excluded",
  }));
}

const carbonConditions = "Room temperature, dry as fabricated: 75°F (23.9°C); short-beam test at 70°F (21.1°C). AS4 / 8552 unidirectional tape, 190 g/m², nominal 35% resin content; baseline autoclave cure M.";
export const qualifiedCarbon: CitedMaterial = {
  id: "as4-8552", name: "AS4 / 8552", family: "Carbon / epoxy", architecture: "Unidirectional · autoclave cured",
  datasetId: "ncamp-as4-8552-2011-rtd-measured-v2", dataset: "2011 qualification · material properties",
  conditions: carbonConditions, reviewedOn, recordRevision, elasticInputs,
  application: "Elastic ply and laminate analysis for the stated material and process, using E1t, E2t, G12 and ν12. Strengths are test means, not design allowables; longitudinal compression is back-calculated from cross-ply tests.",
  source: references["as4-data"],
  supportingReferences: [references["as4-stats"], references["as4-detail"], references["as4-base"], references["as4-process"]],
  recordDetails: [
    "Physical entries describe longitudinal-tension panels; other panels can differ. Dry and wet Tg remain separate from the room-temperature mechanical data. Curved-beam interlaminar strength is a test-specific result, not a general uniaxial strength allowable.",
    "Hexcel 8552/AS4 tape, NMS 128/1 Type 35 Class 1 Grade 190. This is a different resin system from AS4/3501-6.",
    "The 2011 test program used NMS 128/1 (original) and NPS 81228 Rev A, cure M. The later specification editions are linked for context, not substituted for the tested process.",
    "Use tensile moduli with the tensile Poisson’s ratio for the elastic input set. Compressive moduli and Poisson’s ratio remain separately identified.",
    "Measured and thickness-normalized columns are separate in the report. This record uses the measured RTD column only. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "The statistical report contains recommended B-basis values and explicit exclusions; those limits are not replaced by the means shown here. Applicability to a manufactured part requires matching material, process and environment.",
  ],
  properties: properties([
    ["E1t", "Longitudinal tensile modulus", 19.09, "Msi", "Fiber direction", "ASTM D3039/D3039M-00 (2006)", 32],
    ["E2t", "Transverse tensile modulus", 1.34, "Msi", "Transverse direction", "ASTM D3039/D3039M-00 (2006)", 33],
    ["nu12", "Poisson ratio · tension", .302, "—", "Longitudinal–transverse", "ASTM D3039/D3039M-00 (2006)", 32],
    ["G12", "In-plane shear modulus", .70, "Msi", "1–2 plane", "ASTM D3518/D3518M-94 (2007)", 38],
    ["E1c", "Longitudinal compressive modulus", 16.76, "Msi", "Fiber direction", "ASTM D6641/D6641M-01e1", 34],
    ["E2c", "Transverse compressive modulus", 1.43, "Msi", "Transverse direction", "ASTM D6641/D6641M-01e1", 35],
    ["nu12c", "Poisson ratio · compression", .335, "—", "Longitudinal–transverse", "ASTM D6641/D6641M-01e1", 34],
    ["F1t", "Longitudinal tensile strength", 299.22, "ksi", "Fiber direction", "ASTM D3039/D3039M-00 (2006)", 32],
    ["F2t", "Transverse tensile strength", 9.27, "ksi", "Transverse direction", "ASTM D3039/D3039M-00 (2006)", 33],
    ["F1c-derived", "Longitudinal compressive strength · derived", 215.29, "ksi", "Fiber direction", "UNC0 cross-ply compression; lamina back-calculation", 30, "Derived lamina mean"],
    ["F2c", "Transverse compressive strength", 38.85, "ksi", "Transverse direction", "ASTM D6641/D6641M-01e1", 35],
    ["F12-offset", "Shear strength · 0.2% offset", 8.00, "ksi", "1–2 plane", "ASTM D3518/D3518M-94 (2007)", 38],
    ["F12-5pct", "Shear strength · at 5% strain", 13.28, "ksi", "1–2 plane", "ASTM D3518/D3518M-94 (2007)", 38],
    ["SBS", "Short-beam strength", 16.63, "ksi", "Interlaminar test", "ASTM D2344/D2344M-00 (2006)", 39],
  ], carbonConditions).map(p => ({ ...p, conditions: p.key === "SBS"
    ? "70°F (21.1°C), dry as fabricated; [0]34 short-beam specimens; report p. 39."
    : "75°F (23.9°C), dry as fabricated; AS4 / 8552, 190 g/m², 35% nominal resin content; baseline cure M." })).concat(carbonAdditions),
};

export const glassSupportingReferences = [references["glass-stats"], references["glass-detail"], references["glass-base"], references["glass-process"]];
const glassConditions = "75°F (23.9°C), dry as fabricated. FiberCote E765 epoxy / BGF 7781 E-glass, eight-harness satin; vacuum-bag cure 270–280°F (132.2–137.8°C), 110–130 minutes.";
export const qualifiedGlass: CitedMaterial = {
  id: "7781-e765", name: "7781 / E-765", family: "Glass / epoxy", architecture: "Woven · eight-harness satin",
  datasetId: "agate-e765-2001-rtd-measured-v2", dataset: "2001 qualification · material properties",
  conditions: glassConditions, reviewedOn, recordRevision, elasticInputs,
  application: "Elastic ply and laminate analysis for the original qualification material and process, using E1t, E2t, G12 and ν12. Strengths are measured means. Select the 2025 dataset to view the later test program separately.",
  source: references["glass-legacy"],
  supportingReferences: [references["glass-data"], ...glassSupportingReferences],
  recordDetails: [
    "Original AGATE FiberCote E765 / BGF Industries 7781 qualification program. Warp is axis 1; fill is axis 2. Manufacturing and cure are documented in §§2.1–2.2 of the original report.",
    "Mechanical reference values come from the same original RTD qualification program. Moduli and Poisson’s ratio use six specimens from three prepreg lots; strength sample counts are in the linked individual tables.",
    "Physical ranges describe the warp-tension panels; thermal rows retain separate dry/wet conditioning. Tg is not a maximum service temperature.",
    "Displayed axial results are measured means, not the adjacent values normalized to 0.0098 in cured-ply thickness. The 0.0098 in normalization reference is not an actual ply-thickness measurement.",
    "Original shear uses ASTM D5379-93 (V-notched beam). The 2025 dataset uses ASTM D3518 ±45° tension; its offset/5%-strain results are different quantities and must not replace this shear strength directly.",
    "The 2025 publication does not report Poisson’s ratio. Its bagging Option 2 differs from the original baseline Option 1. The linked equivalency report compares the programs; this library does not assert universal interchangeability.",
    "The report’s B-basis columns remain in the original reference; this record displays means. Apparent interlaminar strength on p. 34 is explicitly for quality control only and is excluded from this analysis set.",
  ],
  properties: properties([
    ["E1t", "Warp tensile modulus", 3.73, "Msi", "Warp", "ASTM D3039-95", 29],
    ["E2t", "Fill tensile modulus", 3.52, "Msi", "Fill", "ASTM D3039-95", 30],
    ["nu12", "Poisson ratio · tension", .157, "—", "Warp–fill", "ASTM D3039-95", 29],
    ["G12", "In-plane shear modulus", .70, "Msi", "1–2 plane", "ASTM D5379-93", 33],
    ["E1c", "Warp compressive modulus", 3.81, "Msi", "Warp", "SACMA SRM 1-94 / ASTM D695-91 (modified)", 31],
    ["E2c", "Fill compressive modulus", 3.72, "Msi", "Fill", "SACMA SRM 1-94 / ASTM D695-91 (modified)", 32],
    ["F1t", "Warp tensile strength", 64.94, "ksi", "Warp", "ASTM D3039-95", 29],
    ["F2t", "Fill tensile strength", 52.36, "ksi", "Fill", "ASTM D3039-95", 30],
    ["F1c", "Warp compressive strength", 73.74, "ksi", "Warp", "SACMA SRM 1-94 / ASTM D695-91 (modified)", 31],
    ["F2c", "Fill compressive strength", 58.28, "ksi", "Fill", "SACMA SRM 1-94 / ASTM D695-91 (modified)", 32],
    ["F12", "In-plane shear strength · V-notched beam", 19.05, "ksi", "1–2 plane", "ASTM D5379-93", 33],
  ], glassConditions).concat(legacyGlassAdditions),
};
