/**
 * The studio's calls to the API (ADR-0051, ADR-0050 amendment 1). Every answer's shape is checked at runtime before it is shown:
 * the browser draws what the fea package wrote and computes nothing (ADR-0001).
 */
import type { Checklist, StudioValues } from "./studio-form";

export const ACTOR = "studio";
export const POLL_MS = 2000;
/** `queued` with the hosted tier's job queue (ADR-0056 amendment 3): filed, waiting for a free solver; the message says what for. */
export type JobState = "queued" | "running" | "done" | "stopped" | "refused";
/** Still going: queued for a solver or running; the page keeps polling. */
export const isActive = (state: JobState | undefined | null): boolean => state === "queued" || state === "running";
export type JobStatus = {
  job_id: string; state: JobState; actor: string; started_at: string; finished_at: string | null; coupon: string | null; attempt: string | null;
  message: string | null; stage: string | null; stages_done: string[]; stages: string[]; outputs: Record<string, string>; run_id: string | null;
  log_tail: string[];
};
export type CheckAnswer = { run_id: string | null; state: "ready" | "blocked"; designation: string | null; checklist: Checklist; preview: Preview | null };
export type Preview = {
  units: string; labels: Record<string, string>;
  coupon: { designation: string | null; title: string; kind: string; test: string; card: [string, string][]; layup: string };
  geometry: { length: number; width: number; tab_length: number; hole_diameter: number | null; thickness: number;
    span?: number | null; overhang?: number | null; load_span?: number | null };
  mesh: { nodes: number[][]; quads: number[][]; node_sets: Record<string, number[]>; element_sets: Record<string, number[]>; order: number; mesher: string;
    node_count: number; element_count: number };
  held: { set: string; through: string | null; dofs: number[]; directions: string[]; nodes: number }[];
  loaded: { set: string; through: string | null; control: string; dof: number; direction: string; value: number; unit: string; nodes: number };
  loads?: { set: string; through: string | null; control: string; dof: number; direction: string; value: number; unit: string; nodes: number }[];
  regions?: { edges: string[]; areas: string[] } | null;
  plies: { index: number; angle: number; thickness: number; z_bottom: number; z_top: number; material: string }[];
  material: { name: string; source: string; rights: string; E1: number; E2: number; G12: number; nu12: number; G13: number; G23: number;
    strengths: Record<string, number> | null; f12_star: number | null; criteria: string[]; citation_lines: string[]; ply_thickness: number; plies: number };
  probes: { nodes: Record<string, { index: number; xy: number[] }>; elements: Record<string, { index: number; xy: number[] }> };
  quality?: { summary: QualitySummary; per_element: Record<string, number[]> };
};
export type QualitySummary = { elements: number; acceptable: boolean; measures: Record<string, { word: string; worst: number; element: number; threshold: number; warns: string; over: number }> };
/** One value per ply (a membrane solve), or one per face of the ply, bottom then top (a shell solve, ADR-0053); `Fields.mesh.faces` says which. */
export type Faced<T> = T | T[];
/** The ends of a field as the package wrote them: [min, max], or [null, null] where no value was finite. */
export type Span = [number | null, number | null];
export type Extreme = { value: number; element: number; label: string; ply: number; angle: number; xy: number[]; face?: string | null };
export type FirstPlyFailure = { factor: number; index: number; element: number; label: string; ply: number; angle: number; mode: string; place: string;
  touches_grip: boolean; tied_plies: number[]; xy: number[]; face?: string | null };
