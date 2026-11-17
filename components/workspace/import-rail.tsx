"use client";

import { useState } from "react";
import { formatNumber } from "@/lib/number-format";
import { MAX_MODEL_BYTES, MODEL_UNITS, type ImportedModel, type ModelUnits } from "@/lib/studio-api";
import { importProblemWords, importText } from "@/lib/studio-copy";
import { unitWords } from "@/lib/studio-form";
import { useProject } from "@/components/studio/project-context";
import { StepPanel } from "./panels/step-panel";

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const printed = (value: number) => formatNumber(value, { zeros: false });

/** What the reader took from the file, in counts and names, and what it left out: the import's own report, as the service wrote it. */
function Reading({ model }: { model: ImportedModel }) {
  const reading = model.reading;
  if (!reading) return null;
  const length = reading.unit_labels.length ?? "";
  const types = Object.entries(reading.element_types).map(([type, n]) => `${n} ${type}`).join(", ");
  const loads = [reading.concentrated_loads ? count(reading.concentrated_loads, "force line") : "", reading.pressures ? count(reading.pressures, "pressure line") : ""].filter(Boolean);
  const notes = reading.notes.map((note) => importText(note)).filter((note): note is string => note !== null);
  return (
    <>
      <StepPanel id="import-read" title="What was read" state="pass" word="read">
        <dl className="ws-import-facts" data-testid="import-reading">
          <dt>Mesh</dt><dd>{count(reading.elements, "element")} ({types}), {count(reading.nodes, "node")}</dd>
          <dt>Layup</dt><dd>{reading.layup || "none stated"}{reading.sections[0] ? `, ${printed(reading.sections[0].thickness)} ${length} thick` : ""}</dd>
          <dt>Material</dt><dd>{reading.materials.map((m) => `${m.name}${m.kind === "lamina" && !m.strengths ? " (no strengths)" : ""}`).join(", ") || "none"}</dd>
          <dt>Supports</dt><dd>{count(reading.boundaries, "boundary line")}{reading.couplings ? `, ${count(reading.couplings, "coupling")}` : ""}</dd>
          <dt>Loads</dt><dd>{loads.join(", ") || "by moved supports only"}</dd>
          <dt>Step</dt><dd>{reading.step ?? "none"}, linear static</dd>
        </dl>
        {notes.length ? <ul className="ws-import-notes" data-testid="import-notes">{notes.map((note) => <li key={note}>{note}</li>)}</ul> : null}
      </StepPanel>
      <StepPanel id="import-skipped" title="Left out" note={count(reading.skipped.length, "keyword")} open={false}>
        {reading.skipped.length ? (
          <>
            <p className="studio-hint">Output and print requests, which change no result. Anything that would change one is refused instead.</p>
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
  const warnings = (model?.reading?.warnings ?? []).map((line) => importText(line)).filter((line): line is string => line !== null);
  return (
    <div className="studio-form ws-rail-panels" data-testid="import-rail">
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
        {model && words ? <p className="studio-alert" role="alert" data-testid="import-problem" data-state={model.state}>{words}</p> : null}
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
      </StepPanel>
      {model ? <Reading model={model} /> : null}
    </div>
  );
}
