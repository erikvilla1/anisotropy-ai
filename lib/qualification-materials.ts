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

// NASA/TM-20230001560 (Glenn Research Center and Arizona State University, 2023): a second,
// independent IM7 / 8552 dataset shown beside the NCAMP record through the dataset picker.
// Values are the printed averages in psi; the record stores Msi and ksi with the printed psi
// value kept as the source value. Printed page = PDF page − 6.
type NasaRow = [key: string, label: string, value: number, unit: string, sourceValue: number, sourceUnit: string, pdfPage: number, method: string, detail: string, direction: string, basis: string];
const nasaConditions = "Room temperature, quasi-static loading; the report states no test temperature value or specimen conditioning. IM7 / 8552 unidirectional tape, nominal 190 g/m² and 35% resin content; 16-ply in-plane panels (PT1) and a 120-ply through-thickness panel (PT2); three replicates per test unless stated; strains by digital image correlation.";
const nasaRows: NasaRow[] = [
  ["E1t", "Longitudinal tensile modulus", 23.105148, "Msi", 23105148, "psi", 18, "ASTM D3039; MTS 810 frame", "Table 6; [0]16 specimens, 5 replicates (2 constant thickness, 3 reduced gage thickness)", "Fiber direction", "Measured mean"],
  ["E2t", "Transverse tensile modulus", 1.299337, "Msi", 1299337, "psi", 21, "ASTM D3039; MTS 810 frame", "Table 8; [90]16 specimens, 3 replicates", "Transverse direction", "Measured mean"],
  ["E3t", "Through-thickness tensile modulus", 1.089994, "Msi", 1089994, "psi", 24, "Non-standard geometry dictated by the 120-ply panel; MTS Exceed frame", "Table 10; 3 replicates; the report says the ASTM standard could not be followed (p. 16)", "Through thickness", "Measured mean"],
  ["nu12", "Poisson ratio · tension", .3235, "—", .3235, "—", 18, "ASTM D3039; digital image correlation", "Table 6; [0]16 specimens, 5 replicates", "Longitudinal–transverse", "Measured mean"],
  ["nu21", "Minor Poisson ratio · tension", .0208, "—", .0208, "—", 21, "ASTM D3039; digital image correlation", "Table 8; [90]16 specimens, 3 replicates", "2–1 directions", "Measured mean"],
  ["nu31", "Poisson ratio · through-thickness tension", .026, "—", .026, "—", 24, "Non-standard geometry; digital image correlation in the 1–3 plane", "Table 10; 3 replicates; coefficient of variation 16.8%", "3–1 directions", "Measured mean"],
  ["G12", "In-plane shear modulus", .650712, "Msi", 650712, "psi", 37, "ASTM D5379/D5379M-12 (V-notched beam)", "Table 18; engineering shear strain basis; 3 replicates", "1–2 plane", "Measured mean"],
  ["G23", "Interlaminar shear modulus · 2–3 plane", .414695, "Msi", 414695, "psi", 40, "ASTM D5379/D5379M-12 (V-notched beam)", "Table 20; engineering shear strain basis; 3 replicates from the 120-ply panel", "2–3 plane", "Measured mean"],
  ["G13", "Interlaminar shear modulus · 1–3 plane", .763931, "Msi", 763931, "psi", 44, "ASTM D5379/D5379M-12 (V-notched beam)", "Table 22; engineering shear strain basis; 3 replicates from the 120-ply panel", "1–3 plane", "Measured mean"],
  ["E1c", "Longitudinal compressive modulus", 19.450971, "Msi", 19450971, "psi", 27, "ASTM D6641 geometry; combined loading compression fixture; Instron 1332 frame", "Table 12; [0]16 specimens, 3 replicates", "Fiber direction", "Measured mean"],
  ["E2c", "Transverse compressive modulus", 1.334952, "Msi", 1334952, "psi", 31, "ASTM D3410 geometry; combined loading compression fixture; MTS 810 frame", "Table 14; [90]16 specimens, 3 replicates", "Transverse direction", "Measured mean"],
  ["E3c", "Through-thickness compressive modulus", 1.459939, "Msi", 1459939, "psi", 33, "Cuboid adapted from ASTM D7291; Instron 1332 frame", "Table 16; 3 replicates from the 120-ply panel; no standard exists for this property (p. 26)", "Through thickness", "Measured mean"],
  ["F1t", "Longitudinal tensile strength", 392.337, "ksi", 392337, "psi", 18, "ASTM D3039; MTS 810 frame", "Table 6; mean of the 3 reduced-thickness replicates carried to failure; the 2 constant-thickness specimens debonded their tabs first (p. 9)", "Fiber direction", "Measured mean"],
  ["F2t", "Transverse tensile strength", 11.742, "ksi", 11742, "psi", 21, "ASTM D3039; MTS 810 frame", "Table 8; [90]16 specimens, 3 replicates", "Transverse direction", "Measured mean"],
  ["F3t", "Through-thickness tensile strength", 7.846, "ksi", 7846, "psi", 24, "Non-standard geometry dictated by the 120-ply panel", "Table 10; 3 replicates; two failed near the grip region (p. 16)", "Through thickness", "Measured mean"],
  ["F1c", "Longitudinal compressive strength", 116.744, "ksi", 116744, "psi", 27, "ASTM D6641 geometry; combined loading compression fixture", "Table 12; 3 replicates; the report records end-crushing and longitudinal matrix splitting in the gage area (p. 20); far below the NCAMP cross-ply back-out", "Fiber direction", "Measured mean"],
  ["F2c", "Transverse compressive strength", 34.741, "ksi", 34741, "psi", 31, "ASTM D3410 geometry; combined loading compression fixture", "Table 14; 3 replicates; brooming in the middle of the gage (BGM) failure mode", "Transverse direction", "Measured mean"],
  ["F3c", "Through-thickness compressive strength", 35.458, "ksi", 35458, "psi", 33, "Cuboid adapted from ASTM D7291", "Table 16; 3 replicates; brittle matrix failure in the 1–3 plane", "Through thickness", "Measured mean"],
  ["F12-5pct", "Shear strength · at 5% strain", 14.492, "ksi", 14492, "psi", 37, "ASTM D5379/D5379M-12 (V-notched beam)", "Table 18; stress at 0.05 engineering shear strain; tests ran beyond 5% but not to failure (p. 28)", "1–2 plane", "Measured mean"],
  ["F23", "Interlaminar shear strength · 2–3 plane", 7.410, "ksi", 7410, "psi", 40, "ASTM D5379/D5379M-12 (V-notched beam)", "Table 20; peak stress at failure, mean ultimate engineering shear strain 0.0197; angled cracking adjacent to the notches", "2–3 plane", "Measured mean"],
  ["F13-5pct", "Interlaminar shear strength · 1–3 plane at 5% strain", 15.031, "ksi", 15031, "psi", 44, "ASTM D5379/D5379M-12 (V-notched beam)", "Table 22; stress at about 0.05 engineering shear strain (mean 0.0497); tests ran beyond 5% but not to failure (p. 36)", "1–3 plane", "Measured mean"],
  ["tply", "Nominal cured ply thickness", .18, "mm", .18, "mm", 8, "Table 1, nominal composite characteristics", "Quoted by the report from the NCAMP specification (Ng and Tomblin, NMS 128/2 Rev B, 2013), not measured in this program", "Through thickness", "Reported nominal"],
  ["resin-nominal", "Resin content · nominal", 35, "%", 35, "%", 8, "Table 1, nominal composite characteristics", "35 ± 2 wt.%, quoted from the NCAMP specification; fiber areal weight 190 g/m²", "Bulk", "Reported nominal"],
  ["SG", "Specific gravity", 1.61, "—", 1.61, "—", 58, "ASTM D792-13 immersion", "Table 31; 3 edge samples of the 120-ply panel; specific gravity, multiply by the density of water for mass density", "Bulk", "Measured mean"],
];
export const nasaCarbonIM7: CitedMaterial = {
  id: "im7-8552", name: "IM7 / 8552", family: "Carbon / epoxy", architecture: "Unidirectional",
  datasetId: "nasa-tm-20230001560-im7-8552-rt-measured-v1", dataset: "NASA 2023 characterization · room-temperature means",
  conditions: nasaConditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Independent check of the NCAMP IM7 / 8552 in-plane elastic set, and the only through-thickness moduli (E3, G23, G13) in the library for this material. Elastic inputs E1t, E2t, G12 and ν12 come from one panel set with three to five replicates. Strengths are small-sample means, not design allowables; the longitudinal compressive strength is not comparable with the NCAMP cross-ply back-out.",
  source: references["im7-nasa-2023"],
  recordDetails: [
    "Second, independent IM7 / 8552 dataset, shown beside the NCAMP qualification record through the dataset picker and never merged with it. The tests were run by Arizona State University and NASA Glenn to build MAT213 impact-model input, not as a qualification program: one panel set, three replicates per test (five for longitudinal tension modulus), no prepreg lots, and no statistics beyond mean and standard deviation.",
    "The report says room temperature and quasi-static loading (pp. 1 and 52) and gives no temperature value or conditioning procedure. The record repeats that wording instead of assuming the 70°F dry condition of the NCAMP record.",
    "Longitudinal compression (Table 12) was measured on 16-ply [0] specimens in a combined loading compression fixture per ASTM D6641. The report records end-crushing and longitudinal matrix splitting in the gage area. The 116.7 ksi mean is far below the 251 ksi NCAMP cross-ply back-out for the same material; the entry keeps the measured value with its method so the difference stays visible.",
    "Two of the five longitudinal tension specimens, the constant-thickness ones, were not carried to failure because their tabs debonded (p. 9). The strength mean covers the three reduced-thickness specimens; the modulus and Poisson means cover all five.",
    "Shear moduli are stated in terms of engineering shear strain (pp. 28, 32, 36). The 1–2 and 1–3 plane tests ran beyond 5% engineering strain but not to failure, so those strengths are the stress at 5% strain. The 2–3 plane specimens failed at about 2% strain, so that strength is a failure value.",
    "Through-thickness tension and compression used geometries the report says depart from the ASTM standards (pp. 16 and 26): tension specimens sized by the 120-ply panel thickness, compression cuboids adapted from ASTM D7291. Those entries are for information with that caveat.",
    "Nominal ply thickness and resin content in Table 1 are quoted by the report from the NCAMP specification (Ng and Tomblin, NMS 128/2 Rev B, 2013), not measured here. Specific gravity was measured by ASTM D792-13 on edge samples of the 120-ply panel (Table 31, p. 52).",
    "The NASA Technical Reports Server citation page lists the report with Public Use Permitted and public distribution. The report is linked from the publisher, not copied.",
  ],
  properties: nasaRows.map(([key, label, value, unit, sourceValue, sourceUnit, sourcePage, method, detail, direction, basis]) => ({
    key, label, value, unit, sourceValue, sourceUnit, sourcePage, printedPage: sourcePage - 6, method, direction, basis,
    symbol: ncampSymbols[key.split("-")[0]] || key, conditions: `Room temperature, quasi-static; ${detail}.`,
    evidence: `${label}; printed page ${sourcePage - 6} (PDF page ${sourcePage}); ${detail}`,
  })),
};

