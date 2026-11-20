"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { analyzeWing, getWingFeCheck, startWingFeCheck, StudioError, wakeSolver } from "@/lib/studio-api";
import { EXAMPLE_WING, withValue, type WingAnswer, type WingDescription, type WingFeCheck, type WingValue } from "@/lib/wing";
import { browserStorage } from "@/components/studio/project-context";

/** How long the page waits after the last change before it asks the engine: long enough not to send every keystroke, short enough to
 * feel immediate (ADR-0118). */
export const WING_SETTLE_MS = 350;
/** Where this browser keeps the wing being edited, so a reload picks it up. */
export const WING_STORAGE_KEY = "anisotropy.wing.v1";
/** Where this browser keeps the finite element check under way or last made, and the description it was started for (ADR-0119). */
export const WING_CHECK_KEY = "anisotropy.wing-check.v1";
/** How often the page asks how the check stands while it is queued or running. */
export const CHECK_POLL_MS = 2000;
const POLL_TRIES = 3; // a look that fails this many times running ends the following, with the reason; the check goes on without the page

export type WingContextValue = {
  apiBaseUrl: string;
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
  /** The page may start a check soon: on the hosted tier a machine is started now, so the check does not wait for one. */
  wakeChecks(): void;
};

const WingContext = createContext<WingContextValue | null>(null);

function stored(): WingDescription {
  try {
    const text = browserStorage()?.getItem(WING_STORAGE_KEY);
    const value: unknown = text ? JSON.parse(text) : null;
    if (value && typeof value === "object" && !Array.isArray(value) && "geometry" in value) return value as WingDescription;
  } catch { /* storage blocked or holding something else: start from the example */ }
  return EXAMPLE_WING;
}

function storedCheck(): { jobId: string; wing: WingDescription } | null {
  try {
    const value: unknown = JSON.parse(browserStorage()?.getItem(WING_CHECK_KEY) ?? "null");
    if (value && typeof value === "object" && "jobId" in value && "wing" in value && typeof value.jobId === "string" && value.wing && typeof value.wing === "object") {
      return { jobId: value.jobId, wing: value.wing as WingDescription };
    }
  } catch { /* storage blocked or holding something else: no check */ }
  return null;
}

const following = (check: WingFeCheck | null): boolean => check !== null && (check.state === "queued" || check.state === "running");

/** The wing the workspace edits and the engine's answer to it, shared by the setup, the drawings and the assistant (ADR-0118). Every
 * change is worked again once the typing settles; an answer that comes back for an older description than the newest is dropped. */
export function WingProvider({ apiBaseUrl, children }: { apiBaseUrl: string; children: ReactNode }) {
  const [wing, setWing] = useState<WingDescription>(EXAMPLE_WING);
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
    setWing(stored());
    setRevision((r) => r + 1);
    const check = storedCheck();
    if (check) { setFeWing(check.wing); setFeJob(check.jobId); }
    loaded.current = true;
  }, []);

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
    try { browserStorage()?.setItem(WING_STORAGE_KEY, JSON.stringify(wing)); } catch { /* storage full or blocked: the wing stays on the page */ }
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

  const setValue = useCallback((path: string, value: WingValue | undefined) => setWing((w) => withValue(w, path, value)), []);
  const replace = useCallback((next: WingDescription) => { setWing(next); setRevision((r) => r + 1); }, []);
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
  }, [apiBaseUrl]);

  const startFeCheck = useCallback(async () => {
    if (!apiBaseUrl) { setFeProblem("The analysis service is not set up on this page."); return; }
    setFeProblem("");
    const started = wing;
    try {
      const check = await startWingFeCheck(apiBaseUrl, started);
      setFeCheck(check); setFeWing(started); setFeJob(check.job_id);
      try { browserStorage()?.setItem(WING_CHECK_KEY, JSON.stringify({ jobId: check.job_id, wing: started })); } catch { /* the check goes on; a reload forgets it */ }
    } catch (error) {
      setFeProblem(error instanceof StudioError ? error.message : "The check could not be started. Try again.");
    }
  }, [apiBaseUrl, wing]);
  const wakeChecks = useCallback(() => {
    if (woken.current || !apiBaseUrl) return;
    woken.current = true;
    void wakeSolver(apiBaseUrl);
  }, [apiBaseUrl]);
  const feCheckStale = useMemo(() => feWing !== null && JSON.stringify(feWing) !== JSON.stringify(wing), [feWing, wing]);

  const value = useMemo<WingContextValue>(() => ({
    apiBaseUrl, wing, revision, setValue, replace, openFile, answer, stale: answered !== wing, working, problem,
    feCheck, feCheckStale, feProblem, startFeCheck, wakeChecks,
  }), [apiBaseUrl, wing, revision, setValue, replace, openFile, answer, answered, working, problem, feCheck, feCheckStale, feProblem, startFeCheck, wakeChecks]);
  return <WingContext.Provider value={value}>{children}</WingContext.Provider>;
}

export function useWing(): WingContextValue {
  const value = useContext(WingContext);
  if (!value) throw new Error("useWing outside WingProvider");
  return value;
}
