import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { appliedOf } from "../lib/applied";
import type { Preview } from "../lib/studio-api";
import { sampleNodes } from "../lib/studio-geometry";
import { nodesOf, proposedInputs, sceneInputs } from "../components/studio/scene-inputs";

const fixture = (name: string): Preview => JSON.parse(readFileSync(new URL(`./fixtures/${name}/preview.json`, import.meta.url), "utf8"));

test("a coupon's boundary conditions and load are listed once each, in the words the model's list and the assistant use (ADR-0110)", () => {
  const applied = appliedOf(fixture("studio"));
  assert.deepEqual(applied.conditions.map((c) => [c.set, c.dofs, c.words]), [
    ["Grip-Bottom", [1, 2, 3, 4, 5, 6], "Bottom grip: fixed (encastre)"],
    ["Grip-Top", [1, 3, 4, 5, 6], "Top grip: free to move along the coupon only"],
  ]);
  assert.deepEqual(applied.loads.map((l) => l.words), ["Top grip: pulled 1 mm along the coupon"]); // `loaded` is also in `loads`: said once
  assert.deepEqual(applied.model, ["IM7-8552-Lamina", "[45/0/-45/90]s, 8 plies", "250 shell elements", "one linear static step"]);
});

test("a plate's and an imported model's every load is listed, not only the first (ADR-0110)", () => {
  const plate = fixture("studio-plate");
  const twoLoads = { ...plate, loads: [...(plate.loads ?? []), { set: "Edge-Right", through: null, control: "force", dof: 1, direction: "+x", value: 500, unit: "N", nodes: 17 }] };
  assert.deepEqual(appliedOf(twoLoads).loads.map((l) => l.words), ["Face: pressure −0.01 MPa along +z", "Edge-Right: force 500 N along +x"]);
  const scene = sceneInputs(twoLoads);
  assert.equal(scene.loads.length, 2);
  assert.ok(scene.loads[0].nodes.length > 200, "a pressure on the face covers the face's nodes");
  assert.deepEqual(scene.loads[1].nodes, plate.mesh.node_sets["Edge-Right"]);
  const imported = appliedOf(fixture("studio-import"));
  assert.deepEqual(imported.conditions.map((c) => c.words), ["S_Bottom_CNS_: fixed (encastre)", "S_Top_CNS_: free to move along the coupon only"]);
  assert.deepEqual(imported.loads.map((l) => l.words), ["S_Top_CNS_: pulled 0.8 mm along the coupon"]);
});

test("a region's nodes come from the mesh drawn, its node set or its elements' corners (ADR-0110)", () => {
  const plate = fixture("studio-plate");
  assert.deepEqual(nodesOf(plate, "Edge-Left"), plate.mesh.node_sets["Edge-Left"]);
  assert.deepEqual(nodesOf(plate, "Nowhere"), []);
  assert.deepEqual(nodesOf(plate, "Edge-Left", { node_sets: { "Edge-Left": [1, 2] } }), [1, 2]); // the results' own mesh first
});

test("what the assistant proposes on a plate is drawn with its directions, a pressure pressing down along -z (ADR-0110)", () => {
  const plate = fixture("studio-plate");
  const drawn = proposedInputs(plate, {
    supports: [{ region: "Edge-Bottom", dofs: [2, 4, 6] }],
    loads: [{ region: "Face", kind: "pressure", dof: null, value: "0.1", unit: "MPa" }, { region: "Edge-Right", kind: "force", dof: 1, value: "-500", unit: "N" }],
  });
  assert.ok(drawn);
  assert.deepEqual(drawn.held.map((h) => [h.dofs, h.label]), [[[2, 4, 6], "Edge-Bottom: held along y, rotation about x, rotation about z (YSYMM)"]]);
  assert.deepEqual(drawn.loads.map((l) => [l.direction, l.control, l.label]), [["-z", "pressure", "Face: pressure 0.1 MPa along -z"], ["-x", "force", "Edge-Right: force 500 N along -x"]]);
  assert.equal(proposedInputs(plate, null), null);
  assert.equal(proposedInputs(plate, { supports: [], loads: [] }), null);
});

test("a boundary condition's symbols and a load's arrows sit at a few nodes spread over the region (ADR-0110)", () => {
  // a 5 by 5 grid of nodes, 0 to 4 along x and y
  const grid = Array.from({ length: 25 }, (_, k) => [k % 5, Math.floor(k / 5)]);
  const all = grid.map((_, k) => k);
  assert.deepEqual(sampleNodes(grid, all, 2, 4), [0, 4, 20, 24]); // an area: its corners
  assert.deepEqual(sampleNodes(grid, all, 3, 5), [0, 2, 4, 10, 12, 14, 20, 22, 24]);
  assert.deepEqual(sampleNodes(grid, all, 2, 4, 0.25), [6, 8, 16, 18]); // kept in from the edges, off the line where the field changes
  const bottom = [0, 1, 2, 3, 4];
  assert.deepEqual(sampleNodes(grid, bottom, 3, 5), [0, 1, 2, 3, 4]); // a line: end to end
  assert.deepEqual(sampleNodes(grid, bottom, 3, 3), [0, 2, 4]);
  assert.deepEqual(sampleNodes(grid, bottom, 3, 3, 0.25), [0, 2, 4]); // a line still runs end to end
  assert.deepEqual(sampleNodes(grid, [7], 3, 5), [7]);
  assert.deepEqual(sampleNodes(grid, [], 3, 5), []);
});
