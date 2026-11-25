"use client";

import { Check, X } from "lucide-react";
import { type JobStatus } from "@/lib/studio-api";
import { runDetail, runHeadline, runProblem, runSteps, runTook, secondsText, stepSeconds, verificationOf } from "@/lib/studio-copy";
import { QALine } from "./qa-line";

/** The run in five steps (ADR-0091): Queued, Meshing, Solving, Post-processing, Report ready, mapped from the pipeline's stages in
 * `lib/studio-copy.ts`; under each finished step the seconds it took, and once the run is done how long it took in all (ADR-0064
 * amendment 1); one line on what is happening, the verification line once the reference solver has run, and a stopped run in plain
 * words. The pipeline's stage names and console stay in the job's record. */
export function JobProgress({ job, brief = false, apiBase }: {
  job: JobStatus;
  /** the product's view: the second solver's check without its counts */ brief?: boolean;
  /** the API to read a done run's quality checks from (ADR-0137); without it, no quality line */ apiBase?: string;
}) {
  const steps = runSteps(job);
  const seconds = stepSeconds(job);
  const problem = runProblem(job);
  const detail = runDetail(job);
  const took = runTook(job);
  const check = job.state === "running" || job.state === "done" ? verificationOf(job.result ?? (job.state === "done" ? job.message : null), null, brief) : null;
  return (
    <div className="studio-panel studio-run" data-testid="job-progress" data-state={job.state}>
      <h3>Analysis <span className={`studio-badge studio-badge-${job.state}`} data-testid="job-state">{runHeadline(job)}</span></h3>
      <ol className="studio-stepper" aria-label="Progress">
        {steps.map((s) => (
          <li key={s.id} data-step={s.id} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="studio-step-mark" aria-hidden="true">{s.state === "done" ? <Check size={11} /> : s.state === "stopped" ? <X size={11} /> : null}</span>
            <span className="studio-step-label">{s.label}</span>
            {s.state === "done" && seconds[s.id] !== undefined ? (
              <span className="studio-step-time" data-testid={`step-time-${s.id}`}>{secondsText(seconds[s.id]!)}</span>
            ) : null}
          </li>
        ))}
      </ol>
      {detail ? <p className="studio-muted">{detail}</p> : null}
      {took ? <p className="studio-muted" data-testid="job-took">{took}</p> : null}
      {check ? <p className={check.verified ? "studio-ok" : "studio-warn"} data-testid="job-message">{check.line}</p> : null}
      {apiBase && job.state === "done" ? <QALine apiBase={apiBase} jobId={job.job_id} brief={brief} expected={Boolean(job.outputs?.qa)} /> : null}
      {problem ? <p className="studio-problem" role="alert" data-testid="job-problem">{problem}</p> : null}
    </div>
  );
}
