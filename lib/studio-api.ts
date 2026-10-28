/**
 * The studio's calls to the API (ADR-0051, ADR-0050 amendment 1). Every answer's shape is checked at runtime before it is shown:
 * the browser draws what the fea package wrote and computes nothing (ADR-0001).
 */
import type { Checklist, StudioValues } from "./studio-form";

export const ACTOR = "studio";
export const POLL_MS = 2000;
export type JobState = "running" | "done" | "stopped" | "refused";
export type JobStatus = {
  job_id: string; state: JobState; actor: string; started_at: string; finished_at: string | null; coupon: string | null; attempt: string | null;
  message: string | null; stage: string | null; stages_done: string[]; stages: string[]; outputs: Record<string, string>; run_id: string | null;
  log_tail: string[];
};
export type CheckAnswer = { run_id: string | null; state: "ready" | "blocked"; designation: string | null; checklist: Checklist; preview: Preview | null };
export type Preview = {
  units: string; labels: Record<string, string>;
  coupon: { designation: string | null; title: string; kind: string; test: string; card: [string, string][]; layup: string };
  geometry: { length: number; width: number; tab_length: number; hole_diameter: number | null; thickness: number };
  mesh: { nodes: number[][]; quads: number[][]; node_sets: Record<string, number[]>; element_sets: Record<string, number[]>; order: number; mesher: string;
    node_count: number; element_count: number };
  held: { set: string; through: string | null; dofs: number[]; directions: string[]; nodes: number }[];
  loaded: { set: string; through: string | null; control: string; dof: number; direction: string; value: number; unit: string; nodes: number };
  plies: { index: number; angle: number; thickness: number; z_bottom: number; z_top: number; material: string }[];
  material: { name: string; source: string; rights: string; E1: number; E2: number; G12: number; nu12: number; G13: number; G23: number;
    strengths: Record<string, number> | null; f12_star: number | null; criteria: string[]; citation_lines: string[]; ply_thickness: number; plies: number };
  probes: { nodes: Record<string, { index: number; xy: number[] }>; elements: Record<string, { index: number; xy: number[] }> };
  quality?: { summary: QualitySummary; per_element: Record<string, number[]> };
};
export type QualitySummary = { elements: number; acceptable: boolean; measures: Record<string, { word: string; worst: number; element: number; threshold: number; warns: string; over: number }> };
export type Extreme = { value: number; element: number; label: string; ply: number; angle: number; xy: number[] };
export type FirstPlyFailure = { factor: number; index: number; element: number; label: string; ply: number; angle: number; mode: string; place: string;
  touches_grip: boolean; tied_plies: number[]; xy: number[] };
export type Fields = {
  units: string; labels: Record<string, string>; coupon: Partial<Preview["coupon"]>;
  mesh: { nodes: number[][]; quads: number[][]; node_labels: string[]; element_labels: string[]; node_sets: Record<string, number[]>;
    element_sets: Record<string, number[]>; node_count: number; element_count: number; plies: number; angles: number[] };
  nodal: { displacement: number[][]; magnitude: number[]; reaction: number[][];
    averages: { strain: (number | null)[][]; section_force: (number | null)[][]; ply_stress_12: (number | null)[][][]; ply_mises: (number | null)[][];
      failure_index: Record<string, (number | null)[]> }; averages_note: string };
  element: { strain: number[][]; section_force: number[][]; centroids: number[][];
    ply: { stress_12: number[][][]; stress_xy: number[][][]; strain_12: number[][][]; mises: number[][] };
    failure: Record<string, { ratio: (number | null)[][]; index: number[][]; mode: number[][]; worst_ply: number[]; element_index: number[] }>; modes: string[] };
  summary: { max_displacement: { value: number; node: number; label: string; xy: number[]; components: number[] };
    reaction: { set: string; value: number; sense: string }; applied: { control: string; value: number; unit: string };
    max_ply: Record<string, Extreme>; fpf: Record<string, FirstPlyFailure>; earliest: string | null; equilibrium_residual: number; free_residual: number };
  quality?: QualitySummary;
};
export type Explanation = { writer: string; facts: Record<string, unknown>; sentences: string[]; setup_sentences: string[] };
export type CouponSummary = { name: string; designation: string | null; kind: string; test: string; title: string; layup: string; status: string | null;
  accepted: string | null; attempts: number; category: string | null; problem?: string | null };

