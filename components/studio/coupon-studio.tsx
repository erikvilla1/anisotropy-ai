"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkSetup, couponValues, fetchExplanation, fetchFields, getJob, listCoupons, POLL_MS, startSolve, StudioError,
  type CheckAnswer, type CouponSummary, type Explanation, type Fields, type JobStatus, type Preview,
} from "@/lib/studio-api";
import { blankForm, buildValues, exampleForm, formFromValues, rowErrorsFrom, type StudioForm } from "@/lib/studio-form";
import { printed } from "@/lib/studio-colors";
import { CouponForm } from "./coupon-form";
import { ChecklistPanel } from "./checklist-panel";
import { JobProgress } from "./job-progress";
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

export function PreviewScene({ preview }: { preview: Preview }) {
  const held: SceneMarker[] = preview.held.filter((h, i, all) => all.findIndex((x) => x.set === h.set) === i)
    .map((h) => ({ nodes: preview.mesh.node_sets[h.set] ?? [], label: `held: ${h.set} (${h.through ? "through a reference point" : "node by node"})` }));
  const loaded = { nodes: preview.mesh.node_sets[preview.loaded.set] ?? [], direction: preview.loaded.direction,
    label: `${preview.loaded.control} ${printed(preview.loaded.value)} ${preview.loaded.unit}` };
  return (
    <div className="studio-scene-block" data-testid="preview">
      <Scene nodes={preview.mesh.nodes} quads={preview.mesh.quads} thickness={preview.geometry.thickness} held={held} loaded={loaded} />
      <p className="studio-muted">{preview.coupon.designation ?? "The coupon"}, {preview.coupon.test}: {preview.geometry.length} by {preview.geometry.width} {preview.labels.length},
        {" "}{preview.plies.length} plies {preview.coupon.layup}, {printed(preview.geometry.thickness)} {preview.labels.length} thick; {preview.mesh.element_count} elements.
        The violet frames are held; the amber frame and arrow are the loading.</p>
    </div>
  );
}

