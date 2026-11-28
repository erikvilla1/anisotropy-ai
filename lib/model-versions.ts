/**
 * Versions of a model's setup (ADR-0113): each settled change to the rows or a plate's lists is kept as a version, who made it and why,
 * what it changed, and the answer of a run made from it, so an engineer can see the history, go back to any version and compare two
 * runs. Going back is itself a new version: no earlier state is ever overwritten. The page computes no number: a run's line is the
 * package's own values, printed.
 */
import { layupNotation } from "./studio-chat";
import { fieldByKey, FOLLOWED_KEY, FOLLOWED_LABEL, PLY_KEYS, type StudioForm } from "./studio-form";
import { plateWords, type PlateLists } from "./studio-plate";

/** A run's answer as its version keeps it: the package's reaction, largest displacement and first-ply failure, printed. */
export type VersionResult = { reaction: string; displacement: string; failure: string };
export type ModelVersion = {
  n: number;
  at: string;
  /** who made the change: the engineer on the page, or the assistant from a message the engineer sent */
  by: "you" | "assistant";
  /** the message or the action it came from, when there is one ("use 4 mm elements", "Restored version 2") */
  why: string | null;
  /** what changed from the version before, one line each ("Element size (mm): 2 → 4") */
  changes: string[];
  form: StudioForm;
  plate: PlateLists;
  /** the run made from this version, and its answer once it has one */
  run?: { job: string; result: VersionResult | null };
};

/** How many versions a project keeps in this browser; the oldest go first. */
export const MAX_VERSIONS = 50;
/** Rows a version does not count as a change: the date the page fills in. */
const IGNORED = new Set(["date"]);
const LAYUP_KEYS = new Set([...PLY_KEYS, "symmetric"]);

const clean = (form: StudioForm): StudioForm => Object.fromEntries(Object.entries(form ?? {})
  .filter(([k, v]) => !IGNORED.has(k) && typeof v === "string" && v.trim() !== ""));

/** A value with every object's keys in one order. The server keeps a setup as JSON and answers with its own order of keys, so the lists
 * the page wrote and the same lists read back are told apart by their values alone. A list keeps its order: it is part of the setup. */
const keyed = (value: unknown): unknown => (Array.isArray(value) ? value.map(keyed)
  : typeof value === "object" && value !== null ? Object.fromEntries(Object.keys(value).sort().map((k) => [k, keyed((value as Record<string, unknown>)[k])]))
    : value);

/** A plate's lists as a version counts them, each one present: a list that is missing or is no list reads as empty, an entry that is no
 * object is left out, and nothing else the plate holds is counted. This is the server's `lists_of` (`api/src/anisotropy_api/setup_tools.py`),
 * which another client's setup, written without a list, is read by. */
const LISTS = ["supports", "loads", "regions"] as const;
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const listsOf = (plate: unknown) => Object.fromEntries(LISTS.map((k) => {
  const list = record(plate) ? plate[k] : null;
  return [k, Array.isArray(list) ? list.filter(record).map(keyed) : []];
}));

/** The setup as one string, to tell a change from none, whatever order its keys were written in: the filled rows but the date, and the
 * plate's three lists. It agrees with the server's `setup_key`, held by `tests/fixtures/setup-tools/setup-keys.json` on both sides. */
export function setupKey(form: StudioForm, plate: PlateLists): string {
  const rows = clean(form);
  return JSON.stringify([Object.keys(rows).sort().map((k) => [k, rows[k].trim()]), listsOf(plate)]);
}

const label = (key: string) => (key === FOLLOWED_KEY ? FOLLOWED_LABEL : fieldByKey[key]?.label ?? key);
const shown = (value: string | undefined) => (value ?? "").trim() || "blank";
/** The Analysis step's switch is on or off, never blank (ADR-0142). */
const switched = (value: string | undefined) => ((value ?? "").trim() === "yes" ? "on" : "off");

