"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { X } from "lucide-react";
import { explainJob, sameResults, StudioError, type Convergence, type ExplainAnswer, type Explanation, type CalculixBeside, type Extreme, type Fields, type FirstPlyFailure, type JobStatus,
  type Preview } from "@/lib/studio-api";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, PROBE_COLUMNS, probeCsv, probeTable, valuesFor, type FieldChoice, type ProbeTable } from "@/lib/studio-fields";
import { answerOf, answerStat, BASIS_WORDS, CRITERION_NAMES, extremeRows, modeWords, type AnswerRow } from "@/lib/studio-answer";
import { customerText, downloadable, setWords, shownSentence } from "@/lib/studio-copy";
import { useAllTests, type FieldView, type Place } from "./project-context";
import { DEFAULT_PALETTE, isPalette, legendGradient, legendTicks, overlayColors, PALETTES, percentChange, printed, scaleFor, settled, type Palette, type Scale } from "@/lib/studio-colors";
import { suggestedScale } from "@/lib/studio-geometry";
import { AbaqusCard } from "./abaqus-card";
import { JobFiles, namingOf } from "./job-files";
import { Scene } from "./scene";
import type { SceneField } from "./scene-canvas";
import { proposedInputs, sceneInputs } from "./scene-inputs";
import type { ProposedInputs } from "./project-context";
import { remember, remembered } from "./local";
import { DetailsToggle, Slot, useCanvasSlots, ViewMenu } from "@/components/workspace/canvas-slots";

/** The contour choices: the smooth ramp, or bands of one flat colour each with no line between them (ADR-0063). Twelve by default, as
 * the mockup the founder chose draws them, so the stress through the gauge and at the grips reads in steps (ADR-0063 amendment 3). */
export const CONTOURS: [number, string][] = [[0, "smooth"], [5, "5 bands"], [8, "8 bands"], [10, "10 bands"], [12, "12 bands"]];
export const DEFAULT_CONTOURS = 12;

export function Legend({ scale, label, unit, by, bands = 0, lit = false, card = false, note = "" }: { scale: Scale; label: string; unit: string; by: "node" | "element"; bands?: number;
  /** the lighting is on: the shading changes the colours, which the legend says (ADR-0063 amendment 1) */ lit?: boolean;
  /** the results card's form (ADR-0134 amendment 1): a title and what it is read at, the bar and its two ends; the whole sentence stays
   * for a screen reader */ card?: boolean;
  /** what else the card's legend says beside what the field is read at: a thickness drawn larger than it is */ note?: string }) {
  const sentence = (
    <><strong>{label}</strong>{unit && unit !== "-" ? ` (${unit})` : ""} · {by === "element" ? "element values" : "nodal averages"} · {printed(scale.ends[0])} to {printed(scale.ends[1])}{unit && unit !== "-" ? ` ${unit}` : ""}
      {bands ? ` · ${bands} bands` : ""}{scale.kind === "diverging" ? " · grey is zero" : ""}{lit ? " · lit: the shading changes the colours" : ""}</>
  );
  if (card) {
    const head = legendHead(label, unit);
    const end = (v: number) => (head.share ? `${(100 * v).toFixed(1)} %` : printed(v));
    const sub = [head.sub, note].filter(Boolean).join(" · ");
    return (
      <div className="studio-legend cv-legend" data-testid="legend" data-source={scale.source} data-bands={bands}>
        <div className="cv-legend-head" aria-hidden="true"><span className="cv-legend-title">{head.title}</span><span className="cv-legend-sub" title={sub}>{sub}</span></div>
        <div className="studio-legend-bar" style={{ background: legendGradient(scale, bands) }} aria-hidden="true" />
        <div className="cv-legend-ends" aria-hidden="true"><span>{end(scale.ends[0])}</span><span>{end(scale.ends[1])}</span></div>
        <p className="sr-only">{sentence}{note ? ` · ${note}` : ""}</p>
      </div>
    );
  }
  // a tick at every band boundary up to ten bands; more than that labels every other one, so the numbers keep apart
  const ticks = legendTicks(scale, !bands ? 5 : bands > 10 && bands % 2 === 0 ? bands / 2 + 1 : bands + 1);
  return (
    <div className="studio-legend" data-testid="legend" data-source={scale.source} data-bands={bands}>
      <div className="studio-legend-bar" style={{ background: legendGradient(scale, bands) }} aria-hidden="true" />
      <div className="studio-legend-ticks" aria-hidden="true">{ticks.map((t, i) => (
        <span key={i} style={{ "--at": `${(100 * i) / Math.max(ticks.length - 1, 1)}%` } as CSSProperties}>{printed(t)}</span>
      ))}</div>
      <p>{sentence}</p>
    </div>
  );
}

