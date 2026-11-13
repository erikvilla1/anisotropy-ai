import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  blankForm, buildValues, DECK_UNITS, DEFAULT_UNITS, EXAMPLE, exampleForm, fieldByKey, fieldByLabel, fields, FORM_VERSION, formDefinition, formFromValues, BENDING_KEYS,
  HOLE_KEYS, labelFor, libraryConstantsIn, libraryOptions, PLY_KEYS, rowErrorsFrom, sectionsFor, shortHelp, UNIT_SYSTEMS, unitLabels, unitsOf, unitWords,
  type Checklist,
} from "../lib/studio-form";

const values = JSON.parse(readFileSync("tests/fixtures/studio/values.json", "utf8"));
const checklist: Checklist = JSON.parse(readFileSync("tests/fixtures/studio/checklist.json", "utf8"));

test("the form is the package's definition: one row per field, the ply rows, the hole rows and the library", () => {
  assert.equal(formDefinition.units, "mm-MPa");
  assert.equal(new Set(fields.map((f) => f.key)).size, fields.length);
  assert.equal(PLY_KEYS.length, 16);
  for (const key of HOLE_KEYS) assert.ok(fieldByKey[key], key);
  assert.ok(fieldByKey.criteria.words.includes("all") && fieldByKey.f12_star.kind === "number");
  assert.ok(libraryOptions.some((m) => m.id === "im7-8552" && m.thickness !== null));
  assert.equal(values.form_version, FORM_VERSION, "regenerate tests/fixtures/studio with fea/tools/studio_tool.py fixtures");
});

test("a blank form carries the defaults and the example is complete", () => {
  const blank = blankForm();
  assert.equal(blank.element_size, "2");
  assert.equal(blank.criteria, "all");
  assert.equal(blank.length, "");
  const example = exampleForm("2026-10-28");
  assert.equal(example.date, "2026-10-28");
  for (const field of fields) if (field.required && field.key !== "filled_by") assert.ok(example[field.key] !== "", `${field.key} must be filled in the example`);
  assert.equal(example.filled_by, ""); // the engineer's own name is theirs to type
  assert.equal(Object.keys(EXAMPLE).filter((k) => !fieldByKey[k]).length, 0);
});

test("the hole rows show only for open-hole tension", () => {
  const sections = sectionsFor({ ...blankForm(), test: "unnotched tension" });
  assert.ok(!sections.some((s) => s.fields.some((f) => HOLE_KEYS.includes(f.key))));
  const withHole = sectionsFor({ ...blankForm(), test: "open-hole tension" });
  assert.ok(withHole.some((s) => s.fields.some((f) => f.key === "hole_diameter")));
  assert.equal(withHole.length, formDefinition.sections.length - 2); // every section but the bending one and the dog-bone's
  assert.ok(!sections.some((s) => s.fields.some((f) => BENDING_KEYS.includes(f.key))));
});

test("the bending rows replace the grips and tabs for the bending tests", () => {
  const three = sectionsFor({ ...blankForm(), test: "three-point bending" });
  const keys = three.flatMap((s) => s.fields.map((f) => f.key));
  assert.ok(keys.includes("span") && keys.includes("overhang") && !keys.includes("load_span"));
  assert.ok(!keys.includes("tab_length") && !keys.includes("grips") && !keys.includes("region") && !keys.includes("hole_diameter"));
  const four = sectionsFor({ ...blankForm(), test: "four-point bending" });
  assert.ok(four.flatMap((s) => s.fields.map((f) => f.key)).includes("load_span"));
  assert.ok(sectionsFor({ ...blankForm(), test: "unnotched tension" }).flatMap((s) => s.fields.map((f) => f.key)).includes("tab_length"));
});

test("the values object parses numbers and leaves blanks out, without judging", () => {
  const built = buildValues({ ...blankForm(), ...EXAMPLE, date: "2026-10-28", width: "wide", f12_star: " -0.5 " });
  assert.equal(built.form_version, FORM_VERSION);
  assert.equal(built.length, 250);
  assert.equal(built.ply_1, 45);
  assert.equal(built.width, "wide"); // not a number: left as text for the check to refuse by row
  assert.equal(built.f12_star, -0.5);
  assert.ok(!("notes" in built) && !("ply_5" in built) && !("mesh_nx" in built));
  assert.equal(built.library, "im7-8552");
});

