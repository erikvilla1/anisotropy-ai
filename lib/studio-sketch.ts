/** A sketch of the typed rows, drawn before any check (ADR-0062): the rectangle or the dog-bone (ADR-0075), the tab bands, the hole, the
 * supports and noses of a bending coupon and a plate's drawn boxes, each at the position the engineer typed. Nothing here is a result: the sketch is labelled
 * "not meshed", the thickness is a proportion of plies times ply thickness so the slab reads as a laminate, and no number is printed
 * from it (ADR-0001). The mesh, the held sets and the loads come from the package once the setup is checked (ADR-0051). */
import { BENDING_TESTS, DOGBONE_TEST, FOUR_POINT_TEST, isIsotropic, OPEN_HOLE_TEST, PLATE_TEST, standardOf, unitLabels, unitsOf, type StudioForm } from "./studio-form";
import { libraryThickness, pliesOf } from "./studio-chat";
import type { PlateLists } from "./studio-plate";

export type SketchBox = { name: string; x0: number; x1: number; y0: number; y1: number };
export type Sketch = {
  /** x, across the coupon, and y, along the load (ADR-0004), in the coupon's own length unit. */
  width: number; length: number;
  /** The drawn thickness: plies times ply thickness when both are typed or recorded, else a thin slab; a proportion, not a result. */
  thickness: number; toScale: boolean;
  /** The tab length at each end, when the test has tabs. */
  tabs: number | null;
  hole: number | null;
  /** Support lines and loading-nose lines of a bending coupon, as y positions. */
  supports: number[]; noses: number[];
  boxes: SketchBox[];
  plies: number;
  lengthUnit: string;
  /** Bonded tabs as typed (ADR-0072): their thickness and their bevel in degrees, drawn on both faces of each tab; null without them. */
  tabThickness: number | null; tabBevel: number | null;
  /** The strain measurement: its device and gauge length, drawn as two knife edges centred on the coupon; null when it is not typed or does
   * not fit between the tabs. */
  strain: { device: string; length: number } | null;
  /** The standard picked and its specimen, for the caption. */
  standard: string | null; specimen: string | null;
  /** A dog-bone (ADR-0075): its narrow section and its outline as a closed polygon of (x, y) points; null for a straight strip or sizes that make
   * no dog-bone, which the check refuses by row. */
  dogbone: { narrowWidth: number; narrowLength: number; radius: number; outerRadius: number | null; outline: [number, number][] } | null;
  /** One isotropic material, drawn at its typed thickness (ADR-0075); false for plies. */
  isotropic: boolean;
};

/** The dog-bone's outline as the engine draws it (`fea/src/anisotropy_fea/dogbone.py`, ADR-0075), in the coupon's length unit: a narrow
 * section of half-width a over half its length l, a fillet of radius R tangent to it, then the full half-width b, reached at a corner or,
 * with an outer radius RO (D638 Type IV), through a second arc tangent to both. Plain geometry for the drawing; null when the sizes make no
 * dog-bone (the check says why, by row). */
export type DogboneOutline = { a: number; b: number; l: number; R: number; RO: number | null; sTangent: number; sFull: number; halfLength: number };

export function dogboneOutline(narrowWidth: number, narrowLength: number, radius: number, outerRadius: number | null, width: number, length: number): DogboneOutline | null {
  const a = narrowWidth / 2, b = width / 2, l = narrowLength / 2, R = radius;
  if (!(narrowWidth < width) || !(narrowLength < length)) return null;
  const step = b - a;
  let sTangent: number, sFull: number;
  if (outerRadius === null) {
    if (step > R) return null;
    sTangent = sFull = l + Math.sqrt(R ** 2 - (R - step) ** 2);
  } else {
    const dx = a + R - (b - outerRadius);
    if (dx <= 0 || dx >= R + outerRadius) return null;
    const dy = Math.sqrt((R + outerRadius) ** 2 - dx ** 2);
    sFull = l + dy;
    sTangent = l + (dy * R) / (R + outerRadius);
  }
  if (!(sFull < length / 2)) return null;
  return { a, b, l, R, RO: outerRadius, sTangent, sFull, halfLength: length / 2 };
}

/** The half-width at a distance s from mid-length, either side. */
export function halfWidthAt(o: DogboneOutline, s: number): number {
  const d = Math.abs(s);
  if (d <= o.l) return o.a;
  if (d <= o.sTangent) return o.a + o.R - Math.sqrt(Math.max(o.R ** 2 - (d - o.l) ** 2, 0));
  if (d < o.sFull && o.RO !== null) return o.b - o.RO + Math.sqrt(Math.max(o.RO ** 2 - (d - o.sFull) ** 2, 0));
  return o.b;
}

/** The outline as a closed polygon, counterclockwise: up the right edge from the bottom end to the top, then down the left edge, each arc
 * in `n` chords; x runs across from 0 to the width, y along from 0 to the length (ADR-0004). */
