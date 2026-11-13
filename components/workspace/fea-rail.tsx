"use client";

import { useCallback, useEffect, useState } from "react";
import { hiddenReason, isRowEnabled, isTestEnabled } from "@/lib/enabled-tests";
import { couponValues, DOWNLOADS, isActive, listCoupons, StudioError, type CheckAnswer, type CouponSummary } from "@/lib/studio-api";
import { runStatus } from "@/lib/studio-copy";
import { layupNotation } from "@/lib/studio-chat";
import { JobFiles, namingOf } from "@/components/studio/job-files";
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
  const { form, plate, setForm, setPlate, run: runner, allTests } = useProject();
  const { checking, checked, job, fields } = runner;
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [runBy, setRunBy] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("Load the example or fill in the inputs, then check the setup.");
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
  const changed = useCallback((what: string) => { setErrors({}); clearChecked(); setMessage(""); setStatus(`${what} changed. Check the setup again.`); }, [clearChecked]);
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
    const hidden = hiddenReason(form, allTests); // a test the studio does not offer yet is not sent (ADR-0089)
    if (hidden) { setMessage(hidden); return null; }
    setMessage(""); setErrors({});
    try {
      const answer = await runner.check(values(named()));
      setErrors(rowErrorsFrom(answer.checklist));
      setStatus(answer.state === "ready" ? "Setup ready." : "Fix the items below.");
      return answer;
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The setup could not be checked. Try again.");
      setStatus("");
      return null;
    }
  }

  async function solve() {
    if (!apiBaseUrl) return;
    const answer = checked ?? (await check());
    if (!answer || answer.state !== "ready") return;
    const name = runBy.trim();
    if (!name) { setMessage("Enter your name under Run by."); return; }
    remember(RUN_BY_KEY, name);
    setMessage("");
    try {
      await runner.solve(values(named()), name, answer.checklist.coupon_exists);
      setStatus("Running. Results appear as soon as the solve finishes.");
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The analysis could not start. Try again.");
    }
  }

  useEffect(() => {
    if (!job || !fields) return;
    setStatus(job.state === "done" ? "Done." : "Solved. Verification and the report follow.");
  }, [job, fields]);
  useEffect(() => { if (runner.problem) setMessage(runner.problem); }, [runner.problem]);

  async function loadCoupon(name: string) {
    if (!apiBaseUrl || !name) return;
    try {
      const loaded = await couponValues(apiBaseUrl, name);
      setForm({ ...formFromValues(loaded), filled_by: form.filled_by || runBy, date: today() });
      setPlate(plateFromValues(loaded));
      setErrors({}); setMessage(""); runner.reset();
      setStatus(`${name} opened. Change what you need, then check the setup.`);
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The coupon could not be opened. Try again.");
    }
  }

  function loadExample() {
    setForm(exampleForm(today())); setErrors({}); clearChecked(); setMessage("");
    setStatus("IM7/8552 example loaded: 250 × 25 mm, 56 mm tabs, [45/0/-45/90]s, 1 mm pull.");
  }

  // the fibre tow test is no coupon: its own panels (ADR-0074), while the switch offers it (ADR-0089)
  if (isTow(form) && allTests) return <TowRail apiBaseUrl={apiBaseUrl} />;

  const busy = checking || isActive(job?.state);
  const checklist = checked?.checklist ?? null;
  const state = (id: PanelId) => panelState(id, checklist);
  // the hidden tests' rows (a hole, a span, a dog-bone, one isotropic material) are not shown while the list is closed (ADR-0089)
  const grid = (id: PanelId, keys = visibleKeys(form, id)) => (
    <FieldGrid form={form} keys={keys.filter((key) => isRowEnabled(key, allTests))} errors={errors} disabled={busy} onChange={edit} />
  );
  /** A step whose rows depend on the test waits for the first step's answer, and says so, instead of showing rows that may not apply. */
  const waiting = (id: PanelId) => (!form.test && NEEDS_TEST.includes(id)
    ? <p className="studio-hint" data-testid={`waiting-${id}`}>Pick the test in step 1 first.</p> : null);
  const failing = checklist?.items.filter((item) => item.state === "fail" || item.state === "missing") ?? [];
  const available = job ? DOWNLOADS.filter(([key]) => key in job.outputs) : [];

  return (
    <div className="studio-form ws-rail-panels" data-testid="studio-form">
      {!apiBaseUrl ? <p className="studio-alert">Analysis is not available on this page.</p> : null}

      <div className="ws-rail-head">
        <SetupLine form={form} />
        <div className="studio-actions">
          <button type="button" className="studio-text-button" onClick={loadExample} disabled={busy}>Load example</button>
          {coupons.length ? (
            <span className="studio-reopen">
              <select value={reopen} onChange={(e) => setReopen(e.target.value)} aria-label="Reopen a coupon" disabled={busy}>
                <option value="">Reopen a coupon…</option>
                {coupons.map((c) => {
                  const offered = isTestEnabled(c.test, allTests); // a coupon of a hidden test is listed, kept, and not reopened (ADR-0089)
                  return <option key={c.name} value={c.name} disabled={!offered}>{c.name} ({offered ? `${c.attempts} run${c.attempts === 1 ? "" : "s"}` : `${c.test}: not offered yet`})</option>;
                })}
              </select>
              <button type="button" className="studio-text-button" onClick={() => loadCoupon(reopen)} disabled={busy || !reopen}>Reopen</button>
            </span>
          ) : null}
        </div>
      </div>

      <StepPanel id="test" step={stepNumber("test")} title="Test and standard" state={state("test")}>
        <TestStep form={form} disabled={busy} onChange={edit} allTests={allTests} />
        {grid("test", visibleKeys(form, "test").filter((key) => key === "specimen"))}
        <StandardCard form={form} checklist={checklist} allTests={allTests} />
      </StepPanel>

      <StepPanel id="project" step={stepNumber("project")} title="Project" state={state("project")}>
        {grid("project")}
        {checklist?.designation ? <p className="studio-hint">Coupon {checklist.designation}{checklist.coupon_exists ? `, ${checklist.attempts} run${checklist.attempts === 1 ? "" : "s"} so far` : ", new"}.</p> : null}
      </StepPanel>

      <StepPanel id="geometry" step={stepNumber("geometry")} title="Geometry" state={state("geometry")}>
        {waiting("geometry") ?? (
          <>
            <StandardSize form={form} disabled={busy} onRows={editSize} />
            {grid("geometry")}
            <StepStandard form={form} id="geometry" checklist={checklist} />
            {isPlate ? <p className="studio-hint">A plate&apos;s regions are listed under Loads and supports.</p> : null}
          </>
        )}
      </StepPanel>

      <StepPanel id="layup" step={stepNumber("layup")} title="Layup and material" state={state("layup")}>
        {waiting("layup") ?? (
          <>
            {grid("layup", visibleKeys(form, "layup").filter((key) => key === "material_kind"))}
            {isIsotropic(form)
              ? <p className="studio-hint" data-testid="isotropic-hint">One isotropic material, such as a plastic: give its thickness, E and ν, name and source. Failure is not predicted for it.</p>
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
            {checked?.preview ? <p className="studio-hint">{checked.preview.mesh.element_count} elements, {checked.preview.mesh.node_count} nodes.</p> : null}
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
              return target ? <button type="button" key={item.id} className="studio-text-button" onClick={() => showPanel(target)}>Fix {item.label.toLowerCase()} ({panel(target).title})</button> : null;
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
          <span className="studio-hint">Your name goes on the report.</span>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={solve} disabled={busy || !apiBaseUrl || (checked !== null && checked.state !== "ready")} data-testid="solve-button">Run full analysis</button>
        </div>
        {job ? <p className="studio-hint">{runStatus(job, "Outputs")}</p> : null}
      </StepPanel>

      <StepPanel id="outputs" title="Outputs">
        {job && available.length ? (
          <JobFiles apiBase={apiBaseUrl} job={job} naming={namingOf(fields, form, layupNotation(form))} all />
        ) : <p className="studio-hint">Files appear here when the analysis finishes.</p>}
      </StepPanel>

      <StepPanel id="advanced" title="Advanced" open={false} note="names and codes">
        <p className="studio-hint">Optional inputs. Codes left blank are derived.</p>
        {grid("advanced")}
      </StepPanel>
    </div>
  );
}
