import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  boundaryEdges, boundaryOwners, bounds, centroid, deformedPositions, elementEdges, elementLoop, elementOfTriangle, nodeMeans, plateMesh, quadsToTriangles,
  setBox, suggestedScale, vertexColors,
} from "../lib/studio-geometry";

const preview = JSON.parse(readFileSync("tests/fixtures/studio/preview.json", "utf8"));
const fieldsFile = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8"));
const square = { nodes: [[0, 0], [1, 0], [1, 1], [0, 1], [2, 0], [2, 1]], quads: [[0, 1, 2, 3], [1, 4, 5, 2]] };

function signedArea(p: number[][], tri: number[]): number {
  const [a, b, c] = tri.map((i) => p[i]);
  return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]));
}

test("two triangles per quad, keeping the counterclockwise orientation", () => {
  const triangles = quadsToTriangles(square.quads);
  assert.deepEqual(triangles, [0, 1, 2, 0, 2, 3, 1, 4, 5, 1, 5, 2]);
  for (let t = 0; t < triangles.length; t += 3) assert.ok(signedArea(square.nodes, triangles.slice(t, t + 3)) > 0);
  assert.equal(elementOfTriangle(3), 1);
  const all = quadsToTriangles(preview.mesh.quads);
  assert.equal(all.length, 6 * preview.mesh.element_count);
  for (let t = 0; t < all.length; t += 3) assert.ok(signedArea(preview.mesh.nodes, all.slice(t, t + 3)) > 0);
});

test("the boundary is the edges one quad owns", () => {
  const edges = boundaryEdges(square.quads);
  assert.equal(edges.length, 6); // a 2 by 1 strip has six outer edges
  assert.ok(!edges.some(([a, b]) => (a === 1 && b === 2) || (a === 2 && b === 1)));
  const outline = boundaryEdges(preview.mesh.quads);
  const { size } = bounds(preview.mesh.nodes);
  assert.equal(outline.length, 2 * (Math.round(size[0] / 5) + Math.round(size[1] / 5))); // 5 mm elements around a 25 by 250 mm plate
});

test("the plate is a closed surface: both faces and a wall per boundary edge, four vertices per element face", () => {
  const plate = plateMesh(square.nodes, square.quads, 0.5);
  assert.equal(plate.elementCount, 2);
  assert.equal(plate.vertexNode.length, 4 * 2 + 4 * 2 + 4 * 6);
  assert.equal(plate.positions.length, 3 * plate.vertexNode.length);
  assert.equal(plate.positions[2], 0.25);
  assert.equal(plate.positions[3 * 8 + 2], -0.25);
  assert.equal(plate.topTriangles, 4);
  assert.equal(plate.triangles.length, 3 * (4 + 4 + 2 * 6));
  const at = (v: number) => [plate.positions[3 * v], plate.positions[3 * v + 1]];
  const area = (tri: number[]) => signedArea(tri.map(at), [0, 1, 2]);
  for (let t = 0; t < 12; t += 3) assert.ok(area(plate.triangles.slice(t, t + 3)) > 0); // the top face, seen from +z
  for (let t = 12; t < 24; t += 3) assert.ok(area(plate.triangles.slice(t, t + 3)) < 0); // the bottom face, reversed
  assert.deepEqual(plate.vertexElement.slice(0, 8), [0, 0, 0, 0, 1, 1, 1, 1]);
  assert.deepEqual(boundaryOwners(square.quads).sort(), [0, 0, 0, 1, 1, 1]);
  const big = plateMesh(preview.mesh.nodes, preview.mesh.quads, preview.geometry.thickness);
  assert.equal(big.triangles.length, 3 * (2 * 2 * preview.mesh.element_count + 2 * boundaryEdges(preview.mesh.quads).length));
  const smooth = vertexColors(plate, "node", square.nodes.flatMap((_, i) => [i, i, i]));
  assert.deepEqual(smooth.slice(0, 6), [0, 0, 0, 1, 1, 1]);
  const flat = vertexColors(plate, "element", [0.1, 0.1, 0.1, 0.9, 0.9, 0.9]);
  assert.deepEqual(flat.slice(0, 3), [0.1, 0.1, 0.1]);
  assert.deepEqual(flat.slice(12, 15), [0.9, 0.9, 0.9]);
  assert.equal(elementLoop(square.nodes, square.quads[1], 0.25).length, 4);
  assert.equal(elementEdges(square.nodes, square.quads, 0.25).length, 7);
});

test("deformed positions and the display scale", () => {
  const moved = deformedPositions(square.nodes, square.nodes.map(() => [1, 2]), 10);
  assert.deepEqual(moved[0], [10, 20]);
  const scale = suggestedScale(fieldsFile.mesh.nodes, fieldsFile.nodal.magnitude);
  const largest = Math.max(...fieldsFile.nodal.magnitude);
  assert.ok(scale * largest >= 10 && scale * largest <= 50, `${scale}`); // about a tenth of 250 mm, rounded to one digit
  assert.equal(suggestedScale(square.nodes, [0, 0]), 1);
});

test("where a set sits", () => {
  assert.deepEqual(centroid(square.nodes, [0, 1, 2, 3]), [0.5, 0.5]);
  assert.deepEqual(setBox(square.nodes, [4, 5]), { min: [2, 0], max: [2, 1] });
  assert.equal(setBox(square.nodes, []), null);
  const grip = setBox(preview.mesh.nodes, preview.mesh.node_sets["Grip-Bottom"])!;
  assert.deepEqual(grip.min, [0, 0]);
  assert.equal(grip.max[1], preview.geometry.tab_length);
});

test("node means agree with the package's display averages", () => {
  const means = nodeMeans(square.quads, 6, [1, 3]);
  assert.deepEqual(means, [1, 2, 2, 1, 3, 3]);
  const epsY = fieldsFile.element.strain.map((row: number[]) => row[1]);
  const ours = nodeMeans(fieldsFile.mesh.quads, fieldsFile.mesh.node_count, epsY);
  const theirs = fieldsFile.nodal.averages.strain.map((row: (number | null)[]) => row[1]);
  for (let i = 0; i < ours.length; i++) {
    if (ours[i] === null) assert.equal(theirs[i], null);
    else assert.ok(Math.abs(ours[i]! - theirs[i]!) <= 1e-9 * Math.max(1, Math.abs(ours[i]!)), `node ${i}`);
  }
});
