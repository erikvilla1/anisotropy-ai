/**
 * The studio's calls to the API (ADR-0051, ADR-0050 amendment 1). Every answer's shape is checked at runtime before it is shown:
 * the browser draws what the fea package wrote and computes nothing (ADR-0001).
 */
import type { Checklist, StudioValues } from "./studio-form";
import { ANALYSIS_UNAVAILABLE, customerText, DOWNLOAD_LABELS, sentence } from "./studio-copy";

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
  /** The result's one line once the solve and the CalculiX record are done, while the drawings and the package are still made
   * (ADR-0064); `documents` is then "building", and once the job is done "written" or what is missing and why. */
  result?: string | null; documents?: string | null;
  /** When a solver took the queued job up, and the seconds of each of the tool's stages and of the solver's phases around it
   * (restore_s, lock_wait_s, gate_s, upload_s), as far as the job got (ADR-0056 amendment 6). */
  claimed_at?: string | null; timings?: Record<string, number>;
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
  touches_grip: boolean; tied_plies: number[]; xy: number[]; face?: string | null;
  /** ADR-0085: whether a ply fails at the applied loading (R at or below 1), and the loading at first-ply failure, R times the applied value and the
   * reaction, as the package wrote them; absent on older jobs. */
  fails?: boolean; at_failure?: AtFailure | null };
export type AtFailure = { applied: number; unit: string; reaction: number; reaction_unit: string; every_load: boolean };
/** The answer's basis (ADR-0085): the gauge section when the coupon has one, the whole model otherwise; an earlier failure outside it apart. */
export type Verdict = { basis: "gauge" | "whole"; earliest: string; factor: number; fails: boolean; outside_earlier: OutsideEarlier | null };
export type OutsideEarlier = { criterion: string; factor: number; fails: boolean; element: number; label: string; ply: number; angle: number; face: string | null;
  mode: string; place: string; touches_grip: boolean; xy: number[] };
/** A ply stress at its largest of one sign (or magnitude), with where it is; `ply` and `angle` on the extremes over every ply. Null when never reached. */
export type PlyExtreme = { value: number; element: number; label: string; xy: number[]; face: string | null; ply?: number; angle?: number } | null;
export type ExtremeSet = { S11: { tension: PlyExtreme; compression: PlyExtreme }; S22: { tension: PlyExtreme; compression: PlyExtreme };
  S12: { largest: PlyExtreme }; mises: { largest: PlyExtreme } };
