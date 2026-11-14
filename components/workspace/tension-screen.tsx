"use client";

import { useEffect, useRef, useState } from "react";
import { ENABLED, hiddenItem, isUnsymmetricLayup, notOffered } from "@/lib/enabled-tests";
import { isActive, StudioError } from "@/lib/studio-api";
import { ANALYSIS_UNAVAILABLE, checkText, customerText, downloadsFor, runStatus, sentence } from "@/lib/studio-copy";
import { layupNotation, layupRows, parseLayup, sameLayup } from "@/lib/studio-chat";
import { libraryOptions, NO_STANDARD, rowErrorsFrom, type StudioForm } from "@/lib/studio-form";
import {
  builtLines, D3039, isOwnMaterial, LOAD_KEYS, MESH_KEYS, needsPlyThickness, OWN_MATERIAL_KEYS, SIZE_KEYS, TENSION_HINTS, TENSION_LABELS, tensionMissing,
  tensionValues, underD3039,
} from "@/lib/tension-screen";
import { OWN_MATERIAL_EVENT, tensionPanelTitle, type PanelState } from "@/lib/workspace-panels";
import { FieldGrid } from "@/components/studio/coupon-form";
import { remembered, RUN_BY_KEY } from "@/components/studio/local";
import { JobFiles, namingOf } from "@/components/studio/job-files";
import { useProject } from "@/components/studio/project-context";
import { TableScroll } from "@/components/studio/table-scroll";
import { showPanel, StepPanel } from "./panels/step-panel";

const TENSION = "unnotched tension";
const OWN = "own";

/** A value of the built settings that is a number with or without its unit ("25", "0.75 mm"): set right in its column (audit fea-run-24). */
const NUMERIC = /^[-−+]?\d/;

/** The tension coupon's screen (ADR-0090): the material and the layup, then Run analysis. The standard and the software choose every other
 * row, and "Model settings" says what and why; four things may be changed, folded under "Change settings". Run analysis runs the setup
 * check and, when it is ready, the full analysis; the report and the solver input appear under Files (ADR-0091 amendment 2). */
