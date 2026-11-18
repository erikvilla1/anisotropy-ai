"use client";

import { importProblemWords } from "@/lib/studio-copy";
import { PreviewScene } from "./coupon-studio";
import { useProject } from "./project-context";
import { ResultsView } from "./results-view";

/** The centre of the workspace while a model brought in as a file has it (ADR-0105): the results when it was solved, the model as read
 * when it was not, and why when the file was refused. Every number is the fea package's, on the file as it stands. */
export function ImportedStage({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { imported, setPicked, place } = useProject();
  const { model, busy } = imported;
  if (!model || model.state === "refused") {
    return (
      <section className="studio-output">
        <div className="studio-empty" data-testid="import-empty" data-state={busy ? "busy" : model ? "refused" : "none"}>
          <h3>{busy ? "Reading the model" : model ? "The file was not read" : "No model yet"}</h3>
          <p>{busy ? "The file is read and solved as it stands." : model ? importProblemWords(model) : "Choose an Abaqus input file (.inp) and the units it is written in."}</p>
        </div>
      </section>
    );
  }
  const seconds = model.seconds < 10 ? model.seconds.toFixed(1) : String(Math.round(model.seconds));
  return (
    <section className="studio-output" data-testid="import-stage" data-state={model.state}>
      {model.state === "solved" && model.fields ? (
        <>
          <p className="studio-live-banner" data-testid="import-banner">
            <strong>Imported model</strong> ({seconds} s). Solved as the file states it: no mesh study, and not checked against a second solver.
          </p>
          <ResultsView fields={model.fields} explanation={model.explanation} job={null} apiBase={apiBaseUrl} preview={model.preview} showFiles={false}
            onPicked={setPicked} place={place} />
        </>
      ) : (
        <>
          <p className="studio-alert" role="alert" data-testid="import-unsolved">{importProblemWords(model)}</p>
          {model.preview ? <PreviewScene preview={model.preview} /> : null}
        </>
      )}
    </section>
  );
}
