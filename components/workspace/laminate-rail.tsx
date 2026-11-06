"use client";

import { useState } from "react";
import { missingIn, REPORT_SYSTEMS, type LaminateStep, type ReportUnits } from "@/lib/laminate-chat";
import type { PanelState } from "@/lib/workspace-panels";
import { useLaminate } from "@/components/studio/laminate-context";
import { LayupFields, LoadsFields, MaterialFields } from "./panels/laminate-fields";
import { StepPanel } from "./panels/step-panel";

/** The left column of the laminate workspace (ADR-0062, part 5): one panel per step of the problem, Units, Material, Layup, Loads, and
 * Solve, each editing the one draft the assistant and the stack share. A panel is "checked" once its step is stated; the engine judges
 * the values when it solves (ADR-0003). */
export function LaminateRail() {
  const { draft, setDraft, solving, solve, answer, problem } = useLaminate();
  const system = (draft.system || "SI") as ReportUnits;
  const [errors, setErrors] = useState<string[]>([]);
  const [status, setStatus] = useState("State the units, the material, the layup and the loads, then solve.");
  const state = (step: LaminateStep): PanelState => (missingIn(step, draft).length ? "none" : "pass");

  async function run() {
    const outcome = await solve();
    if (outcome.ok) { setErrors([]); setStatus("Solved. The answer is in the centre, in the units you pick there."); }
    else if ("errors" in outcome) { setErrors(outcome.errors); setStatus(""); }
    else { setErrors([]); setStatus(outcome.refused); }
  }

  return (
    <div className="studio-form ws-rail-panels" data-testid="laminate-rail">
      <StepPanel id="units" title="Units" state={state("units")}>
        <div className="studio-field">
          <label htmlFor="lam-system">Stated in</label>
          <select id="lam-system" aria-label="Units" value={draft.system} disabled={solving} onChange={(e) => setDraft((d) => ({ ...d, system: e.target.value as ReportUnits | "" }))}>
            <option value="">Pick the system…</option>
            {REPORT_SYSTEMS.map((s) => <option key={s.id} value={s.id}>{s.title}: {s.detail}</option>)}
          </select>
          <span className="studio-hint">A number typed with its own unit keeps that unit; the engine converts, never this page.</span>
        </div>
      </StepPanel>

      <StepPanel id="material" title="Material" state={state("material")}>
        <MaterialFields draft={draft} system={system} disabled={solving} onChange={(material) => setDraft((d) => ({ ...d, material }))} />
      </StepPanel>

      <StepPanel id="layup" title="Layup" state={state("layup")}>
        <LayupFields draft={draft} system={system} disabled={solving} onChange={(layup, thickness) => setDraft((d) => ({ ...d, layup, thickness }))} />
      </StepPanel>

      <StepPanel id="loads" title="Loads" state={state("loads")}>
        <LoadsFields loads={draft.loads} system={system} disabled={solving} onChange={(loads) => setDraft((d) => ({ ...d, loads }))} />
      </StepPanel>

      <StepPanel id="solve" title="Solve" state={answer ? "pass" : "none"}>
        <div className="chat-inline lam-solve-options">
          <label htmlFor="lam-f12" className="lam-field"><span>Tsai-Wu f12* <small>optional, between -1 and 1</small></span>
            <input id="lam-f12" type="text" inputMode="decimal" autoComplete="off" className="chat-small-input" placeholder="-0.5" value={draft.f12_star} disabled={solving}
              onChange={(e) => setDraft((d) => ({ ...d, f12_star: e.target.value }))} /></label>
          <label className="lam-field lam-check"><input type="checkbox" data-testid="lam-strain-limits" checked={draft.strain_limits} disabled={solving}
            onChange={(e) => setDraft((d) => ({ ...d, strain_limits: e.target.checked }))} />
            <span>Maximum strain too <small>limits derived from the strengths (strength over modulus, linear to failure)</small></span></label>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={() => void run()} disabled={solving} data-testid="solve-button">Solve</button>
        </div>
        {errors.length ? <ul className="chat-understood studio-alert" role="alert">{errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
        {problem ? <p className="studio-alert" role="alert">{problem}</p> : null}
        <p className="studio-status" role="status" data-testid="status">{solving ? "Solving the stack…" : status}</p>
      </StepPanel>
    </div>
  );
}
