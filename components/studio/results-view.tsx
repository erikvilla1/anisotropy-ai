"use client";

import { useEffect, useMemo, useState } from "react";
import { DOWNLOADS, explainJob, fileUrl, isActive, StudioError, type ExplainAnswer, type Explanation, type CalculixBeside, type Extreme, type Fields, type FirstPlyFailure, type JobStatus,
  type Preview } from "@/lib/studio-api";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, valuesFor, type FieldChoice } from "@/lib/studio-fields";
import { legendGradient, legendTicks, printed, scaleFor, settled, type Scale } from "@/lib/studio-colors";
import { suggestedScale } from "@/lib/studio-geometry";
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
      <p><strong>{label}</strong> ({unit}); {by === "element" ? "element values: the result" : "display averages over the elements sharing a node, for a smooth picture; the element values are the result"}.
        {scale.kind === "diverging" ? " Grey is zero." : ""} The values run from {printed(scale.ends[0])} to {printed(scale.ends[1])} {unit}, {scale.source === "package" ? "the ends the package wrote" : "the smallest and largest shown (this job's fields carry no written ranges)"}.
        {bands ? ` ${bands} bands of the ramp, a line at every tick; the colours are unlit.` : " The colours are unlit."}</p>
    </div>
  );
}

const xyz = (p: number[] | undefined) => (p && p.length === 3 ? ` (${p.map((v) => printed(v)).join(", ")})` : "");
/** The ply stress components as the fields name them (the team's CAE names), said with their symbols. */
const COMPONENT: Record<string, string> = { S11: "σ₁ along the fibres", S22: "σ₂ across the fibres", S12: "τ₁₂ in-plane shear" };

export function SummaryPanel({ fields, onShow }: { fields: Fields; onShow: (element: number, ply: number, criterion: string, face?: string | null) => void }) {
  const s = fields.summary, lab = fields.labels, cx = s.calculix ?? null;
  return (
    <div className="studio-panel" data-testid="summary">
      <h3>Summary</h3>
      <p className="studio-muted" data-testid="summary-who">Result: Anisotropy. Check: CalculiX, run on the same coupon; its results are the <code>.frd</code> under Files, which PrePoMax opens.</p>
      <dl className="studio-summary">
        <div><dt>Applied</dt><dd>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}{s.applied.direction ? `, ${s.applied.direction}` : ""}</dd></div>
        <div><dt>Reaction at {s.reaction.set}</dt><dd data-testid="summary-reaction">{printed(Math.abs(s.reaction.value))} {lab.force} ({s.reaction.sense})
          {cx?.reaction ? <span data-testid="summary-reaction-calculix">; CalculiX {printed(Math.abs(cx.reaction.calculix))} {lab.force}, Anisotropy {cx.reaction.difference} from it</span> : null}</dd></div>
        <div><dt>Largest displacement</dt><dd>{printed(s.max_displacement.value)} {lab.length} at node {s.max_displacement.label.split(".").pop()}
          {s.max_displacement.axis === "z" ? " (the deflection w)" : ""}</dd></div>
      </dl>
      {s.ply_peaks ? (
        <>
          <ValidationTable s={s} cx={cx} lab={lab} />
          <PeaksTable s={s} cx={cx} lab={lab} criterion={s.earliest ?? ""} onShow={onShow} />
        </>
      ) : <OlderPeaks fields={fields} onShow={onShow} />}
      <h4>First-ply failure</h4>
      {Object.keys(s.fpf).length === 0 ? <p className="studio-muted">No failure criterion was asked for.</p> : (
        <FailureTable fpf={s.fpf} earliest={s.earliest} testId="fpf-table" factorPrefix="fpf-factor" onShow={onShow} />
      )}
      <p className="studio-muted">R is the factor on the applied loading at which the first ply fails; the failure index is 1/R. Below 1, the loading of the model is past first-ply failure.
        {s.earliest && s.fpf[s.earliest]?.touches_grip ? " The critical element touches a gripped tab: the clamped edge, not the gauge section, where the stress is not expected to settle as the mesh is refined." : ""}</p>
      {s.fpf_gauge && Object.keys(s.fpf_gauge).length ? (
        <>
          <h4>First-ply failure in the gauge section</h4>
          <FailureTable fpf={s.fpf_gauge} earliest={s.earliest_gauge ?? null} testId="fpf-gauge-table" factorPrefix="fpf-gauge-factor" onShow={onShow} />
          <p className="studio-muted">The same criteria over the gauge section alone, the elements away from the gripped tabs&apos; clamped edge: the factor a test coupon, which breaks in its gauge
            section, is compared with.</p>
        </>
      ) : null}
      {s.test_method ? <TestMethodCard tm={s.test_method} cx={cx?.test_method ?? null} /> : null}
    </div>
  );
}

