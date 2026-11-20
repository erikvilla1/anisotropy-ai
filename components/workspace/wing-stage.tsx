"use client";

import { useMemo, useState } from "react";
import { CATEGORICAL, CRITICAL, DIVERGING, ramp, SEQUENTIAL } from "@/lib/studio-colors";
import {
  answerWords, CHECK_NAMES, CHECK_WORDS, feProgress, feWords, handAndModel, marginText, shown, spanWords, unitText, whereWords,
  type HandAndModel, type WingAnswer, type WingCheckName, type WingFeCheck, type WingFeReport, type WingReport, type WingViews,
} from "@/lib/wing";
import { useWing } from "./wing-context";

type CheckChoice = WingCheckName | "lowest";
const css = (rgb: [number, number, number]) => `rgb(${rgb.map((c) => Math.round(c * 255)).join(",")})`;

/** A margin's colour: below zero the critical red; from zero up, warm at zero fading to grey at +1 and above. The colour carries
 * no number: the legend and the labels do. */
function marginColour(margin: number | null): string {
  if (margin === null) return "#2a2f2a";
  if (margin < 0) return CRITICAL;
  return css(ramp(["#d95926", "#df7a4c", "#e0a07c", "#9ba29b"], Math.min(margin, 1)));
}

/** The lowest of the chosen checks' margins at each station of a case. */
function marginsAlong(views: WingViews, index: number, check: CheckChoice): (number | null)[] {
  const margins = views.cases[index].margins;
  const names = check === "lowest" ? CHECK_NAMES : [check];
  return views.stations.map((_, i) => {
    const values = names.map((n) => margins[n][i]).filter((v): v is number => v !== null);
    return values.length ? Math.min(...values) : null;
  });
}

/** The wing from above, root on the left: the box between the spars coloured by margin along the span, the ribs, the line of
 * shear centres, the spar caps' edges and where a layup changes along the span (ADR-0124). */
function Planform({ views, margins, governingAt, units }: { views: WingViews; margins: (number | null)[]; governingAt: number | null; units: string }) {
  const width = 640, pad = 34;
  const scale = Math.min((width - 2 * pad) / views.half_span, 220 / views.chord);
  const height = views.chord * scale + 2 * pad;
  const X = (y: number) => pad + y * scale; // spanwise
  const Y = (x: number) => pad + x * scale; // chordwise, leading edge at the top
  const [front, rear] = views.spars;
  const bands = views.stations.slice(0, -1).map((y, i) => {
    const both = [margins[i], margins[i + 1]].filter((v): v is number => v !== null);
    return { y0: y, y1: views.stations[i + 1], margin: both.length ? Math.min(...both) : null };
  });
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="wing-svg" role="img" aria-label="The wing from above, coloured by the lowest margin along the span" data-testid="wing-planform">
      <rect x={X(0)} y={Y(0)} width={views.half_span * scale} height={views.chord * scale} className="wing-outline" />
      {bands.map((b, i) => (
        <rect key={i} x={X(b.y0)} y={Y(front)} width={(b.y1 - b.y0) * scale + 0.5} height={(rear - front) * scale} fill={marginColour(b.margin)}>
          <title>{`${shown(b.y0, 3)} to ${shown(b.y1, 3)} ${units} from the root: margin ${marginText(b.margin)}`}</title>
        </rect>
      ))}
      {[front, rear].map((x, i) => <line key={i} x1={X(0)} x2={X(views.half_span)} y1={Y(x)} y2={Y(x)} className="wing-spar" />)}
      {views.ribs.map((y, i) => <line key={i} x1={X(y)} x2={X(y)} y1={Y(0)} y2={Y(views.chord)} className="wing-rib" />)}
      {(views.caps ?? []).filter((cap) => cap.name.startsWith("upper")).flatMap((cap) => [Math.min(...cap.x), Math.max(...cap.x)]).map((x, i) => (
        <line key={`cap-${i}`} x1={X(0)} x2={X(views.half_span)} y1={Y(x)} y2={Y(x)} className="wing-cap-edge"><title>Spar cap edge</title></line>
      ))}
      {(views.changes ?? []).map((y, i) => (
        <line key={`change-${i}`} x1={X(y)} x2={X(y)} y1={Y(front) - 6} y2={Y(rear) + 6} className="wing-change">
          <title>{`The plies change here, ${shown(y, 3)} ${units} from the root`}</title>
        </line>
      ))}
      <line x1={X(0)} x2={X(views.half_span)} y1={Y(views.shear_center)} y2={Y(views.shear_center)} className="wing-sc" />
      {governingAt !== null ? <circle cx={X(governingAt)} cy={Y((front + rear) / 2)} r={6} className="wing-governing" /> : null}
      <line x1={X(0)} x2={X(0)} y1={Y(0) - 8} y2={Y(views.chord) + 8} className="wing-root" />
      <text x={X(0)} y={height - 8} className="wing-label">Root, fixed</text>
      <text x={X(views.half_span)} y={height - 8} className="wing-label" textAnchor="end">Tip · {shown(views.half_span, 4)} {units}</text>
      <text x={X(0)} y={16} className="wing-label">Leading edge</text>
    </svg>
  );
}

