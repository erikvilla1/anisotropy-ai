"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { isUuid, newWingProject, readProjects, reduceWing, upsert, wingProjects, writeProjects, type WingProject } from "@/lib/project-store";
import { analyzeWing, getWingFeCheck, startWingFeCheck, StudioError, wakeSolver } from "@/lib/studio-api";
import { EXAMPLE_WING, feWords, withValue, type WingAnswer, type WingDescription, type WingFeCheck, type WingValue } from "@/lib/wing";
import { wingKey } from "@/lib/wing-versions";
import { browserStorage } from "@/components/studio/project-context";
import { useNewestFromServer, useProjectSync } from "@/components/studio/project-sync";
import { useWingVersions, type WingVersions } from "./use-wing-versions";

/** How long the page waits after the last change before it asks the engine: long enough not to send every keystroke, short enough to
 * feel immediate (ADR-0118). */
export const WING_SETTLE_MS = 350;
/** Where this browser kept its one wing before a wing was a project (ADR-0118); read once, to make it the first wing project (ADR-0122). */
export const WING_STORAGE_KEY = "anisotropy.wing.v1";
/** Where this browser keeps the finite element check under way or last made, the wing project and the description it was started for
 * (ADR-0119, ADR-0122). */
export const WING_CHECK_KEY = "anisotropy.wing-check.v1";
/** How often the page asks how the check stands while it is queued or running. */
export const CHECK_POLL_MS = 2000;
const POLL_TRIES = 3; // a look that fails this many times running ends the following, with the reason; the check goes on without the page

export type WingContextValue = {
  apiBaseUrl: string;
  /** The wing project the page edits (ADR-0122): kept in this browser's list of projects and on the server like a coupon's. */
  project: WingProject;
  /** Its versions, newest last; any can be gone back to (ADR-0122, as ADR-0113). */
  versions: WingVersions;
  /** The project is kept in this browser and on the server: opened from the list, brought over, or changed. */
  kept: boolean;
  wing: WingDescription;
  /** Counts the times the whole description was replaced (an opened file, the example), so the fields show the new values. */
  revision: number;
  setValue(path: string, value: WingValue | undefined): void;
  replace(wing: WingDescription): void;
  /** Reads a wing file through the engine: the description it holds, worked at once; a file the engine refuses changes nothing. */
  openFile(text: string): Promise<string | null>;
  /** The engine's answer to the description as it stands, or to the last description it could work. */
  answer: WingAnswer | null;
  /** The answer is for an earlier description: the newest one is being worked, or was refused. */
  stale: boolean;
  working: boolean;
  /** The engine's refusal of the newest description, in its words, or empty. */
  problem: string;
  /** The finite element check under way or last made (ADR-0119), and whether the wing has changed since it was started. */
  feCheck: WingFeCheck | null;
  feCheckStale: boolean;
  /** Why a check could not be started or followed, in the page's words, or empty. */
  feProblem: string;
  startFeCheck(): Promise<void>;
  /** A plan's approval taken (ADR-0144, step 5): the wing the server changed, kept as a version by the assistant with the sentence as
   * why; the hand calculation the plan carried, shown as the page's own answer; and the check it started, followed as one started here. */
  adoptPlan(next: { wing: WingDescription; why: string; answer: WingAnswer | null; check: WingFeCheck | null }): void;
  /** The page may start a check soon: on the hosted tier a machine is started now, so the check does not wait for one. */
  wakeChecks(): void;
};

const WingContext = createContext<WingContextValue | null>(null);

/** The wing this browser kept before a wing was a project, or null. */
function legacyWing(): WingDescription | null {
  try {
    const text = browserStorage()?.getItem(WING_STORAGE_KEY);
    const value: unknown = text ? JSON.parse(text) : null;
    if (value && typeof value === "object" && !Array.isArray(value) && "geometry" in value) return value as WingDescription;
  } catch { /* storage blocked or holding something else: nothing to bring over */ }
  return null;
}

