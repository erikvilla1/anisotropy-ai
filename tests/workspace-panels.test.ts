import { test } from "node:test";
import assert from "node:assert/strict";
import { MATERIAL_KEYS, PANELS, panelOfItem, panelOfKey, panelOfStep, panelState, visibleKeys } from "../lib/workspace-panels";
import { STEP_ORDER, stepOfKey } from "../lib/studio-chat";
import { blankForm, fields, type Checklist } from "../lib/studio-form";

test("every row of the form belongs to exactly one panel, and every checklist item to at most one", () => {
  const counts = new Map(fields.map((field) => [field.key, 0]));
  for (const panel of PANELS) for (const key of panel.keys) counts.set(key, (counts.get(key) ?? -100) + 1);
  const wrong = [...counts.entries()].filter(([, n]) => n !== 1);
  assert.deepEqual(wrong, [], `rows not in exactly one panel: ${wrong.map(([k, n]) => `${k}:${n}`).join(", ")}`);
  const items = PANELS.flatMap((panel) => panel.items);
  assert.equal(new Set(items).size, items.length);
  assert.equal(panelOfKey("length"), "geometry");
  assert.equal(panelOfKey("own_E1"), "layup");
  assert.equal(panelOfKey("name_part"), "advanced");
  assert.equal(panelOfItem("constraints"), "loads");
  assert.equal(panelOfItem("solver"), "run");
  assert.ok(MATERIAL_KEYS.includes("G13") && !MATERIAL_KEYS.includes("ply_1") && !MATERIAL_KEYS.includes("symmetric"));
});

test("every step of the assistant's conversation names the panel that holds its rows (ADR-0062, part 5)", () => {
  for (const step of STEP_ORDER) assert.ok(PANELS.some((p) => p.id === panelOfStep(step)), step);
  assert.equal(panelOfStep("geometry"), "geometry");
  assert.equal(panelOfStep("name"), "run");
  // every row a step asks for sits on that step's panel, apart from the project rows (the size's source, the standard) and the name, which Run by fills under Advanced
  const apart = new Set(["size_from", "standard", "units", "notes", "date", "filled_by"]);
  for (const key of fields.map((f) => f.key)) {
    const step = stepOfKey(key);
    if (step === null || step === "review" || apart.has(key)) continue;
    assert.equal(panelOfKey(key), panelOfStep(step), key);
  }
});

test("a panel shows only the rows its test uses, in the definition's order", () => {
  const tension = { ...blankForm(), test: "unnotched tension" };
  assert.deepEqual(visibleKeys(tension, "geometry"), [
    "length", "width", "tab_length", "tab_thickness", "tab_bevel", "tab_material", "strain_device", "strain_length",
  ]);
  assert.deepEqual(visibleKeys(tension, "project"), ["notes", "units", "test", "standard", "size_from"]); // no Specimen row without a standard that names them
  assert.ok(visibleKeys({ ...tension, test: "open-hole tension", standard: "ASTM C1869-18(2023)" }, "project").includes("specimen"));
  assert.deepEqual(visibleKeys(tension, "loads"), ["control", "value", "grips", "region"]);
  const bending = { ...blankForm(), test: "four-point bending" };
  assert.deepEqual(visibleKeys(bending, "geometry"), ["length", "width", "span", "overhang", "load_span"]);
  assert.deepEqual(visibleKeys(bending, "loads"), ["control", "value"]);
  const plate = { ...blankForm(), test: "plate" };
  assert.deepEqual(visibleKeys(plate, "loads"), []);
  assert.ok(visibleKeys(plate, "geometry").includes("hole_diameter"));
  assert.ok(visibleKeys(tension, "mesh").includes("element_size") && !visibleKeys(tension, "mesh").includes("hole_ring"));
});

test("a panel's badge is the worst of its items", () => {
  const checklist: Checklist = {
    designation: "IM7-UNT-L1", coupon_exists: false, attempts: 0, state: "blocked", problems: [],
    items: [
      { id: "identity", label: "Who", state: "pass", message: "", rows: [] }, { id: "units", label: "Units", state: "warn", message: "", rows: [] },
      { id: "geometry", label: "Geometry", state: "missing", message: "Length (mm): required", rows: ["Length (mm)"] },
      { id: "material", label: "Material", state: "pass", message: "", rows: [] }, { id: "laminate", label: "Laminate", state: "pass", message: "", rows: [] },
      { id: "criterion", label: "Criterion", state: "warn", message: "", rows: [] },
    ],
  };
  assert.equal(panelState("project", checklist), "warn");
  assert.equal(panelState("geometry", checklist), "missing");
  assert.equal(panelState("layup", checklist), "warn");
  assert.equal(panelState("loads", checklist), "none"); // no item of the loads panel in this checklist
  assert.equal(panelState("geometry", null), "none");
});
