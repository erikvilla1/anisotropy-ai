"use client";

import { Check, X } from "lucide-react";
import { type JobStatus } from "@/lib/studio-api";
import { runDetail, runHeadline, runProblem, runSteps, verificationLine } from "@/lib/studio-copy";

/** The run in five steps (ADR-0091): Queued, Meshing, Solving, Post-processing, Report ready, mapped from the pipeline's stages in
 * `lib/studio-copy.ts`; one line on what is happening, the verification line once the reference solver has run, and a stopped run in
 * plain words. The pipeline's stage names, timings and console stay in the job's record. */
export function JobProgress({ job }: { job: JobStatus }) {
  const steps = runSteps(job);
  const problem = runProblem(job);
  const detail = runDetail(job);
  const verified = job.state === "running" || job.state === "done" ? verificationLine(job.result ?? (job.state === "done" ? job.message : null)) : null;
  return (
    <div className="studio-panel studio-run" data-testid="job-progress" data-state={job.state}>
      <h3>Analysis <span className={`studio-badge studio-badge-${job.state}`} data-testid="job-state">{runHeadline(job)}</span></h3>
      <ol className="studio-stepper" aria-label="Progress">
        {steps.map((s) => (
          <li key={s.id} data-step={s.id} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="studio-step-mark" aria-hidden="true">{s.state === "done" ? <Check size={11} /> : s.state === "stopped" ? <X size={11} /> : null}</span>
            <span className="studio-step-label">{s.label}</span>
          </li>
        ))}
      </ol>
      {detail ? <p className="studio-muted">{detail}</p> : null}
      {verified ? <p className="studio-ok" data-testid="job-message">{verified}</p> : null}
      {problem ? <p className="studio-problem" role="alert" data-testid="job-problem">{problem}</p> : null}
    </div>
  );
}
