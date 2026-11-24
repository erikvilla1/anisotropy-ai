"use client";

import { useMemo, useState } from "react";
import { CATEGORICAL } from "@/lib/studio-colors";
import { shown, unitText, type BondReport, type RepairReport, type RepairViews, type SliceReport } from "@/lib/repair";

/** The drawings of a repair (ADR-0135), for the repair's page and for its report: the half slice as the engine's rectangles
 * (ADR-0131), the bondline's stresses along the bond, and the forces along the slice. All three share one scale along the slice, `r`
 * from the repair's middle, so a point of a curve stands under the place it belongs to. Every number drawn is the engine's or the
 * solver's; this file scales and draws. */

const WIDTH = 720, LEFT = 64, RIGHT = 18;
/** How far along the slice the drawings reach: a quarter past the repair's edge, or to the panel's end when that comes first. The
 * laminate beyond is uniform and the stresses are the far field's. */
export function reachOf(views: RepairViews): number {
  return Math.min(views.half_length, views.outer * 1.25);
}
const xOf = (reach: number) => (r: number) => LEFT + (Math.min(Math.max(r, 0), reach) / reach) * (WIDTH - LEFT - RIGHT);

/** The colour of each ply angle, in order of first appearance from the laminate's bottom ply up (the fixed slots of lib/studio-colors). */
export function angleColours(report: RepairReport): Map<number, string> {
  const colours = new Map<number, string>();
  for (const region of [...report.regions].sort((a, b) => a.z0 - b.z0)) {
    if (region.kind === "adhesive" || region.angle === null || colours.has(region.angle)) continue;
    colours.set(region.angle, CATEGORICAL[colours.size % CATEGORICAL.length]);
  }
  return colours;
}
const angleText = (angle: number) => `${String(angle).replace("-", "−")}°`;

/** The half slice through the repair's middle, along the load: every ply of the laminate, the patch and the cover plies, and the
 * adhesive between them, as the engine's rectangles. The thickness is drawn many times larger than the length, and the caption says
 * by how much. */
export function SliceDrawing({ report, views }: { report: RepairReport; views: RepairViews }) {
  const reach = reachOf(views);
  const X = xOf(reach);
  const zLow = Math.min(...report.regions.map((g) => g.z0)), zHigh = Math.max(...report.regions.map((g) => g.z1));
  const top = 26, tall = 132, bottom = 34;
  const zScale = tall / (zHigh - zLow), xScale = (WIDTH - LEFT - RIGHT) / reach;
  const Y = (z: number) => top + (zHigh - z) * zScale;
  const colours = useMemo(() => angleColours(report), [report]);
  const length = unitText(report.units.length);
  const shownRegions = report.regions.filter((g) => g.r0 < reach);
  const stretch = Math.round(zScale / xScale);
  return (
    <svg viewBox={`0 0 ${WIDTH} ${top + tall + bottom}`} className="wing-svg repair-svg" role="img" data-testid="repair-slice"
      aria-label={`The half slice through the repair, from its middle to ${shown(reach)} ${length} along the load; the thickness is drawn about ${stretch} times larger than the length`}>
      {shownRegions.map((g, i) => {
        const adhesive = g.kind === "adhesive";
        const x = X(g.r0), w = Math.max(X(g.r1) - x, adhesive ? 1.6 : 0.6), y = Y(g.z1), h = Math.max(Y(g.z0) - y, adhesive ? 1.6 : 0.6);
        return (
          <rect key={i} x={x} y={y} width={w} height={h} data-kind={g.kind}
            className={adhesive ? "repair-adhesive" : g.kind === "parent" ? "repair-ply" : "repair-ply repair-ply-patch"}
            fill={adhesive ? undefined : colours.get(g.angle ?? 0)}>
            <title>{`${g.name}: ${shown(g.r0)} to ${shown(g.r1)} ${length} from the middle, ${shown(g.z1 - g.z0, 3)} ${length} thick`}</title>
          </rect>
        );
      })}
      {/* each ply's angle where its rectangle is tall and long enough to hold the figure */}
      {shownRegions.filter((g) => g.kind !== "adhesive" && g.angle !== null && (g.z1 - g.z0) * zScale >= 10 && (Math.min(g.r1, reach) - g.r0) * xScale >= 34).map((g, i) => (
        <text key={`a-${i}`} x={g.kind === "parent" ? X(Math.min(g.r1, reach)) - 6 : X(g.r0) + 6} y={Y((g.z0 + g.z1) / 2) + 3} textAnchor={g.kind === "parent" ? "end" : "start"}
          className="repair-svg-ply">{angleText(g.angle as number)}</text>
      ))}
      <line x1={X(0)} x2={X(0)} y1={top - 12} y2={top + tall + 10} className="repair-middle" />
      <text x={X(0) + 5} y={top - 12} className="wing-label wing-label-small">Middle of the repair</text>
      <text x={WIDTH - RIGHT} y={top - 12} textAnchor="end" className="wing-label wing-label-small">
        {reach < views.half_length ? `the laminate runs on to the panel's end, ${shown(views.half_length)} ${length} →` : "panel's end"}
      </text>
      {views.boundaries.filter((b) => b.r <= reach).map((b, i) => (
        <g key={`b-${i}`}>
          <line x1={X(b.r)} x2={X(b.r)} y1={top + tall + 2} y2={top + tall + 8} className="repair-tick" />
          <text x={X(b.r)} y={top + tall + 21} textAnchor={b.r === 0 ? "start" : "middle"} className="wing-label wing-label-small">{shown(b.r, 3)}</text>
        </g>
      ))}
      <text x={WIDTH - RIGHT} y={top + tall + 21} textAnchor="end" className="wing-label wing-label-small">{length} from the middle</text>
    </svg>
  );
}

