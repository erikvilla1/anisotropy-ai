"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchExplanation, fetchFields, getJob, POLL_MS, StudioError, type Explanation, type Fields, type JobStatus } from "@/lib/studio-api";
import { JobProgress } from "./job-progress";
import { ResultsView } from "./results-view";

/** The viewer window: one job by its id in the address, polled until it ends; the fields as soon as our engine has run. */
export function StudioViewer({ apiBaseUrl }: { apiBaseUrl: string }) {
  const params = useSearchParams();
  const jobId = params.get("job") ?? "";
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [message, setMessage] = useState("");
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
        if (status.state === "running") timer = window.setTimeout(poll, POLL_MS);
      } catch (error) {
        if (!cancelled) setMessage(error instanceof StudioError ? error.message : "The job could not be read.");
      }
    };
    poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [apiBaseUrl, jobId]);
  useEffect(() => {
    if (!job || !apiBaseUrl || !("fields" in job.outputs)) return;
    const stamp = `${job.job_id}:${job.state}`;
    if (loaded.current === stamp) return;
    loaded.current = stamp;
    (async () => {
      try {
        setFields(await fetchFields(apiBaseUrl, job.job_id));
        setExplanation("explanation" in job.outputs ? await fetchExplanation(apiBaseUrl, job.job_id) : null);
      } catch (error) {
        setMessage(error instanceof StudioError ? error.message : "The fields could not be read.");
      }
    })();
  }, [job, apiBaseUrl]);
  if (!jobId) return <p className="studio-alert">No job in the address: open this page from the studio's "Open the viewer in a new window" link.</p>;
  return (
    <div className="studio-viewer">
      {message ? <p className="studio-alert" role="alert">{message}</p> : null}
      {fields ? <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={null} /> : <p className="studio-status" role="status">Waiting for the fields of job {jobId.slice(0, 8)}…</p>}
      {job ? <JobProgress job={job} /> : null}
    </div>
  );
}
