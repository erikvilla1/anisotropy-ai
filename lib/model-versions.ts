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

const clean = (form: StudioForm): StudioForm => Object.fromEntries(Object.entries(form).filter(([k, v]) => !IGNORED.has(k) && (v ?? "").trim() !== ""));

/** The setup as one string, to tell a change from none. */
export function setupKey(form: StudioForm, plate: PlateLists): string {
  const rows = clean(form);
  return JSON.stringify([Object.keys(rows).sort().map((k) => [k, rows[k].trim()]), plate]);
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
