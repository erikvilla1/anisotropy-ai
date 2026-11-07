"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from "react";
import { couponProjects, newProject, readProjects, reduce, upsert, writeProjects, type CouponProject, type ProjectAction } from "@/lib/project-store";
import type { StudioForm } from "@/lib/studio-form";
import type { PlateLists } from "@/lib/studio-plate";
import { useCouponRun, type CouponRun } from "./use-coupon-run";

/** The project the workspace edits and its run, shared by the chat, the form and the viewer (ADR-0062): the rows live in one place, so
 * switching between them loses nothing, and a reload picks the last project up from this browser. */
export type ProjectContextValue = {
  apiBaseUrl: string;
  project: CouponProject;
  form: StudioForm;
  plate: PlateLists;
  /** True when the project came back from this browser's storage rather than starting blank. */
  restored: boolean;
  setForm(next: StudioForm | ((form: StudioForm) => StudioForm)): void;
  setPlate(next: PlateLists): void;
  rename(name: string): void;
  replace(project: CouponProject): void;
  run: CouponRun;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

/** This browser's local storage, or null where it is blocked (a private window, cleared site data). */
export function browserStorage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; }
}

function initial(): { project: CouponProject; restored: boolean } {
  const kept = couponProjects(readProjects(browserStorage()));
  return kept.length ? { project: kept[0], restored: true } : { project: newProject(), restored: false };
}

function projectReducer(project: CouponProject, action: ProjectAction | { type: "form-fn"; fn: (form: StudioForm) => StudioForm }): CouponProject {
  if (action.type === "form-fn") return reduce(project, { type: "form", form: action.fn(project.form) });
  return reduce(project, action);
}

export function ProjectProvider({ apiBaseUrl, children }: { apiBaseUrl: string; children: ReactNode }) {
  const start = useRef<{ project: CouponProject; restored: boolean } | null>(null);
  if (start.current === null) start.current = initial();
  const [project, dispatch] = useReducer(projectReducer, start.current.project);
  const run = useCouponRun(apiBaseUrl);

  useEffect(() => {
    const store = browserStorage();
    writeProjects(upsert(readProjects(store), project), store);
  }, [project]);

  const setForm = useCallback((next: StudioForm | ((form: StudioForm) => StudioForm)) => {
    if (typeof next === "function") dispatch({ type: "form-fn", fn: next });
    else dispatch({ type: "form", form: next });
  }, []);
  const setPlate = useCallback((next: PlateLists) => dispatch({ type: "plate", plate: next }), []);
  const rename = useCallback((name: string) => dispatch({ type: "rename", name }), []);
  const replace = useCallback((next: CouponProject) => dispatch({ type: "replace", project: next }), []);

  const value = useMemo<ProjectContextValue>(() => ({
    apiBaseUrl, project, form: project.form, plate: project.plate, restored: start.current?.restored ?? false, setForm, setPlate, rename, replace, run,
  }), [apiBaseUrl, project, setForm, setPlate, rename, replace, run]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("useProject needs a ProjectProvider above it");
  return value;
}
