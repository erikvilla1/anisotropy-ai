"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { answerMatches, buildProblem, type LaminateDraft, type ReportUnits } from "@/lib/laminate-chat";
import { laminateProjects, newLaminateProject, readProjects, reduceLaminate, upsert, writeProjects, type LaminateProject } from "@/lib/project-store";
import { solveLaminate, StudioError, type LaminateAnswer } from "@/lib/studio-api";
import { browserStorage } from "./project-context";
import { useNewestFromServer, useProjectSync } from "./project-sync";

/** What a solve came to: solved, refused by the page's own reading of the draft (a row missing or not a number), refused by the API
 * (with its status when it answered: 422 is a refusal of the problem, anything else an outage), or answered for another problem
 * (`mismatch`: the analysis ran, and its answer is not shown). */
export type SolveOutcome = { ok: true } | { ok: false; errors: string[] } | { ok: false; refused: string; status?: number; mismatch?: true };

/** What the page says when the answer that came back is not the answer to the problem it sent. */
export const ANSWER_MISMATCH = "The result did not match the problem; solve again.";

/** The laminate project the workspace edits and its answer, shared by the panels, the stack and the assistant (ADR-0062, part 5): the
 * draft lives in one place, each value with the unit it was typed in (ADR-0060), and a reload picks the last laminate project up. */
export type LaminateContextValue = {
  apiBaseUrl: string;
  project: LaminateProject;
  draft: LaminateDraft;
  restored: boolean;
  /** A change of the draft leaves the last answer behind: it answered another problem. */
  setDraft(next: LaminateDraft | ((draft: LaminateDraft) => LaminateDraft)): void;
  rename(name: string): void;
  answer: LaminateAnswer | null;
  solving: boolean;
  /** The API's refusal of the last solve, or empty. */
  problem: string;
  /** Counts the fresh solves (not the re-reports in another unit system), so the assistant can mark its answers. */
  stamp: number;
  solve(reportUnits?: ReportUnits): Promise<SolveOutcome>;
  reset(): void;
};

const LaminateContext = createContext<LaminateContextValue | null>(null);

function initial(): { project: LaminateProject; restored: boolean } {
  const kept = laminateProjects(readProjects(browserStorage()));
  return kept.length ? { project: kept[0], restored: true } : { project: newLaminateProject(), restored: false };
}

export function LaminateProvider({ apiBaseUrl, children }: { apiBaseUrl: string; children: ReactNode }) {
  const start = useRef<{ project: LaminateProject; restored: boolean } | null>(null);
  if (start.current === null) start.current = initial();
  const [project, setProject] = useState<LaminateProject>(start.current.project);
  const [answer, setAnswer] = useState<LaminateAnswer | null>(null);
  const [solving, setSolving] = useState(false);
  const [problem, setProblem] = useState("");
  const [stamp, setStamp] = useState(0);
  const projectRef = useRef(project);
  const answerRef = useRef(answer);
  useEffect(() => { projectRef.current = project; }, [project]);
  useEffect(() => { answerRef.current = answer; }, [answer]);

  useEffect(() => {
    const store = browserStorage();
    writeProjects(upsert(readProjects(store), project), store);
  }, [project]);

  const setDraft = useCallback((next: LaminateDraft | ((draft: LaminateDraft) => LaminateDraft)) => {
    setProject((p) => reduceLaminate(p, { type: "draft", draft: typeof next === "function" ? next(p.draft) : next }));
    setAnswer(null);
    setProblem("");
  }, []);
  const rename = useCallback((name: string) => setProject((p) => reduceLaminate(p, { type: "rename", name })), []);
  const reset = useCallback(() => { setProject(newLaminateProject()); setAnswer(null); setProblem(""); }, []);
  useProjectSync(apiBaseUrl, project); // the server's copy follows this browser's (ADR-0062 part 6)
  useNewestFromServer(apiBaseUrl, "laminate", !start.current.restored && project.updated === project.created,
    (found) => { if (found.kind === "laminate") setProject(found); });

  const solve = useCallback(async (reportUnits?: ReportUnits): Promise<SolveOutcome> => {
    const built = buildProblem(projectRef.current.draft, reportUnits ?? (answerRef.current?.report_units as ReportUnits | undefined));
    if (built.errors) return { ok: false, errors: built.errors };
    if (!apiBaseUrl) return { ok: false, refused: "Analysis is not available on this page. The problem can be stated but not solved." };
    setSolving(true); setProblem("");
    try {
      const solved = await solveLaminate(apiBaseUrl, built.problem);
      if (!answerMatches(built.problem, solved)) { // never shown beside a problem it does not answer
        setAnswer(null); setProblem(ANSWER_MISMATCH);
        return { ok: false, refused: ANSWER_MISMATCH, mismatch: true };
      }
      setAnswer(solved);
      if (!reportUnits) setStamp((s) => s + 1);
      return { ok: true };
    } catch (error) {
      const message = error instanceof StudioError ? error.message : "The solve failed.";
      setProblem(message);
      return { ok: false, refused: message, status: error instanceof StudioError ? error.status : undefined };
    } finally {
      setSolving(false);
    }
  }, [apiBaseUrl]);

  const value = useMemo<LaminateContextValue>(() => ({
    apiBaseUrl, project, draft: project.draft, restored: start.current?.restored ?? false, setDraft, rename, answer, solving, problem, stamp, solve, reset,
  }), [apiBaseUrl, project, setDraft, rename, answer, solving, problem, stamp, solve, reset]);
  return <LaminateContext.Provider value={value}>{children}</LaminateContext.Provider>;
}

export function useLaminate(): LaminateContextValue {
  const value = useContext(LaminateContext);
  if (!value) throw new Error("useLaminate needs a LaminateProvider above it");
  return value;
}
