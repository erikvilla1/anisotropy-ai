"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from "react";
import { couponProjects, isUuid, newFeaProject, newProject, readProjects, reduce, upsert, writeProjects, type CouponProject, type ProjectAction } from "@/lib/project-store";
import type { FeaAnalysis } from "@/lib/workspaces";
import { takeRunToOpen } from "@/lib/run-history";
import { offeredHere, type Offered, type TowAnswer } from "@/lib/studio-api";
import type { StudioForm } from "@/lib/studio-form";
import { PLATE_TEST, type PlateLists } from "@/lib/studio-plate";
import type { TowSpecimenRow } from "@/lib/studio-tow";
import { useNewestFromServer, useProjectSync } from "./project-sync";
import { useCouponRun, type CouponRun } from "./use-coupon-run";
import { useImportedModel, type ImportedState } from "./use-imported-model";
import { useLiveSolve } from "./use-live-solve";
import { usePastRun, type PastState } from "./use-past-run";
import { useVersions, type VersionsState } from "./use-versions";

/** The project the workspace edits and its run, shared by the chat, the form and the viewer (ADR-0062): the rows live in one place, so
 * switching between them loses nothing, and a reload picks the last project up from this browser. */
export type ProjectContextValue = {
  apiBaseUrl: string;
  /** Whether every coupon test is offered (ADR-0089): false, the unnotched tension coupon only, until the API says the switch is on. */
  allTests: boolean;
  /** Whether a model may be brought in as a file (ADR-0105): where every test is offered, and for a founder's sign-in (ADR-0089 amendment 6). */
  imports: boolean;
  /** Whether a plate may be set up on the model tree, held and loaded on any edge or face (ADR-0089 amendment 7): where the import is. */
  plates: boolean;
  /** Whether the model downloads as an Ansys file too (ADR-0129): where the import is, until the file has been run in Ansys. */
  ansysModel: boolean;
  /** Whether this form's every row is offered: every test is, or it is a plate where plates are (ADR-0089 amendment 7). */
  offersAll: boolean;
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
  /** Sets the FEA project up for a kind of work (ADR-0124): a blank project becomes a coupon in place, its name and history kept. */
  setAnalysis(analysis: FeaAnalysis): void;
  setTowAnswer(next: TowAnswer | null): void;
  rename(name: string): void;
  replace(project: CouponProject): void;
  run: CouponRun;
  /** A model brought in as a file (ADR-0105): while it is open, the stage and the assistant are its, and the coupon's rows wait. */
  imported: ImportedState;
  /** A past analysis opened again (ADR-0109): while it is open, the stage and the assistant are its, and the project's rows wait. */
  past: PastState;
  /** The element clicked on the results, by its index in the mesh shown, so the assistant can read "here" (ADR-0099); null for none. */
  picked: number | null;
  setPicked(element: number | null): void;
  /** A place the assistant asks the viewer to frame: the element and, when one is named, the ply, the face and the field. */
  place: Place | null;
  showPlace(place: Omit<Place, "at">): void;
  /** A plate's boundary conditions and loads the assistant proposes and the engineer has not applied: drawn dashed on the model (ADR-0110). */
  proposed: ProposedInputs | null;
  setProposed(next: ProposedInputs | null): void;
  /** The tab of the model tree open on the left whose part the model draws bolder: its boundary conditions or its loads (ADR-0111). */
  emphasis: Emphasis;
  setEmphasis(next: Emphasis): void;
  /** The field the Results tab of the model tree asks the model to be coloured by, and its ply (ADR-0111); null until one is asked. */
  view: FieldView | null;
  showField(next: Omit<FieldView, "at">): void;
  /** The field and ply the model is coloured by now, as the viewer says it, so the Results tab presses the button of what is shown. */
  shownField: { id: string; ply: number } | null;
  setShownField(next: { id: string; ply: number } | null): void;
  /** The versions of the setup (ADR-0113): each settled change, who made it and why, and the run made from it; any can be gone back to. */
  versions: VersionsState;
};

/** A field to colour the results by; `at` tells one request from the next, so the same field can be asked twice. */
export type FieldView = { id: string; ply?: number; at: number };

export type Emphasis = "conditions" | "loads" | null;

/** What a proposal card holds for a plate (ADR-0101), as the model draws it before it is applied (ADR-0110). */
export type ProposedInputs = { supports: { region: string; dofs: number[] }[]; loads: { region: string; kind: "force" | "pressure"; dof: number | null; value: string; unit: string }[] };

/** A place on the results; `at` tells one request from the next, so the same place can be shown twice. */
export type Place = { element: number; ply: number | null; face?: string | null; /** the viewer's field to colour the model by */ field?: string;
  /** the failure criterion the field is of, when the place is a first-ply failure */ criterion?: string; at: number };

const ProjectContext = createContext<ProjectContextValue | null>(null);

/** This browser's local storage, or null where it is blocked (a private window, cleared site data). */
export function browserStorage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; }
}

