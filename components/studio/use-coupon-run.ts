"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkSetup, fetchExplanation, fetchFields, getJob, POLL_MS, startSolve, StudioError,
  type CheckAnswer, type Explanation, type Fields, type JobStatus,
} from "@/lib/studio-api";
import type { StudioValues } from "@/lib/studio-form";

/** A coupon's run: the setup check, the job, its polling and its files, in one place for the chat and the form (ADR-0062). Every number
 * shown comes from the fea package through the API (ADR-0051); this hook only asks and keeps the answers. `check` and `solve` throw a
 * `StudioError` for the caller to word; a polling or reading failure lands in `problem`. */
export type CouponRun = {
  checking: boolean;
  checked: CheckAnswer | null;
  job: JobStatus | null;
  fields: Fields | null;
  explanation: Explanation | null;
  /** The job whose fields were read first; changes once per job, so a message can follow it. */
  loadedJob: string | null;
  problem: string;
  check(values: StudioValues): Promise<CheckAnswer>;
  solve(values: StudioValues, runBy: string, replace: boolean): Promise<JobStatus>;
  /** A changed setup: the check no longer stands. */
  clearChecked(): void;
  /** The results of the last run are left behind; a run still going keeps its progress. */
  clearResults(): void;
  /** Everything gone: a new coupon. */
  reset(): void;
  setProblem(text: string): void;
};

export function useCouponRun(apiBaseUrl: string, projectId: string | null = null): CouponRun {
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState<CheckAnswer | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [loadedJob, setLoadedJob] = useState<string | null>(null);
  const [problem, setProblem] = useState("");
  const fieldsLoaded = useRef<string | null>(null);
  const aborts = useRef<AbortController[]>([]);
  useEffect(() => () => aborts.current.forEach((c) => c.abort("unmount")), []);

  const check = useCallback(async (values: StudioValues) => {
    if (!apiBaseUrl) throw new StudioError("The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.");
    setChecking(true); setProblem("");
    const controller = new AbortController();
    aborts.current.push(controller);
    try {
      const answer = await checkSetup(apiBaseUrl, values, controller.signal, projectId);
      setChecked(answer);
      return answer;
    } finally {
      setChecking(false);
    }
  }, [apiBaseUrl, projectId]);

  const solve = useCallback(async (values: StudioValues, runBy: string, replace: boolean) => {
    if (!apiBaseUrl) throw new StudioError("The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.");
    setProblem(""); setFields(null); setExplanation(null); fieldsLoaded.current = null;
    const started = await startSolve(apiBaseUrl, values, runBy, replace, undefined, projectId);
    setJob(started);
    return started;
  }, [apiBaseUrl, projectId]);

  const clearChecked = useCallback(() => setChecked(null), []);
  const clearResults = useCallback(() => {
    setJob((current) => {
      if (current?.state === "running") return current;
      setFields(null); setExplanation(null); setLoadedJob(null); fieldsLoaded.current = null;
      return null;
    });
  }, []);
  const reset = useCallback(() => {
    setChecked(null); setJob(null); setFields(null); setExplanation(null); setLoadedJob(null); setProblem(""); fieldsLoaded.current = null;
  }, []);

  useEffect(() => {
    if (!job || !apiBaseUrl || job.state !== "running") return;
    const timer = window.setTimeout(async () => {
      try { setJob(await getJob(apiBaseUrl, job.job_id)); }
      catch (error) { setProblem(error instanceof StudioError ? error.message : "The job's status could not be read."); }
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [job, apiBaseUrl]);

  useEffect(() => {
    if (!job || !apiBaseUrl || !("fields" in job.outputs)) return;
    const stamp = `${job.job_id}:${"explanation" in job.outputs}:${job.state}`; // the explanation and the final state arrive after the fields
    if (fieldsLoaded.current === stamp) return;
    const first = fieldsLoaded.current === null || !fieldsLoaded.current.startsWith(job.job_id);
    fieldsLoaded.current = stamp;
    const controller = new AbortController();
    aborts.current.push(controller);
    (async () => {
      try {
        setFields(await fetchFields(apiBaseUrl, job.job_id, controller.signal));
        setExplanation("explanation" in job.outputs ? await fetchExplanation(apiBaseUrl, job.job_id, controller.signal) : null);
        if (first) setLoadedJob(job.job_id);
      } catch (error) {
        if (!controller.signal.aborted) setProblem(error instanceof StudioError ? error.message : "The results could not be read.");
      }
    })();
  }, [job, apiBaseUrl]);

  return { checking, checked, job, fields, explanation, loadedJob, problem, check, solve, clearChecked, clearResults, reset, setProblem };
}
