"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { analyzeRepair, followRepairBond, getRepairPlies, solveRepair, startRepairPlies, StudioError } from "@/lib/studio-api";
import { EXAMPLE_REPAIR, pliesProgress, sameRepair, withValue, type RepairAnswer, type RepairBond, type RepairDescription, type RepairPliesJob, type RepairSolve, type RepairValue,
  type SolveNeed } from "@/lib/repair";
import type { RepairHeld } from "@/lib/repair-chat";
import { browserStorage } from "@/components/studio/project-context";

/** How long the page waits after the last change before it asks the engine: long enough not to send every keystroke, short enough to
 * feel immediate (as the wing's page, ADR-0118). */
export const REPAIR_SETTLE_MS = 350;
/** Where this browser keeps its one repair (ADR-0135): the repair file's table. */
export const REPAIR_STORAGE_KEY = "anisotropy.repair.v1";
/** Where this browser keeps the last solved slice with the repair and the choice it was solved for, so a reload and the report have it. */
export const REPAIR_SOLVE_KEY = "anisotropy.repair-solve.v1";

/** Where this browser keeps the last followed bond with the repair it was followed for (ADR-0140). */
export const REPAIR_BOND_KEY = "anisotropy.repair-bond.v1";

/** Where this browser keeps the repair's last run with its plies damaging (ADR-0141): the repair it was started for, the run, and the
 * second run on a finer mesh when one was asked for. */
export const REPAIR_PLIES_KEY = "anisotropy.repair-plies.v1";
/** How often the page looks at a ply run that is queued or running, and how many looks may fail running before it says so (as the
 * wing's check, ADR-0119). */
export const PLIES_POLL_MS = 2000;
const POLL_TRIES = 3;

export type CutFaces = "open" | "bonded";
export type KeptSolve = { repair: RepairDescription; cutFaces: CutFaces; solve: RepairSolve };
export type KeptBond = { repair: RepairDescription; bond: RepairBond };
export type KeptPlies = { repair: RepairDescription; run: RepairPliesJob; finer: RepairPliesJob | null };

/** Whether a ply run is still under way: the page looks at it again. */
export const pliesUnderWay = (job: RepairPliesJob | null): boolean => job !== null && (job.state === "queued" || job.state === "running");

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

/** The followed bond this browser kept, or null. */
export function storedBond(): KeptBond | null {
  try {
    const value: unknown = JSON.parse(browserStorage()?.getItem(REPAIR_BOND_KEY) ?? "null");
    if (value && typeof value === "object" && "repair" in value && "bond" in value) {
      const kept = value as KeptBond;
      if (kept.repair && typeof kept.repair === "object" && kept.bond && typeof kept.bond.headline === "string" && kept.bond.report?.onset && kept.bond.report?.curve) return kept;
    }
  } catch { /* storage blocked or holding something else: no run */ }
  return null;
}

const isPliesJob = (value: unknown): value is RepairPliesJob => typeof value === "object" && value !== null
  && typeof (value as RepairPliesJob).job_id === "string" && typeof (value as RepairPliesJob).state === "string";

/** The ply run this browser kept, or null. */
export function storedPlies(): KeptPlies | null {
  try {
    const value: unknown = JSON.parse(browserStorage()?.getItem(REPAIR_PLIES_KEY) ?? "null");
    if (value && typeof value === "object" && "repair" in value && "run" in value) {
      const kept = value as KeptPlies;
      if (kept.repair && typeof kept.repair === "object" && isPliesJob(kept.run)) return { repair: kept.repair, run: kept.run, finer: isPliesJob(kept.finer) ? kept.finer : null };
    }
  } catch { /* storage blocked or holding something else: no run */ }
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
  /** The last followed bond (ADR-0140), and whether the repair has changed since it was followed. */
  bond: RepairBond | null;
  bondStale: boolean;
  following: boolean;
  /** Why the bond was not followed, in the engine's, the solver's or the page's words, or empty. */
  bondProblem: string;
  /** What following the bond still needs, by the engine's last answer (of an earlier description while `stale`); null before the
   * first answer, or where the analysis service follows no bonds. */
  bondNeeds: readonly SolveNeed[] | null;
  followBond(): Promise<void>;
  /** The last run that carried the repair until its plies and its bond cannot hold the load (ADR-0141): a job, under way or ended,
   * and the same on a mesh one step finer when that was asked for; whether the repair has changed since the run was started. */
  plies: RepairPliesJob | null;
  pliesFiner: RepairPliesJob | null;
  pliesStale: boolean;
  /** A run is being started. */
  carrying: boolean;
  /** Why the run was not started or could not be followed, in the engine's or the page's words, or empty. */
  pliesProblem: string;
  /** What the run still needs, by the engine's last answer; null before the first answer, or where the service makes no such run. */
  pliesNeeds: readonly SolveNeed[] | null;
  /** Start the run for the repair as it stands, or (`finer` 1) the same on a finer mesh beside a run that is done. */
  carryPlies(finer?: 0 | 1): Promise<void>;
  /** A plan's approval taken (ADR-0144, step 5): the repair it leaves becomes the page's, and the slice it solved and the bond it followed,
   * each of that repair, are kept as the page keeps its own. */
  adoptPlan(next: { repair: RepairDescription; solve: { cutFaces: CutFaces; solve: RepairSolve } | null; bond: RepairBond | null }): void;
};

