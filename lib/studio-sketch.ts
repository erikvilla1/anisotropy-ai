/** A sketch of the typed rows, drawn before any check (ADR-0062): the rectangle, the tab bands, the hole, the supports and noses of a
 * bending coupon and a plate's drawn boxes, each at the position the engineer typed. Nothing here is a result: the sketch is labelled
 * "not meshed", the thickness is a proportion of plies times ply thickness so the slab reads as a laminate, and no number is printed
 * from it (ADR-0001). The mesh, the held sets and the loads come from the package once the setup is checked (ADR-0051). */
import { BENDING_TESTS, FOUR_POINT_TEST, OPEN_HOLE_TEST, PLATE_TEST, unitLabels, unitsOf, type StudioForm } from "./studio-form";
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
};

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
  const listed = pliesOf(form).filter((text) => NUMBER.test(text)).length;
  const plies = form.symmetric === "yes" ? 2 * listed : listed;
  const plyThickness = positive(form.ply_thickness) ?? libraryThickness(form);
  const toScale = plies > 0 && plyThickness !== null && plyThickness > 0;
  const thickness = toScale ? plies * (plyThickness as number) : 0.02 * Math.max(width, length);
  return { width, length, thickness, toScale, tabs, hole, supports, noses, boxes, plies, lengthUnit: unitLabels(unitsOf(form)).length };
}
