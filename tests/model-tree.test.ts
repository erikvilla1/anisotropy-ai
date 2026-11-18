import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { IMPORTED_TABS, MODEL_TREE, TAB_OF_STEP, builtFor, importedLines, listLine, loadLine, meshLine, plateMissing, sizeLine, tabOfKey, tabState, tabToFix } from "../lib/model-tree";
import { blankForm, type Checklist } from "../lib/studio-form";
import { SHOWN_BUILT, TENSION_KEYS } from "../lib/tension-screen";
import { bannedIn } from "../lib/studio-copy";

const checklist = (items: [string, Checklist["items"][number]["state"]][]): Checklist => ({
  items: items.map(([id, state]) => ({ id, label: id, state, message: "", rows: [] })), designation: null, coupon_exists: false, attempts: 1,
  state: "ready", problems: [],
});

test("the tree's tabs are in the order a model is set up, each row of the tension screen and each choice of the software in one tab (ADR-0111)", () => {
  assert.deepEqual(MODEL_TREE.map((t) => t.title), ["Test", "Geometry", "Material", "Layup", "Analysis step", "Boundary conditions", "Loads", "Mesh",
    "Solve", "Results"]);
  const keys = MODEL_TREE.flatMap((t) => t.keys);
  assert.deepEqual([...keys].sort(), [...TENSION_KEYS].sort(), "every row the screen sends, and only those, once");
  const built = MODEL_TREE.flatMap((t) => t.built);
  assert.deepEqual([...built].sort(), [...SHOWN_BUILT].sort(), "every choice the software shows, once");
  // the words of finite element analysis, no program's own (ADR-0091)
  for (const t of MODEL_TREE) assert.deepEqual(bannedIn(t.title), [], t.title);
  // every step of the assistant's conversation opens a tab
  for (const id of Object.values(TAB_OF_STEP)) assert.ok(MODEL_TREE.some((t) => t.id === id), id);
});

test("a row, a failing item and the software's choices are each found in their tab (ADR-0111)", () => {
  assert.equal(tabOfKey("element_size"), "mesh");
  assert.equal(tabOfKey("value"), "loads");
  assert.equal(tabOfKey("ply_3"), "layup");
  assert.equal(tabOfKey("own_E1"), "material");
  assert.equal(tabOfKey("grips"), null, "a coupon's grips are its test's, changed by no row");
  assert.equal(tabToFix({ id: "geometry", rows: ["Width (mm)"] }), "geometry");
  assert.equal(tabToFix({ id: "laminate", rows: ["Ply 1 (bottom)"] }), "layup");
  assert.equal(tabToFix({ id: "constraints", rows: [] }), "conditions");
  assert.equal(tabToFix({ id: "nothing", rows: [] }), null);
  const lines = ["width", "grips", "element_size", "control"].map((key) => ({ key, label: key, value: "", reason: "" }));
  assert.deepEqual(builtFor("conditions", lines).map((l) => l.key), ["grips"]);
  assert.deepEqual(builtFor("loads", lines).map((l) => l.key), ["control"]);
});

test("a tab shows the worst state of the items that judge it, and none before a check (ADR-0111)", () => {
  assert.equal(tabState("mesh", null), "none");
  assert.equal(tabState("mesh", checklist([["mesh", "pass"], ["probes", "warn"], ["load", "fail"]])), "warn");
  assert.equal(tabState("loads", checklist([["mesh", "pass"], ["load", "fail"]])), "fail");
  assert.equal(tabState("step", checklist([["mesh", "fail"]])), "none");
});

test("each closed tab says its values in one line, from the rows given or the software's choices (ADR-0111)", () => {
  const form = { ...blankForm(), element_size: "" }; // a blank form holds the form's own 2 mm; here every row is left to the software
  assert.equal(sizeLine(form, {}), null);
  assert.equal(sizeLine(form, { length: "250", width: "25", tab_length: "56" }), "250 × 25 mm, 56 mm tabs");
  assert.equal(sizeLine({ ...form, width: "15" }, { length: "250", width: "25" }), "250 × 15 mm", "the engineer's row wins over the choice");
  assert.equal(loadLine(form, { value: "1" }, "displacement"), "1 mm pull");
  assert.equal(loadLine({ ...form, control: "force", value: "10000" }, {}, null), "10000 N pull");
  assert.equal(loadLine(form, {}, null), null);
  assert.equal(meshLine(form, { element_size: "2" }, 1500), "2 mm elements, 1500 in all");
  assert.equal(meshLine({ ...form, units: "in-psi", element_size: "0.08" }, {}, null), "0.08 in elements");
  assert.equal(meshLine(form, {}, null), null);
});

test("an imported model's tabs are the tree's own, each line the reader's report; a plate says what it still needs (ADR-0111 amendment 1, ADR-0089 amendment 7)", () => {
  const reading = JSON.parse(readFileSync("tests/fixtures/studio-import/import.json", "utf8")).reading;
  const titles = IMPORTED_TABS.map((id) => MODEL_TREE.find((t) => t.id === id)?.title);
  assert.deepEqual(titles, ["Geometry", "Material", "Layup", "Analysis step", "Boundary conditions", "Loads", "Mesh", "Solve", "Results"]);
  assert.deepEqual(importedLines(reading), {
    geometry: "1 part, 1 instance", material: "IM7-8552", layup: "[0/30/-30/30/0]s, 10 plies", step: "Static, linear",
    conditions: "12 boundary lines, 2 couplings", loads: "by moved supports only", mesh: "16 elements, 27 nodes",
  });
  assert.equal(importedLines({ ...reading, layup: "", pressures: 1, concentrated_loads: 2 }).layup, "none stated");
  assert.equal(importedLines({ ...reading, layup: "", pressures: 1, concentrated_loads: 2 }).loads, "2 force lines, 1 pressure line");
  // a plate: something held, and a load or a held region that moves
  const support = { region: "Edge-Left", dofs: [1, 2, 3], value: "" };
  assert.deepEqual(plateMissing({ supports: [], loads: [], regions: [] }), ["a boundary condition", "a load"]);
  assert.deepEqual(plateMissing({ supports: [{ ...support, value: "0.1" }], loads: [], regions: [] }), []);
  assert.deepEqual(plateMissing({ supports: [support], loads: [], regions: [] }), ["a load"]);
  assert.equal(listLine([{ region: "Edge-Left" }, { region: "Edge-Left" }, { region: "Face" }]), "3 on Edge-Left, Face");
  assert.equal(listLine([]), null);
  assert.equal(tabOfKey("hole_diameter"), "geometry");
});
