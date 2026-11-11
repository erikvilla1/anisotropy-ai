"use client";

import { useCallback, useEffect, useState } from "react";
import { couponValues, DOWNLOADS, fileUrl, isActive, listCoupons, StudioError, type CheckAnswer, type CouponSummary } from "@/lib/studio-api";
import { buildValues, exampleForm, formFromValues, isIsotropic, PLATE_TEST, rowErrorsFrom, withStandard, withTest, type StudioForm } from "@/lib/studio-form";
import { plateFromValues, plateValues, type PlateLists } from "@/lib/studio-plate";
import { MATERIAL_KEYS, NEEDS_TEST, panel, panelState, panelToFix, stepNumber, visibleKeys, type PanelId } from "@/lib/workspace-panels";
import { ChecklistPanel } from "@/components/studio/checklist-panel";
import { FieldGrid } from "@/components/studio/coupon-form";
import { remember, remembered, RUN_BY_KEY, today } from "@/components/studio/local";
import { PlatePanel } from "@/components/studio/plate-panel";
import { StandardCard } from "@/components/studio/standard-card";
import { useProject } from "@/components/studio/project-context";
import { LayupEditor } from "./panels/layup-editor";
import { StandardSize } from "./panels/standard-size";
import { SetupLine, StepStandard } from "./panels/step-standard";
import { showPanel, StepPanel } from "./panels/step-panel";
import { TestStep } from "./panels/test-step";
import { TowRail } from "./tow-rail";
import { isTow } from "@/lib/studio-tow";

/** The left column of the coupon FEA workspace (ADR-0062, part 3): one panel per step, each editing named rows of the one values file
 * (`lib/workspace-panels.ts`), the checklist under Validate, the run under Run, the files under Outputs. The first step asks what test the
 * coupon is and which standard it follows; the steps after it wait for the test, and each shows what the standard asks of it (amendment 1). The rows, the check and the
 * job live in the project store; this column keeps only what belongs to the page: the row errors, the name, the messages. */