/** The key of the slice's drawing: each ply angle's colour, the patch's outline and the adhesive. */
export function SliceLegend({ report }: { report: RepairReport }) {
  const colours = useMemo(() => angleColours(report), [report]);
  return (
    <p className="wing-legend" data-testid="repair-slice-legend">
      {[...colours.entries()].map(([angle, colour]) => <span key={angle}><span className="wing-swatch" style={{ background: colour }} />{angleText(angle)}</span>)}
      <span><span className="wing-swatch repair-swatch-patch" />{report.kind === "external" ? "patch plies" : "patch and cover plies"}</span>
      <span><span className="wing-swatch repair-swatch-adhesive" />adhesive</span>
    </p>
  );
}

/** Round steps for an axis that holds `low` to `high`: about five of them, each 1, 2 or 5 times a power of ten. */
export function axisTicks(low: number, high: number): number[] {
  const span = high - low;
  if (!(span > 0)) return [low];
  const raw = span / 5, power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const ticks: number[] = [];
  for (let k = Math.ceil(low / step - 1e-9); k * step <= high + 1e-9 * span; k += 1) ticks.push(Number((k * step).toPrecision(12)));
  return ticks;
}

type Series = { id: string; label: string; colour: string; dashed?: boolean; lines: { r: number[]; value: number[] }[] };

/** One chart along the slice: series as lines over `r`, the lap's step boundaries as upright lines, zero marked, and under it the
 * values at the place the pointer is over. */
