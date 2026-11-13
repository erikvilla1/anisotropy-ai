"use client";

import { useEffect, useMemo, useState } from "react";
import { DOWNLOADS, explainJob, isActive, StudioError, type Convergence, type ExplainAnswer, type Explanation, type CalculixBeside, type Extreme, type Fields, type FirstPlyFailure, type JobStatus,
  type Preview } from "@/lib/studio-api";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, PROBE_COLUMNS, probeCsv, probeTable, valuesFor, type FieldChoice, type ProbeTable } from "@/lib/studio-fields";
import { answerOf, BASIS_WORDS, CRITERION_NAMES, extremeRows, modeWords, type AnswerRow } from "@/lib/studio-answer";
import { customerText, shownSentence } from "@/lib/studio-copy";
import { legendGradient, legendTicks, percentChange, printed, scaleFor, settled, type Scale } from "@/lib/studio-colors";
import { suggestedScale } from "@/lib/studio-geometry";
import { JobFiles, namingOf } from "./job-files";
import { Scene } from "./scene";
import type { SceneField, SceneMarker } from "./scene-canvas";

/** The contour choices: the smooth ramp, or bands with an isoline at every band boundary, each boundary a labelled tick (ADR-0063). */
export const CONTOURS: [number, string][] = [[0, "smooth"], [5, "5 bands"], [8, "8 bands"], [10, "10 bands"]];
export const DEFAULT_CONTOURS = 8;

export function Legend({ scale, label, unit, by, bands = 0 }: { scale: Scale; label: string; unit: string; by: "node" | "element"; bands?: number }) {
  const ticks = legendTicks(scale, bands ? bands + 1 : 5);
  return (
    <div className="studio-legend" data-testid="legend" data-source={scale.source} data-bands={bands}>
      <div className="studio-legend-bar" style={{ background: legendGradient(scale, bands) }} aria-hidden="true" />
      <div className="studio-legend-ticks" aria-hidden="true">{ticks.map((t, i) => <span key={i}>{printed(t)}</span>)}</div>
      <p><strong>{label}</strong>{unit && unit !== "-" ? ` (${unit})` : ""} · {by === "element" ? "element values" : "nodal averages"} · {printed(scale.ends[0])} to {printed(scale.ends[1])}{unit && unit !== "-" ? ` ${unit}` : ""}
        {bands ? ` · ${bands} bands` : ""}{scale.kind === "diverging" ? " · grey is zero" : ""}</p>
    </div>
  );
}

const xyz = (p: number[] | undefined) => (p && p.length === 3 ? ` (${p.map((v) => printed(v)).join(", ")})` : "");
/** The ply stress components as the fields name them, said with their symbols. */
const COMPONENT: Record<string, string> = { S11: "σ₁ (fibre)", S22: "σ₂ (transverse)", S12: "τ₁₂ (in-plane shear)" };
const criterionName = (criterion: string) => CRITERION_NAMES[criterion] ?? criterion.replace("_", " ");

export function SummaryPanel({ fields, onShow }: { fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const s = fields.summary, lab = fields.labels, cx = s.calculix ?? null;
  return (
    <div className="studio-panel" data-testid="summary">
      <h3>Summary</h3>
      <dl className="studio-summary">
        <div><dt>Applied</dt><dd>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}{s.applied.direction ? `, ${s.applied.direction}` : ""}</dd></div>
        <div><dt>Reaction at {s.reaction.set}</dt><dd data-testid="summary-reaction">{printed(Math.abs(s.reaction.value))} {lab.force} ({s.reaction.sense})
          {cx?.reaction ? <span data-testid="summary-reaction-calculix">; reference solver {printed(Math.abs(cx.reaction.calculix))} {lab.force} ({cx.reaction.difference})</span> : null}</dd></div>
        <div><dt>Largest displacement</dt><dd>{printed(s.max_displacement.value)} {lab.length} at node {s.max_displacement.label.split(".").pop()}
          {s.max_displacement.axis === "z" ? " (the deflection w)" : ""}</dd></div>
      </dl>
      {s.ply_peaks ? (
        <>
          <ValidationTable s={s} cx={cx} lab={lab} />
          <PeaksTable s={s} cx={cx} lab={lab} criterion={s.earliest ?? ""} onShow={onShow} />
        </>
      ) : <OlderPeaks fields={fields} onShow={onShow} />}
      {s.convergence ? <ConvergenceTable study={s.convergence} lab={lab} /> : null}
      <details className="studio-fpf-details" data-testid="fpf-details" open={answerOf(fields) === null}>
      <summary>First-ply failure, all criteria</summary>
      <h4>Whole model</h4>
      {Object.keys(s.fpf).length === 0 ? <p className="studio-muted">No failure criterion selected.</p> : (
        <FailureTable fpf={s.fpf} earliest={s.earliest} testId="fpf-table" factorPrefix="fpf-factor" onShow={onShow} />
      )}
      <p className="studio-muted">R is the load factor at first-ply failure; R below 1 fails at the applied load.
        {s.earliest && s.fpf[s.earliest]?.touches_grip ? " The critical element is at a grip's clamped edge, where stress does not converge." : ""}</p>
      {s.fpf_gauge && Object.keys(s.fpf_gauge).length ? (
        <>
          <h4>Gauge section</h4>
          <FailureTable fpf={s.fpf_gauge} earliest={s.earliest_gauge ?? null} testId="fpf-gauge-table" factorPrefix="fpf-gauge-factor" onShow={onShow} />
          <p className="studio-muted">Away from the grips: the value to compare with a test.</p>
        </>
      ) : null}
      </details>
      {s.test_method ? <TestMethodCard tm={s.test_method} cx={cx?.test_method ?? null} /> : null}
    </div>
  );
}

