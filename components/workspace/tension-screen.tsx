"use client";

import { useEffect, useState } from "react";
import { ENABLED, hiddenItem, isUnsymmetricLayup, notOffered } from "@/lib/enabled-tests";
import { isActive, StudioError } from "@/lib/studio-api";
import { ANALYSIS_UNAVAILABLE, checkText, customerText, downloadable, runStatus, sentence } from "@/lib/studio-copy";
import { layupNotation, layupRows, parseLayup } from "@/lib/studio-chat";
import { appliedOf } from "@/lib/applied";
import { builtFor, loadLine, meshLine, sizeLine, tabState, type TabId } from "@/lib/model-tree";
import { libraryOptions, NO_STANDARD, PLY_KEYS, rowErrorsFrom, type StudioForm } from "@/lib/studio-form";
import {
  builtLines, D3039, isOwnMaterial, LOAD_KEYS, MESH_KEYS, needsPlyThickness, OWN_MATERIAL_KEYS, SIZE_KEYS, TENSION_HINTS, TENSION_LABELS, tensionMissing, valuesInUse,
  tensionValues, underD3039, type BuiltLine,
} from "@/lib/tension-screen";
import { FieldGrid } from "@/components/studio/coupon-form";
import { remembered, RUN_BY_KEY } from "@/components/studio/local";
import { JobFiles, namingOf } from "@/components/studio/job-files";
import { useProject } from "@/components/studio/project-context";
import { StepPanel } from "./panels/step-panel";

const TENSION = "unnotched tension";
const OWN = "own";

/** The tension coupon's model tree (ADR-0111, on ADR-0090): Test, Geometry, Material, Layup, Analysis step, Boundary conditions, Loads,
 * Mesh, Solve and Results, in the order a finite element program sets a model up. The engineer gives the material and the layup; the
 * standard and the software choose every other row, and each tab says what it chose and why. A tab's line says its value; Boundary
 * conditions and Loads light their part of the model while open. Run analysis, above the tree, runs the setup check and, when it is
 * ready, the full analysis; the report and the solver input appear under Results (ADR-0091 amendment 2). */
