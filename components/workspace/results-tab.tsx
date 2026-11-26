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

/** What the Results tab offers to colour the model by, in groups as a desktop tool's results tree lists them, each field where the
 * result has it: the answer first, then the deformation (the total and each direction), the stress of the whole laminate, and each
 * ply's stresses and strains in its fibre axes (ADR-0111 amendment 7). A chip's words are short because its group names the quantity;
 * the legend under the model prints the field's full name. The viewer under the model still offers every field. */
export const TREE_GROUPS: { title: string; fields: [id: string, chip: string | null][]; note?: string }[] = [
  { title: "Failure", fields: [["failure_index", null]] },
  { title: "Deformation (displacement)", fields: [["u_mag", "Total, |u|"], ["u_x", "Along x, uₓ"], ["u_y", "Along y, uᵧ"], ["u_z", "Along z, w"]] },
  { title: "Stress of the whole laminate", fields: [["S_x", "Along x, σx"], ["S_y", "Along y, σy"], ["S_xy", "Shear, τxy"]],
    note: "The force per width over the laminate's thickness: the mean through every ply, in the model's x and y. A ply's own stress is below." },
  { title: "One ply, in its fibre axes", fields: [["S11", null], ["S22", null], ["S12", null], ["E11", null], ["E22", null], ["E12", null]] },
];
export const TREE_FIELDS = TREE_GROUPS.flatMap((g) => g.fields.map(([id]) => id));

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
  const groups = TREE_GROUPS.map((g) => ({ ...g, offered: g.fields.flatMap(([id, chip]) => {
    const o = options.find((x) => x.id === id);
    return o ? [{ ...o, chip: chip ?? o.label }] : [];
  }) })).filter((g) => g.offered.length);
  const flat = (fields.mesh.translations ?? 2) !== 3; // an in-plane model: nothing moves along z
  const angles = fields.mesh.angles ?? [];
  const perPlyShown = options.find((o) => o.id === shownField?.id)?.perPly ?? false;
  const shownPly = perPlyShown && shownField ? shownField.ply : ply; // the viewer's ply while it shows a ply's field
  return (
    <div data-testid="tree-results">
      <dl className="ws-tree-answer" data-testid="tree-results-answer">
        <div><dt>Reaction</dt><dd>{printed(Math.abs(s.reaction.value))} {lab.force}, {s.reaction.sense}, {setWords(s.reaction.set)}</dd></div>
        <div><dt>Largest displacement</dt><dd>{printed(s.max_displacement.value)} {lab.length}</dd></div>
        <div><dt>First-ply failure</dt><dd>{stat ? `${stat.verdict}, ${stat.measure}` : "no failure criterion chosen"}</dd></div>
        {s.followed ? <div data-testid="tree-results-followed"><dt>Nonlinear geometry</dt><dd>{s.followed.fractions.length} load levels; linear {printed(Math.abs(s.followed.linear.largest))} {lab.length}</dd></div> : null}
      </dl>
      {live ? <p className="studio-hint">From the quick solve. Run analysis checks it with a second solver and writes the report.</p> : null}
      <p className="ws-tree-caption">Show on the model</p>
      {groups.map((g) => (
        <div key={g.title} className="ws-tree-group" data-testid="tree-results-group">
          <p className="ws-tree-group-title">{g.title}</p>
          <div className="ws-tree-fields" role="group" aria-label={g.title}>
            {g.offered.map((o) => (
              <button key={o.id} type="button" data-field={o.id} title={o.label} aria-pressed={shownField?.id === o.id}
                onClick={() => showField({ id: o.id, ply: o.perPly ? shownPly : undefined })}>{o.chip}</button>
            ))}
          </div>
          {g.note ? <p className="studio-hint">{g.note}</p> : null}
          {flat && g.offered.some((o) => o.id === "u_mag") ? <p className="studio-hint">Nothing moves along z: this model stays in its own plane.</p> : null}
        </div>
      ))}
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
