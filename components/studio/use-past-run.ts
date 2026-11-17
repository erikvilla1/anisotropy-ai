"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchExplanation, fetchFields, fetchRunValues, getJob, StudioError, type Explanation, type Fields, type JobStatus } from "@/lib/studio-api";

/** A past analysis opened again (ADR-0109), beside the coupon the project sets up: while it is open the stage shows that run's results
 * as it stored them and the assistant answers from them; closing it returns to the project, whose rows it never touched. The page
 * computes nothing: it asks for the run's own files and keeps them, in this page alone. */
export type PastState = {
  /** A past run has the stage: its panel on the left, its results in the centre. */
  open: boolean;
  /** The run's files are being read. */
  busy: boolean;
  job: JobStatus | null;
  fields: Fields | null;
  explanation: Explanation | null;
  /** The rows the run ran on, as the studio edits them; null for a run from before they were kept, or when they could not be read. */
  values: Record<string, unknown> | null;
  /** A failure to reach or read the run, in words the page may show. */
  problem: string;
  show(jobId: string): Promise<void>;
  close(): void;
};

export function usePastRun(apiBaseUrl: string): PastState {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [values, setValues] = useState<Record<string, unknown> | null>(null);
  const [problem, setProblem] = useState("");
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort("unmount"), []);

  const close = useCallback(() => {
    abort.current?.abort("closed"); abort.current = null;
    setOpen(false); setBusy(false); setJob(null); setFields(null); setExplanation(null); setValues(null); setProblem("");
  }, []);
  const show = useCallback(async (jobId: string) => {
    if (!apiBaseUrl) return;
    abort.current?.abort("superseded");
    const controller = new AbortController();
    abort.current = controller;
    setOpen(true); setBusy(true); setProblem(""); setJob(null); setFields(null); setExplanation(null); setValues(null);
    try {
      const found = await getJob(apiBaseUrl, jobId, controller.signal);
      if (found.state !== "done" || !("fields" in found.outputs)) throw new StudioError("This run has no results to show. Run the analysis again from your project.");
      const read = await fetchFields(apiBaseUrl, jobId, controller.signal);
      const said = "explanation" in found.outputs ? await fetchExplanation(apiBaseUrl, jobId, controller.signal).catch(() => null) : null;
      // the run's own rows; without them the results still show, and the setup is not offered to be taken up
      const rows = "values" in found.outputs ? await fetchRunValues(apiBaseUrl, jobId, controller.signal).catch(() => null) : null;
      if (controller.signal.aborted) return;
      setJob(found); setFields(read); setExplanation(said); setValues(rows);
    } catch (error) {
      if (controller.signal.aborted) return;
      setProblem(error instanceof StudioError ? error.message : "The run could not be opened. Reload the page; if it happens again, contact us.");
    } finally {
      if (abort.current === controller) { abort.current = null; setBusy(false); }
    }
  }, [apiBaseUrl]);

  return useMemo(() => ({ open, busy, job, fields, explanation, values, problem, show, close }), [open, busy, job, fields, explanation, values, problem, show, close]);
}
