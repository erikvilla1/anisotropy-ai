"use client";

import { useState } from "react";
import type { LaminateAnswer } from "@/lib/studio-api";
import { printedUnit, REPORT_SYSTEMS, type ReportUnits } from "@/lib/laminate-chat";

/** The engine's number as the page prints it: four significant figures, exponential outside everyday sizes; never a value of its own. */
export function shown(value: unknown, figures = 4): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return value === null ? "unbounded" : "–";
  if (value === 0) return "0";
  const size = Math.abs(value);
  return size >= 1e-3 && size < 1e6 ? String(Number(value.toPrecision(figures))) : value.toExponential(figures - 1);
}

const CRITERION_WORDS: Record<string, string> = { max_stress: "Maximum stress", max_strain: "Maximum strain", tsai_hill: "Tsai-Hill", tsai_wu: "Tsai-Wu" };
const KIND_WORDS: Record<string, string> = { unidirectional: "unidirectional", "cross-ply": "cross-ply", "angle-ply": "angle-ply", "quasi-isotropic": "quasi-isotropic", general: "general (anisotropic)" };
const LOADS = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"] as const;

function Matrix({ title, unit, results, note }: { title: "Q" | "A" | "B" | "D"; unit: string; results: Record<string, unknown>; note?: string }) {
  return (
    <div className="lam-matrix" data-testid={`matrix-${title}`}>
      <div className="lam-matrix-label">{title === "Q" ? "Q, every ply" : title} <i>({printedUnit(unit)})</i></div>
      <div className="lam-matrix-grid">
        {["1", "2", "6"].flatMap((i) => ["1", "2", "6"].map((j) => <span key={i + j}>{shown(results[`${title}${i}${j}`])}</span>))}
      </div>
      {note ? <small className="lam-matrix-note">{note}</small> : null}
    </div>
  );
}

/** Everything the engine returned for a laminate problem (ADR-0060), in the units asked for: the headline strains and failure, the
 * stiffness matrices, every ply's stresses, first-ply failure by each criterion, and the explanation with who wrote it (ADR-0052). */
