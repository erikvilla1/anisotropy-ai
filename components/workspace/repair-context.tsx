"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { analyzeRepair, solveRepair, StudioError } from "@/lib/studio-api";
import { EXAMPLE_REPAIR, sameRepair, withValue, type RepairAnswer, type RepairDescription, type RepairSolve, type RepairValue } from "@/lib/repair";
import { browserStorage } from "@/components/studio/project-context";

/** How long the page waits after the last change before it asks the engine: long enough not to send every keystroke, short enough to
 * feel immediate (as the wing's page, ADR-0118). */
export const REPAIR_SETTLE_MS = 350;
/** Where this browser keeps its one repair (ADR-0135): the repair file's table. */
export const REPAIR_STORAGE_KEY = "anisotropy.repair.v1";
/** Where this browser keeps the last solved slice with the repair and the choice it was solved for, so a reload and the report have it. */
export const REPAIR_SOLVE_KEY = "anisotropy.repair-solve.v1";

export type CutFaces = "open" | "bonded";
export type KeptSolve = { repair: RepairDescription; cutFaces: CutFaces; solve: RepairSolve };

/** The repair this browser kept, or null. */
export function storedRepair(): RepairDescription | null {
  try {
    const value: unknown = JSON.parse(browserStorage()?.getItem(REPAIR_STORAGE_KEY) ?? "null");
    if (value && typeof value === "object" && !Array.isArray(value) && "parent" in value) return value as RepairDescription;
  } catch { /* storage blocked or holding something else: nothing kept */ }
  return null;
}

/** The solved slice this browser kept, or null. */
export function storedSolve(): KeptSolve | null {
  try {
    const value: unknown = JSON.parse(browserStorage()?.getItem(REPAIR_SOLVE_KEY) ?? "null");
    if (value && typeof value === "object" && "repair" in value && "solve" in value && "cutFaces" in value) {
      const kept = value as KeptSolve;
      if (kept.repair && typeof kept.repair === "object" && kept.solve && typeof kept.solve.headline === "string" && kept.solve.report?.bond
        && (kept.cutFaces === "open" || kept.cutFaces === "bonded")) return kept;
    }
  } catch { /* storage blocked or holding something else: no solve */ }
  return null;
}

export type RepairContextValue = {
  apiBaseUrl: string;
  repair: RepairDescription;
  /** Counts the times the whole description was replaced (an opened file, an example, the other kind), so the fields show the new values. */
  revision: number;
  setValue(path: string, value: RepairValue | undefined): void;
  replace(repair: RepairDescription): void;
  /** Reads a repair file through the engine: the description it holds, worked at once; a file the engine refuses changes nothing. */
  openFile(text: string): Promise<string | null>;
  /** The engine's answer to the description as it stands, or to the last description it could work. */
  answer: RepairAnswer | null;
  /** The answer is for an earlier description: the newest one is being worked, or was refused. */
  stale: boolean;
  working: boolean;
  /** The engine's refusal of the newest description, in its words, or empty. */
  problem: string;
  /** The last solved slice (ADR-0132), and whether the repair or the cut faces' choice has changed since it was solved. */
  solve: RepairSolve | null;
  solveStale: boolean;
  solving: boolean;
  /** Why the slice was not solved, in the engine's, the solver's or the page's words, or empty. */
  solveProblem: string;
  cutFaces: CutFaces;
  setCutFaces(choice: CutFaces): void;
  solveSlice(): Promise<void>;
};

const RepairContext = createContext<RepairContextValue | null>(null);

/** The repair the page edits and the engine's answers to it, shared by the steps, the drawings and the words beside them (ADR-0135).
 * The repair is kept in this browser as its repair file's table. Every change is worked by hand again once the typing settles; an
 * answer that comes back for an older description than the newest is dropped. The slice is solved when asked, and its answer is kept
 * with the description it was solved for, so the page says when the two no longer belong together. */
