"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { fetchExplanation, fetchFields, fieldsStamp, getJob, isActive, POLL_MS, StudioError, type Explanation, type Fields, type JobState, type JobStatus } from "@/lib/studio-api";
import { JobProgress } from "./job-progress";
import { ResultsView } from "./results-view";

/** The viewer window: one job by its id in the address, polled until it ends; the fields as soon as our engine has run. "Loading results…"
 * only while the job or its results are on their way; a job that ended without results says so, and a failed read says what failed with
 * "Try again" (audit fea-screens-16). A finished run's progress is one line here (audit fea-screens-31). */
export function StudioViewer({ apiBaseUrl }: { apiBaseUrl: string }) {
  const params = useSearchParams();
  const jobId = params.get("job") ?? "";
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [fieldsState, setFieldsState] = useState<JobState | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0); // "Try again" reads the job afresh
  const loaded = useRef<string | null>(null);
  useEffect(() => {
    if (!apiBaseUrl || !jobId) return;
    let cancelled = false;
    let timer = 0;
    const poll = async () => {
      try {
        const status = await getJob(apiBaseUrl, jobId);
        if (cancelled) return;
        setJob(status);
        if (isActive(status.state)) timer = window.setTimeout(poll, POLL_MS);
      } catch (error) {
        if (!cancelled) setMessage(error instanceof StudioError ? error.message : "The results could not be loaded. Try again.");
      }
    };
    poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [apiBaseUrl, jobId, attempt]);
  useEffect(() => {
    if (!job || !apiBaseUrl || !("fields" in job.outputs)) return;
    const stamp = `${fieldsStamp(job)}:${attempt}`; // read again once the reference solver's values are in them (fea-run-10), and on "Try again"
    if (loaded.current === stamp) return;
    loaded.current = stamp;
    (async () => {
      try {
        setFields(await fetchFields(apiBaseUrl, job.job_id));
        setFieldsState(job.state);
        setExplanation("explanation" in job.outputs ? await fetchExplanation(apiBaseUrl, job.job_id) : null);
      } catch (error) {
        setMessage(error instanceof StudioError ? error.message : "The results could not be loaded. Try again.");
      }
    })();
  }, [job, apiBaseUrl, attempt]);
  if (!jobId) {
    // no job in the address: a plain empty state that says where results come from and leads back (audit fea-screens-15)
    return (
      <div className="studio-empty studio-viewer-empty" data-testid="viewer-empty">
        <h2>No results open</h2>
        <p>Results open here from a finished analysis: open a project and choose Open results in a new window.</p>
        <Link className="studio-button" href="/workspace">Open your projects</Link>
      </div>
    );
  }
  if (!apiBaseUrl) return <p className="studio-status" data-testid="viewer-unavailable">Results are not available on this page.</p>;
  const ended = job !== null && !isActive(job.state);
  const waiting = !message && (job === null || ("fields" in job.outputs && !fields));
  const coupon = [fields?.coupon.test, fields?.coupon.layup].filter(Boolean).join(" · ");
  return (
    <div className="studio-viewer">
      {/* the panels' h3 headings sit under a section heading, as the workspace's columns do (audit fea-run-46, uiux-fea-screens-14) */}
      {job ? <h2 className="sr-only">The analysis and its results</h2> : null}
      {coupon ?<p className="studio-viewer-coupon" data-testid="viewer-coupon">{coupon.charAt(0).toUpperCase() + coupon.slice(1)}</p> : null}
      {/* a problem replaces the loading line, so a gone job does not say it is still loading (audit fea-screens-2) */}
      {message ? (
        <div className="studio-alert" data-testid="viewer-problem">
          <p role="alert">{message}</p>
          <button type="button" className="studio-button" onClick={() => { setMessage(""); loaded.current = null; setAttempt((n) => n + 1); }}>Try again</button>
        </div>
      ) : null}
      {job ? <JobProgress job={job} fields={fields} fieldsState={fieldsState} compact /> : null}
      {fields ? <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={null} />
        : waiting ? <p className="studio-status" role="status">Loading results…</p>
        : ended && !("fields" in job.outputs) ? <p className="studio-muted" data-testid="viewer-no-results">No results were produced.</p> : null}
    </div>
  );
}
