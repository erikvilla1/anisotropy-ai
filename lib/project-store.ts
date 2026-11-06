/** The project: the one thing the workspace edits (ADR-0062). A coupon project holds the rows of the values file (ADR-0046 amendment 3)
 * and a plate's lists (ADR-0054), under a name the engineer gives; the check, the job and its files belong to the run, not to the project,
 * and the coupon's designation stays the fea package's (ADR-0038). Pure: no React, no browser, so `tests/project-store.test.ts` can run it.
 * The browser keeps the projects under one key so a reload picks up where the engineer left off, until the server store (part 6) exists. */

import { blankForm, type StudioForm } from "./studio-form";
import { emptyPlate, type PlateLists } from "./studio-plate";

export const PROJECTS_KEY = "anisotropy.projects.v1";
export const KEPT = 20; // the projects a browser keeps, newest first

export type CouponProject = {
  id: string;
  kind: "fea";
  name: string;
  form: StudioForm;
  plate: PlateLists;
  created: string;
  updated: string;
};

export type ProjectAction =
  | { type: "form"; form: StudioForm }
  | { type: "plate"; plate: PlateLists }
  | { type: "rename"; name: string }
  | { type: "replace"; project: CouponProject };

/** What `localStorage` offers; a test passes a Map-backed stand-in. */
export type StorageLike = { getItem(key: string): string | null; setItem(key: string, value: string): void };

export function makeId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function newProject(form: StudioForm = blankForm(), now: string = new Date().toISOString(), id: string = makeId()): CouponProject {
  return { id, kind: "fea", name: "", form, plate: emptyPlate(), created: now, updated: now };
}

export function projectTitle(project: CouponProject): string {
  return project.name.trim() || "Untitled coupon";
}

export function reduce(project: CouponProject, action: ProjectAction, now: string = new Date().toISOString()): CouponProject {
  switch (action.type) {
    case "form": return { ...project, form: action.form, updated: now };
    case "plate": return { ...project, plate: action.plate, updated: now };
    case "rename": return { ...project, name: action.name, updated: now };
    case "replace": return action.project;
  }
}

function isProject(value: unknown): value is CouponProject {
  if (!value || typeof value !== "object") return false;
  const p = value as Record<string, unknown>;
  return typeof p.id === "string" && p.kind === "fea" && typeof p.name === "string" && typeof p.form === "object" && p.form !== null
    && typeof p.plate === "object" && p.plate !== null && typeof p.created === "string" && typeof p.updated === "string";
}

/** The projects the browser keeps, newest first; nothing when storage is blocked, empty or holds something else. */
export function readProjects(storage: StorageLike | null | undefined): CouponProject[] {
  try {
    const raw = storage?.getItem(PROJECTS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isProject).map((p) => ({ ...p, plate: { supports: p.plate.supports ?? [], loads: p.plate.loads ?? [], regions: p.plate.regions ?? [] } }));
  } catch {
    return [];
  }
}

export function writeProjects(list: CouponProject[], storage: StorageLike | null | undefined): boolean {
  try {
    storage?.setItem(PROJECTS_KEY, JSON.stringify(list.slice(0, KEPT)));
    return true;
  } catch {
    return false; // a private window or blocked storage: the project lives in the page only
  }
}

/** The list with this project first, replacing the one with its id, at most KEPT long. */
export function upsert(list: CouponProject[], project: CouponProject): CouponProject[] {
  return [project, ...list.filter((p) => p.id !== project.id)].slice(0, KEPT);
}
