"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { explainJob, isActive, StudioError, type Convergence, type ExplainAnswer, type Explanation, type CalculixBeside, type Extreme, type Fields, type FirstPlyFailure, type JobStatus,
  type Preview } from "@/lib/studio-api";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, PROBE_COLUMNS, probeCsv, probeTable, valuesFor, withField, type FieldChoice, type ProbeTable } from "@/lib/studio-fields";
import { answerOf, BASIS_WORDS, CRITERION_NAMES, extremeRows, modeWords } from "@/lib/studio-answer";
import { customerText, downloadsFor, heldWords, loadWords, setWords, shownSentence } from "@/lib/studio-copy";
import { plyLabel } from "@/lib/laminate-chat";
import { formatNumber } from "@/lib/number-format";
import { useAllTests } from "./project-context";
import { legendGradient, legendTicks, percentChange, printed, scaleFor, settled, type Scale } from "@/lib/studio-colors";
import { suggestedScale } from "@/lib/studio-geometry";
import { AbaqusCard } from "./abaqus-card";
import { JobFiles, namingOf } from "./job-files";
import { Scene } from "./scene";
import type { SceneField, SceneMarker } from "./scene-canvas";
import { TableScroll } from "./table-scroll";

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

const DASH = "–";
/** A number in a table column (style guide, Tables and numbers): the one rule at four figures, its zeros kept so a column reads evenly. */
const num = (v: number | null | undefined): string => (v === null || v === undefined || !Number.isFinite(v) ? DASH : formatNumber(v));
/** A strain as the result tables print it: in microstrain, the unit in the heading (audit fea-run-19). */
const MICRO = 1e6;
const micro = (v: number | null | undefined): number | null => (v === null || v === undefined ? null : v * MICRO);
const xyz = (p: number[] | undefined) => (p && p.length === 3 ? ` (${p.map((v) => printed(v)).join(", ")})` : "");
/** The ply stress components as the fields name them, said with their symbols. */
const COMPONENT: Record<string, string> = { S11: "σ₁ (fibre)", S22: "σ₂ (transverse)", S12: "τ₁₂ (in-plane shear)" };
const criterionName = (criterion: string) => CRITERION_NAMES[criterion] ?? criterion.replace("_", " ");
const elementNumber = (label: string) => label.split(".").pop() ?? label;
/** A ply with its face on a bending coupon: "Ply 4 · 90°, bottom face". */
const plyWithFace = (ply: number, angle: number, face?: string | null) => `${plyLabel(ply, angle)}${face ? `, ${face} face` : ""}`;
/** The other plies that fail at the same factor, written one way in every failure table: ", tied with Ply 5, Ply 6". */
const tiedWith = (others: number[]) => (others.length ? `, tied with ${others.map((t) => `Ply ${t}`).join(", ")}` : "");

/** "Show" on a row, named for what it shows (WCAG 2.4.6, audit fea-run-37): the visible word stays the start of its name. It sits in the
 * column right after the row's sticky heading; a Show the keyboard reaches scrolls its table back to the start, so the heading never covers
 * it (WCAG 2.4.11, audit uiux-fea-run-21). A press of the mouse leaves the table where it is, so the button stays under the pointer. */
function ShowButton({ element, what, onClick }: { element: string; what: string; onClick: () => void }) {
  return (
    <button type="button" className="studio-text-button" onClick={onClick}
      onFocus={(e) => { const box = e.currentTarget.closest(".studio-table-scroll"); if (box && e.currentTarget.matches(":focus-visible")) box.scrollLeft = 0; }}>
      Show<span className="sr-only"> element {element}, {what}, on the model</span>
    </button>
  );
}

type OnShow = (element: number, ply: number, criterion: string, face?: string | null) => void;

export function SummaryPanel({ fields, onShow, pending = false }: { fields: Fields; onShow: OnShow;
  /** the reference solver has not run yet: a live preview, or a run still going */
  pending?: boolean }) {
  const s = fields.summary, lab = fields.labels, cx = s.calculix ?? null;
  const answered = answerOf(fields) !== null;
  return (
    <div className="studio-panel" data-testid="summary">
      <h3>Summary</h3>
      <dl className="studio-summary">
        <div><dt>Applied</dt><dd>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}{s.applied.direction ? `, ${s.applied.direction}` : ""}</dd></div>
        <div><dt>Reaction at {setWords(s.reaction.set)}</dt><dd data-testid="summary-reaction">{printed(Math.abs(s.reaction.value))} {lab.force} ({s.reaction.sense})
          {cx?.reaction ? <span data-testid="summary-reaction-calculix">; reference solver {printed(Math.abs(cx.reaction.calculix))} {lab.force} ({cx.reaction.difference})</span> : null}</dd></div>
        <div><dt>Largest displacement</dt><dd>{printed(s.max_displacement.value)} {lab.length} at node {elementNumber(s.max_displacement.label)}
          {s.max_displacement.axis === "z" ? " (the deflection w)" : ""}</dd></div>
      </dl>
      {s.ply_peaks ? (
        <>
          <ValidationTable s={s} cx={cx} lab={lab} pending={pending} />
          <PeaksTable s={s} cx={cx} lab={lab} criterion={s.earliest ?? ""} onShow={onShow} />
        </>
      ) : <OlderPeaks fields={fields} onShow={onShow} />}
      {s.convergence ? <ConvergenceTable study={s.convergence} lab={lab} /> : null}
      <details className="studio-fpf-details" data-testid="fpf-details" open={!answered}>
      <summary>First-ply failure, all criteria</summary>
      <h4>Whole model</h4>
      {Object.keys(s.fpf).length === 0 ? <p className="studio-muted">No failure criterion selected.</p> : (
        <FailureTable fpf={s.fpf} earliest={s.earliest} testId="fpf-table" factorPrefix="fpf-factor" label="First-ply failure, whole model" onShow={onShow} />
      )}
      {/* the R rule in one sentence, as under the answer; the caveat once on the page: here only when no answer card says it (audit fea-run-23) */}
      <p className="studio-muted">R is the load factor at first-ply failure; R ≤ 1 fails at the applied loading.
        {answered ? "" : " First-ply failure is the onset of damage, not ultimate strength."}
        {s.earliest && s.fpf[s.earliest]?.touches_grip ? " The critical element is at a grip's clamped edge, where stress does not converge." : ""}</p>
      {s.fpf_gauge && Object.keys(s.fpf_gauge).length ? (
        <>
          <h4>Gauge section</h4>
          <FailureTable fpf={s.fpf_gauge} earliest={s.earliest_gauge ?? null} testId="fpf-gauge-table" factorPrefix="fpf-gauge-factor" label="First-ply failure, gauge section"
            onShow={onShow} />
          <p className="studio-muted">Away from the grips: the value to compare with a test.</p>
        </>
      ) : null}
      </details>
      {s.test_method ? <TestMethodCard tm={s.test_method} cx={cx?.test_method ?? null} /> : null}
    </div>
  );
}

