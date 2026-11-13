"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, Layers3, Plus, RotateCcw, X } from "lucide-react";
import {
  buildAnalysisRequest, CalculationError, exampleForm, loadNames, requestAnalysis, shownCitation, shownMatrices,
  type AnalysisResult, type CalculatorForm, type FieldErrors,
} from "@/lib/laminate-api";
import { ANGLE_CONVENTION } from "@/lib/laminate-chat";
import { findLibraryOption, libraryOptions } from "@/lib/material-library-options";
import { calculatorHandoffKey, readCalculatorHandoff } from "@/lib/home-calculator";
import { ANALYSIS_UNAVAILABLE } from "@/lib/studio-copy";
import { formatted, Matrix } from "@/components/abd-matrix";

/** The calculator's results in the units the laminate workspace prints (style guide, Tables and numbers): strains in microstrain, A in
 * MN/m and B in kN, scaled where the values leave for the screen (ADR-0002); the engine's SI values are unchanged. */
const MICRO = 1e6;
const scaledBy = (rows: number[][], factor: number) => rows.map((row) => row.map((value) => value / factor));

const materialFields = [
  ["E1_GPa", "E₁ (GPa)", "Along the fibres"],
  ["E2_GPa", "E₂ (GPa)", "Across the fibres"],
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

export function LaminateCalculator({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [form, setForm] = useState<CalculatorForm>(exampleForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState("Example inputs loaded. Select Solve to see the results.");
  const activeRequest = useRef<AbortController | null>(null);
  useEffect(() => () => activeRequest.current?.abort("unmount"), []);
  // The home page's "Want to check the math?" leaves its inputs here once; they replace the example, nothing is calculated yet.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(calculatorHandoffKey);
      if (!raw) return;
      sessionStorage.removeItem(calculatorHandoffKey);
      const handed = readCalculatorHandoff(raw);
      if (handed) {
        setForm({ ...handed, material: { ...handed.material, source_reference: shownCitation(handed.material.source_reference) } });
        setStatus("Inputs carried over from the home page. Select Solve to see the results.");
      }
    } catch { /* storage blocked: the example stays */ }
  }, []);

  function update(next: CalculatorForm) {
    setForm(next); setErrors({}); setMessage(""); setResult(null);
    setStatus("Inputs changed. Solve again to see results for the current values.");
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !apiBaseUrl) return;
    setResult(null); setMessage("");
    const parsed = buildAnalysisRequest(form);
    if (parsed.errors) {
      setErrors(parsed.errors); setMessage("Review the highlighted inputs and try again."); setStatus(""); return;
    }
    setErrors({}); setPending(true); setStatus("Solving…");
    const controller = new AbortController();
    activeRequest.current = controller;
    const timeout = window.setTimeout(() => controller.abort("timeout"), 20_000);
    try {
      const answer = await requestAnalysis(apiBaseUrl, parsed.request, controller.signal);
      if (!controller.signal.aborted) { setResult(answer); setStatus("Solved. Results match the current inputs."); }
    } catch (error) {
      if (controller.signal.reason === "unmount") return;
      setStatus("");
      setMessage(controller.signal.aborted
        ? controller.signal.reason === "timeout" ? "The analysis took too long. Your inputs are kept; try again." : "Calculation cancelled. Your inputs are unchanged."
        : error instanceof CalculationError ? error.message : ANALYSIS_UNAVAILABLE);
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
            update(exampleForm()); setStatus("Example inputs loaded. Select Solve to see the results.");
          }}><RotateCcw size={14} /> Load example</button>
        </div>
        <p className="calc-intro">One material across the stack. The example uses AS4 / 3501-6 from the material library under a uniaxial tension load.</p>
        <fieldset disabled={pending}>
          <legend>Material</legend>
          <div className="calc-field calc-source">
            <label htmlFor="material.library">Library material</label>
            <select id="material.library" value={form.material.library} aria-describedby="library-help"
              onChange={(e) => {
                const option = findLibraryOption(e.target.value);
                if (!option) { update({ ...form, material: { ...form.material, library: "" } }); return; }
                // Display values are rounded for the fields; the request sends the dataset reference itself.
                update({ ...form,
                  material: { library: option.value, E1_GPa: option.E1_GPa, E2_GPa: option.E2_GPa, G12_GPa: option.G12_GPa, nu12: option.nu12, source_reference: shownCitation(option.citation) },
                  plies: option.thickness_mm ? form.plies.map((ply) => ({ ...ply, thickness_mm: option.thickness_mm! })) : form.plies });
              }}>
              <option value="">Enter values manually</option>
              {libraryOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <span id="library-help" className={errors["material.library"] ? "calc-field-error" : "calc-hint"}>
              {errors["material.library"] || (form.material.library
                ? "Values shown are rounded; the analysis uses the full cited values. Editing a value switches to manual entry."
                : "Pick a cited dataset from the material library, or type values and their source below.")}
            </span>
          </div>
          <div className="calc-field-grid">{materialFields.map(([key, label, hint]) =>
            <NumericField key={key} name={`material.${key}`} label={label} hint={hint} value={form.material[key]} error={errors[`material.${key}`]}
              onChange={(value) => update({ ...form, material: { ...form.material, [key]: value, library: "" } })} />
          )}</div>
          {errors.material && <p className="calc-field-error">{errors.material}</p>}
          <div className="calc-field calc-source"><label htmlFor="material.source_reference">Material source</label>
            <textarea id="material.source_reference" rows={4} value={form.material.source_reference}
              onChange={(e) => update({ ...form, material: { ...form.material, source_reference: e.target.value, library: "" } })}
              aria-invalid={Boolean(errors["material.source_reference"])} aria-describedby="source-help" />
            <span id="source-help" className={errors["material.source_reference"] ? "calc-field-error" : "calc-hint"}>
              {errors["material.source_reference"] || "Update the citation if you change these properties. Source text is supplied by you and is not verified here."}
            </span>
          </div>
        </fieldset>
        <fieldset disabled={pending}>
          <legend>Ply stack</legend>
          <p className="calc-hint">{ANGLE_CONVENTION}</p>
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
          <p className="calc-hint">Loads are per unit width. Use 0 for loads that do not act.</p>
          <div className="calc-field-grid calc-loads">{loadNames.map((name) => <NumericField key={name} name={`loads.${name}`}
            label={`${name} (${name.startsWith("N") ? "N/m" : "N·m/m"})`} value={form.loads[name]} error={errors[`loads.${name}`]}
            onChange={(value) => update({ ...form, loads: { ...form.loads, [name]: value } })} />)}</div>
        </fieldset>
        {!apiBaseUrl && <p className="calc-notice">Calculations are unavailable on this site. You can still inspect the example inputs.</p>}
        {message && <p className="calc-alert" role="alert">{message}</p>}
        <div className="calc-actions">
          <button className="button primary" type="submit" disabled={pending || !apiBaseUrl}>{pending ? "Solving…" : "Solve"}<ArrowRight size={16} /></button>
          {pending && <button className="calc-text-button" type="button" onClick={() => activeRequest.current?.abort("cancel")}>Cancel</button>}
        </div>
      </form>

      {/* the run's id and the engine's version stay with the record and in data attributes for support, not on the screen (style guide, rule 1) */}
      <section className="calc-output" aria-labelledby="results-title" aria-busy={pending} data-run-id={result?.run_id ?? undefined} data-version={result?.engine_version}>
        <div className="calc-panel-title"><span className="eyebrow">02 / INSPECT</span><span className="calc-hint">Results</span></div>
        <h2 id="results-title">Laminate response</h2>
        <p className="calc-status" role="status">{status}</p>
        {result ? <div className="calc-results" data-testid="calculation-results">
          <div className="calc-vector"><h3>Mid-plane strain <span>microstrain</span></h3>
            <dl>{["εx", "εy", "γxy"].map((label, i) => <div key={label}><dt>{label}</dt><dd data-testid={`strain-${i}`}>{formatted(result.midplane_strain[i] * MICRO)}</dd></div>)}</dl>
          </div>
          <div className="calc-vector"><h3>Curvature <span>1/m</span></h3>
            <dl>{["κx", "κy", "κxy"].map((label, i) => <div key={label}><dt>{label}</dt><dd data-testid={`curvature-${i}`}>{formatted(result.curvature_per_m[i])}</dd></div>)}</dl>
          </div>
          <p className="calc-hint">γxy is engineering shear strain.</p>
          {result.material_provenance && <div className="calc-provenance" data-testid="material-provenance" data-dataset={result.material_provenance.dataset_id}>
            <h3>Material source <span>{result.material_provenance.name}</span></h3>
            <p>{result.material_provenance.citation}</p>
            <ul>{result.material_provenance.values.map((v) => <li key={v.role}>
              <strong>{v.role}</strong> = {v.source_value} {v.source_unit === "—" ? "" : v.source_unit} · {v.basis} · <a href={v.reference_url} target="_blank" rel="noreferrer">page {v.printed_page ?? v.page}</a>
            </li>)}</ul>
            {result.material_provenance.not_provided.length > 0 && <p className="calc-hint">Not provided by this dataset: {result.material_provenance.not_provided.join("; ")}.</p>}
          </div>}
          {(() => {
            const shownAbd = shownMatrices(result);
            return <>
              <Matrix title="A" unit="MN/m" meaning="Stretching stiffness" values={scaledBy(shownAbd.A, 1e6)} />
              <Matrix title="B" unit="kN" meaning="Stretching–bending coupling" values={scaledBy(shownAbd.B, 1e3)} />
              <Matrix title="D" unit="N·m" meaning="Bending stiffness" values={shownAbd.D} />
            </>;
          })()}
        </div> : <div className="calc-empty"><Layers3 size={34} strokeWidth={1} /><h3>No results yet</h3><p>Select Solve to see the A, B and D matrices, mid-plane strains and curvatures.</p></div>}
        <p className="calc-scope">Flat, unnotched laminates · One material · Linear elastic classical laminate theory. This page reports stiffness and deformation; for first-ply failure and temperature change, open the <Link href="/workspace/laminate">laminate workspace</Link>. Results are for research exploration, not design approval.</p>
      </section>
    </div>
  );
}