/** The lowest margin of each check along the span: one line a check, zero marked. */
function MarginChart({ views, index, units }: { views: WingViews; index: number; units: string }) {
  const width = 640, height = 190, left = 74, right = 12, top = 12, bottom = 30;
  const margins = views.cases[index].margins;
  const all = CHECK_NAMES.flatMap((n) => margins[n]).filter((v): v is number => v !== null);
  // the range that matters is near the lowest margin: down to it (and to −1 at most), up to +2; a margin above +2 runs along the top
  const low = Math.max(-1, Math.min(-0.25, ...all.map((v) => v - 0.1)));
  const high = 2;
  const X = (y: number) => left + (y / views.half_span) * (width - left - right);
  const Y = (m: number) => top + (1 - (Math.min(Math.max(m, low), high) - low) / (high - low)) * (height - top - bottom);
  const ticks = [...(low <= -0.5 ? [Math.ceil(low * 2) / 2] : []), 0, 1, 2];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="wing-svg" role="img" aria-label="Lowest margin of each check along the span" data-testid="wing-margin-chart">
      {ticks.map((t) => <g key={t}><line x1={left} x2={width - right} y1={Y(t)} y2={Y(t)} className={t === 0 ? "wing-zero" : "wing-grid"} />
        <text x={left - 6} y={Y(t) + 4} textAnchor="end" className="wing-label wing-label-small">{t === 0 ? "0" : `${t > 0 ? "+" : "−"}${Math.abs(t)}${t === high ? " or more" : ""}`}</text></g>)}
      {CHECK_NAMES.map((name, k) => {
        const points = views.stations.map((y, i) => (margins[name][i] === null ? null : `${X(y).toFixed(1)},${Y(margins[name][i] as number).toFixed(1)}`)).filter(Boolean);
        return points.length ? <polyline key={name} points={points.join(" ")} fill="none" stroke={CATEGORICAL[k]} strokeWidth={2} /> : null;
      })}
      <text x={left} y={height - 8} className="wing-label wing-label-small">root</text>
      <text x={width - right} y={height - 8} textAnchor="end" className="wing-label wing-label-small">tip · {units} from the root</text>
    </svg>
  );
}

/** The root section: the airfoil, the box's walls where the hand calculation puts them, coloured by the shear flow or the spanwise
 * load of the case at the root, the shear center and the centroid. */
