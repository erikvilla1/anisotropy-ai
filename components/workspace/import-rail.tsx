"use client";

import { useEffect, useState } from "react";
import { appliedOf } from "@/lib/applied";
import { IMPORTED_TABS, importedLines, type TabId } from "@/lib/model-tree";
import { formatNumber } from "@/lib/number-format";
import { MAX_MODEL_BYTES, MODEL_UNITS, type ImportedModel, type ModelUnits } from "@/lib/studio-api";
import { importProblemWords, importText, importUnreadLines } from "@/lib/studio-copy";
import { unitWords } from "@/lib/studio-form";
import { useProject } from "@/components/studio/project-context";
import { StepPanel } from "./panels/step-panel";
import { ResultsTab } from "./results-tab";

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const printed = (value: number) => formatNumber(value, { zeros: false });

/** A model brought in as a file on the model tree (ADR-0111 amendment 1): the tabs of any setup, read-only, each tab's line and body what
 * the reader took from the file, its boundary conditions and loads drawn on the model and lit while their tab is open. */
function ImportTree({ model, apiBaseUrl }: { model: ImportedModel; apiBaseUrl: string }) {
  const { emphasis, setEmphasis } = useProject();
  useEffect(() => () => setEmphasis(null), [setEmphasis]); // the tree gone, nothing is lit
  const reading = model.reading;
  if (!reading) return null;
  const length = reading.unit_labels.length ?? "";
  const lines = importedLines(reading);
  const types = Object.entries(reading.element_types).map(([type, n]) => `${n} ${type}`).join(", ");
  const moved = (reading.moved ?? []).map((m) => `Instance ${m.instance} is read where the assembly places it: moved by (${m.by.map(printed).join(", ")}) ${length}`
    + (m.turned_deg ? `, then turned ${printed(m.turned_deg)}° about (${(m.about ?? [0, 0]).map(printed).join(", ")}) ${length}.` : "."))
    .map((note) => importText(note)).filter((note): note is string => note !== null);
  const applied = model.preview ? appliedOf(model.preview) : null;
  const lights = (id: "conditions" | "loads") => (open: boolean) => setEmphasis(open ? id : emphasis === id ? null : emphasis);
  const seconds = model.seconds < 10 ? model.seconds.toFixed(1) : String(Math.round(model.seconds));
  const step = (id: TabId) => IMPORTED_TABS.indexOf(id) + 2; // after File and units
  return (
    <>
      <StepPanel id="geometry" title="Geometry" step={step("geometry")} open={false} note={lines.geometry}>
        <dl className="ws-import-facts" data-testid="import-geometry">
          <dt>Parts</dt><dd>{reading.parts}</dd>
          <dt>Instances</dt><dd>{reading.instances}</dd>
          <dt>Sets</dt><dd>{count(reading.node_sets, "node set")}, {count(reading.element_sets, "element set")}</dd>
        </dl>
        {moved.length ? <ul className="ws-import-notes">{moved.map((note) => <li key={note}>{note}</li>)}</ul> : null}
      </StepPanel>
      <StepPanel id="material" title="Material" step={step("material")} open={false} note={lines.material}>
        <ul className="ws-tree-lines" data-testid="import-materials">
          {reading.materials.map((m) => <li key={m.name}>{m.name}{m.kind === "lamina" ? ", a ply material" : m.kind ? `, ${m.kind}` : ""}{m.kind === "lamina" && !m.strengths ? " (no strengths)" : ""}</li>)}
        </ul>
      </StepPanel>
      <StepPanel id="layup" title="Layup" step={step("layup")} open={false} note={lines.layup}>
        <ul className="ws-tree-lines" data-testid="import-layup">
          {reading.sections.length ? reading.sections.map((s) => (
            <li key={s.element_set}>{reading.layup && reading.sections.length === 1 ? reading.layup : s.element_set}, {printed(s.thickness)} {length} thick
              {`, ${count(s.plies, "ply", "plies")} of ${s.materials.join(", ")}`}{s.rotation_deg ? `, turned ${printed(s.rotation_deg)}°` : ""}</li>
          )) : <li>No layup stated</li>}
        </ul>
      </StepPanel>
      <StepPanel id="step" title="Analysis step" step={step("step")} open={false} note={lines.step}>
        <p className="studio-hint" data-testid="import-step">{reading.step ?? "No step named"}: one static step, linear, as the file states it.</p>
      </StepPanel>
      <StepPanel id="conditions" title="Boundary conditions" step={step("conditions")} open={false} note={lines.conditions} onToggle={lights("conditions")}>
        {applied?.conditions.length ? (
          <ul className="ws-tree-lines" data-testid="import-conditions">{applied.conditions.map((c) => <li key={c.set}>{c.words}</li>)}</ul>
        ) : null}
        <p className="studio-hint">{lines.conditions} in the file, drawn on the model.</p>
      </StepPanel>
      <StepPanel id="loads" title="Loads" step={step("loads")} open={false} note={lines.loads} onToggle={lights("loads")}>
        {applied?.loads.length ? (
          <ul className="ws-tree-lines" data-testid="import-loads">{applied.loads.map((l) => <li key={`${l.set}-${l.direction}`}>{l.words}</li>)}</ul>
        ) : <p className="studio-hint">No load is drawn.</p>}
      </StepPanel>
      <StepPanel id="mesh" title="Mesh" step={step("mesh")} open={false} note={lines.mesh}>
        <p className="studio-hint" data-testid="import-mesh">{count(reading.elements, "element")} ({types}), {count(reading.nodes, "node")}
          {reading.reference_nodes ? `, and ${count(reading.reference_nodes, "reference node")}` : ""}. The mesh is the file&apos;s, as it stands.</p>
      </StepPanel>
      <StepPanel id="run" title="Solve" step={step("run")} state={model.state === "solved" ? "pass" : "fail"} word="solved" open={model.state !== "solved"}
        note={model.state === "solved" ? `${seconds} s` : undefined}>
        <p className={model.state === "solved" ? "studio-hint" : "studio-alert"} data-testid="import-solve">
          {model.state === "solved" ? "Solved as the file states it: no mesh study, and not checked against a second solver." : importProblemWords(model)}</p>
      </StepPanel>
      <StepPanel id="outputs" title="Results" step={step("outputs")} open={model.state === "solved"} note={model.state === "solved" ? undefined : "none"}>
        <ResultsTab apiBaseUrl={apiBaseUrl} />
      </StepPanel>
      <StepPanel id="import-skipped" title="Left out" note={count(reading.skipped.length, "keyword")} open={false}>
        {reading.skipped.length ? (
          <>
            <p className="studio-hint">Output requests, and values a linear static step never uses, such as density. None changes a result; anything that would is refused instead.</p>
            <ul className="ws-import-notes" data-testid="import-skipped">{reading.skipped.map((line) => <li key={line}>{line}</li>)}</ul>
          </>
        ) : <p className="studio-hint">Every keyword in the file was read.</p>}
      </StepPanel>
    </>
  );
}