export type PlyExtremes = { basis: "gauge" | "whole"; plies: ({ ply: number; angle: number } & ExtremeSet)[]; overall: ExtremeSet };
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
    ply: {
      stress_12: Faced<number[]>[][]; stress_xy: Faced<number[]>[][]; strain_12: Faced<number[]>[][]; mises: Faced<number>[][];
      /** Tresca, the three principal stresses and the pressure of each ply (ADR-0066 amendment 2); absent from a job solved before them. */
      invariants?: Record<string, Faced<number>[][]>;
    };
    failure: Record<string, { ratio: Faced<number | null>[][]; index: Faced<number>[][]; mode: Faced<number>[][]; worst_ply: number[]; worst_face?: string[];
      element_index: number[] }>; modes: string[] };
  /** Per field (ADR-0063): `element` and `nodal` spans; a list per ply, and per ply and face, for the ply fields; per criterion for the failure index. */
  ranges?: Record<string, Record<string, unknown>>; ranges_note?: string;
  summary: { max_displacement: { value: number; node: number; label: string; xy: number[]; components: number[]; axis?: string };
    reaction: { set: string; value: number; sense: string; dof?: number }; applied: { control: string; value: number; unit: string; dof?: number; direction?: string; total_force?: number };
    max_ply: Record<string, Extreme>; fpf: Record<string, FirstPlyFailure>; earliest: string | null; equilibrium_residual: number; free_residual: number;
    /** The same over the gauge section alone (the Gauge elements that touch no gripped node): what a test is compared with. Absent on older jobs. */
    fpf_gauge?: Record<string, FirstPlyFailure>; earliest_gauge?: string | null;
    /** The answer (ADR-0085): its basis, earliest criterion and verdict, and the largest ply stresses on that basis; absent on older jobs. */
    verdict?: Verdict | null; ply_extremes?: PlyExtremes;
    /** CalculiX's numbers beside ours, from the comparison record and its `.frd` block (ADR-0030 amendment 6); absent on a job solved before it. */
    calculix?: CalculixBeside | null;
    /** Every ply's own peaks at the element centroids, each marked when its element touches a gripped node (ADR-0066); absent on older jobs. */
    ply_peaks?: PlyPeak[];
    /** Classical laminate theory for a gripped coupon: the reaction over the width as N_y, every ply at its middle (ADR-0066); null when it does not apply. */
    clt?: CltCheck | null;
    /** The mesh convergence study (ADR-0068): the kernel on the spec's mesh and its refinements, the validation quantities and the peaks on each; absent on older jobs. */
    convergence?: Convergence | null;
    /** The quantities the coupon's test standard reduces a test to (ADR-0072); absent without a standard or a strain measurement, and on older jobs. */
    test_method?: TestMethod };
  quality?: QualitySummary;
};
export type PlyPeak = { ply: number; angle: number } & Record<"S11" | "S22" | "S12", { value: number; element: number; label: string; xy: number[]; face: string | null; touches_grip: boolean }>;
/** One mesh of the convergence study: its size, the solve's seconds, and ADR-0066's quantities on it (ADR-0068). */
export type ConvergenceMesh = { factor: number; nx: number; ny: number; elements: number; nodes: number; solve_s: number; reaction: number; reaction_set: string;
  gauge_element: number; gauge_xy: number[]; gauge_strain: number[]; plies: { ply: number; angle: number; stress_12: number[] }[];
  peaks: { ply: number; angle: number; s1: number; element: number; touches_grip: boolean }[]; fpf: Record<string, number>; fpf_gauge: Record<string, number> };
/** The study: `studied` false with the reason when it does not cover the coupon; else the meshes, each quantity's change from the previous mesh
 * (null for the first; a fraction of the finer value, of a triple's largest component) and whether each group settled (last change under `settled_below`). */
export type Convergence = { studied: boolean; reason?: string; units: string | null; factors: number[]; cap: number; settled_below: number; meshes: ConvergenceMesh[];
  left_out: { factor: number; elements: number; reason: string }[]; kernel?: string; note?: string;
  changes?: { reaction: (number | null)[]; gauge_strain: ((number | null)[] | null)[]; plies: { ply: number; stress_12: ((number | null)[] | null)[] }[];
    peaks: { ply: number; s1: (number | null)[] }[]; fpf: Record<string, (number | null)[]>; fpf_gauge: Record<string, (number | null)[]> };
  settled?: Record<"reaction" | "gauge_strain" | "plies" | "peaks" | "fpf" | "fpf_gauge", boolean> };
/** A test standard's quantities from the solved coupon (ADR-0072), every number in the stated units, written by the package. */
export type TestMethod = {
  designation: string | null; width: number; thickness: number; area: number; force: number; stress: number;
  units: { length: string; area: string; force: string; stress: string; modulus: string };
  hole: { diameter: number; net_area: number; net_stress: number; width_to_hole: number; hole_to_thickness: number } | null;
  laminate_theory: { modulus: number; poisson: number; note: string; isotropic?: boolean };
  /** The standard's own words for the shared formulas (D3039's chord over the gross area, D638's modulus of elasticity over the narrow
   * section); absent from a package written before ADR-0075 part 2, which read D3039's. */
  reduction?: { area: string; area_clause: string; stress_clause: string; strain_clause: string; modulus: string; modulus_clause: string; range: string;
    poisson_clause: string };
  strain: { device: string; gauge_length: number; modelled_length: number; nodes: string[]; x: number[]; value: number; microstrain: number; poisson: number | null;
    chord: { from: number; to: number; stress_from: number; stress_to: number; force_from: number; force_to: number; modulus: number } } | null;
  fpf: Record<string, { factor: number; force: number; stress: number; net_stress?: number; strain?: number; microstrain?: number; place: string | null }>;
  fpf_basis: string; earliest: string | null; note_b: boolean;
};
export type CltCheck = { Ny: number; width: number; strain: number[]; plies: { ply: number; angle: number; stress_12: number[] }[]; note: string };
/** One ply's peaks in its own fibre axes read from the `.frd`'s bricks: nodal, extrapolated, as a viewer would show them per ply (ADR-0066).
 *  `s1_max` and `s2_max` are the largest signed values; `s1_max_abs` and `s2_max_abs` the values at the largest magnitude, signed, the
 *  definition of our own per-ply peaks, absent from a record written before they were added. */
