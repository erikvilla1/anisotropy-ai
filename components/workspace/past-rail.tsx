"use client";

import { answerWords, readJobAnswer, runWhen } from "@/lib/run-history";
import { printed } from "@/lib/studio-colors";
import { formFromValues } from "@/lib/studio-form";
import { plateFromValues } from "@/lib/studio-plate";
import { JobFiles, namingOf } from "@/components/studio/job-files";
import { today } from "@/components/studio/local";
import { useProject } from "@/components/studio/project-context";
import { StepPanel } from "./panels/step-panel";

/** The left column while a past analysis has the stage (ADR-0109): which run it is and its answer, its files, and its inputs to take up
 * again. The run is shown as it stored itself; the project's rows are changed only by "Use these inputs". */
export function PastRail({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { past, form, setForm, setPlate, setAnalysis, project, run, allTests } = useProject();
  const { job, fields, values, busy, problem } = past;
  const words = answerWords(readJobAnswer(job?.answer), printed);

  function takeUp() {
    if (!values) return;
    setForm({ ...formFromValues(values), filled_by: form.filled_by, date: today() });
    setPlate(plateFromValues(values));
    if (project.analysis === "none") setAnalysis("coupon"); // a blank FEA project takes the run's coupon (ADR-0124)
    run.reset(); // the project's last check and run were of other rows
    past.close();
  }

  return (
    <div className="studio-form ws-rail-panels" data-testid="past-rail">
      <div className="ws-rail-head">
        <p className="ws-setup-line">Past analysis</p>
        <div className="studio-actions">
          <button type="button" className="studio-text-button" onClick={past.close} data-testid="past-close">Back to the project</button>
        </div>
      </div>
      <StepPanel id="past-run" title="This run" state={job ? "pass" : problem ? "fail" : "none"} word="done">
        {job ? (
          <dl className="ws-import-facts" data-testid="past-facts">
            <dt>Coupon</dt><dd>{job.coupon}</dd>
            <dt>Finished</dt><dd>{runWhen(job.finished_at ?? job.started_at)}</dd>
            <dt>Answer</dt><dd data-testid="past-answer">{words ? `${words.verdict} at ${words.loading}` : "–"}</dd>
            {words ? <><dt>First to fail</dt><dd>{words.facts.join(" · ")}</dd></> : null}
          </dl>
        ) : null}
        {problem ? <p className="studio-alert" role="alert" data-testid="past-problem">{problem}</p> : null}
        <p className="studio-status" role="status" data-testid="past-status">
          {busy ? "Opening the run." : job ? "Shown as it was solved. Nothing here changes it." : ""}
        </p>
      </StepPanel>
      {job ? (
        <StepPanel id="past-files" title="Files">
          <JobFiles apiBase={apiBaseUrl} job={job} naming={namingOf(fields)} all={allTests} testId="past-files" />
        </StepPanel>
      ) : null}
      {job ? (
        <StepPanel id="past-inputs" title="Change and run again">
          {values ? (
            <>
              <div className="studio-buttons">
                <button type="button" className="studio-button studio-button-primary" onClick={takeUp} data-testid="past-use">Use these inputs</button>
              </div>
              <p className="studio-hint">Puts this run&apos;s inputs in your project, in place of the ones there now.</p>
            </>
          ) : <p className="studio-hint" data-testid="past-no-inputs">This run was made before inputs were kept with each run, so they cannot be put back from here.</p>}
        </StepPanel>
      ) : null}
    </div>
  );
}
