"use client";

import { useState } from "react";
import type { LaminateAnswer } from "@/lib/studio-api";
import { plyLabel, printedUnit, REPORT_SYSTEMS, type ReportUnits } from "@/lib/laminate-chat";
import { formatNumber } from "@/lib/number-format";
import { settled } from "@/lib/studio-colors";
import { shownSentence } from "@/lib/studio-copy";

/** The engine's number as the page prints it: the site's one rule (`lib/number-format.ts`), four significant figures with the zeros kept,
 * so a column reads alike ("3.220" beside "3.474"); `zeros` off for a readout or a value in a line of text ("−497"). Never a value of its own. */
export function shown(value: unknown, zeros = true): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return value === null ? "unbounded" : "–";
  return formatNumber(value, { zeros });
}

const CRITERION_WORDS: Record<string, string> = { max_stress: "Maximum stress", max_strain: "Maximum strain", tsai_hill: "Tsai-Hill", tsai_wu: "Tsai-Wu" };
const KIND_WORDS: Record<string, string> = { unidirectional: "unidirectional", "cross-ply": "cross-ply", "angle-ply": "angle-ply", "quasi-isotropic": "quasi-isotropic", general: "general (anisotropic)" };
const LOADS = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"] as const;
const INDICES = ["1", "2", "6"];
const SHEAR_TERMS = [2, 5, 6, 7]; // A16, A26, A61, A62 in the row-major nine
type Face = "mid" | "bottom" | "top";
const FACE_WORDS: Record<Face, string> = { mid: "mid-thickness", bottom: "bottom face", top: "top face" };

/** One stiffness matrix as a table (WCAG 1.3.1): a caption with its unit, the axes as column and row headers, x, y, xy for the
 * laminate's A, B and D and the ply axes 1, 2, 6 for Q. */