export class StudioError extends Error {
  constructor(message: string, public status?: number) { super(message); }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function base(url: string): string { return url.replace(/\/+$/, ""); }

async function call(url: string, init: RequestInit & { signal?: AbortSignal }, what: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, { ...init, credentials: "omit", cache: "no-store" });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new StudioError(`The API did not answer (${what}). Is it running at the address the page was built with?`);
  }
  let payload: unknown = null;
  const text = await response.text();
  try { payload = text ? JSON.parse(text) : null; }
  catch { throw new StudioError(`The API answered ${what} with something that is not JSON (status ${response.status}).`, response.status); }
  if (!response.ok) {
    const detail = isObject(payload) ? payload.detail : null;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d) => (isObject(d) ? `${(d.loc as unknown[] | undefined)?.filter((p) => p !== "body").join(".")}: ${d.msg}` : String(d))).join("; ")
      : `status ${response.status}`;
    throw new StudioError(`${what}: ${message}`, response.status);
  }
  return payload;
}

const headers = { "Content-Type": "application/json", "X-Anisotropy-Actor": ACTOR };

export function readChecklist(payload: unknown): Checklist {
  if (!isObject(payload) || !Array.isArray(payload.items) || (payload.state !== "ready" && payload.state !== "blocked")
    || !payload.items.every((item) => isObject(item) && typeof item.id === "string" && typeof item.label === "string" && typeof item.state === "string"
      && typeof item.message === "string" && Array.isArray(item.rows))) {
    throw new StudioError("The setup check answered with an unexpected shape.");
  }
  return payload as unknown as Checklist;
}

export function readPreview(payload: unknown): Preview {
  if (!isObject(payload) || !isObject(payload.mesh) || !Array.isArray(payload.mesh.nodes) || !Array.isArray(payload.mesh.quads)
    || !Array.isArray(payload.held) || !isObject(payload.loaded) || !Array.isArray(payload.plies) || !isObject(payload.geometry) || !isObject(payload.coupon)
    || typeof payload.units !== "string") {
    throw new StudioError("The preview answered with an unexpected shape.");
  }
  return payload as unknown as Preview;
}

export function readFields(payload: unknown): Fields {
  if (!isObject(payload) || !isObject(payload.mesh) || !Array.isArray(payload.mesh.nodes) || !Array.isArray(payload.mesh.quads)
    || !isObject(payload.nodal) || !Array.isArray(payload.nodal.displacement) || !isObject(payload.element) || !isObject(payload.summary)
    || !isObject(payload.summary.max_displacement) || !isObject(payload.summary.fpf) || typeof payload.units !== "string" || !isObject(payload.labels)) {
    throw new StudioError("The fields file has an unexpected shape.");
  }
  const mesh = payload.mesh as Record<string, unknown>;
  if ((payload.nodal as Record<string, unknown[]>).displacement.length !== (mesh.nodes as unknown[]).length) throw new StudioError("The fields file does not match its mesh.");
  return payload as unknown as Fields;
}

export function readExplanation(payload: unknown): Explanation {
  if (!isObject(payload) || typeof payload.writer !== "string" || !Array.isArray(payload.sentences) || !payload.sentences.every((s) => typeof s === "string")) {
    throw new StudioError("The explanation file has an unexpected shape.");
  }
  return { writer: payload.writer, facts: isObject(payload.facts) ? payload.facts : {}, sentences: payload.sentences as string[],
    setup_sentences: Array.isArray(payload.setup_sentences) ? (payload.setup_sentences as string[]) : [] };
}

export function readJob(payload: unknown): JobStatus {
  if (!isObject(payload) || typeof payload.job_id !== "string" || typeof payload.state !== "string" || !isObject(payload.outputs)
    || !Array.isArray(payload.stages_done) || !Array.isArray(payload.log_tail)) {
    throw new StudioError("The job status has an unexpected shape.");
  }
  return payload as unknown as JobStatus;
}

