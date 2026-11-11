"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from "react";
import { couponProjects, isUuid, newProject, readProjects, reduce, upsert, writeProjects, type CouponProject, type ProjectAction } from "@/lib/project-store";
import { allCouponTests, type TowAnswer } from "@/lib/studio-api";
import type { StudioForm } from "@/lib/studio-form";
import type { PlateLists } from "@/lib/studio-plate";
import type { TowSpecimenRow } from "@/lib/studio-tow";
import { useNewestFromServer, useProjectSync } from "./project-sync";
import { useCouponRun, type CouponRun } from "./use-coupon-run";
import { useLiveSolve } from "./use-live-solve";

/** The project the workspace edits and its run, shared by the chat, the form and the viewer (ADR-0062): the rows live in one place, so
 * switching between them loses nothing, and a reload picks the last project up from this browser. */
export type ProjectContextValue = {
  apiBaseUrl: string;
  /** Whether every coupon test is offered (ADR-0089): false, the unnotched tension coupon only, until the API says the switch is on. */
  allTests: boolean;
  project: CouponProject;
  form: StudioForm;
  plate: PlateLists;
  /** A fibre tow record's specimens (ADR-0074), and the last answer of its calculation, which belongs to the page, not the project. */
  specimens: TowSpecimenRow[];
  towAnswer: TowAnswer | null;
  /** True when the project came back from this browser's storage rather than starting blank. */
  restored: boolean;
  setForm(next: StudioForm | ((form: StudioForm) => StudioForm)): void;
  setPlate(next: PlateLists): void;
  setSpecimens(next: TowSpecimenRow[]): void;
  setTowAnswer(next: TowAnswer | null): void;
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
  const run = useCouponRun(apiBaseUrl, isUuid(project.id) ? project.id : null); // the check and the solve name the project (ADR-0062 part 6)
  const allTests = useAllTests(apiBaseUrl);

  useEffect(() => {
    const store = browserStorage();
    writeProjects(upsert(readProjects(store), project), store);
  }, [project]);

  const setForm = useCallback((next: StudioForm | ((form: StudioForm) => StudioForm)) => {
    if (typeof next === "function") dispatch({ type: "form-fn", fn: next });
    else dispatch({ type: "form", form: next });
  }, []);
  const setPlate = useCallback((next: PlateLists) => dispatch({ type: "plate", plate: next }), []);
  const setSpecimens = useCallback((next: TowSpecimenRow[]) => dispatch({ type: "specimens", specimens: next }), []);
  const [towAnswer, setTowAnswer] = useState<TowAnswer | null>(null);
  const rename = useCallback((name: string) => dispatch({ type: "rename", name }), []);
  const replace = useCallback((next: CouponProject) => dispatch({ type: "replace", project: next }), []);
  useProjectSync(apiBaseUrl, project); // the server's copy follows this browser's (ADR-0062 part 6)
  useLiveSolve(apiBaseUrl, project.form, project.plate, run, allTests); // our kernel answers each settled edit (ADR-0086)
  useNewestFromServer(apiBaseUrl, "fea", !start.current.restored && project.updated === project.created,
    (found) => { if (found.kind === "fea") replace(found); });

  const value = useMemo<ProjectContextValue>(() => ({
    apiBaseUrl, allTests, project, form: project.form, plate: project.plate, specimens: project.specimens, towAnswer, restored: start.current?.restored ?? false,
    setForm, setPlate, setSpecimens, setTowAnswer, rename, replace, run,
  }), [apiBaseUrl, allTests, project, towAnswer, setForm, setPlate, setSpecimens, rename, replace, run]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

/** Whether every coupon test is offered here (ADR-0089), asked once per API address; false until the API answers that it is. */
export function useAllTests(apiBaseUrl: string): boolean {
  const [all, setAll] = useState(false);
  useEffect(() => {
    let current = true;
    void allCouponTests(apiBaseUrl).then((answer) => { if (current) setAll(answer); });
    return () => { current = false; };
  }, [apiBaseUrl]);
  return all;
}

export function useProject(): ProjectContextValue {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("useProject needs a ProjectProvider above it");
  return value;
}
