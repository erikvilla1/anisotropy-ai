"use client";

import { useCallback, useEffect, useState } from "react";
import { couponValues, listCoupons, StudioError, type CheckAnswer, type CouponSummary, type Preview } from "@/lib/studio-api";
import { buildValues, exampleForm, formFromValues, PLATE_TEST, rowErrorsFrom } from "@/lib/studio-form";
import { plateFromValues, plateValues, regionOptions, regionsOfElement, withLoad, withSupport, type PlateLists } from "@/lib/studio-plate";
import { printed } from "@/lib/studio-colors";
import { CouponForm } from "./coupon-form";
import { ChecklistPanel } from "./checklist-panel";
import { JobProgress } from "./job-progress";
import { PlatePanel } from "./plate-panel";
import { useProject } from "./project-context";
import { ResultsView } from "./results-view";
import { Scene } from "./scene";
import type { SceneMarker } from "./scene-canvas";

const RUN_BY_KEY = "anisotropy.studio.run_by";

function today(): string { return new Date().toISOString().slice(0, 10); }

function remembered(key: string): string {
  try { return window.localStorage.getItem(key) ?? ""; } catch { return ""; }
}

function remember(key: string, value: string) {
  try { window.localStorage.setItem(key, value); } catch { /* a private window or blocked storage: the name is simply not kept */ }
}

/** The nodes a load acts on: a node set, or the corner nodes of an element set (a pressure on an area region). */
function nodesOf(preview: Preview, set: string): number[] {
  if (preview.mesh.node_sets[set]) return preview.mesh.node_sets[set];
  const elements = preview.mesh.element_sets[set];
  if (!elements) return [];
  return [...new Set(elements.flatMap((e) => preview.mesh.quads[e] ?? []))];
}

export function PreviewScene({ preview, onPick, picked }: { preview: Preview; onPick?: (element: number | null) => void; picked?: number | null }) {
  const held: SceneMarker[] = preview.held.filter((h, i, all) => all.findIndex((x) => x.set === h.set) === i)
    .map((h) => ({ nodes: nodesOf(preview, h.set), label: `held: ${h.set} (${h.through ? "through a reference point" : "node by node"})` }));
  const loads = (preview.loads ?? [preview.loaded]).map((l) => ({ nodes: nodesOf(preview, l.set), direction: l.direction,
    label: `${l.control} ${printed(l.value)} ${l.unit} on ${l.set}` }));
  return (
    <div className="studio-scene-block" data-testid="preview">
      <Scene nodes={preview.mesh.nodes} quads={preview.mesh.quads} thickness={preview.geometry.thickness} held={held} loaded={loads[0] ?? null}
        loads={loads.slice(1)} onPick={onPick} picked={picked ?? null} />
      <p className="studio-muted">{preview.coupon.designation ?? "The coupon"}, {preview.coupon.test}: {preview.geometry.length} by {preview.geometry.width} {preview.labels.length},
        {" "}{preview.plies.length} plies {preview.coupon.layup}, {printed(preview.geometry.thickness)} {preview.labels.length} thick; {preview.mesh.element_count} elements.
        The violet frames are held; the amber frames and arrows are the loading.{onPick ? " Click an element to hold or load the region it belongs to." : ""}</p>
    </div>
  );
}

