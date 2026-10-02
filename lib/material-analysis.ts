import { materials, materialSource, type Material, type Property } from "./materials";

export const schoolAudit = {
  title: "SE143AB · Appendix F: Material Properties", edition: "Version 2", published: "2026-02-01",
  checked: "2026-10-01", sha256: "d851b3cf31354b715853d906a2de9afaa4ecd288f599bdc91655a46930cf5dcf",
  method: "All six pages visually checked against the library; numerical transcription checked by PDF cell position. This verifies transcription, not experimental accuracy or qualification.",
};
export function schoolCitation(m: Material) {
  return { ...schoolAudit, url: `${materialSource}#page=${m.page}`, page: m.page, section: m.section, recordDate: m.basis,
    underlyingReference: m.id === "7781-e765"
      ? "Appendix cites Tomblin et al., AGATE-WP3.3-033051-105 (2001), p. 217. Original allowable table not independently verified; do not infer statistical basis for individual rows."
      : m.page <= 2 ? "Appendix cites Daniel and Ishai, Engineering Mechanics of Composite Materials, 2nd edition (2006), p. 380. Original book table not independently verified."
      : "No external property reference is identified for this table in the supplied appendix.",
    conditions: "Property-specific test methods, temperature, moisture conditioning, specimen counts and statistical basis are not specified in this appendix.",
  };
}

export function parseProperty(value: string): number | null {
  const cleaned = value.trim().replace(/,/g, "");
  return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(cleaned) && Number.isFinite(Number(cleaned)) ? Number(cleaned) : null;
}
export function propertyIssue(m: Material, p: Property): string | null {
  if (p.review) return p.review;
  if (["as4-3501", "agp370"].includes(m.id) && p.symbol.startsWith("β")) return "Moisture coefficients exactly repeat the thermal coefficients under different units. Confirm with the source owner before moisture analysis.";
  if (["divinycell-h45", "divinycell-h250", "baltek"].includes(m.id) && ["Fc,stable", "Fc,crush"].includes(p.symbol)) return "Core table uses honeycomb-style strength labels for foam/balsa. Applicability of this strength definition is unverified; use the manufacturer's specific compression definition.";
  const value = parseProperty(p.value);
  if (value === null) return /^(?:\s*|—|-|TBD)$/i.test(p.value) ? "Not provided" : "Range or non-scalar value; select an evidenced value before calculation.";
  if (/^[EGF]|^ρ$|^t/.test(p.symbol) && (p.symbol.match(/^F[123]C$/) ? value >= 0 : value <= 0)) return "Value has an unexpected sign or magnitude for this property.";
  return null;
}

// Factors derive from exact SI definitions: inch=0.0254 m; lb=0.45359237 kg;
// standard gravity=9.80665 m/s². Original numbers/signs are never overwritten.
export const PSI_MPA = 0.45359237 * 9.80665 / (0.0254 ** 2) / 1e6;
const conversions: Record<string, [number, string]> = {
  Msi: [PSI_MPA * 1000, "GPa"], ksi: [PSI_MPA * 1000, "MPa"], psi: [PSI_MPA, "MPa"],
  "lb/in³": [0.45359237 / 0.0254 ** 3, "kg/m³"], "lb/ft³": [0.45359237 / 0.3048 ** 3, "kg/m³"],
  in: [25.4, "mm"], "10⁻⁶/°F": [1.8, "10⁻⁶/K"], "10⁻⁶/%": [1, "10⁻⁶/%"], "%": [1, "%"], "—": [1, "1"],
};
export function siProperty(p: Property) {
  const value = parseProperty(p.value), conversion = conversions[p.unit];
  if (value === null || !conversion) return null;
  return { value: value * conversion[0], unit: conversion[1] };
}
export function formatNumber(value: number) { return Number(value.toPrecision(6)).toLocaleString("en-US", { maximumSignificantDigits: 6 }); }