function AlongChart({ series, views, unit, lengthUnit, label, testId, height = 210 }: {
  series: Series[]; views: RepairViews; unit: string; lengthUnit: string; label: string; testId: string; height?: number;
}) {
  const reach = reachOf(views);
  const X = xOf(reach);
  const top = 14, bottom = 30;
  const all = series.flatMap((s) => s.lines.flatMap((line) => line.value.filter((_, i) => line.r[i] <= reach)));
  const lowest = Math.min(0, ...all), highest = Math.max(0, ...all);
  const pad = (highest - lowest || 1) * 0.06;
  const low = lowest < 0 ? lowest - pad : 0, high = highest + pad;
  const Y = (v: number) => top + (1 - (v - low) / (high - low)) * (height - top - bottom);
  const ticks = axisTicks(low, high);
  const [at, setAt] = useState<number | null>(null);
  const readout = at === null ? null : series.map((s) => {
    // the stored point nearest the pointer, within a twentieth of the reach: nothing is interpolated
    let best: { gap: number; r: number; value: number } | null = null;
    for (const line of s.lines) line.r.forEach((r, i) => { const gap = Math.abs(r - at); if (!best || gap < best.gap) best = { gap, r, value: line.value[i] }; });
    const found = best as { gap: number; r: number; value: number } | null;
    return found && found.gap <= reach / 20 ? { ...s, r: found.r, value: found.value } : null;
  }).filter((s): s is Series & { r: number; value: number } => s !== null);
  const move = (event: React.MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * WIDTH;
    setAt(x < LEFT || x > WIDTH - RIGHT ? null : ((x - LEFT) / (WIDTH - LEFT - RIGHT)) * reach);
  };
  return (
    <>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} className="wing-svg repair-svg" role="img" aria-label={label} data-testid={testId} onMouseMove={move} onMouseLeave={() => setAt(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={LEFT} x2={WIDTH - RIGHT} y1={Y(t)} y2={Y(t)} className={t === 0 ? "repair-zero" : "wing-grid"} />
            <text x={LEFT - 6} y={Y(t) + 4} textAnchor="end" className="wing-label wing-label-small">{shown(t, 3)}</text>
          </g>
        ))}
        <text x={12} y={top + (height - top - bottom) / 2} className="wing-label wing-label-small" textAnchor="middle" transform={`rotate(-90 12 ${top + (height - top - bottom) / 2})`}>{unit}</text>
        {views.boundaries.filter((b) => b.r <= reach).map((b, i) => (
          <g key={i}>
            <line x1={X(b.r)} x2={X(b.r)} y1={top} y2={height - bottom} className="repair-boundary"><title>{`${b.name}, ${shown(b.r)} ${lengthUnit} from the middle`}</title></line>
            <text x={X(b.r)} y={height - bottom + 15} textAnchor={b.r === 0 ? "start" : "middle"} className="wing-label wing-label-small">{shown(b.r, 3)}</text>
          </g>
        ))}
        <text x={WIDTH - RIGHT} y={height - 2} textAnchor="end" className="wing-label wing-label-small">{lengthUnit} from the middle</text>
        {series.map((s) => s.lines.map((line, k) => {
          const points = line.r.map((r, i) => (r <= reach ? `${X(r).toFixed(1)},${Y(line.value[i]).toFixed(1)}` : null)).filter(Boolean).join(" ");
          return points ? <polyline key={`${s.id}-${k}`} points={points} fill="none" stroke={s.colour} strokeWidth={2} strokeDasharray={s.dashed ? "6 4" : undefined}
            strokeLinejoin="round" data-series={s.id} /> : null;
        }))}
        {at !== null ? <line x1={X(at)} x2={X(at)} y1={top} y2={height - bottom} className="repair-cursor" /> : null}
        {(readout ?? []).map((s) => <circle key={s.id} cx={X(s.r)} cy={Y(s.value)} r={4} fill={s.colour} className="repair-dot" />)}
      </svg>
      <p className="wing-legend repair-chart-key" data-testid={`${testId}-key`}>
        {series.map((s) => (
          <span key={s.id}><span className={`wing-swatch repair-swatch-line${s.dashed ? " repair-swatch-dashed" : ""}`} style={{ borderTopColor: s.colour }} />{s.label}</span>
        ))}
        <span className="repair-readout" aria-live="off">{readout && readout.length
          ? readout.map((s) => `${s.label} ${shown(s.value)} ${unit} at ${shown(s.r)} ${lengthUnit}`).join(" · ") : "Point at the chart to read a value."}</span>
      </p>
    </>
  );
}

/** The adhesive's stresses along the bond: the hand calculation's shear stress and, once the slice is solved, the slice's shear and
 * peel stress, each the mean through the bondline's thickness. `stale` says the slice was solved for an earlier repair; its lines are
 * then left out, since they would stand under a slice they do not belong to. */
