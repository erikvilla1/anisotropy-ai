"use client";

import { useEffect, useMemo, useState } from "react";
import { DOWNLOADS, explainJob, fileUrl, StudioError, type ExplainAnswer, type Explanation, type Fields, type JobStatus, type Preview } from "@/lib/studio-api";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, valuesFor, type FieldChoice } from "@/lib/studio-fields";
import { colorsOf, legendTicks, printed, scaleFor, type Scale } from "@/lib/studio-colors";
import { suggestedScale } from "@/lib/studio-geometry";
import { Scene } from "./scene";
import type { SceneMarker } from "./scene-canvas";

export function Legend({ scale, label, unit, by }: { scale: Scale; label: string; unit: string; by: "node" | "element" }) {
  const ticks = legendTicks(scale, 5);
  return (
    <div className="studio-legend" data-testid="legend">
      <div className="studio-legend-bar" style={{ background: `linear-gradient(to right, ${scale.stops.join(", ")})` }} aria-hidden="true" />
      <div className="studio-legend-ticks" aria-hidden="true">{ticks.map((t, i) => <span key={i}>{printed(t)}</span>)}</div>
      <p><strong>{label}</strong> ({unit}); {by === "element" ? "element values: the result" : "display averages over the elements sharing a node, for a smooth picture; the element values are the result"}.
        {scale.kind === "diverging" ? " Grey is zero." : ""} From {printed(scale.min)} to {printed(scale.max)} {unit}.</p>
    </div>
  );
}

