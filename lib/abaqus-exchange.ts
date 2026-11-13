/**
 * The exchange with the user's own Abaqus, as the run's page shows it (ADR-0094, step 6): the calls to the API's upload routes, the
 * shape of every answer checked before it is shown, and the card's words. The comparison is the fea package's, read from the upload's
 * row: this file counts and computes nothing (ADR-0001); it prints the numbers `fea/tools/abaqus_upload.py compare` wrote, a fraction
 * as a percentage.
 */
import { ACTOR, StudioError } from "./studio-api";
import { formatNumber, inProse } from "./number-format";
import { printed } from "./studio-colors";
import { bannedInAbaqusCard, sentence } from "./studio-copy";

// --------------------------------------------------------------------------------------------------------------------- the shapes

/** What the card may offer here: whether uploads are kept at all, whether a file sent straight from Abaqus arrives, and the limits. */
export type Exchange = { uploads: boolean; connector_route: boolean; max_bundle_bytes: number; max_uploads: number; max_tokens: number };
export type ModelItem = { item: string; yours: string; ours: string; same: boolean | null };
export type Criterion = { criterion: string; met: boolean | null; judged: boolean; evidence: string };
/** One zone of the coupon as the comparison summed it up: its count of values, and the quantity furthest from ours with where it is. */
export type ZoneSummary = { elements: number | null; values: number; quantity: string; worst: number; your_element: number | null; our_element: number | null;
  layer: number | null; yours: number | null; ours: number | null };
export type Comparison = {
  verdict: "agrees" | "differs" | "incomplete";
  units: string; converted_from: string | null;
  bundle: { job: string | null; coupon: string | null; created: string; written_by: { abaqus?: string | null; connector?: string | null } };
  ours: { coupon: string; elements: number; layers: number };
  model: { compared: string; same: boolean | null; items: ModelItem[]; reason?: string };
  pairing: { same_mesh: boolean; how: string; elements: number };
  reaction: { nodes: number; yours: number; ours: number; difference: number | null } | null;
  criteria: Criterion[];
  summary: { places: number; model: { items: number; judged: number; different: number }; zones: Record<string, ZoneSummary>;
    labels: { length: string; stress: string; force: string } };
};
/** The comparison did not take the pair: the reasons, in the fea package's words. */
export type Refusal = { verdict: "refused"; problems: string[] };
export type Upload = {
  id: string; created_at: string; bundle_sha256: string; bundle_bytes: number; units: string; job: string | null; coupon: string | null; in_scope: boolean;
  job_id: string | null; verdict: "agrees" | "differs" | "incomplete" | "refused" | null; compared_at: string | null; not_compared: string | null;
  token_id: string | null; facts: Record<string, unknown> | null; comparison: Comparison | Refusal | null;
};
/** An upload key as the API keeps it: never the key, only its last characters. */
export type UploadKey = { id: string; name: string; hint: string; created_at: string; last_used_at: string | null; revoked_at: string | null };
export type NewUploadKey = UploadKey & { token: string };

const isObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const isText = (v: unknown): v is string => typeof v === "string";
const textOrNull = (v: unknown): v is string | null => v === null || typeof v === "string";
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const numberOrNull = (v: unknown): v is number | null => v === null || finite(v);
const flag = (v: unknown): v is boolean | null => v === null || typeof v === "boolean";

export function readExchange(payload: unknown): Exchange {
  if (!isObject(payload) || typeof payload.uploads !== "boolean" || typeof payload.connector_route !== "boolean" || !finite(payload.max_bundle_bytes)
    || !finite(payload.max_uploads) || !finite(payload.max_tokens)) throw new StudioError("The exchange settings have an unexpected shape.");
  return payload as unknown as Exchange;
}

