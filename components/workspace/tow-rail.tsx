"use client";

import { useCallback, useEffect, useState } from "react";
import { isUuid } from "@/lib/project-store";
import { StudioError, towTest } from "@/lib/studio-api";
import { withStandard, withTest, type StudioForm } from "@/lib/studio-form";
import {
  failureCodeWords, nextSpecimen, pastedSpecimens, specimenFields, TOW_PANELS, towDefaults, towFieldByKey, towPanelState, towRowErrors, towStepNumber, towValues,
  type TowPanelId,
  type TowSpecimenRow,
} from "@/lib/studio-tow";
import { ChecklistPanel } from "@/components/studio/checklist-panel";
import { Field, FieldGrid } from "@/components/studio/coupon-form";
import { useProject } from "@/components/studio/project-context";
import { StandardCard } from "@/components/studio/standard-card";
import { SetupLine } from "./panels/step-standard";
import { showPanel, StepPanel } from "./panels/step-panel";
import { TestStep } from "./panels/test-step";

const SHARED = ["test", "standard", "filled_by", "date", "notes"];

/** The tow's rows of one panel as a grid: the coupon form's own rows (test, standard, who, date, notes) by the coupon grid, the tow's by
 * their definitions, which carry the standard's units and no Units row. */
function TowGrid({ form, keys, errors, disabled, onChange }: {
  form: StudioForm; keys: string[]; errors: Record<string, string>; disabled: boolean; onChange: (key: string, value: string) => void;
}) {
  const shared = keys.filter((k) => SHARED.includes(k));
  const own = keys.filter((k) => towFieldByKey[k]);
  return (
    <>
      {shared.length ? <FieldGrid form={form} keys={shared} errors={errors} disabled={disabled} onChange={onChange} /> : null}
      {own.length ? (
        <div className="studio-field-grid">
          {own.map((key) => <Field key={key} field={towFieldByKey[key]} value={form[key] ?? ""} units="" error={errors[key]} disabled={disabled}
            onChange={(value) => onChange(key, value)} />)}
        </div>
      ) : null}
    </>
  );
}