type KeptCheck = { project: string | null; jobId: string; wing: WingDescription };

function storedCheck(): KeptCheck | null {
  try {
    const value: unknown = JSON.parse(browserStorage()?.getItem(WING_CHECK_KEY) ?? "null");
    if (value && typeof value === "object" && "jobId" in value && "wing" in value && typeof value.jobId === "string" && value.wing && typeof value.wing === "object") {
      const project = "project" in value && typeof value.project === "string" ? value.project : null; // none: kept before ADR-0122
      return { project, jobId: value.jobId, wing: value.wing as WingDescription };
    }
  } catch { /* storage blocked or holding something else: no check */ }
  return null;
}

/** The wing project the page opens: the last one this browser changed or opened from the list of projects; with none, the wing it kept
 * before a wing was a project, as a project of its own; with neither, the example, which is kept only once it is changed. */
function opening(): { project: WingProject; kept: boolean; legacy: boolean } {
  const store = browserStorage();
  const kept = wingProjects(readProjects(store));
  if (kept.length) return { project: kept[0], kept: true, legacy: false };
  const legacy = legacyWing();
  if (!legacy) return { project: newWingProject(EXAMPLE_WING), kept: false, legacy: false };
  const project = newWingProject(legacy);
  if (writeProjects(upsert(readProjects(store), project), store)) {
    try { store?.removeItem(WING_STORAGE_KEY); } catch { /* it is read again next time, and found kept */ }
  }
  return { project, kept: true, legacy: true };
}

/** Before the page has read this browser's storage: a wing that is neither kept nor sent (its id is no project's). */
const OPENING: WingProject = { id: "opening", kind: "wing", name: "", wing: EXAMPLE_WING, created: "", updated: "" };

const following = (check: WingFeCheck | null): boolean => check !== null && (check.state === "queued" || check.state === "running");

/** The wing the workspace edits and the engine's answer to it, shared by the setup, the drawings and the assistant (ADR-0118). The wing
 * is a project (ADR-0122): kept in this browser's list of projects and, a moment after each change, on the server under the signed-in
 * email, with its versions in this browser. Every change is worked again once the typing settles; an answer that comes back for an
 * older description than the newest is dropped. */