export function BondChart({ report, views, slice, stale = false }: { report: RepairReport; views: RepairViews; slice: SliceReport | null; stale?: boolean }) {
  const stress = unitText(report.units.stress), length = unitText(report.units.length);
  const series: Series[] = [];
  if (views.lap) series.push({ id: "hand", label: "Shear by hand", colour: CATEGORICAL[0], dashed: true, lines: [{ r: views.lap.r, value: views.lap.shear }] });
  if (slice && !stale) {
    series.push({ id: "shear", label: "Shear, solved slice", colour: CATEGORICAL[1], lines: slice.bond.lines.map((line) => ({ r: line.r, value: line.shear })) });
    series.push({ id: "peel", label: "Peel, solved slice", colour: CATEGORICAL[2], lines: slice.bond.lines.map((line) => ({ r: line.r, value: line.peel })) });
  }
  if (!series.length) return <p className="studio-muted" data-testid="repair-bond-empty">The bondline&apos;s stresses are drawn once a load is stated.</p>;
  return <AlongChart series={series} views={views} unit={stress} lengthUnit={length} testId="repair-bond-chart"
    label={`The adhesive's stresses along the bond, in ${stress}, against the distance from the repair's middle`} />;
}

/** The force per unit width each part carries along the slice: the patch by hand, and the patch, the laminate and the adhesive by the
 * solved slice. Their sum is the load at every station. */
export function ForceChart({ report, views, slice }: { report: RepairReport; views: RepairViews; slice: SliceReport | null }) {
  const force = unitText(report.units.force), length = unitText(report.units.length);
  const series: Series[] = [];
  if (views.lap) series.push({ id: "hand", label: "Patch by hand", colour: CATEGORICAL[0], dashed: true, lines: [{ r: views.lap.r, value: views.lap.patch_force }] });
  if (slice) {
    series.push({ id: "patch", label: "Patch, solved slice", colour: CATEGORICAL[1], lines: [{ r: slice.forces.r, value: slice.forces.patch }] });
    series.push({ id: "laminate", label: "Laminate, solved slice", colour: CATEGORICAL[3], lines: [{ r: slice.forces.r, value: slice.forces.laminate }] });
  }
  if (!series.length) return null;
  return <AlongChart series={series} views={views} unit={force} lengthUnit={length} testId="repair-force-chart" height={190}
    label={`The force per unit width in the patch and in the laminate along the slice, in ${force}`} />;
}

/** The adhesive's shear stress along the bond of a followed bond (ADR-0137), on the scale of the slice: as the bond first softens,
 * when the stress is at the bond's strength at one point, and at the load at which it lets go, when it has spread: where the bond
 * is softening the stress has fallen from the strength, and where it has parted it carries none. */
export function LetGoChart({ report, views, bond }: { report: RepairReport; views: RepairViews; bond: BondReport }) {
  const state = bond.let_go;
  if (!state) return null;
  const stress = unitText(report.units.stress), length = unitText(report.units.length);
  const series: Series[] = [
    { id: "onset", label: "Shear as the bond first softens", colour: CATEGORICAL[0], dashed: true, lines: bond.onset.lines.map((line) => ({ r: line.r, value: line.shear })) },
    { id: "let-go", label: "Shear as the bond lets go", colour: CATEGORICAL[1], lines: state.lines.map((line) => ({ r: line.r, value: line.shear })) },
  ];
  return <AlongChart series={series} views={views} unit={stress} lengthUnit={length} testId="repair-let-go-chart" height={190}
    label={`The adhesive's shear stress along the bond as it first softens and at the load at which it lets go, in ${stress}, against the distance from the repair's middle`} />;
}

/** The followed bond's path (ADR-0137): the load per unit width against the length of bond past its strength, softening or parted.
 * Nothing is past it until the load at which the bond first softens; from there the softening spreads as the load grows, to the
 * load at which the bond lets go, and the load falls after it. Every point is a state the solver settled; the two loads are marked
 * and named. */