/** The left column while a model brought in as a file has the stage (ADR-0105): the file and the units it is written in, then what was
 * read. The file is sent as it is; nothing here reads it. */
export function ImportRail({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { imported } = useProject();
  const { model, busy, problem } = imported;
  const [file, setFile] = useState<File | null>(null);
  const [units, setUnits] = useState<ModelUnits | "">("");
  const tooLarge = file !== null && file.size > MAX_MODEL_BYTES;
  const words = model ? importProblemWords(model) : null;
  const unread = model?.problem ? importUnreadLines(model.problem.unread) : [];
  const warnings = (model?.reading?.warnings ?? []).map((line) => importText(line)).filter((line): line is string => line !== null);
  const notes = (model?.reading?.notes ?? []).map((note) => importText(note)).filter((note): note is string => note !== null);
  return (
    <div className="studio-form ws-rail-panels ws-tree" data-testid="import-rail">
      <div className="ws-rail-head">
        <p className="ws-setup-line">Imported model</p>
        <div className="studio-actions">
          <button type="button" className="studio-text-button" onClick={imported.close} data-testid="import-close">Back to the coupon</button>
        </div>
      </div>
      <StepPanel id="import-file" step={1} title="File and units" state={model ? (model.state === "refused" ? "fail" : "pass") : "none"} word="read">
        <div className="studio-field">
          <label htmlFor="import-file">Abaqus input file (.inp)</label>
          <input id="import-file" type="file" accept=".inp,text/plain" disabled={busy} data-testid="import-file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <span className="studio-hint">Flat four-node shell models with one linear static step are read. The file is not stored.</span>
        </div>
        <div className="studio-field">
          <label htmlFor="import-units">Units the file is written in</label>
          <select id="import-units" value={units} disabled={busy} onChange={(e) => setUnits(e.target.value as ModelUnits | "")} data-testid="import-units">
            <option value="">Choose…</option>
            {MODEL_UNITS.map((u) => <option key={u} value={u}>{unitWords(u)}</option>)}
          </select>
          <span className="studio-hint">A file carries no units, and none are guessed from its numbers.</span>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" disabled={busy || !file || !units || tooLarge || !apiBaseUrl} data-testid="import-send"
            onClick={() => { if (file && units) void imported.send(file, units); }}>{busy ? "Reading…" : "Read and solve"}</button>
        </div>
        {tooLarge ? <p className="studio-alert" role="alert">This file is larger than {MAX_MODEL_BYTES / 1e6} MB, the largest model read.</p> : null}
        {problem ? <p className="studio-alert" role="alert" data-testid="import-failed">{problem}</p> : null}
        {model && words ? (
          <div className="studio-alert" role="alert" data-state={model.state}>
            <p data-testid="import-problem" data-state={model.state}>{words}</p>
            {/* every kind of thing the file holds that is not read, at once: nobody should learn a model's limits one upload at a time */}
            {unread.length > 1 ? <ul className="ws-import-notes" data-testid="import-unread">{unread.map((line) => <li key={line}>{line}</li>)}</ul> : null}
          </div>
        ) : null}
        {warnings.length ? (
          // a value far from any material's usually means the wrong units, which would make every result wrong: said beside the choice
          <div className="studio-alert" role="alert" data-testid="import-warnings">
            <p>Check the units:</p>
            <ul className="ws-import-notes">{warnings.map((line) => <li key={line}>{line}</li>)}</ul>
          </div>
        ) : null}
        <p className="studio-status" role="status" data-testid="import-status">
          {busy ? "Reading the file." : model ? (model.state === "solved" ? `${model.name}: read and solved.` : model.state === "read" ? `${model.name}: read, not solved.` : `${model.name}: not read.`) : "Choose a file and its units."}
        </p>
        {notes.length ? <ul className="ws-import-notes" data-testid="import-notes">{notes.map((note) => <li key={note}>{note}</li>)}</ul> : null}
      </StepPanel>
      {model ? <ImportTree model={model} apiBaseUrl={apiBaseUrl} /> : null}
    </div>
  );
}
