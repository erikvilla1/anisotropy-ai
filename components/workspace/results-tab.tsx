"use client";

import { useState } from "react";
import { answerStat } from "@/lib/studio-answer";
import { printed } from "@/lib/studio-colors";
import { downloadable, setWords } from "@/lib/studio-copy";
import { fieldOptions } from "@/lib/studio-fields";
import { layupNotation } from "@/lib/studio-chat";
import { JobFiles, namingOf } from "@/components/studio/job-files";
import { useProject } from "@/components/studio/project-context";
import { resultsOnPage } from "@/components/studio/use-imported-model";

/** The fields the Results tab offers to colour the model by, in this order, where the result has them: the answer first, then the
 * deformation, then each ply's stresses and strains in its fibre axes. The viewer under the model still offers every field. */
export const TREE_FIELDS = ["failure_index", "u_mag", "u_z", "S11", "S22", "S12", "E11", "E22", "E12"];

/** The Results tab of the model tree (ADR-0111): the answer in three lines, buttons that colour the model by a field and a ply, and the
 * report and files once the run has ended; for an imported model, its results and no files. Every number is the result's own (the fields
 * the package wrote); the page computes none. */
export function ResultsTab({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { run: runner, form, imported, past, shownField, showField } = useProject();
  const { fields, live, readOnly } = resultsOnPage(runner, imported, past); // an imported model's own results while it is open (ADR-0105)
  const job = readOnly ? null : runner.job;
  const [ply, setPly] = useState(1);
  const available = downloadable(job, false); // the product's view: the customer's files (D4), once the run has ended (ADR-0064 amendment 2)
  const files = job && available.length ? (
    <JobFiles apiBase={apiBaseUrl} job={job} naming={namingOf(runner.fields, form, layupNotation(form))} testId="tension-files" />
  ) : null;
  if (!fields) {
    return files ?? <p className="studio-hint">{readOnly ? "No results: the model was read, not solved." : "The results appear here and on the model when the analysis has run."}</p>;
  }
  const s = fields.summary, lab = fields.labels;
  const stat = answerStat(fields, printed);
  const options = fieldOptions(fields);
  const offered = TREE_FIELDS.map((id) => options.find((o) => o.id === id)).filter((o) => o !== undefined);
  const angles = fields.mesh.angles ?? [];
  const perPlyShown = options.find((o) => o.id === shownField?.id)?.perPly ?? false;
  const shownPly = perPlyShown && shownField ? shownField.ply : ply; // the viewer's ply while it shows a ply's field
  return (
    <div data-testid="tree-results">
      <dl className="ws-tree-answer" data-testid="tree-results-answer">
        <div><dt>Reaction</dt><dd>{printed(Math.abs(s.reaction.value))} {lab.force}, {s.reaction.sense}, {setWords(s.reaction.set)}</dd></div>
        <div><dt>Largest displacement</dt><dd>{printed(s.max_displacement.value)} {lab.length}</dd></div>
        <div><dt>First-ply failure</dt><dd>{stat ? `${stat.verdict}, R = ${stat.factor}` : "no failure criterion chosen"}</dd></div>
      </dl>
      {live ? <p className="studio-hint">From the quick solve. Run analysis checks it with a second solver and writes the report.</p> : null}
      <p className="ws-tree-caption">Show on the model</p>
      <div className="ws-tree-fields" role="group" aria-label="Show on the model">
        {offered.map((o) => (
          <button key={o.id} type="button" data-field={o.id} aria-pressed={shownField?.id === o.id}
            onClick={() => showField({ id: o.id, ply: o.perPly ? shownPly : undefined })}>{o.label}</button>
        ))}
      </div>
      {fields.mesh.plies > 1 ? (
        <label className="studio-field ws-tree-ply">
          <span>Ply, for a ply&apos;s stress or strain</span>
          <select value={shownPly} aria-label="Ply shown" onChange={(e) => {
            const next = Number(e.target.value);
            setPly(next);
            if (shownField && perPlyShown) showField({ id: shownField.id, ply: next }); // the field shown follows the ply picked
          }}>
            {Array.from({ length: fields.mesh.plies }, (_, i) => (
              <option key={i + 1} value={i + 1}>Ply {i + 1}{angles[i] !== undefined ? ` (${printed(angles[i])}°)` : ""}{i === 0 ? ", bottom" : ""}</option>
            ))}
          </select>
        </label>
      ) : null}
      {files}
    </div>
  );
}