function Matrix({ title, unit, values }: { title: "Q" | "A" | "B" | "D"; unit: string; values: number[] }) {
  const axes = title === "Q" ? ["1", "2", "6"] : ["x", "y", "xy"];
  return (
    <div className="lam-matrix" data-testid={`matrix-${title}`}>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-num lam-matrix-table">
          <caption>{title === "Q" ? "Q, every ply" : title} ({printedUnit(unit)})</caption>
          <thead><tr><td />{axes.map((axis) => <th scope="col" key={axis}>{axis}</th>)}</tr></thead>
          <tbody>
            {axes.map((axis, i) => (
              <tr key={axis}><th scope="row">{axis}</th>{values.slice(3 * i, 3 * i + 3).map((value, j) => <td key={j}>{shown(value)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Everything the engine returned for a laminate problem (ADR-0060), in the units asked for: the headline strains and failure, the
 * stiffness matrices, every ply's stresses, first-ply failure by each criterion, and the explanation in the product's words (ADR-0091); who
 * wrote it stays in the run record and in `data-writer`. Arithmetic noise is shown as zero, at the stack summary's tolerance (ADR-0059). */
export function LaminateResults({ answer, busy, onReport }: { answer: LaminateAnswer; busy: boolean; onReport: (system: ReportUnits) => void }) {
  const [axes, setAxes] = useState<"local" | "global">("local");
  const [face, setFace] = useState<Face>("mid");
  const r = answer.results, u = answer.units, f = answer.facts, s = answer.summary;
  const angles = (answer.case.laminate as { layup: number[] }).layup;
  const earliest = typeof f.earliest === "string" ? f.earliest : null;
  const governing = earliest ? Number(r[`fpf_ply_${earliest}`]) : null;
  const prose = answer.prose.map(shownSentence).filter((sentence): sentence is string => sentence !== null);

  // the matrices: B is zero without extension–bending coupling, A16 and A26 without extension–shear coupling; the rest is settled
  const matrix = (prefix: "Q" | "A" | "B" | "D"): number[] => {
    const values = settled(INDICES.flatMap((i) => INDICES.map((j) => Number(r[`${prefix}${i}${j}`]))));
    if (prefix === "B" && !s.coupling.extension_bending) return values.map(() => 0);
    if (prefix === "A" && !s.coupling.extension_shear) return values.map((v, k) => (SHEAR_TERMS.includes(k) ? 0 : v));
    return values;
  };

  // the stack curves when a curvature is not roundoff (the API zeroes it at its tolerance): then the faces differ, and may be picked
  const kappas = [f.kappa_x, f.kappa_y, f.kappa_xy];
  const curved = kappas.some((v) => typeof v === "number") ? kappas.some((v) => typeof v === "number" && v !== 0)
    : Array.isArray(r.curvature) && !(r.curvature as number[]).every((v) => v === 0);
  const rowsAt = (where: Face) => r[`ply_stress_${axes}${where === "mid" ? "" : `_${where}`}`];
  const faces = curved && (["bottom", "top"] as Face[]).every((where) => Array.isArray(rowsAt(where)) && (rowsAt(where) as unknown[]).length === angles.length);
  const stresses = rowsAt(faces ? face : "mid") as number[][];

  // the loads at failure: the unit goes in the heading when every criterion's loads share one
  const failureLoads = answer.criteria.map((criterion) => {
    const forces = (r[`fpf_forces_${criterion}`] as number[] | undefined) ?? [0, 0, 0];
    const moments = (r[`fpf_moments_${criterion}`] as number[] | undefined) ?? [0, 0, 0];
    return [...forces, ...moments].map((v, i) => ({ name: LOADS[i], v, unit: i < 3 ? u.N : u.M })).filter((item) => item.v !== 0);
  });
  const loadUnits = new Set(failureLoads.flat().map((item) => item.unit));
  const loadUnit = loadUnits.size === 1 ? [...loadUnits][0] : null;
  const scaled = f.thermal_only ? `the temperature change of ${shown(f.delta_T, false)} ${printedUnit(u.delta_T ?? "")} itself grows until the first ply fails; R is the factor on it`
    : typeof f.delta_T === "number" ? `every load scales together until the first ply fails, the temperature change of ${shown(f.delta_T, false)} ${printedUnit(u.delta_T ?? "")} held at its value; R is the factor on the applied loads`
      : "every load scales together until the first ply fails; R is the factor on the applied loads";
  const settings = [answer.criteria.includes("max_strain") ? "Maximum strain limits: strength ÷ modulus." : null,
    answer.criteria.includes("tsai_wu") && typeof answer.case.f12_star === "number" ? `Tsai-Wu uses f₁₂* = ${formatNumber(answer.case.f12_star, { zeros: false })}.` : null].filter(Boolean);

  return (
    <div className="lam-results" data-testid="laminate-results" data-units={answer.report_units}>
      <div className="lam-unitbar">
        <span>Show results in</span>
        <span className="lam-toggle" role="group" aria-label="Result units">
          {REPORT_SYSTEMS.map((system) => (
            <button type="button" key={system.id} aria-pressed={answer.report_units === system.id} disabled={busy} onClick={() => onReport(system.id)}>{system.title}</button>
          ))}
        </span>
        <small>Results are recomputed in the units you pick.</small>
      </div>

      <section className="studio-panel">
        <h3>Answer</h3>
        <div className="chat-stats lam-stats">
          <div><span>ε<sub>x</sub>, mid-plane</span><strong data-testid="lam-eps-x">{shown(f.eps_x_microstrain, false)}</strong><small>microstrain</small></div>
          <div><span>ε<sub>y</sub>, mid-plane</span><strong>{shown(f.eps_y_microstrain, false)}</strong><small>microstrain</small></div>
          <div><span>γ<sub>xy</sub>, mid-plane</span><strong>{shown(f.gamma_xy_microstrain, false)}</strong><small>microstrain</small></div>
          {earliest ? (
            <div><span>First-ply failure</span><strong data-testid="lam-fpf">R = {shown(r[`fpf_ratio_${earliest}`], false)}</strong>
              <small>{CRITERION_WORDS[earliest] ?? earliest}, {plyLabel(governing ?? 0, Number(f[`${earliest}_angle`]))}</small></div>
          ) : <div><span>First-ply failure</span><strong>–</strong><small>{typeof f.F1t === "number" ? "no load applied" : "no strengths given"}</small></div>}
          <div><span>E<sub>x</sub> · E<sub>y</sub></span><strong>{shown(r.Ex, false)} · {shown(r.Ey, false)}</strong><small>{printedUnit(u.modulus)}</small></div>
          <div><span>G<sub>xy</sub></span><strong>{shown(r.Gxy, false)}</strong><small>{printedUnit(u.modulus)}</small></div>
          <div><span>ν<sub>xy</sub></span><strong>{shown(r.nu_xy, false)}</strong></div>
        </div>
        <dl className="studio-summary lam-summary" data-testid="lam-summary">
          <div><dt>Stack</dt><dd>{s.ply_count} plies, {shown(r.total_thickness, false)} {printedUnit(u.length)} thick, {KIND_WORDS[s.kind] ?? s.kind}</dd></div>
          <div><dt>Stacking</dt><dd>{s.symmetric ? "symmetric" : s.antisymmetric ? "antisymmetric" : "unsymmetric"}, {s.balanced ? "balanced" : "unbalanced"}</dd></div>
          <div><dt>Coupling</dt><dd>{[s.coupling.extension_shear ? "extension–shear" : null, s.coupling.extension_bending ? "extension–bending" : null, s.coupling.bending_twisting ? "bending–twisting" : null].filter(Boolean).join(", ") || "none"}</dd></div>
          {typeof r.areal_mass === "number" ? <div><dt>Areal mass</dt><dd>{shown(r.areal_mass, false)} {printedUnit(u.areal_mass)}</dd></div> : null}
          {answer.material ? <div><dt>Material</dt><dd>{answer.material.name}, {answer.material.citation}</dd></div> : null}
        </dl>
      </section>

      <section className="studio-panel">
        <h3>Stiffness</h3>
        <p className="studio-muted">A, B and D: rows and columns x, y, xy. Q: the ply&apos;s own axes 1, 2, 6.</p>
        <div className="lam-matrices">
          <Matrix title="Q" unit={u.modulus} values={matrix("Q")} />
          <Matrix title="A" unit={u.A} values={matrix("A")} />
          <Matrix title="B" unit={u.B} values={matrix("B")} />
          <Matrix title="D" unit={u.D} values={matrix("D")} />
        </div>
      </section>

      <section className="studio-panel">
        <h3>Stress in each ply</h3>
        <div className="studio-controls lam-axes">
          <label>Axes
            <select aria-label="Stress axes" value={axes} onChange={(e) => setAxes(e.target.value as "local" | "global")}>
              <option value="local">fibre axes: σ₁, σ₂, τ₁₂</option>
              <option value="global">laminate axes: σx, σy, τxy</option>
            </select>
          </label>
          {faces ? (
            <label>Through the ply
              <select aria-label="Through the ply" value={face} onChange={(e) => setFace(e.target.value as Face)} data-testid="lam-face">
                {(["mid", "bottom", "top"] as Face[]).map((where) => <option key={where} value={where}>{FACE_WORDS[where]}</option>)}
              </select>
            </label>
          ) : null}
        </div>
        <p className="studio-muted">{!curved ? "Values at ply mid-thickness, bottom ply first."
          : faces ? "The stack curves, so the stresses vary through each ply: pick where to read them. Bottom ply first."
            : "The stack curves, so the stresses vary through each ply; values are at mid-thickness. Bottom ply first."}</p>
        <div className="studio-table-scroll">
          <table className="studio-table studio-table-num studio-table-sticky" data-testid="lam-ply-table">
            <thead>
              <tr><th scope="col" rowSpan={2}>Ply</th>
                <th scope="colgroup" colSpan={3} className="studio-table-group-head">{axes === "local" ? "Stress, fibre axes" : "Stress, laminate axes"} ({printedUnit(u.stress)})</th></tr>
              <tr className="lam-stress-heads">{(axes === "local" ? ["σ₁", "σ₂", "τ₁₂"] : ["σx", "σy", "τxy"]).map((name) => <th scope="col" key={name}>{name}</th>)}</tr>
            </thead>
            <tbody>
              {stresses.map((row, index) => (
                <tr key={index} className={governing === index + 1 ? "studio-earliest" : undefined} data-ply={index + 1}>
                  <th scope="row">{plyLabel(index + 1, angles[index])}{governing === index + 1 ? <span className="studio-muted"> (governs)</span> : null}</th>
                  {settled(row).map((value, k) => <td key={k}>{shown(value)}</td>)}
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
            <p className="studio-muted">{f.thermal_only ? "No load: " : ""}{f.thermal_only ? scaled : scaled.charAt(0).toUpperCase() + scaled.slice(1)}. The lowest R is marked (governs).</p>
            <div className="studio-table-scroll">
              <table className="studio-table studio-table-num studio-table-sticky" data-testid="lam-fpf-table">
                <thead><tr><th scope="col">Criterion</th><th scope="col">R</th><th scope="col" className="studio-text-cell">Ply</th>
                  <th scope="col">{f.thermal_only ? `Temperature change at failure (${printedUnit(u.delta_T ?? "")})` : loadUnit ? `Loads at failure (${printedUnit(loadUnit)})` : "Loads at failure"}</th></tr></thead>
                <tbody>
                  {answer.criteria.map((criterion, index) => {
                    const at = failureLoads[index];
                    const mode = f[`${criterion}_mode`];
                    return (
                      <tr key={criterion} className={criterion === earliest ? "studio-earliest" : undefined} data-criterion={criterion}>
                        <th scope="row">{CRITERION_WORDS[criterion] ?? criterion}{criterion === earliest ? <span className="studio-muted"> (governs)</span> : null}</th>
                        <td data-testid={`lam-ratio-${criterion}`}>{shown(r[`fpf_ratio_${criterion}`])}</td>
                        <td className="studio-text-cell">{plyLabel(Number(r[`fpf_ply_${criterion}`]), Number(f[`${criterion}_angle`]))}{typeof mode === "string" && mode !== "interactive" ? `, ${mode}` : ""}</td>
                        <td data-testid={`lam-at-failure-${criterion}`}>{f.thermal_only ? shown(r[`fpf_delta_T_${criterion}`])
                          : at.length ? at.map((item) => `${item.name} ${shown(item.v)}${loadUnit ? "" : ` ${printedUnit(item.unit)}`}`).join(", ") : "–"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {settings.length ? <p className="studio-muted">{settings.join(" ")}</p> : null}
            {typeof answer.case.f12_star !== "number" ? <p className="studio-muted">Tsai-Wu needs f₁₂*: enter it under Solve, then solve again.</p> : null}
            {!answer.criteria.includes("max_strain") ? <p className="studio-muted" data-testid="lam-no-max-strain">Maximum strain needs strain limits: tick “Also check maximum strain” under Solve, then solve again.</p> : null}
          </>
        ) : <p className="studio-muted">{typeof f.F1t === "number" ? "No load was applied, so there is nothing to scale." : "Not evaluated: the material has no strengths."}</p>}
      </section>

      <section className="studio-panel lam-explanation" data-testid="lam-explanation" data-writer={answer.writer}>
        <h3>What this shows</h3>
        {prose.slice(0, 2).map((sentence, index) => <p key={index}>{sentence}</p>)}
        <details className="studio-details-more"><summary>Details</summary>
          {prose.slice(2).map((sentence, index) => <p key={index}>{sentence}</p>)}
          <p className="studio-muted">Solver version {answer.engine_version}</p>
        </details>
      </section>
    </div>
  );
}
