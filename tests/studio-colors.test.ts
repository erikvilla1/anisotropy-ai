import { test } from "node:test";
import assert from "node:assert/strict";
import { angleSlots, CATEGORICAL, colorAt, colorsOf, DIVERGING, hexToRgb, legendGradient, legendTicks, percentChange, printed, ramp, scaleFor, SEQUENTIAL, settled } from "../lib/studio-colors";

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
  assert.deepEqual(legendTicks({ min: 0, max: 100 }, 5), [0, 25, 50, 75, 100]);
  assert.equal(printed(123.456789), "123.5");
  assert.equal(printed(0.000012345), "1.234 × 10⁻⁵"); // the site's one rule (lib/number-format.ts): no programmer's e-notation
  assert.equal(printed(2787.75), "2788");
  assert.equal(printed(16211.4), "16210"); // plain up to a million, as the Summary prints a reaction
  assert.equal(printed(1.5e6), "1.5 × 10⁶");
  assert.equal(printed(-364.5), "−364.5"); // the minus sign, as the convergence table's percentChange prints it
  assert.equal(printed(0.0026), "0.0026"); // no trailing zeros in a readout
  assert.equal(printed(0), "0");
  assert.equal(printed(null), "–");
});

test("a change from the previous mesh prints signed, two figures under one percent and one decimal above (ADR-0068)", () => {
  assert.equal(percentChange(-0.00023590981), "−0.024 %");
  assert.equal(percentChange(0.11390684), "+11.4 %");
  assert.equal(percentChange(-0.0776955), "−7.8 %");
  assert.equal(percentChange(0), "+0.00 %");
  assert.equal(percentChange(-1e-7), "+0.00 %");
  assert.equal(percentChange(null), "–");
});

test("a component that is noise beside the others in its set prints as zero, a small real one stays", () => {
  assert.deepEqual(settled([479.2, -0.2514, 4.078e-15]), [479.2, -0.2514, 0]);  // the 0° ply's shear under tension is zero, not 4e-15
  assert.deepEqual(settled([-0.001127, 0.003641, 5.883e-7]), [-0.001127, 0.003641, 5.883e-7]);  // CalculiX's small shear strain is a value
  assert.deepEqual(settled([-0.001127, 0.003641, -3.49e-19]), [-0.001127, 0.003641, 0]);
  assert.deepEqual(settled([0, 0, 0]), [0, 0, 0]);
  assert.deepEqual(settled([null, 1e-20, 2]), [null, 0, 2]);
  assert.deepEqual(settled([null, undefined]), [null, undefined]);
});

test("the scale's ends are the package's range when it wrote one, the values' extremes otherwise (ADR-0063)", () => {
  const written = scaleFor([0.2, 0.4], false, [0, 1]);
  assert.deepEqual([written.min, written.max, written.ends, written.source], [0, 1, [0, 1], "package"]);
  const signed = scaleFor([0.2], false, [-2, 1]);
  assert.deepEqual([signed.kind, signed.min, signed.max, signed.ends], ["diverging", -2, 2, [-2, 1]]); // symmetric around the grey; the ends as written
  const fallback = scaleFor([3, null, 7]);
  assert.deepEqual([fallback.ends, fallback.source], [[3, 7], "values"]);
  assert.equal(legendTicks(written, 9).length, 9); // one tick per band boundary
  assert.equal(legendGradient(written, 0), `linear-gradient(to right, ${SEQUENTIAL.join(", ")})`);
  const banded = legendGradient(written, 4);
  assert.ok(banded.startsWith("linear-gradient(to right, rgb(") && banded.includes("% 25%") && banded.endsWith(" 75% 100%)"));
});

test("ply angles take fixed slots in order of first appearance", () => {
  const slots = angleSlots([45, 0, -45, 90, 90, -45, 0, 45]);
  assert.deepEqual([...slots.entries()], [[45, CATEGORICAL[0]], [0, CATEGORICAL[1]], [-45, CATEGORICAL[2]], [90, CATEGORICAL[3]]]);
});