/** This tab's session storage, or null where it is blocked. */
export function tabStorage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.sessionStorage; } catch { return null; }
}

/** The kind of work the address asks the FEA page to be set up for (ADR-0124): `?for=coupon`, or a library material sent from its page
 * (`?material=`), which only a coupon takes. None otherwise, and on the server, which has no address. */
function askedFor(): FeaAnalysis | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("for") === "coupon" || params.has("material") ? "coupon" : null;
}

/** The project the FEA page opens: the newest FEA project kept, or a blank one (ADR-0124); one not set up yet is set up for the kind the
 * address asks for. */
function initial(): { project: CouponProject; restored: boolean } {
  const kept = couponProjects(readProjects(browserStorage()));
  const asked = askedFor();
  const start = kept.length ? { project: kept[0], restored: true } : { project: asked === "coupon" ? newProject() : newFeaProject(), restored: false };
  if (asked && start.project.analysis === "none") start.project = { ...start.project, analysis: asked };
  return start;
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
  const { all: allTests, imports, plates, ansysModel } = useOffered(apiBaseUrl);
  const imported = useImportedModel(apiBaseUrl);
  const past = usePastRun(apiBaseUrl);
  // a run picked from the list of past analyses is opened once, as the page arrives (ADR-0109)
  const { show: showPast } = past;
  useEffect(() => {
    const asked = takeRunToOpen(tabStorage());
    if (asked) void showPast(asked);
  }, [showPast]);

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
  const setAnalysis = useCallback((analysis: FeaAnalysis) => dispatch({ type: "analysis", analysis }), []);
  const [towAnswer, setTowAnswer] = useState<TowAnswer | null>(null);
  const rename = useCallback((name: string) => dispatch({ type: "rename", name }), []);
  const replace = useCallback((next: CouponProject) => dispatch({ type: "replace", project: next }), []);
  const [picked, setPicked] = useState<number | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const showPlace = useCallback((next: Omit<Place, "at">) => setPlace((last) => ({ ...next, at: (last?.at ?? 0) + 1 })), []);
  const [proposed, setProposed] = useState<ProposedInputs | null>(null);
  const [emphasis, setEmphasis] = useState<Emphasis>(null);
  const [view, setView] = useState<FieldView | null>(null);
  const showField = useCallback((next: Omit<FieldView, "at">) => setView((last) => ({ ...next, at: (last?.at ?? 0) + 1 })), []);
  const [shownField, setShownField] = useState<{ id: string; ply: number } | null>(null);
  const versions = useVersions(project.id, project.form, project.plate, run, setForm, setPlate, browserStorage);
  useProjectSync(apiBaseUrl, project); // the server's copy follows this browser's (ADR-0062 part 6)
  const offersAll = allTests || (plates && project.form.test === PLATE_TEST); // a founder's plate is offered every row (ADR-0089 amendment 7)
  useLiveSolve(apiBaseUrl, project.form, project.plate, run, allTests, offersAll); // our kernel answers each settled edit (ADR-0086)
  const asked = useRef<FeaAnalysis | null | undefined>(undefined);
  if (asked.current === undefined) asked.current = askedFor();
  useNewestFromServer(apiBaseUrl, "fea", !start.current.restored && project.updated === project.created,
    (found) => { if (found.kind === "fea") replace(asked.current && found.analysis === "none" ? { ...found, analysis: asked.current } : found); });

  const value = useMemo<ProjectContextValue>(() => ({
    apiBaseUrl, allTests, imports, plates, ansysModel, offersAll, project, form: project.form, plate: project.plate, specimens: project.specimens, towAnswer, restored: start.current?.restored ?? false,
    setForm, setPlate, setSpecimens, setAnalysis, setTowAnswer, rename, replace, run, imported, past, picked, setPicked, place, showPlace, proposed, setProposed,
    emphasis, setEmphasis, view, showField, shownField, setShownField, versions,
  }), [apiBaseUrl, allTests, imports, plates, ansysModel, offersAll, project, towAnswer, setForm, setPlate, setSpecimens, setAnalysis, rename, replace, run, imported, past, picked, place, showPlace, proposed,
    emphasis, view, showField, shownField, versions]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

/** What the API offers here (ADR-0089), asked once per API address; nothing more than the tension coupon until the API answers. */
export function useOffered(apiBaseUrl: string): Offered {
  const [offered, setOffered] = useState<Offered>({ all: false, imports: false, plates: false, ansysModel: false });
  useEffect(() => {
    let current = true;
    void offeredHere(apiBaseUrl).then((answer) => { if (current) setOffered(answer); });
    return () => { current = false; };
  }, [apiBaseUrl]);
  return offered;
}
/** Whether every coupon test is offered here (ADR-0089); false until the API answers that it is. */
export const useAllTests = (apiBaseUrl: string): boolean => useOffered(apiBaseUrl).all;

export function useProject(): ProjectContextValue {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("useProject needs a ProjectProvider above it");
  return value;
}
