"use client";

import { isActive, type JobStatus } from "@/lib/studio-api";

const STAGES = ["the setup check", "the input", "the decks", "the attempt", "our engine", "CalculiX", "the CalculiX record", "the result", "the drawings",
  "the package", "the outputs"];

export function JobProgress({ job }: { job: JobStatus }) {
  const stages = job.stages.length ? job.stages : STAGES;
  const done = new Set(job.stages_done);
  const timings = job.timings ?? {};
  const seconds = (stage: string) => (typeof timings[stage] === "number" ? ` (${timings[stage].toFixed(1)} s)` : "");
  const solverSeconds = ["restore_s", "lock_wait_s", "gate_s", "upload_s"].filter((k) => typeof timings[k] === "number")
    .map((k) => `${k.replace("_s", "").replace("_", " ")} ${timings[k].toFixed(1)} s`).join(", ");
  return (
    <div className="studio-panel" data-testid="job-progress" data-state={job.state}>
      <h3>Solve <span className={`studio-badge studio-badge-${job.state}`}>{job.state}</span></h3>
      <p className="studio-muted">Job {job.job_id.slice(0, 8)}{job.coupon ? `, coupon ${job.coupon}` : ""}{job.attempt ? `, ${job.attempt.split("/").pop()}` : ""}.
        {job.state === "queued" ? " Waiting for a free solver; it starts by itself." : ""}
        {job.state === "running" && !job.result ? " Our engine's fields appear as soon as it has run; CalculiX and the record follow, then the drawings and the package." : ""}
        {job.state === "running" && job.result ? " The result is in; the drawings and the package are still being made, and appear under Outputs when written." : ""}</p>
      <ol className="studio-stages">
        {stages.map((stage) => {
          const state = done.has(stage) || (job.state === "done" && job.stage === stage) ? "done"
            : job.stage === stage && job.state === "running" ? "current" : job.stage === stage ? "stopped" : "waiting";
          return <li key={stage} data-state={state}><span aria-hidden="true">{state === "done" ? "✓" : state === "current" ? "▶" : state === "stopped" ? "✕" : "·"}</span> {stage}{seconds(stage)}</li>;
        })}
      </ol>
      {solverSeconds ? <p className="studio-muted" data-testid="solver-timings">Around the tool: {solverSeconds}.</p> : null}
      {job.message ? <p className={job.state === "done" || job.result ? "studio-ok" : isActive(job.state) ? "studio-muted" : "studio-problem"} data-testid="job-message">{job.message}</p> : null}
      {job.log_tail.length ? <details><summary>Console (last lines)</summary><pre className="studio-console">{job.log_tail.join("\n")}</pre></details> : null}
    </div>
  );
}