export function TensionScreen({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, setForm, setLayupRefused, run: runner } = useProject();
  const { checking, checked, job, fields, problem } = runner;
  const [layup, setLayup] = useState(() => layupNotation(form));
  const [layupError, setLayupError] = useState("");
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false); // the last Run analysis met a failure of the service, not of the setup: the button says Try again
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [ownPicked, setOwnPicked] = useState(() => !form.library && Boolean(form.own_name));
  const busy = checking || isActive(job?.state);
  const hidden = hiddenItem(form, false); // a project of a test the studio does not offer yet (ADR-0089)

  useEffect(() => { setLayup(layupNotation(form)); }, [form.ply_1, form.symmetric]); // eslint-disable-line react-hooks/exhaustive-deps
  // the stage hears of a refused layup, so it does not say "Ready to run" beside a Run analysis that waits for it (round-2 review N6)
  useEffect(() => { setLayupRefused(Boolean(layupError)); return () => setLayupRefused(false); }, [layupError, setLayupRefused]);

  // a changed setup leaves the last run behind, as an edit in the assistant does: no "Verified" line or files of other inputs over the
  // new preview (audit fea-run-J2-2); a run still going keeps its progress
  const edit = (rows: StudioForm) => { setForm((f) => ({ ...f, ...rows })); runner.clearChecked(); runner.clearResults(); setMessage(""); setFailed(false); setErrors({}); };
  const own = ownPicked || isOwnMaterial(form) && Boolean(form.own_name);
  const missing = tensionMissing(form);
  const checklist = checked?.checklist ?? null;
  const built = builtLines(checklist);
  const problems = checklist?.items.filter((item) => item.state === "fail" || item.state === "missing") ?? [];
  const available = job ? downloadsFor(false).filter(([key]) => key in job.outputs) : []; // the product's view: the customer's files (D4)
  // an outage the live preview met is said here, once; the assistant leaves it to the rail on this screen (audit fea-run-48)
  const alert = message || (problem === ANALYSIS_UNAVAILABLE ? ANALYSIS_UNAVAILABLE : "");
  // "checked" only once a check passed; filled but not yet checked is said so (audit fea-run-29)
  const inputState: PanelState = missing.length ? "missing" : problems.length ? "fail" : checklist?.state === "ready" ? "pass" : "pending";
  // a stopped or refused run is said once, in words, on the Analysis card; the rail points there (audit fea-run-18)
  const status = !job ? "" : job.state === "stopped" ? "Stopped. See Analysis." : job.state === "refused" ? "Not started. See Analysis." : runStatus(job, "Files");

  function pickMaterial(value: string) {
    if (value === OWN) { setOwnPicked(true); edit({ library: "" }); return; }
    setOwnPicked(false);
    edit({ library: value, ...Object.fromEntries(OWN_MATERIAL_KEYS.map((key) => [key, ""])) });
  }

  // the assistant's own-material suggestion, answered with the latest state of this screen
  const onOwnMaterial = useRef<() => void>(() => {});
  useEffect(() => {
    onOwnMaterial.current = () => {
      if (busy) return;
      if (!own) pickMaterial(OWN);
      window.setTimeout(() => showPanel("tension-input", "tension-material"), 0); // once the fields of the own material are on the page
    };
  });
  useEffect(() => {
    const listener = () => onOwnMaterial.current();
    window.addEventListener(OWN_MATERIAL_EVENT, listener);
    return () => window.removeEventListener(OWN_MATERIAL_EVENT, listener);
  }, []);

  function applyLayup(text = layup) {
    const parsed = parseLayup(text);
    if (!parsed) { setLayupError("This layup could not be read. Write it as [45/0/-45/90]s, [0/90]2s or [±45]2s, bottom ply first."); return; }
    // a layup that bends as it is pulled is refused here, before Run analysis, in the words the setup check uses (ADR-0089 amendment 4)
    if (isUnsymmetricLayup(parsed)) { setLayupError(ENABLED.unsymmetric ?? "Use a layup that reads the same from both faces."); return; }
    setLayupError("");
    // the same layup again ("Use layup" or Enter with nothing changed) is no edit: the finished run and its files stay (review P1)
    if (sameLayup(form, parsed)) { setLayup(layupNotation(form)); return; }
    edit(layupRows(parsed));
  }

  async function build() {
    // a refused layup never reached the form, which still holds the one before: nothing runs until the layup is fixed (review R2-3)
    if (!apiBaseUrl || missing.length || layupError) return;
    setMessage(""); setFailed(false); setErrors({});
    const values = tensionValues({ ...form, filled_by: form.filled_by || remembered(RUN_BY_KEY) });
    try {
      const answer = await runner.check(values);
      setErrors(rowErrorsFrom(answer.checklist));
      if (answer.state !== "ready") { setMessage("Fix the items below, then run again."); return; }
      await runner.solve(values, (form.filled_by || remembered(RUN_BY_KEY) || "studio").trim(), answer.checklist.coupon_exists);
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The analysis could not start. Try again.");
      setFailed(true);
      if (error instanceof StudioError && error.message === ANALYSIS_UNAVAILABLE) runner.setProblem(ANALYSIS_UNAVAILABLE); // the stage says it waits too
    }
  }

  // the button says the run's state while it waits (decision D23: "Queued…", no Stop), and Try again after the service failed it (audit fea-run-34)
  const runWord = busy ? (checking ? "Checking…" : job?.state === "queued" ? "Queued…" : "Running…") : failed ? "Try again" : "Run analysis";
  return (
    <div className="studio-form ws-rail-panels" data-testid="tension-screen">
      {!apiBaseUrl ? <p className="studio-alert">Analysis is not available on this page.</p> : null}

      {hidden ? <p className="studio-alert" data-testid="test-not-available">{notOffered(hidden)} Run analysis makes an unnotched tension coupon of the same material and layup.</p> : null}
      <StepPanel id="tension-coupon" title={tensionPanelTitle("tension-coupon")}>
        <fieldset className="ws-question" data-testid="tension-standard" disabled={busy}>
          <legend>Which standard?</legend>
          {/* the fieldset is the group and its legend the question; each card's title names its radio and its detail describes it (audit uiux-fea-run-40) */}
          <div className="ws-choices">
            {[[D3039, "ASTM D3039", "Specimen size from Table 2; extensometer at mid-length", "d3039"],
              [NO_STANDARD, "No standard", "Your own size, under Change settings", "none"]].map(([value, title, detail, key]) => (
              <label key={value} className="ws-choice" data-checked={(value === NO_STANDARD) !== underD3039(form)}>
                <input type="radio" name="tension-standard" value={value} checked={(value === NO_STANDARD) !== underD3039(form)}
                  aria-labelledby={`tension-standard-${key}`} aria-describedby={`tension-standard-${key}-detail`}
                  onChange={() => edit({ test: TENSION, standard: value })} />
                <span className="ws-choice-title" id={`tension-standard-${key}`}>{title}</span>
                <span className="ws-choice-detail" id={`tension-standard-${key}-detail`}>{detail}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </StepPanel>

      <StepPanel id="tension-input" title={tensionPanelTitle("tension-input")} state={inputState}>
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
              aria-invalid={layupError ? true : undefined} aria-describedby={layupError ? "tension-layup-error" : undefined}
              onChange={(e) => { setLayup(e.target.value); setLayupError(""); }} onBlur={() => { if (layup.trim() && layup !== layupNotation(form)) applyLayup(); }} />
            <button type="submit" className="chat-secondary" disabled={busy}>Use layup</button>
          </span>
          {layupError ? <span className="chat-error" id="tension-layup-error" role="alert">{layupError}</span> : null}
        </form>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={() => void build()} data-testid="build-button"
            disabled={busy || !apiBaseUrl || missing.length > 0 || Boolean(layupError)} aria-describedby={missing.length ? "tension-missing" : undefined}>
            {runWord}
          </button>
        </div>
        {missing.length ? <p className="studio-hint" id="tension-missing" data-testid="tension-missing">Still needed: {missing.join(", ")}.</p> : null}
        {problems.length ? (
          <ul className="studio-alert" data-testid="tension-problems">{problems.map((item) => <li key={item.id}><strong>{item.label}:</strong> {checkText(item)}</li>)}</ul>
        ) : null}
        {alert ? <p className="studio-alert" role="alert">{alert}</p> : null}
        {job ? <p className={job.state === "stopped" || job.state === "refused" ? "studio-alert" : "studio-status"} role="status" data-testid="status">{status}</p> : null}
      </StepPanel>

      <StepPanel id="tension-change" title={tensionPanelTitle("tension-change")} open={!underD3039(form)} note="load, size, mesh">
        <p className="studio-hint">Leave a field blank to use the default.</p>
        <FieldGrid form={form} keys={[...LOAD_KEYS, ...SIZE_KEYS, ...MESH_KEYS]} errors={errors} disabled={busy} hints={TENSION_HINTS}
          onChange={(key, value) => edit({ [key]: value })} />
      </StepPanel>

      {/* the files first, open once the run has them, and the settings folded then, so the downloads are never pushed out of sight (audit fea-run-57);
          the results in a window of their own are offered once, in the model's heading (audit fea-run-18, uiux-fea-run-28) */}
      <StepPanel id="tension-files" title={tensionPanelTitle("tension-files")} open={available.length > 0} note={available.length ? undefined : "after the analysis"}>
        {job && available.length ? (
          <JobFiles apiBase={apiBaseUrl} job={job} naming={namingOf(fields, form, layupNotation(form))} testId="tension-files" viewer={false} />
        ) : <p className="studio-hint">Files appear here when the analysis finishes.</p>}
      </StepPanel>

      <StepPanel id="tension-built" title={tensionPanelTitle("tension-built")} open={built.length > 0 && available.length === 0}
        note={built.length ? `${built.length} defaults` : "filled in when the analysis runs"}>
        {built.length ? (
          <TableScroll label={tensionPanelTitle("tension-built")}>
            <table className="studio-table studio-table-prose" data-testid="tension-built">
              <thead><tr><th scope="col">Setting</th><th scope="col" className="studio-num-head">Value</th><th scope="col">Why</th></tr></thead>
              <tbody>{built.map((line) => {
                const why = customerText(line.reason);
                return (
                  <tr key={line.key} data-row={line.key}><th scope="row" className="studio-wrap">{line.label}</th>
                    <td className={NUMERIC.test(String(line.value)) ? "studio-num" : "studio-text-cell"}>{line.value}</td>
                    <td className="studio-wrap studio-muted">{why ? `${sentence(why).replace(/[.;,:]$/, "")}.` : ""}</td></tr>
                );
              })}</tbody>
            </table>
          </TableScroll>
        ) : <p className="studio-hint">The defaults used for this run, and why.</p>}
      </StepPanel>
    </div>
  );
}
