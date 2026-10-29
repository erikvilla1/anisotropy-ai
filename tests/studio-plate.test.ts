import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emptyPlate, plateFromValues, plateValues, plateWords, regionOptions, regionsOfElement, withLoad, withSupport, PLATE_TEST } from "../lib/studio-plate";
import { blankForm, buildValues, sectionsFor } from "../lib/studio-form";
import { readPreview } from "../lib/studio-api";

const values = JSON.parse(readFileSync("tests/fixtures/studio-plate/values.json", "utf8"));
const preview = readPreview(JSON.parse(readFileSync("tests/fixtures/studio-plate/preview.json", "utf8")));

test("a plate's form hides the grips and the loading rows and sends its lists (ADR-0054)", () => {
  const form = { ...blankForm(), test: PLATE_TEST, length: "100", width: "100" };
  const keys = sectionsFor(form).flatMap((s) => s.fields.map((f) => f.key));
  assert.ok(keys.includes("tab_length") && keys.includes("hole_diameter") && keys.includes("length"));
  for (const key of ["grips", "region", "control", "value", "span"]) assert.ok(!keys.includes(key), key);
  const lists = plateFromValues(values);
  assert.equal(lists.supports.length, 6);
  assert.deepEqual(lists.loads, [{ region: "Face", kind: "pressure", pressure: "-0.01" }]);
  assert.equal(lists.regions[1].name, "Corner-X");
  const built = buildValues(form, plateValues(lists));
  assert.deepEqual(built.loads, [{ region: "Face", pressure: -0.01 }]);
  assert.deepEqual((built.supports as Record<string, unknown>[])[4], { region: "Corner-Origin", dofs: [1, 2] });
  assert.deepEqual((built.regions as Record<string, unknown>[])[0], { name: "Corner-Origin", x0: 0, x1: 0.1, y0: 0, y1: 0.1 });
  assert.ok(!("supports" in buildValues({ ...form, test: "unnotched tension" }, plateValues(lists)))); // a coupon never sends the lists
  const blankValue = plateValues({ ...emptyPlate(), supports: [{ region: "Edge-Top", dofs: [2], value: " " }] });
  assert.deepEqual(blankValue.supports, [{ region: "Edge-Top", dofs: [2] }]); // a blank travel is left out so the check judges the row
});

test("the regions a plate offers follow the form, the boxes and the hole", () => {
  const form = { ...blankForm(), test: PLATE_TEST, tab_length: "20" };
  const names = regionOptions(form, { ...emptyPlate(), regions: [{ name: "Patch", x0: "1", x1: "2", y0: "1", y1: "2" }] }).map((o) => o.name);
  assert.deepEqual(names, ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Face", "Tab-Bottom", "Tab-Top", "Patch"]);
  const withHole = regionOptions({ ...form, tab_length: "", hole_diameter: "6" }, emptyPlate());
  assert.ok(withHole.some((o) => o.name === "Hole" && o.kind === "edge") && !withHole.some((o) => o.name === "Tab-Top"));
});

test("a click on an element names the regions it touches, and the buttons add rows", () => {
  const form = { ...blankForm(), test: PLATE_TEST, length: "100", width: "100" };
  const lists = plateFromValues(values);
  const options = regionOptions(form, lists);
  const corner = regionsOfElement(0, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, options).map((r) => r.name);
  assert.deepEqual(corner, ["Edge-Bottom", "Edge-Left", "Face", "Corner-Origin"]); // the first element sits at the origin
  const middle = regionsOfElement(136, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, options).map((r) => r.name);
  assert.deepEqual(middle, ["Face"]);
  const held = withSupport(emptyPlate(), "Edge-Left");
  assert.deepEqual(held.supports, [{ region: "Edge-Left", dofs: [1, 2, 3], value: "" }]);
  const loaded = withLoad(withLoad(held, "Face", "area"), "Edge-Top", "edge");
  assert.deepEqual(loaded.loads, [{ region: "Face", kind: "pressure", pressure: "" }, { region: "Edge-Top", kind: "force", dof: 3, total: "" }]);
  assert.equal(plateWords(loaded)[0], "Edge-Left holds x, y, z");
  assert.ok(plateWords(loaded)[1].includes("Face under a pressure of ? MPa"));
});

test("the plate preview lists every load with its region and the regions the plate offers", () => {
  assert.equal(preview.loads?.length, 1);
  assert.equal(preview.loads?.[0].control, "pressure");
  assert.equal(preview.loads?.[0].direction, "+z"); // a negative Abaqus pressure pushes along the normal
  assert.deepEqual(preview.regions, { edges: ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right"], areas: ["Face", "Corner-Origin", "Corner-X"] });
  assert.equal(preview.held.filter((h) => h.set === "Edge-Left").length, 2); // dof 3 and dof 4, one boundary line each
});