/** The card legend's title and what it is read at, from the field's label: its first part, then the rest (the ply, the criterion). The
 * failure index 1/R is read as the share of the strength used (ADR-0134 amendment 1): its ends are the package's index in percent. */
export function legendHead(label: string, unit: string): { title: string; sub: string; share: boolean } {
  const parts: string[] = [];
  let depth = 0, from = 0;
  for (let i = 0; i < label.length; i++) {
    const c = label[i];
    if (c === "(") depth++;
    else if (c === ")") depth = Math.max(0, depth - 1);
    else if (c === "," && depth === 0) { parts.push(label.slice(from, i).trim()); from = i + 1; }
  }
  parts.push(label.slice(from).trim());
  const share = /^Failure index 1\/R\b/.test(parts[0]);
  const title = share ? "Strength used" : `${parts[0]}${unit && unit !== "-" ? ` (${unit})` : ""}`;
  return { title, sub: parts.slice(1).filter(Boolean).join(" · "), share };
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
        <div><dt>Reaction at {setWords(s.reaction.set)}</dt><dd data-testid="summary-reaction">{printed(Math.abs(s.reaction.value))} {lab.force} ({s.reaction.sense})
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
                  {/* one definition in both columns, each component at its largest magnitude with its sign (ADR-0066); a record written
                      before the reference solver's side had it shows a dash, never a different quantity in the same row */}
                  <td>{f && typeof f.s1_max_abs === "number" ? <><span className="studio-num">{three([f.s1_max_abs, f.s2_max_abs, f.t12_max_abs])}</span> at node {f.s1_max_abs_node}{xyz(f.s1_max_abs_xyz)}</> : DASH}</td>
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
  const reading = fields.summary.gauge_reading;
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
      {a.basis === "gauge" && reading ? (
        <p className="studio-muted" data-testid="answer-gauge-reading">
          The gauge section is read at least {printed(reading.stand_off)} {L} from each tab line, a quarter of the {reading.of}, the same distance on every mesh.
        </p>
      ) : null}
      {a.outside ? (
        <p className="studio-answer-outside" data-testid="answer-outside">
          {a.outside.touches_grip ? "At a grip edge" : a.outside.near_tab ? "Beside a tab line" : `Outside ${a.basisWords}`}, {a.outside.name} is reached earlier, at {printed(a.outside.factor)} × {times}: {who(a.outside)}, {modeWords(a.outside.mode)}, element{" "}
          {a.outside.label.split(".").pop()} {where(a.outside.xy, L)}.
          {a.outside.touches_grip || a.outside.near_tab ? " Stress there grows as the mesh is refined, so it is reported separately." : ""}{" "}
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
  const all = useAllTests(apiBase); // the customer's files, or every file with the development switch on (decision D4)
  if (!downloadable(job, all).length) return null; // files once the run has ended (ADR-0064 amendment 2)
  return (
    <div className="studio-panel" data-testid="downloads">
      <h3>Files</h3>
      <JobFiles apiBase={apiBase} job={job} naming={namingOf(fields)} viewer={false} all={all} />
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

/** The answer in its short form, in the results card's third column (ADR-0134 and its amendment 1, ADR-0099): one bold sentence with the
 * share of the strength used and the ply, one plain line with the loading, its labels, where it is reached earlier apart, then Show where
 * and Details. Every number is the package's (ADR-0051): the share used is its failure index in percent. */
function AnswerShort({ fields, onShow, details, onDetails }: {
  fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void; details: boolean; onDetails: (open: boolean) => void;
}) {
  const a = answerOf(fields);
  const stat = answerStat(fields, printed);
  const s = fields.summary, lab = fields.labels;
  const more = <DetailsToggle open={details} onToggle={onDetails} />;
  if (!a || !stat) {
    return (
      <div className="cv-answer-short" data-testid="answer-short">
        <h3 className="cv-verdict">Reaction {printed(Math.abs(s.reaction.value))} {lab.force}</h3>
        <p className="cv-answer-line">Largest displacement {printed(s.max_displacement.value)} {lab.length}.</p>
        <p className="cv-answer-labels">No failure criterion chosen</p>
        <div className="cv-answer-actions">{more}</div>
      </div>
    );
  }
  const e = a.earliest;
  const control = a.control ? a.control[0].toUpperCase() + a.control.slice(1) : "Applied";
  const line = a.appliedNow
    ? `${control} ${printed(a.appliedNow.applied)} ${a.appliedUnit}: it carries ${printed(Math.abs(a.appliedNow.reaction))} ${a.forceUnit}`
      + (e.reaction !== null ? `; the first ply would ${e.fails ? "have failed" : "fail"} at about ${printed(Math.abs(e.reaction))} ${a.forceUnit}.` : ".")
    : `Every load scaled together; R is the factor on them.`;
  return (
    <div className="cv-answer-short" data-testid="answer-short" data-fails={e.fails}>
      <h3 className="cv-verdict" data-testid="answer-short-verdict">
        {stat.verdict}: {(100 * e.index).toFixed(1)} % of its strength used, in ply {e.ply} ({e.angle}°){e.face ? `, ${e.face} face` : ""}.
      </h3>
      <p className="cv-answer-line">{line}</p>
      <p className="cv-answer-labels">R {stat.factor} · {e.name} · {modeWords(e.mode)} · {a.basisWords}</p>
      {stat.outside ? <p className="cv-answer-note">{stat.outside}</p> : null}
      <div className="cv-answer-actions">
        <button type="button" className="studio-text-button" onClick={() => onShow(e.element, e.ply, e.criterion, e.face)}>Show where</button>
        {more}
      </div>
    </div>
  );
}

/** Where the readout card stands over the model: beside the click that picked the element, on the side with more room; null for a pick
 * from elsewhere (the chat, a table's Show), which stands at the model's top right. */
type ReadoutAt = { left?: number; right?: number; top: number } | null;

export function ResultsView({ fields, explanation, job, apiBase, preview, live = null, updating = false, showFiles = true, onPicked, place = null, proposed = null,
  emphasis = null, view = null, onShown }: {
  fields: Fields; explanation: Explanation | null; job: JobStatus | null; apiBase: string; preview: Preview | null;
  /** a plate's boundary conditions and loads proposed and not applied yet, drawn dashed (ADR-0110) */
  proposed?: ProposedInputs | null;
  /** the tab of the model tree open on the left: its boundary conditions or its loads drawn bolder (ADR-0111) */
  emphasis?: "conditions" | "loads" | null;
  /** told the element clicked on the model, so the assistant can read "here" (ADR-0099) */
  onPicked?: (element: number | null) => void;
  /** a place the assistant answered about: framed on the model once per `at` (ADR-0099) */
  place?: Place | null;
  /** a field the model tree's Results tab asked for, and its ply: shown once per `at` (ADR-0111) */
  view?: FieldView | null;
  /** told the field and ply the model is coloured by, each time they change, so the Results tab shows which (ADR-0111) */
  onShown?: (shown: { id: string; ply: number } | null) => void;
  /** our kernel's live answer (ADR-0086), shown with its seconds until a full run checks it; null for a full run's result */
  live?: { seconds: number; warm: boolean } | null;
  /** a newer live answer is on its way: the numbers shown are the last rows' */
  updating?: boolean;
  /** the job's files at the foot; off in the workspace, whose left column lists them */
  showFiles?: boolean;
}) {
  const canvas = useCanvasSlots(); // in the FEA workspace's layout the parts go to the card, the details and over the model (ADR-0134)
  const [choice, setChoice] = useState<FieldChoice>(() => DEFAULT_CHOICE(fields));
  const [scale, setScale] = useState<number>(() => suggestedScale(fields.mesh.nodes, fields.nodal.magnitude));
  const [deformed, setDeformed] = useState(true);
  const [wireframe, setWireframe] = useState(true);
  const [contours, setContours] = useState(DEFAULT_CONTOURS);
  const [palette, setPalette] = useState<Palette>(DEFAULT_PALETTE);
  const [lit, setLit] = useState(true); // results lit, as the founder's chosen look; off, every colour is the legend's exactly (ADR-0063 amendment 2)
  const [thick, setThick] = useState(false); // the plate drawn thicker than it is, said on screen (ADR-0063 amendment 2)
  const [picked, setPicked] = useState<number | null>(null);
  const [readoutAt, setReadoutAt] = useState<ReadoutAt>(null);
  const pointer = useRef<{ x: number; y: number; t: number } | null>(null);
  const [highlight, setHighlight] = useState<number | null>(() => criticalElement(fields));
  const [answer, setAnswer] = useState<ExplainAnswer | null>(null);
  useEffect(() => {
    // the colours the engineer chose last, in this browser (ADR-0063 amendment 1)
    const kept = remembered(PALETTE_KEY);
    if (isPalette(kept)) setPalette(kept);
  }, []);
  const pickPalette = (next: Palette) => { setPalette(next); remember(PALETTE_KEY, next); };
  useEffect(() => {
    // once our engine has written the explanation, the API's writer (the template, or a model behind a setting) rephrases it (ADR-0052)
    if (!job || !apiBase || !("explanation" in job.outputs)) return;
    let cancelled = false;
    explainJob(apiBase, job.job_id, "result").then((a) => { if (!cancelled) setAnswer(a); })
      .catch((error) => { if (!cancelled && !(error instanceof StudioError && error.status === 409)) setAnswer(null); });
    return () => { cancelled = true; };
  }, [job?.job_id, job?.state, "explanation" in (job?.outputs ?? {}), apiBase]);
  const shownBefore = useRef(fields);
  useEffect(() => {
    // a run's fields read again (its later parts arrived) are the same model: the field, the ply and the place shown stay (ADR-0056 amendment 11)
    const again = sameResults(shownBefore.current, fields);
    shownBefore.current = fields;
    if (again) return;
    setChoice(DEFAULT_CHOICE(fields)); setScale(suggestedScale(fields.mesh.nodes, fields.nodal.magnitude)); setHighlight(criticalElement(fields));
  }, [fields]);
  const options = useMemo(() => fieldOptions(fields), [fields]);
  const option = options.find((o) => o.id === choice.id) ?? options[0];
  const values = useMemo(() => valuesFor(fields, choice), [fields, choice]);
  const colorScale = useMemo(() => scaleFor(values.values, !values.signed, values.range, palette), [values, palette]);
  const field = useMemo<SceneField>(() => ({ by: values.by, values: values.values,
    scale: { min: colorScale.min, max: colorScale.max, stops: colorScale.stops, bands: contours, lit } }), [values, colorScale, contours, lit]);
  // every boundary condition and load drawn and listed in words, as before the run (ADR-0110; audit fea-run-16)
  const inputs = useMemo(() => (preview ? sceneInputs(preview, fields.mesh) : { held: [], loads: [], about: [] }), [preview, fields.mesh]);
  const pending = useMemo(() => (preview ? proposedInputs(preview, proposed, fields.mesh) : null), [preview, proposed, fields.mesh]);
  const readout = picked !== null ? elementReadout(fields, picked, choice, printed) : null;
  const overlay = overlayColors(palette);
  /** An element picked: on the model by a click, beside which its readout stands, or from elsewhere. */
  const pick = (element: number | null, at: ReadoutAt = null) => { setPicked(element); setReadoutAt(element === null ? null : at); };
  const pickOnModel = (element: number | null) => {
    const over = canvas?.places.over;
    const p = pointer.current;
    if (element === null || !over || !p || Date.now() - p.t > 2000) { pick(element); return; }
    const box = over.getBoundingClientRect();
    const x = p.x - box.left, y = p.y - box.top;
    const top = Math.max(8, Math.min(y - 40, box.height - 280));
    pick(element, x > box.width * 0.55 ? { right: Math.max(8, box.width - x + 16), top } : { left: Math.min(x + 16, Math.max(8, box.width - 360)), top });
  };
  const show = (element: number, ply: number, criterion: string, face?: string | null) => {
    setHighlight(element); pick(element);
    const faceIndex = face && fields.mesh.faces ? Math.max(0, fields.mesh.faces.indexOf(face)) : undefined;
    setChoice((c) => ({ ...c, ply, criterion: criterion || c.criterion, face: faceIndex ?? c.face }));
    canvas?.setDetails(false); // the model is under the details: shown, it is seen
  };
  useEffect(() => { onPicked?.(picked); }, [picked, onPicked]);
  useEffect(() => () => onPicked?.(null), [onPicked]); // the results gone, nothing is picked
  useEffect(() => {
    // Esc puts the readout over the model away, before the shell closes anything else (ADR-0134)
    if (!canvas || picked === null) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && !canvas.details) { event.preventDefault(); pick(null); } };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [canvas, picked]); // eslint-disable-line react-hooks/exhaustive-deps
  const viewed = useRef(view?.at ?? 0); // a field asked for before these results were on the page is not asked again
  useEffect(() => {
    if (!view || view.at === viewed.current) return;
    viewed.current = view.at;
    if (!fieldOptions(fields).some((o) => o.id === view.id)) return;
    setChoice((c) => ({ ...c, id: view.id, ply: view.ply ?? c.ply }));
  }, [view?.at]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { onShown?.({ id: choice.id, ply: choice.ply }); }, [choice.id, choice.ply, onShown]);
  useEffect(() => () => onShown?.(null), [onShown]); // the results gone, no field is shown
  const placed = useRef(place?.at ?? 0); // a place asked for before these results were on the page is not shown again
  useEffect(() => {
    // the place of an answer in the conversation: its element outlined and read, its ply (and face) on the model
    if (!place || place.at === placed.current) return;
    placed.current = place.at;
    if (place.element < 0 || place.element >= fields.mesh.element_labels.length) return;
    setHighlight(place.element); pick(place.element);
    const faceIndex = place.face && fields.mesh.faces ? Math.max(0, fields.mesh.faces.indexOf(place.face)) : undefined;
    const id = place.field && fieldOptions(fields).some((o) => o.id === place.field) ? place.field : undefined;
    const criterion = place.criterion && fields.element.failure[place.criterion] ? place.criterion : undefined;
    setChoice((c) => ({ ...c, id: id ?? c.id, ply: place.ply ?? c.ply, face: faceIndex ?? c.face, criterion: criterion ?? c.criterion }));
  }, [place?.at]); // eslint-disable-line react-hooks/exhaustive-deps

  const thickNote = thick ? `thickness ×${THICKNESS_SHOWN}` : "";
  const legend = <Legend scale={colorScale} label={values.label} unit={values.unit} by={values.by} bands={contours} lit={lit} card={canvas !== null} note={thickNote} />;
  const head = legendHead(values.label, values.unit);
  // the field, and the ply, face and criterion it is read at: always in sight
  const primary = (
    <>
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
    </>
  );
  // how it is drawn: under View in the workspace's card, in the row elsewhere
  const drawing = (
    <>
      {!option.nodalOnly && !option.elementOnly && option.id !== "failure_index_ply" ? (
        <label>Values
          <select value={choice.averaged ? "average" : "element"} onChange={(e) => setChoice({ ...choice, averaged: e.target.value === "average" })} aria-label="Shown as">
            <option value="element">Element</option>
            <option value="average">Nodal average</option>
          </select>
        </label>
      ) : null}
      <label>Contours
        <select value={contours} onChange={(e) => setContours(Number(e.target.value))} aria-label="Contours">
          {CONTOURS.map(([bands, word]) => <option key={bands} value={bands}>{word}</option>)}
        </select>
      </label>
      <label>Colours
        <select value={palette} onChange={(e) => { if (isPalette(e.target.value)) pickPalette(e.target.value); }} aria-label="Colours">
          {PALETTES.map(([id, word]) => <option key={id} value={id}>{word}</option>)}
        </select>
      </label>
      <label><input type="checkbox" checked={deformed} onChange={(e) => setDeformed(e.target.checked)} /> Deformed, ×
        <input type="number" value={scale} min={0} step="any" onChange={(e) => setScale(Number(e.target.value) || 0)} aria-label="Deformation scale" className="studio-scale" /></label>
      <label><input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} /> Mesh edges</label>
      <label><input type="checkbox" checked={lit} onChange={(e) => setLit(e.target.checked)} data-testid="lighting" /> Lighting</label>
      <p className="studio-muted cv-view-hint">Off: every colour is exactly the legend&apos;s.</p>
      <label><input type="checkbox" checked={thick} onChange={(e) => setThick(e.target.checked)} data-testid="thickness-shown" /> Thickness ×{THICKNESS_SHOWN}</label>
      <p className="studio-muted cv-view-hint">Draws the plate thicker than it is, to read its sides.</p>
    </>
  );
  const hint = <p className="studio-muted studio-pick-hint">Click an element to read its values. The critical element is outlined in {overlay.criticalWord}.</p>;
  const readoutCard = readout ? (
    <div className={`studio-panel studio-readout${canvas ? " cv-readout" : ""}`} data-testid="readout"
      style={canvas ? (readoutAt ? { left: readoutAt.left, right: readoutAt.right, top: readoutAt.top } : { right: 12, top: 48 }) : undefined}>
      <h3>{readout.title}{highlight === picked ? <span className="studio-badge">critical</span> : null}
        {canvas ? <button type="button" className="icon-button cv-readout-close" onClick={() => pick(null)} title="Close (Esc)" data-testid="readout-close">
          <X size={14} aria-hidden={true} /><span className="sr-only">Close the readout</span></button> : null}</h3>
      <dl>{readout.rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <p className="studio-muted">Click another element to read it, or the background to clear.</p>
      {picked !== null ? <ProbePanel fields={fields} table={probeTable(fields, picked)} /> : null}
    </div>
  ) : null;
  const rest = (
    <>
      <SummaryPanel fields={fields} onShow={show} />
      {/* the user's own Abaqus beside a finished run of the tension coupon, the one the comparison covers (ADR-0094 part 7) */}
      {job && !live && job.state === "done" && apiBase && fields.coupon.kind === "unnotched_tension"
        ? <AbaqusCard apiBase={apiBase} job={job} fields={fields} onShow={show} /> : null}
      <ExplanationPanel explanation={explanation} answer={answer} />
      {job && showFiles ? <Downloads apiBase={apiBase} job={job} fields={fields} /> : null}
    </>
  );
  return (
    <div className="studio-results" data-testid="results" data-source={live ? "live" : "run"} data-updating={updating}>
      {live ? (
        <p className="studio-live-banner" data-testid="live-banner">
          <strong>Preview</strong> ({live.seconds < 10 ? live.seconds.toFixed(1) : Math.round(live.seconds)} s). Run the analysis to verify it and write the report.{updating ? " Updating…" : ""}
        </p>
      ) : updating ? <p className="studio-live-banner" data-testid="live-banner">Updating…</p> : null}
      <div className="studio-scene-block" onPointerDown={(e) => { pointer.current = { x: e.clientX, y: e.clientY, t: Date.now() }; }}>
        <Scene nodes={fields.mesh.nodes} quads={fields.mesh.quads} thickness={(preview?.geometry.thickness ?? 1) * (thick ? THICKNESS_SHOWN : 1)} field={field}
          displacement={deformed ? fields.nodal.displacement : null} scale={scale} held={inputs.held} loads={inputs.loads} about={inputs.about} proposed={pending}
          highlight={highlight} picked={picked} emphasis={emphasis} palette={palette}
          wireframe={wireframe} onPick={canvas ? pickOnModel : (element) => pick(element)} />
        {canvas ? null : legend}
      </div>
      {canvas ? (
        <>
          <Slot name="view">
            {legend}
            {/* one View menu under the legend (ADR-0134 amendment 1): the field and what it is read at, how it is drawn, and the scene's
                own part, how the model is looked at and what is drawn on it */}
            <ViewMenu summary={[head.title, head.sub].filter(Boolean).join(" · ")}>
              <div className="studio-controls cv-controls" data-testid="field-controls">{primary}</div>
              <div className="cv-view-sep" aria-hidden="true" />
              {drawing}
              {hint}
            </ViewMenu>
          </Slot>
          <Slot name="answer">
            <AnswerShort fields={fields} onShow={show} details={canvas.details} onDetails={canvas.setDetails} />
          </Slot>
          <Slot name="over">{readoutCard}</Slot>
          <Slot name="details">
            <AnswerCard fields={fields} onShow={show} />
            {rest}
          </Slot>
        </>
      ) : (
        <>
          <div className="studio-controls" data-testid="field-controls">{primary}{drawing}</div>
          <AnswerCard fields={fields} onShow={show} />
          {readoutCard ?? hint}
          {rest}
        </>
      )}
    </div>
  );
}

const PALETTE_KEY = "anisotropy.studio.colours";
/** How much thicker the plate is drawn when asked: the mockup's (ADR-0063 amendment 2). */
const THICKNESS_SHOWN = 2.4;