export function CouponStudio({ apiBaseUrl, part }: { apiBaseUrl: string; part?: "input" | "output" }) {
  const { form, plate, setForm, setPlate, run: runner } = useProject(); // the rows and the run live in the project (ADR-0062)
  const { checking, checked, job, fields, explanation } = runner;
  const [pickedElement, setPickedElement] = useState<number | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [runBy, setRunBy] = useState("");
  const [message, setMessage] = useState("");
  const [coupons, setCoupons] = useState<CouponSummary[]>([]);
  const [reopen, setReopen] = useState("");
  const [status, setStatus] = useState("Load the example or fill in the rows, then check the setup.");
  useEffect(() => { setRunBy(remembered(RUN_BY_KEY)); }, []);
  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listCoupons(apiBaseUrl, controller.signal).then(setCoupons).catch(() => setCoupons([]));
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);

  const { clearChecked } = runner;
  const edit = useCallback((key: string, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors({}); clearChecked(); setMessage("");
    setStatus("Inputs changed. Check the setup again before solving.");
  }, [setForm, clearChecked]);
  const editPlate = useCallback((lists: PlateLists) => {
    setPlate(lists);
    setErrors({}); clearChecked(); setMessage("");
    setStatus("Supports or loads changed. Check the setup again before solving.");
  }, [setPlate, clearChecked]);
  const isPlate = form.test === PLATE_TEST;
  const values = () => buildValues(form, isPlate ? plateValues(plate) : undefined);

  async function check(): Promise<CheckAnswer | null> {
    if (!apiBaseUrl) return null;
    setMessage(""); setErrors({});
    try {
      const answer = await runner.check(values());
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
      await runner.solve(values(), name, answer.checklist.coupon_exists);
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

  const busy = checking || (job?.state === "running");
  const viewerLink = job ? `/workspace/fea/view?job=${encodeURIComponent(job.job_id)}` : null;
  const input = (
      <aside className="studio-input">
        {!apiBaseUrl ? <p className="studio-alert">The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.</p> : null}
        <div className="studio-actions">
          <button type="button" className="studio-text-button" onClick={() => { setForm(exampleForm(today())); setErrors({}); clearChecked(); setMessage(""); setStatus("The public IM7/8552 example is loaded: 250 by 25 mm with 56 mm tabs, [45/0/-45/90]s, 1 mm pull."); }} disabled={busy}>Load example</button>
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
        <CouponForm form={form} errors={errors} disabled={busy} onChange={edit} />
        {isPlate ? <PlatePanel form={form} lists={plate} errors={errors} disabled={busy} onChange={editPlate} /> : null}
        <div className="studio-field studio-run-by">
          <label htmlFor="studio-run-by">Run by</label>
          <input id="studio-run-by" type="text" value={runBy} onChange={(e) => setRunBy(e.target.value)} disabled={busy} autoComplete="name" />
          <span className="studio-hint">Named in the attempt log and the CalculiX record.</span>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button" onClick={check} disabled={busy || !apiBaseUrl} data-testid="check-button">Check setup</button>
          <button type="button" className="studio-button studio-button-primary" onClick={solve} disabled={busy || !apiBaseUrl || (checked !== null && checked.state !== "ready")} data-testid="solve-button">Run analysis</button>
        </div>
        {message ? <p className="studio-alert" role="alert">{message}</p> : null}
        <p className="studio-status" role="status" data-testid="status">{status}</p>
      </aside>
  );
  const output = (
      <section className="studio-output">
        {fields ? (
          <>
            {viewerLink ? <p className="studio-viewer-link"><a href={viewerLink} target="_blank" rel="noreferrer" data-testid="viewer-link">Open the viewer in a new window</a></p> : null}
            <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={checked?.preview ?? null} />
            {job ? <JobProgress job={job} /> : null}
          </>
        ) : (
          <>
            {checked?.preview ? (
              <>
                <PreviewScene preview={checked.preview} onPick={isPlate ? setPickedElement : undefined} picked={pickedElement} />
                {isPlate && pickedElement !== null ? (() => {
                  const preview = checked.preview;
                  const touched = regionsOfElement(pickedElement, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, regionOptions(form, plate));
                  return (
                    <div className="studio-picked" data-testid="picked-regions">
                      <span>Element {pickedElement + 1} belongs to:</span>
                      {touched.map((r) => (
                        <span key={r.name}><strong>{r.name}</strong>{" "}
                          <button type="button" className="studio-text-button" onClick={() => editPlate(withSupport(plate, r.name))}>hold</button>{" "}
                          <button type="button" className="studio-text-button" onClick={() => editPlate(withLoad(plate, r.name, r.kind))}>load</button></span>
                      ))}
                      {!touched.length ? <span className="studio-muted">no named region; draw a box around it</span> : null}
                    </div>
                  );
                })() : null}
              </>
            ) : (
              <div className="studio-empty" data-testid="empty-scene">
                <h3>No model yet</h3>
                <p>Check the setup and the coupon appears here: its mesh, the held tab and the pulled tab.</p>
              </div>
            )}
            {job ? <JobProgress job={job} /> : null}
            <ChecklistPanel checklist={checked?.checklist ?? null} checking={checking} />
          </>
        )}
      </section>
  );
  if (part === "input") return input;
  if (part === "output") return output;
  return <div className="studio-layout">{input}{output}</div>;
}
