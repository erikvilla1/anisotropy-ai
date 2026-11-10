/**
 * How the studio colours a field (ADR-0051), by the job the colour does: a magnitude takes one hue from dark to light, a signed
 * field takes two hues with a neutral grey midpoint at zero, and the plies' angles take fixed categorical slots (the same four hues
 * in the same order wherever they appear, each ply also labelled). The surface is the site's dark theme. Colours never carry a
 * number: the legend's ticks and the readout do.
 */

export type RGB = [number, number, number]; // 0..1

/** One hue, the site's accent green, from the dark surface to near white: for |u|, stresses as magnitudes, the failure index. */
export const SEQUENTIAL = ["#10170f", "#1f3a1c", "#376330", "#5d8f52", "#8fbb80", "#c1deb5", "#eef5e8"];
/** Two hues with a neutral grey at the midpoint: cool for negative, warm for positive. */
export const DIVERGING = ["#2a78d6", "#5d95dd", "#8eb0e0", "#9ba29b", "#e0a07c", "#df7a4c", "#d95926"];
/** Fixed categorical slots for the ply angles, in order of first appearance (the reference palette's first slots, dark steps). */
export const CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];
export const CRITICAL = "#e66767"; // the status colour for the critical element's outline, with its label beside it
export const HELD = "#9085e9"; // a held set's frame
export const LOADED = "#c98500"; // the loaded set's frame and the arrow

export function hexToRgb(hex: string): RGB {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function lerp(a: RGB, b: RGB, t: number): RGB { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

/** A colour along a ramp at t in [0, 1]. */
export function ramp(stops: string[], t: number): RGB {
  const clamped = Math.min(1, Math.max(0, t));
  const position = clamped * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(position));
  return lerp(hexToRgb(stops[i]), hexToRgb(stops[i + 1]), position - i);
}

export type Scale = {
  kind: "sequential" | "diverging"; min: number; max: number; stops: string[];
  /** The field's ends: the range the package wrote, or the smallest and largest value shown when it wrote none. */
  ends: [number, number]; source: "package" | "values";
};

/** The scale for a field: its ends are the range the package wrote (ADR-0063) or, for a job solved before the package wrote ranges, the
 * smallest and largest of the values shown (picked, not computed); diverging when it changes sign, around zero and symmetric; sequential otherwise. */
export function scaleFor(values: (number | null)[], forceSequential = false, range: [number, number] | null = null): Scale {
  let ends: [number, number];
  let source: Scale["source"];
  if (range) { ends = range; source = "package"; }
  else {
    let lo = Infinity, hi = -Infinity;
    for (const v of values) if (v !== null && Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
    ends = lo <= hi ? [lo, hi] : [0, 1];
    source = "values";
  }
  let [min, max] = ends;
  if (min === max) { min -= 1; max += 1; }
  if (!forceSequential && min < 0 && max > 0) {
    const bound = Math.max(-min, max);
    return { kind: "diverging", min: -bound, max: bound, stops: DIVERGING, ends, source };
  }
  return { kind: "sequential", min, max, stops: SEQUENTIAL, ends, source };
}

export function colorAt(scale: Scale, value: number | null): RGB {
  if (value === null || !Number.isFinite(value)) return hexToRgb("#3a3f3b"); // no value: a mid grey, named in the legend
  return ramp(scale.stops, (value - scale.min) / (scale.max - scale.min));
}

/** Red, green, blue for every value, flat, as a mesh's colour attribute wants it. */
export function colorsOf(scale: Scale, values: (number | null)[]): number[] {
  const out: number[] = [];
  for (const value of values) out.push(...colorAt(scale, value));
  return out;
}

/** Legend ticks from min to max, inclusive: one per band boundary when the contours are banded, so every isoline is labelled. */
export function legendTicks(scale: Pick<Scale, "min" | "max">, count = 5): number[] {
  return Array.from({ length: count }, (_, i) => scale.min + (scale.max - scale.min) * i / (count - 1));
}

/** The legend's bar: the smooth ramp, or one flat step per band, the colour of the band's centre, as the results material paints it. */
export function legendGradient(scale: Pick<Scale, "stops">, bands: number): string {
  if (!bands) return `linear-gradient(to right, ${scale.stops.join(", ")})`;
  const css = (rgb: RGB) => `rgb(${rgb.map((c) => Math.round(c * 255)).join(" ")})`;
  const steps = Array.from({ length: bands }, (_, i) => `${css(ramp(scale.stops, (i + 0.5) / bands))} ${(100 * i) / bands}% ${(100 * (i + 1)) / bands}%`);
  return `linear-gradient(to right, ${steps.join(", ")})`;
}

/** A number as the legend and the readout print it: four significant digits, no trailing noise. */
export function printed(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1e5 || magnitude < 1e-3) return value.toExponential(3);
  return String(Number(value.toPrecision(4)));
}

/** A change from the previous mesh as the convergence table prints it (ADR-0068): signed, two figures under 1 %, one decimal above, a dash for none. */
export function percentChange(change: number | null | undefined): string {
  if (change === null || change === undefined || !Number.isFinite(change)) return "–";
  const magnitude = Math.abs(100 * change);
  const text = magnitude < 0.001 ? "0.00" : magnitude < 1 ? magnitude.toPrecision(2) : magnitude.toFixed(1);
  return `${change < 0 && magnitude >= 0.001 ? "−" : "+"}${text} %`;
}

/** A set of components read together, with the ones that are numerical noise beside the others set to zero: a component below a billionth of the
 *  set's largest magnitude is the solver's arithmetic, not a value (a 4e-15 MPa shear in a 0° ply is zero, and a table that prints it reads
 *  as a difference). A set with no finite value is returned as it is. */
export function settled<T extends number | null | undefined>(values: T[]): T[] {
  const scale = Math.max(0, ...values.map((x) => (typeof x === "number" && Number.isFinite(x) ? Math.abs(x) : 0)));
  return values.map((x) => (typeof x === "number" && Number.isFinite(x) && Math.abs(x) < 1e-9 * scale ? (0 as T) : x));
}

/** The categorical slot of each distinct ply angle, in order of first appearance from the bottom ply. */
export function angleSlots(angles: number[]): Map<number, string> {
  const slots = new Map<number, string>();
  for (const angle of angles) if (!slots.has(angle)) slots.set(angle, CATEGORICAL[slots.size % CATEGORICAL.length]);
  return slots;
}