function Section({ views, index, field, units }: { views: WingViews; index: number; field: "shear_flow" | "load"; units: WingReport["units"] }) {
  const width = 640, pad = 24;
  const { airfoil } = views;
  const zs = [...airfoil.upper, ...airfoil.lower];
  const zMin = Math.min(...zs), zMax = Math.max(...zs);
  const scale = (width - 2 * pad) / views.chord;
  const height = (zMax - zMin) * scale + 2 * pad + 40;
  const X = (x: number) => pad + x * scale;
  const Z = (z: number) => pad + (zMax - z) * scale;
  const outline = [...airfoil.x.map((x, i) => `${X(x)},${Z(airfoil.upper[i])}`), ...airfoil.x.map((x, i) => `${X(x)},${Z(airfoil.lower[i])}`).reverse()].join(" ");
  const root = views.cases[index].root;
  const values = root.flatMap((w) => w[field]).filter((v): v is number => v !== null);
  const top = Math.max(1e-12, ...values.map(Math.abs));
  const colour = (v: number | null) => v === null ? "#555" : field === "shear_flow" ? css(ramp(SEQUENTIAL.slice(2), Math.abs(v) / top)) : css(ramp(DIVERGING, 0.5 + v / (2 * top)));
  const label = field === "shear_flow" ? "shear flow" : "spanwise load";
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="wing-svg" role="img" aria-label={`The root section with the ${label} round the box`} data-testid="wing-section">
      <polygon points={outline} className="wing-airfoil" />
      {(views.caps ?? []).map((cap) => (
        <polyline key={cap.name} points={cap.x.map((x, i) => `${X(x)},${Z(cap.z[i])}`).join(" ")} className="wing-cap" data-testid={`wing-cap-${cap.name.replace(/ /g, "-")}`}>
          <title>{`${cap.name[0].toUpperCase()}${cap.name.slice(1)}`}</title>
        </polyline>
      ))}
      {views.walls.map((wall, w) => wall.x.slice(0, -1).map((x, i) => (
        <line key={`${w}-${i}`} x1={X(x)} y1={Z(wall.z[i])} x2={X(wall.x[i + 1])} y2={Z(wall.z[i + 1])} stroke={colour(root[w][field][i])} strokeWidth={6} strokeLinecap="round">
          <title>{`${wall.name}: ${label} ${shown(root[w][field][i], 4)} ${unitText(units.running_load)}`}</title>
        </line>
      )))}
      <circle cx={X(views.shear_center)} cy={Z(views.centroid[1])} r={5} className="wing-sc-dot"><title>{`Shear center, ${shown(views.shear_center, 4)} ${unitText(units.length)} from the leading edge`}</title></circle>
      <path d={`M${X(views.centroid[0]) - 5},${Z(views.centroid[1])} h10 M${X(views.centroid[0])},${Z(views.centroid[1]) - 5} v10`} className="wing-centroid"><title>Centroid</title></path>
      {views.spars.map((x, i) => (
        <text key={i} x={X(x)} y={height - 14} textAnchor="middle" className="wing-label">{i === 0 ? "Front" : "Rear"} web · {shown(views.spar_heights[i], 3)} {unitText(units.length)}</text>
      ))}
      <text x={X(views.shear_center)} y={Z(views.centroid[1]) - 10} textAnchor="middle" className="wing-label wing-label-small">shear center</text>
      <text x={width - pad} y={16} textAnchor="end" className="wing-label wing-label-small">{label}: 0 to {shown(top, 3)} {unitText(units.running_load)}{field === "load" ? ", blue compression, orange tension" : ""}</text>
    </svg>
  );
}

/** EI and GJ: one value for a wing whose plies do not change along the span, else one a stretch, root to tip (ADR-0124). */
function stiffness(d: WingReport["design"], u: WingReport["units"]): [string, string][] {
  const stretches = d.stretches ?? [];
  if (stretches.length < 2) {
    return [["Bending stiffness EI", `${shown(d.bending_stiffness)} ${unitText(u.stiffness)}`], ["Torsion stiffness GJ", `${shown(d.torsion_stiffness)} ${unitText(u.stiffness)}`]];
  }
  const span = stretches[stretches.length - 1].end;
  const each = (key: "bending_stiffness" | "torsion_stiffness") =>
    stretches.map((s) => `${shown(s[key])} from ${spanWords(s.start / span, s.end / span)}`).join("; ") + ` ${unitText(u.stiffness)}`;
  return [["Bending stiffness EI", each("bending_stiffness")], ["Torsion stiffness GJ", each("torsion_stiffness")]];
}