export type AnalysisPurpose = "in-plane-elastic" | "laminate-elastic" | "strength-screening" | "mass" | "core-elastic";
export const analysisPurposes: Record<AnalysisPurpose, string> = {
  "in-plane-elastic": "In-plane lamina elasticity", "laminate-elastic": "Laminate stiffness inputs",
  "strength-screening": "In-plane strength screening inputs", mass: "Mass / density", "core-elastic": "Core compression & shear stiffness",
};
export function assessAnalysis(material: Material, purpose: AnalysisPurpose) {
  const core = material.family === "Sandwich cores", full = material.properties.some(p => p.symbol === "E11");
  const elastic = full ? ["E11", "E22", "G12", "ν12"] : ["EL", "ET", "GLT", "νLT"];
  const required = purpose === "mass" ? ["ρ"] : purpose === "core-elastic" ? ["Ec", "GL", "GW"] : purpose === "strength-screening" ? [...elastic, "F1T", "F1C", "F2T", "F2C", full ? "FS6" : "FS"] : purpose === "laminate-elastic" ? [...elastic, "tply"] : elastic;
  const problems: string[] = [];
  if ((core && !["mass", "core-elastic"].includes(purpose)) || (!core && purpose === "core-elastic")) problems.push("This analysis requires a different material model.");
  const inputs = required.map(symbol => material.properties.find(p => p.symbol === symbol));
  required.forEach((symbol, i) => { const p = inputs[i]; const issue = p ? propertyIssue(material, p) : "Not provided"; if (issue) problems.push(`${symbol}: ${issue}`); else if (p && !siProperty(p)) problems.push(`${symbol}: Unit conversion is not defined; review required.`); });
  if (!core && purpose !== "mass" && purpose !== "core-elastic" && problems.length === 0) {
    const [e1, e2, , nu] = elastic.map(s => parseProperty(material.properties.find(p => p.symbol === s)!.value)!);
    if (!(1 - nu * nu * e2 / e1 > 0)) problems.push("The in-plane elastic constants do not form a positive-definite compliance matrix.");
  }
  return { purpose, label: analysisPurposes[purpose], inputsAvailable: problems.length === 0, required, problems,
    use: "Preliminary analysis with documented source assumptions; input completeness is not validation of the physical material or solver." };
}

export function analysisPacket(id: string, purpose: AnalysisPurpose, acknowledgeLimitations: boolean) {
  const material = materials.find(m => m.id === id);
  if (!material) throw new Error("Unknown material");
  if (!Object.hasOwn(analysisPurposes, purpose)) throw new Error("Unknown analysis purpose");
  const assessment = assessAnalysis(material, purpose);
  if (!assessment.inputsAvailable) throw new Error(assessment.problems.join("\n"));
  if (acknowledgeLimitations !== true) throw new Error("Acknowledge source conditions and material applicability before exporting analysis inputs.");
  return { schemaVersion: 1, materialId: id, name: material.name, purpose, use: "preliminary-analysis", designAllowables: false,
    source: schoolCitation(material), process: material.process, assumptionsAcknowledged: true,
    limitations: ["User must establish applicability to their material and test conditions.", "No defaults, missing values, unverified corrections or mixed-source properties are included.", "The library supplies inputs; it does not validate a solver or approve a component."],
    properties: assessment.required.map(symbol => { const p = material.properties.find(p => p.symbol === symbol)!; const si = siProperty(p)!;
      const compressiveStrength = /^F[123]C$/.test(symbol);
      return { symbol, label: p.label, sourceValue: p.value, sourceUnit: p.unit, value: compressiveStrength ? Math.abs(si.value) : si.value, unit: si.unit,
        transformation: compressiveStrength ? "Converted to SI; negative source compression converted to positive strength magnitude" : "Converted to SI; source sign retained",
        sourcePage: material.page, basis: "As reported in appendix; statistical basis unverified" }; }),
  };
}
