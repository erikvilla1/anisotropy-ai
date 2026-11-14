"use client";

import Link from "next/link";
import { Check, RotateCcw, X } from "lucide-react";
import { type Fields, type JobState, type JobStatus } from "@/lib/studio-api";
import { RUN_STEPS, runDetail, runHeadline, runProblem, runSteps, runVerification, type StepState } from "@/lib/studio-copy";

/** What a screen reader hears after each step's name: the state the marks show (audit fea-run-20). */
const STEP_STATE_WORDS: Record<StepState, string> = { done: ", done", current: ", in progress", stopped: ", stopped", waiting: ", not started" };

/** A problem's sentence with its "contact us" a link to the contact page (audit fea-run-18). */
export function withContactLink(text: string) {
  const at = text.indexOf("contact us");
  if (at < 0) return text;
  return <>{text.slice(0, at)}<Link href="/contact">contact us</Link>{text.slice(at + "contact us".length)}</>;
}

/** The run in five steps (ADR-0091): Queued, Meshing, Solving, Post-processing, Report ready, mapped from the pipeline's stages in
 * `lib/studio-copy.ts`; one line on what is happening, the verification line once the reference solver has run, and a stopped run in
 * plain words, said here once with "Run again" (the rail and the assistant point here). The step being worked on reads what it does
 * ("Writing the report"), and each step tells a screen reader its state. `compact`, the viewer's finished run: one line. The pipeline's
 * stage names, timings and console stay in the job's record. */
export function JobProgress({ job, fields, fieldsState, onRetry, retryProblem = "", compact = false }: {
  job: JobStatus;
  /** The fields read for this job, and the job's state when they were read. */
  fields?: Fields | null; fieldsState?: JobState | null;
  /** Runs a stopped analysis again with the same inputs; absent where the page cannot (the viewer). */
  onRetry?: () => void;
  /** Why the last Run again did not start, said under its button (round-2 review N9). */
  retryProblem?: string;
  compact?: boolean;
}) {
  const steps = runSteps(job);
  const problem = runProblem(job);
  const detail = runDetail(job);
  const check = runVerification(job, fields, fieldsState);
  if (compact && job.state === "done" && !problem) {
    return (
      <div className="studio-panel studio-run studio-run-compact" data-testid="job-progress" data-state={job.state}>
        <p><strong>Analysis complete</strong>{check ? <> · <span className={check.verified ? "studio-ok" : "studio-warn"} data-testid="job-message">{check.line}</span></> : null}</p>
      </div>
    );
  }
  return (
    <div className="studio-panel studio-run" data-testid="job-progress" data-state={job.state}>
      <div className="studio-run-head">
        <h3>Analysis</h3>
        <span className={`studio-badge studio-badge-${job.state}`} data-testid="job-state">{runHeadline(job)}</span>
      </div>
      <ol className="studio-stepper" aria-label="Progress">
        {steps.map((s) => (
          <li key={s.id} data-step={s.id} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="studio-step-mark" aria-hidden="true">{s.state === "done" ? <Check size={11} /> : s.state === "stopped" ? <X size={11} /> : null}</span>
            <span className="studio-step-label">{s.state === "current" ? RUN_STEPS.find((r) => r.id === s.id)?.doing ?? s.label : s.label}</span>
            <span className="sr-only">{STEP_STATE_WORDS[s.state]}</span>
          </li>
        ))}
      </ol>
      <div className="studio-run-lines">
        {detail ? <p className="studio-muted">{detail}</p> : null}
        {check ? <p className={check.verified ? "studio-ok" : "studio-warn"} data-testid="job-message">{check.line}</p> : null}
        {problem ? <p className="studio-problem" data-testid="job-problem">{withContactLink(problem)}</p> : null}
        {job.state === "stopped" && onRetry ? (
          <button type="button" className="studio-button studio-run-again" onClick={onRetry} data-testid="run-again"><RotateCcw size={13} aria-hidden="true" /> Run again</button>
        ) : null}
        {job.state === "stopped" && onRetry && retryProblem ? <p className="studio-problem" role="alert" data-testid="run-again-problem">{withContactLink(retryProblem)}</p> : null}
      </div>
    </div>
  );
}