export type FrdPly = { ply: number; angle: number; fibre: number; nodes: number; s1_max?: number; s1_max_node?: number; s1_max_xyz?: number[]; s2_max?: number; s2_max_node?: number;
  s1_max_abs?: number; s1_max_abs_node?: number; s1_max_abs_xyz?: number[]; s2_max_abs?: number; s2_max_abs_node?: number; s2_max_abs_xyz?: number[];
  t12_max_abs?: number; t12_max_abs_node?: number; gauge_s1_max?: number; gauge_s1_max_node?: number };
export type CalculixBeside = {
  record: string; units: string; tolerance: number; agree: string;
  reaction: { calculix: number; ours: number; difference: string; agrees: boolean } | null;
  gauge_element: string | null;
  gauge: { ply: number; ours: (number | null)[]; calculix: (number | null)[]; agrees: (boolean | null)[] }[];
  /** The gauge element's mean strain [eps_x, eps_y, gamma_xy], ours and CalculiX's (ADR-0066); absent on a record without the strain group. */
  gauge_strain?: { ours: (number | null)[]; calculix: (number | null)[]; agrees: (boolean | null)[] };
  /** CalculiX's strain at the strain measurement and its chord modulus, beside ours on the same twin (ADR-0072); absent without one. */
  test_method?: { calculix: { strain: number; modulus: number }; ours: { strain: number; modulus: number }; agrees: boolean; difference: string; nodes: string[] } | null;
  frd: (Record<string, unknown> & { nodes: number; mises_max: number; mises_max_node: number; mises_max_xyz: number[]; syy_max: number; syy_max_node: number;
    sxx_max: number; sxx_min: number; gauge_mises_max?: number; gauge_syy_max?: number; gauge_from?: number; gauge_to?: number; plies?: FrdPly[] }) | null;
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
    throw new StudioError(ANALYSIS_UNAVAILABLE); // an outage: what happened and what to do, the same words as the calculator's
  }
  let payload: unknown = null;
  const text = await response.text();
  try { payload = text ? JSON.parse(text) : null; }
  catch { throw new StudioError(response.status >= 500 ? ANALYSIS_UNAVAILABLE : `The analysis service sent an answer the page cannot read (${what}). Try again.`, response.status); }
  if (response.status >= 500) throw new StudioError(ANALYSIS_UNAVAILABLE, response.status);
  if (!response.ok) {
    const detail = isObject(payload) ? payload.detail : null;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d) => (isObject(d) ? `${(d.loc as unknown[] | undefined)?.filter((p) => p !== "body").join(".")}: ${d.msg}` : String(d))).join("; ")
      : `status ${response.status}`;
    // the API's own words when they are fit to show (ADR-0091); otherwise what failed and what to do
    throw new StudioError(customerText(message) && !/^status \d+$/.test(message) ? `${sentence(what)}: ${message}` : `${sentence(what)} failed. Try again.`, response.status);
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

/** The live solve (ADR-0086): the setup check and, when nothing blocks, our kernel's fields and explanation, a preview with no mesh study
 * and no CalculiX; `seconds` at the API, `warm` when a warm worker answered. Every number is the fea package's (ADR-0051). */
export type LiveAnswer = CheckAnswer & { fields: Fields | null; explanation: Explanation | null; seconds: number; warm: boolean;
  timings: Record<string, number> };

