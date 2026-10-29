"use client";

import type { JobStatus } from "@/lib/studio-api";

const STAGES = ["the setup check", "the input", "the decks", "the attempt", "our engine", "CalculiX", "the CalculiX record", "the package", "the outputs"];

export function JobProgress({ job }: { job: JobStatus }) {
  const stages = job.stages.length ? job.stages : STAGES;
  const done = new Set(job.stages_done);
  return (
    <div className="studio-panel" data-testid="job-progress" data-state={job.state}>
      <h3>Solve <span className={`studio-badge studio-badge-${job.state}`}>{job.state}</span></h3>
      <p className="studio-muted">Job {job.job_id.slice(0, 8)}{job.coupon ? `, coupon ${job.coupon}` : ""}{job.attempt ? `, ${job.attempt.split("/").pop()}` : ""}.
        {job.state === "running" ? " Our engine's fields appear as soon as it has run; CalculiX, the record and the package follow." : ""}</p>
      <ol className="studio-stages">
        {stages.map((stage) => {
          const state = done.has(stage) || (job.state === "done" && job.stage === stage) ? "done"
            : job.stage === stage && job.state === "running" ? "current" : job.stage === stage ? "stopped" : "waiting";
          return <li key={stage} data-state={state}><span aria-hidden="true">{state === "done" ? "✓" : state === "current" ? "▶" : state === "stopped" ? "✕" : "·"}</span> {stage}</li>;
        })}
      </ol>
      {job.message ? <p className={job.state === "done" ? "studio-ok" : "studio-problem"} data-testid="job-message">{job.message}</p> : null}
      {job.log_tail.length ? <details><summary>Console (last lines)</summary><pre className="studio-console">{job.log_tail.join("\n")}</pre></details> : null}
    </div>
  );
}