/** The quantities the coupon's test standard reduces a test to (ADR-0072), as the package wrote them: the area, the stress, the strain over the
 * measurement, the modulus beside laminate theory and CalculiX, Poisson's ratio, the net section of an open hole, and the first-ply
 * failure stress, which is never the standard's ultimate strength. Three significant figures, as the standards report. Each standard's own
 * words: D3039's chord modulus over the gross area, D638's modulus of elasticity over the narrow section (ADR-0075). */
function TestMethodCard({ tm, cx }: { tm: NonNullable<Fields["summary"]["test_method"]>; cx: NonNullable<CalculixBeside["test_method"]> | null }) {
  const u = tm.units;
  const three = (v: number) => Number(v.toPrecision(3)).toString();
  const capital = (words: string) => words.charAt(0).toUpperCase() + words.slice(1);
  const area = tm.reduction?.area ?? "gross area";
  const modulus = tm.reduction?.modulus ?? "chord modulus";
  const theory = tm.laminate_theory.isotropic ? "the material's own" : "laminate theory";
  const rows: [string, string][] = [
    [capital(area), `${three(tm.area)} ${u.area} (${three(tm.width)} × ${three(tm.thickness)} ${u.length})`],
    ["Stress P/A", `${three(Math.abs(tm.stress))} ${u.stress} under ${three(Math.abs(tm.force))} ${u.force}`],
  ];
  if (tm.hole) {
    rows.push(["Net section", `${three(tm.hole.net_area)} ${u.area}, ${three(Math.abs(tm.hole.net_stress))} ${u.stress}`],
      ["w/D and D/h", `${three(tm.hole.width_to_hole)} and ${three(tm.hole.hole_to_thickness)}`]);
  }
  if (tm.strain) {
    const c = tm.strain.chord;
    rows.push([`Strain over the ${tm.strain.device}`, `${three(Math.abs(tm.strain.microstrain))} microstrain over ${three(tm.strain.modelled_length)} ${u.length}`],
      [`${capital(modulus)}, ${three(c.from * 1e6)} to ${three(c.to * 1e6)} microstrain`, `${three(c.modulus)} ${u.modulus}` + (cx ? `; reference solver ${three(cx.calculix.modulus)} ${u.modulus}` : "")
        + `; ${theory} ${three(tm.laminate_theory.modulus)} ${u.modulus}`],
      [`Load between those strains`, `${three(Math.abs(c.force_from))} to ${three(Math.abs(c.force_to))} ${u.force}`]);
    if (tm.strain.poisson !== null) rows.push(["Poisson's ratio", `${three(tm.strain.poisson)}; ${theory} ${three(tm.laminate_theory.poisson)}`]);
  }
  const first = tm.earliest ? tm.fpf[tm.earliest] : null;
  if (first) {
    rows.push([`First-ply-failure stress (${criterionName(tm.earliest ?? "")}, ${tm.fpf_basis.replace(/^the /, "")})`, `${three(Math.abs(first.stress))} ${u.stress} ${area === "gross area" ? "gross" : `on the ${area}`}`
      + (first.net_stress !== undefined ? `, ${three(Math.abs(first.net_stress))} ${u.stress} net` : "")
      + (first.microstrain !== undefined ? ` at ${three(Math.abs(first.microstrain))} microstrain` : "")]);
  }
  return (
    <div className="ws-test-method" data-testid="test-method">
      <h4>{tm.designation ? `${tm.designation} test quantities` : "Test quantities"}</h4>
      <dl className="studio-summary">
        {rows.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}
      </dl>
      <p className="studio-muted">The standard&apos;s formulas applied to the solution. First-ply-failure stress is not ultimate strength, which a linear model cannot predict.
        {tm.note_b ? " The first ply fails below 6000 microstrain, so the chord range follows D3039 Table 3, note B." : ""}</p>
    </div>
  );
}

const DASH = "–";
const three = (v: (number | null | undefined)[] | undefined, marks?: (boolean | null)[]) =>  // the noise beside a triple's real values prints as 0
  v ? settled(v).map((x, i) => `${x === null || x === undefined ? DASH : printed(x)}${marks && marks[i] === false ? " ✕" : ""}`).join(" / ") : DASH;

/** The validation table (ADR-0066): one row per quantity, one column per source, every cell the same quantity read the same way: the
 *  reaction, the gauge-centre strain and every ply's σ₁ / σ₂ / τ₁₂ in its fibre axes at the gauge-centre element. */
