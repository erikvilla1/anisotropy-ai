"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, Layers3, Plus, RotateCcw, X } from "lucide-react";
import {
  buildAnalysisRequest, CalculationError, exampleForm, loadNames, requestAnalysis,
  type AnalysisResult, type CalculatorForm, type FieldErrors,
} from "@/lib/laminate-api";

const materialFields = [
  ["E1_GPa", "E₁ (GPa)", "Along the fibers"],
  ["E2_GPa", "E₂ (GPa)", "Across the fibers"],
  ["G12_GPa", "G₁₂ (GPa)", "In-plane shear"],
  ["nu12", "ν₁₂", "Major Poisson ratio"],
] as const;

function NumericField({ name, label, value, error, hint, onChange }: {
  name: string; label: string; value: string; error?: string; hint?: string; onChange: (value: string) => void;
}) {
  return (
    <div className="calc-field">
      <label htmlFor={name}>{label}</label>
      <input id={name} name={name} type="text" inputMode="decimal" value={value}
        onChange={(e) => onChange(e.target.value)} aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : hint ? `${name}-hint` : undefined} />
      {error ? <span className="calc-field-error" id={`${name}-error`}>{error}</span>
        : hint ? <span className="calc-hint" id={`${name}-hint`}>{hint}</span> : null}
    </div>
  );
}

/** Formatting changes precision for display only; the engine supplies every result value. */
function formatted(value: number) { return value === 0 ? "0" : value.toExponential(6); }

