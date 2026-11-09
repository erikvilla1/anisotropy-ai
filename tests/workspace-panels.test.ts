import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MATERIAL_KEYS, NEEDS_TEST, PANELS, panelOfItem, panelOfKey, panelOfStep, panelState, setupLine, stepNumber, stepRequirements, visibleKeys,
} from "../lib/workspace-panels";
import { STEP_ORDER, stepOfKey } from "../lib/studio-chat";
import { blankForm, fieldByKey, fields, NO_STANDARD, testDescription, type Checklist } from "../lib/studio-form";

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
  assert.equal(panelOfKey("test"), "test");
  assert.equal(panelOfKey("standard"), "test");
  assert.equal(panelOfKey("size_from"), "geometry"); // where the size comes from sits beside the sizes a standard names
  assert.equal(panelOfItem("standard"), "test");
  assert.ok(MATERIAL_KEYS.includes("G13") && !MATERIAL_KEYS.includes("ply_1") && !MATERIAL_KEYS.includes("symmetric"));
});

test("every step of the assistant's conversation names the panel that holds its rows (ADR-0062, part 5)", () => {
  for (const step of STEP_ORDER) assert.ok(PANELS.some((p) => p.id === panelOfStep(step)), step);
  assert.equal(panelOfStep("geometry"), "geometry");
  assert.equal(panelOfStep("name"), "run");
  assert.equal(panelOfStep("test"), "test");
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
    "size_from", "length", "width", "tab_length", "tab_thickness", "tab_bevel", "tab_material", "strain_device", "strain_length",
  ]);
  assert.deepEqual(visibleKeys(tension, "test"), ["test", "standard"]); // no Specimen row without a standard that names them
  assert.ok(visibleKeys({ ...tension, test: "open-hole tension", standard: "ASTM C1869-18(2023)" }, "test").includes("specimen"));
  assert.deepEqual(visibleKeys(tension, "project"), ["notes", "units"]);
  assert.deepEqual(visibleKeys(tension, "loads"), ["control", "value", "grips", "region"]);
  const bending = { ...blankForm(), test: "four-point bending" };
  assert.deepEqual(visibleKeys(bending, "geometry"), ["size_from", "length", "width", "span", "overhang", "load_span"]);
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

test("the setup opens on the test and its standard, and the steps that depend on the test wait for it (ADR-0062 amendment 1)", () => {
  assert.equal(stepNumber("test"), 1);
  assert.equal(stepNumber("geometry"), 3);
  assert.equal(stepNumber("validate"), null);
  assert.ok(!NEEDS_TEST.includes("test") && !NEEDS_TEST.includes("project") && NEEDS_TEST.includes("geometry"));
  for (const test of fieldByKey.test.words) assert.ok(testDescription(test).length > 5, `the Test row's help describes ${test}`);
  assert.equal(testDescription("unnotched tension"), "a plain strip pulled");
  assert.equal(setupLine(blankForm()), null);
  const tension = { ...blankForm(), test: "unnotched tension" };
  assert.deepEqual(setupLine(tension)?.offered.map((p) => p.designation), ["ASTM D3039/D3039M-17"]);
  assert.equal(setupLine(tension)?.standard, null);
  assert.equal(setupLine({ ...tension, standard: "ASTM D3039/D3039M-17" })?.standard?.id, "astm-d3039");
  assert.deepEqual(setupLine({ ...blankForm(), test: "in-plane shear" })?.offered, []);
});

test("each step shows what the coupon's standard asks of its rows, judged once checked (ADR-0062 amendment 1)", () => {
  const d3039 = { ...blankForm(), test: "unnotched tension", standard: "ASTM D3039/D3039M-17" };
  const geometry = stepRequirements(d3039, "geometry", null).map((r) => r.id);
  assert.ok(geometry.includes("min-length") && geometry.includes("t2-width") && geometry.includes("extensometer"), geometry.join(", "));
  assert.ok(!geometry.includes("speed") && !geometry.includes("scope-matrix")); // the laboratory's clauses and the layup's stay off Geometry
  const layup = stepRequirements(d3039, "layup", null).map((r) => r.id);
  assert.ok(layup.includes("scope-matrix") && layup.includes("t2-thickness") && !layup.includes("t2-width"), layup.join(", "));
  assert.deepEqual(stepRequirements(d3039, "test", null), []); // the first step has the whole standard on its card
  assert.deepEqual(stepRequirements({ ...d3039, standard: NO_STANDARD }, "geometry", null), []);
  const checklist: Checklist = {
    designation: null, coupon_exists: false, attempts: 0, state: "ready", problems: [],
    items: [{ id: "standard", label: "Test standard", state: "warn", message: "", rows: [],
      requirements: [{ id: "t2-width", clause: "Table 2", level: "recommended", text: "", rows: ["width"], state: "advisory", value: "20 mm", limit: "25 mm" }] }],
  };
  const judged = stepRequirements(d3039, "geometry", checklist).find((r) => r.id === "t2-width");
  assert.equal(judged && "state" in judged ? judged.state : null, "advisory");
});
