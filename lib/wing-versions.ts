/**
 * Versions of a wing (ADR-0120, kept as ADR-0113 keeps a coupon's setup): each settled change to the description is a version, who made it
 * and why, and what it changed in the page's own labels, so an engineer can see the wing's history and go back to any version. Going
 * back is itself a new version: no earlier state is ever overwritten. Pure: no React, no browser, so `tests/wing-versions.test.ts` runs it.
 */
import {
  AERO_FIELDS, AILERON_FIELDS, ENVELOPE_FIELDS, GEOMETRY_FIELDS, GUST_FACTOR_FIELDS, GUST_SPEED_FIELDS, OWN_MATERIAL_FIELDS, SPEED_FIELDS,
  WING_CORES, WING_MATERIALS, type WingDescription, type WingValue,
} from "./wing";

export type WingVersion = {
  n: number;
  at: string;
  /** who made the change: the engineer on the page, or the assistant from a message the engineer sent */
  by: "you" | "assistant";
  /** the message or the action it came from, when there is one ("Opened example-wing.toml", "Back to version 3") */
  why: string | null;
  /** what changed from the version before, one line each ("Chord: 0.45 → 0.5") */
  changes: string[];
  wing: WingDescription;
  /** the finite element check started from this version (ADR-0119), and its headline once it has one */
  check?: { job: string; headline: string | null };
};

/** How many versions a wing keeps in this browser; the oldest go first. */
export const MAX_WING_VERSIONS = 50;
export const wingVersionsKey = (project: string): string => `anisotropy.wing-versions.v1.${project}`;

/** The labels of the values the page edits, in the order its panels show them; a value of another path is named by its path. */
const ORDER: [string, string][] = [
  ["title", "Name"], ["units", "Units"], ["geometry.airfoil", "Airfoil"], ...GEOMETRY_FIELDS.map((f): [string, string] => [f.path, f.label]),
  ["material.library", "Material"], ["material.name", "Material name"], ...OWN_MATERIAL_FIELDS.map((f): [string, string] => [f.path, f.label]),
  ["skin.half_stack", "Skin layup"], ["skin.core", "Core"], ["skin.core_thickness", "Core thickness"], ["spar.half_stack", "Spar web layup"],
  ["rib.half_stack", "Rib layup"], ...AERO_FIELDS.map((f): [string, string] => [f.path, f.label]),
  ...ENVELOPE_FIELDS.map((f): [string, string] => [f.path, f.label]), ["envelope.criterion", "Failure criterion"], ["envelope.airspeed", "Speeds are"],
  ["envelope.speed_unit", "Speed unit"],
  ...[...SPEED_FIELDS, ...GUST_SPEED_FIELDS, ...GUST_FACTOR_FIELDS, ...AILERON_FIELDS].map((f): [string, string] => [f.path, f.label]),
];
const LABELS: Record<string, string> = Object.fromEntries(ORDER);
/** Text a version does not count as a change: where the description came from. */
const IGNORED = new Set(["source"]);
const NAMES: Record<string, string> = Object.fromEntries([...WING_MATERIALS, ...WING_CORES].map((m) => [m.id, m.name]));

const isTable = (value: WingValue | undefined): value is WingDescription => typeof value === "object" && value !== null && !Array.isArray(value);

/** Every value of the description by its path, a list being one value. */
function leaves(wing: WingDescription, prefix = ""): Map<string, WingValue> {
  const found = new Map<string, WingValue>();
  for (const [key, value] of Object.entries(wing)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (isTable(value)) for (const [p, v] of leaves(value, path)) found.set(p, v);
    else if (!IGNORED.has(path)) found.set(path, value);
  }
  return found;
}

/** A value as a change line prints it: a half stack as the laminate it makes, a list with commas, a library entry by its name. */
function shownValue(path: string, value: WingValue | undefined): string {
  if (value === undefined || value === "") return "blank";
  if (Array.isArray(value)) return path.endsWith("half_stack") ? `[${value.join("/")}]s` : value.join(", ");
  if (typeof value === "string") return NAMES[value] ?? value;
  return String(value);
}

/** The description as one string, to tell a change from none. */
export function wingKey(wing: WingDescription): string {
  return JSON.stringify([...leaves(wing)].sort(([a], [b]) => a.localeCompare(b)));
}

/** What changed between two descriptions, one line per value in its label, in the order the page shows them. */
export function wingChanges(before: WingDescription | null, after: WingDescription): string[] {
  if (!before) return ["The wing as it started"];
  const a = leaves(before), b = leaves(after);
  const rank = (path: string) => { const i = ORDER.findIndex(([p]) => p === path); return i < 0 ? ORDER.length : i; };
  const paths = [...new Set([...a.keys(), ...b.keys()])].filter((p) => JSON.stringify(a.get(p)) !== JSON.stringify(b.get(p)))
    .sort((x, y) => rank(x) - rank(y) || x.localeCompare(y));
  return paths.map((p) => `${LABELS[p] ?? p}: ${shownValue(p, a.get(p))} → ${shownValue(p, b.get(p))}`);
}

/** The versions with one more at the end, numbered after the last, the oldest dropped past MAX_WING_VERSIONS. An unchanged wing adds none. */
export function withWingVersion(list: WingVersion[], wing: WingDescription, by: WingVersion["by"], why: string | null, at: string): WingVersion[] {
  const last = list[list.length - 1] ?? null;
  if (last && wingKey(last.wing) === wingKey(wing)) return list;
  const version: WingVersion = { n: (last?.n ?? 0) + 1, at, by, why, changes: wingChanges(last?.wing ?? null, wing), wing };
  return [...list, version].slice(-MAX_WING_VERSIONS);
}

/** The version a check was started from: the last one, marked with the check's job. */
export function withWingCheck(list: WingVersion[], job: string): WingVersion[] {
  if (!list.length || list.some((v) => v.check?.job === job)) return list;
  return list.map((v, i) => (i === list.length - 1 ? { ...v, check: { job, headline: null } } : v));
}

/** A check's headline kept on the version it was started from. */
export function withWingCheckResult(list: WingVersion[], job: string, headline: string): WingVersion[] {
  return list.map((v) => (v.check?.job === job && v.check.headline !== headline ? { ...v, check: { job, headline } } : v));
}

/** What `localStorage` offers; a test passes a Map-backed stand-in. */
type StorageLike = { getItem(key: string): string | null; setItem(key: string, value: string): void };

export function readWingVersions(storage: StorageLike | null | undefined, project: string): WingVersion[] {
  try {
    const parsed: unknown = JSON.parse(storage?.getItem(wingVersionsKey(project)) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((v): v is WingVersion => Boolean(v) && typeof v.n === "number" && isTable(v.wing) && Array.isArray(v.changes)) : [];
  } catch { return []; }
}

export function writeWingVersions(storage: StorageLike | null | undefined, project: string, list: WingVersion[]): void {
  try { storage?.setItem(wingVersionsKey(project), JSON.stringify(list.slice(-MAX_WING_VERSIONS))); } catch { /* storage full or blocked: the history stays on the page */ }
}
