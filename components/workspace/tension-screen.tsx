"use client";

import { useEffect, useState } from "react";
import { hiddenReason } from "@/lib/enabled-tests";
import { DOWNLOADS, fileUrl, isActive, StudioError } from "@/lib/studio-api";
import { layupNotation, layupRows, parseLayup } from "@/lib/studio-chat";
import { libraryOptions, NO_STANDARD, rowErrorsFrom, type StudioForm } from "@/lib/studio-form";
import {
  builtLines, D3039, isOwnMaterial, LOAD_KEYS, MESH_KEYS, OWN_MATERIAL_KEYS, SIZE_KEYS, tensionMissing, tensionValues, underD3039,
} from "@/lib/tension-screen";
import { FieldGrid } from "@/components/studio/coupon-form";
import { remembered, RUN_BY_KEY } from "@/components/studio/local";
import { useProject } from "@/components/studio/project-context";
import { StepPanel } from "./panels/step-panel";

const TENSION = "unnotched tension";
const OWN = "own";

/** The tension coupon's screen (ADR-0090): the material and the layup, then Build. The standard and the software choose every other row,
 * and the list under "How we built it" says what and why; four things may be changed, folded under "Change a choice". The Build runs the
 * setup check and, when it is ready, the full analysis; the decks, the document and the package appear under Files. No Abaqus row is
 * asked for: our Abaqus deck is written from the same model. */
