import test from "node:test";
import assert from "node:assert/strict";
import { quadTransform, topFace, bridgeFrame, type Point, type Rect } from "../components/home/tour-bridge";
import { BRIDGE, STEPS, TOTAL, finalView, layupScript, viewAt } from "../components/home/tour-timeline";
import { DEFAULT_LAYUP } from "../lib/home-calculator";
import { expandLayup } from "../lib/layup";

// The tour's clock and the bridge's geometry (components/home/tour-timeline.ts, tour-bridge.ts): what is on screen at a scroll
// position, and where the hero's clip is carried. No laminate quantity is involved.

const parsed = expandLayup(DEFAULT_LAYUP).layup!;
const script = layupScript(DEFAULT_LAYUP, parsed.angles.length, parsed.symmetric);
const at = (t: number) => viewAt(t, script, parsed.angles.length, "25000");
const range = (id: string) => STEPS.find((step) => step.id === id)!;

test("a listed ply starts when the slash or bracket that ends its angle is typed; the mirrored plies follow the s, in order", () => {
  assert.deepEqual(script.starts.slice(0, 4), [4, 8, 10, 13]); // "[45/", "[45/-45/", "[45/-45/0/", "[45/-45/0/90]"
  assert.equal(script.starts.length, 8);
  for (let i = 1; i < script.starts.length; i++) assert.ok(script.starts[i] > script.starts[i - 1]);
  assert.ok(script.starts[4] > DEFAULT_LAYUP.length);
  // A notation the plain reading does not follow lays every ply after the typing.
  const repeated = expandLayup("[±45]2").layup!;
  const other = layupScript("[±45]2", repeated.angles.length, repeated.symmetric);
  assert.equal(other.starts.length, repeated.angles.length);
  assert.ok(other.starts.every((start) => start > "[±45]2".length));
});

test("the steps follow the bridge in order and fill the tour's length", () => {
  assert.equal(STEPS[0].start, BRIDGE);
  for (let i = 1; i < STEPS.length; i++) assert.equal(STEPS[i].start, STEPS[i - 1].end);
  assert.equal(STEPS[STEPS.length - 1].end, TOTAL);
  assert.deepEqual(STEPS.map((step) => step.id), ["material", "layup", "engine", "loads", "handover"]);
});

test("the scroll only ever adds: typing, laid plies and the engine's stages never go back as the page scrolls on", () => {
  let before = at(range("layup").at(0.06));
  for (let t = range("layup").at(0.06); t <= TOTAL; t += 0.005) {
    const now = at(t);
    assert.ok(now.layupChars >= before.layupChars);
    assert.ok(now.laid >= before.laid - 1e-9);
    assert.ok(now.engine >= before.engine);
    assert.ok(now.loadChars >= before.loadChars);
    assert.ok(now.step >= before.step);
    before = now;
  }
});

test("each moment of the tour shows what its step says", () => {
  const start = at(0);
  assert.equal(start.step, -1);
  assert.equal(start.laid, 8); // the whole stack stands behind the hero's clip
  assert.equal(start.explode, 0);
  assert.equal(at(BRIDGE).explode, 1); // the plies have separated when the bridge ends
  const material = at(range("material").at(0.7));
  assert.deepEqual([material.step, material.picked, material.constants, material.layupChars], [0, true, 1, 0]);
  const typing = at(range("layup").at(0.4));
  assert.equal(typing.step, 1);
  assert.ok(typing.layupChars > 0 && typing.layupChars < DEFAULT_LAYUP.length);
  assert.ok(typing.laid > 0 && typing.laid < 8);
  const laid = at(range("layup").at(0.9));
  assert.deepEqual([laid.layupChars, laid.laid, laid.thickness], [DEFAULT_LAYUP.length, 8, true]);
  assert.deepEqual([at(range("engine").at(0.05)).engine, at(range("engine").at(0.2)).engine, at(range("engine").at(0.45)).engine, at(range("engine").at(0.8)).engine], [0, 1, 2, 3]);
  const before = at(range("loads").at(0.3));
  assert.deepEqual([before.loaded, before.mark], [false, false]);
  const loaded = at(range("loads").at(0.8));
  assert.deepEqual([loaded.step, loaded.loadChars, loaded.loaded, loaded.mark], [3, 5, true, true]);
  const end = at(TOTAL);
  assert.deepEqual([end.step, end.explode, end.mark, end.laid], [4, 0, false, 8]);
  const whole = finalView(script, 8, "25000");
  assert.deepEqual([whole.layupChars, whole.laid, whole.engine, whole.loadChars, whole.loaded], [DEFAULT_LAYUP.length, 8, 3, 5, true]);
});

/** A point of the source rectangle carried by a CSS matrix3d (column-major), with the perspective divide. */
function carried(matrix: string, [x, y]: Point): Point {
  const m = matrix.slice("matrix3d(".length, -1).split(",").map(Number);
  const w = m[3] * x + m[7] * y + m[15];
  return [(m[0] * x + m[4] * y + m[12]) / w, (m[1] * x + m[5] * y + m[13]) / w];
}

test("the bridge's transform carries the corners of the kept part of the clip onto the four points it is given", () => {
  const from: Rect = { x: 20, y: 0, width: 1400, height: 900 };
  const to: [Point, Point, Point, Point] = [[594.6, 339.2], [935.8, 374.5], [910.6, 481.6], [472.5, 419.9]];
  const matrix = quadTransform(from, to);
  const corners: Point[] = [[20, 0], [1420, 0], [1420, 900], [20, 900]];
  corners.forEach((corner, index) => {
    const [x, y] = carried(matrix, corner);
    assert.ok(Math.abs(x - to[index][0]) < 1e-3 && Math.abs(y - to[index][1]) < 1e-3, `corner ${index}: ${x}, ${y}`);
  });
});

test("the top ply's face is a convex quadrilateral inside the view, and it turns with the camera", () => {
  for (const azimuth of [-24, 0, 14]) {
    const face = topFace(634, 900, azimuth);
    for (const [x, y] of face) assert.ok(x > 0 && x < 634 && y > 0 && y < 900);
    // Convex and wound one way: every turn has the same sign.
    const turns = face.map((point, i) => {
      const a = face[(i + 1) % 4], b = face[(i + 2) % 4];
      return (a[0] - point[0]) * (b[1] - a[1]) - (a[1] - point[1]) * (b[0] - a[0]);
    });
    assert.ok(turns.every((turn) => turn > 0) || turns.every((turn) => turn < 0));
  }
  assert.notDeepEqual(topFace(634, 900, 0), topFace(634, 900, 10));
});

test("the bridge starts from the hero as it is and ends with the clip gone from the ply", () => {
  const geometry = { media: { x: 0, y: 0, width: 1440, height: 900 }, view: { x: 364, y: 0, width: 634, height: 900 } };
  const rest = bridgeFrame(0, geometry);
  assert.deepEqual([rest.copy, rest.shade, rest.opacity, rest.media], [1, 1, 1, true]);
  assert.deepEqual(carried(rest.transform, [1440, 900]), [1440, 900]);
  const landed = bridgeFrame(0.72, geometry);
  const face = topFace(634, 900, -24).map(([x, y]) => [x + 364, y]);
  const [x, y] = carried(landed.transform, [20, 0]); // the kept part's top left corner (the clip is cut to the face's proportions)
  assert.ok(Math.abs(x - face[0][0]) < 0.01 && Math.abs(y - face[0][1]) < 0.01);
  assert.equal(landed.copy, 0);
  const done = bridgeFrame(0.9, geometry);
  assert.deepEqual([done.opacity, done.media], [0, false]);
});