export function TensionScreen({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, setForm, run: runner, imports, imported, emphasis, setEmphasis } = useProject();
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
  const available = downloadable(job, false); // the product's view: the customer's files (D4), once the run has ended (ADR-0064 amendment 2)
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

  const preview = checked?.preview ?? runner.live?.preview ?? null;
  const applied = preview ? appliedOf(preview) : null;
  const inUse = valuesInUse(checklist);
  const chosenControl = String(checklist?.built?.find((b) => b.row === "control")?.value ?? "") || null;
  const material = own ? (form.own_name || "My own material") : libraryOptions.find((m) => m.id === form.library)?.name ?? null;
  const notation = layupNotation(form);
  const plies = PLY_KEYS.filter((key) => (form[key] ?? "").trim()).length * ((form.symmetric ?? "").trim() === "yes" ? 2 : 1);
  const state = (id: TabId) => tabState(id, checklist);
  /** A tab whose part is drawn on the model lights it while it is open (ADR-0111). */
  const lights = (id: "conditions" | "loads") => (open: boolean) => setEmphasis(open ? id : emphasis === id ? null : emphasis);
  const defaults = (id: TabId) => <Defaults id={id} lines={builtFor(id, built)} />;

  return (
    <div className="studio-form ws-rail-panels ws-tree" data-testid="tension-screen">
      {!apiBaseUrl ? <p className="studio-alert">Analysis is not available on this page.</p> : null}

      {hidden ? <p className="studio-alert" data-testid="test-not-available">{notOffered(hidden)} Run analysis makes an unnotched tension coupon of the same material and layup.</p> : null}
      {/* the model's action, above its tree: what is still needed, what to fix, and the run's progress (ADR-0111) */}
      <div className="ws-tree-head" data-testid="tree-head">
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={() => void build()} data-testid="build-button"
            disabled={busy || !apiBaseUrl || missing.length > 0 || Boolean(layupError)}>
            {busy ? (checking ? "Checking…" : "Running…") : "Run analysis"}
          </button>
          {/* a model built elsewhere, read and solved as it stands (ADR-0105): a founder's sign-in is offered it here, on the product's
              own screen, and no other test with it (ADR-0089 amendment 6) */}
          {imports && apiBaseUrl ? <button type="button" className="studio-text-button" onClick={imported.show} disabled={busy} data-testid="import-open">Import a model</button> : null}
        </div>
        {missing.length ? <p className="studio-hint" data-testid="tension-missing">Still needed: {missing.join(", ")}.</p> : null}
        {alert ? <p className="studio-alert" role="alert">{alert}</p> : null}
      </div>

      <StepPanel id="test" title="Test" step={1} state={state("test")} open={false}
        note={`Unnotched tension, ${underD3039(form) ? "ASTM D3039" : "no standard"}`}>
        <fieldset className="ws-question" data-testid="tension-standard" disabled={busy}>
          <legend>Which standard?</legend>
          <div className="ws-choices" role="radiogroup" aria-label="Standard">
            {[[D3039, "ASTM D3039", "Specimen size from Table 2; extensometer at mid-length"],
              [NO_STANDARD, "No standard", "Your own size, under Geometry"]].map(([value, title, detail]) => (
              <label key={value} className="ws-choice" data-checked={(value === NO_STANDARD) !== underD3039(form)}>
                <input type="radio" name="tension-standard" value={value} checked={(value === NO_STANDARD) !== underD3039(form)} aria-label={title}
                  onChange={() => edit({ test: TENSION, standard: value })} />
                <span className="ws-choice-title">{title}</span>
                <span className="ws-choice-detail">{detail}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {defaults("test")}
      </StepPanel>

      <StepPanel id="geometry" title="Geometry" step={2} state={state("geometry")} open={!underD3039(form)}
        note={sizeLine(form, inUse) ?? (underD3039(form) ? "from the standard" : "your own size")}>
        <p className="studio-hint">Leave a field blank to use the {underD3039(form) ? "standard's size" : "value shown"}.</p>
        <FieldGrid form={form} keys={SIZE_KEYS} errors={errors} disabled={busy} hints={TENSION_HINTS} placeholders={inUse}
          onChange={(key, value) => edit({ [key]: value })} />
        {defaults("geometry")}
      </StepPanel>

      <StepPanel id="material" title="Material" step={3} state={missingMaterial(missing) ? "missing" : state("material")} note={material ?? "choose one"}>
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
        {defaults("material")}
      </StepPanel>

      <StepPanel id="layup" title="Layup" step={4} state={missing.includes("the layup") ? "missing" : state("layup")}
        note={notation ? `${notation}, ${plies} plies` : "bottom ply first"}>
        <form className="studio-field" onSubmit={(e) => { e.preventDefault(); applyLayup(); }}>
          <label htmlFor="tension-layup">Layup, bottom ply first</label>
          <span className="chat-inline">
            <input id="tension-layup" type="text" placeholder="[45/0/-45/90]s" value={layup} disabled={busy} autoComplete="off"
              onChange={(e) => { setLayup(e.target.value); setLayupError(""); }} onBlur={() => { if (layup.trim() && layup !== layupNotation(form)) applyLayup(); }} />
            <button type="submit" className="studio-text-button" disabled={busy}>Use</button>
          </span>
          {layupError ? <span className="chat-error" role="alert">{layupError}</span> : null}
          <span className="studio-hint">0° runs along the load.</span>
        </form>
      </StepPanel>

      <StepPanel id="step" title="Analysis step" step={5} open={false} note="Static, linear">
        <p className="studio-hint" data-testid="tree-step">One static step, linear: the load is applied in one go and every result scales with it.</p>
      </StepPanel>

      <StepPanel id="conditions" title="Boundary conditions" step={6} state={state("conditions")} open={false} onToggle={lights("conditions")}
        note={applied ? `${applied.conditions.length} on the grips` : "on the grips"}>
        {applied ? (
          <ul className="ws-tree-lines" data-testid="tree-conditions">{applied.conditions.map((c) => <li key={c.set}>{c.words}</li>)}</ul>
        ) : <p className="studio-hint">Drawn on the model and listed here once it is built.</p>}
        <p className="studio-hint">A tension test holds the coupon by its grips: the bottom one fixed, the top one moving along the coupon.</p>
        {defaults("conditions")}
      </StepPanel>

      <StepPanel id="loads" title="Loads" step={7} state={state("loads")} open={false} onToggle={lights("loads")}
        note={loadLine(form, inUse, chosenControl) ?? "a pull at the top grip"}>
        {applied ? (
          <ul className="ws-tree-lines" data-testid="tree-loads">{applied.loads.map((l) => <li key={`${l.set}-${l.direction}`}>{l.words}</li>)}</ul>
        ) : null}
        <p className="studio-hint">Leave a field blank to use the default.</p>
        <FieldGrid form={form} keys={LOAD_KEYS} errors={errors} disabled={busy} hints={TENSION_HINTS}
          placeholders={chosenControl ? { ...inUse, control: chosenControl } : inUse}
          onChange={(key, value) => edit({ [key]: value })} />
        {defaults("loads")}
      </StepPanel>

      <StepPanel id="mesh" title="Mesh" step={8} state={state("mesh")} open={false}
        note={meshLine(form, inUse, preview?.mesh.element_count ?? null) ?? "2 mm elements"}>
        <FieldGrid form={form} keys={MESH_KEYS} errors={errors} disabled={busy} hints={TENSION_HINTS} placeholders={inUse}
          onChange={(key, value) => edit({ [key]: value })} />
        {preview ? <p className="studio-hint">{preview.mesh.element_count} shell elements, {preview.mesh.node_count} nodes.</p> : null}
        {defaults("mesh")}
      </StepPanel>

      <StepPanel id="run" title="Solve" step={9} state={problems.length ? "fail" : state("run")} open={problems.length > 0 || Boolean(job)}
        note={job ? undefined : "Run analysis, above"}>
        {problems.length ? (
          <ul className="studio-alert" data-testid="tension-problems">{problems.map((item) => <li key={item.id}><strong>{item.label}:</strong> {checkText(item)}</li>)}</ul>
        ) : null}
        {job ? <p className={job.state === "stopped" || job.state === "refused" ? "studio-alert" : "studio-status"} role="status" data-testid="status">
          {runStatus(job, "Results")}</p> : <p className="studio-hint">Run analysis checks the setup, then solves it and verifies the result.</p>}
      </StepPanel>

      <StepPanel id="outputs" title="Results" step={10} open={available.length > 0} note={available.length ? undefined : "after the analysis"}>
        {job && available.length ? (
          <JobFiles apiBase={apiBaseUrl} job={job} naming={namingOf(fields, form, layupNotation(form))} testId="tension-files" />
        ) : <p className="studio-hint">The report and files appear here when the analysis finishes. The results show on the model.</p>}
      </StepPanel>
    </div>
  );
}

const missingMaterial = (missing: string[]): boolean => missing.some((m) => m !== "the layup" && !/length|width/i.test(m));

/** What the software chose for a tab, each with its reason (ADR-0090), shown in the tab it belongs to (ADR-0111). */
function Defaults({ id, lines }: { id: TabId; lines: BuiltLine[] }) {
  if (!lines.length) return null;
  return (
    <div className="studio-table-scroll ws-tree-defaults">
      <table className="studio-table studio-table-prose" data-testid={`defaults-${id}`}>
        <caption>Chosen for you</caption>
        <tbody>{lines.map((line) => {
          const why = customerText(line.reason);
          return (
            <tr key={line.key} data-row={line.key}><th scope="row" className="studio-wrap">{line.label}</th>
              <td className="studio-num">{line.value}</td>
              <td className="studio-wrap studio-muted">{why ? `${sentence(why).replace(/[.;,:]$/, "")}.` : ""}</td></tr>
          );
        })}</tbody>
      </table>
    </div>
  );
}