/** What changed between two setups, one line per row in its label, the plies as one layup, and a plate's lists as their sentences. */
export function changesBetween(before: { form: StudioForm; plate: PlateLists } | null, after: { form: StudioForm; plate: PlateLists }): string[] {
  if (!before) return ["The setup as it started"];
  const a = clean(before.form), b = clean(after.form);
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((k) => (a[k] ?? "").trim() !== (b[k] ?? "").trim());
  const lines: string[] = [];
  if (keys.some((k) => LAYUP_KEYS.has(k))) lines.push(`Layup: ${layupNotation(before.form) || "blank"} → ${layupNotation(after.form) || "blank"}`);
  for (const key of keys.filter((k) => !LAYUP_KEYS.has(k)).sort()) {
    lines.push(key === FOLLOWED_KEY ? `${label(key)}: ${switched(a[key])} → ${switched(b[key])}` : `${label(key)}: ${shown(a[key])} → ${shown(b[key])}`);
  }
  const was = plateWords(before.plate), now = plateWords(after.plate);
  for (const line of now.filter((l) => !was.includes(l))) lines.push(`Added: ${line}`);
  for (const line of was.filter((l) => !now.includes(l))) lines.push(`Removed: ${line}`);
  return lines;
}

/** The versions with one more at the end, numbered after the last, the oldest dropped past MAX_VERSIONS. Unchanged setups add none. */
export function withVersion(list: ModelVersion[], form: StudioForm, plate: PlateLists, by: ModelVersion["by"], why: string | null, at: string): ModelVersion[] {
  const last = list[list.length - 1] ?? null;
  if (last && setupKey(last.form, last.plate) === setupKey(form, plate)) return list;
  const version: ModelVersion = { n: (last?.n ?? 0) + 1, at, by, why, changes: changesBetween(last, { form, plate }), form, plate };
  return [...list, version].slice(-MAX_VERSIONS);
}

/** The version a run was made from: the last one, marked with the job. */
export function withRun(list: ModelVersion[], job: string): ModelVersion[] {
  if (!list.length || list.some((v) => v.run?.job === job)) return list;
  return list.map((v, i) => (i === list.length - 1 ? { ...v, run: { job, result: null } } : v));
}

/** A run's answer kept on the version it was made from. */
export function withResult(list: ModelVersion[], job: string, result: VersionResult): ModelVersion[] {
  return list.map((v) => (v.run?.job === job ? { ...v, run: { job, result } } : v));
}

/** Two versions side by side: what differs in the setup, and each run's answer where it has one. */
export function comparison(a: ModelVersion, b: ModelVersion): { changes: string[]; rows: [string, string, string][] } {
  const [older, newer] = a.n < b.n ? [a, b] : [b, a];
  const r = (v: ModelVersion, key: keyof VersionResult) => v.run?.result?.[key] ?? "not run";
  return {
    changes: changesBetween(older, newer),
    rows: [["First-ply failure", r(older, "failure"), r(newer, "failure")], ["Reaction", r(older, "reaction"), r(newer, "reaction")],
      ["Largest displacement", r(older, "displacement"), r(newer, "displacement")]],
  };
}

/** The server's versions of a project (ADR-0143), checked: each with a whole number, a time, who made it, its lines and its setup; anything
 * else is left out, and a payload that is no list is none. The setup is the page's own object, as the page sent it. */
export function readServerVersions(payload: unknown): ModelVersion[] {
  if (!Array.isArray(payload)) return [];
  const text = (v: unknown): v is string => typeof v === "string";
  const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
  return payload.flatMap((v): ModelVersion[] => {
    if (!object(v) || !Number.isInteger(v.n) || !text(v.at) || (v.by !== "you" && v.by !== "assistant") || !(v.why === null || text(v.why))
      || !Array.isArray(v.changes) || !v.changes.every(text) || !object(v.form) || !Object.values(v.form).every(text) || !object(v.plate)) return [];
    const run = object(v.run) && text(v.run.job) ? { job: v.run.job, result: readResult(v.run.result) } : undefined;
    return [{ n: v.n as number, at: v.at, by: v.by, why: v.why as string | null, changes: v.changes as string[], form: v.form as StudioForm,
      plate: v.plate as PlateLists, ...(run ? { run } : {}) }];
  });
}