// NCAMP woven fabric records. Warp is axis 1, fill is axis 2. Measured RTD column only;
// compression is measured directly on [0] and [90] fabric specimens, so F1c and F2c are
// measured means, not cross-ply back-outs.
const pwConditions = (system: string) => `70°F (21.1°C), dry as fabricated. ${system}`;

const as4pwConditions = pwConditions("Hexcel 8552S / AS4 3k plain weave fabric, 193 g/m², nominal 38% resin content; NMS 128/3, NPS 81228 cure cycle M; panels fabricated by Cessna, tested at NIAR; three prepreg lots.");
export const qualifiedAS4PW: CitedMaterial = {
  id: "as4-8552s-pw", name: "AS4 PW / 8552S", family: "Carbon / epoxy", architecture: "Woven · 3k plain weave · autoclave cured",
  datasetId: "ncamp-as4-8552s-pw-2011-rtd-measured-v1", dataset: "2011 qualification · material properties",
  conditions: as4pwConditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis of the woven ply for the stated material and process, using the warp and fill tensile moduli, G12 and ν12. Strengths are test means, not design allowables. Shear strength is reported at 0.2% offset only for this condition.",
  source: references["as4pw-data"],
  supportingReferences: [references["as4pw-stats"], references["as4-base"], references["as4-process"]],
  recordDetails: [
    "Hexcel 8552S resin on AS4 3k plain weave, NMS 128/3. The detail specification link was not confirmed on 2026-10-10; the NMS 128 base and NPS 81228 process specifications are linked for the 8552 family. Warp is axis 1 and fill is axis 2 (p. 9).",
    "Test environments are defined on p. 22: RTD is 70 ± 10°F, dry. Measured and normalized columns are separate in the report (normalized by the 0.0078 in average cured ply thickness, p. 27). This record uses the measured RTD column only.",
    "Warp and fill compression were measured directly on [0]15 and [90]15 fabric specimens by ASTM D6641, so the compressive strengths are measured means. The report prints compressive Poisson ratios ν12c and ν21c; both are recorded.",
    "In-plane shear at 5% strain is not reported for the RTD condition (Table 2-1 prints a dash), so only the 0.2% offset strength is recorded. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "Table 3-1 of the statistical report (p. 33) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 128/3 (p. 9).",
  ],
  properties: ncampProperties([
    ["E1t", "Warp tensile modulus", 9.58, "Msi", 31, "ASTM D3039-00", "[0]15; 3 lots", "Warp", "Measured mean"],
    ["E2t", "Fill tensile modulus", 9.66, "Msi", 32, "ASTM D3039-00", "[90]15; 3 lots", "Fill", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .046, "—", 29, "ASTM D3039-00", "Table 2-1, measured RTD column; warp tension", "Warp–fill", "Measured mean"],
    ["G12", "In-plane shear modulus", .72, "Msi", 35, "ASTM D3518-94", "[45/-45]2S; 3 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Warp compressive modulus", 9.20, "Msi", 33, "ASTM D6641-01", "[0]15; 3 lots", "Warp", "Measured mean"],
    ["E2c", "Fill compressive modulus", 9.01, "Msi", 34, "ASTM D6641-01e1", "[90]15; 3 lots", "Fill", "Measured mean"],
    ["nu12c", "Poisson ratio · compression", .046, "—", 29, "ASTM D6641-01", "Table 2-1, measured RTD column; warp compression", "Warp–fill", "Measured mean"],
    ["nu21c", "Minor Poisson ratio · compression", .054, "—", 29, "ASTM D6641-01e1", "Table 2-1, measured RTD column; fill compression", "Fill–warp", "Measured mean"],
    ["F1t", "Warp tensile strength", 111.52, "ksi", 31, "ASTM D3039-00", "[0]15; 3 lots", "Warp", "Measured mean"],
    ["F2t", "Fill tensile strength", 109.19, "ksi", 32, "ASTM D3039-00", "[90]15; 3 lots", "Fill", "Measured mean"],
    ["F1c", "Warp compressive strength", 122.37, "ksi", 33, "ASTM D6641-01", "[0]15; 3 lots; measured directly on fabric specimens", "Warp", "Measured mean"],
    ["F2c", "Fill compressive strength", 113.31, "ksi", 34, "ASTM D6641-01e1", "[90]15; 3 lots; measured directly on fabric specimens", "Fill", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 8.11, "ksi", 35, "ASTM D3518-94", "[45/-45]2S; 3 lots; the 5% strain value is not reported for RTD", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 13.36, "ksi", 29, "ASTM D2344", "Table 2-1, measured RTD column", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0078, "in", 27, "Normalization CPT, §1.5.8", "Average cured ply thickness used as the nominal value for normalization", "Through thickness", "Reported nominal"],
    ["density-LT", "Density · warp-tension panels", 1.57, "g/cm³", 31, "Composite density, warp-tension panel summary", "Warp-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
    ["Vf-LT", "Fiber volume · warp-tension panels", 55.53, "%", 31, "Warp-tension panel summary", "Warp-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · warp-tension panels", 36.63, "%", 31, "Warp-tension panel summary", "Warp-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 396.75, "°F", 29, "DMA, SACMA SRM 18-94", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 332.02, "°F", 29, "DMA, SACMA SRM 18-94", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rtd70),
};

const t650pwConditions = pwConditions("Cytec (Solvay) Cycom 5320-1 / T650 3k plain weave fabric, nominal 36% resin content; NMS 532/6, NPS 85321 baseline cure cycle C (out of autoclave); panels fabricated by Gulfstream, tested at NIAR; three prepreg lots.");
export const qualifiedT650PW: CitedMaterial = {
  id: "t650-5320-1-pw", name: "T650 PW / 5320-1", family: "Carbon / epoxy", architecture: "Woven · 3k plain weave · out-of-autoclave cured",
  datasetId: "ncamp-t650-5320-1-pw-2015-rtd-measured-v1", dataset: "2015 qualification · material properties",
  conditions: t650pwConditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis of the woven ply for the stated material and process, using the warp and fill tensile moduli, G12 and ν12. Strengths are test means, not design allowables.",
  source: references["t650pw-data"],
  supportingReferences: [references["t650pw-stats"]],
  recordDetails: [
    "Cycom 5320-1 resin on T650 3k plain weave, NMS 532/6 and NPS 85321. Those specifications are published on the NCAMP site; their direct links were not confirmed on 2026-10-10 and are not recorded. Warp is axis 1 and fill is axis 2 (p. 9).",
    "RTD is 70°F, dry (individual test summaries, p. 23). Measured and normalized columns are separate in the report (normalized by the 0.0077 in average cured ply thickness, p. 20). This record uses the measured RTD column only.",
    "Warp and fill compression were measured directly on [0]15 and [90]15 fabric specimens by ASTM D6641-05, so the compressive strengths are measured means. Table 2-1 prints no compressive Poisson ratio.",
    "In-plane shear is ASTM D3518-07 on [45/-45]3S; the 0.2% offset and 5% strain strengths are both reported for RTD. Short-beam strength is an apparent interlaminar test result, not an in-plane shear input.",
    "Table 3-1 of the statistical report (p. 34) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 532/6 (p. 8).",
  ],
  properties: ncampProperties([
    ["E1t", "Warp tensile modulus", 9.990, "Msi", 23, "ASTM D3039-08", "[0]15; 3 lots", "Warp", "Measured mean"],
    ["E2t", "Fill tensile modulus", 9.931, "Msi", 24, "ASTM D3039-08", "[90]15; 3 lots", "Fill", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .053, "—", 23, "ASTM D3039-08", "[0]15; 3 lots", "Warp–fill", "Measured mean"],
    ["G12", "In-plane shear modulus", .735, "Msi", 27, "ASTM D3518-07", "[45/-45]3S; 3 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Warp compressive modulus", 9.370, "Msi", 25, "ASTM D6641-05", "[0]15; 3 lots", "Warp", "Measured mean"],
    ["E2c", "Fill compressive modulus", 8.876, "Msi", 26, "ASTM D6641-05", "[90]15; 3 lots", "Fill", "Measured mean"],
    ["F1t", "Warp tensile strength", 124.900, "ksi", 23, "ASTM D3039-08", "[0]15; 3 lots", "Warp", "Measured mean"],
    ["F2t", "Fill tensile strength", 121.810, "ksi", 24, "ASTM D3039-08", "[90]15; 3 lots", "Fill", "Measured mean"],
    ["F1c", "Warp compressive strength", 106.167, "ksi", 25, "ASTM D6641-05", "[0]15; 3 lots; measured directly on fabric specimens", "Warp", "Measured mean"],
    ["F2c", "Fill compressive strength", 100.365, "ksi", 26, "ASTM D6641-05", "[90]15; 3 lots; measured directly on fabric specimens", "Fill", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 8.299, "ksi", 27, "ASTM D3518-07", "[45/-45]3S; 3 lots", "1–2 plane", "Measured mean"],
    ["F12-5pct", "Shear strength · at 5% strain", 14.650, "ksi", 27, "ASTM D3518-07", "[45/-45]3S; 3 lots", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 11.035, "ksi", 21, "ASTM D2344", "Table 2-1, measured RTD column", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0077, "in", 20, "Normalization CPT, §1.5.8", "Average cured ply thickness used as the nominal value for normalization", "Through thickness", "Reported nominal"],
    ["density-LT", "Density · warp-tension panels", 1.544, "g/cm³", 23, "Composite density, warp-tension panel summary", "Warp-tension panel summary; not a universal density for every tested panel", "Bulk", "Reported panel property"],
    ["Vf-LT", "Fiber volume · warp-tension panels", 57.73, "%", 23, "Warp-tension panel summary", "Warp-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · warp-tension panels", 34.10, "%", 23, "Warp-tension panel summary", "Warp-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 374.80, "°F", 21, "ASTM D7028", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 318.62, "°F", 21, "ASTM D7028", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rtd70),
};

const tc250Conditions = pwConditions("TenCate (Toray) TC250 / HTS40 F13 12k plain weave fabric (TCAC 12k HTS SFP OSI/TC250), nominal 42% resin content; NMS 688/2, NPS 81688 cure cycle C; panels fabricated by Advanced Composites Technologies, tested at NIAR; three prepreg lots.");
export const qualifiedTC250: CitedMaterial = {
  id: "hts40-tc250", name: "HTS40 PW / TC250", family: "Carbon / epoxy", architecture: "Woven · 12k plain weave · out-of-autoclave cured",
  datasetId: "ncamp-hts40-tc250-2016-rtd-measured-v1", dataset: "2016 qualification · material properties",
  conditions: tc250Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Elastic ply and laminate analysis of the woven ply for the stated material and process, using the warp and fill tensile moduli, G12 and ν12. Strengths are test means, not design allowables. The glass transition temperature is low; the elevated-temperature condition in this program is 180°F.",
  source: references["tc250-data"],
  supportingReferences: [references["tc250-stats"]],
  recordDetails: [
    "TenCate TC250 resin on HTS40 F13 12k 800 tex plain weave, NMS 688/2 and NPS 81688. Those specifications are published on the NCAMP site; their direct links were not confirmed on 2026-10-10 and are not recorded. Warp is axis 1 and fill is axis 2 (p. 9).",
    "Test environments are defined on p. 19: RTD is 70 ± 10°F, dry; ETD and ETW are 180°F for this material. Measured and normalized columns are separate in the report (normalized by the 0.0085 in average cured ply thickness, p. 24). This record uses the measured RTD column only.",
    "Warp and fill compression were measured directly on [0]12 and [90]12 fabric specimens by ASTM D6641M-09, so the compressive strengths are measured means. The report prints compressive Poisson ratios ν12c and ν21c; both are recorded.",
    "The composite density printed on the individual test summaries (1.207 g/cm³ on every page) is not entered: it is inconsistent with the fiber volume and resin content printed beside it and could not be verified. UNVERIFIED. Fiber volume and resin content from the warp-tension panels are recorded.",
    "Table 3-1 of the statistical report (p. 32) gives the NCAMP recommended B-basis values; those limits are not replaced by the means shown here. NCAMP states the data is not applicable when the material is not procured to NMS 688/2 (p. 9).",
  ],
  properties: ncampProperties([
    ["E1t", "Warp tensile modulus", 8.66, "Msi", 28, "ASTM D3039M-08", "[0]12; 3 lots", "Warp", "Measured mean"],
    ["E2t", "Fill tensile modulus", 8.58, "Msi", 29, "ASTM D3039M-08", "[90]12; 3 lots", "Fill", "Measured mean"],
    ["nu12", "Poisson ratio · tension", .040, "—", 28, "ASTM D3039M-08", "[0]12; 3 lots", "Warp–fill", "Measured mean"],
    ["G12", "In-plane shear modulus", .52, "Msi", 32, "ASTM D3518-94", "[45/-45]2S; 3 lots", "1–2 plane", "Measured mean"],
    ["E1c", "Warp compressive modulus", 8.02, "Msi", 30, "ASTM D6641M-09", "[0]12; 3 lots", "Warp", "Measured mean"],
    ["E2c", "Fill compressive modulus", 8.04, "Msi", 31, "ASTM D6641M-09", "[90]12; 3 lots", "Fill", "Measured mean"],
    ["nu12c", "Poisson ratio · compression", .051, "—", 26, "ASTM D6641M-09", "Table 2-1, measured RTD column; warp compression", "Warp–fill", "Measured mean"],
    ["nu21c", "Minor Poisson ratio · compression", .049, "—", 26, "ASTM D6641M-09", "Table 2-1, measured RTD column; fill compression", "Fill–warp", "Measured mean"],
    ["F1t", "Warp tensile strength", 126.33, "ksi", 28, "ASTM D3039M-08", "[0]12; 3 lots", "Warp", "Measured mean"],
    ["F2t", "Fill tensile strength", 121.76, "ksi", 29, "ASTM D3039M-08", "[90]12; 3 lots", "Fill", "Measured mean"],
    ["F1c", "Warp compressive strength", 100.14, "ksi", 30, "ASTM D6641M-09", "[0]12; 3 lots; measured directly on fabric specimens", "Warp", "Measured mean"],
    ["F2c", "Fill compressive strength", 89.96, "ksi", 31, "ASTM D6641M-09", "[90]12; 3 lots; measured directly on fabric specimens", "Fill", "Measured mean"],
    ["F12-offset", "Shear strength · 0.2% offset", 5.72, "ksi", 32, "ASTM D3518-94", "[45/-45]2S; 3 lots", "1–2 plane", "Measured mean"],
    ["F12-5pct", "Shear strength · at 5% strain", 9.87, "ksi", 32, "ASTM D3518-94", "[45/-45]2S; 3 lots", "1–2 plane", "Measured mean"],
    ["SBS", "Short-beam strength", 9.36, "ksi", 26, "ASTM D2344", "Table 2-1, measured RTD column", "Interlaminar test", "Measured mean"],
    ["tply", "Nominal cured ply thickness", .0085, "in", 24, "Normalization CPT, §1.5.8", "Average cured ply thickness used as the nominal value for normalization", "Through thickness", "Reported nominal"],
    ["Vf-LT", "Fiber volume · warp-tension panels", 49.29, "%", 28, "Warp-tension panel summary", "Warp-tension panel summary; volume basis", "Bulk", "Reported panel property"],
    ["resin-LT", "Resin content · warp-tension panels", 41.16, "%", 28, "Warp-tension panel summary", "Warp-tension panel summary; mass basis", "Bulk", "Reported panel property"],
    ["Tg-dry", "Glass transition temperature · dry", 259.26, "°F", 26, "DMA, SACMA SRM 18R-94", "Dry; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 198.49, "°F", 26, "DMA, SACMA SRM 18R-94", "Wet; lamina summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], rtd70),
};

// MIL-HDBK-17-2F (2002, canceled 2013) historical records. Public domain (ADR-0018). The
// handbook prints a data class for every value (Table 1.4.2(c)); the class is kept as the basis.
// Pages are PDF pages of the ASSIST copy; printed pages are the handbook's own (for example 4-230).
type HandbookRow = [key: string, label: string, value: number, unit: string, pdfPage: number, printed: string, method: string, detail: string, direction: string, basis: string];
const handbookProperties = (rows: HandbookRow[], environment: string): CitedProperty[] =>
  rows.map(([key, label, value, unit, sourcePage, printed, method, detail, direction, basis]) => ({
    key, label, value, unit, sourcePage, method, direction, basis, symbol: ncampSymbols[key.split("-")[0]] || key,
    conditions: `${environment}; ${detail}.`, sourceValue: value, sourceUnit: unit,
    evidence: `${label}; handbook page ${printed} (PDF page ${sourcePage}); ${detail}`,
  }));
const handbookAmbient = "72°F (22.2°C), ambient moisture (handbook condition A)";
const handbookCaveat = "Historical data from a canceled handbook (MIL-HDBK-17-2F, canceled 26 March 2013 and superseded by CMH-17); the data classes printed by the handbook are kept as the basis of every value.";

const t650976Conditions = `${handbookAmbient}. ${handbookCaveat} ICI Fiberite T650-35 12k / 976 unidirectional tape prepreg, Amoco T650-35 fiber; autoclave cure 350°F, 90 min, 95 psi; tested 1993 to 1996.`;
export const handbookT650976: CitedMaterial = {
  id: "t650-35-976", name: "T650-35 / 976", family: "Carbon / epoxy", architecture: "Unidirectional · autoclave cured · historical handbook data",
  datasetId: "mil-hdbk-17-2f-t650-35-976-2002-ambient-measured-v1", dataset: "MIL-HDBK-17-2F §4.2.29 · historical handbook data",
  conditions: t650976Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1",
  application: "Historical reference values for T650-35 / 976 tape at room temperature. Not an elastic input set: the handbook prints no Poisson ratio and no longitudinal compression for this material, and the transverse moduli are screening data. Strengths are means with the handbook's data class; B-basis values exist only for the B30 and B18 classes and stay in the handbook.",
  source: references["milhdbk-17-2f"],
  supportingReferences: [references["milhdbk-17-2f-notice-1"]],
  recordDetails: [
    "MIL-HDBK-17-2F, Volume 2, Section 4.2.29 (handbook pages 4-228 to 4-233). The handbook was canceled by Notice 1 on 26 March 2013; the notice names SAE R-423 (CMH-17 Volume 2, 2012) as a possible replacement. These values are shown as historical data and are not in the current CMH-17 public record this library holds.",
    "Rights: the handbook cover carries Distribution Statement A and the document is a Department of Defense handbook; the official copy is on DLA ASSIST (ident 53882). Public domain under ADR-0018. The ASSIST download stamps every page with its download time, so the recorded fingerprint identifies this dated copy; page numbering matches the research copy.",
    "Condition A is ambient moisture at 72°F; the handbook does not state a drying procedure. Longitudinal tension is normalized to 60% fiber volume (0.0052 in cured ply thickness); this record uses the measured column. Transverse and shear tests are not normalized.",
    "Data classes (handbook Table 1.4.2(c)): B30 means a B-basis value from at least 30 specimens in 5 batches; B18 from 18 specimens in 3 batches; Mean, Interim and Screening carry no basis value. The class of each value is its basis here.",
    "No Poisson ratio, longitudinal compression or strain to failure is printed for this material, so the record has no elastic input set. Physical values are the handbook's nominal column (page 4-229).",
  ],
  properties: handbookProperties([
    ["E1t", "Longitudinal tensile modulus", 22.5, "Msi", 301, "4-230", "ASTM D3039-89", "Table 4.2.29(a); [0]9; 32 specimens, 5 batches; measured (normalized 22.0)", "Fiber direction", "Mean"],
    ["E2t", "Transverse tensile modulus", 1.30, "Msi", 302, "4-231", "ASTM D3039-89", "Table 4.2.29(b); [90]24; 9 specimens, 3 batches; not normalized", "Transverse direction", "Screening"],
    ["G12", "In-plane shear modulus", .745, "Msi", 304, "4-233", "ASTM D3518-82", "Table 4.2.29(d); [+45/-45]4s; 30 specimens, 5 batches; not normalized", "1–2 plane", "Mean"],
    ["E2c", "Transverse compressive modulus", 1.38, "Msi", 303, "4-232", "ASTM D3410-87", "Table 4.2.29(c); [90]22; 9 specimens, 3 batches; not normalized", "Transverse direction", "Screening"],
    ["F1t", "Longitudinal tensile strength", 236, "ksi", 301, "4-230", "ASTM D3039-89", "Table 4.2.29(a); [0]9; 32 specimens, 5 batches; measured (normalized 231); B-value 200 measured", "Fiber direction", "B30"],
    ["F2t", "Transverse tensile strength", 5.71, "ksi", 302, "4-231", "ASTM D3039-89", "Table 4.2.29(b); [90]24; 18 specimens, 3 batches; B-value 4.42", "Transverse direction", "B18"],
    ["F2c", "Transverse compressive strength", 33.6, "ksi", 303, "4-232", "ASTM D3410-87", "Table 4.2.29(c); [90]22; 18 specimens, 3 batches; B-value 28.1", "Transverse direction", "B18"],
    ["F12", "In-plane shear strength", 14.9, "ksi", 304, "4-233", "ASTM D3518-82", "Table 4.2.29(d); [+45/-45]4s; 30 specimens, 5 batches; B-value 8.57", "1–2 plane", "B30"],
    ["tply", "Nominal cured ply thickness", .0052, "in", 300, "4-229", "Physical property summary, nominal column", "Nominal value; as submitted 0.0049 to 0.0058 in", "Through thickness", "Reported nominal"],
    ["Vf-nominal", "Fiber volume · nominal", 61, "%", 300, "4-229", "Physical property summary, nominal column", "Nominal value; as submitted 55.3 to 65.3%", "Bulk", "Reported nominal"],
    ["Tg-dry", "Glass transition temperature · dry", 486, "°F", 299, "4-228", "DMA E′", "Section 4.2.29 summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
    ["Tg-wet", "Glass transition temperature · wet", 410, "°F", 299, "4-228", "DMA E′", "Section 4.2.29 summary. Tg is not a maximum service temperature", "Bulk", "Reported transition temperature"],
  ], handbookAmbient),
};

const ea9396Conditions = `${handbookAmbient}. ${handbookCaveat} E-glass 7781 8-harness satin fabric, wet lay-up with Dexter-Hysol EA 9396 epoxy; vacuum bag cure 200°F, 45 min, 25 in Hg; tested 1988 to 1991. The handbook marks every table of this material "all documentation presently required were not supplied".`;
export const handbookEA9396: CitedMaterial = {
  id: "7781-ea9396", name: "7781 / EA 9396", family: "Glass / epoxy", architecture: "Woven · eight-harness satin · wet lay-up · historical handbook data",
  datasetId: "mil-hdbk-17-2f-7781-ea9396-2002-ambient-measured-v1", dataset: "MIL-HDBK-17-2F §6.2.4 · historical handbook data",
  conditions: ea9396Conditions, reviewedOn: "2026-10-10", recordRevision: "2026-10-10.1", elasticInputs,
  application: "Historical reference values for a wet lay-up E-glass / EA 9396 fabric at room temperature, using the warp and fill tensile moduli, G12 and ν12 as an elastic set with the handbook's Interim and Screening classes. Strengths are Interim-class means with no basis values. A different material and process from the 7781 / E-765 prepreg record.",
  source: references["milhdbk-17-2f"],
  supportingReferences: [references["milhdbk-17-2f-notice-1"]],
  recordDetails: [
    "MIL-HDBK-17-2F, Volume 2, Section 6.2.4 (handbook pages 6-36 to 6-44). The handbook was canceled by Notice 1 on 26 March 2013; these values are shown as historical data. Warp is axis 1 and fill is axis 2.",
    "Rights: Distribution Statement A on the cover; Department of Defense handbook; official copy on DLA ASSIST (ident 53882). Public domain under ADR-0018. The ASSIST download stamps every page with its download time, so the recorded fingerprint identifies this dated copy.",
    "Every table of this material carries the handbook's warning that required documentation was not supplied, and the tension tables note high batch variability. All values are Interim or Screening class; no B-basis values are printed. Void content is 3.7 to 5.4%.",
    "Tension and compression are normalized to 50% fiber volume (0.0085 in cured ply thickness); this record uses the measured column. Shear is not normalized. Condition A is ambient moisture at 72°F with no stated drying.",
    "No glass transition temperature is printed (the handbook refers to a data analysis note). Physical values are the handbook's nominal column (page 6-37).",
  ],
  properties: handbookProperties([
    ["E1t", "Warp tensile modulus", 3.62, "Msi", 431, "6-38", "ASTM D3039-76", "Table 6.2.4(a); [0f]8; 15 specimens, 3 batches; measured (normalized 3.39)", "Warp", "Interim"],
    ["E2t", "Fill tensile modulus", 3.67, "Msi", 432, "6-39", "ASTM D3039-76", "Table 6.2.4(b); [0f]8 fill; 15 specimens, 3 batches; measured (normalized 3.41)", "Fill", "Interim"],
    ["nu12", "Poisson ratio · tension", .115, "—", 431, "6-38", "ASTM D3039-76", "Table 6.2.4(a); 6 specimens, 3 batches", "Warp–fill", "Screening"],
    ["nu21", "Minor Poisson ratio · tension", .127, "—", 432, "6-39", "ASTM D3039-76", "Table 6.2.4(b); 6 specimens, 3 batches", "Fill–warp", "Screening"],
    ["G12", "In-plane shear modulus", .758, "Msi", 437, "6-44", "ASTM D3518-76", "Table 6.2.4(g); [±45f]s; 22 specimens, 3 batches; not normalized", "1–2 plane", "Interim"],
    ["E1c", "Warp compressive modulus", 3.68, "Msi", 434, "6-41", "ASTM D3410B-87", "Table 6.2.4(d); [0f]16; 15 specimens, 3 batches; measured (normalized 3.45)", "Warp", "Interim"],
    ["E2c", "Fill compressive modulus", 3.66, "Msi", 435, "6-42", "ASTM D3410B-87", "Table 6.2.4(e); [0f]16 fill; 15 specimens, 3 batches; measured (normalized 3.37)", "Fill", "Interim"],
    ["F1t", "Warp tensile strength", 51.8, "ksi", 431, "6-38", "ASTM D3039-76", "Table 6.2.4(a); [0f]8; 15 specimens, 3 batches; measured (normalized 48.3); most failures under the tabs", "Warp", "Interim"],
    ["F2t", "Fill tensile strength", 54.3, "ksi", 432, "6-39", "ASTM D3039-76", "Table 6.2.4(b); [0f]8 fill; 15 specimens, 3 batches; measured (normalized 50.5)", "Fill", "Interim"],
    ["F1c", "Warp compressive strength", 49.6, "ksi", 434, "6-41", "ASTM D3410B-87", "Table 6.2.4(d); [0f]16; 15 specimens, 3 batches; measured (normalized 46.4)", "Warp", "Interim"],
    ["F2c", "Fill compressive strength", 40.8, "ksi", 435, "6-42", "ASTM D3410B-87", "Table 6.2.4(e); [0f]16 fill; 15 specimens, 3 batches; measured (normalized 37.7)", "Fill", "Interim"],
    ["F12", "In-plane shear strength", 11.5, "ksi", 437, "6-44", "ASTM D3518-76", "Table 6.2.4(g); [±45f]s; 23 specimens, 3 batches; not normalized", "1–2 plane", "Interim"],
    ["tply", "Nominal cured ply thickness", .0085, "in", 430, "6-37", "Physical property summary, nominal column", "Nominal value; as submitted 0.0083 to 0.0087 in", "Through thickness", "Reported nominal"],
    ["Vf-nominal", "Fiber volume · nominal", 54, "%", 430, "6-37", "Physical property summary, nominal column (ASTM D2584)", "Nominal value; as submitted 51.2 to 56.9%", "Bulk", "Reported nominal"],
    ["density-nominal", "Composite density · nominal", 1.91, "g/cm³", 430, "6-37", "Physical property summary, nominal column (ASTM D792)", "Nominal value assuming 0% void content; as submitted 1.88 to 1.96 g/cm³", "Bulk", "Reported nominal"],
  ], handbookAmbient),
};
