"use client";

import { useEffect, useState } from "react";
import { hasCondition, missingIn, REPORT_SYSTEMS, type LaminateStep, type ReportUnits } from "@/lib/laminate-chat";
import { CONDITIONS } from "@/lib/conditions";
import type { PanelState } from "@/lib/workspace-panels";
import { useLaminate } from "@/components/studio/laminate-context";
import { LayupFields, LoadsFields, MaterialFields, TemperatureFields } from "./panels/laminate-fields";
import { showPanel, StepPanel } from "./panels/step-panel";

/** The left column of the laminate workspace (ADR-0062, part 5): one panel per step of the problem, Units, Material, Layup, Loads, and
 * Solve, each editing the one draft the assistant and the stack share. A panel is "complete" once its step is stated, and Solve "solved"
 * once there is an answer; the engine judges the values when it solves (ADR-0003). The status line follows the shared state, so a solve
 * started from the assistant reads the same here. */
export function LaminateRail() {
  const { draft, setDraft, solving, solve, answer, problem } = useLaminate();
  const system = (draft.system || "SI") as ReportUnits;
  const [errors, setErrors] = useState<string[]>([]);
  const [refused, setRefused] = useState("");
  useEffect(() => { setErrors([]); setRefused(""); }, [draft]); // a changed problem leaves the last reading behind
  // a solve started anywhere, the assistant's too, leaves this panel's last reading behind, and so does the answer it brings
  useEffect(() => { if (solving || answer) { setErrors([]); setRefused(""); } }, [solving, answer]);
  const state = (step: LaminateStep): PanelState => (missingIn(step, draft).length ? "none" : "pass");
  const offered = CONDITIONS.filter((c) => c.product === "laminate" && !hasCondition(draft, c.id));
  const addCondition = (id: string, panel: string) => {
    setDraft((d) => ({ ...d, conditions: [...(d.conditions ?? []), id] }));
    window.setTimeout(() => showPanel(panel), 0);  // the panel exists once the draft has the condition
  };

  async function run() {
    const outcome = await solve();
    setErrors(!outcome.ok && "errors" in outcome ? outcome.errors : []);
    setRefused(!outcome.ok && "refused" in outcome ? outcome.refused : "");
  }

  // the API's refusal is the shared one; a page-side one (no service) is this panel's, and never stands beside an answer
  const shownRefusal = problem || (answer ? "" : refused);
  // "under the stack" holds at every width: the results follow the stack's drawing whether the columns stand side by side or stack
  const status = solving ? "Solving the stack…" : answer ? "Solved. Results are under the stack."
    : errors.length || shownRefusal ? "" : "Enter the units, material, layup and loads, then solve.";

  return (
    <div className="studio-form ws-rail-panels" data-testid="laminate-rail">
      <StepPanel id="units" title="Units" state={state("units")} word="complete">
        <div className="studio-field">
          <label htmlFor="lam-system">Stated in</label>
          <select id="lam-system" value={draft.system} disabled={solving} onChange={(e) => setDraft((d) => ({ ...d, system: e.target.value as ReportUnits | "" }))}>
            <option value="">Pick the system…</option>
            {REPORT_SYSTEMS.map((s) => <option key={s.id} value={s.id}>{s.title}: {s.detail}</option>)}
          </select>
          <span className="studio-hint">A value typed with a unit keeps that unit.</span>
        </div>
      </StepPanel>

      <StepPanel id="material" title="Material" state={state("material")} word="complete">
        <MaterialFields draft={draft} system={system} disabled={solving} onChange={(material) => setDraft((d) => ({ ...d, material }))} />
      </StepPanel>

      <StepPanel id="layup" title="Layup" state={state("layup")} word="complete">
        <LayupFields draft={draft} system={system} disabled={solving} onChange={(layup, thickness) => setDraft((d) => ({ ...d, layup, thickness }))} />
      </StepPanel>

      <StepPanel id="loads" title="Loads" state={state("loads")} word="complete">
        <LoadsFields loads={draft.loads} system={system} disabled={solving} onChange={(loads) => setDraft((d) => ({ ...d, loads }))} />
      </StepPanel>

      {hasCondition(draft, "temperature") ? (
        <StepPanel id="temperature" title="Temperature change" state={state("temperature")} word="complete" note="a condition">
          <TemperatureFields draft={draft} system={system} disabled={solving} onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))} />
          <div className="studio-buttons"><button type="button" className="studio-text-button" disabled={solving} data-testid="remove-temperature"
            onClick={() => setDraft((d) => ({ ...d, conditions: (d.conditions ?? []).filter((c) => c !== "temperature"), delta_T: null }))}>Remove the temperature change</button></div>
        </StepPanel>
      ) : null}

      {offered.length ? (
        <div className="lam-conditions" data-testid="add-condition">
          <span className="studio-hint">Add a condition:</span>
          {offered.map((c) => <button key={c.id} type="button" className="studio-text-button" title={c.detail} disabled={solving}
            onClick={() => addCondition(c.id, c.panel)}>+ {c.title}</button>)}
        </div>
      ) : null}

      <StepPanel id="solve" title="Solve" state={answer ? "pass" : "none"} word="solved">
        <div className="chat-inline lam-solve-options">
          <label htmlFor="lam-f12" className="lam-field"><span>Tsai-Wu f₁₂* <small>optional, between −1 and 1; leave blank to skip Tsai-Wu</small></span>
            <input id="lam-f12" type="text" inputMode="decimal" autoComplete="off" className="chat-small-input" value={draft.f12_star} disabled={solving}
              onChange={(e) => setDraft((d) => ({ ...d, f12_star: e.target.value }))} /></label>
          <label className="lam-field lam-check"><input type="checkbox" data-testid="lam-strain-limits" checked={draft.strain_limits} disabled={solving}
            onChange={(e) => setDraft((d) => ({ ...d, strain_limits: e.target.checked }))} />
            <span>Also check maximum strain <small>limits: strength ÷ modulus</small></span></label>
        </div>
        <div className="studio-buttons">
          <button type="button" className="studio-button studio-button-primary" onClick={() => void run()} disabled={solving} data-testid="solve-button">Solve</button>
        </div>
        {errors.length ? <ul className="chat-understood studio-alert" role="alert">{errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
        {shownRefusal ? <p className="studio-alert" role="alert">{shownRefusal}</p> : null}
        <p className="studio-status" role="status" data-testid="status">{status}</p>
      </StepPanel>
    </div>
  );
}
