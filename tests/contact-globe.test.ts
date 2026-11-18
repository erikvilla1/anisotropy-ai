import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import { flat, graticule, isNear, limbCut, nearRuns, seenAs, toVector, turnMatrix, turned, vectorsOf, type Place } from "../components/contact/globe-math";

// The contact page's globe: the geometry it is drawn with (components/contact/globe-math.ts) and the lines it draws
// (lib/globe-land.json, written by scripts/globe-land.mjs).

const close = (actual: number, expected: number, within = 1e-9) => assert.ok(Math.abs(actual - expected) <= within, `${actual} is not ${expected}`);

test("the place that faces the eye is drawn in the middle, a place a quarter turn away on the limb, and the far side is told apart", () => {
  for (const turn of [{ lon: 0, lat: 0 }, { lon: -122, lat: 18 }, { lon: 151, lat: -34 }, { lon: 179.5, lat: 60 }]) {
    const facing = turned([turn.lon, turn.lat], turn);
    close(facing[0], 0);
    close(facing[1], 0);
    close(facing[2], 1);
    assert.deepEqual(flat(facing).map((value) => Math.round(value * 1e9) / 1e9 + 0), [0, 0]);
    // The place straight across the globe is in the middle too, on the far side.
    const across = turned([turn.lon + 180, -turn.lat], turn);
    close(across[2], -1);
    assert.equal(isNear(across), false);
    assert.equal(isNear(facing), true);
  }
  // Untilted, a quarter turn to the east is on the limb at the right, and the north pole on the limb at the top.
  const level = { lon: 10, lat: 0 };
  const east = turned([100, 0], level);
  close(east[0], 1);
  close(east[2], 0);
  close(Math.hypot(...flat(east)), 1);
  const pole = turned([0, 90], level);
  close(pole[1], 1);
  close(pole[2], 0);
  // A little further round is far, a little nearer is near.
  assert.equal(isNear(turned([101, 0], level)), false);
  assert.equal(isNear(turned([99, 0], level)), true);
  // East is to the right and north is up; seen a little from above, the north pole comes towards the eye.
  assert.ok(turned([20, 0], level)[0] > 0);
  assert.ok(turned([10, 20], level)[1] > 0);
  assert.ok(turned([0, 90], { lon: 0, lat: 18 })[2] > 0);
  // A turn keeps every point on the sphere.
  const matrix = turnMatrix({ lon: -122, lat: 18 });
  for (const place of [[0, 0], [45, 45], [-170, -80], [123.4, 5.6]] as Place[]) close(Math.hypot(...seenAs(toVector(place), matrix)), 1);
});