export function LoadCurve({ bond }: { bond: BondReport }) {
  const force = unitText(bond.units.force), length = unitText(bond.units.length);
  const xs = bond.curve.damaged_length, ys = bond.curve.load, moved = bond.curve.end_movement;
  const height = 230, top = 22, bottom = 34;
  const xHigh = Math.max(...xs, 0) * 1.06 || 1, yHigh = Math.max(...ys, 0) * 1.1 || 1;
  const X = (v: number) => LEFT + (v / xHigh) * (WIDTH - LEFT - RIGHT), Y = (v: number) => top + (1 - v / yHigh) * (height - top - bottom);
  const [at, setAt] = useState<number | null>(null); // the stored state nearest the pointer
  const move = (event: React.MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * WIDTH, y = ((event.clientY - box.top) / box.height) * height;
    let best = 0, gap = Infinity;
    xs.forEach((v, i) => { const d = Math.hypot(X(v) - x, Y(ys[i]) - y); if (d < gap) { gap = d; best = i; } });
    setAt(gap <= 60 ? best : null);
  };
  const fell = bond.let_go;
  return (
    <>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} className="wing-svg repair-svg" role="img" data-testid="repair-load-curve" onMouseMove={move} onMouseLeave={() => setAt(null)}
        aria-label={`The load per unit width, in ${force}, against the length of bond past its strength, in ${length}, as the bond softens and lets go`}>
        {axisTicks(0, yHigh).map((t) => (
          <g key={`y-${t}`}>
            <line x1={LEFT} x2={WIDTH - RIGHT} y1={Y(t)} y2={Y(t)} className={t === 0 ? "repair-zero" : "wing-grid"} />
            <text x={LEFT - 6} y={Y(t) + 4} textAnchor="end" className="wing-label wing-label-small">{shown(t, 3)}</text>
          </g>
        ))}
        {axisTicks(0, xHigh).map((t) => (
          <g key={`x-${t}`}>
            <line x1={X(t)} x2={X(t)} y1={height - bottom} y2={height - bottom + 5} className="repair-tick" />
            <text x={X(t)} y={height - bottom + 17} textAnchor="middle" className="wing-label wing-label-small">{shown(t, 3)}</text>
          </g>
        ))}
        <text x={12} y={top + (height - top - bottom) / 2} className="wing-label wing-label-small" textAnchor="middle" transform={`rotate(-90 12 ${top + (height - top - bottom) / 2})`}>{force}</text>
        <text x={WIDTH - RIGHT} y={height - 2} textAnchor="end" className="wing-label wing-label-small">bond past its strength, {length}</text>
        <polyline points={xs.map((v, i) => `${X(v).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join(" ")} fill="none" stroke={CATEGORICAL[0]} strokeWidth={2} strokeLinejoin="round" data-series="load" />
        <g data-mark="onset">
          <circle cx={X(0)} cy={Y(bond.onset.load)} r={4.5} fill={CATEGORICAL[0]} className="repair-dot" />
          <text x={X(0) + 10} y={Y(bond.onset.load) + 4} className="wing-label wing-label-small">first softens, {shown(bond.onset.load)} {force}</text>
        </g>
        {fell ? (
          <g data-mark="let-go">
            <circle cx={X(fell.damaged_length)} cy={Y(fell.load)} r={4.5} fill={CATEGORICAL[0]} className="repair-dot" />
            <text x={X(fell.damaged_length) - 9} y={Y(fell.load) - 8} textAnchor="end" className="wing-label wing-label-small">lets go, {shown(fell.load)} {force}</text>
          </g>
        ) : null}
        {at !== null ? <circle cx={X(xs[at])} cy={Y(ys[at])} r={4} fill="none" stroke={CATEGORICAL[0]} strokeWidth={2} /> : null}
      </svg>
      <p className="wing-legend repair-chart-key" data-testid="repair-load-curve-key">
        <span className="repair-readout" aria-live="off">{at !== null
          ? `${shown(ys[at])} ${force} with ${shown(xs[at])} ${length} of the bond past its strength; the panel's end has moved ${shown(moved[at])} ${length}`
          : "Point at the curve to read a state."}</span>
      </p>
    </>
  );
}

/** The caption under the slice: what is drawn, and by how much the thickness is stretched. */
export function sliceCaption(report: RepairReport, views: RepairViews): string {
  const reach = reachOf(views), length = unitText(report.units.length);
  const zLow = Math.min(...report.regions.map((g) => g.z0)), zHigh = Math.max(...report.regions.map((g) => g.z1));
  const stretch = Math.round((132 / (zHigh - zLow)) / ((WIDTH - LEFT - RIGHT) / reach));
  const last = views.boundaries[views.boundaries.length - 1];
  return `Half of the slice through the repair's middle, along the load. The thickness is drawn about ${stretch} times larger than the length. `
    + `The lap runs from the repair's edge, ${shown(views.outer)} ${length} from the middle, inward to `
    + `${last.r === 0 ? "the middle" : `${report.kind === "external" ? "the hole's edge" : "the deepest cut"}, ${shown(last.r)} ${length} from the middle`}.`;
}
