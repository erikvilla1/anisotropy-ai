import type { Followed } from "./studio-api";

/** The load against deflection curve of a plate solved with nonlinear geometry (ADR-0142), laid out for drawing. Every number is the
 * package's (`summary.followed`): the page places them and computes none. The curve starts at no load and no displacement; the linear
 * answer is the straight line through the same origin, drawn as far as the plot goes, since at a large load it lies far beyond it. */
export type CurvePoint = { percent: number; value: number; linear: number; x: number; y: number };
export type CurveLayout = {
  width: number; height: number; left: number; right: number; top: number; bottom: number;
  points: CurvePoint[]; path: string;
  /** the linear answer's line, from the origin to where it leaves the plot */
  linear: { x1: number; y1: number; x2: number; y2: number; leaves: boolean };
  xTicks: { x: number; label: string }[]; yTicks: { y: number; label: string }[];
  xMax: number; unit: string;
};

/** A round step that gives about `count` ticks up to `max`: 1, 2 or 5 times a power of ten. */
export function niceStep(max: number, count = 4): number {
  if (!(max > 0)) return 1;
  const raw = max / count, power = 10 ** Math.floor(Math.log10(raw));
  const lead = raw / power;
  return (lead <= 1 ? 1 : lead <= 2 ? 2 : lead <= 5 ? 5 : 10) * power;
}

export function curveLayout(followed: Followed, print: (value: number) => string, width = 360, height = 220): CurveLayout | null {
  const { fractions, curve } = followed;
  if (!fractions.length || curve.values.length !== fractions.length || curve.linear.length !== fractions.length) return null;
  const values = curve.values.map(Math.abs), linear = curve.linear.map(Math.abs);
  const reached = Math.max(...values);
  if (!(reached > 0)) return null;
  const step = niceStep(reached), xMax = Math.ceil(reached / step - 1e-9) * step;
  const left = 46, right = 14, top = 12, bottom = 36;
  const sx = (v: number) => left + ((width - left - right) * v) / xMax;
  const sy = (f: number) => height - bottom - (height - top - bottom) * f;
  const points = fractions.map((f, i) => ({ percent: Math.round(1000 * f) / 10, value: values[i], linear: linear[i], x: sx(values[i]), y: sy(f) }));
  const path = `M${sx(0).toFixed(1)},${sy(0).toFixed(1)}` + points.map((p) => ` L${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");
  // the linear line reaches the full load at its last value; past the plot's edge it is cut where it leaves
  const full = linear[linear.length - 1], last = fractions[fractions.length - 1];
  const leaves = full > xMax;
  const end = leaves ? { v: xMax, f: full > 0 ? (last * xMax) / full : 0 } : { v: full, f: last };
  const xTicks = Array.from({ length: Math.round(xMax / step) + 1 }, (_, i) => ({ x: sx(i * step), label: print(Number((i * step).toPrecision(6))) }));
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({ y: sy(f), label: `${100 * f} %` }));
  return { width, height, left, right, top, bottom, points, path,
    linear: { x1: sx(0), y1: sy(0), x2: sx(end.v), y2: sy(end.f), leaves }, xTicks, yTicks, xMax, unit: curve.unit };
}