function Design({ report }: { report: WingReport }) {
  const d = report.design, u = report.units, a = report.aeroelastic;
  const rows: [string, string][] = [
    ["Mass, one side", `${shown(d.mass)} ${unitText(u.mass)} (skins ${shown(d.mass_skins, 3)}${d.mass_caps ? `, spar caps ${shown(d.mass_caps, 3)}` : ""}, spars ${shown(d.mass_spars, 3)}, core ${shown(d.mass_core, 3)})`],
    ...stiffness(d, u),
    ["First bending frequency", `${shown(d.first_bending_frequency, 3)} Hz`],
    ["Shear center", `${shown(d.shear_center)} ${unitText(u.length)} from the leading edge`],
    ["Shear carried", `front web ${Math.round(d.shear_shares[0] * 100)} %, rear web ${Math.round(d.shear_shares[1] * 100)} %, curved skins the rest`],
    ["Skin buckling load", `${shown(d.skin_buckling_load)} ${unitText(u.running_load)}`],
  ];
  if (a) {
    rows.push(["Divergence speed", a.divergence_never ? "never" : a.divergence_speed === null ? `needs ${a.needs.join(", ") || "values"}` : `${shown(a.divergence_speed, 4)} ${u.speed}${a.divergence_over_dive !== null ? `, ${shown(a.divergence_over_dive, 3)} × dive` : ""}`]);
    rows.push(["Aileron reversal speed", a.reversal_never ? "never" : a.reversal_speed === null ? "needs the aileron" : `${shown(a.reversal_speed, 4)} ${u.speed}${a.reversal_over_dive !== null ? `, ${shown(a.reversal_over_dive, 3)} × dive` : ""}`]);
  }
  return (
    <table className="studio-table wing-design" data-testid="wing-design">
      <tbody>{rows.map(([k, v]) => <tr key={k}><th scope="row">{k}</th><td>{v}</td></tr>)}</tbody>
    </table>
  );
}

