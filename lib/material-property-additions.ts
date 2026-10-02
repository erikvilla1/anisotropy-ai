import type { CitedProperty } from "./curated-materials";

type Row = [key: string, label: string, value: number, unit: string, page: number, method: string, conditions: string, direction: string, valueEnd?: number];
function rows(data: Row[], basis: string): CitedProperty[] {
  const symbols: Record<string, string> = { density: "ρ", Vf: "Vf", resin: "wr", void: "Vv", tply: "tply", Tg: "Tg", "cell": "Cell size", shear: "γ" };
  return data.map(([key, label, value, unit, sourcePage, method, conditions, direction, valueEnd]) => ({
    key, label, value, unit, sourcePage, method, conditions, direction, valueEnd,
    sourceValue: value, sourceUnit: unit, basis, symbol: symbols[key.split("-")[0]] || key,
    evidence: `${label}; original report p. ${sourcePage}; ${conditions}`,
  }));
}

// These are source-specific reported properties, never missing-value estimates.
export const carbonAdditions = rows([
  ["nu21c", "Minor Poisson ratio · compression", .029, "—", 30, "ASTM D6641/D6641M-01e1", "75°F, dry; transverse compression, TC. Table 2-1 identifies this as ν21c.", "2–1 directions"],
  ["ILT", "Interlaminar tensile strength · curved beam", 7.90, "ksi", 63, "ASTM D6415-99 E1", "75°F, dry; [0]22 curved-beam specimens, one prepreg lot. Test-specific interlaminar result.", "Through thickness"],
], "Measured mean").concat(rows([
  ["density-LT", "Density · longitudinal-tension panels", 1.59, "g/cm³", 32, "ASTM D792-00; physical-test matrix p. 23", "Longitudinal-tension panel summary; not a universal density for every tested panel.", "Bulk"],
  ["Vf-LT", "Fiber volume · longitudinal-tension panels", 59.56, "%", 32, "ASTM D3171-06; physical-test matrix p. 23", "Longitudinal-tension panel summary; volume basis.", "Bulk"],
  ["resin-LT", "Resin content · longitudinal-tension panels", 33.28, "%", 32, "ASTM D3171-06; physical-test matrix p. 23", "Longitudinal-tension panel summary; mass basis.", "Bulk"],
], "Reported panel property"), rows([
  ["Tg-dry", "Glass transition temperature · dry", 400.27, "°F", 30, "DMA, SACMA SRM 18R-94", "Dry; lamina summary. Tg is not a maximum service temperature.", "Bulk"],
  ["Tg-wet", "Glass transition temperature · wet", 321.04, "°F", 30, "DMA, SACMA SRM 18R-94", "Wet; lamina summary. Tg is not a maximum service temperature.", "Bulk"],
], "Reported transition temperature"));

export const legacyGlassAdditions = rows([
  ["density-WT", "Density range · warp-tension panels", 1.81, "g/cm³", 29, "Reported panel characterization, §3.1.2.1", "Warp-tension panels; reported range, not a mean or design allowable.", "Bulk", 1.86],
  ["Vf-WT", "Fiber volume range · warp-tension panels", 44, "%", 29, "Reported panel characterization, §3.1.2.1", "Warp-tension panels; volume basis.", "Bulk", 49],
  ["resin-WT", "Resin content range · warp-tension panels", 33, "%", 29, "Reported panel characterization, §3.1.2.1", "Warp-tension panels; mass basis.", "Bulk", 35],
  ["void-WT", "Void content range · warp-tension panels", 1.1, "%", 29, "Reported panel characterization, §3.1.2.1", "Warp-tension panel summary; retain the published range, not an acceptance limit.", "Bulk", 9],
  ["tply-WT", "Ply thickness range · warp-tension panels", .0091, "in", 29, "Reported panel characterization, §3.1.2.1", "Actual panel range; distinct from 0.0098 in normalization thickness.", "Through thickness", .0101],
], "Reported panel range").concat(rows([
  ["Tg-dry", "Glass transition temperature · dry", 335.2, "°F", 27, "DMA, SRM 18-94", "Dry; qualification summary. Not a maximum service temperature.", "Bulk"],
  ["Tg-wet", "Glass transition temperature · wet", 258.2, "°F", 27, "DMA, SRM 18-94", "Wet; qualification summary. Not a maximum service temperature.", "Bulk"],
  ["Tg-wet45", "Glass transition temperature · 45-day wet", 259.9, "°F", 27, "DMA, SRM 18-94", "45-day wet conditioning; qualification summary.", "Bulk"],
], "Reported transition temperature"));

export const modernGlassAdditions = rows([
  ["density-WT", "Density · warp-tension panels", 1.869, "g/cm³", 18, "Reported physical characterization, §2.2.1", "Warp-tension panel summary; not a universal value for all panels.", "Bulk"],
  ["Vf-WT", "Fiber volume · warp-tension panels", 50.84, "%", 18, "Reported physical characterization, §2.2.1", "Warp-tension panel summary; volume basis.", "Bulk"],
  ["resin-WT", "Resin content · warp-tension panels", 30.98, "%", 18, "Reported physical characterization, §2.2.1", "Warp-tension panel summary; mass basis, distinct from nominal prepreg resin content.", "Bulk"],
], "Reported panel property").concat(rows([
  ["Tg-dry", "Glass transition temperature · dry", 330.6, "°F", 17, "SACMA SRM 18R-94", "Dry; Table 2-1 summary. Not a maximum service temperature.", "Bulk"],
  ["Tg-wet", "Glass transition temperature · wet", 265.9, "°F", 17, "SACMA SRM 18R-94", "Wet; Table 2-1 summary. Not a maximum service temperature.", "Bulk"],
], "Reported transition temperature"));

// Pinned to the exact reviewed supplier PDFs. A different source fingerprint
// must undergo a new review before these supplemental rows can be carried over.
export const supplierAdditions: Record<string, CitedProperty[]> = {
  "divinycell-h45": rows([
    ["density", "Density", 48, "kg/m³", 1, "ISO 845", "+23°C; H45 column", "Bulk"],
    ["shear-strain", "Shear strain", 12, "%", 1, "ASTM C273", "+23°C; H45 column", "Shear"],
  ], "Nominal"),
  "divinycell-h250": rows([
    ["density", "Density", 250, "kg/m³", 1, "ISO 845", "+23°C; H250 column", "Bulk"],
    ["shear-strain", "Shear strain", 45, "%", 1, "ASTM C273", "+23°C; H250 column", "Shear"],
  ], "Nominal"),
  "nomex-aramid": rows([
    ["density", "Density", 1.8, "lb/ft³", 4, "Manufacturer grade designation", "HRH-10 / 1/8 / 1.8; nominal grade density", "Bulk"],
    ["cell-size", "Cell size", .125, "in", 4, "Manufacturer grade designation", "HRH-10 / 1/8 / 1.8; nominal hexagonal cell", "Cell"],
  ], "Nominal grade property"),
  m55j: rows([
    ["Vf-normalization", "Fiber volume · normalization basis", 60, "%", 3, "Manufacturer laminate table normalization", "121°C autoclave cure at 85 psi; normalization basis, not an independently measured fiber fraction.", "Bulk"],
  ], "Normalization basis"),
};
