import { test } from "node:test";
import assert from "node:assert/strict";
import { angleSlots, CATEGORICAL, colorAt, colorsOf, DIVERGING, hexToRgb, legendTicks, printed, ramp, scaleFor, SEQUENTIAL } from "../lib/studio-colors";

test("the ramps: one hue dark to light for a magnitude, two hues around a neutral grey for a signed field", () => {
  assert.equal(SEQUENTIAL.length, 7);
  const first = hexToRgb(SEQUENTIAL[0]), last = hexToRgb(SEQUENTIAL[SEQUENTIAL.length - 1]);
  assert.ok(first[0] + first[1] + first[2] < last[0] + last[1] + last[2]);
  assert.equal(DIVERGING[3], "#9ba29b"); // the neutral midpoint is the theme's muted grey
  assert.deepEqual(ramp(SEQUENTIAL, 0), first);
  assert.deepEqual(ramp(SEQUENTIAL, 1), last);
  assert.deepEqual(ramp(SEQUENTIAL, 2), last); // clamped
});

test("the scale follows the field's sign", () => {
  const magnitude = scaleFor([0, 1, 2.5]);
  assert.equal(magnitude.kind, "sequential");
  assert.deepEqual([magnitude.min, magnitude.max], [0, 2.5]);
  const signed = scaleFor([-1, 0.2, 3]);
  assert.equal(signed.kind, "diverging");
  assert.deepEqual([signed.min, signed.max], [-3, 3]); // symmetric, so the grey sits at zero
  assert.deepEqual(colorAt(signed, 0), hexToRgb("#9ba29b"));
  assert.equal(scaleFor([-1, 3], true).kind, "sequential");
  const flat = scaleFor([2, 2, 2]);
  assert.ok(flat.min < 2 && flat.max > 2);
  assert.equal(scaleFor([null, null]).kind, "sequential");
});

test("colours are flat triples and a missing value is the named grey", () => {
  const scale = scaleFor([0, 10]);
  const colours = colorsOf(scale, [0, 10, null]);
  assert.equal(colours.length, 9);
  assert.deepEqual(colours.slice(0, 3), hexToRgb(SEQUENTIAL[0]));
  assert.deepEqual(colours.slice(6, 9), hexToRgb("#3a3f3b"));
});

test("legend ticks and printed numbers", () => {
  assert.deepEqual(legendTicks({ kind: "sequential", min: 0, max: 100, stops: SEQUENTIAL }, 5), [0, 25, 50, 75, 100]);
  assert.equal(printed(123.456789), "123.5");
  assert.equal(printed(0.000012345), "1.234e-5");
  assert.equal(printed(2787.75), "2788");
  assert.equal(printed(0), "0");
  assert.equal(printed(null), "–");
});

test("ply angles take fixed slots in order of first appearance", () => {
  const slots = angleSlots([45, 0, -45, 90, 90, -45, 0, 45]);
  assert.deepEqual([...slots.entries()], [[45, CATEGORICAL[0]], [0, CATEGORICAL[1]], [-45, CATEGORICAL[2]], [90, CATEGORICAL[3]]]);
});
