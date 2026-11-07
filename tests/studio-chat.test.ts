import { test } from "node:test";
import assert from "node:assert/strict";
import { blankForm, buildValues, exampleForm, type StudioForm } from "../lib/studio-form";
import {
  applyMessage, couponLines, DIMENSIONED_KEYS, labelOf, layupNotation, layupRows, libraryConstants, libraryThickness, LOAD_CHIPS, missingIn, nextStep, parseLayup,
  PUSH_CHIPS, readMessage, SIZE_CHIPS, stepOfKey, switchUnits, unitsNamed,
} from "../lib/studio-chat";

test("the laminate notation expands repeats, ± pairs and subscripts, and marks the lower half of a symmetric stack", () => {
  assert.deepEqual(parseLayup("[45/0/-45/90]s"), { plies: [45, 0, -45, 90], symmetric: true });
  assert.deepEqual(parseLayup("[0/90]2s"), { plies: [0, 90, 0, 90], symmetric: true });
  assert.deepEqual(parseLayup("[±45]2"), { plies: [45, -45, 45, -45], symmetric: false });
  assert.deepEqual(parseLayup("[0_2/90]s"), { plies: [0, 0, 90], symmetric: true });
  assert.deepEqual(parseLayup("[0₂/+-30]"), { plies: [0, 0, 30, -30], symmetric: false });
  assert.equal(parseLayup("45/0/-45/90"), null);
  assert.equal(parseLayup("[0/abc]"), null);
  assert.equal(parseLayup("[0]17"), null); // more plies than the form has rows
});

test("a layup fills the ply rows and clears the ones past the stack, and reads back in the same notation", () => {
  const form = { ...exampleForm("2026-10-29"), ...layupRows(parseLayup("[0/90]")!) };
  assert.equal(form.ply_1, "0");
  assert.equal(form.ply_2, "90");
  assert.equal(form.ply_3, "");
  assert.equal(form.symmetric, "no");
  assert.equal(layupNotation(form), "[0/90]");
  assert.equal(layupNotation(exampleForm("2026-10-29")), "[45/0/-45/90]s");
});

test("one typed line states a whole coupon in form rows", () => {
  const { rows, understood } = readMessage("Open-hole tension, IM7/8552, [45/0/-45/90]s, 36 x 250 mm, 6 mm hole, 1 mm pull");
  assert.equal(rows.test, "open-hole tension");
  assert.equal(rows.library, "im7-8552");
  assert.equal(rows.ply_4, "90");
  assert.equal(rows.symmetric, "yes");
  assert.equal(rows.length, "250");
  assert.equal(rows.width, "36");
  assert.equal(rows.hole_diameter, "6");
  assert.equal(rows.control, "displacement");
  assert.equal(rows.value, "1");
  assert.ok(understood.length >= 6);
});

test("forces convert kN to the form's N, tabs, spans and standards are read, and the longest library id wins", () => {
  assert.deepEqual([readMessage("10 kN").rows.control, readMessage("10 kN").rows.value], ["force", "10000"]);
  assert.equal(readMessage("56 mm tabs").rows.tab_length, "56");
  assert.equal(readMessage("no tabs").rows.tab_length, "0");
  assert.equal(readMessage("three-point bending, span 48").rows.span, "48");
  assert.equal(readMessage("three-point bending").rows.test, "three-point bending");
  assert.equal(readMessage("per ASTM D3039").rows.standard, "ASTM D3039");
  assert.equal(readMessage("AS4/8552S PW").rows.library, "as4-8552s-pw");
  assert.equal(readMessage("AS4/8552").rows.library, "as4-8552");
  assert.deepEqual(readMessage("hello there"), { rows: {}, understood: [] });
});

