"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkSetup, fetchExplanation, fetchFields, getJob, isActive, liveSolve, POLL_MS, startSolve, StudioError,
  type CheckAnswer, type Explanation, type Fields, type JobStatus, type LiveAnswer,
} from "@/lib/studio-api";
import type { StudioValues } from "@/lib/studio-form";
import { liveKey } from "@/lib/studio-live";

/** A coupon's run: the setup check, the job, its polling and its files, in one place for the chat and the form (ADR-0062). Every number
 * shown comes from the fea package through the API (ADR-0051); this hook only asks and keeps the answers. `check` and `solve` throw a
 * `StudioError` for the caller to word; a polling or reading failure lands in `problem` and is tried again a moment later, up to RETRIES
 * times per job, since the hosted API answers through a Worker and a container that can miss one request (seen live on 2026-11-07). */
export const RETRIES = 10;
export type CouponRun = {
  checking: boolean;
  checked: CheckAnswer | null;
  job: JobStatus | null;
  fields: Fields | null;
  explanation: Explanation | null;
  /** The job whose fields were read first; changes once per job, so a message can follow it. */
  loadedJob: string | null;
  problem: string;
  /** The live solve (ADR-0086): our kernel's last answer to the rows as they stood, the rows it answered, and whether one is on its way. */
  live: LiveAnswer | null;
  liveFor: string | null;
  living: boolean;
  /** When the live answer and the full run's fields arrived: the page shows the newer. */
  liveAt: number;
  fieldsAt: number;
  /** Ask our kernel for these rows; `key` names them (`liveKey`). A newer call aborts an older one. */
  solveLive(values: StudioValues, key: string): Promise<void>;
  /** The rows changed into a setup the kernel cannot answer yet: the last live answer no longer stands. */
  dropLive(): void;
  /** The rows moved on: the live answer on its way is not wanted; the last one shown stays until a newer comes. */
  cancelLive(): void;
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
  const [live, setLive] = useState<LiveAnswer | null>(null);
  const [liveFor, setLiveFor] = useState<string | null>(null);
  const [living, setLiving] = useState(false);
  const [liveAt, setLiveAt] = useState(0);
  const [fieldsAt, setFieldsAt] = useState(0);
  // The rows the shown check answered, and a count of explicit checks: a live answer for rows already checked, or one sent before the latest
  // check, leaves that check in place, so what was offered on it (the chat's Run) stays offered (ADR-0086).
  const checkedKey = useRef<string | null>(null);
  const checks = useRef(0);
  const liveAbort = useRef<AbortController | null>(null);
  const fieldsLoaded = useRef<string | null>(null);
  const readFor = useRef<string | null>(null); // the job whose fields have been read once, whatever the reads in between
  const aborts = useRef<AbortController[]>([]);
  const [tick, setTick] = useState(0); // a failed poll or read schedules another try
  const retries = useRef(0);
  const retry = useCallback(() => {
    if (retries.current >= RETRIES) return;
    retries.current += 1;
    window.setTimeout(() => setTick((t) => t + 1), POLL_MS);
  }, []);
  useEffect(() => () => aborts.current.forEach((c) => c.abort("unmount")), []);

  const check = useCallback(async (values: StudioValues) => {
    if (!apiBaseUrl) throw new StudioError("The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.");
    setChecking(true); setProblem("");
    const controller = new AbortController();
    aborts.current.push(controller);
    try {
      const answer = await checkSetup(apiBaseUrl, values, controller.signal, projectId);
      setChecked(answer);
      checkedKey.current = liveKey(values);
      checks.current += 1;
      return answer;
    } finally {
      setChecking(false);
    }
  }, [apiBaseUrl, projectId]);

  const solve = useCallback(async (values: StudioValues, runBy: string, replace: boolean) => {
    if (!apiBaseUrl) throw new StudioError("The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.");
    setProblem(""); setFields(null); setExplanation(null); fieldsLoaded.current = null; readFor.current = null;
    liveAbort.current?.abort("superseded"); liveAbort.current = null; setLiving(false); // the full run supersedes a live answer still on its way
    const started = await startSolve(apiBaseUrl, values, runBy, replace, undefined, projectId);
    retries.current = 0;
    setJob(started);
    return started;
  }, [apiBaseUrl, projectId]);

  const solveLive = useCallback(async (values: StudioValues, key: string) => {
    if (!apiBaseUrl) return;
    liveAbort.current?.abort("superseded");  // the rows moved on: the older answer is not wanted
    const controller = new AbortController();
    liveAbort.current = controller;
    setLiving(true);
    const checksBefore = checks.current;
    try {
      const answer = await liveSolve(apiBaseUrl, values, controller.signal, projectId);
      if (controller.signal.aborted) return;
      setLive(answer); setLiveFor(key); setLiveAt(Date.now()); setProblem("");
      if (checkedKey.current !== key && checks.current === checksBefore) { setChecked(answer); checkedKey.current = key; }
    } catch (error) {
      if (controller.signal.aborted) return;
      setProblem(error instanceof StudioError ? `The live preview failed: ${error.message}` : "The live preview failed.");
    } finally {
      if (liveAbort.current === controller) { liveAbort.current = null; setLiving(false); }
    }
  }, [apiBaseUrl, projectId]);
  const dropLive = useCallback(() => {
    liveAbort.current?.abort("superseded"); liveAbort.current = null;
    setLive(null); setLiveFor(null); setLiving(false);
  }, []);
  const cancelLive = useCallback(() => {
    liveAbort.current?.abort("superseded"); liveAbort.current = null; setLiving(false);
  }, []);
  useEffect(() => () => liveAbort.current?.abort("unmount"), []);

  const clearChecked = useCallback(() => { setChecked(null); checkedKey.current = null; }, []);
  const clearResults = useCallback(() => {
    setJob((current) => {
      if (isActive(current?.state)) return current;
      setFields(null); setExplanation(null); setLoadedJob(null); fieldsLoaded.current = null; readFor.current = null;
      return null;
    });
  }, []);
  const reset = useCallback(() => {
    setChecked(null); setJob(null); setFields(null); setExplanation(null); setLoadedJob(null); setProblem(""); fieldsLoaded.current = null; readFor.current = null;
    checkedKey.current = null;
    liveAbort.current?.abort("reset"); liveAbort.current = null; setLive(null); setLiveFor(null); setLiving(false);
  }, []);

  useEffect(() => {
    if (!job || !apiBaseUrl || !isActive(job.state)) return;
    const timer = window.setTimeout(async () => {
      try { setJob(await getJob(apiBaseUrl, job.job_id)); setProblem(""); }
      catch (error) { setProblem(error instanceof StudioError ? error.message : "The job's status could not be read."); retry(); }
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [job, apiBaseUrl, tick, retry]);

  useEffect(() => {
    if (!job || !apiBaseUrl || !("fields" in job.outputs)) return;
    const stamp = `${job.job_id}:${"explanation" in job.outputs}:${job.state}`; // the explanation and the final state arrive after the fields
    if (fieldsLoaded.current === stamp) return;
    fieldsLoaded.current = stamp;
    const controller = new AbortController();
    aborts.current.push(controller);
    (async () => {
      try {
        setFields(await fetchFields(apiBaseUrl, job.job_id, controller.signal));
        setFieldsAt(Date.now());
        setExplanation("explanation" in job.outputs ? await fetchExplanation(apiBaseUrl, job.job_id, controller.signal) : null);
        setProblem("");
        if (readFor.current !== job.job_id) { readFor.current = job.job_id; setLoadedJob(job.job_id); } // once per job, after a read that succeeded
      } catch (error) {
        if (controller.signal.aborted) return;
        setProblem(error instanceof StudioError ? error.message : "The results could not be read.");
        fieldsLoaded.current = null; // not read: the next tick tries again
        retry();
      }
    })();
  }, [job, apiBaseUrl, tick]);

  return { checking, checked, job, fields, explanation, loadedJob, problem, live, liveFor, living, liveAt, fieldsAt, solveLive, dropLive, cancelLive, check, solve,
    clearChecked, clearResults, reset, setProblem };
}