export function LaminateResults({ answer, busy, onReport }: { answer: LaminateAnswer; busy: boolean; onReport: (system: ReportUnits) => void }) {
  const [axes, setAxes] = useState<"local" | "global">("local");
  const r = answer.results, u = answer.units, f = answer.facts, s = answer.summary;
  const angles = (answer.case.laminate as { layup: number[] }).layup;
  const earliest = typeof f.earliest === "string" ? f.earliest : null;
  const governing = earliest ? Number(r[`fpf_ply_${earliest}`]) : null;
  const stresses = (axes === "local" ? r.ply_stress_local : r.ply_stress_global) as number[][];
  const badge = answer.writer === "template" ? "written by the template from the engine's numbers"
    : `written by ${answer.writer}${answer.model ? ` (${answer.model})` : ""}, every number checked against the engine's`;
  return (
    <div className="lam-results" data-testid="laminate-results" data-units={answer.report_units}>
      <div className="lam-unitbar">
        <span>Show results in</span>
        <span className="lam-toggle" role="group" aria-label="Result units">
          {REPORT_SYSTEMS.map((system) => (
            <button type="button" key={system.id} aria-pressed={answer.report_units === system.id} disabled={busy} onClick={() => onReport(system.id)}>{system.title}</button>
          ))}
        </span>
        <small>Every value is solved again by the engine in the system you pick; the page converts nothing.</small>
      </div>

      <section className="studio-panel">
        <h3>Answer <span className="studio-badge">{printedUnit(u.stress)}, {printedUnit(u.N)}</span></h3>
        <div className="chat-stats lam-stats">
          <div><span>ε<sub>x</sub>, mid-plane</span><strong data-testid="lam-eps-x">{shown(f.eps_x_microstrain)}</strong><small>microstrain</small></div>
          <div><span>ε<sub>y</sub>, mid-plane</span><strong>{shown(f.eps_y_microstrain)}</strong><small>microstrain</small></div>
          <div><span>γ<sub>xy</sub>, mid-plane</span><strong>{shown(f.gamma_xy_microstrain)}</strong><small>microstrain</small></div>
          {earliest ? (
            <div><span>First-ply failure</span><strong data-testid="lam-fpf">R = {shown(r[`fpf_ratio_${earliest}`])}</strong>
              <small>{CRITERION_WORDS[earliest] ?? earliest}, ply {governing} ({shown(f[`${earliest}_angle`])}°)</small></div>
          ) : <div><span>First-ply failure</span><strong>–</strong><small>{typeof f.F1t === "number" ? "no load applied" : "no strengths given"}</small></div>}
          <div><span>E<sub>x</sub> · E<sub>y</sub></span><strong>{shown(r.Ex)} · {shown(r.Ey)}</strong><small>{printedUnit(u.modulus)}</small></div>
          <div><span>G<sub>xy</sub> · ν<sub>xy</sub></span><strong>{shown(r.Gxy)} · {shown(r.nu_xy)}</strong><small>{printedUnit(u.modulus)}, no unit</small></div>
        </div>
        <dl className="studio-summary lam-summary" data-testid="lam-summary">
          <div><dt>Stack</dt><dd>{s.ply_count} plies, {shown(r.total_thickness)} {printedUnit(u.length)} thick, {KIND_WORDS[s.kind] ?? s.kind}</dd></div>
          <div><dt>Stacking</dt><dd>{s.symmetric ? "symmetric" : s.antisymmetric ? "antisymmetric" : "unsymmetric"}, {s.balanced ? "balanced" : "unbalanced"}</dd></div>
          <div><dt>Coupling</dt><dd>{[s.coupling.extension_shear ? "extension–shear" : null, s.coupling.extension_bending ? "extension–bending" : null, s.coupling.bending_twisting ? "bending–twisting" : null].filter(Boolean).join(", ") || "none at the engine's tolerance"}</dd></div>
          {typeof r.areal_mass === "number" ? <div><dt>Areal mass</dt><dd>{shown(r.areal_mass)} {printedUnit(u.areal_mass)}</dd></div> : null}
          {answer.material ? <div><dt>Material</dt><dd>{answer.material.name}, {answer.material.citation}</dd></div> : null}
        </dl>
      </section>

      <section className="studio-panel">
        <h3>Stiffness</h3>
        <p className="studio-muted">Rows and columns in the order x, y, xy. Q is the ply's reduced stiffness in its own axes; A, B and D are the laminate's.</p>
        <div className="lam-matrices">
          <Matrix title="Q" unit={u.modulus} results={r} />
          <Matrix title="A" unit={u.A} results={r} />
          <Matrix title="B" unit={u.B} results={r} note={s.coupling.extension_bending ? undefined : "no extension–bending coupling at the engine's tolerance: these entries are roundoff"} />
          <Matrix title="D" unit={u.D} results={r} />
        </div>
      </section>

      <section className="studio-panel">
        <h3>Stress in each ply <span className="studio-badge">{printedUnit(u.stress)}</span></h3>
        <div className="studio-controls lam-axes">
          <label>Axes
            <select aria-label="Stress axes" value={axes} onChange={(e) => setAxes(e.target.value as "local" | "global")}>
              <option value="local">fibre axes: σ₁, σ₂, τ₁₂</option>
              <option value="global">laminate axes: σx, σy, τxy</option>
            </select>
          </label>
        </div>
        <p className="studio-muted">Bottom ply first, at mid-thickness. {Array.isArray(r.curvature) && (r.curvature as number[]).every((v) => v === 0) ? "" : "With curvature the faces differ; the engine's case runner lists both."}</p>
        <div className="calc-table-scroll">
          <table className="studio-table" data-testid="lam-ply-table">
            <thead><tr><th>Ply</th><th>Angle</th><th>{axes === "local" ? "σ₁" : "σx"}</th><th>{axes === "local" ? "σ₂" : "σy"}</th><th>{axes === "local" ? "τ₁₂" : "τxy"}</th></tr></thead>
            <tbody>
              {stresses.map((row, index) => (
                <tr key={index} className={governing === index + 1 ? "studio-earliest" : undefined} data-ply={index + 1}>
                  <td>{index + 1}</td><td>{angles[index] > 0 ? `+${angles[index]}` : angles[index]}°</td>
                  {row.map((value, k) => <td key={k}>{shown(value)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="studio-panel">
        <h3>First-ply failure</h3>
        {answer.criteria.length ? (
          <>
            <p className="studio-muted">Every load scales together until the first ply fails; R is the factor on the applied loads. Highlighted: the lowest R.</p>
            <div className="calc-table-scroll">
              <table className="studio-table" data-testid="lam-fpf-table">
                <thead><tr><th>Criterion</th><th>R</th><th>Ply</th><th>Loads at failure</th></tr></thead>
                <tbody>
                  {answer.criteria.map((criterion) => {
                    const forces = r[`fpf_forces_${criterion}`] as number[];
                    const moments = (r[`fpf_moments_${criterion}`] as number[] | undefined) ?? [0, 0, 0];
                    const at = [...forces, ...moments].map((v, i) => ({ name: LOADS[i], v, unit: i < 3 ? u.N : u.M })).filter((item) => item.v !== 0);
                    return (
                      <tr key={criterion} className={criterion === earliest ? "studio-earliest" : undefined} data-criterion={criterion}>
                        <td>{CRITERION_WORDS[criterion] ?? criterion}{criterion === "tsai_wu" && typeof answer.case.f12_star === "number" ? ` (f12* = ${answer.case.f12_star})` : ""}</td>
                        <td data-testid={`lam-ratio-${criterion}`}>{shown(r[`fpf_ratio_${criterion}`])}</td>
                        <td>{shown(r[`fpf_ply_${criterion}`])} ({shown(f[`${criterion}_angle`])}°){typeof f[`${criterion}_mode`] === "string" && f[`${criterion}_mode`] !== "interactive" ? `, ${f[`${criterion}_mode`]}` : ""}</td>
                        <td>{at.length ? at.map((item) => `${item.name} = ${shown(item.v)} ${printedUnit(item.unit)}`).join(", ") : "–"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {typeof answer.case.f12_star !== "number" ? <p className="studio-muted">Tsai-Wu is not computed without f12*; give it on the review card to add it.</p> : null}
          </>
        ) : <p className="studio-muted">{typeof f.F1t === "number" ? "No load was applied, so there is nothing to scale." : "Not evaluated: the material has no strengths."}</p>}
      </section>

      <section className="studio-panel lam-explanation" data-testid="lam-explanation" data-writer={answer.writer}>
        <h3>What this shows</h3>
        {answer.prose.map((sentence, index) => <p key={index}>{sentence}</p>)}
        <p className="studio-muted">{badge}.{answer.reason ? ` ${answer.withheld ? "The model's draft was withheld: " : "The template's words stand: "}${answer.reason}.` : ""}</p>
      </section>
      <p className="studio-muted">Engine {answer.engine_version}{answer.run_id ? `, run ${answer.run_id}` : ""}.</p>
    </div>
  );
}