test("the chat asks in order and reaches the review only when every step has its rows", () => {
  const blank = { ...blankForm(), date: "2026-10-29" };
  assert.equal(nextStep(blank), "test");
  assert.equal(nextStep({ ...blank, test: "unnotched tension" }), "material");
  const example = exampleForm("2026-10-29");
  assert.equal(nextStep(example), "name"); // the engineer's name is theirs to give
  assert.equal(nextStep({ ...example, filled_by: "A. Engineer" }), "review");
  assert.deepEqual(missingIn("geometry", { ...example, test: "four-point bending", tab_length: "" }), ["span", "load_span"]);
  assert.deepEqual(missingIn("geometry", { ...example, test: "open-hole tension" }), ["hole_diameter"]);
  assert.deepEqual(missingIn("layup", { ...example, library: "" }), ["ply_thickness"]); // own constants carry no ply thickness
});

test("a blocked row leads back to the step that asks for it", () => {
  assert.equal(stepOfKey("length"), "geometry");
  assert.equal(stepOfKey("ply_7"), "layup");
  assert.equal(stepOfKey("own_E1"), "material");
  assert.equal(stepOfKey("G23"), "shear");
  assert.equal(stepOfKey("filled_by"), "name");
  assert.equal(stepOfKey("material_code"), null); // the codes are derived (ADR-0038 amendment 1); an override lives on the full form only
  assert.equal(stepOfKey("name_part"), null); // only the full form has the Abaqus names
});

test("the chat fills the same values the full form sends, and the summary shows only what is stated", () => {
  const example: StudioForm = { ...exampleForm("2026-10-29"), filled_by: "A. Engineer" };
  const typed = { ...blankForm(), date: "2026-10-29", filled_by: "A. Engineer", ...readMessage("unnotched tension IM7/8552 [45/0/-45/90]s 250 x 25 mm 56 mm tabs 1 mm pull").rows,
    size_from: example.size_from, G13: example.G13, G23: example.G23, material_code: example.material_code };
  assert.deepEqual(buildValues(typed), buildValues({ ...example, notes: "", standard: "none" }));
  const lines = Object.fromEntries(couponLines(example));
  assert.equal(lines.Layup, "[45/0/-45/90]s, 8 plies");
  assert.equal(lines.Size, "250 × 25 mm, 56 mm tabs");
  assert.equal(Object.fromEntries(couponLines(blankForm())).Material, "");
  assert.ok(libraryConstants("im7-8552")!.G12 > 0);
});

test("the summary and the labels follow the coupon's units, and the Units row leads back to the first question", () => {
  const lines = Object.fromEntries(couponLines(exampleForm("2026-10-29")));
  assert.equal(lines.Units, "mm, MPa and N");
  const inches = { ...blankForm("in-psi"), test: "unnotched tension", length: "10", width: "1", tab_length: "2.2", control: "force", value: "2000" };
  const inchLines = Object.fromEntries(couponLines(inches));
  assert.equal(inchLines.Units, "in, psi and lbf");
  assert.equal(inchLines.Size, "10 × 1 in, 2.2 in tabs");
  assert.equal(inchLines.Load, "2000 lbf force");
  assert.equal(labelOf("length"), "Length, tabs included (mm)");
  assert.equal(labelOf("length", "in-psi"), "Length, tabs included (in)");
  assert.equal(labelOf("own_E1", "in-ksi"), "E1 (ksi)");
  assert.equal(labelOf("G13", "m-Pa"), "G13 (Pa)");
  assert.equal(labelOf("value", "in-psi"), "Amount");
  assert.equal(stepOfKey("units"), "test");
  assert.ok(DIMENSIONED_KEYS.includes("length") && DIMENSIONED_KEYS.includes("own_F6") && !DIMENSIONED_KEYS.includes("element_size"));
});

test("a message is read in the coupon's units: inches and pounds for a coupon stated in in-psi", () => {
  const { rows, understood } = readMessage("unnotched tension, 10 x 1 in, 2.2 in tabs, 0.25 in hole, pulled 0.04 in", "in-psi");
  assert.deepEqual([rows.length, rows.width, rows.tab_length, rows.hole_diameter, rows.control, rows.value], ["10", "1", "2.2", "0.25", "displacement", "0.04"]);
  assert.ok(understood.includes("length 10 in") && understood.includes("0.04 in displacement"));
  assert.deepEqual([readMessage("2 kips", "in-psi").rows.control, readMessage("2 kips", "in-psi").rows.value], ["force", "2000"]);
  assert.equal(readMessage("500 lbf", "in-ksi").rows.value, "500");
  assert.equal(readMessage('10" x 1"', "in-psi").rows.length, "10");
  assert.equal(readMessage("0.25 x 0.025 m, 0.056 m tabs", "m-Pa").rows.tab_length, "0.056");
  assert.equal(readMessage("250 x 25 mm", "in-psi").rows.length, undefined); // a number in another system is not read as inches
  assert.equal(readMessage("10 x 1 in", "mm-MPa").rows.length, undefined);
});