function Matrix({ title, unit, meaning, values }: { title: string; unit: string; meaning: string; values: number[][] }) {
  return (
    <div className="calc-matrix">
      <h3>{title} <span>{unit}</span></h3>
      <p>{meaning}</p>
      <div className="calc-table-scroll" tabIndex={0} role="region" aria-label={`${title} stiffness matrix`}>
        <table aria-label={`${title} matrix`}><thead><tr><th scope="col">↔</th>{["x", "y", "xy"].map((axis) => <th scope="col" key={axis}>{axis}</th>)}</tr></thead>
          <tbody>{values.map((row, i) => <tr key={i}><th scope="row">{["x", "y", "xy"][i]}</th>{row.map((value, j) => <td key={j}>{formatted(value)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

export function LaminateCalculator({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [form, setForm] = useState<CalculatorForm>(exampleForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState("Example inputs loaded. Select Analyze laminate to calculate.");
  const activeRequest = useRef<AbortController | null>(null);
  useEffect(() => () => activeRequest.current?.abort("unmount"), []);

  function update(next: CalculatorForm) {
    setForm(next); setErrors({}); setMessage(""); setResult(null);
    setStatus("Inputs changed. Analyze again to calculate the current values.");
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !apiBaseUrl) return;
    setResult(null); setMessage("");
    const parsed = buildAnalysisRequest(form);
    if (parsed.errors) {
      setErrors(parsed.errors); setMessage("Review the highlighted inputs and try again."); setStatus(""); return;
    }
    setErrors({}); setPending(true); setStatus("Calculating laminate response…");
    const controller = new AbortController();
    activeRequest.current = controller;
    const timeout = window.setTimeout(() => controller.abort("timeout"), 20_000);
    try {
      const answer = await requestAnalysis(apiBaseUrl, parsed.request, controller.signal);
      if (!controller.signal.aborted) { setResult(answer); setStatus("Calculation complete. Results match the current inputs."); }
    } catch (error) {
      if (controller.signal.reason === "unmount") return;
      setStatus("");
      setMessage(controller.signal.aborted
        ? controller.signal.reason === "timeout" ? "The calculation timed out. Please try again." : "Calculation cancelled. Your inputs are unchanged."
        : error instanceof CalculationError ? error.message : "Cannot reach the calculation service. Check that it is running, then try again.");
      if (error instanceof CalculationError) setErrors(error.fields);
    } finally {
      window.clearTimeout(timeout); activeRequest.current = null; setPending(false);
    }
  }

  return (
    <div className="calculator-layout">
      <form className="calc-form" onSubmit={analyze} noValidate aria-label="Laminate inputs">
        <div className="calc-panel-title"><span className="eyebrow">01 / DEFINE</span>
          <button className="calc-text-button" type="button" disabled={pending} onClick={() => {
            update(exampleForm()); setStatus("Example inputs loaded. Select Analyze laminate to calculate.");
          }}><RotateCcw size={14} /> Load example</button>
        </div>
        <p className="calc-intro">One material across the stack. The example uses cited AS4/3501-6 properties and a constructed tension load.</p>
        <fieldset disabled={pending}>
          <legend>Material</legend>
          <div className="calc-field-grid">{materialFields.map(([key, label, hint]) =>
            <NumericField key={key} name={`material.${key}`} label={label} hint={hint} value={form.material[key]} error={errors[`material.${key}`]}
              onChange={(value) => update({ ...form, material: { ...form.material, [key]: value } })} />
          )}</div>
          {errors.material && <p className="calc-field-error">{errors.material}</p>}
          <div className="calc-field calc-source"><label htmlFor="material.source_reference">Material source</label>
            <textarea id="material.source_reference" rows={4} value={form.material.source_reference}
              onChange={(e) => update({ ...form, material: { ...form.material, source_reference: e.target.value } })}
              aria-invalid={Boolean(errors["material.source_reference"])} aria-describedby="source-help" />
            <span id="source-help" className={errors["material.source_reference"] ? "calc-field-error" : "calc-hint"}>
              {errors["material.source_reference"] || "Update the citation if you change these properties. Source text is supplied by you and is not verified here."}
            </span>
          </div>
        </fieldset>
        <fieldset disabled={pending}>
          <legend>Ply stack</legend>
          <p className="calc-hint">Bottom face first. Angles are counterclockwise from x to the fibers.</p>
          <div className="calc-plies">{form.plies.map((ply, index) => <div className="calc-ply" key={index}>
            <span className="calc-ply-index">{index + 1}</span>
            <NumericField name={`plies.${index}.angle_deg`} label={`Ply ${index + 1} angle (°)`} value={ply.angle_deg} error={errors[`plies.${index}.angle_deg`]}
              onChange={(value) => update({ ...form, plies: form.plies.map((p, i) => i === index ? { ...p, angle_deg: value } : p) })} />
            <NumericField name={`plies.${index}.thickness_mm`} label={`Ply ${index + 1} thickness (mm)`} value={ply.thickness_mm} error={errors[`plies.${index}.thickness_mm`]}
              onChange={(value) => update({ ...form, plies: form.plies.map((p, i) => i === index ? { ...p, thickness_mm: value } : p) })} />
            <button className="calc-remove" type="button" aria-label={`Remove ply ${index + 1}`} disabled={form.plies.length === 1}
              onClick={() => update({ ...form, plies: form.plies.filter((_, i) => i !== index) })}><X size={17} /></button>
          </div>)}</div>
          {errors.plies && <p className="calc-field-error">{errors.plies}</p>}
          <button className="calc-text-button" type="button" onClick={() => update({ ...form, plies: [...form.plies, { angle_deg: "", thickness_mm: "" }] })}><Plus size={15} /> Add ply</button>
        </fieldset>
        <fieldset disabled={pending}>
          <legend>Loads per unit width</legend>
          <p className="calc-hint">Enter every component, including 0 for unused loads. These are resultants per width, not total forces or moments.</p>
          <div className="calc-field-grid calc-loads">{loadNames.map((name) => <NumericField key={name} name={`loads.${name}`}
            label={`${name} (${name.startsWith("N") ? "N/m" : "N·m/m"})`} value={form.loads[name]} error={errors[`loads.${name}`]}
            onChange={(value) => update({ ...form, loads: { ...form.loads, [name]: value } })} />)}</div>
        </fieldset>
        {!apiBaseUrl && <p className="calc-notice">Calculations are unavailable on this site. You can still inspect the example inputs.</p>}
        {message && <p className="calc-alert" role="alert">{message}</p>}
        <div className="calc-actions">
          <button className="button primary" type="submit" disabled={pending || !apiBaseUrl}>{pending ? "Calculating…" : "Analyze laminate"}<ArrowRight size={16} /></button>
          {pending && <button className="calc-text-button" type="button" onClick={() => activeRequest.current?.abort("cancel")}>Cancel</button>}
        </div>
      </form>

      <section className="calc-output" aria-labelledby="results-title" aria-busy={pending}>
        <div className="calc-panel-title"><span className="eyebrow">02 / INSPECT</span><span className="calc-hint">{result ? `Engine ${result.engine_version}` : "Engine results"}</span></div>
        <h2 id="results-title">Laminate response</h2>
        <p className="calc-status" role="status">{status}</p>
        {result ? <div className="calc-results" data-testid="calculation-results">
          <div className="calc-vector"><h3>Mid-plane strain <span>dimensionless</span></h3>
            <dl>{["εx", "εy", "γxy"].map((label, i) => <div key={label}><dt>{label}</dt><dd data-testid={`strain-${i}`}>{formatted(result.midplane_strain[i])}</dd></div>)}</dl>
          </div>
          <div className="calc-vector"><h3>Curvature <span>1/m</span></h3>
            <dl>{["κx", "κy", "κxy"].map((label, i) => <div key={label}><dt>{label}</dt><dd data-testid={`curvature-${i}`}>{formatted(result.curvature_per_m[i])}</dd></div>)}</dl>
          </div>
          <p className="calc-hint">γxy is engineering shear strain. Values use scientific notation; e−4 means × 10⁻⁴.</p>
          <Matrix title="A" unit="N/m" meaning="Stretching stiffness" values={result.A_N_per_m} />
          <Matrix title="B" unit="N" meaning="Stretching–bending coupling" values={result.B_N} />
          <Matrix title="D" unit="N·m" meaning="Bending stiffness" values={result.D_N_m} />
        </div> : <div className="calc-empty"><Layers3 size={34} strokeWidth={1} /><h3>Your layup, calculated.</h3><p>Run an analysis to inspect stretching, bending and the connection between them.</p></div>}
        <p className="calc-scope">Flat, unnotched laminates · One material · Linear elastic CLT. This screen reports stiffness and deformation; strength, holes, temperature and moisture effects are outside its scope. Results are for research exploration, not design approval.</p>
      </section>
    </div>
  );
}