/** The quantities the coupon's test standard reduces a test to (ADR-0072), as the package wrote them: the area, the stress, the strain over the
 * measurement, the modulus beside laminate theory and the reference solver, Poisson's ratio, the net section of an open hole, and the first-ply
 * failure stress. The standard's derived quantities at three significant figures, as the standards report them (ADR-0091 amendment 3); the
 * load the stress is under at the page's four, as the Summary prints it. Each standard's own words: D3039's chord modulus over the gross area,
 * D638's modulus of elasticity over the narrow section (ADR-0075). */
function TestMethodCard({ tm, cx }: { tm: NonNullable<Fields["summary"]["test_method"]>; cx: NonNullable<CalculixBeside["test_method"]> | null }) {
  const u = tm.units;
  const three = (v: number) => Number(v.toPrecision(3)).toString();
  const capital = (words: string) => words.charAt(0).toUpperCase() + words.slice(1);
  const area = tm.reduction?.area ?? "gross area";
  const modulus = tm.reduction?.modulus ?? "chord modulus";
  const theory = tm.laminate_theory.isotropic ? "the material's own" : "laminate theory";
  const rows: [string, string][] = [
    [capital(area), `${three(tm.area)} ${u.area} (${three(tm.width)} × ${three(tm.thickness)} ${u.length})`],
    ["Stress P/A", `${three(Math.abs(tm.stress))} ${u.stress} under ${printed(Math.abs(tm.force))} ${u.force}`],
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
      <p className="studio-muted">The standard&apos;s formulas applied to the solution, to three significant figures as the standard reports them.
        {tm.note_b ? " The first ply fails below 6000 microstrain, so the chord range follows D3039 Table 3, note B." : ""}</p>
    </div>
  );
}

/** A triple's three cells, the noise beside its real values printed as 0, each marked ✕ where its source disagrees (one number per cell,
 * audit uiux-fea-screens-27). */
function tripleCells(values: (number | null | undefined)[] | undefined, marks?: (boolean | null)[], scale = 1, key = ""): ReactNode[] {
  const shown = values ? settled(values) : [undefined, undefined, undefined];
  return [0, 1, 2].map((i) => {
    const v = shown[i];
    return <td key={`${key}${i}`}>{num(v === null || v === undefined ? null : v * scale)}{marks && marks[i] === false ? " ✕" : ""}</td>;
  });
}
/** A triple in one cell, for the convergence study's columns of meshes: the style guide's one exception to one number per cell, since there
 *  the columns are meshes, not sources or components. */
const three = (v: (number | null | undefined)[] | undefined, scale = 1) =>
  v ? settled(v).map((x) => num(x === null || x === undefined ? null : x * scale)).join(" / ") : DASH;

/** The validation (ADR-0066): one row per quantity, one column per source, every cell the same quantity read the same way, one number per
 * cell (audit uiux-fea-screens-27): the reaction and the gauge-centre strain, then every ply's σ₁ σ₂ τ₁₂ in its fibre axes at the gauge-centre
 * element, grouped by source. The FEA column is the package's own: the reference solver's record when it ran, else the coupon's own mesh in
 * the convergence study (audit fea-run-J2-1), so the product's values never vanish with the reference block. */