/** The specimens tested, one small card each: the forces, the failure code with its words, valid or rejected with the reason. */
function SpecimenList({ rows, disabled, error, onRows }: { rows: TowSpecimenRow[]; disabled: boolean; error?: string; onRows: (rows: TowSpecimenRow[]) => void }) {
  const [paste, setPaste] = useState("");
  const set = (i: number, key: string, value: string) => onRows(rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
  return (
    <div className="ws-specimens" data-testid="tow-specimens">
      {rows.map((row, i) => {
        const words = row.failure_code ? failureCodeWords(row.failure_code) : null;
        return (
          <fieldset key={i} className="ws-specimen" data-specimen={row.id} data-status={row.status}>
            <legend>Specimen {row.id || i + 1}</legend>
            <div className="ws-specimen-grid">
              {specimenFields.map((field) => (
                <label key={field.key} className={`ws-specimen-cell ws-specimen-${field.key}`}>
                  <span>{field.label}</span>
                  {field.kind === "list" ? (
                    <select value={row[field.key] ?? ""} disabled={disabled} onChange={(e) => set(i, field.key, e.target.value)}>
                      {field.words.map((w) => <option key={w} value={w}>{w}</option>)}
                    </select>
                  ) : (
                    <input type="text" value={row[field.key] ?? ""} disabled={disabled} inputMode={field.kind === "number" ? "decimal" : undefined}
                      onChange={(e) => set(i, field.key, e.target.value)} autoComplete="off" aria-label={`Specimen ${row.id || i + 1}: ${field.label}`} />
                  )}
                </label>
              ))}
            </div>
            <div className="ws-specimen-foot">
              <span className="studio-hint">{row.failure_code ? (words ?? "not a code of Fig. 1") : "failure code: type, area, location (Fig. 1)"}</span>
              <button type="button" className="studio-text-button" disabled={disabled} onClick={() => onRows(rows.filter((_, j) => j !== i))}>Remove</button>
            </div>
          </fieldset>
        );
      })}
      {error ? <p className="studio-field-error">{error}</p> : null}
      <div className="studio-buttons">
        <button type="button" className="studio-text-button" disabled={disabled} onClick={() => onRows([...rows, nextSpecimen(rows)])} data-testid="add-specimen">Add a specimen</button>
      </div>
      <details className="ws-paste">
        <summary>Paste specimens from a spreadsheet</summary>
        <p className="studio-hint">One specimen per line, its cells separated by tabs or commas, in this order: {specimenFields.map((f) => f.label).join(", ")}.</p>
        <textarea rows={4} value={paste} disabled={disabled} onChange={(e) => setPaste(e.target.value)} aria-label="Specimens to paste" />
        <div className="studio-buttons">
          <button type="button" className="studio-text-button" disabled={disabled || !paste.trim()} onClick={() => { onRows([...rows, ...pastedSpecimens(paste)]); setPaste(""); }}>Add these</button>
          <button type="button" className="studio-text-button" disabled={disabled || !paste.trim()} onClick={() => { onRows(pastedSpecimens(paste)); setPaste(""); }}>Replace the list</button>
        </div>
      </details>
    </div>
  );
}

/** The left column for a fibre tow record (ADR-0074): the coupon form's Test list picked "fibre tow tension", so its panels give way to the
 * tow's after the same first step, Test and standard (ADR-0062 amendment 1): the project, the fibre, its mass and density, the impregnated
 * strand, the tensile set-up, the specimens and Calculate. The record goes to
 * `POST /v1/tow-tests` as typed; the fea package judges it and the engine computes every number, so this column only keeps the text. */
export function TowRail({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { project, form, specimens, setForm, setSpecimens, towAnswer, setTowAnswer, allTests } = useProject();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("Fill in the fibre, the test and the specimens, then calculate.");
  useEffect(() => {
    if (Object.keys(towDefaults(form)).length) setForm((f) => ({ ...towDefaults(f), ...f })); // the tow's rows at their defaults, once
  }, [form, setForm]);

  const changed = useCallback((what: string) => {
    setErrors({}); setTowAnswer(null); setMessage(""); setStatus(`${what} changed. Calculate again.`);
  }, [setTowAnswer]);
  const edit = useCallback((key: string, value: string) => {
    const note = key === "test" ? withTest(form, value).note : "";
    setForm((f) => (key === "test" ? withTest(f, value).form : key === "standard" ? withStandard(f, value) : { ...f, [key]: value }));
    changed("Inputs");
    if (note) setStatus(note);
  }, [form, setForm, changed]);
  const editSpecimens = useCallback((rows: TowSpecimenRow[]) => { setSpecimens(rows); changed("The specimens"); }, [setSpecimens, changed]);

  async function calculate() {
    if (!apiBaseUrl) return;
    setBusy(true); setMessage(""); setErrors({});
    try {
      const answer = await towTest(apiBaseUrl, towValues(form, specimens), undefined, isUuid(project.id) ? project.id : null);
      setTowAnswer(answer);
      setErrors(towRowErrors(answer.checklist));
      setStatus(answer.state === "ready" ? `Calculated: ${answer.result?.counts.valid ?? 0} valid specimens. The results are in the centre.` : "The record is blocked; the items below say what to fix.");
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The tow calculation failed.");
      setStatus("");
    } finally {
      setBusy(false);
    }
  }

  const checklist = towAnswer?.checklist ?? null;
  const state = (id: TowPanelId) => towPanelState(id, checklist);
  const panelOf = (item: string) => TOW_PANELS.find((p) => p.items.includes(item));
  const failing = checklist?.items.filter((item) => item.state === "fail" || item.state === "missing") ?? [];
  const grid = (id: TowPanelId) => <TowGrid form={form} keys={TOW_PANELS.find((p) => p.id === id)?.keys ?? []} errors={errors} disabled={busy} onChange={edit} />;
  const step = (id: TowPanelId) => ({ id, step: towStepNumber(id), title: TOW_PANELS.find((p) => p.id === id)?.title ?? id, state: state(id) });

  return (
    <div className="studio-form ws-rail-panels" data-testid="tow-form">
      {!apiBaseUrl ? <p className="studio-alert">Analysis is not available on this page.</p> : null}
      <div className="ws-rail-head"><SetupLine form={form} /></div>
      <StepPanel {...step("tow-standard")} note="ASTM D4018: a fibre tow, no model">
        <TestStep form={form} disabled={busy} onChange={edit} allTests={allTests} />
        <StandardCard form={form} checklist={checklist} tow allTests={allTests} />
      </StepPanel>
      <StepPanel {...step("tow-project")}>
        <p className="studio-hint">A resin-impregnated carbon or graphite fibre tow, pulled to failure: its strength and chord modulus come from the forces and the
          fibre&apos;s mass per unit length and density, with no finite element model. The rows are in the standard&apos;s units (SI only).</p>
        {grid("tow-project")}
      </StepPanel>
      <StepPanel {...step("tow-fibre")}>{grid("tow-fibre")}</StepPanel>
      <StepPanel {...step("tow-mass")}>{grid("tow-mass")}</StepPanel>
      <StepPanel {...step("tow-strand")}>{grid("tow-strand")}</StepPanel>
      <StepPanel {...step("tow-test")}>{grid("tow-test")}</StepPanel>
      <StepPanel {...step("tow-specimens")} note={`${specimens.length} listed`}>
        <SpecimenList rows={specimens} disabled={busy} error={errors.specimens} onRows={editSpecimens} />
      </StepPanel>
      <StepPanel id="tow-calculate" title="Calculate" state={checklist ? (checklist.state === "ready" ? "pass" : "fail") : "none"}>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={calculate} disabled={busy || !apiBaseUrl} data-testid="tow-calculate">Calculate</button>
        </div>
        <ChecklistPanel checklist={checklist} checking={busy} title="Record check" ready="calculated" subject="This record"
          waiting="Select Calculate. The record is read and judged by the fea package, every number computed by the engine; a failed or missing item blocks the result, a deviation does not." />
        {failing.length ? (
          <p className="ws-fix-links">
            {failing.map((item) => {
              const target = panelOf(item.id);
              return target ? <button type="button" key={item.id} className="studio-text-button" onClick={() => showPanel(target.id)}>Fix {item.label.toLowerCase()} under {target.title}</button> : null;
            })}
          </p>
        ) : null}
        {message ? <p className="studio-alert" role="alert">{message}</p> : null}
        <p className="studio-status" role="status" data-testid="status">{status}</p>
      </StepPanel>
    </div>
  );
}
