"use client";

import { runWhen } from "@/lib/run-history";
import { useProject } from "./project-context";
import { ResultsView } from "./results-view";

/** The centre of the workspace while a past analysis has it (ADR-0109): that run's results as it stored them. Every number is the fea
 * package's, of the day it ran; nothing is solved again to show it. */
export function PastStage({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { past, setPicked, place } = useProject();
  const { job, fields, explanation, busy, problem } = past;
  if (!job || !fields) {
    return (
      <section className="studio-output">
        <div className="studio-empty" data-testid="past-empty" data-state={busy ? "busy" : problem ? "failed" : "none"}>
          <h3>{busy ? "Opening the run" : "The run was not opened"}</h3>
          <p>{busy ? "Its results are read as it stored them." : problem || "Pick a run from your analyses."}</p>
        </div>
      </section>
    );
  }
  return (
    <section className="studio-output" data-testid="past-stage">
      <p className="studio-live-banner" data-testid="past-banner">
        <strong>Past run</strong> of {job.coupon}, {runWhen(job.finished_at ?? job.started_at)}. Shown as it was solved.
      </p>
      <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={null} showFiles={false} onPicked={setPicked} place={place} />
    </section>
  );
}
