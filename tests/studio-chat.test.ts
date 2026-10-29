import { test } from "node:test";
import assert from "node:assert/strict";
import { blankForm, buildValues, exampleForm, type StudioForm } from "../lib/studio-form";
import { couponLines, layupNotation, layupRows, libraryConstants, missingIn, nextStep, parseLayup, readMessage, stepOfKey } from "../lib/studio-chat";

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