export function FeaRail({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, plate, setForm, setPlate, run: runner } = useProject();
  const { checking, checked, job, fields } = runner;
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [runBy, setRunBy] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("Load the example or fill in the rows, then check the setup.");
  const [coupons, setCoupons] = useState<CouponSummary[]>([]);
  const [reopen, setReopen] = useState("");
  useEffect(() => { setRunBy(remembered(RUN_BY_KEY)); }, []);
  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listCoupons(apiBaseUrl, controller.signal).then(setCoupons).catch(() => setCoupons([]));
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);

  const { clearChecked } = runner;
  const changed = useCallback((what: string) => { setErrors({}); clearChecked(); setMessage(""); setStatus(`${what} changed. Check the setup again before solving.`); }, [clearChecked]);
  const edit = useCallback((key: string, value: string) => {
    // a new test or standard clears the rows that belonged to the old one, and says so (ADR-0072)
    const note = key === "test" ? withTest(form, value).note : "";
    setForm((f) => (key === "test" ? withTest(f, value).form : key === "standard" ? withStandard(f, value) : { ...f, [key]: value }));
    changed("Inputs");
    if (note) setStatus(note);
  }, [form, setForm, changed]);
  const editSize = useCallback((rows: StudioForm) => { setForm((f) => ({ ...f, ...rows })); changed("The size"); }, [setForm, changed]);
  const editRows = useCallback((rows: StudioForm) => { setForm((f) => ({ ...f, ...rows })); changed("The layup"); }, [setForm, changed]);
  const editPlate = useCallback((lists: PlateLists) => { setPlate(lists); changed("Supports or loads"); }, [setPlate, changed]);
  const isPlate = form.test === PLATE_TEST;
  const values = (rows: StudioForm = form) => buildValues(rows, isPlate ? plateValues(plate) : undefined);

  /** The rows with the engineer's name: the file names who filled it, and that is the one who runs it unless Advanced says otherwise. */
  function named(): StudioForm {
    const name = runBy.trim();
    if (form.filled_by.trim() || !name) return form;
    const rows = { ...form, filled_by: name };
    setForm(rows);
    return rows;
  }

  async function check(): Promise<CheckAnswer | null> {
    if (!apiBaseUrl) return null;
    setMessage(""); setErrors({});
    try {
      const answer = await runner.check(values(named()));
      setErrors(rowErrorsFrom(answer.checklist));
      setStatus(answer.state === "ready" ? `Setup ready: ${answer.designation ?? "the coupon"} can be solved.` : "The setup is blocked; the items below say what to fix.");
      return answer;
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The setup check failed.");
      setStatus("");
      return null;
    }
  }

  async function solve() {
    if (!apiBaseUrl) return;
    const answer = checked ?? (await check());
    if (!answer || answer.state !== "ready") return;
    const name = runBy.trim();
    if (!name) { setMessage("Give your name under Run by: the attempt log and the CalculiX record name who ran it."); return; }
    remember(RUN_BY_KEY, name);
    setMessage("");
    try {
      await runner.solve(values(named()), name, answer.checklist.coupon_exists);
      setStatus("Solving. The fields appear as soon as our engine has run.");
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The solve could not start.");
    }
  }

  useEffect(() => {
    if (!job || !fields) return;
    setStatus(job.state === "done" ? `Done: ${job.message ?? "the package is written"}.` : "Our engine has run; CalculiX, the record and the package follow.");
  }, [job, fields]);
  useEffect(() => { if (runner.problem) setMessage(runner.problem); }, [runner.problem]);

  async function loadCoupon(name: string) {
    if (!apiBaseUrl || !name) return;
    try {
      const loaded = await couponValues(apiBaseUrl, name);
      setForm({ ...formFromValues(loaded), filled_by: form.filled_by || runBy, date: today() });
      setPlate(plateFromValues(loaded));
      setErrors({}); setMessage(""); runner.reset();
      setStatus(`Coupon ${name} loaded; change what you need and check the setup. Solving it adds the next attempt.`);
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The coupon could not be read.");
    }
  }

  function loadExample() {
    setForm(exampleForm(today())); setErrors({}); clearChecked(); setMessage("");
    setStatus("The public IM7/8552 example is loaded: 250 by 25 mm with 56 mm tabs, [45/0/-45/90]s, 1 mm pull.");
  }

  if (isTow(form)) return <TowRail apiBaseUrl={apiBaseUrl} />; // the fibre tow test is no coupon: its own panels (ADR-0074)

  const busy = checking || isActive(job?.state);
  const checklist = checked?.checklist ?? null;
  const state = (id: PanelId) => panelState(id, checklist);
  const grid = (id: PanelId, keys = visibleKeys(form, id)) => <FieldGrid form={form} keys={keys} errors={errors} disabled={busy} onChange={edit} />;
  /** A step whose rows depend on the test waits for the first step's answer, and says so, instead of showing rows that may not apply. */
  const waiting = (id: PanelId) => (!form.test && NEEDS_TEST.includes(id)
    ? <p className="studio-hint" data-testid={`waiting-${id}`}>Pick the test under step 1 first: what this step asks for depends on it.</p> : null);
  const failing = checklist?.items.filter((item) => item.state === "fail" || item.state === "missing") ?? [];
  const available = job ? DOWNLOADS.filter(([key]) => key in job.outputs) : [];

  return (
    <div className="studio-form ws-rail-panels" data-testid="studio-form">
      {!apiBaseUrl ? <p className="studio-alert">The page was built without the API&apos;s address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.</p> : null}

      <div className="ws-rail-head">
        <SetupLine form={form} />
        <div className="studio-actions">
          <button type="button" className="studio-text-button" onClick={loadExample} disabled={busy}>Load example</button>
          {coupons.length ? (
            <span className="studio-reopen">
              <select value={reopen} onChange={(e) => setReopen(e.target.value)} aria-label="Reopen a coupon" disabled={busy}>
                <option value="">Reopen a coupon…</option>
                {coupons.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.status ?? "?"}, {c.attempts} attempt{c.attempts === 1 ? "" : "s"})</option>)}
              </select>
              <button type="button" className="studio-text-button" onClick={() => loadCoupon(reopen)} disabled={busy || !reopen}>Reopen</button>
            </span>
          ) : null}
        </div>
      </div>

      <StepPanel id="test" step={stepNumber("test")} title="Test and standard" state={state("test")}>
        <TestStep form={form} disabled={busy} onChange={edit} />
        {grid("test", visibleKeys(form, "test").filter((key) => key === "specimen"))}
        <StandardCard form={form} checklist={checklist} />
      </StepPanel>

      <StepPanel id="project" step={stepNumber("project")} title="Project" state={state("project")}>
        {grid("project")}
        {checklist?.designation ? <p className="studio-hint">Coupon {checklist.designation}{checklist.coupon_exists ? `, ${checklist.attempts} attempt${checklist.attempts === 1 ? "" : "s"} so far` : ", new"}: the name is derived from the material, the test and the layup.</p> : null}
      </StepPanel>

      <StepPanel id="geometry" step={stepNumber("geometry")} title="Geometry" state={state("geometry")}>
        {waiting("geometry") ?? (
          <>
            <StandardSize form={form} disabled={busy} onRows={editSize} />
            {grid("geometry")}
            <StepStandard form={form} id="geometry" checklist={checklist} />
            {isPlate ? <p className="studio-hint">A plate&apos;s regions, the boxes you draw, are listed under Loads and supports.</p> : null}
          </>
        )}
      </StepPanel>

      <StepPanel id="layup" step={stepNumber("layup")} title="Layup and material" state={state("layup")}>
        {waiting("layup") ?? (
          <>
            {grid("layup", visibleKeys(form, "layup").filter((key) => key === "material_kind"))}
            {isIsotropic(form)
              ? <p className="studio-hint" data-testid="isotropic-hint">One isotropic material, such as a plastic: no plies, so give its thickness, E and nu, with its name and source. Its yield and failure are not modelled yet, so no failure criterion applies.</p>
              : <LayupEditor form={form} errors={errors} disabled={busy} onChange={edit} onRows={editRows} />}
            {grid("layup", visibleKeys(form, "layup").filter((key) => MATERIAL_KEYS.includes(key)))}
            <StepStandard form={form} id="layup" checklist={checklist} />
          </>
        )}
      </StepPanel>

      <StepPanel id="loads" step={stepNumber("loads")} title="Loads and supports" state={state("loads")}>
        {waiting("loads") ?? (
          <>
            {isPlate ? <PlatePanel form={form} lists={plate} errors={errors} disabled={busy} onChange={editPlate} /> : grid("loads")}
            <StepStandard form={form} id="loads" checklist={checklist} />
          </>
        )}
      </StepPanel>

      <StepPanel id="mesh" step={stepNumber("mesh")} title="Mesh" state={state("mesh")}>
        {waiting("mesh") ?? (
          <>
            {grid("mesh")}
            {checked?.preview ? <p className="studio-hint">{checked.preview.mesh.element_count} elements, {checked.preview.mesh.node_count} nodes, {checked.preview.mesh.mesher} mesher.</p> : null}
          </>
        )}
      </StepPanel>

      <StepPanel id="validate" title="Validate" state={checklist ? (checklist.state === "ready" ? "pass" : "fail") : "none"}>
        <div className="studio-buttons">
          <button type="button" className="studio-button" onClick={check} disabled={busy || !apiBaseUrl} data-testid="check-button">Check setup</button>
        </div>
        <ChecklistPanel checklist={checklist} checking={checking} />
        {failing.length ? (
          <p className="ws-fix-links">
            {failing.map((item) => {
              const target = panelToFix(item);
              return target ? <button type="button" key={item.id} className="studio-text-button" onClick={() => showPanel(target)}>Fix {item.label.toLowerCase()} under {panel(target).title}</button> : null;
            })}
          </p>
        ) : null}
        {message ? <p className="studio-alert" role="alert">{message}</p> : null}
        <p className="studio-status" role="status" data-testid="status">{status}</p>
      </StepPanel>

      <StepPanel id="run" title="Run" state={state("run")}>
        <div className="studio-field studio-run-by">
          <label htmlFor="studio-run-by">Run by</label>
          <input id="studio-run-by" type="text" value={runBy} onChange={(e) => setRunBy(e.target.value)} disabled={busy} autoComplete="name" />
          <span className="studio-hint">Named in the attempt log and the CalculiX record; remembered in this browser.</span>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={solve} disabled={busy || !apiBaseUrl || (checked !== null && checked.state !== "ready")} data-testid="solve-button">Run full analysis</button>
        </div>
        {job ? <p className="studio-hint">{job.state === "queued" ? `Queued: ${job.message ?? "waiting for a free solver"}.` : job.state === "running" ? `Running: ${job.stage ?? "starting"}.` : job.state === "done" ? "Done. The results are in the centre, the files under Outputs." : `${job.state}: ${job.message ?? ""}`}</p> : null}
      </StepPanel>

      <StepPanel id="outputs" title="Outputs">
        {job && available.length ? (
          <ul className="studio-downloads ws-outputs">
            {available.map(([key, label]) => <li key={key}><a href={fileUrl(apiBaseUrl, job.job_id, key)} target="_blank" rel="noreferrer">{label}</a></li>)}
            <li><a href={`/workspace/fea/view?job=${encodeURIComponent(job.job_id)}`} target="_blank" rel="noreferrer">The viewer in a new window</a></li>
          </ul>
        ) : <p className="studio-hint">The package, its PDF, the decks and the CalculiX results appear here as the run writes them.</p>}
      </StepPanel>

      <StepPanel id="advanced" title="Advanced: every other row" open={false} note="names, codes, the Abaqus names">
        <p className="studio-hint">Rows the steps above do not ask for: the coupon&apos;s codes are derived when blank; the Abaqus names only name the deck&apos;s parts.</p>
        {grid("advanced")}
      </StepPanel>
    </div>
  );
}