export type Fields = {
  units: string; labels: Record<string, string>; coupon: Partial<Preview["coupon"]>; kernel?: string;
  mesh: { nodes: number[][]; quads: number[][]; node_labels: string[]; element_labels: string[]; node_sets: Record<string, number[]>;
    element_sets: Record<string, number[]>; node_count: number; element_count: number; plies: number; angles: number[];
    faces?: string[] | null; translations?: number };
  nodal: { displacement: number[][]; magnitude: number[]; reaction: number[][]; rotation?: number[][]; moment_reaction?: number[][];
    averages: { strain: (number | null)[][]; section_force: (number | null)[][]; ply_stress_12: Faced<(number | null)[]>[][]; ply_mises: Faced<number | null>[][];
      failure_index: Record<string, (number | null)[]>; curvature?: (number | null)[][]; moment?: (number | null)[][]; shear_force?: (number | null)[][] };
    averages_note: string };
  element: { strain: number[][]; section_force: number[][]; centroids: number[][];
    curvature?: number[][]; moment?: number[][]; shear_force?: number[][]; shear_strain?: number[][];
    ply: { stress_12: Faced<number[]>[][]; stress_xy: Faced<number[]>[][]; strain_12: Faced<number[]>[][]; mises: Faced<number>[][] };
    failure: Record<string, { ratio: Faced<number | null>[][]; index: Faced<number>[][]; mode: Faced<number>[][]; worst_ply: number[]; worst_face?: string[];
      element_index: number[] }>; modes: string[] };
  /** Per field (ADR-0063): `element` and `nodal` spans; a list per ply, and per ply and face, for the ply fields; per criterion for the failure index. */
  ranges?: Record<string, Record<string, unknown>>; ranges_note?: string;
  summary: { max_displacement: { value: number; node: number; label: string; xy: number[]; components: number[]; axis?: string };
    reaction: { set: string; value: number; sense: string; dof?: number }; applied: { control: string; value: number; unit: string; dof?: number; direction?: string; total_force?: number };
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
    // Same-origin credentials: hosted, the page and /api share anisotropy.dev, so the browser sends the Access sign-in cookie
    // and Access lets the call through (ADR-0056); locally the API is another origin and gets no cookie, as before.
    response = await fetch(url, { ...init, credentials: "same-origin", cache: "no-store" });
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

export async function checkSetup(apiBase: string, values: StudioValues, signal?: AbortSignal, projectId: string | null = null): Promise<CheckAnswer> {
  const body = { values, ...(projectId ? { project_id: projectId } : {}) }; // the project the derived designation is written back to (ADR-0062 part 6)
  const payload = await call(`${base(apiBase)}/v1/coupon-jobs/check`, { method: "POST", headers, body: JSON.stringify(body), signal }, "the setup check");
  if (!isObject(payload)) throw new StudioError("The setup check answered with an unexpected shape.");
  const checklist = readChecklist(payload.checklist);
  const preview = payload.preview === null || payload.preview === undefined ? null : readPreview(payload.preview);
  return { run_id: typeof payload.run_id === "string" ? payload.run_id : null, state: checklist.state, designation: checklist.designation, checklist, preview };
}

export async function startSolve(apiBase: string, values: StudioValues, runBy: string, replace: boolean, signal?: AbortSignal, projectId: string | null = null): Promise<JobStatus> {
  const body = { values, run_by: runBy, replace, ...(projectId ? { project_id: projectId } : {}) };
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

// ------------------------------------------------------------------------------------------ the projects (ADR-0062 part 6)

export type ProjectJobRecord = { job_id: string; state: JobState; coupon: string | null; attempt: string | null; message: string | null; started_at: string;
  finished_at: string | null; run_id: string | null };
/** A workspace project as the API keeps it: the page's own object under `content`, the designation its last check derived, its jobs when read by id. */
export type ProjectRecord = {
  id: string; kind: "fea" | "laminate"; name: string; content: Record<string, unknown>; form_version: string | null; units: string | null;
  designation: string | null; last_check_run_id: string | null; created_at: string; updated_at: string; jobs: ProjectJobRecord[];
};
export type ProjectUpload = Pick<ProjectRecord, "kind" | "name" | "content" | "form_version" | "units">;

const PROJECTS = "/v1/projects";
const text = (v: unknown): string | null => (typeof v === "string" ? v : null);

export function readProjectRecord(payload: unknown): ProjectRecord {
  if (!isObject(payload) || typeof payload.id !== "string" || (payload.kind !== "fea" && payload.kind !== "laminate") || typeof payload.name !== "string"
    || !isObject(payload.content) || typeof payload.created_at !== "string" || typeof payload.updated_at !== "string") {
    throw new StudioError("The API answered a project with an unexpected shape.");
  }
  const jobs = Array.isArray(payload.jobs) ? payload.jobs.filter(isObject).map((j) => ({
    job_id: String(j.job_id), state: (["queued", "running", "done", "stopped", "refused"].includes(String(j.state)) ? j.state : "stopped") as JobState,
    coupon: text(j.coupon), attempt: text(j.attempt), message: text(j.message), started_at: String(j.started_at), finished_at: text(j.finished_at), run_id: text(j.run_id),
  })) : [];
  return { id: payload.id, kind: payload.kind, name: payload.name, content: payload.content, form_version: text(payload.form_version), units: text(payload.units),
    designation: text(payload.designation), last_check_run_id: text(payload.last_check_run_id), created_at: payload.created_at, updated_at: payload.updated_at, jobs };
}

/** The requester's projects on the server, the last changed first; a 503 means the API keeps no projects (run records off). */
export async function listProjects(apiBase: string, signal?: AbortSignal): Promise<ProjectRecord[]> {
  const payload = await call(`${base(apiBase)}${PROJECTS}`, { method: "GET", headers, signal }, "the projects");
  if (!Array.isArray(payload)) throw new StudioError("The API answered the projects with an unexpected shape.");
  return payload.map(readProjectRecord);
}

/** The project as the page states it, created or replaced by its id. */
export async function putProject(apiBase: string, id: string, upload: ProjectUpload, signal?: AbortSignal): Promise<ProjectRecord> {
  return readProjectRecord(await call(`${base(apiBase)}${PROJECTS}/${encodeURIComponent(id)}`, { method: "PUT", headers, body: JSON.stringify(upload), signal }, "saving the project"));
}

export async function getProject(apiBase: string, id: string, signal?: AbortSignal): Promise<ProjectRecord> {
  return readProjectRecord(await call(`${base(apiBase)}${PROJECTS}/${encodeURIComponent(id)}`, { method: "GET", headers, signal }, "the project"));
}

export async function renameProject(apiBase: string, id: string, name: string, signal?: AbortSignal): Promise<ProjectRecord> {
  return readProjectRecord(await call(`${base(apiBase)}${PROJECTS}/${encodeURIComponent(id)}`, { method: "PATCH", headers, body: JSON.stringify({ name }), signal }, "renaming the project"));
}

/** True when the API keeps no projects: run records are switched off there (503). */
export const noProjectStore = (error: unknown): boolean => error instanceof StudioError && error.status === 503;

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

export type ExplainAnswer = { run_id: string | null; job_id: string; kind: "setup" | "result"; writer: string; model: string | null; prose: string[];
  withheld: boolean; reason: string | null; facts: Record<string, unknown> };

export function readExplainAnswer(payload: unknown): ExplainAnswer {
  if (!isObject(payload) || typeof payload.writer !== "string" || !Array.isArray(payload.prose) || !payload.prose.every((s) => typeof s === "string")
    || typeof payload.withheld !== "boolean") {
    throw new StudioError("The explanation answered with an unexpected shape.");
  }
  return payload as unknown as ExplainAnswer;
}

/** The explanation of a job's result or setup through the API (ADR-0052): the template's sentences, or a model's rephrasing kept only
 * when every number in it is a fact; the answer says who wrote it. */
export async function explainJob(apiBase: string, jobId: string, kind: "setup" | "result", signal?: AbortSignal): Promise<ExplainAnswer> {
  const payload = await call(`${base(apiBase)}/v1/coupon-jobs/${encodeURIComponent(jobId)}/explain`,
    { method: "POST", headers, body: JSON.stringify({ kind }), signal }, "the explanation");
  return readExplainAnswer(payload);
}

/** The downloadable files of a job, in the order the page lists them, with the words of fea/tools/run_coupon.py. */
export const DOWNLOADS: [string, string][] = [
  ["package", "The package for the team (zip)"], ["document", "The document (PDF)"], ["abaqus_deck", "Our Abaqus deck (.inp)"],
  ["prepomax_deck", "The CalculiX twin for PrePoMax (.inp)"], ["prepomax_results", "Its results for PrePoMax (.frd)"],
  ["kernel_summary", "Our engine's summary (text)"], ["kernel_vtu", "Every ply's stresses for ParaView (.vtu)"], ["fields", "Every field (JSON)"],
  ["explanation", "The explanation (JSON)"], ["record", "The CalculiX record (TOML)"], ["checklist", "The setup check (JSON)"], ["preview", "The preview (JSON)"],
];

// ----------------------------------------------------------------------------------------------- laminate problems (ADR-0060)

export type LaminateSummary = {
  ply_count: number; total_thickness_m: number; symmetric: boolean; antisymmetric: boolean; balanced: boolean;
  kind: "unidirectional" | "cross-ply" | "angle-ply" | "quasi-isotropic" | "general";
  coupling: { extension_shear: boolean; extension_bending: boolean; bending_twisting: boolean };
  relative_tolerance: number; areal_mass_kg_per_m2: number | null; areal_mass_missing: string | null;
};
/** The answer to a laminate problem: every result in the units asked for, keyed as the engine's case runner keys them, the stack
 * described, the material cited when it came from the library, and the explanation with who wrote it (ADR-0052). */
export type LaminateAnswer = {
  run_id: string | null; engine_version: string; report_units: string; units: Record<string, string>;
  case: Record<string, unknown>; results: Record<string, unknown>; criteria: string[]; summary: LaminateSummary;
  material: { material_id: string; name: string; dataset_id: string; citation: string; ply_thickness_m: number | null; values: { role: string; value: number; unit: string }[] } | null;
  writer: string; model: string | null; prose: string[]; withheld: boolean; reason: string | null; facts: Record<string, unknown>;
};

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const vector3 = (v: unknown): v is number[] => Array.isArray(v) && v.length === 3 && v.every(finite);

/** The answer's shape, checked before anything is drawn: the matrices, the strains, every ply's stresses and the words. */
export function readLaminateAnswer(payload: unknown): LaminateAnswer {
  const bad = () => new StudioError("The laminate solve answered with an unexpected shape.");
  if (!isObject(payload) || typeof payload.engine_version !== "string" || typeof payload.report_units !== "string" || !isObject(payload.units)
    || !isObject(payload.results) || !isObject(payload.summary) || !isObject(payload.case) || !Array.isArray(payload.criteria)
    || typeof payload.writer !== "string" || !Array.isArray(payload.prose) || !payload.prose.every((s) => typeof s === "string")
    || typeof payload.withheld !== "boolean" || !isObject(payload.facts)) throw bad();
  const results = payload.results;
  for (const prefix of ["Q", "A", "B", "D"]) for (const i of "126") for (const j of "126") if (!finite(results[`${prefix}${i}${j}`])) throw bad();
  if (!vector3(results.strain_global) || !vector3(results.curvature) || !finite(results.Ex) || !finite(results.Ey) || !finite(results.Gxy) || !finite(results.nu_xy)
    || !finite(results.total_thickness)) throw bad();
  const plies = (payload.case.laminate as { layup?: unknown } | undefined)?.layup;
  if (!Array.isArray(plies) || !plies.every(finite)) throw bad();
  for (const key of ["ply_stress_local", "ply_stress_global", "ply_strain_local"]) {
    const rows = results[key];
    if (!Array.isArray(rows) || rows.length !== plies.length || !rows.every(vector3)) throw bad();
  }
  for (const criterion of payload.criteria) {
    if (typeof criterion !== "string" || !finite(results[`fpf_ply_${criterion}`]) || !vector3(results[`fpf_forces_${criterion}`])
      || !(results[`fpf_ratio_${criterion}`] === null || finite(results[`fpf_ratio_${criterion}`]))) throw bad();
  }
  return payload as unknown as LaminateAnswer;
}

/** One solve of a laminate problem: the values as typed with their units; the API converts and the engine solves. */
export async function solveLaminate(apiBaseUrl: string, problem: unknown, signal?: AbortSignal): Promise<LaminateAnswer> {
  const payload = await call(`${base(apiBaseUrl)}/v1/laminates/solve`, { method: "POST", headers, body: JSON.stringify(problem), signal }, "the laminate solve");
  return readLaminateAnswer(payload);
}