export function RepairProvider({ apiBaseUrl, children }: { apiBaseUrl: string; children: ReactNode }) {
  const [repair, setRepairState] = useState<RepairDescription>(EXAMPLE_REPAIR);
  const [keep, setKeep] = useState(false); // the repair is kept: found in this browser, opened or changed
  const [revision, setRevision] = useState(0);
  const [answer, setAnswer] = useState<RepairAnswer | null>(null);
  const [answered, setAnswered] = useState<RepairDescription | null>(null);
  const [working, setWorking] = useState(false);
  const [problem, setProblem] = useState("");
  const [kept, setKept] = useState<KeptSolve | null>(null);
  const [solving, setSolving] = useState(false);
  const [solveProblem, setSolveProblem] = useState("");
  const [cutFaces, setCutFacesState] = useState<CutFaces>("open");
  const loaded = useRef(false);
  const worked = useRef<RepairDescription | null>(null); // the description the shown answer belongs to, so an opened file is not worked twice

  const setRepair = useCallback((next: RepairDescription | ((r: RepairDescription) => RepairDescription)) => {
    setRepairState((r) => (typeof next === "function" ? next(r) : next));
    setKeep(true);
  }, []);

  useEffect(() => { // after the first paint, so the server's page and the browser's first one agree
    const found = storedRepair();
    if (found) { setRepairState(found); setKeep(true); }
    const solved = storedSolve();
    if (solved) { setKept(solved); setCutFacesState(solved.cutFaces); }
    setRevision((r) => r + 1);
    loaded.current = true;
  }, []);
  useEffect(() => {
    if (!keep) return;
    try { browserStorage()?.setItem(REPAIR_STORAGE_KEY, JSON.stringify(repair)); } catch { /* the repair stays on the page; a reload forgets it */ }
  }, [repair, keep]);

  useEffect(() => {
    if (!loaded.current) return;
    if (!apiBaseUrl) { setProblem("The analysis service is not set up on this page."); return; }
    if (worked.current === repair) { setWorking(false); return; }
    const controller = new AbortController();
    setWorking(true);
    const timer = window.setTimeout(() => {
      analyzeRepair(apiBaseUrl, { repair }, controller.signal).then((found) => {
        worked.current = repair; setAnswer(found); setAnswered(repair); setProblem("");
      }).catch((error) => {
        if (controller.signal.aborted) return;
        setProblem(error instanceof StudioError ? error.message : "The repair could not be worked. Try again.");
      }).finally(() => { if (!controller.signal.aborted) setWorking(false); });
    }, REPAIR_SETTLE_MS);
    return () => { window.clearTimeout(timer); controller.abort("replaced"); };
  }, [apiBaseUrl, repair, revision]);

  const setValue = useCallback((path: string, value: RepairValue | undefined) => setRepair((r) => withValue(r, path, value)), [setRepair]);
  const replace = useCallback((next: RepairDescription) => { setRepair(next); setRevision((r) => r + 1); }, [setRepair]);
  const openFile = useCallback(async (text: string): Promise<string | null> => {
    if (!apiBaseUrl) return "The analysis service is not set up on this page.";
    try {
      const found = await analyzeRepair(apiBaseUrl, { toml: text });
      worked.current = found.repair;
      setRepair(found.repair); setRevision((r) => r + 1); setAnswer(found); setAnswered(found.repair); setProblem("");
      return null;
    } catch (error) {
      return error instanceof StudioError ? error.message : "The file could not be read. Try again.";
    }
  }, [apiBaseUrl, setRepair]);

  const solveSlice = useCallback(async () => {
    if (!apiBaseUrl) { setSolveProblem("The analysis service is not set up on this page."); return; }
    setSolveProblem(""); setSolving(true);
    const started = repair, faces = cutFaces;
    try {
      const solve = await solveRepair(apiBaseUrl, started, faces);
      const next = { repair: started, cutFaces: faces, solve };
      setKept(next); setKeep(true);
      try { browserStorage()?.setItem(REPAIR_SOLVE_KEY, JSON.stringify(next)); } catch { /* the solve stays on the page; a reload forgets it */ }
    } catch (error) {
      setSolveProblem(error instanceof StudioError ? error.message : "The slice could not be solved. Try again.");
    } finally {
      setSolving(false);
    }
  }, [apiBaseUrl, repair, cutFaces]);
  const setCutFaces = useCallback((choice: CutFaces) => setCutFacesState(choice), []);
  const solveStale = useMemo(() => kept !== null && (!sameRepair(kept.repair, repair) || kept.cutFaces !== cutFaces), [kept, repair, cutFaces]);

  const value = useMemo<RepairContextValue>(() => ({
    apiBaseUrl, repair, revision, setValue, replace, openFile, answer, stale: answered !== repair, working, problem,
    solve: kept?.solve ?? null, solveStale, solving, solveProblem, cutFaces, setCutFaces, solveSlice,
  }), [apiBaseUrl, repair, revision, setValue, replace, openFile, answer, answered, working, problem, kept, solveStale, solving, solveProblem, cutFaces,
    setCutFaces, solveSlice]);
  return <RepairContext.Provider value={value}>{children}</RepairContext.Provider>;
}

export function useRepair(): RepairContextValue {
  const value = useContext(RepairContext);
  if (!value) throw new Error("useRepair outside RepairProvider");
  return value;
}
