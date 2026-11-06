/** The project: the one thing a workspace edits (ADR-0062). A coupon project holds the rows of the values file (ADR-0046 amendment 3)
 * and a plate's lists (ADR-0054); a laminate project holds the draft of a laminate problem (ADR-0060), each value with its unit; both
 * under a name the engineer gives. The check, the job and its files belong to the run, not to the project, and the coupon's designation
 * stays the fea package's (ADR-0038). Pure: no React, no browser, so `tests/project-store.test.ts` can run it. The browser keeps the
 * projects of both kinds under one key so a reload picks up where the engineer left off, until the server store (part 6) exists. */

import { blankDraft, type LaminateDraft } from "./laminate-chat";
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

export type LaminateProject = {
  id: string;
  kind: "laminate";
  name: string;
  draft: LaminateDraft;
  created: string;
  updated: string;
};

export type Project = CouponProject | LaminateProject;

export type ProjectAction =
  | { type: "form"; form: StudioForm }
  | { type: "plate"; plate: PlateLists }
  | { type: "rename"; name: string }
  | { type: "replace"; project: CouponProject };

export type LaminateAction =
  | { type: "draft"; draft: LaminateDraft }
  | { type: "rename"; name: string }
  | { type: "replace"; project: LaminateProject };

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

export function newLaminateProject(draft: LaminateDraft = blankDraft(), now: string = new Date().toISOString(), id: string = makeId()): LaminateProject {
  return { id, kind: "laminate", name: "", draft, created: now, updated: now };
}

export function projectTitle(project: Project): string {
  return project.name.trim() || (project.kind === "fea" ? "Untitled coupon" : "Untitled laminate");
}

export function reduce(project: CouponProject, action: ProjectAction, now: string = new Date().toISOString()): CouponProject {
  switch (action.type) {
    case "form": return { ...project, form: action.form, updated: now };
    case "plate": return { ...project, plate: action.plate, updated: now };
    case "rename": return { ...project, name: action.name, updated: now };
    case "replace": return action.project;
  }
}

export function reduceLaminate(project: LaminateProject, action: LaminateAction, now: string = new Date().toISOString()): LaminateProject {
  switch (action.type) {
    case "draft": return { ...project, draft: action.draft, updated: now };
    case "rename": return { ...project, name: action.name, updated: now };
    case "replace": return action.project;
  }
}

function hasShape(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object") return false;
  const p = value as Record<string, unknown>;
  return typeof p.id === "string" && typeof p.name === "string" && typeof p.created === "string" && typeof p.updated === "string";
}

function isCouponProject(value: unknown): value is CouponProject {
  return hasShape(value) && value.kind === "fea" && typeof value.form === "object" && value.form !== null && typeof value.plate === "object" && value.plate !== null;
}

function isLaminateProject(value: unknown): value is LaminateProject {
  return hasShape(value) && value.kind === "laminate" && typeof value.draft === "object" && value.draft !== null;
}

/** A kept project with the lists and the draft's rows a newer page expects filled in. */
function whole(project: Project): Project {
  if (project.kind === "fea") return { ...project, plate: { supports: project.plate.supports ?? [], loads: project.plate.loads ?? [], regions: project.plate.regions ?? [] } };
  return { ...project, draft: { ...blankDraft(), ...project.draft } };
}

/** The projects the browser keeps, both kinds, newest first; nothing when storage is blocked, empty or holds something else. */
export function readProjects(storage: StorageLike | null | undefined): Project[] {
  try {
    const raw = storage?.getItem(PROJECTS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((p): p is Project => isCouponProject(p) || isLaminateProject(p)).map(whole);
  } catch {
    return [];
  }
}

export const couponProjects = (list: Project[]): CouponProject[] => list.filter((p): p is CouponProject => p.kind === "fea");
export const laminateProjects = (list: Project[]): LaminateProject[] => list.filter((p): p is LaminateProject => p.kind === "laminate");

export function writeProjects(list: Project[], storage: StorageLike | null | undefined): boolean {
  try {
    storage?.setItem(PROJECTS_KEY, JSON.stringify(list.slice(0, KEPT)));
    return true;
  } catch {
    return false; // a private window or blocked storage: the project lives in the page only
  }
}

/** The list with this project first, replacing the one with its id, at most KEPT long. */
export function upsert(list: Project[], project: Project): Project[] {
  return [project, ...list.filter((p) => p.id !== project.id)].slice(0, KEPT);
}
