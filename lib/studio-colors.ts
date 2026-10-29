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

export type Scale = { kind: "sequential" | "diverging"; min: number; max: number; stops: string[] };

/** The scale for a field: diverging when it changes sign, around zero and symmetric; sequential otherwise. */
export function scaleFor(values: (number | null)[], forceSequential = false): Scale {
  const finite = values.filter((v): v is number => v !== null && Number.isFinite(v));
  let min = finite.length ? Math.min(...finite) : 0, max = finite.length ? Math.max(...finite) : 1;
  if (min === max) { min -= 1; max += 1; }
  if (!forceSequential && min < 0 && max > 0) {
    const bound = Math.max(-min, max);
    return { kind: "diverging", min: -bound, max: bound, stops: DIVERGING };
  }
  return { kind: "sequential", min, max, stops: SEQUENTIAL };
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

/** Legend ticks from min to max, inclusive, rounded to show cleanly. */
export function legendTicks(scale: Scale, count = 5): number[] {
  return Array.from({ length: count }, (_, i) => scale.min + (scale.max - scale.min) * i / (count - 1));
}

/** A number as the legend and the readout print it: four significant digits, no trailing noise. */
export function printed(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1e5 || magnitude < 1e-3) return value.toExponential(3);
  return String(Number(value.toPrecision(4)));
}

/** The categorical slot of each distinct ply angle, in order of first appearance from the bottom ply. */
export function angleSlots(angles: number[]): Map<number, string> {
  const slots = new Map<number, string>();
  for (const angle of angles) if (!slots.has(angle)) slots.set(angle, CATEGORICAL[slots.size % CATEGORICAL.length]);
  return slots;
}
