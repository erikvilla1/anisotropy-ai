import { test } from "node:test";
import assert from "node:assert/strict";
import { positive, sketchOf } from "../lib/studio-sketch";
import { blankForm, exampleForm } from "../lib/studio-form";

test("the sketch draws only typed positive numbers, and nothing without a width and a length", () => {
  assert.equal(positive("250"), 250);
  assert.equal(positive(" 2.5e1 "), 25);
  assert.equal(positive("0"), null);
  assert.equal(positive("-3"), null);
  assert.equal(positive("abc"), null);
  assert.equal(positive(""), null);
  assert.equal(sketchOf(blankForm()), null);
  assert.equal(sketchOf({ ...blankForm(), width: "25" }), null);
  assert.equal(sketchOf({ ...blankForm(), width: "25", length: "wide" }), null);
});

test("the tension example sketches its tabs and its thickness from the plies, an open hole its hole", () => {
  const example = exampleForm("2026-11-06");
  const sketch = sketchOf(example)!;
  assert.deepEqual([sketch.width, sketch.length, sketch.tabs, sketch.hole], [25, 250, 56, null]);
  assert.deepEqual([sketch.supports, sketch.noses, sketch.boxes], [[], [], []]);
  assert.equal(sketch.plies, 8); // [45/0/-45/90]s: four listed, mirrored
  assert.ok(sketch.toScale && sketch.thickness > 0); // the library records IM7/8552's ply thickness
  assert.equal(sketch.lengthUnit, "mm");
  const hole = sketchOf({ ...example, test: "open-hole tension", hole_diameter: "6" })!;
  assert.equal(hole.hole, 6);
  assert.equal(sketchOf({ ...example, test: "open-hole tension", hole_diameter: "30" })!.hole, null); // wider than the coupon: not drawn
  assert.equal(sketchOf({ ...example, tab_length: "200" })!.tabs, null); // tabs longer than the coupon: not drawn
  const thin = sketchOf({ ...example, library: "", ply_thickness: "" })!;
  assert.equal(thin.toScale, false);
  assert.equal(thin.thickness, 0.02 * 250);
});

test("a bending coupon sketches its supports and noses from the span and overhang, a plate its drawn boxes", () => {
  const three = sketchOf({ ...blankForm(), test: "three-point bending", width: "13", length: "60", span: "48", overhang: "6" })!;
  assert.deepEqual(three.supports, [6, 54]);
  assert.deepEqual(three.noses, [30]);
  assert.equal(three.tabs, null);
  const four = sketchOf({ ...blankForm(), test: "four-point bending", width: "13", length: "60", span: "48", overhang: "6", load_span: "16" })!;
  assert.deepEqual(four.noses, [22, 38]);
  assert.deepEqual(sketchOf({ ...blankForm(), test: "three-point bending", width: "13", length: "60", span: "70" })!.supports, []); // longer than the coupon
  const plate = sketchOf({ ...blankForm(), test: "plate", width: "100", length: "100", hole_diameter: "10" },
    { supports: [], loads: [], regions: [{ name: "Patch", x0: "10", x1: "30", y0: "40", y1: "60" }, { name: "Bad", x0: "5", x1: "5", y0: "0", y1: "1" }] })!;
  assert.deepEqual(plate.boxes, [{ name: "Patch", x0: 10, x1: 30, y0: 40, y1: 60 }]);
  assert.equal(plate.hole, 10);
  assert.equal(sketchOf({ ...blankForm(), test: "plate", width: "100", length: "100" }, null)!.boxes.length, 0);
});
