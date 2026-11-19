"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { analyzeWing, StudioError } from "@/lib/studio-api";
import { EXAMPLE_WING, withValue, type WingAnswer, type WingDescription, type WingValue } from "@/lib/wing";
import { browserStorage } from "@/components/studio/project-context";

/** How long the page waits after the last change before it asks the engine: long enough not to send every keystroke, short enough to
 * feel immediate (ADR-0118). */
export const WING_SETTLE_MS = 350;
/** Where this browser keeps the wing being edited, so a reload picks it up. */
export const WING_STORAGE_KEY = "anisotropy.wing.v1";

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

  useEffect(() => { // after the first paint, so the server's page and the browser's first one agree
    setWing(stored());
    setRevision((r) => r + 1);
    loaded.current = true;
  }, []);

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

  const value = useMemo<WingContextValue>(() => ({
    apiBaseUrl, wing, revision, setValue, replace, openFile, answer, stale: answered !== wing, working, problem,
  }), [apiBaseUrl, wing, revision, setValue, replace, openFile, answer, answered, working, problem]);
  return <WingContext.Provider value={value}>{children}</WingContext.Provider>;
}

export function useWing(): WingContextValue {
  const value = useContext(WingContext);
  if (!value) throw new Error("useWing outside WingProvider");
  return value;
}