export function WingProvider({ apiBaseUrl, children }: { apiBaseUrl: string; children: ReactNode }) {
  const [project, setProject] = useState<WingProject>(OPENING);
  const [keep, setKeep] = useState(false); // the project is kept and sent: opened from the list, brought over, or changed
  const [fresh, setFresh] = useState(false); // nothing was kept in this browser: the newest wing on the server is offered
  const wing = project.wing;
  const setWing = useCallback((next: WingDescription | ((w: WingDescription) => WingDescription)) => {
    setProject((p) => reduceWing(p, { type: "wing", wing: typeof next === "function" ? next(p.wing) : next }));
    setKeep(true);
  }, []);
  const [revision, setRevision] = useState(0);
  const [answer, setAnswer] = useState<WingAnswer | null>(null);
  const [answered, setAnswered] = useState<WingDescription | null>(null);
  const [working, setWorking] = useState(false);
  const [problem, setProblem] = useState("");
  const loaded = useRef(false);
  const worked = useRef<WingDescription | null>(null); // the description the shown answer belongs to, so an opened file is not worked twice
  const [feCheck, setFeCheck] = useState<WingFeCheck | null>(null);
  const [feWing, setFeWing] = useState<WingDescription | null>(null);
  const [feProblem, setFeProblem] = useState("");
  const [feJob, setFeJob] = useState<string | null>(null);
  const woken = useRef(false);

  useEffect(() => { // after the first paint, so the server's page and the browser's first one agree
    const opened = opening();
    setProject(opened.project); setKeep(opened.kept); setFresh(!opened.kept);
    setRevision((r) => r + 1);
    const check = storedCheck();
    if (check && (check.project === opened.project.id || (check.project === null && opened.legacy))) { setFeWing(check.wing); setFeJob(check.jobId); }
    loaded.current = true;
  }, []);
  useEffect(() => { // this browser's list of projects follows the wing, which goes to its front
    if (!keep) return;
    const store = browserStorage();
    writeProjects(upsert(readProjects(store), project), store);
  }, [project, keep]);
  useProjectSync(apiBaseUrl, keep ? project : OPENING); // the server's copy follows this browser's (ADR-0062 part 6)
  const kept = useRef(keep);
  useEffect(() => { kept.current = keep; }, [keep]);
  useNewestFromServer(apiBaseUrl, "wing", fresh && !keep, (found) => {
    if (found.kind !== "wing" || kept.current) return; // typing started before the server answered: the engineer's wing stands
    setProject(found); setKeep(true); setRevision((r) => r + 1);
  });

  // The check is followed while it is queued or running, and read once when the page opens with one kept: every CHECK_POLL_MS, a
  // look that fails tried again up to POLL_TRIES times. A check the service no longer has is forgotten.
  useEffect(() => {
    if (!apiBaseUrl || !feJob) return;
    const controller = new AbortController();
    let timer = 0, failures = 0;
    const look = () => {
      getWingFeCheck(apiBaseUrl, feJob, controller.signal).then((check) => {
        failures = 0;
        setFeCheck(check); setFeProblem("");
        if (following(check)) timer = window.setTimeout(look, CHECK_POLL_MS);
      }).catch((error) => {
        if (controller.signal.aborted) return;
        if (error instanceof StudioError && error.status === 404) {
          setFeCheck(null); setFeJob(null); setFeWing(null);
          try { browserStorage()?.removeItem(WING_CHECK_KEY); } catch { /* nothing kept */ }
          return;
        }
        failures += 1;
        if (failures < POLL_TRIES) { timer = window.setTimeout(look, CHECK_POLL_MS); return; }
        setFeProblem(error instanceof StudioError ? error.message : "The check's progress could not be read. Reload the page to see it.");
      });
    };
    look();
    return () => { window.clearTimeout(timer); controller.abort("replaced"); };
  }, [apiBaseUrl, feJob]);

  useEffect(() => {
    if (!loaded.current) return;
    if (!apiBaseUrl) { setProblem("The analysis service is not set up on this page."); return; }
    if (worked.current === wing) { setWorking(false); return; }
    const controller = new AbortController();
    setWorking(true);
    const timer = window.setTimeout(() => {
      analyzeWing(apiBaseUrl, { wing }, controller.signal).then((found) => {
        worked.current = wing; setAnswer(found); setAnswered(wing); setProblem("");
      }).catch((error) => {
        if (controller.signal.aborted) return;
        setProblem(error instanceof StudioError ? error.message : "The wing could not be worked. Try again.");
      }).finally(() => { if (!controller.signal.aborted) setWorking(false); });
    }, WING_SETTLE_MS);
    return () => { window.clearTimeout(timer); controller.abort("replaced"); };
  }, [apiBaseUrl, wing]);

  const setValue = useCallback((path: string, value: WingValue | undefined) => setWing((w) => withValue(w, path, value)), [setWing]);
  const replace = useCallback((next: WingDescription) => { setWing(next); setRevision((r) => r + 1); }, [setWing]);
  const versions = useWingVersions(project.id, keep, wing, replace);
  const openFile = useCallback(async (text: string): Promise<string | null> => {
    if (!apiBaseUrl) return "The analysis service is not set up on this page.";
    try {
      const found = await analyzeWing(apiBaseUrl, { toml: text });
      worked.current = found.wing;
      setWing(found.wing); setRevision((r) => r + 1); setAnswer(found); setAnswered(found.wing); setProblem("");
      return null;
    } catch (error) {
      return error instanceof StudioError ? error.message : "The file could not be read. Try again.";
    }
  }, [apiBaseUrl, setWing]);

  const startFeCheck = useCallback(async () => {
    if (!apiBaseUrl) { setFeProblem("The analysis service is not set up on this page."); return; }
    setFeProblem("");
    const started = wing;
    try {
      // the check names the wing project, which the server ignores until it keeps it; a check started keeps the wing from then on
      const check = await startWingFeCheck(apiBaseUrl, started, isUuid(project.id) ? project.id : null);
      setFeCheck(check); setFeWing(started); setFeJob(check.job_id); setKeep(true);
      versions.checked(check.job_id);
      try { browserStorage()?.setItem(WING_CHECK_KEY, JSON.stringify({ project: project.id, jobId: check.job_id, wing: started })); } catch { /* the check goes on; a reload forgets it */ }
    } catch (error) {
      setFeProblem(error instanceof StudioError ? error.message : "The check could not be started. Try again.");
    }
  }, [apiBaseUrl, wing, project.id, versions]);
  // a check's headline, once it has one, is kept on the version it was started from
  const doneReport = feCheck?.state === "done" ? feCheck.report : null;
  const checkedVersion = versions.checked;
  useEffect(() => {
    if (feCheck && doneReport) checkedVersion(feCheck.job_id, feWords(doneReport).headline);
  }, [doneReport]); // eslint-disable-line react-hooks/exhaustive-deps
  const wakeChecks = useCallback(() => {
    if (woken.current || !apiBaseUrl) return;
    woken.current = true;
    void wakeSolver(apiBaseUrl);
  }, [apiBaseUrl]);
  const feCheckStale = useMemo(() => feWing !== null && JSON.stringify(feWing) !== JSON.stringify(wing), [feWing, wing]);

  // a plan's check marks the version it was started from once the plan's wing is the page's, so the version marked is the wing it changed
  const marking = useRef<{ wing: string; job: string } | null>(null);
  const adoptPlan = useCallback(({ wing: next, why, answer: found, check }: { wing: WingDescription; why: string; answer: WingAnswer | null;
    check: WingFeCheck | null }) => {
    versions.attribute("assistant", why); // the version this makes says who made it and from which sentence
    if (found && wingKey(found.wing) === wingKey(next)) { worked.current = next; setAnswer(found); setAnswered(next); setProblem(""); }
    setWing(next); setRevision((r) => r + 1);
    if (!check) return;
    setFeCheck(check); setFeWing(next); setFeJob(check.job_id); setFeProblem("");
    marking.current = { wing: wingKey(next), job: check.job_id };
    try { browserStorage()?.setItem(WING_CHECK_KEY, JSON.stringify({ project: project.id, jobId: check.job_id, wing: next })); } catch { /* the check goes on; a reload forgets it */ }
  }, [versions, setWing, project.id]);
  const markChecked = versions.checked;
  useEffect(() => {
    const mark = marking.current;
    if (!mark || mark.wing !== wingKey(wing)) return;
    marking.current = null;
    markChecked(mark.job);
  }, [wing, markChecked]);

  const value = useMemo<WingContextValue>(() => ({
    apiBaseUrl, project, versions, kept: keep, wing, revision, setValue, replace, openFile, answer, stale: answered !== wing, working, problem,
    feCheck, feCheckStale, feProblem, startFeCheck, adoptPlan, wakeChecks,
  }), [apiBaseUrl, project, versions, keep, wing, revision, setValue, replace, openFile, answer, answered, working, problem, feCheck, feCheckStale, feProblem,
    startFeCheck, adoptPlan, wakeChecks]);
  return <WingContext.Provider value={value}>{children}</WingContext.Provider>;
}

export function useWing(): WingContextValue {
  const value = useContext(WingContext);
  if (!value) throw new Error("useWing outside WingProvider");
  return value;
}