test("naming another system switches the coupon when nothing dimensioned is stated, and refuses the message once it is", () => {
  assert.equal(unitsNamed("in inches and psi"), "in-psi");
  assert.equal(unitsNamed("use ksi"), "in-ksi");
  assert.equal(unitsNamed("metres and pascals"), "m-Pa");
  assert.equal(unitsNamed("back to mm"), null); // a bare mm or in is not a statement of the system
  assert.equal(unitsNamed("in millimetres"), "mm-MPa");
  const blank = { ...blankForm(), date: "2026-10-29" };
  const fresh = applyMessage(blank, "unnotched tension, IM7/8552, 10 x 1 inch, 2.2 in tabs, 0.04 in pull");
  assert.equal(fresh.rows.units, "in-psi");
  assert.deepEqual([fresh.rows.length, fresh.rows.tab_length, fresh.rows.value, fresh.rows.element_size], ["10", "2.2", "0.04", blankForm("in-psi").element_size]);
  assert.equal(fresh.understood[0], "units: in, psi and lbf");
  assert.equal(fresh.note, null);
  const stated = { ...exampleForm("2026-10-29"), filled_by: "A. Engineer" };
  const refused = applyMessage(stated, "pull it 0.04 inches");
  assert.deepEqual(refused.rows, {});
  assert.match(refused.note ?? "", /names in, psi and lbf, but this coupon is stated in mm, MPa and N/);
  const switched = applyMessage(stated, "switch to inches and psi");
  assert.equal(switched.rows.units, "in-psi");
  assert.equal(switched.rows.length, ""); // the mm numbers do not survive: the page converts nothing
  assert.equal(switched.rows.G13, "");
  assert.match(switched.note ?? "", /cleared Length, tabs included, Width, Tab length/);
  assert.equal(applyMessage(stated, "make it [0/90]2s").rows.ply_1, "0"); // no system named: read as before
  const { form, cleared } = switchUnits(stated, "m-Pa");
  assert.equal(form.units, "m-Pa");
  assert.equal(form.element_size, "0.002");
  assert.ok(cleared.includes("length") && cleared.includes("value") && !cleared.includes("ply_1"));
  assert.deepEqual(switchUnits(stated, "furlongs"), { form: stated, cleared: [] });
});

test("the library's constants and the chips come per system from the engine's table", () => {
  const mm = libraryConstants("im7-8552")!, psi = libraryConstants("im7-8552", "in-psi")!, ksi = libraryConstants("im7-8552", "in-ksi")!;
  assert.ok(Math.abs(mm.G12 - 4688.43) < 0.01);
  assert.ok(Math.abs(psi.G12 - 680000) < 1); // 4688.43 MPa is 0.68 Msi
  assert.ok(Math.abs(ksi.G12 - 680) < 1e-3);
  assert.ok(Math.abs(libraryThickness({ ...blankForm("in-psi"), library: "im7-8552" })! - 0.0072) < 1e-9);
  assert.equal(libraryThickness({ ...blankForm(), library: "im7-8552" }), 0.18288);
  assert.equal(libraryThickness(blankForm()), null);
  for (const units of ["mm-MPa", "m-Pa", "in-psi", "in-ksi"]) {
    assert.ok(SIZE_CHIPS[units].rows.length && LOAD_CHIPS[units].length === 3 && PUSH_CHIPS[units].length === 3, units);
  }
  assert.equal(LOAD_CHIPS["in-psi"][2].value, "2000");
});