/** A comparison as the command wrote it, or null for one this page does not read: one written before the summary, or of another shape. */
export function readComparison(payload: unknown): Comparison | Refusal | null {
  if (!isObject(payload)) return null;
  if (payload.verdict === "refused") return Array.isArray(payload.problems) && payload.problems.every(isText) ? { verdict: "refused", problems: payload.problems } : null;
  if (payload.verdict !== "agrees" && payload.verdict !== "differs" && payload.verdict !== "incomplete") return null;
  const { bundle, ours, model, pairing, reaction, criteria, summary } = payload;
  if (!isText(payload.units) || !textOrNull(payload.converted_from) || !isObject(bundle) || !textOrNull(bundle.job) || !isObject(bundle.written_by)
    || !isObject(ours) || !finite(ours.elements) || !isObject(model) || !isText(model.compared) || !flag(model.same) || !Array.isArray(model.items)
    || !model.items.every((i) => isObject(i) && isText(i.item) && isText(i.yours) && isText(i.ours) && flag(i.same))
    || !isObject(pairing) || typeof pairing.same_mesh !== "boolean" || !isText(pairing.how) || !finite(pairing.elements)
    || !(reaction === null || (isObject(reaction) && finite(reaction.yours) && finite(reaction.ours) && numberOrNull(reaction.difference)))
    || !Array.isArray(criteria) || !criteria.every((c) => isObject(c) && isText(c.criterion) && flag(c.met) && typeof c.judged === "boolean" && isText(c.evidence))
    || !isObject(summary) || !finite(summary.places) || !isObject(summary.model) || !finite(summary.model.judged) || !finite(summary.model.different)
    || !isObject(summary.zones) || !isObject(summary.labels) || !isText(summary.labels.force) || !isText(summary.labels.stress)
    || !Object.values(summary.zones).every((z) => isObject(z) && finite(z.values) && isText(z.quantity) && finite(z.worst) && numberOrNull(z.your_element)
      && numberOrNull(z.layer) && numberOrNull(z.yours) && numberOrNull(z.ours))) return null;
  return payload as unknown as Comparison;
}

export function readUpload(payload: unknown): Upload {
  if (!isObject(payload) || !isText(payload.id) || !isText(payload.created_at) || !isText(payload.bundle_sha256) || !finite(payload.bundle_bytes)
    || !isText(payload.units) || !textOrNull(payload.job) || !textOrNull(payload.coupon) || typeof payload.in_scope !== "boolean" || !textOrNull(payload.job_id)
    || !textOrNull(payload.verdict) || !textOrNull(payload.compared_at) || !textOrNull(payload.not_compared)) {
    throw new StudioError("The file's record has an unexpected shape.");
  }
  return { ...(payload as unknown as Upload), token_id: textOrNull(payload.token_id) ? payload.token_id : null, facts: isObject(payload.facts) ? payload.facts : null,
    comparison: readComparison(payload.comparison) };
}

export function readUploadKey(payload: unknown): UploadKey {
  if (!isObject(payload) || !isText(payload.id) || !isText(payload.name) || !isText(payload.hint) || !isText(payload.created_at) || !textOrNull(payload.last_used_at)
    || !textOrNull(payload.revoked_at)) throw new StudioError("The upload key has an unexpected shape.");
  return payload as unknown as UploadKey;
}

// ----------------------------------------------------------------------------------------------------------------------- the calls

const base = (url: string): string => url.replace(/\/+$/, "");
const UPLOADS = "/v1/abaqus-uploads";
const KEYS = "/v1/upload-tokens";
const actor = { "X-Anisotropy-Actor": ACTOR };

/** A call that did not succeed: the status, and the API's own sentence, which the card turns into its words (`sendProblem`). */
export class ExchangeError extends StudioError {
  constructor(message: string, status: number | undefined, public detail: string | null) { super(message, status); }
}

async function ask(url: string, init: RequestInit, what: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, { ...init, credentials: "same-origin", cache: "no-store" });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ExchangeError(`The service did not answer (${what}). Check your connection and try again.`, undefined, null);
  }
  const text = await response.text();
  let payload: unknown = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = null; }
  if (!response.ok) {
    const detail = isObject(payload) && isText(payload.detail) ? payload.detail : null;
    throw new ExchangeError(`${sentence(what)} failed. Try again.`, response.status, detail);
  }
  return payload;
}