export async function liveSolve(apiBase: string, values: StudioValues, signal?: AbortSignal, projectId: string | null = null): Promise<LiveAnswer> {
  const body = { values, ...(projectId ? { project_id: projectId } : {}) };
  const payload = await call(`${base(apiBase)}/v1/coupon-jobs/live`, { method: "POST", headers, body: JSON.stringify(body), signal }, "the live solve");
  if (!isObject(payload)) throw new StudioError("The live solve answered with an unexpected shape.");
  const checklist = readChecklist(payload.checklist);
  const preview = payload.preview === null || payload.preview === undefined ? null : readPreview(payload.preview);
  const fields = payload.fields === null || payload.fields === undefined ? null : readFields(payload.fields);
  const explanation = payload.explanation === null || payload.explanation === undefined ? null : readExplanation(payload.explanation);
  const timings = isObject(payload.timings) ? Object.fromEntries(Object.entries(payload.timings).filter(([, v]) => typeof v === "number")) as Record<string, number> : {};
  return { run_id: typeof payload.run_id === "string" ? payload.run_id : null, state: checklist.state, designation: checklist.designation, checklist, preview,
    fields, explanation, seconds: typeof payload.seconds === "number" ? payload.seconds : 0, warm: payload.warm === true, timings };
}

/** A fibre tow record's answer (ADR-0074): the checklist and, when nothing blocks, the result in the standard's report units (N, MPa, GPa, g/m,
 * g/cm³, mm², microstrain). Every number is the engine's; the page shows them as they come. */
export type TowStats = { n: number; mean: number; sd: number; cv: number };
export type TowSpecimenResult = {
  id: string; status: "valid" | "rejected"; note: string; max_force: number | null; force_lower: number | null; force_upper: number | null;
  strength: number | null; modulus: number | null; failure_code: string | null; failure_words: string | null;
};
export type TowResult = {
  test: string; designation: string | null; fibre: string; lot: string | null; units: Record<string, string>;
  fibre_properties: { mul: number; mul_from: string; bundles: number; specimen_mul: number; density: number; density_from: string; area: number;
    resin_content: number | null; resin_content_from: string | null };
  strains: { failure: number; preload: number; chord: [number, number]; chord_table: [number, number]; chord_from: string };
  specimens: TowSpecimenResult[];
  strength: TowStats | null; modulus: TowStats | null;
  counts: { specimens: number; valid: number; strength: number; modulus: number };
  planning: { preload_force: number | null; force_lower: number | null; force_upper: number | null; failure_force: number | null; from: string[] };
  conformance: { designation: string; words: string; deviations: number; advisories: number } | null;
  report: { clause: string; item: string; rows: string[]; shown: boolean }[];
  note: string;
};
export type TowAnswer = { run_id: string | null; state: "ready" | "blocked"; checklist: Checklist; result: TowResult | null };