function ValidationTable({ s, cx, lab }: { s: Fields["summary"]; cx: CalculixBeside | null; lab: Fields["labels"] }) {
  const clt = s.clt ?? null;
  const gaugeElement = cx?.gauge_element?.split(".").pop();
  const plies = Math.max(clt?.plies.length ?? 0, cx?.gauge.length ?? 0);
  if (!clt && !cx) return null;
  return (
    <>
      <h4>Verification</h4>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-num studio-table-sticky" data-testid="validation-table">
          <thead>
            <tr><th scope="col">Quantity</th><th scope="col">Laminate theory</th><th scope="col">FEA</th><th scope="col">Reference solver</th></tr>
          </thead>
          <tbody>
            <tr data-row="reaction"><th scope="row">Reaction ({lab.force})</th><td>input</td><td>{printed(Math.abs(s.reaction.value))}</td>
              <td>{cx?.reaction ? `${printed(Math.abs(cx.reaction.calculix))} (${cx.reaction.difference})` : DASH}</td></tr>
            <tr data-row="strain"><th scope="row">Gauge εx / εy / γxy</th><td>{three(clt?.strain)}</td><td>{three(cx?.gauge_strain?.ours)}</td>
              <td>{three(cx?.gauge_strain?.calculix, cx?.gauge_strain?.agrees)}</td></tr>
            <tr className="studio-table-group"><th scope="colgroup" colSpan={4}>Ply stress σ₁ / σ₂ / τ₁₂ ({lab.stress}), gauge centre</th></tr>
            {Array.from({ length: plies }, (_, k) => {
              const c = clt?.plies[k], g = cx?.gauge[k];
              const angle = c?.angle ?? (g ? s.ply_peaks?.[k]?.angle : undefined);
              return (
                <tr key={k} data-ply={k + 1}><th scope="row">Ply {k + 1}{angle !== undefined ? ` · ${angle}°` : ""}</th>
                  <td>{three(c?.stress_12)}</td><td>{three(g?.ours)}</td><td>{three(g?.calculix, g?.agrees)}</td></tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="studio-muted">Fibre axes; plies from the bottom face; angles from the load axis.{clt ? ` Laminate theory: Ny = reaction / width = ${printed(clt.Ny)} ${lab.force}/${lab.length}.` : ""}
        {gaugeElement ? ` FEA at the centroid of element ${gaugeElement}; reference solver at its integration-point mean.` : ""}
        {cx ? ` ✕ marks a value outside ${printed(100 * cx.tolerance)} %.` : " The reference solver runs with the full analysis."}</p>
    </>
  );
}

/** The stress concentration at the clamped edge (ADR-0066): every ply's peak in every column, apart from the validation table because the
 *  free-edge corner where a gripped tab ends is singular: each number grows as the mesh is refined and depends on where it is read. */
function PeaksTable({ s, cx, lab, criterion, onShow }: { s: Fields["summary"]; cx: CalculixBeside | null; lab: Fields["labels"]; criterion: string;
  onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const peaks = s.ply_peaks ?? [];
  const frdPlies = cx?.frd?.plies ?? null;
  const clamped = peaks.some((p) => p.S11.touches_grip);
  return (
    <details className="studio-details" data-testid="peaks">
      <summary><h4>{clamped ? "Peak stresses at the grips" : "Peak stresses"} (not converged)</h4></summary>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-sticky" data-testid="peaks-table">
          <thead>
            <tr><th scope="col">Ply</th><th scope="col">FEA, element centroid, σ₁ / σ₂ / τ₁₂ ({lab.stress})</th><th scope="col">Reference solver, corner node ({lab.stress})</th></tr>
          </thead>
          <tbody>
            {peaks.map((p, k) => {
              const f = frdPlies?.[k];
              return (
                <tr key={p.ply} data-ply={p.ply}>
                  <th scope="row">{p.ply} · {p.angle}°</th>
                  <td><span className="studio-num">{three([p.S11.value, p.S22.value, p.S12.value])}</span> at element {p.S11.label.split(".").pop()}{p.S11.face ? `, ${p.S11.face} face` : ""}{p.S11.touches_grip ? ", grip edge" : ""}
                    {" "}<button type="button" className="studio-text-button" onClick={() => onShow(p.S11.element, p.ply, criterion, p.S11.face)}>Show</button></td>
                  <td>{f && typeof f.s1_max === "number" ? <><span className="studio-num">{three([f.s1_max, f.s2_max, f.t12_max_abs])}</span> at node {f.s1_max_node}{xyz(f.s1_max_xyz)}</> : DASH}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="studio-muted">{clamped ? "At a grip's free edge the stress is singular: it grows as the mesh is refined, so these values are not compared. " : ""}
        The reference solver reports values extrapolated to corner nodes, so its peaks sit above the element centroids.</p>
    </details>
  );
}

/** The largest |change| of a triple's components, the one its row reports (the components are read against the triple's largest value). */
const worst = (changes: (number | null)[] | null | undefined): number | null =>
  changes ? changes.reduce<number | null>((acc, c) => (c === null ? acc : acc === null || Math.abs(c) > Math.abs(acc) ? c : acc), null) : null;

/** The mesh convergence study (ADR-0068): the kernel on the coupon's mesh and on refinements that split every element along both axes; one
 *  column per mesh, each cell the value and its change from the previous mesh, and a last column saying whether the quantity has settled
 *  (its last change under the study's threshold). The peaks and the failure factors keep ADR-0066's label: not validation values. */
function ConvergenceTable({ study, lab }: { study: Convergence; lab: Fields["labels"] }) {
  if (!study.studied) {
    const reason = customerText(study.reason);
    return <p className="studio-muted" data-testid="convergence-not-studied">Mesh convergence: not studied{reason ? `, ${reason}` : ""}.</p>;
  }
  const meshes = study.meshes, changes = study.changes!, settled = study.settled!, below = study.settled_below;
  const last = meshes.length - 1;
  const verdict = (change: number | null) => (change === null ? DASH : Math.abs(change) < below ? `${percentChange(change)}, settled` : `${percentChange(change)}, still moving`);
  const cells = (values: (number | string)[], steps: (number | null)[]) => (
    <>
      {values.map((v, i) => <td key={i}>{typeof v === "number" ? printed(v) : v}{i > 0 && steps[i] !== null ? <span className="studio-muted"> ({percentChange(steps[i])})</span> : null}</td>)}
      <td>{verdict(steps[last])}</td>
    </>
  );
  const tripleCells = (values: number[][], steps: ((number | null)[] | null)[]) =>
    cells(values.map((v) => three(v)), steps.map((c) => worst(c)));
  const gaugeElements = Array.from(new Set(meshes.map((m) => m.gauge_element)));
  const settledNames = Object.entries({ reaction: "the reaction", gauge_strain: "the gauge strain", plies: "the gauge ply stresses" })
    .filter(([key]) => settled[key as keyof typeof settled]).map(([, name]) => name);
  const movingNames = Object.entries({ peaks: "the grip peaks", fpf: "the whole-model R", fpf_gauge: "the gauge-section R" })
    .filter(([key]) => !settled[key as keyof typeof settled]).map(([, name]) => name);
  return (
    <details className="studio-details" data-testid="convergence">
      <summary><h4>Mesh convergence</h4></summary>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-num studio-table-sticky" data-testid="convergence-table">
          <thead>
            <tr><th scope="col">Quantity</th>{meshes.map((m) => <th key={m.factor} scope="col">{m.factor}× mesh<br /><span className="studio-muted">{m.elements.toLocaleString("en-US")} elements</span></th>)}
              <th scope="col">Last step<br /><span className="studio-muted">settled &lt; {printed(100 * below)} %</span></th></tr>
          </thead>
          <tbody>
            <tr data-row="reaction"><th scope="row">Reaction ({lab.force})</th>{cells(meshes.map((m) => m.reaction), changes.reaction)}</tr>
            <tr data-row="strain"><th scope="row">Gauge εx / εy / γxy</th>{tripleCells(meshes.map((m) => m.gauge_strain), changes.gauge_strain)}</tr>
            <tr className="studio-table-group"><th scope="colgroup" colSpan={meshes.length + 2}>Gauge ply stress σ₁ / σ₂ / τ₁₂ ({lab.stress})</th></tr>
            {meshes[0].plies.map((p, k) => (
              <tr key={`gauge-${p.ply}`} data-ply={p.ply} data-row="gauge">
                <th scope="row">Ply {p.ply} · {p.angle}°</th>
                {tripleCells(meshes.map((m) => m.plies[k].stress_12), changes.plies[k].stress_12)}
              </tr>
            ))}
            <tr className="studio-table-group"><th scope="colgroup" colSpan={meshes.length + 2}>Largest |σ₁| ({lab.stress})</th></tr>
            {meshes[0].peaks.map((p, k) => (
              <tr key={`peak-${p.ply}`} data-ply={p.ply} data-row="peak">
                <th scope="row">Ply {p.ply} · {p.angle}°{p.touches_grip ? ", grip" : ""}</th>
                {cells(meshes.map((m) => m.peaks[k].s1), changes.peaks[k].s1)}
              </tr>
            ))}
            {Object.keys(changes.fpf).length ? <tr className="studio-table-group"><th scope="colgroup" colSpan={meshes.length + 2}>First-ply failure R</th></tr> : null}
            {Object.keys(changes.fpf).map((criterion) => (
              <tr key={`fpf-${criterion}`} data-row="fpf" data-criterion={criterion}>
                <th scope="row">{criterionName(criterion)}, whole model</th>
                {cells(meshes.map((m) => m.fpf[criterion]), changes.fpf[criterion])}
              </tr>
            ))}
            {Object.keys(changes.fpf_gauge).map((criterion) => (
              <tr key={`fpfg-${criterion}`} data-row="fpf-gauge" data-criterion={criterion}>
                <th scope="row">{criterionName(criterion)}, gauge section</th>
                {cells(meshes.map((m) => m.fpf_gauge[criterion]), changes.fpf_gauge[criterion])}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="studio-muted" data-testid="convergence-words">
        Each refinement splits every element in both directions; percentages are the change from the previous mesh, read at element {gaugeElements.join(", then ")}.
        {settledNames.length ? <> {capitalise(listed(settledNames))} changed by less than {printed(100 * below)} %.</> : null}
        {movingNames.length ? <> {capitalise(listed(movingNames))} keep changing: they sit at a grip&apos;s free edge, where stress is singular.</> : null}
        {study.left_out.length ? <> {study.left_out.map((o) => `The ${o.factor}× mesh (${o.elements.toLocaleString("en-US")} elements) is over the ${study.cap.toLocaleString("en-US")}-element limit.`).join(" ")}</> : null}
      </p>
    </details>
  );
}

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** Names as prose: "a", "a and b", "a, b and c". */
const listed = (names: string[]) => (names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`);

/** The Summary of a job solved before ADR-0066: the largest of each component over all plies, and CalculiX's viewer numbers beside them. */
function OlderPeaks({ fields, onShow }: { fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const s = fields.summary, lab = fields.labels, cx = s.calculix ?? null;
  const fibre = s.max_ply.S11;
  const others = Object.entries(s.max_ply).filter(([name]) => name !== "mises" && name !== "S11");  // the ply von Mises row is gone: a viewer's von Mises is another quantity (ADR-0030 amendment 6)
  const place = (m: Extreme) => <>in ply {m.ply} ({m.angle}°){m.face ? `, ${m.face} face,` : ""} at element {m.label.split(".").pop()}</>;
  return (
    <>
      {cx && cx.gauge.length ? (
        <>
          <h4>Verification, gauge section</h4>
          <div className="studio-table-scroll">
            <table className="studio-table studio-table-num studio-table-sticky" data-testid="gauge-table">
              <thead><tr><th scope="col">Ply</th><th scope="col">σ₁ ({lab.stress})</th><th scope="col">σ₂ ({lab.stress})</th><th scope="col">τ₁₂ ({lab.stress})</th></tr></thead>
              <tbody>
                {cx.gauge.map((g) => (
                  <tr key={g.ply} data-ply={g.ply}><th scope="row">{g.ply} · {fields.mesh.angles[g.ply - 1]}°</th>
                    {[0, 1, 2].map((i) => <td key={i}>{g.ours[i] === null ? "–" : printed(g.ours[i] as number)} / {g.calculix[i] === null ? "–" : printed(g.calculix[i] as number)}{g.agrees[i] === false ? " ✕" : ""}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="studio-muted">Each cell: FEA / reference solver at element {cx.gauge_element?.split(".").pop()}. ✕ marks a value outside {printed(100 * cx.tolerance)} %.</p>
        </>
      ) : null}
      <h4>Peaks at the grips</h4>
      <dl className="studio-summary">
        {fibre ? (
          <div data-testid="summary-fibre-peak"><dt>Largest σ₁ along the fibres</dt>
            <dd>{printed(fibre.value)} {lab.stress} {place(fibre)}
              <button type="button" className="studio-text-button" onClick={() => onShow(fibre.element, fibre.ply, s.earliest ?? "", fibre.face)}>Show</button>
              {cx?.frd ? <span data-testid="summary-fibre-calculix">; reference solver σyy = {printed(cx.frd.syy_max)} {lab.stress} at corner node {cx.frd.syy_max_node}{xyz(cx.frd.syy_max_xyz as number[] | undefined)}</span> : null}</dd></div>
        ) : null}
        {others.map(([name, m]) => (
          <div key={name}><dt>Largest {COMPONENT[name] ?? name}</dt>
            <dd>{printed(m.value)} {lab.stress} {place(m)}
              <button type="button" className="studio-text-button" onClick={() => onShow(m.element, m.ply, s.earliest ?? "", m.face)}>Show</button></dd></div>
        ))}
        {cx?.frd ? (
          <>
            <div data-testid="summary-frd-mises"><dt>Largest von Mises, reference solver</dt><dd>{printed(cx.frd.mises_max)} {lab.stress} at node {cx.frd.mises_max_node}{xyz(cx.frd.mises_max_xyz)}</dd></div>
            <div><dt>Transverse stress at the grips, reference solver</dt><dd>σxx from {printed(cx.frd.sxx_min)} to {printed(cx.frd.sxx_max)} {lab.stress}</dd></div>
            {typeof cx.frd.gauge_mises_max === "number" ? <div><dt>Gauge section, reference solver</dt><dd>largest σyy {printed(cx.frd.gauge_syy_max as number)}, von Mises {printed(cx.frd.gauge_mises_max)} {lab.stress}</dd></div> : null}
          </>
        ) : null}
      </dl>
      <p className="studio-muted">FEA values are fibre-axis ply stresses at element centroids; reference solver values are global-axis nodal values. Both peak at the grip edge, where stress grows as the mesh is refined.</p>
    </>
  );
}

const where = (xy: number[], unit: string) => `(${xy.map((v) => printed(v)).join(", ")} ${unit})`;

/** The answer to "does it fail, at what load, where" (ADR-0085), as the package wrote it: per criterion in the gauge section (the whole model for a
 * coupon without one), fails or holds at the applied loading, the factor R, the loading at first-ply failure, the ply, mode and position; the
 * earlier failure at a clamped edge apart; the largest ply stresses with their sign. Every number is the package's (ADR-0051). */
export function AnswerCard({ fields, onShow }: { fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const a = answerOf(fields);
  if (!a) return null;
  const L = fields.labels.length ?? "";
  const e = a.earliest;
  const loading = (r: AnswerRow) => r.applied === null ? "–"
    : `${printed(Math.abs(r.applied))} ${a.appliedUnit}` + (a.control !== "force" && r.reaction !== null ? `, ${printed(Math.abs(r.reaction))} ${a.forceUnit}` : "");
  const times = a.everyLoad ? "every applied load" : "the applied loading";
  const who = (r: { ply: number; angle: number; face: string | null }) => `ply ${r.ply} (${r.angle}°)${r.face ? `, ${r.face} face` : ""}`;
  const extremes = fields.summary.ply_extremes;
  return (
    <div className="studio-panel studio-answer" data-testid="answer" data-basis={a.basis} data-fails={e.fails}>
      <h3>First-ply failure <span className="studio-badge">{a.basisWords}</span></h3>
      <p className="studio-answer-headline" data-testid="answer-headline">
        <strong>{e.fails ? "Fails" : "Holds"} at the applied loading</strong> ({e.name}).{" "}
        {e.fails ? `The first ply fails at ${printed(e.factor)} of ${times}` : `The first ply would fail at ${printed(e.factor)} × ${times}`}
        {e.applied !== null ? ` (${loading(e)}${a.control !== "force" ? ` at ${a.reactionSet}` : ""})` : ""}: {who(e)}, {modeWords(e.mode)}, element {e.label.split(".").pop()} {where(e.xy, L)}.
      </p>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-sticky" data-testid="answer-table">
          <thead><tr><th scope="col">Criterion</th><th scope="col">Verdict</th><th scope="col" className="studio-num-head">R</th><th scope="col">Load at failure</th><th scope="col">First ply, mode</th><th scope="col">Location</th><th scope="col"><span className="sr-only">Show</span></th></tr></thead>
          <tbody>
            {a.rows.map((r) => (
              <tr key={r.criterion} data-criterion={r.criterion} data-fails={r.fails} className={r.earliest ? "studio-earliest" : undefined}>
                <th scope="row">{r.name}{r.earliest ? " (governs)" : ""}</th>
                <td data-testid={`answer-verdict-${r.criterion}`}><span className={`studio-badge studio-badge-${r.fails ? "fail" : "pass"}`}>{r.fails ? "fails" : "holds"}</span></td>
                <td className="studio-num" data-testid={`answer-factor-${r.criterion}`}>{printed(r.factor)}</td>
                <td className="studio-num" data-testid={`answer-loading-${r.criterion}`}>{loading(r)}</td>
                <td>{who(r)}{r.tied.length ? `, tied with ${r.tied.join(", ")}` : ""}; {modeWords(r.mode)}</td>
                <td>element {r.label.split(".").pop()} {where(r.xy, L)}</td>
                <td><button type="button" className="studio-text-button" onClick={() => onShow(r.element, r.ply, r.criterion, r.face)}>Show</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="studio-muted">R is the load factor at first-ply failure; R ≤ 1 fails at the applied loading. First-ply failure is the onset of damage, not ultimate strength.</p>
      {a.outside ? (
        <p className="studio-answer-outside" data-testid="answer-outside">
          {a.outside.touches_grip ? "At a grip edge" : `Outside ${a.basisWords}`}, {a.outside.name} is reached earlier, at {printed(a.outside.factor)} × {times}: {who(a.outside)}, {modeWords(a.outside.mode)}, element{" "}
          {a.outside.label.split(".").pop()} {where(a.outside.xy, L)}.
          {a.outside.touches_grip ? " Stress there grows as the mesh is refined, so it is reported separately." : ""}{" "}
          <button type="button" className="studio-text-button" onClick={() => onShow(a.outside!.element, a.outside!.ply, a.outside!.criterion, a.outside!.face)}>Show</button>
        </p>
      ) : null}
      {extremes ? <ExtremesTable extremes={extremes} basis={BASIS_WORDS[extremes.basis]} unit={fields.labels.stress ?? ""} lengthUnit={L} criterion={e.criterion} onShow={onShow} /> : null}
    </div>
  );
}

const EXTREME_HEADS = ["σ₁ tension", "σ₁ compression", "σ₂ tension", "σ₂ compression", "τ₁₂ largest"];

function ExtremesTable({ extremes, basis, unit, lengthUnit, criterion, onShow }: {
  extremes: NonNullable<Fields["summary"]["ply_extremes"]>; basis: string; unit: string; lengthUnit: string; criterion: string;
  onShow: (element: number, ply: number, criterion: string, face?: string | null) => void;
}) {
  const rows = extremeRows(extremes.overall);
  return (
    <>
      <h4>Largest ply stresses, {basis}</h4>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-sticky" data-testid="answer-extremes">
          <thead><tr><th scope="col">Stress</th><th scope="col" className="studio-num-head">Value ({unit})</th><th scope="col">Ply</th><th scope="col">Location</th><th scope="col"><span className="sr-only">Show</span></th></tr></thead>
          <tbody>
            {rows.map(({ key, words, extreme }) => (
              <tr key={key} data-extreme={key}>
                <th scope="row">{words}</th><td className="studio-num">{printed(extreme.value)}</td><td className="studio-nowrap">{extreme.ply} · {extreme.angle}°{extreme.face ? `, ${extreme.face} face` : ""}</td>
                <td>element {extreme.label.split(".").pop()} {where(extreme.xy, lengthUnit)}</td>
                <td><button type="button" className="studio-text-button" onClick={() => onShow(extreme.element, extreme.ply ?? 1, criterion, extreme.face)}>Show</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="studio-answer-plies">
        <summary>By ply</summary>
        <div className="studio-table-scroll">
          <table className="studio-table studio-table-num studio-table-sticky" data-testid="answer-extremes-plies">
            <thead><tr><th scope="col">Ply</th>{EXTREME_HEADS.map((h) => <th key={h} scope="col">{h}</th>)}</tr>
              <tr className="studio-table-units"><th scope="col" />{EXTREME_HEADS.map((h) => <th key={h} scope="col">{unit}</th>)}</tr></thead>
            <tbody>
              {extremes.plies.map((p) => (
                <tr key={p.ply}><th scope="row">{p.ply} · {p.angle}°</th>
                  {[p.S11.tension, p.S11.compression, p.S22.tension, p.S22.compression, p.S12.largest].map((x, i) => <td key={i}>{x ? printed(x.value) : "–"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="studio-muted">Fibre-axis stresses at element centroids; tension and compression listed separately.</p>
    </>
  );
}

function FailureTable({ fpf, earliest, testId, factorPrefix, onShow }: {
  fpf: Record<string, FirstPlyFailure>; earliest: string | null; testId: string; factorPrefix: string;
  onShow: (element: number, ply: number, criterion: string, face?: string | null) => void;
}) {
  return (
    <div className="studio-table-scroll">
      <table className="studio-table studio-table-sticky" data-testid={testId}>
        <thead><tr><th scope="col">Criterion</th><th scope="col" className="studio-num-head">R</th><th scope="col" className="studio-num-head">1/R</th><th scope="col">Ply</th><th scope="col">Mode</th><th scope="col">Location</th><th scope="col"><span className="sr-only">Show</span></th></tr></thead>
        <tbody>
          {Object.entries(fpf).sort(([, a], [, b]) => a.factor - b.factor).map(([criterion, f]) => (
            <tr key={criterion} data-criterion={criterion} className={criterion === earliest ? "studio-earliest" : undefined}>
              <th scope="row">{criterionName(criterion)}{criterion === earliest ? " (governs)" : ""}</th>
              <td className="studio-num" data-testid={`${factorPrefix}-${criterion}`}>{printed(f.factor)}</td><td className="studio-num">{printed(f.index)}</td>
              <td className="studio-nowrap">{f.ply} · {f.angle}°{f.face ? `, ${f.face} face` : ""}{f.tied_plies.length > 1 ? `, tied ${f.tied_plies.join(", ")}` : ""}</td>
              <td>{modeWords(f.mode)}</td><td>element {f.label.split(".").pop()}, {f.place}</td>
              <td><button type="button" className="studio-text-button" onClick={() => onShow(f.element, f.ply, criterion, f.face)}>Show</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The explanation of the result (ADR-0052), as the product's own words (ADR-0091): the writer stays in the run record and in `data-writer`,
 * not on the page; the first two sentences shown, the rest under Details. */
export function ExplanationPanel({ explanation, answer }: { explanation: Explanation | null; answer?: ExplainAnswer | null }) {
  if (!explanation && !answer) return null;
  const prose = (answer?.prose ?? explanation?.sentences ?? []).map(shownSentence).filter((sentence): sentence is string => sentence !== null);
  const writer = answer?.writer ?? explanation?.writer ?? "template";
  const setup = (explanation?.setup_sentences ?? []).map(shownSentence).filter((sentence): sentence is string => sentence !== null);
  if (!prose.length && !setup.length) return null;
  return (
    <div className="studio-panel" data-testid="explanation" data-writer={writer}>
      <h3>What this shows</h3>
      {prose.slice(0, 2).map((sentence, i) => <p key={i}>{sentence}</p>)}
      {prose.length > 2 || setup.length ? (
        <details className="studio-details-more">
          <summary>Details</summary>
          {prose.slice(2).map((sentence, i) => <p key={i}>{sentence}</p>)}
          {setup.length ? <><h4>Setup</h4>{setup.map((s, i) => <p key={i}>{s}</p>)}</> : null}
        </details>
      ) : null}
    </div>
  );
}

export function Downloads({ apiBase, job, fields }: { apiBase: string; job: JobStatus; fields: Fields | null }) {
  if (!DOWNLOADS.some(([key]) => key in job.outputs)) return null;
  return (
    <div className="studio-panel" data-testid="downloads">
      <h3>Files</h3>
      <JobFiles apiBase={apiBase} job={job} naming={namingOf(fields)} viewer={false} />
      {isActive(job.state) ? <p className="studio-muted">More files appear as the analysis finishes.</p> : null}
    </div>
  );
}

/** The element the viewer frames: the answer's first failure, in the gauge section when the coupon has one (ADR-0085); the whole model's earliest on an
 * older job. */
function criticalElement(fields: Fields): number | null {
  const answer = answerOf(fields);
  if (answer) return answer.earliest.element;
  return fields.summary.earliest ? fields.summary.fpf[fields.summary.earliest].element : null;
}

/** The probe table's headings (ADR-0091): groups with the unit on the first row, the symbols on the second, in the order of
 * `PROBE_COLUMNS` (σ₁ σ₂ τ₁₂, Mises, Tresca, the three principal stresses, the pressure, ε₁ ε₂ γ₁₂). */
const PROBE_GROUPS: { title: string; span: number; heads: string[] }[] = [
  { title: "Stress, fibre axes", span: 3, heads: ["σ₁", "σ₂", "τ₁₂"] },
  { title: "Mises", span: 1, heads: [""] },
  { title: "Tresca", span: 1, heads: [""] },
  { title: "Principal stress", span: 3, heads: ["max", "mid", "min"] },
  { title: "Pressure", span: 1, heads: [""] },
  { title: "Strain, fibre axes", span: 3, heads: ["ε₁", "ε₂", "γ₁₂"] },
];

/** Every ply of the picked element (ADR-0066 amendment 2): the element's number, the centroid, no averaging, each ply in its fibre axes;
 * with a CSV of the same numbers. */
function ProbePanel({ fields, table }: { fields: import("@/lib/studio-api").Fields; table: ProbeTable }) {
  const lab = fields.labels;
  const faces = table.rows.some((r) => r.face);
  const href = `data:text/csv;charset=utf-8,${encodeURIComponent(probeCsv(fields, table))}`;
  return (
    <details className="studio-probe" data-testid="probe" open>
      <summary>Ply results at element {table.label}</summary>
      <p className="studio-muted">{table.note}</p>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-num studio-table-sticky studio-table-compact" data-testid="probe-table">
          <thead>
            <tr>
              <th scope="col" rowSpan={2}>Ply</th>{faces ? <th scope="col" rowSpan={2}>Face</th> : null}
              {PROBE_GROUPS.map((g) => (g.span === 1
                ? <th key={g.title} scope="col" rowSpan={2}>{g.title}<br /><span className="studio-muted">{lab.stress}</span></th>
                : <th key={g.title} scope="colgroup" colSpan={g.span} className="studio-table-group-head">{g.title}{g.title.startsWith("Strain") ? "" : ` (${lab.stress})`}</th>))}
            </tr>
            <tr>{PROBE_GROUPS.filter((g) => g.span > 1).flatMap((g) => g.heads.map((h) => <th key={`${g.title}-${h}`} scope="col">{h}</th>))}</tr>
          </thead>
          <tbody>{table.rows.map((r) => (
            <tr key={`${r.ply}-${r.face ?? ""}`} data-ply={r.ply}><th scope="row">{r.ply} · {r.angle}°</th>{faces ? <td className="studio-text-cell">{r.face}</td> : null}
              {r.values.map((v, i) => <td key={PROBE_COLUMNS[i]}>{v === null || v === undefined ? "–" : printed(v)}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
      <p className="studio-muted">Mises, Tresca and the principal stresses are for comparison, not composite failure criteria.
        {" "}<a href={href} download={`probe-element-${table.label}.csv`} data-testid="probe-csv">Export CSV</a></p>
    </details>
  );
}

export function ResultsView({ fields, explanation, job, apiBase, preview, live = null, updating = false, showFiles = true }: {
  fields: Fields; explanation: Explanation | null; job: JobStatus | null; apiBase: string; preview: Preview | null;
  /** our kernel's live answer (ADR-0086), shown with its seconds until a full run checks it; null for a full run's result */
  live?: { seconds: number; warm: boolean } | null;
  /** a newer live answer is on its way: the numbers shown are the last rows' */
  updating?: boolean;
  /** the job's files at the foot; off in the workspace, whose left column lists them */
  showFiles?: boolean;
}) {
  const [choice, setChoice] = useState<FieldChoice>(() => DEFAULT_CHOICE(fields));
  const [scale, setScale] = useState<number>(() => suggestedScale(fields.mesh.nodes, fields.nodal.magnitude));
  const [deformed, setDeformed] = useState(true);
  const [wireframe, setWireframe] = useState(true);
  const [contours, setContours] = useState(DEFAULT_CONTOURS);
  const [picked, setPicked] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number | null>(() => criticalElement(fields));
  const [answer, setAnswer] = useState<ExplainAnswer | null>(null);
  useEffect(() => {
    // once our engine has written the explanation, the API's writer (the template, or a model behind a setting) rephrases it (ADR-0052)
    if (!job || !apiBase || !("explanation" in job.outputs)) return;
    let cancelled = false;
    explainJob(apiBase, job.job_id, "result").then((a) => { if (!cancelled) setAnswer(a); })
      .catch((error) => { if (!cancelled && !(error instanceof StudioError && error.status === 409)) setAnswer(null); });
    return () => { cancelled = true; };
  }, [job?.job_id, job?.state, "explanation" in (job?.outputs ?? {}), apiBase]);
  useEffect(() => { setChoice(DEFAULT_CHOICE(fields)); setScale(suggestedScale(fields.mesh.nodes, fields.nodal.magnitude)); setHighlight(criticalElement(fields)); }, [fields]);
  const options = useMemo(() => fieldOptions(fields), [fields]);
  const option = options.find((o) => o.id === choice.id) ?? options[0];
  const values = useMemo(() => valuesFor(fields, choice), [fields, choice]);
  const colorScale = useMemo(() => scaleFor(values.values, !values.signed, values.range), [values]);
  const field = useMemo<SceneField>(() => ({ by: values.by, values: values.values, scale: { min: colorScale.min, max: colorScale.max, stops: colorScale.stops, bands: contours } }),
    [values, colorScale, contours]);
  const held: SceneMarker[] = preview ? preview.held.filter((h, i, all) => all.findIndex((x) => x.set === h.set) === i)
    .map((h) => ({ nodes: fields.mesh.node_sets[h.set] ?? preview.mesh.node_sets[h.set] ?? [], label: `held: ${h.set}` })) : [];
  const loaded = preview ? { nodes: fields.mesh.node_sets[preview.loaded.set] ?? preview.mesh.node_sets[preview.loaded.set] ?? [],
    direction: preview.loaded.direction, label: `${preview.loaded.control} ${printed(preview.loaded.value)} ${preview.loaded.unit}` } : null;
  const readout = picked !== null ? elementReadout(fields, picked, choice, printed) : null;
  const show = (element: number, ply: number, criterion: string, face?: string | null) => {
    setHighlight(element); setPicked(element);
    const faceIndex = face && fields.mesh.faces ? Math.max(0, fields.mesh.faces.indexOf(face)) : undefined;
    setChoice((c) => ({ ...c, ply, criterion: criterion || c.criterion, face: faceIndex ?? c.face }));
  };
  return (
    <div className="studio-results" data-testid="results" data-source={live ? "live" : "run"} data-updating={updating}>
      {live ? (
        <p className="studio-live-banner" data-testid="live-banner">
          <strong>Preview</strong> ({live.seconds < 10 ? live.seconds.toFixed(1) : Math.round(live.seconds)} s). Run the analysis to verify it and write the report.{updating ? " Updating…" : ""}
        </p>
      ) : updating ? <p className="studio-live-banner" data-testid="live-banner">Updating…</p> : null}
      <div className="studio-scene-block">
        <Scene nodes={fields.mesh.nodes} quads={fields.mesh.quads} thickness={preview?.geometry.thickness ?? 1} field={field}
          displacement={deformed ? fields.nodal.displacement : null} scale={scale} held={held} loaded={loaded} highlight={highlight} picked={picked}
          wireframe={wireframe} onPick={setPicked} />
        <Legend scale={colorScale} label={values.label} unit={values.unit} by={values.by} bands={contours} />
      </div>
      <div className="studio-controls" data-testid="field-controls">
        <label>Field
          <select value={choice.id} onChange={(e) => setChoice({ ...choice, id: e.target.value })} aria-label="Field">
            {[...new Set(options.map((o) => o.group))].map((group) => (
              <optgroup key={group} label={group}>{options.filter((o) => o.group === group).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</optgroup>
            ))}
          </select>
        </label>
        {option.perPly ? (
          <label>Ply
            <select value={choice.ply} onChange={(e) => setChoice({ ...choice, ply: Number(e.target.value) })} aria-label="Ply">
              {fields.mesh.angles.map((angle, i) => <option key={i} value={i + 1}>{i + 1}: {angle}°</option>)}
            </select>
          </label>
        ) : null}
        {option.perFace && fields.mesh.faces ? (
          <label>Face
            <select value={choice.face} onChange={(e) => setChoice({ ...choice, face: Number(e.target.value) })} aria-label="Face">
              {fields.mesh.faces.map((face, i) => <option key={face} value={i}>{face}</option>)}
            </select>
          </label>
        ) : null}
        {option.perCriterion ? (
          <label>Criterion
            <select value={choice.criterion} onChange={(e) => setChoice({ ...choice, criterion: e.target.value })} aria-label="Criterion">
              {Object.keys(fields.element.failure).map((c) => <option key={c} value={c}>{criterionName(c)}</option>)}
            </select>
          </label>
        ) : null}
        {!option.nodalOnly && !option.elementOnly && option.id !== "failure_index_ply" ? (
          <label>Values
            <select value={choice.averaged ? "average" : "element"} onChange={(e) => setChoice({ ...choice, averaged: e.target.value === "average" })} aria-label="Shown as">
              <option value="element">Element</option>
              <option value="average">Nodal average</option>
            </select>
          </label>
        ) : null}
        <label><input type="checkbox" checked={deformed} onChange={(e) => setDeformed(e.target.checked)} /> Deformed, ×
          <input type="number" value={scale} min={0} step="any" onChange={(e) => setScale(Number(e.target.value) || 0)} aria-label="Deformation scale" className="studio-scale" /></label>
        <label><input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} /> Mesh edges</label>
        <label>Contours
          <select value={contours} onChange={(e) => setContours(Number(e.target.value))} aria-label="Contours">
            {CONTOURS.map(([bands, word]) => <option key={bands} value={bands}>{word}</option>)}
          </select>
        </label>
      </div>
      <AnswerCard fields={fields} onShow={show} />
      {readout ? (
        <div className="studio-panel studio-readout" data-testid="readout">
          <h3>{readout.title}{highlight === picked ? <span className="studio-badge">critical</span> : null}</h3>
          <dl>{readout.rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <p className="studio-muted">Click another element to read it, or the background to clear.</p>
          {picked !== null ? <ProbePanel fields={fields} table={probeTable(fields, picked)} /> : null}
        </div>
      ) : <p className="studio-muted studio-pick-hint">Click an element to read its values. The critical element is outlined in red.</p>}
      <SummaryPanel fields={fields} onShow={show} />
      <ExplanationPanel explanation={explanation} answer={answer} />
      {job && showFiles ? <Downloads apiBase={apiBase} job={job} fields={fields} /> : null}
    </div>
  );
}