/** What the card may offer here; null when the API does not say (an older API, or none), and then the card is not shown. */
export async function getExchange(apiBase: string, signal?: AbortSignal): Promise<Exchange | null> {
  try { return readExchange(await ask(`${base(apiBase)}/v1/abaqus-exchange`, { method: "GET", headers: actor, signal }, "the exchange settings")); }
  catch (error) { if (signal?.aborted) throw error; return null; }
}

/** The requester's own files that stand beside one run, the newest first, without their comparisons. */
export async function listUploads(apiBase: string, jobId: string, signal?: AbortSignal): Promise<Upload[]> {
  const payload = await ask(`${base(apiBase)}${UPLOADS}?mine=true&job_id=${encodeURIComponent(jobId)}`, { method: "GET", headers: actor, signal }, "your files");
  if (!Array.isArray(payload)) throw new StudioError("The list of files has an unexpected shape.");
  return payload.map(readUpload);
}

export async function getUpload(apiBase: string, id: string, signal?: AbortSignal): Promise<Upload> {
  return readUpload(await ask(`${base(apiBase)}${UPLOADS}/${encodeURIComponent(id)}`, { method: "GET", headers: actor, signal }, "the file's record"));
}

export async function compareAgain(apiBase: string, id: string, jobId: string): Promise<Upload> {
  return readUpload(await ask(`${base(apiBase)}${UPLOADS}/${encodeURIComponent(id)}/compare?job_id=${encodeURIComponent(jobId)}`, { method: "POST", headers: actor }, "the comparison"));
}

export async function removeUpload(apiBase: string, id: string): Promise<void> {
  await ask(`${base(apiBase)}${UPLOADS}/${encodeURIComponent(id)}`, { method: "DELETE", headers: actor }, "removing the file");
}

/** Where the file as it was sent is handed back from. It is a link, and a link carries no header, so the actor is named in the address. */
export const sentFileUrl = (apiBase: string, id: string): string => `${base(apiBase)}${UPLOADS}/${encodeURIComponent(id)}/bundle?actor=${ACTOR}`;
/** Where the connector's files are handed out as one zip. */
export const connectorUrl = (apiBase: string): string => `${base(apiBase)}/v1/abaqus-connector`;

export type SendStage = "sending" | "comparing";
/** Send the connector's file as the request's body, to stand beside one run. `onStage` hears "sending" with the fraction that has left
 * the browser, then "comparing" once all of it has: the API reads the model and compares it within the same request. */