test("a line that goes round to the far side is cut on the limb, and starts again on the limb where it comes back", () => {
  const level = turnMatrix({ lon: 0, lat: 0 });
  // Along the equator from the middle to the far side: cut where it meets the limb, at the right.
  const out = nearRuns(vectorsOf([[0, 0], [60, 0], [120, 0], [170, 0]]), level);
  assert.equal(out.length, 1);
  assert.equal(out[0].length, 6); // two near points and the cut
  close(Math.hypot(out[0][4], out[0][5]), 1, 1e-6);
  close(out[0][4], 1, 1e-6);
  close(out[0][5], 0, 1e-6);
  // All the way round: two parts, the second starting on the limb at the left.
  const round = nearRuns(vectorsOf([[0, 0], [60, 0], [120, 0], [180, 0], [240, 0], [300, 0], [350, 0]]), level);
  assert.equal(round.length, 2);
  close(Math.hypot(round[0][round[0].length - 2], round[0][round[0].length - 1]), 1, 1e-6);
  close(Math.hypot(round[1][0], round[1][1]), 1, 1e-6);
  close(round[1][0], -1, 1e-6);
  // Every cut is on the limb however the globe is turned, and no drawn point is outside the disc.
  const tilted = turnMatrix({ lon: -122, lat: 18 });
  const meridian: Place[] = [];
  for (let lat = -85; lat <= 85; lat += 5) meridian.push([40, lat]);
  const far: Place[] = [];
  for (let lon = 0; lon <= 360; lon += 5) far.push([lon, 30]);
  for (const line of [meridian, far]) {
    const runs = nearRuns(vectorsOf(line), tilted);
    assert.ok(runs.length >= 1);
    for (const run of runs) {
      assert.ok(run.length >= 4 && run.length % 2 === 0);
      for (let index = 0; index < run.length; index += 2) assert.ok(Math.hypot(run[index], run[index + 1]) <= 1 + 1e-6);
    }
  }
  const parallel = nearRuns(vectorsOf(far), tilted);
  for (const run of parallel) {
    const ends = [Math.hypot(run[0], run[1]), Math.hypot(run[run.length - 2], run[run.length - 1])];
    // A part that was cut ends on the limb; the 30th parallel is cut at both ends when seen from 18 degrees north.
    for (const end of ends) close(end, 1, 1e-6);
  }
  // A line wholly on the far side draws nothing, one wholly near is one part with every point, and a single near point is no line.
  assert.deepEqual(nearRuns(vectorsOf([[170, 0], [180, 10], [-170, 0]]), level), []);
  assert.equal(nearRuns(vectorsOf([[-10, 0], [0, 10], [10, 0]]), level)[0].length, 6);
  assert.deepEqual(nearRuns(vectorsOf([[0, 0]]), level), []);
  // The cut itself: between a near and a far point, on the limb.
  const cut = limbCut(toVector([80, 10]), toVector([100, 10]));
  close(Math.hypot(...cut), 1, 1e-12);
  assert.ok(cut[0] > 0.9);
});

test("the net under the coasts is a line every 30 degrees, of places on the globe", () => {
  const net = graticule(30);
  assert.equal(net.length, 12 + 5); // twelve meridians and five parallels between the poles
  for (const line of net) {
    assert.ok(line.length >= 2);
    for (const [lon, lat] of line) assert.ok(Math.abs(lon) <= 180 + 1e-9 && Math.abs(lat) <= 90 + 1e-9);
  }
});

test("the globe's lines say where they come from and are places on the globe, small enough to send", () => {
  const record = JSON.parse(readFileSync("lib/globe-land.json", "utf8")) as { what: string; source: string; licence: string[]; made_by: string; lines: [number, number][][] };
  assert.match(record.source, /world-atlas.*countries-110m\.json.*Natural Earth/);
  assert.match(record.source, /public domain/);
  // The package's licence asks that its notice goes with every copy: it is in the file, word for word.
  assert.ok(record.licence.some((line) => line.includes("ISC")));
  assert.ok(record.licence.some((line) => line.startsWith("Copyright ")));
  assert.ok(record.licence.some((line) => line.includes("provided that the above copyright notice and this permission notice appear in all copies")));
  assert.equal(record.made_by, "scripts/globe-land.mjs");
  assert.ok(record.lines.length > 200, `${record.lines.length} lines`);
  let points = 0;
  for (const line of record.lines) {
    assert.ok(line.length >= 2, "a line has two points or more");
    for (const place of line) {
      points += 1;
      assert.equal(place.length, 2);
      const [lon, lat] = place;
      assert.ok(Number.isFinite(lon) && Number.isFinite(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90, `${lon}, ${lat}`);
      assert.ok(Math.abs(lon * 10 - Math.round(lon * 10)) < 1e-6 && Math.abs(lat * 10 - Math.round(lat * 10)) < 1e-6, "to a tenth of a degree");
    }
  }
  assert.ok(points > 5000, `${points} points`);
  assert.ok(statSync("lib/globe-land.json").size < 120 * 1024, `${statSync("lib/globe-land.json").size} bytes`);
  // Every line draws: turned any way, its near parts stay on the disc.
  const matrix = turnMatrix({ lon: -122, lat: 18 });
  let drawn = 0;
  for (const line of record.lines) {
    for (const run of nearRuns(vectorsOf(line), matrix)) {
      drawn += 1;
      for (let index = 0; index < run.length; index += 2) assert.ok(Math.hypot(run[index], run[index + 1]) <= 1 + 1e-5);
    }
  }
  assert.ok(drawn > 100, `${drawn} parts on the near side`);
});