export async function checkSetup(apiBase: string, values: StudioValues, signal?: AbortSignal): Promise<CheckAnswer> {
  const payload = await call(`${base(apiBase)}/v1/coupon-jobs/check`, { method: "POST", headers, body: JSON.stringify({ values }), signal }, "the setup check");
  if (!isObject(payload)) throw new StudioError("The setup check answered with an unexpected shape.");
  const checklist = readChecklist(payload.checklist);
  const preview = payload.preview === null || payload.preview === undefined ? null : readPreview(payload.preview);
  return { run_id: typeof payload.run_id === "string" ? payload.run_id : null, state: checklist.state, designation: checklist.designation, checklist, preview };
}

export async function startSolve(apiBase: string, values: StudioValues, runBy: string, replace: boolean, signal?: AbortSignal): Promise<JobStatus> {
  const body = { values, run_by: runBy, replace };
  return readJob(await call(`${base(apiBase)}/v1/coupon-jobs`, { method: "POST", headers, body: JSON.stringify(body), signal }, "starting the solve"));
}

export async function getJob(apiBase: string, jobId: string, signal?: AbortSignal): Promise<JobStatus> {
  return readJob(await call(`${base(apiBase)}/v1/coupon-jobs/${encodeURIComponent(jobId)}`, { method: "GET", signal }, "the job's status"));
}

export async function listJobs(apiBase: string, signal?: AbortSignal): Promise<JobStatus[]> {
  const payload = await call(`${base(apiBase)}/v1/coupon-jobs`, { method: "GET", signal }, "the jobs");
  if (!Array.isArray(payload)) throw new StudioError("The job list has an unexpected shape.");
  return payload.map(readJob);
}

export async function listCoupons(apiBase: string, signal?: AbortSignal): Promise<CouponSummary[]> {
  const payload = await call(`${base(apiBase)}/v1/coupons`, { method: "GET", signal }, "the coupons");
  if (!Array.isArray(payload) || !payload.every((c) => isObject(c) && typeof c.name === "string")) throw new StudioError("The coupon list has an unexpected shape.");
  return payload as CouponSummary[];
}

export async function couponValues(apiBase: string, name: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
  const payload = await call(`${base(apiBase)}/v1/coupons/${encodeURIComponent(name)}/values`, { method: "GET", signal }, "the coupon's rows");
  if (!isObject(payload) || !isObject(payload.values)) throw new StudioError("The coupon's rows have an unexpected shape.");
  return payload.values;
}

/** Where one of a job's files is, by key: a link for the downloads and the address the viewer loads the fields from. */
export function fileUrl(apiBase: string, jobId: string, key: string): string {
  return `${base(apiBase)}/v1/coupon-jobs/${encodeURIComponent(jobId)}/files/${encodeURIComponent(key)}`;
}

export async function fetchFields(apiBase: string, jobId: string, signal?: AbortSignal): Promise<Fields> {
  return readFields(await call(fileUrl(apiBase, jobId, "fields"), { method: "GET", signal }, "the fields"));
}

export async function fetchExplanation(apiBase: string, jobId: string, signal?: AbortSignal): Promise<Explanation> {
  return readExplanation(await call(fileUrl(apiBase, jobId, "explanation"), { method: "GET", signal }, "the explanation"));
}

/** The downloadable files of a job, in the order the page lists them, with the words of fea/tools/run_coupon.py. */
export const DOWNLOADS: [string, string][] = [
  ["package", "The package for the team (zip)"], ["document", "The document (PDF)"], ["abaqus_deck", "Our Abaqus deck (.inp)"],
  ["prepomax_deck", "The CalculiX twin for PrePoMax (.inp)"], ["prepomax_results", "Its results for PrePoMax (.frd)"],
  ["kernel_summary", "Our engine's summary (text)"], ["kernel_vtu", "Every ply's stresses for ParaView (.vtu)"], ["fields", "Every field (JSON)"],
  ["explanation", "The explanation (JSON)"], ["record", "The CalculiX record (TOML)"], ["checklist", "The setup check (JSON)"], ["preview", "The preview (JSON)"],
];