/** The quantities the coupon's test standard reduces a test to (ADR-0072), as the package wrote them: the area, the stress, the strain over the
 * measurement, the chord modulus beside laminate theory and CalculiX, Poisson's ratio, the net section of an open hole, and the first-ply
 * failure stress, which is never the standard's ultimate strength. Three significant figures, as the standards report. */
function TestMethodCard({ tm, cx }: { tm: NonNullable<Fields["summary"]["test_method"]>; cx: NonNullable<CalculixBeside["test_method"]> | null }) {
  const u = tm.units;
  const three = (v: number) => Number(v.toPrecision(3)).toString();
  const rows: [string, string][] = [
    ["Gross area", `${three(tm.area)} ${u.area} (${three(tm.width)} × ${three(tm.thickness)} ${u.length})`],
    ["Stress P/A", `${three(Math.abs(tm.stress))} ${u.stress} under ${three(Math.abs(tm.force))} ${u.force}`],
  ];
  if (tm.hole) {
    rows.push(["Net section", `${three(tm.hole.net_area)} ${u.area}, ${three(Math.abs(tm.hole.net_stress))} ${u.stress}`],
      ["w/D and D/h", `${three(tm.hole.width_to_hole)} and ${three(tm.hole.hole_to_thickness)}`]);
  }
  if (tm.strain) {
    const c = tm.strain.chord;
    rows.push([`Strain over the ${tm.strain.device}`, `${three(Math.abs(tm.strain.microstrain))} microstrain over ${three(tm.strain.modelled_length)} ${u.length}`],
      ["Chord modulus, 1000 to 3000 microstrain", `${three(c.modulus)} ${u.modulus}` + (cx ? `; CalculiX ${three(cx.calculix.modulus)} ${u.modulus}` : "")
        + `; laminate theory ${three(tm.laminate_theory.modulus)} ${u.modulus}`],
      ["Load for the chord", `${three(Math.abs(c.force_from))} to ${three(Math.abs(c.force_to))} ${u.force}`]);
    if (tm.strain.poisson !== null) rows.push(["Poisson's ratio", `${three(tm.strain.poisson)}; laminate theory ${three(tm.laminate_theory.poisson)}`]);
  }
  const first = tm.earliest ? tm.fpf[tm.earliest] : null;
  if (first) {
    rows.push([`First-ply-failure stress (${tm.earliest}, ${tm.fpf_basis})`, `${three(Math.abs(first.stress))} ${u.stress} gross`
      + (first.net_stress !== undefined ? `, ${three(Math.abs(first.net_stress))} ${u.stress} net` : "")
      + (first.microstrain !== undefined ? ` at ${three(Math.abs(first.microstrain))} microstrain` : "")]);
  }
  return (
    <div className="ws-test-method" data-testid="test-method">
      <h4>{tm.designation ? `As ${tm.designation} reduces a test` : "As a test is reduced"}</h4>
      <dl className="studio-summary">
        {rows.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}
      </dl>
      <p className="studio-muted">From our engine&apos;s solution by the standard&apos;s own formulas. A linear model gives the same chord over any range. The first-ply-failure stress is the load
        at which the first ply fails, over the area: not the ultimate strength the standard takes at a test&apos;s maximum force, which a linear model cannot give.
        {tm.note_b ? " The first ply fails below 6000 microstrain, where Table 3 note B of D3039 moves the chord range." : ""}</p>
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
      <h4>Validation: the same quantity in every column</h4>
      <table className="studio-table" data-testid="validation-table">
        <thead>
          <tr><th>Quantity</th><th>Laminate theory</th><th>Anisotropy</th><th>CalculiX</th></tr>
          <tr className="studio-muted">
            <th />
            <th>{clt ? `N_y = reaction / width (${printed(clt.Ny)} ${lab.force}/${lab.length}), N_x = N_xy = 0, each ply at its middle` : "not for this loading"}</th>
            <th>element centroid{gaugeElement ? `, element ${gaugeElement}` : ""}</th>
            <th>{cx ? `integration-point average${gaugeElement ? `, element ${gaugeElement}` : ""}` : "no twin was run"}</th>
          </tr>
        </thead>
        <tbody>
          <tr data-row="reaction"><td>Reaction force, {lab.force}</td><td>input</td><td>{printed(Math.abs(s.reaction.value))}</td>
            <td>{cx?.reaction ? `${printed(Math.abs(cx.reaction.calculix))} (${cx.reaction.difference})` : DASH}</td></tr>
          <tr data-row="strain"><td>Gauge centre εx / εy / γxy</td><td>{three(clt?.strain)}</td><td>{three(cx?.gauge_strain?.ours)}</td>
            <td>{three(cx?.gauge_strain?.calculix, cx?.gauge_strain?.agrees)}</td></tr>
          {Array.from({ length: plies }, (_, k) => {
            const c = clt?.plies[k], g = cx?.gauge[k];
            const angle = c?.angle ?? (g ? s.ply_peaks?.[k]?.angle : undefined);
            return (
              <tr key={k} data-ply={k + 1}><td>Ply {k + 1}{angle !== undefined ? ` (${angle}°)` : ""}: σ₁ / σ₂ / τ₁₂, {lab.stress}</td>
                <td>{three(c?.stress_12)}</td><td>{three(g?.ours)}</td><td>{three(g?.calculix, g?.agrees)}</td></tr>
            );
          })}
        </tbody>
      </table>
      <p className="studio-muted">Each ply&apos;s stresses are in its own fibre axes (σ₁ along the fibres, σ₂ across, τ₁₂ in-plane shear), plies counted from the bottom face, angles from the
        coupon&apos;s length axis. {cx ? <>The record {cx.record} holds {cx.agree} values within {printed(100 * cx.tolerance)} %; a ✕ marks one outside.</> : null}
        {" "}CalculiX, the open-source solver, is the check; the same table read from an Abaqus run of the deck is a command-line tool (<code>tools/abaqus_beside.py</code>), not a column here (the founder, 2026-11-08).</p>
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
      <summary><h4>{clamped ? "Stress concentration at the clamped edge" : "Peaks over the model"}: not a validation value</h4></summary>
      <table className="studio-table" data-testid="peaks-table">
        <thead>
          <tr><th>Ply</th><th>Anisotropy, element centroid</th><th>CalculiX, brick corner node</th></tr>
          <tr className="studio-muted"><th /><th>σ₁ / σ₂ / τ₁₂, {lab.stress}, the largest of each over the elements</th>
            <th>the same, extrapolated to the nodes of the ply&apos;s bricks</th></tr>
        </thead>
        <tbody>
          {peaks.map((p, k) => {
            const f = frdPlies?.[k];
            return (
              <tr key={p.ply} data-ply={p.ply}>
                <td>{p.ply} ({p.angle}°)</td>
                <td>{three([p.S11.value, p.S22.value, p.S12.value])} at element {p.S11.label.split(".").pop()}{p.S11.face ? `, ${p.S11.face} face` : ""}{p.S11.touches_grip ? ", clamped edge" : ""}
                  {" "}<button type="button" className="studio-text-button" onClick={() => onShow(p.S11.element, p.ply, criterion, p.S11.face)}>show</button></td>
                <td>{f && typeof f.s1_max === "number" ? <>{three([f.s1_max, f.s2_max, f.t12_max_abs])} at node {f.s1_max_node}{xyz(f.s1_max_xyz)}</> : DASH}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="studio-muted">{clamped ? "Where a gripped tab ends at a free edge the elastic solution is singular: the value there grows as the mesh is refined and depends on where it is read, so no two columns are expected to agree. " : ""}
        Anisotropy reads the element centroid; CalculiX&apos;s <code>.frd</code> holds one brick per element and ply with values extrapolated to the corner nodes, so its peak sits above the centroid of the same ply.
        {cx?.frd ? <> What PrePoMax shows of that file is in the global axes: its S11 is σxx across the width ({printed(cx.frd.sxx_min)} to {printed(cx.frd.sxx_max)} {lab.stress}), its S22 is σyy along the coupon
          (largest {printed(cx.frd.syy_max)} {lab.stress} at node {cx.frd.syy_max_node}) and its von Mises is the three-dimensional invariant (largest {printed(cx.frd.mises_max)} {lab.stress} at node {cx.frd.mises_max_node}{xyz(cx.frd.mises_max_xyz)}),
          none of them a composite quantity; open the ply&apos;s part and read S22 for a 0° ply&apos;s σ₁.</> : null}</p>
    </details>
  );
}

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
          <h4>Gauge section, where the two solvers agree</h4>
          <table className="studio-table" data-testid="gauge-table">
            <thead><tr><th>Ply</th><th>σ₁ along the fibres</th><th>σ₂ across the fibres</th><th>τ₁₂ shear</th></tr></thead>
            <tbody>
              {cx.gauge.map((g) => (
                <tr key={g.ply} data-ply={g.ply}><td>{g.ply} ({fields.mesh.angles[g.ply - 1]}°)</td>
                  {[0, 1, 2].map((i) => <td key={i}>{g.ours[i] === null ? "–" : printed(g.ours[i] as number)} / {g.calculix[i] === null ? "–" : printed(g.calculix[i] as number)}{g.agrees[i] === false ? " ✕" : ""}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="studio-muted">Each cell is Anisotropy / CalculiX, in {lab.stress}, at the centre element {cx.gauge_element?.split(".").pop()}: Anisotropy at the element&apos;s centroid, CalculiX
            averaged over its integration points. The record {cx.record} holds {cx.agree} values within {printed(100 * cx.tolerance)} %; a ✕ marks one outside.</p>
        </>
      ) : null}
      <h4>Peaks at the tab line</h4>
      <dl className="studio-summary">
        {fibre ? (
          <div data-testid="summary-fibre-peak"><dt>Largest σ₁ along the fibres</dt>
            <dd>{printed(fibre.value)} {lab.stress} {place(fibre)}
              <button type="button" className="studio-text-button" onClick={() => onShow(fibre.element, fibre.ply, s.earliest ?? "", fibre.face)}>show</button>
              {cx?.frd ? <span data-testid="summary-fibre-calculix">; CalculiX puts σyy = {printed(cx.frd.syy_max)} {lab.stress} at the corner node {cx.frd.syy_max_node}{xyz(cx.frd.syy_max_xyz as number[] | undefined)}: a clamped
                edge, so the element&apos;s average and the corner node differ, and both grow as the mesh is refined</span> : null}</dd></div>
        ) : null}
        {others.map(([name, m]) => (
          <div key={name}><dt>Largest {COMPONENT[name] ?? name}</dt>
            <dd>{printed(m.value)} {lab.stress} {place(m)}
              <button type="button" className="studio-text-button" onClick={() => onShow(m.element, m.ply, s.earliest ?? "", m.face)}>show</button></dd></div>
        ))}
        {cx?.frd ? (
          <>
            <div data-testid="summary-frd-mises"><dt>Largest von Mises, CalculiX</dt><dd>{printed(cx.frd.mises_max)} {lab.stress} at node {cx.frd.mises_max_node}{xyz(cx.frd.mises_max_xyz)}</dd></div>
            <div><dt>Transverse stress at the grips, CalculiX</dt><dd>σxx from {printed(cx.frd.sxx_min)} to {printed(cx.frd.sxx_max)} {lab.stress} (PrePoMax labels it S11)</dd></div>
            {typeof cx.frd.gauge_mises_max === "number" ? <div><dt>Gauge section, CalculiX</dt><dd>largest σyy {printed(cx.frd.gauge_syy_max as number)}, von Mises {printed(cx.frd.gauge_mises_max)} {lab.stress}</dd></div> : null}
          </>
        ) : null}
      </dl>
      <p className="studio-muted">Anisotropy&apos;s values are each ply&apos;s stresses in its own fibre axes (σ₁, σ₂, τ₁₂) at element centroids. CalculiX&apos;s are what PrePoMax shows of
        the <code>.frd</code>: the global axes (σxx across the width, σyy along the coupon), one brick per ply, values extrapolated to the nodes, a three-dimensional von Mises.
        Both peak where a gripped tab ends, a clamped edge whose stress grows as the mesh is refined; the gauge section is where the two agree.</p>
    </>
  );
}

function FailureTable({ fpf, earliest, testId, factorPrefix, onShow }: {
  fpf: Record<string, FirstPlyFailure>; earliest: string | null; testId: string; factorPrefix: string;
  onShow: (element: number, ply: number, criterion: string, face?: string | null) => void;
}) {
  return (
    <table className="studio-table" data-testid={testId}>
      <thead><tr><th>Criterion</th><th>Factor R</th><th>Index 1/R</th><th>Ply</th><th>Mode</th><th>Where</th><th></th></tr></thead>
      <tbody>
        {Object.entries(fpf).sort(([, a], [, b]) => a.factor - b.factor).map(([criterion, f]) => (
          <tr key={criterion} data-criterion={criterion} className={criterion === earliest ? "studio-earliest" : undefined}>
            <td>{criterion.replace("_", " ")}{criterion === earliest ? " (earliest)" : ""}</td>
            <td data-testid={`${factorPrefix}-${criterion}`}>{printed(f.factor)}</td><td>{printed(f.index)}</td>
            <td>{f.ply} ({f.angle}°){f.face ? `, ${f.face} face` : ""}{f.tied_plies.length > 1 ? `, tied ${f.tied_plies.join(", ")}` : ""}</td>
            <td>{f.mode}</td><td>element {f.label.split(".").pop()}, {f.place}</td>
            <td><button type="button" className="studio-text-button" onClick={() => onShow(f.element, f.ply, criterion, f.face)}>show</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ExplanationPanel({ explanation, answer }: { explanation: Explanation | null; answer?: ExplainAnswer | null }) {
  if (!explanation && !answer) return null;
  const prose = answer?.prose ?? explanation?.sentences ?? [];
  const writer = answer?.writer ?? explanation?.writer ?? "template";
  const badge = writer === "template" ? "written by the template from the engine's numbers" : `written by ${writer}${answer?.model ? ` (${answer.model})` : ""}, every number checked against the engine's`;
  return (
    <div className="studio-panel" data-testid="explanation" data-writer={writer}>
      <h3>What this shows <span className="studio-badge studio-badge-writer">{badge}</span></h3>
      {answer?.reason ? <p className="studio-muted" data-testid="explanation-reason">{answer.withheld ? "The model's draft was withheld: " : "The template's words stand: "}{answer.reason}.</p> : null}
      {prose.map((sentence, i) => <p key={i}>{sentence}</p>)}
      {explanation?.setup_sentences.length ? <details><summary>The setup, as checked</summary>{explanation.setup_sentences.map((s, i) => <p key={i}>{s}</p>)}</details> : null}
    </div>
  );
}

export function Downloads({ apiBase, job }: { apiBase: string; job: JobStatus }) {
  const available = DOWNLOADS.filter(([key]) => key in job.outputs);
  if (!available.length) return null;
  return (
    <div className="studio-panel" data-testid="downloads">
      <h3>Files</h3>
      <ul className="studio-downloads">
        {available.map(([key, label]) => <li key={key}><a href={fileUrl(apiBase, job.job_id, key)} target="_blank" rel="noreferrer" data-key={key}>{label}</a></li>)}
      </ul>
      {isActive(job.state) ? <p className="studio-muted">More files join the list as the job goes on.</p> : null}
    </div>
  );
}

export function ResultsView({ fields, explanation, job, apiBase, preview }: {
  fields: Fields; explanation: Explanation | null; job: JobStatus | null; apiBase: string; preview: Preview | null;
}) {
  const [choice, setChoice] = useState<FieldChoice>(() => DEFAULT_CHOICE(fields));
  const [scale, setScale] = useState<number>(() => suggestedScale(fields.mesh.nodes, fields.nodal.magnitude));
  const [deformed, setDeformed] = useState(true);
  const [wireframe, setWireframe] = useState(true);
  const [contours, setContours] = useState(DEFAULT_CONTOURS);
  const [picked, setPicked] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number | null>(() => (fields.summary.earliest ? fields.summary.fpf[fields.summary.earliest].element : null));
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
    <div className="studio-results" data-testid="results">
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
              {Object.keys(fields.element.failure).map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
            </select>
          </label>
        ) : null}
        {!option.nodalOnly && option.id !== "failure_index_ply" ? (
          <label>Shown as
            <select value={choice.averaged ? "average" : "element"} onChange={(e) => setChoice({ ...choice, averaged: e.target.value === "average" })} aria-label="Shown as">
              <option value="element">element values (the result)</option>
              <option value="average">display averages (smooth)</option>
            </select>
          </label>
        ) : null}
        <label><input type="checkbox" checked={deformed} onChange={(e) => setDeformed(e.target.checked)} /> deformed shape, scale
          <input type="number" value={scale} min={0} step="any" onChange={(e) => setScale(Number(e.target.value) || 0)} aria-label="Deformation scale" className="studio-scale" /> ×</label>
        <label><input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} /> element edges</label>
        <label>Contours
          <select value={contours} onChange={(e) => setContours(Number(e.target.value))} aria-label="Contours">
            {CONTOURS.map(([bands, word]) => <option key={bands} value={bands}>{word}</option>)}
          </select>
        </label>
      </div>
      {readout ? (
        <div className="studio-panel studio-readout" data-testid="readout">
          <h3>{readout.title}{highlight === picked ? " (the critical element)" : ""}</h3>
          <dl>{readout.rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <p className="studio-muted">Click an element on the plate to read it; click the background to clear.</p>
        </div>
      ) : <p className="studio-muted studio-pick-hint">Click an element on the plate to read its values. The critical element is framed in red.</p>}
      <SummaryPanel fields={fields} onShow={show} />
      <ExplanationPanel explanation={explanation} answer={answer} />
      {job ? <Downloads apiBase={apiBase} job={job} /> : null}
    </div>
  );
}