export function sendUpload(apiBase: string, jobId: string, file: Blob, onStage: (stage: SendStage, fraction: number) => void): Promise<Upload> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${base(apiBase)}${UPLOADS}?job_id=${encodeURIComponent(jobId)}`);
    request.setRequestHeader("Content-Type", "application/zip");
    request.setRequestHeader("X-Anisotropy-Actor", ACTOR);
    request.upload.onprogress = (event) => { if (event.lengthComputable && event.total > 0) onStage("sending", event.loaded / event.total); };
    request.upload.onload = () => onStage("comparing", 1);
    request.onerror = () => reject(new ExchangeError("The service did not answer. Check your connection and try again.", undefined, null));
    request.onload = () => {
      let payload: unknown = null;
      try { payload = request.responseText ? JSON.parse(request.responseText) : null; } catch { payload = null; }
      if (request.status < 200 || request.status >= 300) {
        reject(new ExchangeError("The file was not sent.", request.status, isObject(payload) && isText(payload.detail) ? payload.detail : null));
        return;
      }
      try { resolve(readUpload(payload)); } catch (error) { reject(error); }
    };
    onStage("sending", 0);
    request.send(file);
  });
}

export async function listUploadKeys(apiBase: string, signal?: AbortSignal): Promise<UploadKey[]> {
  const payload = await ask(`${base(apiBase)}${KEYS}`, { method: "GET", headers: actor, signal }, "your upload keys");
  if (!Array.isArray(payload)) throw new StudioError("The list of upload keys has an unexpected shape.");
  return payload.map(readUploadKey);
}

/** A new upload key: the answer holds the key itself, this once. */
export async function createUploadKey(apiBase: string, name: string): Promise<NewUploadKey> {
  const payload = await ask(`${base(apiBase)}${KEYS}`, { method: "POST", headers: { ...actor, "Content-Type": "application/json" }, body: JSON.stringify({ name }) }, "creating the upload key");
  const key = readUploadKey(payload);
  if (!isObject(payload) || !isText(payload.token) || !payload.token) throw new StudioError("The upload key has an unexpected shape.");
  return { ...key, token: payload.token };
}

export async function cancelUploadKey(apiBase: string, id: string): Promise<UploadKey> {
  return readUploadKey(await ask(`${base(apiBase)}${KEYS}/${encodeURIComponent(id)}`, { method: "DELETE", headers: actor }, "cancelling the upload key"));
}

// ----------------------------------------------------------------------------------------------------------------------- the words

/** A text of the fea package or the API, shown on the card when it names nothing the card may not (the card may name the user's own
 * Abaqus and the connector's files), its numbers as the page prints them (the minus sign, no exponent in letters); null otherwise. */
export function cardText(text: string | null | undefined): string | null {
  const trimmed = text?.trim();
  return trimmed && !bannedInAbaqusCard(trimmed).length ? inProse(trimmed) : null;
}

export type Tone = "pass" | "fail" | "open";
/** The answer first: "Agrees with ours", "Differs in 2 places", or that not every part could be compared. */
export function headline(comparison: Comparison | Refusal): { words: string; tone: Tone } {
  if (comparison.verdict === "refused") return { words: "Not compared", tone: "open" };
  if (comparison.verdict === "agrees") return { words: "Agrees with ours", tone: "pass" };
  if (comparison.verdict === "incomplete") return { words: "Not every part could be compared", tone: "open" };
  const places = comparison.summary.places;
  return { words: places === 1 ? "Differs in 1 place" : places > 1 ? `Differs in ${places} places` : "Differs from ours", tone: "fail" };
}

/** Where the model came from, in one line: the job's name, the program that solved it, and how many elements stood beside ours. */
export function provenance(comparison: Comparison): string {
  const by = comparison.bundle.written_by.abaqus;
  const paired = `${comparison.pairing.elements.toLocaleString("en-US")} of its elements beside ours${comparison.pairing.same_mesh ? "" : ", by position: the two meshes differ"}`;
  return `${comparison.bundle.job ?? "Your model"}${by ? `, solved by ${by}` : ""}: ${paired}.`
    + (comparison.converted_from ? ` Your values were written in ${comparison.converted_from} and are shown in ${comparison.units}.` : "");
}

/** A fraction as the card prints a difference: the size of the percentage by the site's one rule for numbers. */
export const percent = (fraction: number): string => `${formatNumber(100 * Math.abs(fraction), { zeros: false })} %`;

/** The exporter's names for a ply's values, as the rest of the page writes them. */
const QUANTITY: Record<string, string> = { S11: "σ₁", S22: "σ₂", S12: "τ₁₂", E11: "ε₁", E22: "ε₂", E12: "γ₁₂", Mises: "Mises", Tresca: "Tresca", Pressure: "pressure",
  "Max. Principal": "largest principal stress", "Mid. Principal": "middle principal stress", "Min. Principal": "smallest principal stress" };
export const quantityName = (quantity: string): string => QUANTITY[quantity] ?? quantity;
const isStrain = (quantity: string): boolean => /^E\d\d$/.test(quantity);

export type RowId = "model" | "force" | "gauge" | "free";
export type RowState = "same" | "differs" | "open" | "shown";
/** One line of the card: what was compared, what was found, and how it stands. `element` is ours, where the largest difference is. */
export type CardRow = { id: RowId; label: string; said: string; state: RowState; mark: string; element: number | null; ply: number | null };

const ZONE: Record<Exclude<RowId, "model" | "force">, { zone: string; label: string; prefix: string }> = {
  gauge: { zone: "gauge", label: "The gauge section", prefix: "Gauge" },
  free: { zone: "free length", label: "Between gauge and tabs", prefix: "Free length" },
};
const limitOf = (criterion: string): string | null => criterion.match(/within (\d+(?:\.\d+)?) %/)?.[1] ?? null;
const mark = (c: Criterion): { state: RowState; mark: string } => {
  const limit = limitOf(c.criterion);
  if (!c.judged) return { state: "shown", mark: "not judged" };
  if (c.met === null) return { state: "open", mark: "not compared" };
  return c.met ? { state: "same", mark: limit ? `within ${limit} %` : "agrees" } : { state: "differs", mark: limit ? `outside ${limit} %` : "differs" };
};

/** The card's four lines, in the order the decision gives them: the model, the pull force, the gauge section, between gauge and tabs. */
export function cardRows(c: Comparison): CardRow[] {
  const counted = c.summary.model, force = c.summary.labels.force;
  const rows: CardRow[] = [];
  if (c.model.compared === "not compared") {
    rows.push({ id: "model", label: "The model", said: `Not compared${cardText(c.model.reason) ? `: ${cardText(c.model.reason)}` : ""}.`, state: "open", mark: "not compared", element: null, ply: null });
  } else {
    const without = c.model.compared === "without the mesh" ? ", compared without the mesh" : "";
    rows.push(counted.different === 0
      ? { id: "model", label: "The model", said: `The same as ours on all ${counted.judged} items${without}.`, state: "same", mark: "same", element: null, ply: null }
      : { id: "model", label: "The model", said: `${counted.different} of ${counted.judged} items differ${without}.`, state: "differs", mark: "differs", element: null, ply: null });
  }
  const reaction = c.criteria.find((x) => x.criterion.startsWith("Reaction"));
  if (reaction) {
    const said = c.reaction ? `Yours ${printed(Math.abs(c.reaction.yours))} ${force}, ours ${printed(Math.abs(c.reaction.ours))} ${force}${cardText(reaction.evidence) ? ` (${cardText(reaction.evidence)})` : ""}.`
      : /^no reactions read/.test(reaction.evidence) ? "Your file holds no reaction forces, so the pull force was not compared."
        : `${sentence(cardText(reaction.evidence) ?? "not compared")}.`;
    rows.push({ id: "force", label: "The pull force", said, ...mark(reaction), element: null, ply: null });
  }
  for (const id of ["gauge", "free"] as const) {
    const criterion = c.criteria.find((x) => x.criterion.startsWith(ZONE[id].prefix));
    if (!criterion) continue;
    const zone = c.summary.zones[ZONE[id].zone];
    const where = zone && zone.your_element !== null ? `, your element ${zone.your_element}${zone.layer !== null ? `, ply ${zone.layer}` : ""}` : "";
    const said = zone ? `${zone.values.toLocaleString("en-US")} values; the largest difference is ${percent(zone.worst)} (${quantityName(zone.quantity)}${where}).`
      + (criterion.judged ? "" : " Shown, not judged: the two meshes differ.")
      : `${sentence(cardText(criterion.evidence) ?? "not compared")}.`;
    rows.push({ id, label: ZONE[id].label, said, ...mark(criterion), element: zone?.our_element ?? null, ply: zone?.layer ?? null });
  }
  return rows;
}

/** A difference where it is: the item by name, the user's value beside ours, and the place on the coupon. */
export type Difference = { what: string; yours: string; ours: string; where: string | null };
export function differences(c: Comparison): Difference[] {
  const { force, stress } = c.summary.labels;
  const out: Difference[] = c.model.items.filter((i) => i.same === false).map((i) => ({ what: i.item, yours: i.yours, ours: i.ours, where: "the model" }));
  for (const criterion of c.criteria) {
    if (!criterion.judged || criterion.met !== false) continue;
    if (criterion.criterion.startsWith("Reaction") && c.reaction) {
      out.push({ what: "The pull force", yours: `${printed(Math.abs(c.reaction.yours))} ${force}`, ours: `${printed(Math.abs(c.reaction.ours))} ${force}`, where: "the top grip" });
      continue;
    }
    const id = (["gauge", "free"] as const).find((key) => criterion.criterion.startsWith(ZONE[key].prefix));
    const zone = id ? c.summary.zones[ZONE[id].zone] : undefined;
    if (!id || !zone) continue;
    const unit = isStrain(zone.quantity) ? "" : ` ${stress}`;
    out.push({ what: `${quantityName(zone.quantity)}, ${ZONE[id].label.replace(/^The /, "the ").replace(/^Between/, "between")}`, yours: `${printed(zone.yours)}${unit}`, ours: `${printed(zone.ours)}${unit}`,
      where: zone.your_element !== null ? `your element ${zone.your_element}${zone.layer !== null ? `, ply ${zone.layer}` : ""}` : null });
  }
  return out;
}

/** Why a stored file was not compared with this run, in plain words with what to do next. The API's reasons name its own records. */
export function notComparedWords(reason: string | null | undefined): string {
  const said = reason ?? "";
  if (/out of the comparison's scope/.test(said)) return "The comparison does not cover this model yet. What could not be read is listed under Details.";
  if (/is no longer there/.test(said)) return "This run's files are no longer stored, so nothing can stand beside your model. Run the analysis again, then send the file again.";
  if (/that run is not one the comparison covers|the comparison needs one/.test(said)) return "The comparison does not cover this kind of coupon yet.";
  if (/^the comparison did not run/.test(said)) return "The comparison could not run just now. Click Compare again.";
  if (/an upload stands beside a run that is done/.test(said)) return "This run has not finished. Compare again once it has.";
  return "This file was stored but not compared with this run. Click Compare again.";
}

/** Megabytes as the card writes a size limit. */
export const megabytes = (bytes: number): string => `${Math.round(bytes / (1024 * 1024))} MB`;

/** Why a file was not taken, and what to do next: the card's sentence, and the fea package's reasons for the detail. */
export function sendProblem(error: unknown, limits: Pick<Exchange, "max_bundle_bytes" | "max_uploads">): { words: string; reasons: string[] } {
  const status = error instanceof StudioError ? error.status : undefined;
  const detail = error instanceof ExchangeError ? error.detail ?? "" : "";
  if (status === 413) return { words: `This file is larger than ${megabytes(limits.max_bundle_bytes)}, the most that can be sent.`, reasons: [] };
  if (status === 422) {
    const reasons = detail.includes(": ") ? detail.slice(detail.indexOf(": ") + 2).split("; ").map((r) => cardText(r)).filter((r): r is string => r !== null) : [];
    return { words: "This is not a file the connector wrote, so nothing was stored. Send the file named <job>-anisotropy.zip.", reasons };
  }
  if (status === 429) return { words: `You have ${limits.max_uploads} files stored, the most a person may keep. Remove one, then send again.`, reasons: [] };
  if (status === 401 || status === 403) return { words: "Your sign-in has ended. Reload the page, sign in, and send the file again.", reasons: [] };
  if (status === 404) return { words: "This file is no longer stored, or it belongs to someone else.", reasons: [] };
  if (status === 409) return { words: notComparedWords(detail.replace(/^Not compared: /, "")), reasons: [] };
  if (status === undefined) return { words: error instanceof StudioError ? error.message : "The file was not sent. Try again.", reasons: [] };
  return { words: "The file could not be read or stored just now. Nothing was kept. Try again.", reasons: [] };
}

/** The file name a key is saved under, and the name the connector's command gives it. */
export const KEY_FILE = "anisotropy-key.txt";
const SAFE = /^[A-Za-z0-9_.-]{1,80}$/;

/** The command that sends a finished job straight from Abaqus to stand beside this run. The key is never in it: the command names the
 * file the key was saved in (Abaqus writes a command's arguments into its own record). */
export function connectorCommand(options: { apiAddress: string; jobId: string; coupon: string | null; units: string }): string {
  const units = options.units === "m-Pa" ? "m-Pa" : "mm-MPa"; // the systems an input file of ours is written in
  return ["abaqus python anisotropy_connector.py <your job>.odb", `--units ${units}`, ...(options.coupon && SAFE.test(options.coupon) ? [`--coupon ${options.coupon}`] : []),
    `--send ${options.apiAddress.replace(/\/+$/, "")}`, `--token-file ${KEY_FILE}`, `--our-run ${options.jobId}`].join(" ");
}
