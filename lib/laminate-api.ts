import example from "../api/examples/zero-degree-tension.json";

export const loadNames = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"] as const;
export type LoadName = (typeof loadNames)[number];
export type CalculatorForm = {
  material: { E1_GPa: string; E2_GPa: string; G12_GPa: string; nu12: string; source_reference: string };
  plies: { angle_deg: string; thickness_mm: string }[];
  loads: Record<LoadName, string>;
};
export type AnalysisRequest = {
  unit_system: "SI_BASE";
  material: { E1_pa: number; E2_pa: number; G12_pa: number; nu12: number; source_reference: string };
  plies: { angle_deg: number; thickness_m: number }[];
  loads: Record<LoadName, number>;
};
export type AnalysisResult = {
  engine_version: string;
  inputs: AnalysisRequest;
  A_N_per_m: number[][];
  B_N: number[][];
  D_N_m: number[][];
  midplane_strain: number[];
  curvature_per_m: number[];
};
export type FieldErrors = Record<string, string>;

/** Reuse the cited API example; only convert its input units for the form. */
export function exampleForm(): CalculatorForm {
  return {
    material: {
      E1_GPa: String(example.material.E1_pa / 1e9),
      E2_GPa: String(example.material.E2_pa / 1e9),
      G12_GPa: String(example.material.G12_pa / 1e9),
      nu12: String(example.material.nu12),
      source_reference: example.material.source_reference,
    },
    plies: example.plies.map((ply) => ({ angle_deg: String(ply.angle_deg), thickness_mm: String(ply.thickness_m * 1e3) })),
    loads: Object.fromEntries(loadNames.map((name) => [name, String(example.loads[name])])) as Record<LoadName, string>,
  };
}

/** Preserve blanks as errors. Convert GPa/mm at the input boundary; perform no laminate math. */
export function buildAnalysisRequest(form: CalculatorForm): { request: AnalysisRequest; errors?: never } | { request?: never; errors: FieldErrors } {
  const errors: FieldErrors = {};
  function number(text: string, field: string, scale = 1, positive = false): number {
    const value = text.trim();
    const converted = Number(value) * scale;
    if (!value) errors[field] = "Enter a value; use 0 explicitly when appropriate.";
    else if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value) || !Number.isFinite(converted)) errors[field] = "Enter a finite number.";
    else if (positive && converted <= 0) errors[field] = "Enter a value greater than zero.";
    return converted;
  }
  const source = form.material.source_reference.trim();
  if (!source) errors["material.source_reference"] = "Enter the source of these material values.";
  if (!form.plies.length) errors.plies = "Add at least one ply.";
  const request: AnalysisRequest = {
    unit_system: "SI_BASE",
    material: {
      E1_pa: number(form.material.E1_GPa, "material.E1_GPa", 1e9, true),
      E2_pa: number(form.material.E2_GPa, "material.E2_GPa", 1e9, true),
      G12_pa: number(form.material.G12_GPa, "material.G12_GPa", 1e9, true),
      nu12: number(form.material.nu12, "material.nu12"),
      source_reference: source,
    },
    plies: form.plies.map((ply, index) => ({
      angle_deg: number(ply.angle_deg, `plies.${index}.angle_deg`),
      thickness_m: number(ply.thickness_mm, `plies.${index}.thickness_mm`, 1e-3, true),
    })),
    loads: Object.fromEntries(loadNames.map((name) => [name, number(form.loads[name], `loads.${name}`)])) as Record<LoadName, number>,
  };
  return Object.keys(errors).length ? { errors } : { request };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Translate API error locations back to the form's display-unit field names. */
export function apiFieldErrors(payload: unknown): FieldErrors {
  const fields: FieldErrors = {};
  if (!isObject(payload) || !Array.isArray(payload.detail)) return fields;
  for (const error of payload.detail) {
    if (!isObject(error) || !Array.isArray(error.loc) || typeof error.msg !== "string") continue;
    const key = error.loc.filter((part) => part !== "body").join(".")
      .replace(/^material\.(E1|E2|G12)_pa$/, "material.$1_GPa")
      .replace(/^(plies\.\d+)\.thickness_m$/, "$1.thickness_mm");
    fields[key] = error.msg;
  }
  return fields;
}

export class CalculationError extends Error {
  constructor(message: string, public fields: FieldErrors = {}) { super(message); }
}

/** Validate the values we display and the echoed request; TypeScript alone cannot check network JSON. */
export function readAnalysisResult(payload: unknown, request: AnalysisRequest): AnalysisResult {
  const vector = (v: unknown): v is number[] => Array.isArray(v) && v.length === 3 && v.every((n) => typeof n === "number" && Number.isFinite(n));
  const matrix = (m: unknown) => Array.isArray(m) && m.length === 3 && m.every(vector);
  const inputs = isObject(payload) && isObject(payload.inputs) ? payload.inputs : null;
  const sameFields = (value: unknown, expected: Record<string, unknown>) => isObject(value) && Object.entries(expected).every(([key, v]) => value[key] === v);
  const sameInputs = inputs?.unit_system === request.unit_system
    && sameFields(inputs.material, request.material) && sameFields(inputs.loads, request.loads)
    && Array.isArray(inputs.plies) && inputs.plies.length === request.plies.length
    && inputs.plies.every((ply, i) => sameFields(ply, request.plies[i]));
  if (!isObject(payload) || typeof payload.engine_version !== "string" || !payload.engine_version.trim()
    || !matrix(payload.A_N_per_m) || !matrix(payload.B_N) || !matrix(payload.D_N_m)
    || !vector(payload.midplane_strain) || !vector(payload.curvature_per_m) || !sameInputs) {
    throw new CalculationError("The calculation service returned an unexpected result. Please try again.");
  }
  return payload as AnalysisResult;
}

/** Send one explicit request; errors never fall back to example or locally computed results. */
export async function requestAnalysis(baseUrl: string, request: AnalysisRequest, signal: AbortSignal): Promise<AnalysisResult> {
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/v1/laminates/response`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request), signal, credentials: "omit", cache: "no-store",
  });
  let payload: unknown;
  try { payload = await response.json(); }
  catch { throw new CalculationError("The calculation service returned an unreadable response. Please try again."); }
  if (!response.ok) {
    const message = response.status === 422 && isObject(payload) && typeof payload.detail === "string"
      ? payload.detail : response.status === 422 ? "Review the highlighted inputs and try again." : "The calculation service could not complete this request. Please try again.";
    throw new CalculationError(message, apiFieldErrors(payload));
  }
  return readAnalysisResult(payload, request);
}