const RepairContext = createContext<RepairContextValue | null>(null);

/** The repair the page edits and the engine's answers to it, shared by the steps, the drawings and the words beside them (ADR-0135).
 * The repair is kept in this browser as its repair file's table. Every change is worked by hand again once the typing settles; an
 * answer that comes back for an older description than the newest is dropped. The slice is solved when asked, and its answer is kept
 * with the description it was solved for, so the page says when the two no longer belong together; the bond followed until it lets
 * go (ADR-0140) is kept the same way. The run with the plies damaging (ADR-0141) takes minutes, so it is a job: the page starts it, keeps
 * its id with the repair, and looks at it every two seconds until it has ended, across a reload. */
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
  const [keptBond, setKeptBond] = useState<KeptBond | null>(null);
  const [following, setFollowing] = useState(false);
  const [bondProblem, setBondProblem] = useState("");
  const [keptPlies, setKeptPlies] = useState<KeptPlies | null>(null);
  const [carrying, setCarrying] = useState(false);
  const [pliesProblem, setPliesProblem] = useState("");
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
    const followed = storedBond();
    if (followed) setKeptBond(followed);
    const carried = storedPlies();
    if (carried) setKeptPlies(carried);
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
  const followBond = useCallback(async () => {
    if (!apiBaseUrl) { setBondProblem("The analysis service is not set up on this page."); return; }
    setBondProblem(""); setFollowing(true);
    const started = repair;
    try {
      const bond = await followRepairBond(apiBaseUrl, started);
      const next = { repair: started, bond };
      setKeptBond(next); setKeep(true);
      try { browserStorage()?.setItem(REPAIR_BOND_KEY, JSON.stringify(next)); } catch { /* the run stays on the page; a reload forgets it */ }
    } catch (error) {
      setBondProblem(error instanceof StudioError ? error.message : "The bond could not be followed. Try again.");
    } finally {
      setFollowing(false);
    }
  }, [apiBaseUrl, repair]);
  // A ply run's jobs are looked at while they are queued or running: every PLIES_POLL_MS, a look that fails tried again up to
  // POLL_TRIES times. A job the service no longer has is forgotten. What is kept in this browser follows every look.
  const keepPlies = useCallback((next: KeptPlies | null) => {
    try {
      if (next) browserStorage()?.setItem(REPAIR_PLIES_KEY, JSON.stringify(next));
      else browserStorage()?.removeItem(REPAIR_PLIES_KEY);
    } catch { /* the run stays on the page; a reload forgets it */ }
  }, []);
  const underWay = [keptPlies?.run ?? null, keptPlies?.finer ?? null].filter(pliesUnderWay).map((job) => (job as RepairPliesJob).job_id).join(" ");
  useEffect(() => {
    if (!apiBaseUrl || !underWay) return;
    const controller = new AbortController();
    const timers: number[] = [];
    for (const jobId of underWay.split(" ")) {
      let failures = 0;
      const look = () => {
        getRepairPlies(apiBaseUrl, jobId, controller.signal).then((job) => {
          failures = 0;
          setPliesProblem("");
          setKeptPlies((kept) => {
            if (!kept) return kept;
            const next = kept.run.job_id === jobId ? { ...kept, run: job } : kept.finer?.job_id === jobId ? { ...kept, finer: job } : kept;
            if (next !== kept) keepPlies(next);
            return next;
          });
          if (pliesUnderWay(job)) timers.push(window.setTimeout(look, PLIES_POLL_MS));
        }).catch((error) => {
          if (controller.signal.aborted) return;
          if (error instanceof StudioError && error.status === 404) {
            setKeptPlies((kept) => {
              const next = !kept || kept.run.job_id === jobId ? null : kept.finer?.job_id === jobId ? { ...kept, finer: null } : kept;
              if (next !== kept) keepPlies(next);
              return next;
            });
            return;
          }
          failures += 1;
          if (failures < POLL_TRIES) { timers.push(window.setTimeout(look, PLIES_POLL_MS)); return; }
          setPliesProblem(error instanceof StudioError ? error.message : "The run's progress could not be read. Reload the page to see it.");
        });
      };
      look();
    }
    return () => { timers.forEach((timer) => window.clearTimeout(timer)); controller.abort("replaced"); };
  }, [apiBaseUrl, underWay, keepPlies]);
  const carryPlies = useCallback(async (finer: 0 | 1 = 0) => {
    if (!apiBaseUrl) { setPliesProblem("The analysis service is not set up on this page."); return; }
    const started = finer && keptPlies ? keptPlies.repair : repair; // a finer run is of the repair the first run carried
    if (finer && (!keptPlies || keptPlies.run.state !== "done" || !sameRepair(keptPlies.repair, repair))) return;
    setPliesProblem(""); setCarrying(true);
    try {
      const job = await startRepairPlies(apiBaseUrl, started, finer);
      const next: KeptPlies = finer && keptPlies ? { ...keptPlies, finer: job } : { repair: started, run: job, finer: null };
      setKeptPlies(next); setKeep(true); keepPlies(next);
    } catch (error) {
      setPliesProblem(error instanceof StudioError ? error.message : "The run could not be started. Try again.");
    } finally {
      setCarrying(false);
    }
  }, [apiBaseUrl, repair, keptPlies, keepPlies]);
  const pliesStale = useMemo(() => keptPlies !== null && !sameRepair(keptPlies.repair, repair), [keptPlies, repair]);
  const pliesNeeds = answer?.ply_needs ?? null;
  const bondStale = useMemo(() => keptBond !== null && !sameRepair(keptBond.repair, repair), [keptBond, repair]);
  const bondNeeds = answer?.bond_needs ?? null;
  const setCutFaces = useCallback((choice: CutFaces) => setCutFacesState(choice), []);
  const solveStale = useMemo(() => kept !== null && (!sameRepair(kept.repair, repair) || kept.cutFaces !== cutFaces), [kept, repair, cutFaces]);
  const adoptPlan = useCallback(({ repair: next, solve, bond }: { repair: RepairDescription; solve: { cutFaces: CutFaces; solve: RepairSolve } | null;
    bond: RepairBond | null }) => {
    replace(next);
    if (solve) {
      const solved: KeptSolve = { repair: next, cutFaces: solve.cutFaces, solve: solve.solve };
      setKept(solved); setCutFacesState(solve.cutFaces); setSolveProblem("");
      try { browserStorage()?.setItem(REPAIR_SOLVE_KEY, JSON.stringify(solved)); } catch { /* the solve stays on the page; a reload forgets it */ }
    }
    if (bond) {
      const followed: KeptBond = { repair: next, bond };
      setKeptBond(followed); setBondProblem("");
      try { browserStorage()?.setItem(REPAIR_BOND_KEY, JSON.stringify(followed)); } catch { /* the run stays on the page; a reload forgets it */ }
    }
  }, [replace]);

  const value = useMemo<RepairContextValue>(() => ({
    apiBaseUrl, repair, revision, setValue, replace, openFile, answer, stale: answered !== repair, working, problem,
    solve: kept?.solve ?? null, solveStale, solving, solveProblem, cutFaces, setCutFaces, solveSlice,
    bond: keptBond?.bond ?? null, bondStale, following, bondProblem, bondNeeds, followBond,
    plies: keptPlies?.run ?? null, pliesFiner: keptPlies?.finer ?? null, pliesStale, carrying, pliesProblem, pliesNeeds, carryPlies, adoptPlan,
  }), [apiBaseUrl, repair, revision, setValue, replace, openFile, answer, answered, working, problem, kept, solveStale, solving, solveProblem, cutFaces,
    setCutFaces, solveSlice, keptBond, bondStale, following, bondProblem, bondNeeds, followBond, keptPlies, pliesStale, carrying, pliesProblem, pliesNeeds,
    carryPlies, adoptPlan]);
  return <RepairContext.Provider value={value}>{children}</RepairContext.Provider>;
}

/** What the page holds when a message is answered (`RepairHeld`): the repair, its hand calculation, and each run of it that belongs to the
 * repair as it stands, with whether an older one is kept. */
export function heldOf(ctx: RepairContextValue): RepairHeld {
  const { repair, answer, solve, solveStale, bond, bondStale, bondNeeds, plies, pliesFiner, pliesStale, pliesNeeds } = ctx;
  return { repair, report: answer?.report ?? null, slice: solve && !solveStale ? solve.report : null, sliceStale: !!solve && solveStale, needs: answer?.needs ?? [],
    bond: bond && !bondStale ? bond.report : null, bondStale: !!bond && bondStale, bondNeeds,
    plies: plies?.state === "done" && !pliesStale ? plies.report : null, pliesFiner: pliesFiner?.state === "done" && !pliesStale ? pliesFiner.report : null,
    pliesStale: !!plies && pliesStale, pliesNeeds, pliesRunning: plies && pliesUnderWay(plies) && !pliesStale ? pliesProgress(plies) : null };
}

export function useRepair(): RepairContextValue {
  const value = useContext(RepairContext);
  if (!value) throw new Error("useRepair outside RepairProvider");
  return value;
}