export function CouponStudio({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [form, setForm] = useState<StudioForm>(() => blankForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [runBy, setRunBy] = useState("");
  const [message, setMessage] = useState("");
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState<CheckAnswer | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [coupons, setCoupons] = useState<CouponSummary[]>([]);
  const [reopen, setReopen] = useState("");
  const [status, setStatus] = useState("Load the example or fill in the rows, then check the setup.");
  const fieldsLoaded = useRef<string | null>(null);
  const aborts = useRef<AbortController[]>([]);
  useEffect(() => { setRunBy(remembered(RUN_BY_KEY)); return () => aborts.current.forEach((c) => c.abort("unmount")); }, []);
  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listCoupons(apiBaseUrl, controller.signal).then(setCoupons).catch(() => setCoupons([]));
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);

  const edit = useCallback((key: string, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors({}); setChecked(null); setMessage("");
    setStatus("Inputs changed. Check the setup again before solving.");
  }, []);

  async function check(): Promise<CheckAnswer | null> {
    if (!apiBaseUrl) return null;
    setChecking(true); setMessage(""); setErrors({});
    const controller = new AbortController();
    aborts.current.push(controller);
    try {
      const answer = await checkSetup(apiBaseUrl, buildValues(form), controller.signal);
      setChecked(answer);
      setErrors(rowErrorsFrom(answer.checklist));
      setStatus(answer.state === "ready" ? `Setup ready: ${answer.designation ?? "the coupon"} can be solved.` : "The setup is blocked; the items below say what to fix.");
      return answer;
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The setup check failed.");
      setStatus("");
      return null;
    } finally {
      setChecking(false);
    }
  }

  async function solve() {
    if (!apiBaseUrl) return;
    const answer = checked ?? (await check());
    if (!answer || answer.state !== "ready") return;
    const name = runBy.trim();
    if (!name) { setMessage("Give your name under Run by: the attempt log and the CalculiX record name who ran it."); return; }
    remember(RUN_BY_KEY, name);
    setMessage(""); setFields(null); setExplanation(null); fieldsLoaded.current = null;
    try {
      const started = await startSolve(apiBaseUrl, buildValues(form), name, answer.checklist.coupon_exists);
      setJob(started);
      setStatus("Solving. The fields appear as soon as our engine has run.");
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The solve could not start.");
    }
  }

  useEffect(() => {
    if (!job || !apiBaseUrl || job.state !== "running") return;
    const timer = window.setTimeout(async () => {
      try { setJob(await getJob(apiBaseUrl, job.job_id)); }
      catch (error) { setMessage(error instanceof StudioError ? error.message : "The job's status could not be read."); }
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [job, apiBaseUrl]);

  useEffect(() => {
    if (!job || !apiBaseUrl || !("fields" in job.outputs)) return;
    const stamp = `${job.job_id}:${job.state}`;
    if (fieldsLoaded.current === stamp) return;
    fieldsLoaded.current = stamp;
    const controller = new AbortController();
    aborts.current.push(controller);
    (async () => {
      try {
        setFields(await fetchFields(apiBaseUrl, job.job_id, controller.signal));
        setExplanation("explanation" in job.outputs ? await fetchExplanation(apiBaseUrl, job.job_id, controller.signal) : null);
        setStatus(job.state === "done" ? `Done: ${job.message ?? "the package is written"}.` : "Our engine has run; CalculiX, the record and the package follow.");
      } catch (error) {
        if (!controller.signal.aborted) setMessage(error instanceof StudioError ? error.message : "The fields could not be read.");
      }
    })();
  }, [job, apiBaseUrl]);

  async function loadCoupon(name: string) {
    if (!apiBaseUrl || !name) return;
    try {
      const values = await couponValues(apiBaseUrl, name);
      setForm({ ...formFromValues(values), filled_by: form.filled_by || runBy, date: today() });
      setErrors({}); setChecked(null); setMessage(""); setFields(null); setExplanation(null); setJob(null);
      setStatus(`Coupon ${name} loaded; change what you need and check the setup. Solving it adds the next attempt.`);
    } catch (error) {
      setMessage(error instanceof StudioError ? error.message : "The coupon could not be read.");
    }
  }

  const busy = checking || (job?.state === "running");
  const viewerLink = job ? `/studio/view?job=${encodeURIComponent(job.job_id)}` : null;
  return (
    <div className="studio-layout">
      <aside className="studio-input">
        {!apiBaseUrl ? <p className="studio-alert">The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so nothing can be checked or solved.</p> : null}
        <div className="studio-actions">
          <button type="button" className="studio-text-button" onClick={() => { setForm(exampleForm(today())); setErrors({}); setChecked(null); setMessage(""); setStatus("The public IM7/8552 example is loaded: 250 by 25 mm with 56 mm tabs, [45/0/-45/90]s, 1 mm pull."); }} disabled={busy}>Load example</button>
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
        <div className="studio-field studio-run-by">
          <label htmlFor="studio-run-by">Run by</label>
          <input id="studio-run-by" type="text" value={runBy} onChange={(e) => setRunBy(e.target.value)} disabled={busy} autoComplete="name" />
          <span className="studio-hint">Named in the attempt log and the CalculiX record.</span>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button" onClick={check} disabled={busy || !apiBaseUrl} data-testid="check-button">Check setup</button>
          <button type="button" className="studio-button studio-button-primary" onClick={solve} disabled={busy || !apiBaseUrl || (checked !== null && checked.state !== "ready")} data-testid="solve-button">Solve</button>
        </div>
        {message ? <p className="studio-alert" role="alert">{message}</p> : null}
        <p className="studio-status" role="status" data-testid="status">{status}</p>
      </aside>
      <section className="studio-output">
        {fields ? (
          <>
            {viewerLink ? <p className="studio-viewer-link"><a href={viewerLink} target="_blank" rel="noreferrer" data-testid="viewer-link">Open the viewer in a new window</a></p> : null}
            <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={checked?.preview ?? null} />
            {job ? <JobProgress job={job} /> : null}
          </>
        ) : (
          <>
            {checked?.preview ? <PreviewScene preview={checked.preview} /> : (
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
    </div>
  );
}