function ValidationTable({ s, cx, lab, pending }: { s: Fields["summary"]; cx: CalculixBeside | null; lab: Fields["labels"]; pending: boolean }) {
  const clt = s.clt ?? null;
  const base = s.convergence?.studied ? s.convergence.meshes.find((m) => m.factor === 1) ?? null : null;
  const fem = cx ? { strain: cx.gauge_strain?.ours, plies: cx.gauge.map((g) => g.ours), element: cx.gauge_element ? elementNumber(cx.gauge_element) : null }
    : base ? { strain: base.gauge_strain, plies: base.plies.map((p) => p.stress_12), element: String(base.gauge_element) } : null;
  const plies = Math.max(clt?.plies.length ?? 0, cx?.gauge.length ?? 0, base?.plies.length ?? 0);
  if (!clt && !cx && !fem) return null;
  const angleOf = (k: number) => clt?.plies[k]?.angle ?? base?.plies[k]?.angle ?? s.ply_peaks?.[k]?.angle;
  const sources = fem ? ["Laminate theory", "FEA", "Reference solver"] : ["Laminate theory"];
  const STRAIN = ["εx", "εy", "γxy"];
  // each region named for the table it holds: without FEA values the first holds the gauge strain alone, by laminate theory
  const title = fem ? "Verification" : "Laminate theory at the gauge centre";
  return (
    <>
      <h4>{title}</h4>
      <TableScroll label={fem ? "Verification: the reaction and the gauge strain" : `${title}: the gauge strain`}>
        <table className="studio-table studio-table-num studio-table-sticky" data-testid="validation-table">
          <thead>
            <tr><th scope="col">Quantity</th>{sources.map((source) => <th scope="col" key={source}>{source}</th>)}</tr>
          </thead>
          <tbody>
            {fem ? (
              <tr data-row="reaction"><th scope="row">Reaction ({lab.force})</th><td>{DASH}</td><td>{num(Math.abs(s.reaction.value))}</td>
                <td>{cx?.reaction ? `${num(Math.abs(cx.reaction.calculix))}${cx.reaction.agrees === false ? " ✕" : ""}` : DASH}</td></tr>
            ) : null}
            {STRAIN.map((symbol, i) => (
              <tr key={symbol} data-row="strain" data-component={i}><th scope="row">Gauge {symbol} (microstrain)</th>
                <td>{num(micro(clt ? settled(clt.strain)[i] : null))}</td>
                {fem ? <><td>{num(micro(fem.strain ? settled(fem.strain)[i] : null))}</td>
                  <td>{num(micro(cx?.gauge_strain ? settled(cx.gauge_strain.calculix)[i] : null))}{cx?.gauge_strain?.agrees[i] === false ? " ✕" : ""}</td></> : null}
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
      <TableScroll label={fem ? `Verification: ply stresses at the gauge centre (${lab.stress})` : `${title}: ply stresses (${lab.stress})`}>
        <table className="studio-table studio-table-num studio-table-sticky" data-testid="validation-plies">
          <thead>
            <tr><th scope="col" rowSpan={2}>Ply</th>
              {sources.map((source) => <th key={source} scope="colgroup" colSpan={3} className="studio-table-group-head">{source} ({lab.stress})</th>)}</tr>
            <tr className="studio-table-subhead">{sources.flatMap((source) => ["σ₁", "σ₂", "τ₁₂"].map((h) => <th key={`${source}-${h}`} scope="col">{h}</th>))}</tr>
          </thead>
          <tbody>
            {Array.from({ length: plies }, (_, k) => {
              const angle = angleOf(k);
              return (
                <tr key={k} data-ply={k + 1}><th scope="row">{angle !== undefined ? plyLabel(k + 1, angle) : `Ply ${k + 1}`}</th>
                  {tripleCells(clt?.plies[k]?.stress_12, undefined, 1, "clt")}
                  {fem ? <>{tripleCells(fem.plies[k], undefined, 1, "fem")}{tripleCells(cx?.gauge[k]?.calculix, cx?.gauge[k]?.agrees, 1, "ref")}</> : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </TableScroll>
      <p className="studio-muted">Fibre axes; plies from the bottom face; angles from the load axis; x across the width, y along the load.
        {clt ? ` Laminate theory takes the FEA reaction as its load: Ny = reaction / width = ${printed(clt.Ny)} ${lab.force}/${lab.length}.` : ""}
        {fem?.element ? ` FEA at the centroid of element ${fem.element}${cx ? "; reference solver at its integration-point mean" : ""}.` : ""}
        {cx ? ` ✕ marks a value outside ${printed(100 * cx.tolerance)} %.` : pending ? " The reference solver runs with the full analysis." : fem ? " No reference solver values for this run." : ""}</p>
    </>
  );
}

/** The stress concentration at the clamped edge (ADR-0066): every ply's peak in every column, apart from the validation table because the
 *  free-edge corner where a gripped tab ends is singular: each number grows as the mesh is refined and depends on where it is read. */
function PeaksTable({ s, cx, lab, criterion, onShow }: { s: Fields["summary"]; cx: CalculixBeside | null; lab: Fields["labels"]; criterion: string; onShow: OnShow }) {
  const peaks = s.ply_peaks ?? [];
  const frdPlies = cx?.frd?.plies ?? null;
  const clamped = peaks.some((p) => p.S11.touches_grip);
  const title = clamped ? "Peak stresses at the grips" : "Peak stresses";
  return (
    <details className="studio-details" data-testid="peaks">
      <summary><h4>{title} (not converged)</h4></summary>
      <TableScroll label={title}>
        <table className="studio-table studio-table-num studio-table-sticky" data-testid="peaks-table">
          <thead>
            <tr><th scope="col" rowSpan={2}>Ply</th><th scope="col" rowSpan={2}><span className="sr-only">Show</span></th>
              <th scope="colgroup" colSpan={3} className="studio-table-group-head">FEA, element centroid ({lab.stress})</th>
              <th scope="col" rowSpan={2} className="studio-text-cell">Element</th>
              <th scope="colgroup" colSpan={3} className="studio-table-group-head">Reference solver, corner node ({lab.stress})</th>
              <th scope="col" rowSpan={2} className="studio-text-cell">Node</th></tr>
            <tr className="studio-table-subhead">{["FEA", "Reference"].flatMap((who) => ["σ₁", "σ₂", "τ₁₂"].map((h) => <th key={`${who}-${h}`} scope="col">{h}</th>))}</tr>
          </thead>
          <tbody>
            {peaks.map((p, k) => {
              const f = frdPlies?.[k];
              const element = elementNumber(p.S11.label);
              return (
                <tr key={p.ply} data-ply={p.ply}>
                  <th scope="row">{plyLabel(p.ply, p.angle)}</th>
                  <td className="studio-text-cell"><ShowButton element={element} what={`the largest σ₁ of ${plyLabel(p.ply, p.angle)}`} onClick={() => onShow(p.S11.element, p.ply, criterion, p.S11.face)} /></td>
                  {tripleCells([p.S11.value, p.S22.value, p.S12.value], undefined, 1, "fea")}
                  <td className="studio-text-cell">{element}{p.S11.face ? `, ${p.S11.face} face` : ""}{p.S11.touches_grip ? ", grip edge" : ""}</td>
                  {/* one definition in both columns, each component at its largest magnitude with its sign (ADR-0066); a record written
                      before the reference solver's side had it shows dashes, never a different quantity in the same row */}
                  {f && typeof f.s1_max_abs === "number" ? tripleCells([f.s1_max_abs, f.s2_max_abs ?? null, f.t12_max_abs ?? null], undefined, 1, "ref")
                    : [0, 1, 2].map((i) => <td key={`ref${i}`}>{DASH}</td>)}
                  <td className="studio-text-cell">{f && typeof f.s1_max_abs === "number" ? `${f.s1_max_abs_node}${xyz(f.s1_max_abs_xyz)}` : DASH}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </TableScroll>
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
 *  (its last change under the study's threshold). The peaks and the failure factors keep ADR-0066's label: not validation values. Each group
 *  of rows is a row group with its own heading (audit uiux-fea-run-38). */
function ConvergenceTable({ study, lab }: { study: Convergence; lab: Fields["labels"] }) {
  if (!study.studied) {
    const reason = customerText(study.reason);
    return <p className="studio-muted" data-testid="convergence-not-studied">Mesh convergence: not studied{reason ? `, ${reason}` : ""}.</p>;
  }
  const meshes = study.meshes, changes = study.changes!, settledGroups = study.settled!, below = study.settled_below;
  const last = meshes.length - 1;
  const span = meshes.length + 2;
  const verdict = (change: number | null) => (change === null ? DASH : Math.abs(change) < below ? `${percentChange(change)}, settled` : `${percentChange(change)}, still moving`);
  const cells = (values: (number | string)[], steps: (number | null)[]) => (
    <>
      {values.map((v, i) => <td key={i}>{typeof v === "number" ? num(v) : v}{i > 0 && steps[i] !== null ? <span className="studio-muted"> ({percentChange(steps[i])})</span> : null}</td>)}
      <td>{verdict(steps[last])}</td>
    </>
  );
  const tripleRow = (values: number[][], steps: ((number | null)[] | null)[], scale = 1) =>
    cells(values.map((v) => three(v, scale)), steps.map((c) => worst(c)));
  const gaugeElements = Array.from(new Set(meshes.map((m) => m.gauge_element)));
  const settledNames = Object.entries({ reaction: "the reaction", gauge_strain: "the gauge strain", plies: "the gauge ply stresses" })
    .filter(([key]) => settledGroups[key as keyof typeof settledGroups]).map(([, name]) => name);
  const movingNames = Object.entries({ peaks: "the grip peaks", fpf: "the whole-model R", fpf_gauge: "the gauge-section R" })
    .filter(([key]) => !settledGroups[key as keyof typeof settledGroups]).map(([, name]) => name);
  const group = (title: string) => <tr className="studio-table-group"><th scope="rowgroup" colSpan={span}>{title}</th></tr>;
  return (
    <details className="studio-details" data-testid="convergence">
      <summary><h4>Mesh convergence</h4></summary>
      <TableScroll label="Mesh convergence">
        <table className="studio-table studio-table-num studio-table-sticky" data-testid="convergence-table">
          <thead>
            <tr><th scope="col">Quantity</th>{meshes.map((m) => <th key={m.factor} scope="col">{m.factor}× mesh<br /><span className="studio-muted">{m.elements.toLocaleString("en-US")} elements</span></th>)}
              <th scope="col">Last step<br /><span className="studio-muted">settled &lt; {printed(100 * below)} %</span></th></tr>
          </thead>
          <tbody>
            <tr data-row="reaction"><th scope="row">Reaction ({lab.force})</th>{cells(meshes.map((m) => m.reaction), changes.reaction)}</tr>
            <tr data-row="strain"><th scope="row">Gauge εx / εy / γxy (microstrain)</th>{tripleRow(meshes.map((m) => m.gauge_strain), changes.gauge_strain, MICRO)}</tr>
          </tbody>
          <tbody>
            {group(`Gauge ply stress σ₁ / σ₂ / τ₁₂ (${lab.stress})`)}
            {meshes[0].plies.map((p, k) => (
              <tr key={`gauge-${p.ply}`} data-ply={p.ply} data-row="gauge">
                <th scope="row">{plyLabel(p.ply, p.angle)}</th>
                {tripleRow(meshes.map((m) => m.plies[k].stress_12), changes.plies[k].stress_12)}
              </tr>
            ))}
          </tbody>
          <tbody>
            {group(`Largest |σ₁| (${lab.stress})`)}
            {meshes[0].peaks.map((p, k) => (
              <tr key={`peak-${p.ply}`} data-ply={p.ply} data-row="peak">
                <th scope="row">{plyLabel(p.ply, p.angle)}{p.touches_grip ? ", grip" : ""}</th>
                {cells(meshes.map((m) => m.peaks[k].s1), changes.peaks[k].s1)}
              </tr>
            ))}
          </tbody>
          {Object.keys(changes.fpf).length || Object.keys(changes.fpf_gauge).length ? (
            <tbody>
              {group("First-ply failure R")}
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
          ) : null}
        </table>
      </TableScroll>
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
function OlderPeaks({ fields, onShow }: { fields: Fields; onShow: OnShow }) {
  const s = fields.summary, lab = fields.labels, cx = s.calculix ?? null;
  const fibre = s.max_ply.S11;
  const others = Object.entries(s.max_ply).filter(([name]) => name !== "mises" && name !== "S11");  // the ply von Mises row is gone: a viewer's von Mises is another quantity (ADR-0030 amendment 6)
  const place = (m: Extreme) => <>in {plyWithFace(m.ply, m.angle, m.face)}, at element {elementNumber(m.label)}</>;
  return (
    <>
      {cx && cx.gauge.length ? (
        <>
          <h4>Verification, gauge section</h4>
          <TableScroll label="Verification, gauge section">
            <table className="studio-table studio-table-num studio-table-sticky" data-testid="gauge-table">
              <thead>
                <tr><th scope="col" rowSpan={2}>Ply</th>
                  {["FEA", "Reference solver"].map((source) => <th key={source} scope="colgroup" colSpan={3} className="studio-table-group-head">{source} ({lab.stress})</th>)}</tr>
                <tr className="studio-table-subhead">{["FEA", "Reference"].flatMap((who) => ["σ₁", "σ₂", "τ₁₂"].map((h) => <th key={`${who}-${h}`} scope="col">{h}</th>))}</tr>
              </thead>
              <tbody>
                {cx.gauge.map((g) => (
                  <tr key={g.ply} data-ply={g.ply}><th scope="row">{plyLabel(g.ply, fields.mesh.angles[g.ply - 1])}</th>
                    {tripleCells(g.ours, undefined, 1, "fem")}{tripleCells(g.calculix, g.agrees, 1, "ref")}
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
          <p className="studio-muted">FEA and reference solver{cx.gauge_element ? ` at element ${elementNumber(cx.gauge_element)}` : ""}. ✕ marks a value outside {printed(100 * cx.tolerance)} %.</p>
        </>
      ) : null}
      <h4>Peaks at the grips</h4>
      <dl className="studio-summary">
        {fibre ? (
          <div data-testid="summary-fibre-peak"><dt>Largest σ₁ along the fibres</dt>
            <dd>{printed(fibre.value)} {lab.stress} {place(fibre)}
              <ShowButton element={elementNumber(fibre.label)} what="the largest σ₁" onClick={() => onShow(fibre.element, fibre.ply, s.earliest ?? "", fibre.face)} />
              {cx?.frd ? <span data-testid="summary-fibre-calculix">; reference solver σyy = {printed(cx.frd.syy_max)} {lab.stress} at corner node {cx.frd.syy_max_node}{xyz(cx.frd.syy_max_xyz as number[] | undefined)}</span> : null}</dd></div>
        ) : null}
        {others.map(([name, m]) => (
          <div key={name}><dt>Largest {COMPONENT[name] ?? name}</dt>
            <dd>{printed(m.value)} {lab.stress} {place(m)}
              <ShowButton element={elementNumber(m.label)} what={`the largest ${COMPONENT[name] ?? name}`} onClick={() => onShow(m.element, m.ply, s.earliest ?? "", m.face)} /></dd></div>
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

const coordinates = (xy: number[]) => xy.map((v) => num(v)).join(", ");

/** The answer to "does it fail, at what load, where" (ADR-0085), as the package wrote it: per criterion in the gauge section (the whole model for a
 * coupon without one), fails or holds at the applied loading, the factor R, the loading at first-ply failure, the ply, mode and position; the
 * earlier failure at a clamped edge apart; the largest ply stresses with their sign. Every number is the package's (ADR-0051). One headline,
 * the mode and the coordinates left to the table, which gives each one column and its unit in the heading (audit fea-run-25, fea-run-26). */
export function AnswerCard({ fields, onShow }: { fields: Fields; onShow: OnShow }) {
  const a = answerOf(fields);
  if (!a) return null;
  const L = fields.labels.length ?? "";
  const e = a.earliest;
  const byDisplacement = a.control !== "force";
  const times = a.everyLoad ? "every applied load" : "the applied loading";
  // the load at first-ply failure in the headline: the force the grip carries then, where it is (the mode and the place are the table's)
  const force = byDisplacement ? (e.reaction !== null ? `${printed(Math.abs(e.reaction))} ${a.forceUnit} at ${a.reactionSet}` : null)
    : e.applied !== null ? `${printed(Math.abs(e.applied))} ${a.appliedUnit}` : null;
  const extremes = fields.summary.ply_extremes;
  const appliedHead = `${byDisplacement ? "Displacement" : "Force"} (${a.appliedUnit})`;
  return (
    <div className="studio-panel studio-answer" data-testid="answer" data-basis={a.basis} data-fails={e.fails}>
      <h3>First-ply failure <span className="studio-badge">{a.basisWords}</span></h3>
      <p className="studio-answer-headline" data-testid="answer-headline">
        <strong>{e.fails ? "Fails" : "Holds"} at the applied loading.</strong>{" "}
        {e.name}: the first ply {e.fails ? `fails at ${printed(e.factor)} of ${times}` : `would fail at ${printed(e.factor)} × ${times}`}{force ? `, ${force}` : ""},
        in <span className="studio-nowrap">{plyWithFace(e.ply, e.angle, e.face)}</span>, element {elementNumber(e.label)}.
      </p>
      <TableScroll label={`First-ply failure, ${a.basisWords}`}>
        <table className="studio-table studio-table-sticky" data-testid="answer-table">
          <thead>
            <tr><th scope="col" rowSpan={2}>Criterion</th><th scope="col" rowSpan={2}><span className="sr-only">Show</span></th><th scope="col" rowSpan={2}>Verdict</th>
              <th scope="col" rowSpan={2} className="studio-num-head">R</th>
              <th scope="colgroup" colSpan={byDisplacement ? 2 : 1} className="studio-table-group-head">At first-ply failure</th>
              <th scope="col" rowSpan={2}>Ply</th><th scope="col" rowSpan={2}>Mode</th><th scope="col" rowSpan={2} className="studio-num-head">Element</th>
              <th scope="col" rowSpan={2} className="studio-num-head">x, y ({L})</th></tr>
            <tr className="studio-table-subhead"><th scope="col" className="studio-num-head">{appliedHead}</th>
              {byDisplacement ? <th scope="col" className="studio-num-head">Reaction ({a.forceUnit})</th> : null}</tr>
          </thead>
          <tbody>
            {a.rows.map((r) => (
              <tr key={r.criterion} data-criterion={r.criterion} data-fails={r.fails} className={r.earliest ? "studio-earliest" : undefined}>
                <th scope="row">{r.name}{r.earliest ? " (governs)" : ""}</th>
                <td><ShowButton element={elementNumber(r.label)} what={`first-ply failure by ${r.name}`} onClick={() => onShow(r.element, r.ply, r.criterion, r.face)} /></td>
                <td data-testid={`answer-verdict-${r.criterion}`}><span className={`studio-badge studio-badge-${r.fails ? "fail" : "pass"}`}>{r.fails ? "fails" : "holds"}</span></td>
                <td className="studio-num" data-testid={`answer-factor-${r.criterion}`}>{num(r.factor)}</td>
                <td className="studio-num" data-testid={`answer-loading-${r.criterion}`}>{r.applied === null ? DASH : num(Math.abs(r.applied))}</td>
                {byDisplacement ? <td className="studio-num">{r.reaction === null ? DASH : num(Math.abs(r.reaction))}</td> : null}
                <td className="studio-nowrap">{plyWithFace(r.ply, r.angle, r.face)}{tiedWith(r.tied)}</td>
                <td>{modeWords(r.mode)}</td>
                <td className="studio-num">{elementNumber(r.label)}</td>
                <td className="studio-num">{coordinates(r.xy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
      <p className="studio-muted">R is the load factor at first-ply failure; R ≤ 1 fails at the applied loading. First-ply failure is the onset of damage, not ultimate strength.</p>
      {a.outside ? (
        <p className="studio-answer-outside" data-testid="answer-outside">
          {a.outside.touches_grip ? "At a grip edge" : `Outside ${a.basisWords}`}, {a.outside.name} is reached earlier, at {printed(a.outside.factor)} × {times}: {plyWithFace(a.outside.ply, a.outside.angle, a.outside.face)},{" "}
          {modeWords(a.outside.mode)}, element {elementNumber(a.outside.label)}.
          {a.outside.touches_grip ? " Stress there grows as the mesh is refined, so it is reported separately." : ""}{" "}
          <ShowButton element={elementNumber(a.outside.label)} what={a.outside.touches_grip ? "the earlier failure at a grip edge" : "the earlier failure"}
            onClick={() => onShow(a.outside!.element, a.outside!.ply, a.outside!.criterion, a.outside!.face)} />
        </p>
      ) : null}
      {extremes ? <ExtremesTable extremes={extremes} basis={BASIS_WORDS[extremes.basis]} unit={fields.labels.stress ?? ""} lengthUnit={L} criterion={e.criterion} onShow={onShow} /> : null}
    </div>
  );
}

const EXTREME_HEADS = ["σ₁ tension", "σ₁ compression", "σ₂ tension", "σ₂ compression", "τ₁₂ largest"];

function ExtremesTable({ extremes, basis, unit, lengthUnit, criterion, onShow }: {
  extremes: NonNullable<Fields["summary"]["ply_extremes"]>; basis: string; unit: string; lengthUnit: string; criterion: string; onShow: OnShow;
}) {
  const rows = extremeRows(extremes.overall);
  return (
    <>
      <h4>Largest ply stresses, {basis}</h4>
      <TableScroll label={`Largest ply stresses, ${basis}`}>
        <table className="studio-table studio-table-sticky" data-testid="answer-extremes">
          <thead><tr><th scope="col">Stress</th><th scope="col"><span className="sr-only">Show</span></th><th scope="col" className="studio-num-head">Value ({unit})</th>
            <th scope="col">Ply</th><th scope="col" className="studio-num-head">Element</th><th scope="col" className="studio-num-head">x, y ({lengthUnit})</th></tr></thead>
          <tbody>
            {rows.map(({ key, words, extreme }) => (
              <tr key={key} data-extreme={key}>
                <th scope="row">{words}</th>
                <td><ShowButton element={elementNumber(extreme.label)} what={words} onClick={() => onShow(extreme.element, extreme.ply ?? 1, criterion, extreme.face)} /></td>
                <td className="studio-num">{num(extreme.value)}</td>
                <td className="studio-nowrap">{extreme.ply !== undefined && extreme.angle !== undefined ? plyWithFace(extreme.ply, extreme.angle, extreme.face) : DASH}</td>
                <td className="studio-num">{elementNumber(extreme.label)}</td>
                <td className="studio-num">{coordinates(extreme.xy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
      <details className="studio-answer-plies">
        <summary>By ply</summary>
        <TableScroll label={`Largest ply stresses by ply, ${basis}`}>
          <table className="studio-table studio-table-num studio-table-sticky" data-testid="answer-extremes-plies">
            {/* Ply spans both heading rows, so the sticky column holds no empty units cell for the "MPa" labels to slide under */}
            <thead><tr><th scope="col" rowSpan={2}>Ply</th>{EXTREME_HEADS.map((h) => <th key={h} scope="col">{h}</th>)}</tr>
              <tr className="studio-table-units">{EXTREME_HEADS.map((h) => <th key={h} scope="col">{unit}</th>)}</tr></thead>
            <tbody>
              {extremes.plies.map((p) => (
                <tr key={p.ply}><th scope="row">{plyLabel(p.ply, p.angle)}</th>
                  {[p.S11.tension, p.S11.compression, p.S22.tension, p.S22.compression, p.S12.largest].map((x, i) => <td key={i}>{x ? num(x.value) : "–"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      </details>
      <p className="studio-muted">Fibre-axis stresses at element centroids; tension and compression listed separately.</p>
    </>
  );
}

function FailureTable({ fpf, earliest, testId, factorPrefix, label, onShow }: {
  fpf: Record<string, FirstPlyFailure>; earliest: string | null; testId: string; factorPrefix: string; label: string; onShow: OnShow;
}) {
  return (
    <TableScroll label={label}>
      <table className="studio-table studio-table-sticky" data-testid={testId}>
        <thead><tr><th scope="col">Criterion</th><th scope="col"><span className="sr-only">Show</span></th><th scope="col" className="studio-num-head">R</th>
          <th scope="col" className="studio-num-head">1/R</th><th scope="col">Ply</th><th scope="col">Mode</th><th scope="col" className="studio-num-head">Element</th><th scope="col">Where</th></tr></thead>
        <tbody>
          {Object.entries(fpf).sort(([, a], [, b]) => a.factor - b.factor).map(([criterion, f]) => (
            <tr key={criterion} data-criterion={criterion} className={criterion === earliest ? "studio-earliest" : undefined}>
              <th scope="row">{criterionName(criterion)}{criterion === earliest ? " (governs)" : ""}</th>
              <td><ShowButton element={elementNumber(f.label)} what={`first-ply failure by ${criterionName(criterion)}`} onClick={() => onShow(f.element, f.ply, criterion, f.face)} /></td>
              <td className="studio-num" data-testid={`${factorPrefix}-${criterion}`}>{num(f.factor)}</td><td className="studio-num">{num(f.index)}</td>
              <td className="studio-nowrap">{plyWithFace(f.ply, f.angle, f.face)}{tiedWith(f.tied_plies.filter((t) => t !== f.ply))}</td>
              <td>{modeWords(f.mode)}</td><td className="studio-num">{elementNumber(f.label)}</td><td>{f.place}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
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
  if (!downloadsFor(all).some(([key]) => key in job.outputs)) return null;
  return (
    <div className="studio-panel" data-testid="downloads">
      <h3>Files</h3>
      <JobFiles apiBase={apiBase} job={job} naming={namingOf(fields)} viewer={false} all={all} />
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
 * `PROBE_COLUMNS` (σ₁ σ₂ τ₁₂, von Mises, Tresca, the three principal stresses, the pressure, ε₁ ε₂ γ₁₂); a single column's heading on one
 * line with its unit (audit fea-run-25). */
const PROBE_GROUPS: { title: string; span: number; heads: string[] }[] = [
  { title: "Stress, fibre axes", span: 3, heads: ["σ₁", "σ₂", "τ₁₂"] },
  { title: "von Mises", span: 1, heads: [""] },
  { title: "Tresca", span: 1, heads: [""] },
  { title: "Principal stress", span: 3, heads: ["max", "mid", "min"] },
  { title: "Pressure", span: 1, heads: [""] },
  { title: "Strain, fibre axes", span: 3, heads: ["ε₁", "ε₂", "γ₁₂"] },
];

/** Every ply of the picked element (ADR-0066 amendment 2): the element's number, the centroid, no averaging, each ply in its fibre axes;
 * with a CSV of the same numbers. */
function ProbePanel({ fields, table }: { fields: Fields; table: ProbeTable }) {
  const lab = fields.labels;
  const faces = table.rows.some((r) => r.face);
  const href = `data:text/csv;charset=utf-8,${encodeURIComponent(probeCsv(fields, table))}`;
  const title = `Ply results at element ${table.label}`;
  return (
    <details className="studio-probe" data-testid="probe" open>
      <summary>{title}</summary>
      <p className="studio-muted">{table.note}</p>
      <p className="studio-probe-actions"><a className="studio-text-button" href={href} download={`probe-element-${table.label}.csv`} data-testid="probe-csv">Export CSV</a></p>
      <TableScroll label={title}>
        <table className="studio-table studio-table-num studio-table-sticky studio-table-compact" data-testid="probe-table">
          <thead>
            <tr>
              <th scope="col" rowSpan={2}>Ply</th>{faces ? <th scope="col" rowSpan={2}>Face</th> : null}
              {PROBE_GROUPS.map((g) => (g.span === 1
                ? <th key={g.title} scope="col" rowSpan={2}>{g.title} ({lab.stress})</th>
                : <th key={g.title} scope="colgroup" colSpan={g.span} className="studio-table-group-head">{g.title}{g.title.startsWith("Strain") ? "" : ` (${lab.stress})`}</th>))}
            </tr>
            <tr className="studio-table-subhead">{PROBE_GROUPS.filter((g) => g.span > 1).flatMap((g) => g.heads.map((h) => <th key={`${g.title}-${h}`} scope="col">{h}</th>))}</tr>
          </thead>
          <tbody>{table.rows.map((r) => (
            <tr key={`${r.ply}-${r.face ?? ""}`} data-ply={r.ply}><th scope="row">{plyLabel(r.ply, r.angle)}</th>{faces ? <td className="studio-text-cell">{r.face}</td> : null}
              {r.values.map((v, i) => <td key={PROBE_COLUMNS[i]}>{num(v)}</td>)}</tr>
          ))}</tbody>
        </table>
      </TableScroll>
      <p className="studio-muted">von Mises, Tresca and the principal stresses are for comparison, not composite failure criteria.</p>
    </details>
  );
}

/** An element's number as the tables print it, to its index in the mesh; null when the model has no such element. */
const elementIndex = (fields: Fields, number: string): number | null => {
  const at = fields.mesh.element_labels.findIndex((label) => elementNumber(label) === number.trim());
  return at >= 0 ? at : null;
};

export function ResultsView({ fields, explanation, job, apiBase, preview, live = null, updating = false, showFiles = true, viewerLink = null }: {
  fields: Fields; explanation: Explanation | null; job: JobStatus | null; apiBase: string; preview: Preview | null;
  /** our kernel's live answer (ADR-0086), shown with its seconds until a full run checks it; null for a full run's result */
  live?: { seconds: number; warm: boolean } | null;
  /** a newer live answer is on its way: the numbers shown are the last rows' */
  updating?: boolean;
  /** the job's files at the foot; off in the workspace, whose left column lists them */
  showFiles?: boolean;
  /** the address of this run's results in a window of their own, offered in the model's heading */
  viewerLink?: string | null;
}) {
  const [choice, setChoice] = useState<FieldChoice>(() => DEFAULT_CHOICE(fields));
  const [scale, setScale] = useState<number>(() => suggestedScale(fields.mesh.nodes, fields.nodal.magnitude));
  const [deformed, setDeformed] = useState(true);
  const [wireframe, setWireframe] = useState(true);
  const [contours, setContours] = useState(DEFAULT_CONTOURS);
  const [picked, setPicked] = useState<number | null>(null);
  const [typed, setTyped] = useState("");
  const [typedError, setTypedError] = useState("");
  const [fit, setFit] = useState(0);
  const [shown, setShown] = useState(0); // counts the table's Show presses: each brings the model into view and the readout into focus
  const sceneBlock = useRef<HTMLDivElement>(null);
  const readoutHeading = useRef<HTMLHeadingElement>(null);
  // the critical element stays the answer's: Show and a click pick an element, they never move the critical outline (audit uiux-fea-run-3)
  const highlight = useMemo(() => criticalElement(fields), [fields]);
  const [answer, setAnswer] = useState<ExplainAnswer | null>(null);
  useEffect(() => {
    // once our engine has written the explanation, the API's writer (the template, or a model behind a setting) rephrases it (ADR-0052)
    if (!job || !apiBase || !("explanation" in job.outputs)) return;
    let cancelled = false;
    explainJob(apiBase, job.job_id, "result").then((a) => { if (!cancelled) setAnswer(a); })
      .catch((error) => { if (!cancelled && !(error instanceof StudioError && error.status === 409)) setAnswer(null); });
    return () => { cancelled = true; };
  }, [job?.job_id, job?.state, "explanation" in (job?.outputs ?? {}), apiBase]);
  useEffect(() => { setChoice(DEFAULT_CHOICE(fields)); setScale(suggestedScale(fields.mesh.nodes, fields.nodal.magnitude)); }, [fields]);
  useEffect(() => { setTyped(picked !== null ? elementNumber(fields.mesh.element_labels[picked] ?? "") : ""); setTypedError(""); }, [picked, fields]);
  useEffect(() => {
    if (!shown) return;
    sceneBlock.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    readoutHeading.current?.focus({ preventScroll: true });
  }, [shown]);
  const options = useMemo(() => fieldOptions(fields), [fields]);
  const option = options.find((o) => o.id === choice.id) ?? options[0];
  const values = useMemo(() => valuesFor(fields, choice), [fields, choice]);
  const colorScale = useMemo(() => scaleFor(values.values, !values.signed, values.range), [values]);
  const field = useMemo<SceneField>(() => ({ by: values.by, values: values.values, scale: { min: colorScale.min, max: colorScale.max, stops: colorScale.stops, bands: contours } }),
    [values, colorScale, contours]);
  // the sets in words, one line per set, as the model's key says them (audit fea-run-16)
  const held: SceneMarker[] = preview ? [...new Set(preview.held.map((h) => h.set))].map((set) => {
    const of = preview.held.filter((h) => h.set === set);
    return { nodes: fields.mesh.node_sets[set] ?? preview.mesh.node_sets[set] ?? [], label: heldWords(set, of.flatMap((h) => h.dofs), of.flatMap((h) => h.directions)) };
  }) : [];
  const loaded = preview ? { nodes: fields.mesh.node_sets[preview.loaded.set] ?? preview.mesh.node_sets[preview.loaded.set] ?? [],
    direction: preview.loaded.direction, label: loadWords(preview.loaded) } : null;
  const readout = picked !== null ? elementReadout(fields, picked, choice, printed) : null;
  const show = (element: number, ply: number, criterion: string, face?: string | null) => {
    setPicked(element);
    const faceIndex = face && fields.mesh.faces ? Math.max(0, fields.mesh.faces.indexOf(face)) : undefined;
    setChoice((c) => ({ ...c, ply, criterion: criterion || c.criterion, face: faceIndex ?? c.face }));
    setShown((n) => n + 1);
  };
  const readTyped = () => {
    const index = elementIndex(fields, typed);
    if (index === null) { setTypedError(typed.trim() ? `No element ${typed.trim()} in this model.` : "Enter an element's number."); return; }
    setTypedError(""); setPicked(index);
  };
  const unit = values.unit && values.unit !== "-" ? ` ${values.unit}` : "";
  // the view's text alternative (WCAG 1.1.1, audit fea-run-47): the field and its range, and the critical element
  const sceneLabel = `3D view: ${values.label}, ${values.by === "element" ? "element values" : "nodal averages"}, ${printed(colorScale.ends[0])} to ${printed(colorScale.ends[1])}${unit}`
    + (highlight !== null ? `; critical element ${elementNumber(fields.mesh.element_labels[highlight] ?? "")} outlined` : "");
  return (
    <div className="studio-results" data-testid="results" data-source={live ? "live" : "run"} data-updating={updating}>
      {live ? (
        <p className="studio-live-banner" data-testid="live-banner">
          <strong>Preview</strong> ({live.seconds < 10 ? live.seconds.toFixed(1) : Math.round(live.seconds)} s). Run the analysis to verify it and write the report.{updating ? " Updating…" : ""}
        </p>
      ) : updating ? <p className="studio-live-banner" data-testid="live-banner">Updating…</p> : null}
      {/* the model in the same frame before and after the run, its heading and its link in one row (audit uiux-fea-run-28) */}
      <div className="studio-panel studio-model" data-testid="model-panel">
        <div className="studio-panel-head">
          <h3>The model <span className="studio-badge">{fields.mesh.element_count} elements, {fields.mesh.node_count} nodes</span></h3>
          {viewerLink ? (
            <a className="studio-viewer-link" href={viewerLink} target="_blank" rel="noreferrer" data-testid="viewer-link">
              <ArrowUpRight size={13} aria-hidden="true" /> Open results in a new window</a>
          ) : null}
        </div>
        <div className="studio-scene-block" ref={sceneBlock}>
          <Scene nodes={fields.mesh.nodes} quads={fields.mesh.quads} thickness={preview?.geometry.thickness ?? 1} field={field}
            displacement={deformed ? fields.nodal.displacement : null} scale={scale} held={held} loaded={loaded} highlight={highlight} picked={picked}
            wireframe={wireframe} onPick={setPicked} label={sceneLabel} fit={fit} />
          <Legend scale={colorScale} label={values.label} unit={values.unit} by={values.by} bands={contours} />
          <p className="studio-muted studio-pick-hint">Click an element, enter its number or use Show in a table to read its values. With the view focused, the arrow keys turn it and + and − zoom.</p>
        </div>
        <div className="studio-controls" data-testid="field-controls">
          <label>Field
            <select value={choice.id} onChange={(e) => setChoice(withField(choice, e.target.value))} aria-label="Field">
              {[...new Set(options.map((o) => o.group))].map((group) => (
                <optgroup key={group} label={group}>{options.filter((o) => o.group === group).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</optgroup>
              ))}
            </select>
          </label>
          {option.perPly ? (
            <label>Ply
              <select value={choice.ply} onChange={(e) => setChoice({ ...choice, ply: Number(e.target.value) })} aria-label="Ply">
                {fields.mesh.angles.map((angle, i) => <option key={i} value={i + 1}>{plyLabel(i + 1, angle)}</option>)}
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
              <select value={choice.averaged ? "average" : "element"} onChange={(e) => setChoice({ ...choice, averaged: e.target.value === "average" })} aria-label="Values">
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
          <label>Scale ×
            <input type="number" value={scale} min={0} step="any" onChange={(e) => setScale(Number(e.target.value) || 0)} className="studio-scale" />
          </label>
          <label className="studio-check"><input type="checkbox" checked={deformed} onChange={(e) => setDeformed(e.target.checked)} /> Deformed</label>
          <label className="studio-check"><input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} /> Mesh edges</label>
          {/* the keyboard's way to what a click on the model shows (WCAG 2.1.1, audit fea-run-47) */}
          <form className="studio-element-pick" onSubmit={(e) => { e.preventDefault(); readTyped(); }}>
            <label>Element
              <input type="text" inputMode="numeric" value={typed} onChange={(e) => { setTyped(e.target.value); setTypedError(""); }} className="studio-element-input"
                aria-invalid={typedError ? true : undefined} aria-describedby={typedError ? "studio-element-error" : undefined} autoComplete="off" />
            </label>
            <button type="submit" className="studio-text-button">Show<span className="sr-only"> element</span></button>
            {picked !== null ? <button type="button" className="studio-text-button" onClick={() => setPicked(null)}>Clear</button> : null}
            {typedError ? <span className="chat-error" id="studio-element-error" role="alert">{typedError}</span> : null}
          </form>
          <button type="button" className="studio-text-button" onClick={() => setFit((n) => n + 1)}>Fit view</button>
        </div>
        {readout ? (
          <div className="studio-readout" data-testid="readout">
            <h4 ref={readoutHeading} tabIndex={-1}>{readout.title}{highlight === picked ? <span className="studio-badge">critical</span> : null}</h4>
            <dl>{readout.rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
            <p className="studio-muted">Click another element or enter its number to read it; Clear, or a click on the background, closes it.</p>
            {picked !== null ? <ProbePanel fields={fields} table={probeTable(fields, picked)} /> : null}
          </div>
        ) : null}
      </div>
      <AnswerCard fields={fields} onShow={show} />
      <SummaryPanel fields={fields} onShow={show} pending={Boolean(live) || isActive(job?.state)} />
      {/* the user's own Abaqus beside a finished run of the tension coupon, the one the comparison covers (ADR-0094 part 7) */}
      {job && !live && job.state === "done" && apiBase && fields.coupon.kind === "unnotched_tension"
        ? <AbaqusCard apiBase={apiBase} job={job} fields={fields} onShow={show} /> : null}
      <ExplanationPanel explanation={explanation} answer={answer} />
      {job && showFiles ? <Downloads apiBase={apiBase} job={job} fields={fields} /> : null}
    </div>
  );
}
