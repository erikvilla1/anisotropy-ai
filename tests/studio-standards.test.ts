import { test } from "node:test";
import assert from "node:assert/strict";
import {
  blankForm, exampleForm, fieldByKey, mergeRows, NO_STANDARD, presetRows, presetsOf, sectionsFor, shortHelp, standardOf, STANDARDS, standardsFor, withStandard,
  withTest, wordsFor,
} from "../lib/studio-form";
import { sketchOf } from "../lib/studio-sketch";

const D3039 = "ASTM D3039/D3039M-17";
const C1869 = "ASTM C1869-18(2023)";
const d3039 = STANDARDS.find((p) => p.designation === D3039)!;
const c1869 = STANDARDS.find((p) => p.designation === C1869)!;
const visible = (form: Record<string, string>) => new Set(sectionsFor(form).flatMap((s) => s.fields.map((f) => f.key)));

test("the Standard row offers none and the standards of the test picked; the Specimen row the picked standard's specimens (ADR-0072)", () => {
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "unnotched tension" }), [NO_STANDARD, D3039]);
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "open-hole tension" }), [NO_STANDARD, C1869]);
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "three-point bending" }), [NO_STANDARD]);
  assert.deepEqual(wordsFor(fieldByKey.standard, blankForm()), [NO_STANDARD, D3039, C1869, "ASTM D4018-23"]); // before a test is picked, every one
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "fibre tow tension" }), [NO_STANDARD, "ASTM D4018-23"]); // ADR-0074
  assert.deepEqual(wordsFor(fieldByKey.specimen, { ...blankForm(), test: "open-hole tension", standard: C1869 }), ["A", "B", "other"]);
  assert.deepEqual(standardsFor("unnotched tension").map((p) => p.id), ["astm-d3039"]);
  assert.equal(standardOf({ ...blankForm(), standard: "ASTM D3039" }), null); // a word the list does not hold names no standard
});

test("a new test clears a standard that does not cover it, with a note; a new standard clears a specimen it does not name", () => {
  const oht = { ...blankForm(), test: "open-hole tension", standard: C1869, specimen: "B" };
  const moved = withTest(oht, "unnotched tension");
  assert.deepEqual([moved.form.test, moved.form.standard, moved.form.specimen], ["unnotched tension", NO_STANDARD, ""]);
  assert.match(moved.note, /ASTM C1869-18\(2023\) covers open-hole tension, not unnotched tension: the Standard row is back to none/);
  assert.equal(withTest(oht, "open-hole tension").note, "");
  assert.equal(withStandard(oht, NO_STANDARD).specimen, "");
  assert.equal(withStandard({ ...oht, specimen: "A" }, C1869).specimen, "A");
  assert.deepEqual([mergeRows(oht, { test: "unnotched tension" }).standard, mergeRows(oht, { test: "unnotched tension", standard: D3039 }).standard],
    [NO_STANDARD, D3039]);
});

test("a standard's size fills its rows in the coupon's units, with the specimen and where the size comes from", () => {
  const b = presetRows({ ...blankForm(), test: "open-hole tension", standard: C1869 }, c1869, c1869.variants.find((v) => v.key === "B")!);
  assert.deepEqual([b.width, b.hole_diameter, b.length, b.tab_length, b.specimen], ["10", "3", "60", "15", "B"]);
  assert.match(b.size_from, /^ASTM C1869-18\(2023\), Table 2: Specimen B: a 3 mm hole in a 10 mm wide strip; the least length/);
  const zero = d3039.classes.find((c) => c.key === "0-ud")!;
  const inches = presetRows({ ...blankForm("in-psi"), test: "unnotched tension", standard: D3039 }, d3039, zero);
  assert.deepEqual([inches.width, inches.length, inches.tab_length, inches.tab_thickness, inches.tab_bevel], ["0.5", "10", "2.25", "0.062", "7"]); // §1.2
  const balanced = presetRows({ ...blankForm(), tab_thickness: "1.5", tab_bevel: "7", tab_material: "glass" }, d3039, d3039.classes.find((c) => c.key === "balanced")!);
  assert.deepEqual([balanced.width, balanced.length, balanced.tab_thickness, balanced.tab_bevel, balanced.tab_material], ["25", "250", "", "", ""]);
  assert.equal(balanced.tab_length, undefined); // Table 2 gives none for this class: the typed tab length stays
  assert.deepEqual(presetsOf(d3039).map((p) => p.key), ["0-ud", "90-ud", "balanced"]);
});

test("the Specimen row shows for a standard that names specimens; the tab and strain rows for the pulled and pushed tests", () => {
  assert.ok(!visible({ ...blankForm(), test: "open-hole tension" }).has("specimen"));
  assert.ok(visible({ ...blankForm(), test: "open-hole tension", standard: C1869 }).has("specimen"));
  assert.ok(!visible({ ...blankForm(), test: "unnotched tension", standard: D3039 }).has("specimen"));
  assert.ok(visible({ ...blankForm(), test: "unnotched tension" }).has("strain_length") && !visible({ ...blankForm(), test: "four-point bending" }).has("tab_bevel"));
});

test("a hint does not stop at e.g.", () => {
  assert.equal(shortHelp({ ...fieldByKey.notes, help: "the number of plies, e.g. 8. More below." }), "the number of plies, e.g. 8.");
});

test("the sketch draws bonded tabs with their bevel and the strain measurement as typed, and names the standard", () => {
  const form = { ...exampleForm("2026-11-08"), standard: D3039, tab_thickness: "1.5", tab_bevel: "7", strain_device: "extensometer", strain_length: "25" };
  const sketch = sketchOf(form)!;
  assert.deepEqual([sketch.tabThickness, sketch.tabBevel, sketch.strain, sketch.standard, sketch.specimen],
    [1.5, 7, { device: "extensometer", length: 25 }, D3039, null]);
  assert.equal(sketchOf({ ...form, tab_bevel: "" })!.tabThickness, null); // a tab without its bevel is not drawn as a block
  assert.equal(sketchOf({ ...form, tab_bevel: "120" })!.tabBevel, null);
  assert.equal(sketchOf({ ...form, strain_length: "200" })!.strain, null); // longer than the 138 mm between the tabs
  const b = sketchOf({ ...blankForm(), test: "open-hole tension", standard: C1869, specimen: "B", width: "10", length: "60", tab_length: "15", hole_diameter: "3" })!;
  assert.deepEqual([b.hole, b.specimen, b.standard], [3, "B", C1869]);
});