export function SummaryPanel({ fields, onShow }: { fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const s = fields.summary, lab = fields.labels;
  return (
    <div className="studio-panel" data-testid="summary">
      <h3>Summary</h3>
      <dl className="studio-summary">
        <div><dt>Applied</dt><dd>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}{s.applied.direction ? `, ${s.applied.direction}` : ""}</dd></div>
        <div><dt>Reaction at {s.reaction.set}</dt><dd data-testid="summary-reaction">{printed(Math.abs(s.reaction.value))} {lab.force} ({s.reaction.sense})</dd></div>
        <div><dt>Largest displacement</dt><dd>{printed(s.max_displacement.value)} {lab.length} at node {s.max_displacement.label.split(".").pop()}
          {s.max_displacement.axis === "z" ? " (the deflection w)" : ""}</dd></div>
        {Object.entries(s.max_ply).map(([name, m]) => (
          <div key={name}><dt>Largest ply {name === "mises" ? "von Mises" : name}</dt>
            <dd>{printed(m.value)} {lab.stress} in ply {m.ply} ({m.angle}°){m.face ? `, ${m.face} face,` : ""} at element {m.label.split(".").pop()}
              <button type="button" className="studio-text-button" onClick={() => onShow(m.element, m.ply, s.earliest ?? "", m.face)}>show</button></dd></div>
        ))}
      </dl>
      <h4>First-ply failure</h4>
      {Object.keys(s.fpf).length === 0 ? <p className="studio-muted">No failure criterion was asked for.</p> : (
        <table className="studio-table" data-testid="fpf-table">
          <thead><tr><th>Criterion</th><th>Factor R</th><th>Index 1/R</th><th>Ply</th><th>Mode</th><th>Where</th><th></th></tr></thead>
          <tbody>
            {Object.entries(s.fpf).sort(([, a], [, b]) => a.factor - b.factor).map(([criterion, f]) => (
              <tr key={criterion} data-criterion={criterion} className={criterion === s.earliest ? "studio-earliest" : undefined}>
                <td>{criterion.replace("_", " ")}{criterion === s.earliest ? " (earliest)" : ""}</td>
                <td data-testid={`fpf-factor-${criterion}`}>{printed(f.factor)}</td><td>{printed(f.index)}</td>
                <td>{f.ply} ({f.angle}°){f.face ? `, ${f.face} face` : ""}{f.tied_plies.length > 1 ? `, tied ${f.tied_plies.join(", ")}` : ""}</td>
                <td>{f.mode}</td><td>element {f.label.split(".").pop()}, {f.place}</td>
                <td><button type="button" className="studio-text-button" onClick={() => onShow(f.element, f.ply, criterion, f.face)}>show</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="studio-muted">R is the factor on the applied loading at which the first ply fails; the failure index is 1/R. Below 1, the loading of the model is past first-ply failure.
        {s.earliest && s.fpf[s.earliest]?.touches_grip ? " The critical element touches a gripped tab, where the stress is not expected to settle as the mesh is refined." : ""}</p>
    </div>
  );
}

export function ExplanationPanel({ explanation, answer }: { explanation: Explanation | null; answer?: ExplainAnswer | null }) {
  if (!explanation && !answer) return null;
  const prose = answer?.prose ?? explanation?.sentences ?? [];
  const writer = answer?.writer ?? explanation?.writer ?? "template";
  const badge = writer === "template" ? "written by the template from the engine's numbers" : `written by ${writer}${answer?.model ? ` (${answer.model})` : ""}, every number checked against the engine's`;
  return (
    <div className="studio-panel" data-testid="explanation" data-writer={writer}>
      <h3>What this shows <span className="studio-badge studio-badge-writer">{badge}</span></h3>
      {answer?.reason ? <p className="studio-muted" data-testid="explanation-reason">{answer.withheld ? "The model's draft was withheld: " : "The template's words stand: "}{answer.reason}.</p> : null}
      {prose.map((sentence, i) => <p key={i}>{sentence}</p>)}
      {explanation?.setup_sentences.length ? <details><summary>The setup, as checked</summary>{explanation.setup_sentences.map((s, i) => <p key={i}>{s}</p>)}</details> : null}
    </div>
  );
}

export function Downloads({ apiBase, job }: { apiBase: string; job: JobStatus }) {
  const available = DOWNLOADS.filter(([key]) => key in job.outputs);
  if (!available.length) return null;
  return (
    <div className="studio-panel" data-testid="downloads">
      <h3>Files</h3>
      <ul className="studio-downloads">
        {available.map(([key, label]) => <li key={key}><a href={fileUrl(apiBase, job.job_id, key)} target="_blank" rel="noreferrer" data-key={key}>{label}</a></li>)}
      </ul>
      {job.state === "running" ? <p className="studio-muted">More files join the list as the job goes on.</p> : null}
    </div>
  );
}

export function ResultsView({ fields, explanation, job, apiBase, preview }: {
  fields: Fields; explanation: Explanation | null; job: JobStatus | null; apiBase: string; preview: Preview | null;
}) {
  const [choice, setChoice] = useState<FieldChoice>(() => DEFAULT_CHOICE(fields));
  const [scale, setScale] = useState<number>(() => suggestedScale(fields.mesh.nodes, fields.nodal.magnitude));
  const [deformed, setDeformed] = useState(true);
  const [wireframe, setWireframe] = useState(true);
  const [picked, setPicked] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number | null>(() => (fields.summary.earliest ? fields.summary.fpf[fields.summary.earliest].element : null));
  const [answer, setAnswer] = useState<ExplainAnswer | null>(null);
  useEffect(() => {
    // once our engine has written the explanation, the API's writer (the template, or a model behind a setting) rephrases it (ADR-0052)
    if (!job || !apiBase || !("explanation" in job.outputs)) return;
    let cancelled = false;
    explainJob(apiBase, job.job_id, "result").then((a) => { if (!cancelled) setAnswer(a); })
      .catch((error) => { if (!cancelled && !(error instanceof StudioError && error.status === 409)) setAnswer(null); });
    return () => { cancelled = true; };
  }, [job?.job_id, job?.state, "explanation" in (job?.outputs ?? {}), apiBase]);
  useEffect(() => { setChoice(DEFAULT_CHOICE(fields)); setScale(suggestedScale(fields.mesh.nodes, fields.nodal.magnitude)); }, [fields]);
  const options = useMemo(() => fieldOptions(fields), [fields]);
  const option = options.find((o) => o.id === choice.id) ?? options[0];
  const values = useMemo(() => valuesFor(fields, choice), [fields, choice]);
  const colorScale = useMemo(() => scaleFor(values.values, !values.signed), [values]);
  const colors = useMemo(() => ({ by: values.by, rgb: colorsOf(colorScale, values.values) }), [values, colorScale]);
  const held: SceneMarker[] = preview ? preview.held.filter((h, i, all) => all.findIndex((x) => x.set === h.set) === i)
    .map((h) => ({ nodes: fields.mesh.node_sets[h.set] ?? preview.mesh.node_sets[h.set] ?? [], label: `held: ${h.set}` })) : [];
  const loaded = preview ? { nodes: fields.mesh.node_sets[preview.loaded.set] ?? preview.mesh.node_sets[preview.loaded.set] ?? [],
    direction: preview.loaded.direction, label: `${preview.loaded.control} ${printed(preview.loaded.value)} ${preview.loaded.unit}` } : null;
  const readout = picked !== null ? elementReadout(fields, picked, choice, printed) : null;
  const show = (element: number, ply: number, criterion: string, face?: string | null) => {
    setHighlight(element); setPicked(element);
    const faceIndex = face && fields.mesh.faces ? Math.max(0, fields.mesh.faces.indexOf(face)) : undefined;
    setChoice((c) => ({ ...c, ply, criterion: criterion || c.criterion, face: faceIndex ?? c.face }));
  };
  return (
    <div className="studio-results" data-testid="results">
      <div className="studio-scene-block">
        <Scene nodes={fields.mesh.nodes} quads={fields.mesh.quads} thickness={preview?.geometry.thickness ?? 1} colors={colors}
          displacement={deformed ? fields.nodal.displacement : null} scale={scale} held={held} loaded={loaded} highlight={highlight} picked={picked}
          wireframe={wireframe} onPick={setPicked} />
        <Legend scale={colorScale} label={values.label} unit={values.unit} by={values.by} />
      </div>
      <div className="studio-controls" data-testid="field-controls">
        <label>Field
          <select value={choice.id} onChange={(e) => setChoice({ ...choice, id: e.target.value })} aria-label="Field">
            {[...new Set(options.map((o) => o.group))].map((group) => (
              <optgroup key={group} label={group}>{options.filter((o) => o.group === group).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</optgroup>
            ))}
          </select>
        </label>
        {option.perPly ? (
          <label>Ply
            <select value={choice.ply} onChange={(e) => setChoice({ ...choice, ply: Number(e.target.value) })} aria-label="Ply">
              {fields.mesh.angles.map((angle, i) => <option key={i} value={i + 1}>{i + 1}: {angle}°</option>)}
            </select>
          </label>
        ) : null}
        {option.perFace && fields.mesh.faces ? (
          <label>Face
            <select value={choice.face} onChange={(e) => setChoice({ ...choice, face: Number(e.target.value) })} aria-label="Face">
              {fields.mesh.faces.map((face, i) => <option key={face} value={i}>{face}</option>)}
            </select>
          </label>
        ) : null}
        {option.perCriterion ? (
          <label>Criterion
            <select value={choice.criterion} onChange={(e) => setChoice({ ...choice, criterion: e.target.value })} aria-label="Criterion">
              {Object.keys(fields.element.failure).map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
            </select>
          </label>
        ) : null}
        {!option.nodalOnly && option.id !== "failure_index_ply" ? (
          <label>Shown as
            <select value={choice.averaged ? "average" : "element"} onChange={(e) => setChoice({ ...choice, averaged: e.target.value === "average" })} aria-label="Shown as">
              <option value="element">element values (the result)</option>
              <option value="average">display averages (smooth)</option>
            </select>
          </label>
        ) : null}
        <label><input type="checkbox" checked={deformed} onChange={(e) => setDeformed(e.target.checked)} /> deformed shape, scale
          <input type="number" value={scale} min={0} step="any" onChange={(e) => setScale(Number(e.target.value) || 0)} aria-label="Deformation scale" className="studio-scale" /> ×</label>
        <label><input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} /> element edges</label>
      </div>
      {readout ? (
        <div className="studio-panel studio-readout" data-testid="readout">
          <h3>{readout.title}{highlight === picked ? " (the critical element)" : ""}</h3>
          <dl>{readout.rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <p className="studio-muted">Click an element on the plate to read it; click the background to clear.</p>
        </div>
      ) : <p className="studio-muted studio-pick-hint">Click an element on the plate to read its values. The critical element is framed in red.</p>}
      <SummaryPanel fields={fields} onShow={show} />
      <ExplanationPanel explanation={explanation} answer={answer} />
      {job ? <Downloads apiBase={apiBase} job={job} /> : null}
    </div>
  );
}
