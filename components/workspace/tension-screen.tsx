"use client";

import { useEffect, useState } from "react";
import { ENABLED, hiddenItem, isUnsymmetricLayup, notOffered } from "@/lib/enabled-tests";
import { isActive, StudioError } from "@/lib/studio-api";
import { ANALYSIS_UNAVAILABLE, checkText, customerText, downloadsFor, runStatus, sentence } from "@/lib/studio-copy";
import { layupNotation, layupRows, parseLayup } from "@/lib/studio-chat";
import { libraryOptions, NO_STANDARD, rowErrorsFrom, type StudioForm } from "@/lib/studio-form";
import {
  builtLines, D3039, isOwnMaterial, LOAD_KEYS, MESH_KEYS, needsPlyThickness, OWN_MATERIAL_KEYS, SIZE_KEYS, TENSION_HINTS, TENSION_LABELS, tensionMissing,
  tensionValues, underD3039,
} from "@/lib/tension-screen";
import { FieldGrid } from "@/components/studio/coupon-form";
import { remembered, RUN_BY_KEY } from "@/components/studio/local";
import { JobFiles, namingOf } from "@/components/studio/job-files";
import { useProject } from "@/components/studio/project-context";
import { StepPanel } from "./panels/step-panel";

const TENSION = "unnotched tension";
const OWN = "own";

/** The tension coupon's screen (ADR-0090): the material and the layup, then Run analysis. The standard and the software choose every other
 * row, and "Model settings" says what and why; four things may be changed, folded under "Change settings". Run analysis runs the setup
 * check and, when it is ready, the full analysis; the report and the solver input appear under Files (ADR-0091 amendment 2). */