export function outlinePoints(o: DogboneOutline, n = 24): [number, number][] {
  const c = o.halfLength;
  const arc = (from: number, to: number) => Array.from({ length: n }, (_, i) => from + ((to - from) * (i + 1)) / n);
  const outwards = [o.l, ...arc(o.l, o.sTangent), ...(o.RO !== null ? arc(o.sTangent, o.sFull) : []), c]; // distances from mid-length
  const along = [...[...outwards].reverse().map((d) => -d), ...outwards]; // from the bottom end to the top end
  const right = along.map((d) => [o.b + halfWidthAt(o, d), c + d] as [number, number]);
  const left = [...along].reverse().map((d) => [o.b - halfWidthAt(o, d), c + d] as [number, number]);
  return [...right, ...left];
}

const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

/** A typed positive number, or null: blank, a word, zero and a negative value draw nothing. */
export function positive(text: string | undefined): number | null {
  const value = (text ?? "").trim();
  if (!NUMBER.test(value)) return null;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function nonNegative(text: string | undefined): number | null {
  const value = (text ?? "").trim();
  if (!NUMBER.test(value)) return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export function sketchOf(form: StudioForm, lists?: PlateLists | null): Sketch | null {
  const width = positive(form.width), length = positive(form.length);
  if (width === null || length === null) return null;
  const bending = BENDING_TESTS.includes(form.test);
  const plate = form.test === PLATE_TEST;
  const tabLength = bending ? null : positive(form.tab_length);
  const tabs = tabLength !== null && 2 * tabLength < length ? tabLength : null;
  const diameter = form.test === OPEN_HOLE_TEST || plate ? positive(form.hole_diameter) : null;
  const hole = diameter !== null && diameter < width ? diameter : null;
  const supports: number[] = [], noses: number[] = [];
  if (bending) {
    const span = positive(form.span), overhang = nonNegative(form.overhang) ?? 0;
    if (span !== null && overhang + span <= length) {
      supports.push(overhang, overhang + span);
      const mid = overhang + span / 2;
      if (form.test === FOUR_POINT_TEST) {
        const loadSpan = positive(form.load_span);
        if (loadSpan !== null && loadSpan < span) noses.push(mid - loadSpan / 2, mid + loadSpan / 2);
      } else noses.push(mid);
    }
  }
  const boxes: SketchBox[] = [];
  if (plate && lists) {
    for (const region of lists.regions) {
      const x0 = nonNegative(region.x0), x1 = nonNegative(region.x1), y0 = nonNegative(region.y0), y1 = nonNegative(region.y1);
      if (x0 === null || x1 === null || y0 === null || y1 === null || x1 <= x0 || y1 <= y0) continue;
      boxes.push({ name: region.name.trim() || `Box ${boxes.length + 1}`, x0, x1, y0, y1 });
    }
  }
  const tabThickness = tabs !== null ? positive(form.tab_thickness) : null;
  const bevel = positive(form.tab_bevel);
  const tabBevel = tabThickness !== null && bevel !== null && bevel <= 90 ? bevel : null;
  const gauge = !bending && !plate ? positive(form.strain_length) : null;
  const device = (form.strain_device ?? "").trim();
  const strain = gauge !== null && device && gauge < length - 2 * (tabs ?? 0) ? { device, length: gauge } : null;
  const profile = standardOf(form);
  const listed = pliesOf(form).filter((text) => NUMBER.test(text)).length;
  const plies = form.symmetric === "yes" ? 2 * listed : listed;
  const plyThickness = positive(form.ply_thickness) ?? libraryThickness(form);
  const toScale = plies > 0 && plyThickness !== null && plyThickness > 0;
  const isotropic = isIsotropic(form);
  const solid = isotropic ? positive(form.thickness) : null; // a plastic is drawn at its typed thickness
  const thickness = solid ?? (toScale && !isotropic ? plies * (plyThickness as number) : 0.02 * Math.max(width, length));
  const narrowWidth = form.test === DOGBONE_TEST ? positive(form.narrow_width) : null;
  const narrowLength = positive(form.narrow_length), radius = positive(form.radius), outerRadius = positive(form.outer_radius);
  const outline = narrowWidth !== null && narrowLength !== null && radius !== null
    ? dogboneOutline(narrowWidth, narrowLength, radius, outerRadius, width, length) : null;
  const dogbone = outline !== null
    ? { narrowWidth: narrowWidth as number, narrowLength: narrowLength as number, radius: radius as number, outerRadius, outline: outlinePoints(outline) } : null;
  return {
    width, length, thickness, toScale, tabs, hole, supports, noses, boxes, plies, lengthUnit: unitLabels(unitsOf(form)).length,
    tabThickness: tabBevel !== null ? tabThickness : null, tabBevel, strain, standard: profile?.designation ?? null,
    specimen: profile?.variant_words.length && form.specimen ? form.specimen : null, dogbone, isotropic,
    ...(isotropic ? { toScale: solid !== null, plies: 0 } : {}),
  };
}