function Cases({ report, selected, onSelect }: { report: WingReport; selected: number; onSelect: (index: number) => void }) {
  const u = report.units;
  const proof = report.cases.some((c) => CHECK_NAMES.some((n) => c.checks[n].margin_proof !== null));
  return (
    <div className="wing-table-wrap">
      <table className="studio-table wing-cases" data-testid="wing-cases">
        <thead><tr><th>Case</th><th>Tip deflection</th>
          {CHECK_NAMES.map((n) => <th key={n}>{CHECK_WORDS[n]}</th>)}{proof ? <th>Proof, lowest</th> : null}</tr></thead>
        <tbody>
          {report.cases.map((c, i) => {
            const proofs = CHECK_NAMES.map((n) => c.checks[n].margin_proof).filter((v): v is number => v !== null);
            const governing = report.governing && report.governing.case === c.number && report.governing.altitude === c.altitude;
            return (
              <tr key={`${c.number}@${c.altitude}`} data-selected={i === selected ? "true" : undefined} data-governing={governing ? "true" : undefined} onClick={() => onSelect(i)}>
                <td><button type="button" className="chat-link" onClick={() => onSelect(i)}>{c.number} {c.label}</button>
                  <span className="wing-case-line">{shown(c.altitude, 5)} {u.altitude} · {shown(c.speed, 4)} {u.speed} · n {c.load_factor >= 0 ? "+" : "−"}{shown(Math.abs(c.load_factor), 3)}</span></td>
                <td>{shown(c.tip_deflection, 3)} {unitText(u.deflection)}</td>
                {CHECK_NAMES.map((n) => { const m = c.checks[n].margin_ultimate; return <td key={n} className={m !== null && m < 0 ? "wing-negative" : undefined}>{marginText(m)}</td>; })}
                {proof ? <td>{proofs.length ? marginText(Math.min(...proofs)) : "–"}</td> : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const MODE_WORDS: Record<string, string> = { bending: "bending", torsion: "torsion", "fore and aft": "fore and aft", local: "a panel's own" };

/** The finite element check beside the hand calculation (ADR-0119): the lowest margins by both, every case side by side, the wing as a
 * beam, its first modes, flutter and the panel that buckles first. Every number is the check's report; the page picks and words. */
function FeResults({ check, stale }: { check: WingFeCheck; stale: boolean }) {
  const report = check.report;
  if (!report) {
    return (
      <section className="studio-panel" data-testid="wing-fe">
        <h3>Finite element check</h3>
        <p className={check.state === "refused" || check.state === "stopped" ? "studio-alert" : "studio-muted"} role="status">{feProgress(check)}</p>
      </section>
    );
  }
  return <FeReport report={report} stale={stale} />;
}

/** A cell of the hand calculation's value over the model's. */
function Pair({ pair, print }: { pair: HandAndModel; print: (value: number | null) => string }) {
  const low = (v: number | null) => print === marginText && v !== null && v < 0;
  return <td><span className={low(pair.hand) ? "wing-negative" : undefined}>{print(pair.hand)}</span><br /><span className={low(pair.fe) ? "wing-negative" : undefined}>{print(pair.fe)}</span></td>;
}

function FeReport({ report, stale }: { report: WingFeReport; stale: boolean }) {
  const u = report.units;
  const words = feWords(report);
  const deflection = (v: number | null) => shown(v, 3);
  const beam: [string, string, string][] = [
    ["Shear center", `${shown(report.beam.shear_center.hand)} · ${shown(report.beam.shear_center.fe)}`, `${unitText(u.length)} from the leading edge`],
    ["Torsion stiffness GJ", handAndModel(report.beam.torsion_stiffness, (v) => shown(v)), unitText(u.stiffness)],
    ["First bending frequency", handAndModel(report.beam.first_bending_frequency, (v) => shown(v, 3)), "Hz"],
  ];
  if (report.divergence_speed) beam.push(["Divergence speed", handAndModel(report.divergence_speed, (v) => (v === null ? "never" : shown(v, 4))), `${u.speed}, equivalent`]);
  return (
    <section className="studio-panel wing-fe" data-testid="wing-fe" data-state={stale ? "stale" : "current"}>
      <h3>Finite element check</h3>
      <p data-testid="wing-fe-headline"><strong>{words.headline}</strong></p>
      <p>{words.where}</p>
      {stale ? <p className="studio-alert" role="status">This check is for the wing as it was when it started. The wing has changed since; check it again to see the change.</p> : null}
      <p className="studio-muted">{words.root}</p>
      <details className="wing-fe-more">
        <summary>Every case: hand calculation above, model below</summary>
      <div className="wing-table-wrap">
        <table className="studio-table wing-cases" data-testid="wing-fe-cases">
          <thead><tr><th>Case</th><th>Tip deflection, {unitText(u.deflection)}</th><th>Skin strength</th><th>Spar web strength</th><th>At the root</th></tr></thead>
          <tbody>{report.cases.map((c) => {
            const governing = c.number === report.lowest.case && c.altitude === report.lowest.altitude;
            return (
              <tr key={`${c.number}@${c.altitude}`} data-governing={governing ? "true" : undefined}>
                <td>{c.number} {c.label}<span className="wing-case-line">{shown(c.altitude, 5)} {u.altitude}</span></td>
                <Pair pair={c.tip_deflection} print={deflection} />
                <Pair pair={c.skin} print={marginText} />
                <Pair pair={c.spar} print={marginText} />
                <Pair pair={c.root} print={marginText} />
              </tr>
            );
          })}</tbody>
        </table>
      </div>
      </details>
      <h4>The wing as a beam, hand calculation · model</h4>
      <table className="studio-table wing-design" data-testid="wing-fe-beam">
        <tbody>{beam.map(([k, v, unit]) => <tr key={k}><th scope="row">{k}</th><td>{v} {unit}</td></tr>)}</tbody>
      </table>
      <h4>Vibration modes</h4>
      <p data-testid="wing-fe-modes">{report.modes.map((m) => `${m.number}: ${shown(m.frequency, 3)} Hz, ${MODE_WORDS[m.kind] ?? m.kind}`).join(" · ")}</p>
      {report.flutter ? (
        <p data-testid="wing-fe-flutter">Flutter, from the first bending ({shown(report.flutter.bending_frequency, 3)} Hz) and torsion ({shown(report.flutter.torsion_frequency, 3)} Hz) modes: {report.flutter.altitudes.map((a) =>
          `${shown(a.altitude, 5)} ${u.altitude}: ${a.speed === null ? "none found" : `${shown(a.speed, 4)} ${u.speed}${a.times_required !== null ? `, ${shown(a.times_required, 3)} × the flutter speed asked for` : ""}`}`).join("; ")}.</p>
      ) : <p className="studio-muted">No torsion mode among the first modes, so no flutter estimate.</p>}
      {report.buckling.length ? (
        <>
          <h4>Panel buckling under the hardest cases</h4>
          <table className="studio-table" data-testid="wing-fe-buckling">
            <thead><tr><th>Case</th><th>Panel</th><th>Buckles at</th><th>Margin, model</th><th>Hand: skin · web</th></tr></thead>
            <tbody>{report.buckling.map((b) => (
              <tr key={`${b.case}@${b.altitude}`}><td>{b.case} {b.label}</td><td>{b.part.toLowerCase()} bay at {shown(b.station, 3)} {unitText(u.length)}</td>
                <td>{shown(b.factor, 3)} × limit load</td><td>{marginText(b.margin_ultimate)}</td><td>{marginText(b.hand_skin)} · {marginText(b.hand_web)}</td></tr>
            ))}</tbody>
          </table>
          <p className="studio-muted">A web&apos;s bay is judged on its mean load, which leaves out its own bending; for the webs the hand calculation&apos;s check is the one to go by.</p>
        </>
      ) : null}
      <p className="studio-muted">{report.model.elements.toLocaleString("en-US")} shell elements of {shown(report.model.element_size, 3)} {unitText(u.thickness)}, every ply a layer; the root clamped; solved in {Math.max(1, Math.round(report.seconds.total))} s.
        {report.not_run ? ` ${report.not_run} case${report.not_run === 1 ? "" : "s"} still wait for inputs, as in the hand calculation.` : ""}</p>
    </section>
  );
}

/** The centre of the wing workspace (ADR-0118): the answer in one line, the wing from above and its root section for the chosen case,
 * the margins along the span, the design summary and every case's margins. Every number is the engine's; the page picks and draws. */
export function WingStage() {
  const { answer, stale, working, problem } = useWing();
  if (!answer) {
    return (
      <div className="studio-panel wing-stage" data-testid="wing-stage" data-state="waiting">
        <p className={problem ? "studio-alert" : "studio-muted"} role={problem ? "alert" : "status"}>{problem || (working ? "Working the wing…" : "The wing appears here.")}</p>
      </div>
    );
  }
  return <Answer answer={answer} stale={stale} problem={problem} />;
}

function Answer({ answer, stale, problem }: { answer: WingAnswer; stale: boolean; problem: string }) {
  const { report, views } = answer;
  const { feCheck, feCheckStale } = useWing();
  const governingIndex = useMemo(() => Math.max(0, report.cases.findIndex((c) => report.governing && c.number === report.governing.case && c.altitude === report.governing.altitude)), [report]);
  const [chosen, setChosen] = useState<number | null>(null);
  const [check, setCheck] = useState<CheckChoice>("lowest");
  const [field, setField] = useState<"shear_flow" | "load">("shear_flow");
  const words = answerWords(report);
  const index = chosen !== null && chosen < report.cases.length ? chosen : governingIndex;
  const chosenCase = report.cases[index];
  const length = unitText(report.units.length);
  const margins = chosenCase ? marginsAlong(views, index, check) : [];
  const gCheck = report.governing && chosenCase ? chosenCase.checks[check === "lowest" ? report.governing.check : check] : null;
  const governingAt = gCheck && gCheck.station !== null && index === governingIndex ? gCheck.station : null;
  return (
    <div className="wing-stage" data-testid="wing-stage" data-state={stale ? "stale" : "current"}>
      <section className="studio-panel wing-answer" data-testid="wing-answer" data-passes={report.passes ? "true" : "false"}>
        <h2>{words.verdict}</h2>
        <p>{words.detail}</p>
        <p className="studio-muted">{words.facts.join(" · ")}{stale ? " · updating for your last change" : ""}</p>
        {problem ? <p className="studio-alert" role="alert">{problem} The results below are for the last wing that could be worked.</p> : null}
      </section>
      {feCheck ? <FeResults check={feCheck} stale={feCheckStale} /> : null}
      {chosenCase ? (
        <section className="studio-panel wing-views">
          <div className="wing-toolbar">
            <label htmlFor="wing-case">Case</label>
            <select id="wing-case" value={index} onChange={(e) => setChosen(Number(e.target.value))} data-testid="wing-case">
              {report.cases.map((c, i) => <option key={i} value={i}>{c.number} {c.label}, {shown(c.altitude, 5)} {report.units.altitude}{i === governingIndex ? " (governs)" : ""}</option>)}
            </select>
            <label htmlFor="wing-check">Check</label>
            <select id="wing-check" value={check} onChange={(e) => setCheck(e.target.value as CheckChoice)} data-testid="wing-check">
              <option value="lowest">Lowest of all</option>
              {CHECK_NAMES.map((n) => <option key={n} value={n}>{CHECK_WORDS[n]}</option>)}
            </select>
          </div>
          <h3>From above</h3>
          <Planform views={views} margins={margins} governingAt={governingAt} units={length} />
          <p className="wing-legend"><span className="wing-swatch" style={{ background: CRITICAL }} /> below 0 <span className="wing-swatch" style={{ background: marginColour(0) }} /> 0
            <span className="wing-swatch" style={{ background: marginColour(0.5) }} /> +0.5 <span className="wing-swatch" style={{ background: marginColour(1) }} /> +1 or more: margin at ultimate load, the box between the spars
            <span><span className="wing-swatch wing-swatch-line" /> line of shear centers</span><span><span className="wing-swatch wing-swatch-ring" /> where the case governs</span></p>
          <h3>Margins along the span</h3>
          <MarginChart views={views} index={index} units={length} />
          <p className="wing-legend">{CHECK_NAMES.map((n, k) => <span key={n}><span className="wing-swatch" style={{ background: CATEGORICAL[k] }} /> {CHECK_WORDS[n]} </span>)}</p>
          <div className="wing-toolbar">
            <h3>Root section</h3>
            <div className="wing-toggle" role="group" aria-label="What the walls show">
              <button type="button" aria-pressed={field === "shear_flow"} onClick={() => setField("shear_flow")}>Shear flow</button>
              <button type="button" aria-pressed={field === "load"} onClick={() => setField("load")}>Spanwise load</button>
            </div>
          </div>
          <Section views={views} index={index} field={field} units={report.units} />
          <p className="studio-muted" data-testid="wing-views-note">Case {chosenCase.number}, {chosenCase.label}: root shear {shown(chosenCase.root_shear, 4)} {unitText(report.units.force)}, moment {shown(chosenCase.root_moment, 4)} {unitText(report.units.moment)}, torque {shown(chosenCase.root_torque, 4)} {unitText(report.units.moment)}; tip {shown(chosenCase.tip_deflection, 3)} {unitText(report.units.deflection)} up, twist {shown(chosenCase.tip_twist, 3)}°.
            {gCheck ? ` ${CHECK_WORDS[check === "lowest" && report.governing ? report.governing.check : (check as WingCheckName)]}: ${marginText(gCheck.margin_ultimate)}, ${whereWords(gCheck, report.units)}.` : ""}</p>
        </section>
      ) : null}
      <section className="studio-panel">
        <h3>The wing</h3>
        <Design report={report} />
      </section>
      {report.cases.length ? (
        <section className="studio-panel">
          <h3>Margins at ultimate load, every case</h3>
          <Cases report={report} selected={index} onSelect={setChosen} />
        </section>
      ) : null}
      {report.not_run.length ? (
        <section className="studio-panel" data-testid="wing-not-run">
          <h3>Cases waiting for inputs</h3>
          <ul className="wing-needs">{report.not_run.map((n) => <li key={`${n.number}@${n.altitude}`}>{n.number} {n.label} at {shown(n.altitude, 5)} {report.units.altitude}: needs {n.needs}</li>)}</ul>
        </section>
      ) : null}
    </div>
  );
}
