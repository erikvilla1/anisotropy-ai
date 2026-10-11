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

// Hexcel 8552 / IM7 unidirectional tape, NCAMP 2019 (Rev B) report. Measured RTD column only,
// like the AS4 record above; the normalized column and the B-basis limits stay in the reports.
const im7Conditions = "70°F (21.1°C), dry as fabricated. Hexcel 8552 / IM7 unidirectional tape, 190 g/m², nominal 35% resin content; NMS 128/2, NPS 81228 cure cycle M.";
const im7Symbols: Record<string, string> = { density: "ρ", Vf: "Vf", resin: "wr", tply: "tply", Tg: "Tg" };
type Im7Row = [key: string, label: string, value: number, unit: string, page: number, method: string, conditions: string, direction: string, basis: string];
const im7Rows: Im7Row[] = [
  ["E1t", "Longitudinal tensile modulus", 23.51, "Msi", 30, "ASTM D3039/D3039M-00ε1", "[0]6; 18 specimens, 3 lots", "Fiber direction", "Measured mean"],
  ["E2t", "Transverse tensile modulus", 1.30, "Msi", 31, "ASTM D3039/D3039M-00", "[90]11; 20 specimens, 3 lots", "Transverse direction", "Measured mean"],
  ["nu12", "Poisson ratio · tension", .316, "—", 30, "ASTM D3039/D3039M-00ε1", "[0]6; 18 specimens, 3 lots", "Longitudinal–transverse", "Measured mean"],
  ["G12", "In-plane shear modulus", .68, "Msi", 34, "ASTM D3518/D3518M-94", "[+45/-45]3S; 16 specimens, 3 lots", "1–2 plane", "Measured mean"],
  ["E1c", "Longitudinal compressive modulus", 20.44, "Msi", 32, "ASTM D6641/D6641M-01ε1", "[0]14; 15 specimens, 3 lots", "Fiber direction", "Measured mean"],
  ["E2c", "Transverse compressive modulus", 1.41, "Msi", 33, "ASTM D6641/D6641M-01e1", "[90]14; 20 specimens, 3 lots", "Transverse direction", "Measured mean"],
  ["nu12c", "Poisson ratio · compression", .356, "—", 32, "ASTM D6641/D6641M-01ε1", "[0]14; 15 specimens, 3 lots", "Longitudinal–transverse", "Measured mean"],
  ["nu21c", "Minor Poisson ratio · compression", .024, "—", 33, "ASTM D6641/D6641M-01e1", "[90]14; 20 specimens, 3 lots", "2–1 directions", "Measured mean"],
  ["F1t", "Longitudinal tensile strength", 371.08, "ksi", 30, "ASTM D3039/D3039M-00ε1", "[0]6; 18 specimens, 3 lots", "Fiber direction", "Measured mean"],
  ["F2t", "Transverse tensile strength", 9.29, "ksi", 31, "ASTM D3039/D3039M-00", "[90]11; 20 specimens, 3 lots", "Transverse direction", "Measured mean"],
  ["F1c-derived", "Longitudinal compressive strength · derived", 251.13, "ksi", 28, "UNC0 cross-ply compression; lamina back-calculation", "Table 2-1, measured RTD column; derived from [90/0] cross-ply tests with a back-out factor", "Fiber direction", "Derived lamina mean"],
  ["F2c", "Transverse compressive strength", 41.44, "ksi", 33, "ASTM D6641/D6641M-01e1", "[90]14; 20 specimens, 3 lots", "Transverse direction", "Measured mean"],
  ["F12-offset", "Shear strength · 0.2% offset", 7.76, "ksi", 34, "ASTM D3518/D3518M-94", "[+45/-45]3S; 16 specimens, 3 lots", "1–2 plane", "Measured mean"],
  ["F12-5pct", "Shear strength · at 5% strain", 13.22, "ksi", 34, "ASTM D3518/D3518M-94", "[+45/-45]3S; 12 specimens, 3 lots", "1–2 plane", "Measured mean"],
  ["SBS", "Short-beam strength", 17.13, "ksi", 37, "ASTM D2344/D2344M-00ε1", "[0]34; 18 specimens, 3 lots", "Interlaminar test", "Measured mean"],
  ["tply", "Nominal cured ply thickness", .0072, "in", 28, "Normalization CPT, §1.5.8", "Nominal value used for normalization; grand average of the measured panels is 0.007229 in (p. 26)", "Through thickness", "Reported nominal"],
  ["density-LT", "Density · longitudinal-tension panels", 1.58, "g/cm³", 30, "Composite density, LT panel summary", "Longitudinal-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
  ["Vf-LT", "Fiber volume · longitudinal-tension panels", 57.30, "%", 30, "LT panel summary", "Longitudinal-tension panel summary; volume basis", "Bulk", "Reported panel property"],
  ["resin-LT", "Resin content · longitudinal-tension panels", 35.33, "%", 30, "LT panel summary", "Longitudinal-tension panel summary; mass basis", "Bulk", "Reported panel property"],
  ["Tg-dry", "Glass transition temperature · dry", 406.43, "°F", 28, "DMA, SACMA SRM 18-94", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ["Tg-wet", "Glass transition temperature · wet", 321.41, "°F", 28, "DMA, SACMA SRM 18-94", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
];
export const qualifiedCarbonIM7: CitedMaterial = {
  id: "im7-8552", name: "IM7 / 8552", family: "Carbon / epoxy", architecture: "Unidirectional · autoclave cured",
  datasetId: "ncamp-im7-8552-2019-rtd-measured-v1", dataset: "2019 qualification · material properties",
  conditions: im7Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis for the stated material and process, using E1t, E2t, G12 and ν12. Strengths are test means, not design allowables; longitudinal compression is back-calculated from cross-ply tests.",
  source: references["im7-data"],
  supportingReferences: [references["im7-stats"], references["as4-base"], references["as4-process"]],
  recordDetails: [
    "Hexcel 8552/IM7 tape, NMS 128/2. The detail specification is published on the NCAMP site; its direct link could not be confirmed on 2026-10-10 and is not recorded. The NMS 128 base specification and NPS 81228 process specification linked here cover the 8552 family.",
    "Test environments are defined on p. 22: RTD is 70 ± 10°F, dry. Panels were fabricated by Cessna and tested at NIAR; three prepreg lots.",
    "Measured and normalized columns are separate in the report (normalized by the 0.0072 in nominal cured ply thickness, p. 26). This record uses the measured RTD column only.",
    "Use tensile moduli with the tensile Poisson ratio for the elastic input set. Compressive moduli and Poisson ratios remain separately identified.",
    "Longitudinal compressive strength is derived from [90/0] cross-ply (UNC0) tests with a back-out factor, as Table 2-1 states. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "Table 3-1 of the statistical report gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 128/2 (p. 9).",
  ],
  properties: im7Rows.map(([key, label, value, unit, sourcePage, method, detail, direction, basis]) => ({
    key, label, value, unit, sourcePage, method, direction, basis, symbol: im7Symbols[key.split("-")[0]] || key,
    conditions: `70°F (21.1°C), dry as fabricated; ${detail}.`, sourceValue: value, sourceUnit: unit,
    evidence: `${label}; original report p. ${sourcePage}; ${detail}`,
  })),
};

// Shared builder for NCAMP qualification records entered from the measured RTD column.
type NcampRow = [key: string, label: string, value: number, unit: string, page: number, method: string, detail: string, direction: string, basis: string];
const ncampSymbols: Record<string, string> = { density: "ρ", Vf: "Vf", resin: "wr", tply: "tply", Tg: "Tg" };
const ncampProperties = (rows: NcampRow[], environment: string): CitedProperty[] =>
  rows.map(([key, label, value, unit, sourcePage, method, detail, direction, basis]) => ({
    key, label, value, unit, sourcePage, method, direction, basis, symbol: ncampSymbols[key.split("-")[0]] || key,
    conditions: `${environment}; ${detail}.`, sourceValue: value, sourceUnit: unit,
    evidence: `${label}; original report p. ${sourcePage}; ${detail}`,
  }));
const rtd70 = "70°F (21.1°C), dry as fabricated";

// Solvay Cycom 5320-1 / T650 unidirectional tape, NCAMP 2017 (Rev A) report.
const t650Conditions = "70°F (21.1°C), dry as fabricated. Solvay Cytec Cycom 5320-1 / T650 unidirectional tape, 145 g/m², nominal 33% resin content; NMS 532/5, NPS 85321 baseline cure cycle C.";
export const qualifiedT650: CitedMaterial = {
  id: "t650-5320-1", name: "T650 / 5320-1", family: "Carbon / epoxy", architecture: "Unidirectional · NPS 85321 cure cycle C",
  datasetId: "ncamp-t650-5320-1-2017-rtd-measured-v1", dataset: "2017 qualification · material properties",
  conditions: t650Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis for the stated material and process, using E1t, E2t, G12 and ν12. Strengths are test means, not design allowables; longitudinal compression is back-calculated from cross-ply tests.",
  source: references["t650-data"],
  supportingReferences: [references["t650-stats"]],
  recordDetails: [
    "Solvay (Cytec) Cycom 5320-1 with T650 fiber, NMS 532/5 and NPS 85321. Those specifications are published on the NCAMP site; their direct links were not confirmed on 2026-10-10 and are not recorded.",
    "Test environments are defined on p. 18: RTD is 70 ± 10°F, dry. Panels were fabricated by Gulfstream and tested at NIAR; three prepreg lots.",
    "Measured and normalized columns are separate in the report (normalized by the 0.0055 in nominal cured ply thickness, p. 21). This record uses the measured RTD column only.",
    "Use tensile moduli with the tensile Poisson ratio for the elastic input set. Compressive moduli remain separately identified; the report gives no compressive Poisson ratio in Table 2-1.",
    "Longitudinal compressive strength is derived from cross-ply (UNC0) tests with a back-out factor, as Table 2-1 states. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "Table 3-1 of the statistical report (p. 33) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 532/5 (p. 9).",
  ],
  properties: ncampProperties([
    ["E1t", "Longitudinal tensile modulus", 20.077, "Msi", 24, "ASTM D3039-08", "[0]8; 20 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["E2t", "Transverse tensile modulus", 1.331, "Msi", 25, "ASTM D3039-08", "[90]16; 21 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .326, "—", 24, "ASTM D3039-08", "[0]8; 20 specimens, 3 lots", "Longitudinal–transverse", "Measured mean"],
    ["G12", "In-plane shear modulus", .718, "Msi", 28, "ASTM D3518-07", "[45/-45]4S; 21 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Longitudinal compressive modulus", 18.356, "Msi", 26, "ASTM D6641-05", "[0]20; 21 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["E2c", "Transverse compressive modulus", 1.427, "Msi", 27, "ASTM D6641-05", "[90]20; 21 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F1t", "Longitudinal tensile strength", 299.004, "ksi", 24, "ASTM D3039-08", "[0]8; 21 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["F2t", "Transverse tensile strength", 10.096, "ksi", 25, "ASTM D3039-08", "[90]16; 21 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F1c-derived", "Longitudinal compressive strength · derived", 237.875, "ksi", 22, "UNC0 cross-ply compression; lamina back-calculation", "Table 2-1, measured RTD column; derived from cross-ply tests with a back-out factor", "Fiber direction", "Derived lamina mean"],
    ["F2c", "Transverse compressive strength", 39.751, "ksi", 27, "ASTM D6641-05", "[90]20; 23 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 8.121, "ksi", 28, "ASTM D3518-07", "[45/-45]4S; 21 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["F12-5pct", "Shear strength · at 5% strain", 13.501, "ksi", 28, "ASTM D3518-07", "[45/-45]4S; 21 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 15.639, "ksi", 36, "ASTM D2344-06", "[0]45; 21 specimens, 3 lots", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0055, "in", 22, "Normalization CPT, §1.5.8", "Average cured ply thickness used as the nominal value for normalization (p. 21)", "Through thickness", "Reported nominal"],
    ["density-LT", "Density · longitudinal-tension panels", 1.574, "g/cm³", 24, "Composite density, LT panel summary", "Longitudinal-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
    ["Vf-LT", "Fiber volume · longitudinal-tension panels", 61.88, "%", 24, "LT panel summary", "Longitudinal-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · longitudinal-tension panels", 30.66, "%", 24, "LT panel summary", "Longitudinal-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 389.13, "°F", 22, "ASTM D7028", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 321.79, "°F", 22, "ASTM D7028", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rtd70),
};

// TenCate (now Toray Advanced Composites) BT250E-6 / IM7 GP unidirectional tape, NCAMP 2017 report.
const bt250Conditions = "70°F (21.1°C), dry as fabricated. TenCate BT250E-6 / IM7 GP 12k unidirectional tape, 148 g/m², nominal 33% resin content; NMS 250/1, NPS 81250.";
export const qualifiedBT250: CitedMaterial = {
  id: "im7-bt250e-6", name: "IM7 / BT250E-6", family: "Carbon / epoxy", architecture: "Unidirectional · NPS 81250 cure",
  datasetId: "ncamp-im7-bt250e-6-2017-rtd-measured-v1", dataset: "2017 qualification · material properties",
  conditions: bt250Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis for the stated material and process, using E1t, E2t, G12 and ν12. Strengths are test means, not design allowables; longitudinal compression is back-calculated from cross-ply tests.",
  source: references["bt250-data"],
  supportingReferences: [references["bt250-stats"]],
  recordDetails: [
    "TenCate BT250E-6 with IM7 GP 12k fiber, NMS 250/1 and NPS 81250. Those specifications are published on the NCAMP site; their direct links were not confirmed on 2026-10-10 and are not recorded. TenCate Advanced Composites is now part of Toray.",
    "Test environments are defined on p. 14: RTD is 70 ± 10°F, dry. Panels were fabricated by Advanced Technologies Inc. and tested at NIAR; three prepreg lots.",
    "Measured and normalized columns are separate in the report. Normalization uses the measured 0.0058 in cured ply thickness at the supplier’s request; the theoretical value was 0.0055 in (p. 18). This record uses the measured RTD column only.",
    "Use tensile moduli with the tensile Poisson ratio for the elastic input set. Compressive moduli remain separately identified; the report gives no compressive Poisson ratio in Table 2-1.",
    "Longitudinal compressive strength is derived from cross-ply (UNC0) tests with a back-out factor, as Table 2-1 states. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "Table 3-1 of the statistical report (p. 30) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 250/1 (p. 6).",
  ],
  properties: ncampProperties([
    ["E1t", "Longitudinal tensile modulus", 22.603, "Msi", 20, "ASTM D3039-08", "[0]8; 22 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["E2t", "Transverse tensile modulus", 1.248, "Msi", 21, "ASTM D3039-08", "[90]16; 21 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .309, "—", 20, "ASTM D3039-08", "[0]8; 21 specimens, 3 lots", "Longitudinal–transverse", "Measured mean"],
    ["G12", "In-plane shear modulus", .629, "Msi", 24, "ASTM D3518-07", "[45/-45]4S; 21 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Longitudinal compressive modulus", 20.228, "Msi", 22, "ASTM D6641-09", "[0]20; 18 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["E2c", "Transverse compressive modulus", 1.340, "Msi", 23, "ASTM D6641-09", "[90]20; 19 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F1t", "Longitudinal tensile strength", 355.785, "ksi", 20, "ASTM D3039-08", "[0]8; 22 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["F2t", "Transverse tensile strength", 5.701, "ksi", 21, "ASTM D3039-08", "[90]16; 21 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F1c-derived", "Longitudinal compressive strength · derived", 213.784, "ksi", 19, "UNC0 cross-ply compression; lamina back-calculation", "Table 2-1, measured RTD column; derived from cross-ply tests with a back-out factor", "Fiber direction", "Derived lamina mean"],
    ["F2c", "Transverse compressive strength", 27.527, "ksi", 23, "ASTM D6641-09", "[90]20; 23 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 6.709, "ksi", 24, "ASTM D3518-07", "[45/-45]4S; 21 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["F12-5pct", "Shear strength · at 5% strain", 10.084, "ksi", 24, "ASTM D3518-07", "[45/-45]4S; 20 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 9.874, "ksi", 26, "ASTM D2344-06", "[0]45; 21 specimens, 3 lots", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0058, "in", 19, "Normalization CPT, §1.5.8", "Measured cured ply thickness used as the nominal value for normalization at the supplier request; theoretical value 0.0055 in (p. 18)", "Through thickness", "Reported nominal"],
    ["density-LT", "Density · longitudinal-tension panels", 1.522, "g/cm³", 20, "Composite density, LT panel summary", "Longitudinal-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
    ["Vf-LT", "Fiber volume · longitudinal-tension panels", 57.70, "%", 20, "LT panel summary", "Longitudinal-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · longitudinal-tension panels", 32.76, "%", 20, "LT panel summary", "Longitudinal-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 281.24, "°F", 19, "ASTM D7028", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 241.92, "°F", 19, "ASTM D7028", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rtd70),
};

// Toray Advanced Composites TC380 / T1100GC 24K unidirectional tape, NCAMP 2025 report.
const tc380Conditions = "70°F (21.1°C), dry as fabricated. Toray Advanced Composites TC380 / T1100GC 24K unidirectional tape, 120 g/m², nominal 35% resin content; NMS 380/1, NPS 83800.";
export const qualifiedTC380: CitedMaterial = {
  id: "t1100gc-tc380", name: "T1100GC / TC380", family: "Carbon / epoxy", architecture: "Unidirectional · NPS 83800 cure",
  datasetId: "ncamp-t1100gc-tc380-2025-rtd-measured-v1", dataset: "2025 qualification · material properties",
  conditions: tc380Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis for the stated material and process, using E1t, E2t, G12 and ν12. Strengths are test means, not design allowables; longitudinal compression is back-calculated from cross-ply tests.",
  source: references["tc380-data"],
  supportingReferences: [references["tc380-stats"]],
  recordDetails: [
    "Toray Advanced Composites TC380 resin with T1100GC 24K fiber, NMS 380/1 and NPS 83800. Those specifications are published on the NCAMP site; their direct links were not confirmed on 2026-10-10 and are not recorded.",
    "Test environments are defined on p. 24: RTD is 70 ± 10°F, dry. Panels were fabricated by the National Center for Aviation Training and tested at NIAR; three prepreg lots.",
    "Measured and normalized columns are separate in the report. Normalization uses the theoretical 0.0048 in cured ply thickness; the measured average of the qualification panels was 0.004763 in (p. 31). This record uses the measured RTD column only.",
    "Use tensile moduli with the tensile Poisson ratio for the elastic input set. Compressive moduli and the compressive Poisson ratio remain separately identified.",
    "Longitudinal compressive strength is derived from [90/0/90]7 cross-ply (UNC0) tests with a back-out factor (§2.5.4, p. 41), as Table 2-1 states. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "Table 3-1 of the statistical report (p. 36) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 380/1 (p. 10).",
  ],
  properties: ncampProperties([
    ["E1t", "Longitudinal tensile modulus", 22.97, "Msi", 39, "ASTM D3039-17", "[0]10; 18 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["E2t", "Transverse tensile modulus", 1.111, "Msi", 40, "ASTM D3039-17", "[90]18; 18 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .3132, "—", 39, "ASTM D3039-17", "[0]10; 18 specimens, 3 lots", "Longitudinal–transverse", "Measured mean"],
    ["G12", "In-plane shear modulus", .5740, "Msi", 43, "ASTM D3518-18", "[45/-45]4S; 18 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Longitudinal compressive modulus", 20.83, "Msi", 41, "ASTM D6641-23", "[0]20; 18 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["E2c", "Transverse compressive modulus", 1.198, "Msi", 42, "ASTM D6641-23", "[90]20; 18 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["nu12c", "Poisson ratio · compression", .3621, "—", 41, "ASTM D6641-23", "[0]20; 18 specimens, 3 lots", "Longitudinal–transverse", "Measured mean"],
    ["F1t", "Longitudinal tensile strength", 475.3, "ksi", 39, "ASTM D3039-17", "[0]10; 18 specimens, 3 lots", "Fiber direction", "Measured mean"],
    ["F2t", "Transverse tensile strength", 10.70, "ksi", 40, "ASTM D3039-17", "[90]18; 18 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F1c-derived", "Longitudinal compressive strength · derived", 236.2, "ksi", 41, "UNC0 cross-ply compression; lamina back-out factor (§2.5.4)", "[90/0/90]7 cross-ply; 20 specimens, 3 lots; measured RTD column", "Fiber direction", "Derived lamina mean"],
    ["F2c", "Transverse compressive strength", 29.33, "ksi", 42, "ASTM D6641-23", "[90]20; 18 specimens, 3 lots", "Transverse direction", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 6.369, "ksi", 43, "ASTM D3518-18", "[45/-45]4S; 18 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["F12-5pct", "Shear strength · at 5% strain", 11.16, "ksi", 43, "ASTM D3518-18", "[45/-45]4S; 18 specimens, 3 lots", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 14.40, "ksi", 44, "ASTM D2344-22", "[0]32; 18 specimens, 3 lots", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0048, "in", 31, "Normalization CPT, §1.5.8", "Theoretical cured ply thickness used for normalization; measured average 0.004763 in", "Through thickness", "Reported nominal"],
    ["density-LT", "Density · longitudinal-tension panels", 1.518, "g/cm³", 39, "Composite density, LT panel summary", "Longitudinal-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
    ["Vf-LT", "Fiber volume · longitudinal-tension panels", 55.96, "%", 39, "LT panel summary", "Longitudinal-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · longitudinal-tension panels", 34.01, "%", 39, "LT panel summary", "Longitudinal-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 408.21, "°F", 32, "ASTM D7028", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 332.38, "°F", 32, "ASTM D7028", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rtd70),
};

// Syensqo (formerly Solvay) EP2190 / IMS65 24K unidirectional tape, NCAMP 2025 report, phases 1 to 3.
// Room-temperature tests were run at 75°F in ambient condition, not dried, so the environment is RTA.
const rta75 = "75°F (23.9°C), ambient";
const ep2190Conditions = "75°F (23.9°C), ambient (60 to 80°F, 65% RH maximum, 48 h minimum). Syensqo EP2190 / IMS65 24K unidirectional tape, 145 g/m², nominal 35% resin content; NMS 219/1, NPS 82190.";
export const qualifiedEP2190: CitedMaterial = {
  id: "ims65-ep2190", name: "IMS65 / EP2190", family: "Carbon / epoxy", architecture: "Unidirectional · NPS 82190 cure",
  datasetId: "ncamp-ims65-ep2190-2025-rta-measured-v1", dataset: "2025 qualification · material properties",
  conditions: ep2190Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis for the stated material and process, using E1t, E2t, G12 and ν12. Strengths are test means at ambient room-temperature condition, not design allowables.",
  source: references["ep2190-data"],
  supportingReferences: [references["ep2190-stats"]],
  recordDetails: [
    "Syensqo (formerly Solvay) EP2190 resin with IMS65 24K fiber, NMS 219/1 and NPS 82190. Those specifications are published on the NCAMP site; their direct links were not confirmed on 2026-10-10 and are not recorded. Prepreg made in Wrexham, UK; panels and tests at the Solvay facility in Anaheim under NCAMP supervision; phases 1 to 3, four prepreg lots for most tests.",
    "Test environments are defined on p. 26: RTA is 75 ± 5°F, ambient, meaning specimens exposed at 60 to 80°F and 65% RH maximum for at least 48 h before test, not dried. This differs from the dried RTD condition of the other NCAMP records.",
    "Measured and normalized columns are separate in the report (normalized by the theoretical 0.0056 in cured ply thickness; measured average 0.005763 in, p. 30). This record uses the measured RTA column only.",
    "Longitudinal and transverse compression were measured directly on [0]8 and [90]8 specimens by SACMA SRM 1R-94, so the compressive strengths are measured means, not cross-ply back-outs. No compressive Poisson ratio is reported in Table 2-1.",
    "The dry Tg footnote on p. 33 says specimens may have absorbed ambient moisture before DMA testing, which depressed the 337.71°F value; Syensqo batch-release history gives 377 to 406°F.",
    "Table 3-1 of the statistical report (p. 37) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 219/1 (p. 9).",
  ],
  properties: ncampProperties([
    ["E1t", "Longitudinal tensile modulus", 22.04, "Msi", 39, "ASTM D3039-17", "[0]8; 24 specimens, 4 lots", "Fiber direction", "Measured mean"],
    ["E2t", "Transverse tensile modulus", 1.255, "Msi", 40, "ASTM D3039-17", "[90]16; 30 specimens, 4 lots", "Transverse direction", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .3299, "—", 39, "ASTM D3039-17", "[0]8; 24 specimens, 4 lots", "Longitudinal–transverse", "Measured mean"],
    ["nu21", "Minor Poisson ratio · tension", .01683, "—", 40, "ASTM D3039-17", "[90]16; 24 specimens, 4 lots", "2–1 directions", "Measured mean"],
    ["G12", "In-plane shear modulus", .6053, "Msi", 45, "ASTM D3518-18", "[45/-45]2S; 30 specimens, 4 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Longitudinal compressive modulus", 19.72, "Msi", 42, "SACMA SRM 1R-94", "[0]8; 24 specimens, 4 lots", "Fiber direction", "Measured mean"],
    ["E2c", "Transverse compressive modulus", 1.503, "Msi", 44, "SACMA SRM 1R-94", "[90]8; 24 specimens, 4 lots", "Transverse direction", "Measured mean"],
    ["F1t", "Longitudinal tensile strength", 415.8, "ksi", 39, "ASTM D3039-17", "[0]8; 24 specimens, 4 lots", "Fiber direction", "Measured mean"],
    ["F2t", "Transverse tensile strength", 11.14, "ksi", 40, "ASTM D3039-17", "[90]16; 30 specimens, 4 lots", "Transverse direction", "Measured mean"],
    ["F1c", "Longitudinal compressive strength", 207.7, "ksi", 41, "SACMA SRM 1R-94", "[0]8; 24 specimens, 4 lots; measured directly, not a cross-ply back-out", "Fiber direction", "Measured mean"],
    ["F2c", "Transverse compressive strength", 41.31, "ksi", 43, "SACMA SRM 1R-94", "[90]8; 24 specimens, 4 lots", "Transverse direction", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 6.187, "ksi", 45, "ASTM D3518-18", "[45/-45]2S; 30 specimens, 4 lots", "1–2 plane", "Measured mean"],
    ["F12-5pct", "Shear strength · at 5% strain", 10.63, "ksi", 45, "ASTM D3518-18", "[45/-45]2S; 24 specimens, 4 lots", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 12.64, "ksi", 53, "ASTM D2344-16", "[0]44; 24 specimens, 4 lots", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0056, "in", 30, "Normalization CPT, §1.5.8", "Theoretical cured ply thickness used for normalization; measured average 0.005763 in", "Through thickness", "Reported nominal"],
    ["density-LT", "Density · longitudinal-tension panels", 1.553, "g/cm³", 39, "Composite density, LT panel summary", "Longitudinal-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
    ["Vf-LT", "Fiber volume · longitudinal-tension panels", 56.57, "%", 39, "LT panel summary", "Longitudinal-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · longitudinal-tension panels", 35.17, "%", 39, "LT panel summary", "Longitudinal-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 337.71, "°F", 33, "ASTM D7028", "Dry; lamina summary. The report notes ambient moisture before DMA testing lowered this value (historical 377 to 406°F). Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 286.78, "°F", 33, "ASTM D7028", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rta75),
};
