import example from "../api/examples/zero-degree-tension.json";
import { findLibraryOption } from "./material-library-options";
import { settled } from "./studio-colors";
import { ANALYSIS_UNAVAILABLE, customerText } from "./studio-copy";

export const loadNames = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"] as const;
export type LoadName = (typeof loadNames)[number];
export type CalculatorForm = {
  // library: "" for manually typed values, otherwise a library option value (materialId::datasetId).
  material: { library: string; E1_GPa: string; E2_GPa: string; G12_GPa: string; nu12: string; source_reference: string };
  plies: { angle_deg: string; thickness_mm: string }[];
  loads: Record<LoadName, string>;
};
export type ExplicitMaterial = { E1_pa: number; E2_pa: number; G12_pa: number; nu12: number; source_reference: string };
export type LibraryMaterialRef = { library_id: string; dataset_id: string };
export type MaterialProvenance = {
  material_id: string; name: string; dataset_id: string; dataset: string; record_revision: string | null; rights: string; citation: string;
  E1_pa: number; E2_pa: number; G12_pa: number; nu12: number; ply_thickness_m: number | null; not_provided: string[];
  values: { role: string; key: string; value: number; unit: string; source_value: number; source_unit: string; basis: string; page: number; printed_page: number | null; reference_url: string }[];
  /** The record's density and fiber volume fraction (ADR-0059); null when the record states none. */
  density_kg_per_m3?: number | null;
  fiber_volume_fraction?: number | null;
};
/** The stack described before any load, as the engine reports it (ADR-0059). */
export type LaminateSummary = {
  ply_count: number; total_thickness_m: number; symmetric: boolean; antisymmetric: boolean; balanced: boolean;
  kind: "unidirectional" | "cross-ply" | "angle-ply" | "quasi-isotropic" | "general";
  coupling: { extension_shear: boolean; extension_bending: boolean; bending_twisting: boolean };
  relative_tolerance: number; areal_mass_kg_per_m2: number | null; areal_mass_missing: string | null;
};
export type FailureCriterion = {
  criterion: "max_stress" | "max_strain" | "tsai_hill" | "tsai_wu"; strength_ratio: number | null; ply: number; angle_deg: number;
  face: "bottom" | "top"; z_m: number; mode: string; failure_loads: Record<LoadName, number>;
};
/** First-ply failure under the request's loads by every criterion the inputs support (ADR-0059, ADR-0021). */
export type FirstPlyFailure = {
  evaluated: boolean; reason: string | null; criteria: FailureCriterion[]; not_computed: { criterion: string; reason: string }[];
};
export type AnalysisRequest = {
  unit_system: "SI_BASE";
  material: ExplicitMaterial | LibraryMaterialRef;
  plies: { angle_deg: number; thickness_m: number }[];
  loads: Record<LoadName, number>;
};
export type AnalysisResult = {
  /** The run record's id (ADR-0026); null when the service runs with recording switched off. */
  run_id?: string | null;
  engine_version: string;
  inputs: AnalysisRequest;
  A_N_per_m: number[][];
  B_N: number[][];
  D_N_m: number[][];
  midplane_strain: number[];
  curvature_per_m: number[];
  material_provenance?: MaterialProvenance | null;
  summary?: LaminateSummary | null;
  first_ply_failure?: FirstPlyFailure | null;
};
export type FieldErrors = Record<string, string>;

/** The library dataset the calculator's example uses: AS4 / 3501-6, as the material library cites it. */
export const EXAMPLE_LIBRARY = "as4-3501::daniel-ishai-2006-as4-3501-v2";

/** A library option's citation as the form shows it: the source and its page, without the dataset's id and record revision, which
 * the API's answer still carries. */
export const shownCitation = (citation: string): string => citation.replace(/ · dataset \S+ \(record [^)]*\)/, "");

/** The example: AS4 / 3501-6 from the material library, its cited values as the select shows them (the request sends the dataset
 * reference), under the API example's ply and uniaxial load, converted to the form's units. */
export function exampleForm(): CalculatorForm {
  const option = findLibraryOption(EXAMPLE_LIBRARY)!;
  return {
    material: {
      library: option.value, E1_GPa: option.E1_GPa, E2_GPa: option.E2_GPa, G12_GPa: option.G12_GPa, nu12: option.nu12,
      source_reference: shownCitation(option.citation),
    },
    plies: example.plies.map((ply) => ({ angle_deg: String(ply.angle_deg), thickness_mm: option.thickness_mm ?? String(ply.thickness_m * 1e3) })),
    loads: Object.fromEntries(loadNames.map((name) => [name, String(example.loads[name])])) as Record<LoadName, string>,
  };
}

/** A, B and D as the page shows them, at the stack summary's tolerance (ADR-0059): B is zero when the stack has no extension–bending
 * coupling, A16 and A26 when it has no extension–shear coupling, and any other entry below a billionth of its matrix's largest is roundoff. */