export async function towTest(apiBase: string, values: Record<string, unknown>, signal?: AbortSignal, projectId: string | null = null): Promise<TowAnswer> {
  const body = { values, ...(projectId ? { project_id: projectId } : {}) };
  const payload = await call(`${base(apiBase)}/v1/tow-tests`, { method: "POST", headers, body: JSON.stringify(body), signal }, "the tow calculation");
  if (!isObject(payload)) throw new StudioError("The tow calculation answered with an unexpected shape.");
  const checklist = readChecklist(payload.checklist);
  const result = isObject(payload.result) && Array.isArray(payload.result.specimens) ? (payload.result as unknown as TowResult) : null;
  return { run_id: typeof payload.run_id === "string" ? payload.run_id : null, state: checklist.state, checklist, result };
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

/** Where one of a job's files is, by key: a link for the downloads and the address the viewer loads the fields from. With `name`, the
 * API hands the file out under that name (ADR-0091). */
export function fileUrl(apiBase: string, jobId: string, key: string, name?: string): string {
  return `${base(apiBase)}/v1/coupon-jobs/${encodeURIComponent(jobId)}/files/${encodeURIComponent(key)}${name ? `?name=${encodeURIComponent(name)}` : ""}`;
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

/** The files of a job the page offers for download, in the order it lists them, with their plain names (ADR-0091): the report, the
 * package, the solver input and the reference solver's input and results. The other outputs (the fields, the explanation, the record, the
 * summary, the `.vtu`, the setup check, the preview) remain job outputs the viewer and the explanation read; they are not offered as files. */
export const DOWNLOADS: [string, string][] = DOWNLOAD_LABELS;

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

// ----------------------------------------------------------------------------------------------- the model proposes (ADR-0088)

/** A row a message may fill: a coupon's number names the unit it is stated in, a laminate's the dimension of its units; a pure number neither. */
export type OfferedRow = {
  key: string; label: string; kind: "number" | "choice" | "notation";
  unit?: string; dimension?: string; choices?: { value: string; label: string }[];
};
export type ProposalRequest = {
  product: "coupon" | "laminate"; message: string; rows: OfferedRow[];
  conditions: { id: string; title: string; detail: string }[]; form: Record<string, string>;
};
/** A value the engineer wrote, for an offered row: as the row takes it, as written, and the words it came from. */
export type Proposal = { key: string; label: string; value: string; unit: string | null; written_value: string; written_unit: string | null; quote: string };
export type ProposalAnswer = {
  run_id: string | null; writer: string; model: string | null; proposals: Proposal[];
  conditions: { id: string; title: string; quote: string }[]; question: string | null; dropped: { key: string; reason: string }[]; reason: string | null;
};
export type AssistantInfo = { proposes: boolean; provider: string | null; model: string | null };

const isText = (v: unknown): v is string => typeof v === "string";
const isTextOrNull = (v: unknown): v is string | null => v === null || typeof v === "string";

export function readProposalAnswer(payload: unknown): ProposalAnswer {
  const bad = () => new StudioError("The proposals answered with an unexpected shape.");
  if (!isObject(payload) || !isText(payload.writer) || !isTextOrNull(payload.model) || !isTextOrNull(payload.question) || !isTextOrNull(payload.reason)
    || !Array.isArray(payload.proposals) || !Array.isArray(payload.conditions) || !Array.isArray(payload.dropped)) throw bad();
  for (const p of payload.proposals) {
    if (!isObject(p) || !isText(p.key) || !isText(p.label) || !isText(p.value) || !isTextOrNull(p.unit) || !isText(p.written_value) || !isTextOrNull(p.written_unit)
      || !isText(p.quote)) throw bad();
  }
  for (const c of payload.conditions) if (!isObject(c) || !isText(c.id) || !isText(c.title) || !isText(c.quote)) throw bad();
  for (const d of payload.dropped) if (!isObject(d) || !isText(d.key) || !isText(d.reason)) throw bad();
  return payload as unknown as ProposalAnswer;
}

/** The model's reading of a message, kept by the source guard; nothing in it has entered the problem until the engineer applies it. */
export async function proposeRows(apiBase: string, request: ProposalRequest, signal?: AbortSignal): Promise<ProposalAnswer> {
  const payload = await call(`${base(apiBase)}/v1/workspace/proposals`, { method: "POST", headers, body: JSON.stringify(request), signal }, "the proposals");
  return readProposalAnswer(payload);
}

const couponTestAnswers = new Map<string, Promise<boolean>>();
/** Whether every coupon test is offered here (ADR-0089), asked once per API address. False, the unnotched tension coupon only, unless the
 * API says all: before it answers, when it does not (an older API) and with no API at all. */
export function allCouponTests(apiBase: string): Promise<boolean> {
  if (!apiBase) return Promise.resolve(false);
  const key = base(apiBase);
  if (!couponTestAnswers.has(key)) {
    couponTestAnswers.set(key, call(`${key}/v1/coupon-tests`, { method: "GET", headers }, "the tests offered")
      .then((payload) => isObject(payload) && payload.all === true)
      .catch(() => false));
  }
  return couponTestAnswers.get(key)!;
}

const assistantInfos = new Map<string, Promise<AssistantInfo | null>>();
/** Whether a model reads messages here, asked once per API address; null when the API does not say (an older API, or none). */
export function assistantInfo(apiBase: string): Promise<AssistantInfo | null> {
  const key = base(apiBase);
  if (!assistantInfos.has(key)) {
    assistantInfos.set(key, call(`${key}/v1/workspace/assistant`, { method: "GET", headers }, "the assistant")
      .then((payload) => (isObject(payload) && typeof payload.proposes === "boolean" ? payload as unknown as AssistantInfo : null))
      .catch(() => null));
  }
  return assistantInfos.get(key)!;
}