export function TensionScreen({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, setForm, run: runner } = useProject();
  const { checking, checked, job, fields, problem } = runner;
  const [layup, setLayup] = useState(() => layupNotation(form));
  const [layupError, setLayupError] = useState("");
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [ownPicked, setOwnPicked] = useState(() => !form.library && Boolean(form.own_name));
  const busy = checking || isActive(job?.state);
  const hidden = hiddenItem(form, false); // a project of a test the studio does not offer yet (ADR-0089)

  useEffect(() => { setLayup(layupNotation(form)); }, [form.ply_1, form.symmetric]); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (rows: StudioForm) => { setForm((f) => ({ ...f, ...rows })); runner.clearChecked(); setMessage(""); setErrors({}); };
  const own = ownPicked || isOwnMaterial(form) && Boolean(form.own_name);
  const missing = tensionMissing(form);
  const checklist = checked?.checklist ?? null;
  const built = builtLines(checklist);
  const problems = checklist?.items.filter((item) => item.state === "fail" || item.state === "missing") ?? [];
  const available = job ? downloadsFor(false).filter(([key]) => key in job.outputs) : []; // the product's view: the customer's files (D4)
  // an outage the live preview met is said here, once; the assistant leaves it to the rail on this screen (audit fea-run-48)
  const alert = message || (problem === ANALYSIS_UNAVAILABLE ? ANALYSIS_UNAVAILABLE : "");

  function pickMaterial(value: string) {
    if (value === OWN) { setOwnPicked(true); edit({ library: "" }); return; }
    setOwnPicked(false);
    edit({ library: value, ...Object.fromEntries(OWN_MATERIAL_KEYS.map((key) => [key, ""])) });
  }

  function applyLayup(text = layup) {
    const parsed = parseLayup(text);
    if (!parsed) { setLayupError("Use the form [45/0/-45/90]s, [0/90]2s or [±45]2s, bottom ply first."); return; }
    // a layup that bends as it is pulled is refused here, before Run analysis, in the words the setup check uses (ADR-0089 amendment 4)
    if (isUnsymmetricLayup(parsed)) { setLayupError(ENABLED.unsymmetric ?? "Use a layup that reads the same from both faces."); return; }
    setLayupError("");
    edit(layupRows(parsed));
  }

  async function build() {
    // a refused layup never reached the form, which still holds the one before: nothing runs until the layup is fixed (review R2-3)
    if (!apiBaseUrl || missing.length || layupError) return;
    setMessage(""); setErrors({});
    const values = tensionValues({ ...form, filled_by: form.filled_by || remembered(RUN_BY_KEY) });
    try {
      const answer = await runner.check(values);
      setErrors(rowErrorsFrom(answer.checklist));
      if (answer.state !== "ready") { setMessage("Fix the items below, then run again."); return; }
      await runner.solve(values, (form.filled_by || remembered(RUN_BY_KEY) || "studio").trim(), answer.checklist.coupon_exists);
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The analysis could not start. Try again.");
      if (error instanceof StudioError && error.message === ANALYSIS_UNAVAILABLE) runner.setProblem(ANALYSIS_UNAVAILABLE); // the stage says it waits too
    }
  }

  return (
    <div className="studio-form ws-rail-panels" data-testid="tension-screen">
      {!apiBaseUrl ? <p className="studio-alert">Analysis is not available on this page.</p> : null}

      {hidden ? <p className="studio-alert" data-testid="test-not-available">{notOffered(hidden)} Run analysis makes an unnotched tension coupon of the same material and layup.</p> : null}
      <StepPanel id="tension-coupon" title="Unnotched tension coupon">
        <fieldset className="ws-question" data-testid="tension-standard" disabled={busy}>
          <legend>Which standard?</legend>
          <div className="ws-choices" role="radiogroup" aria-label="Standard">
            {[[D3039, "ASTM D3039", "Specimen size from Table 2; extensometer at mid-length"],
              [NO_STANDARD, "No standard", "Your own size, under Change settings"]].map(([value, title, detail]) => (
              <label key={value} className="ws-choice" data-checked={(value === NO_STANDARD) !== underD3039(form)}>
                <input type="radio" name="tension-standard" value={value} checked={(value === NO_STANDARD) !== underD3039(form)} aria-label={title}
                  onChange={() => edit({ test: TENSION, standard: value })} />
                <span className="ws-choice-title">{title}</span>
                <span className="ws-choice-detail">{detail}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </StepPanel>

      <StepPanel id="tension-input" title="Material and layup" state={missing.length ? "missing" : "pass"}>
        <div className="studio-field">
          <label htmlFor="tension-material">Material</label>
          <select id="tension-material" value={own ? OWN : form.library ?? ""} onChange={(e) => pickMaterial(e.target.value)} disabled={busy}
            aria-invalid={Boolean(errors.library)}>
            <option value="">Choose a material</option>
            {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            <option value={OWN}>My own material…</option>
          </select>
        </div>
        {own ? (
          <div data-testid="own-material">
            <p className="studio-hint">Your material&apos;s constants and their source. G13 and G23 are optional.</p>
            <FieldGrid form={form} keys={OWN_MATERIAL_KEYS} errors={errors} disabled={busy} hints={TENSION_HINTS} labels={TENSION_LABELS}
              onChange={(key, value) => edit({ [key]: value })} />
          </div>
        ) : needsPlyThickness(form) ? (
          <div data-testid="library-ply-thickness">
            <p className="studio-hint">The library gives no ply thickness for this material. Enter the cured ply thickness.</p>
            <FieldGrid form={form} keys={["ply_thickness"]} errors={errors} disabled={busy} hints={TENSION_HINTS} onChange={(key, value) => edit({ [key]: value })} />
          </div>
        ) : null}
        <form className="studio-field" onSubmit={(e) => { e.preventDefault(); applyLayup(); }}>
          <label htmlFor="tension-layup">Layup, bottom ply first</label>
          <span className="chat-inline">
            <input id="tension-layup" type="text" placeholder="[45/0/-45/90]s" value={layup} disabled={busy} autoComplete="off"
              onChange={(e) => { setLayup(e.target.value); setLayupError(""); }} onBlur={() => { if (layup.trim() && layup !== layupNotation(form)) applyLayup(); }} />
            <button type="submit" className="studio-text-button" disabled={busy}>Use</button>
          </span>
          {layupError ? <span className="chat-error" role="alert">{layupError}</span> : null}
        </form>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={() => void build()} data-testid="build-button"
            disabled={busy || !apiBaseUrl || missing.length > 0 || Boolean(layupError)}>
            {busy ? (checking ? "Checking…" : "Running…") : "Run analysis"}
          </button>
        </div>
        {missing.length ? <p className="studio-hint" data-testid="tension-missing">Still needed: {missing.join(", ")}.</p> : null}
        {problems.length ? (
          <ul className="studio-alert" data-testid="tension-problems">{problems.map((item) => <li key={item.id}><strong>{item.label}:</strong> {checkText(item)}</li>)}</ul>
        ) : null}
        {alert ? <p className="studio-alert" role="alert">{alert}</p> : null}
        {job ? <p className={job.state === "stopped" || job.state === "refused" ? "studio-alert" : "studio-status"} role="status" data-testid="status">
          {runStatus(job, "Files")}</p> : null}
      </StepPanel>

      <StepPanel id="tension-change" title="Change settings" open={!underD3039(form)} note="load, size, mesh">
        <p className="studio-hint">Leave a field blank to use the default.</p>
        <FieldGrid form={form} keys={[...LOAD_KEYS, ...SIZE_KEYS, ...MESH_KEYS]} errors={errors} disabled={busy} hints={TENSION_HINTS}
          onChange={(key, value) => edit({ [key]: value })} />
      </StepPanel>

      <StepPanel id="tension-built" title="Model settings" open={built.length > 0} note={built.length ? `${built.length} defaults` : "filled in when the analysis runs"}>
        {built.length ? (
          <div className="studio-table-scroll">
            <table className="studio-table studio-table-prose" data-testid="tension-built">
              <thead><tr><th scope="col">Setting</th><th scope="col" className="studio-num-head">Value</th><th scope="col">Why</th></tr></thead>
              <tbody>{built.map((line) => {
                const why = customerText(line.reason);
                return (
                  <tr key={line.key} data-row={line.key}><th scope="row" className="studio-wrap">{line.label}</th>
                    <td className="studio-num">{line.value}</td>
                    <td className="studio-wrap studio-muted">{why ? `${sentence(why).replace(/[.;,:]$/, "")}.` : ""}</td></tr>
                );
              })}</tbody>
            </table>
          </div>
        ) : <p className="studio-hint">The defaults used for this run, and why.</p>}
      </StepPanel>

      <StepPanel id="tension-files" title="Files" open={available.length > 0} note={available.length ? undefined : "after the analysis"}>
        {job && available.length ? (
          <JobFiles apiBase={apiBaseUrl} job={job} naming={namingOf(fields, form, layupNotation(form))} testId="tension-files" />
        ) : <p className="studio-hint">Files appear here when the analysis finishes.</p>}
      </StepPanel>
    </div>
  );
}