function readResult(value: unknown): VersionResult | null {
  if (typeof value !== "object" || value === null) return null;
  const r = value as Record<string, unknown>;
  return typeof r.reaction === "string" && typeof r.displacement === "string" && typeof r.failure === "string"
    ? { reaction: r.reaction, displacement: r.displacement, failure: r.failure } : null;
}

/** A version as the server takes it: who made it and why, what it changed and its setup; the number, the time and the run are the server's. */
export const versionUpload = (v: ModelVersion) => ({ by: v.by, why: v.why, changes: v.changes, form: v.form as Record<string, string>,
  plate: v.plate as unknown as Record<string, unknown> });

/** The versions the server does not yet hold, the oldest first: those after the last setup both lists share. All of them when the server
 * holds none, none when the server's last is this browser's last. */
export function unsent(local: ModelVersion[], server: ModelVersion[]): ModelVersion[] {
  if (!server.length) return local;
  const last = setupKey(server[server.length - 1].form, server[server.length - 1].plate);
  let i = local.length - 1;
  while (i >= 0 && setupKey(local[i].form, local[i].plate) !== last) i--;
  return i < 0 ? local.slice(-1) : local.slice(i + 1);
}

/** The history as the page shows it once the server holds versions: the server's, each keeping a run this browser marked on the same
 * setup and the server has not yet heard of, then this browser's versions the server does not hold, numbered after its last. */
export function mergeVersions(server: ModelVersion[], local: ModelVersion[]): ModelVersion[] {
  if (!server.length) return local;
  // a run marked here goes on the server's last version of the same setup: the numbers of the two lists need not agree
  const marked = new Map<number, NonNullable<ModelVersion["run"]>>();
  for (const l of local) {
    if (!l.run) continue;
    const key = setupKey(l.form, l.plate);
    const on = [...server].reverse().find((v) => setupKey(v.form, v.plate) === key);
    if (on) marked.set(on.n, l.run);
  }
  const kept = server.map((v) => {
    const mine = marked.get(v.n);
    if (!mine || v.run?.result || (v.run && v.run.job !== mine.job)) return v;
    return { ...v, run: mine };
  });
  const after = kept[kept.length - 1].n;
  return [...kept, ...unsent(local, server).map((v, i) => ({ ...v, n: after + i + 1 }))].slice(-MAX_VERSIONS);
}

/** The runs this browser marked that the server's versions do not yet say: a version's job, or its answer once read. */
export function runsToSend(server: ModelVersion[], shown: ModelVersion[]): { n: number; job: string; result: VersionResult | null }[] {
  return shown.flatMap((v) => {
    const there = server.find((s) => s.n === v.n);
    if (!there || !v.run || (there.run?.job === v.run.job && (!v.run.result || there.run.result))) return [];
    return [{ n: v.n, job: v.run.job, result: v.run.result }];
  });
}

const KEY = (project: string) => `anisotropy.versions.${project}`;

/** A project's versions from this browser; none where storage is blocked or holds something else. */
export function readVersions(storage: Storage | null, project: string): ModelVersion[] {
  try {
    const parsed = JSON.parse(storage?.getItem(KEY(project)) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((v) => v && typeof v.n === "number" && v.form && v.plate) : [];
  } catch { return []; }
}

export function writeVersions(storage: Storage | null, project: string, list: ModelVersion[]): void {
  try { storage?.setItem(KEY(project), JSON.stringify(list)); } catch { /* a full or blocked storage keeps the versions of this page only */ }
}