export function TensionScreen({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, setForm, run: runner } = useProject();
  const { checking, checked, job } = runner;
  const [layup, setLayup] = useState(() => layupNotation(form));
  const [layupError, setLayupError] = useState("");
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [ownPicked, setOwnPicked] = useState(() => !form.library && Boolean(form.own_name));
  const busy = checking || isActive(job?.state);
  const hidden = hiddenReason(form, false); // a project of a test the studio does not offer yet (ADR-0089)

  useEffect(() => { setLayup(layupNotation(form)); }, [form.ply_1, form.symmetric]); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (rows: StudioForm) => { setForm((f) => ({ ...f, ...rows })); runner.clearChecked(); setMessage(""); setErrors({}); };
  const own = ownPicked || isOwnMaterial(form) && Boolean(form.own_name);
  const missing = tensionMissing(form);
  const checklist = checked?.checklist ?? null;
  const built = builtLines(checklist);
  const problems = checklist?.items.filter((item) => item.state === "fail" || item.state === "missing") ?? [];
  const available = job ? DOWNLOADS.filter(([key]) => key in job.outputs) : [];

  function pickMaterial(value: string) {
    if (value === OWN) { setOwnPicked(true); edit({ library: "" }); return; }
    setOwnPicked(false);
    edit({ library: value, ...Object.fromEntries(OWN_MATERIAL_KEYS.map((key) => [key, ""])) });
  }

  function applyLayup(text = layup) {
    const parsed = parseLayup(text);
    if (!parsed) { setLayupError("Write it as [45/0/-45/90]s, [0/90]2s or [±45]2s, bottom ply first."); return; }
    setLayupError("");
    edit(layupRows(parsed));
  }

  async function build() {
    if (!apiBaseUrl || missing.length) return;
    setMessage(""); setErrors({});
    const values = tensionValues({ ...form, filled_by: form.filled_by || remembered(RUN_BY_KEY) });
    try {
      const answer = await runner.check(values);
      setErrors(rowErrorsFrom(answer.checklist));
      if (answer.state !== "ready") { setMessage("Something stops the build: the items below say what to change."); return; }
      await runner.solve(values, (form.filled_by || remembered(RUN_BY_KEY) || "studio").trim(), answer.checklist.coupon_exists);
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The build could not start.");
    }
  }

  return (
    <div className="studio-form ws-rail-panels" data-testid="tension-screen">
      {!apiBaseUrl ? <p className="studio-alert">The page was built without the API&apos;s address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be built.</p> : null}

      {hidden ? <p className="studio-alert" data-testid="test-not-available">{hidden} Build makes an unnotched tension coupon of its material and layup; its other rows are kept.</p> : null}
      <StepPanel id="tension-coupon" title="Unnotched tension coupon">
        <fieldset className="ws-question" data-testid="tension-standard" disabled={busy}>
          <legend>Which standard?</legend>
          <div className="ws-choices" role="radiogroup" aria-label="Standard">
            {[[D3039, "ASTM D3039", "the size from Table 2 for your layup, an extensometer at mid-length"],
              [NO_STANDARD, "No standard", "your own size, under Change a choice"]].map(([value, title, detail]) => (
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
            <option value="">choose one</option>
            {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            <option value={OWN}>My own material…</option>
          </select>
        </div>
        {own ? (
          <div data-testid="own-material">
            <p className="studio-hint">Your material&apos;s constants and their source; G13 and G23 may be left blank (taken as stated under How we built it).</p>
            <FieldGrid form={form} keys={OWN_MATERIAL_KEYS} errors={errors} disabled={busy} onChange={(key, value) => edit({ [key]: value })} />
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
            disabled={busy || !apiBaseUrl || missing.length > 0}>
            {busy ? (checking ? "Checking…" : "Building…") : "Build the model"}
          </button>
        </div>
        {missing.length ? <p className="studio-hint" data-testid="tension-missing">Still needed: {missing.join(", ")}.</p> : null}
        {problems.length ? (
          <ul className="studio-alert" data-testid="tension-problems">{problems.map((item) => <li key={item.id}><strong>{item.label}:</strong> {item.message}</li>)}</ul>
        ) : null}
        {message ? <p className="studio-alert" role="alert">{message}</p> : null}
        {job ? <p className="studio-status" role="status" data-testid="status">{job.state === "queued" ? `Queued: ${job.message ?? "waiting for a free solver"}.`
          : job.state === "running" ? `Running: ${job.stage ?? "starting"}.` : job.state === "done" ? "Done: the results are in the centre, the files below."
            : `${job.state}: ${job.message ?? ""}`}</p> : null}
      </StepPanel>

      <StepPanel id="tension-change" title="Change a choice" open={!underD3039(form)} note="pull or force, size and tabs, element size">
        <p className="studio-hint">Leave a row blank and the software chooses it, as How we built it says.</p>
        <FieldGrid form={form} keys={[...LOAD_KEYS, ...SIZE_KEYS, ...MESH_KEYS]} errors={errors} disabled={busy} onChange={(key, value) => edit({ [key]: value })} />
      </StepPanel>

      <StepPanel id="tension-built" title="How we built it" open={built.length > 0} note={built.length ? `${built.length} choices` : "after Build"}>
        {built.length ? (
          <table className="studio-table" data-testid="tension-built">
            <thead><tr><th scope="col">Row</th><th scope="col">Value</th><th scope="col">Why</th></tr></thead>
            <tbody>{built.map((line) => <tr key={line.key} data-row={line.key}><td>{line.label}</td><td>{line.value}</td><td>{line.reason}</td></tr>)}</tbody>
          </table>
        ) : <p className="studio-hint">Build lists every row the software chose for you, with its reason.</p>}
      </StepPanel>

      <StepPanel id="tension-files" title="Files" open={available.length > 0}>
        {job && available.length ? (
          <ul className="studio-downloads ws-outputs" data-testid="tension-files">
            {available.map(([key, label]) => <li key={key}><a href={fileUrl(apiBaseUrl, job.job_id, key)} target="_blank" rel="noreferrer">{label}</a></li>)}
            <li><a href={`/workspace/fea/view?job=${encodeURIComponent(job.job_id)}`} target="_blank" rel="noreferrer">The viewer in a new window</a></li>
          </ul>
        ) : <p className="studio-hint">Our Abaqus deck, the CalculiX deck and results, the document and the package appear here as the build writes them.</p>}
      </StepPanel>
    </div>
  );
}