test("a coupon read back fills the form", () => {
  const form = formFromValues({ ...values, angles: [45, 0, -45, 90], symmetric: true, mesh_partitions: [56, 194], mesh_seeds: [28, 69, 28], notes: null });
  assert.equal(form.ply_1, "45");
  assert.equal(form.ply_4, "90");
  assert.equal(form.ply_5, "");
  assert.equal(form.symmetric, "yes");
  assert.equal(form.mesh_partitions, "56, 194");
  assert.equal(form.notes, "");
  assert.equal(form.length, "250");
});

test("a checklist's failing rows land on their fields", () => {
  const blocked: Checklist = {
    ...checklist, state: "blocked",
    items: checklist.items.map((item) => item.id === "geometry" ? { ...item, state: "missing", message: "Length (mm): required", rows: ["Length (mm)", "Width (mm)"] } : item),
  };
  assert.deepEqual(rowErrorsFrom(blocked), { length: "Required.", width: "Check this value." }); // each field its own problem (fea-run-49)
  assert.deepEqual(rowErrorsFrom(checklist), {});
});

test("a row's hint is its help's first sentence, as a sentence", () => {
  assert.ok(shortHelp(fieldByKey.length).startsWith("The whole coupon"));
  assert.ok(shortHelp(fieldByKey.G13).length <= 141);
  for (const field of fields) {
    const hint = shortHelp(field);
    if (hint) assert.match(hint, /^[^a-z].*[.?!]$/, field.key); // capitalised and ended, never cut on ';' (fea-run-J2-3)
  }
});

test("the form carries the engine's unit systems: labels per row, defaults per system and the library's constants, nothing converted here", () => {
  assert.deepEqual(UNIT_SYSTEMS, ["mm-MPa", "m-Pa", "in-psi", "in-ksi"]);
  assert.equal(DEFAULT_UNITS, "mm-MPa");
  assert.equal(DECK_UNITS, "mm-MPa");
  assert.equal(unitWords("in-psi"), "in, psi and lbf");
  assert.deepEqual([unitLabels("in-ksi").stress, unitLabels("in-ksi").force, unitLabels("m-Pa").length], ["ksi", "lbf", "m"]);
  assert.equal(labelFor(fieldByKey.length, "in-psi"), "Length (in)");
  assert.equal(labelFor(fieldByKey.own_E1, "in-ksi"), "Own material: E1 (ksi)");
  assert.equal(labelFor(fieldByKey.value, "m-Pa"), "Value (m or N)");
  assert.equal(labelFor(fieldByKey.test, "in-psi"), "Test");
  assert.equal(fieldByLabel["Length (in)"]?.key, "length");
  assert.equal(fieldByLabel["Own material: G12 (psi)"]?.key, "own_G12");
  assert.equal(fieldByKey.units.kind, "list");
  assert.deepEqual(fieldByKey.units.words, UNIT_SYSTEMS);
  const inches = blankForm("in-psi");
  assert.equal(inches.units, "in-psi");
  assert.ok(Math.abs(Number(inches.element_size) - 2 / 25.4) < 1e-9); // the engine's 2 mm default, in inches
  assert.equal(blankForm().element_size, "2");
  assert.equal(blankForm("furlongs").units, "mm-MPa");
  assert.equal(unitsOf({ units: "in-ksi" }), "in-ksi");
  assert.equal(unitsOf({ units: "SI" }), "mm-MPa");
  assert.equal(unitsOf({}), "mm-MPa");
  assert.equal(formFromValues({ units: "in-psi", length: 10 }).units, "in-psi");
  assert.equal(formFromValues({ length: 250 }).units, "mm-MPa");
  assert.equal(buildValues({ ...exampleForm("2026-10-29"), units: "in-psi" }).units, "in-psi");
  const im7 = libraryConstantsIn("im7-8552", "in-psi")!;
  assert.ok(Math.abs(im7.E1 - 23.51e6) < 1e4 && Math.abs(im7.ply_thickness! - 0.0072) < 1e-9);
  assert.equal(libraryConstantsIn("no-such-material", "in-psi"), null);
  assert.deepEqual(rowErrorsFrom({ ...checklist, items: [{ id: "geometry", label: "Geometry defined", state: "missing", message: "Length (in): required", rows: ["Length (in)"] }] }),
    { length: "Required." });
});