export function shownMatrices(result: Pick<AnalysisResult, "A_N_per_m" | "B_N" | "D_N_m" | "summary">): { A: number[][]; B: number[][]; D: number[][] } {
  const coupling = result.summary?.coupling;
  const clean = (rows: number[][]) => { const flat = settled(rows.flat()); return rows.map((row, i) => flat.slice(3 * i, 3 * i + 3)); };
  const A = clean(result.A_N_per_m).map((row, i) => row.map((v, j) => (coupling && !coupling.extension_shear && (i === 2) !== (j === 2) ? 0 : v)));
  const B = coupling && !coupling.extension_bending ? result.B_N.map((row) => row.map(() => 0)) : clean(result.B_N);
  return { A, B, D: clean(result.D_N_m) };
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
  const library = form.material.library ? findLibraryOption(form.material.library) : undefined;
  if (form.material.library && !library) errors["material.library"] = "Choose a library material or enter values manually.";
  const source = form.material.source_reference.trim();
  if (!library && !source) errors["material.source_reference"] = "Enter the source of these material values.";
  if (!form.plies.length) errors.plies = "Add at least one ply.";
  // A library choice sends the dataset reference; the engine resolves and cites it (ADR-0020).
  const material: AnalysisRequest["material"] = library
    ? { library_id: library.materialId, dataset_id: library.datasetId }
    : {
      E1_pa: number(form.material.E1_GPa, "material.E1_GPa", 1e9, true),
      E2_pa: number(form.material.E2_GPa, "material.E2_GPa", 1e9, true),
      G12_pa: number(form.material.G12_GPa, "material.G12_GPa", 1e9, true),
      nu12: number(form.material.nu12, "material.nu12"),
      source_reference: source,
    };
  const request: AnalysisRequest = {
    unit_system: "SI_BASE",
    material,
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
      .replace(/^material\.(explicit|library)(?=\.|$)/, "material") // discriminated-union tag
      .replace(/^material\.(E1|E2|G12)_pa$/, "material.$1_GPa")
      .replace(/^material\.(library_id|dataset_id)$/, "material.library")
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
    || !vector(payload.midplane_strain) || !vector(payload.curvature_per_m) || !sameInputs
    || !validSummary(payload.summary) || !validFailure(payload.first_ply_failure)) {
    throw new CalculationError(UNEXPECTED_RESULT);
  }
  return payload as AnalysisResult;
}

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const finiteOrNull = (v: unknown) => v === null || finite(v);
const bool = (v: unknown): v is boolean => typeof v === "boolean";
const KINDS = ["unidirectional", "cross-ply", "angle-ply", "quasi-isotropic", "general"];
const CRITERIA = ["max_stress", "max_strain", "tsai_hill", "tsai_wu"];

/** The stack's description (ADR-0059) is optional in an older service's answer; when present it must be whole. */
export function validSummary(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (!isObject(value) || !isObject(value.coupling)) return false;
  const c = value.coupling;
  return finite(value.ply_count) && finite(value.total_thickness_m) && bool(value.symmetric) && bool(value.antisymmetric)
    && bool(value.balanced) && typeof value.kind === "string" && KINDS.includes(value.kind) && finite(value.relative_tolerance)
    && finiteOrNull(value.areal_mass_kg_per_m2) && (value.areal_mass_missing === null || typeof value.areal_mass_missing === "string")
    && bool(c.extension_shear) && bool(c.extension_bending) && bool(c.bending_twisting);
}

export function validFailure(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (!isObject(value) || !bool(value.evaluated) || !(value.reason === null || typeof value.reason === "string")) return false;
  if (!Array.isArray(value.criteria) || !Array.isArray(value.not_computed)) return false;
  const validCriterion = (item: unknown) => {
    if (!isObject(item)) return false;
    const loads = item.failure_loads;
    return typeof item.criterion === "string" && CRITERIA.includes(item.criterion) && finiteOrNull(item.strength_ratio) && finite(item.ply)
      && finite(item.angle_deg) && (item.face === "bottom" || item.face === "top") && finite(item.z_m) && typeof item.mode === "string"
      && isObject(loads) && loadNames.every((name) => finite(loads[name]));
  };
  return value.criteria.every(validCriterion)
    && value.not_computed.every((item) => isObject(item) && typeof item.criterion === "string" && typeof item.reason === "string");
}

const UNEXPECTED_RESULT = "The analysis returned an unexpected result. Try again; if it happens again, contact us.";
const NOT_STARTED = "The analysis could not start. Try again; if it fails again, contact us.";

/** Send one explicit request; errors never fall back to example or locally computed results. An outage (no answer, or a 5xx) says
 * the analysis is unavailable and the inputs are kept; only a refusal of the inputs (422) asks for them to be checked; any other
 * refusal (signed out, a limit reached) gives the API's words when they can be shown, or says the analysis could not start. */
export async function requestAnalysis(baseUrl: string, request: AnalysisRequest, signal: AbortSignal): Promise<AnalysisResult> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl.replace(/\/+$/, "")}/v1/laminates/response`, {
      // The actor header names this client in the run record (ADR-0026).
      method: "POST", headers: { "Content-Type": "application/json", "X-Anisotropy-Actor": "calculator" },
      // Same-origin credentials carry the Access sign-in cookie to the hosted /api and nothing to another origin (ADR-0056).
      body: JSON.stringify(request), signal, credentials: "same-origin", cache: "no-store",
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new CalculationError(ANALYSIS_UNAVAILABLE);
  }
  let payload: unknown;
  try { payload = await response.json(); }
  catch { throw new CalculationError(response.ok ? UNEXPECTED_RESULT : response.status >= 500 ? ANALYSIS_UNAVAILABLE : NOT_STARTED); }
  if (!response.ok) {
    if (response.status >= 500) throw new CalculationError(ANALYSIS_UNAVAILABLE);
    const said = isObject(payload) && typeof payload.detail === "string" ? customerText(payload.detail) : null;
    if (response.status !== 422) throw new CalculationError(said ?? NOT_STARTED);
    throw new CalculationError(said ?? "Review the highlighted inputs and try again.", apiFieldErrors(payload));
  }
  return readAnalysisResult(payload, request);
}
