import { test } from "node:test";
import assert from "node:assert/strict";
import {
  blankForm, buildValues, exampleForm, fieldByKey, isIsotropic, mergeRows, NO_STANDARD, presetRows, presetsOf, sectionsFor, shortHelp, standardOf, STANDARDS,
  standardsFor, withStandard, withTest, wordsFor,
} from "../lib/studio-form";
import { dogboneOutline, halfWidthAt, sketchOf } from "../lib/studio-sketch";

const D3039 = "ASTM D3039/D3039M-17";
const C1869 = "ASTM C1869-18(2023)";
const D638 = "ASTM D638-22";
const d3039 = STANDARDS.find((p) => p.designation === D3039)!;
const c1869 = STANDARDS.find((p) => p.designation === C1869)!;
const d638 = STANDARDS.find((p) => p.designation === D638)!;
const visible = (form: Record<string, string>) => new Set(sectionsFor(form).flatMap((s) => s.fields.map((f) => f.key)));

test("the Standard row offers none and the standards of the test picked; the Specimen row the picked standard's specimens (ADR-0072)", () => {
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "unnotched tension" }), [NO_STANDARD, D3039, D638]);
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "open-hole tension" }), [NO_STANDARD, C1869]);
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "three-point bending" }), [NO_STANDARD]);
  assert.deepEqual(wordsFor(fieldByKey.standard, blankForm()), [NO_STANDARD, D3039, D638, C1869, "ASTM D4018-23"]); // before a test is picked, every one
  assert.deepEqual(wordsFor(fieldByKey.standard, { ...blankForm(), test: "fibre tow tension" }), [NO_STANDARD, "ASTM D4018-23"]); // ADR-0074
  assert.deepEqual(wordsFor(fieldByKey.specimen, { ...blankForm(), test: "open-hole tension", standard: C1869 }), ["A", "B", "other"]);
  assert.deepEqual(wordsFor(fieldByKey.specimen, { ...blankForm(), test: "unnotched tension", standard: D638 }), ["I", "II", "III", "IV", "V"]);
  assert.deepEqual(standardsFor("unnotched tension").map((p) => p.id), ["astm-d3039", "astm-d638"]);
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
  assert.deepEqual([b.hole, b.specimen, b.standard], [3, "Specimen B", C1869]);
  const one = sketchOf({ ...blankForm(), test: "unnotched tension", standard: D638, specimen: "I", width: "19", length: "165", tab_length: "25" })!;
  assert.equal(one.specimen, "Type I"); // the standard's own word: D638 has types, C1869 specimens
});

test("a size is a whole shape, and a Size from that an old standard's size wrote leaves with that standard (review of ADR-0075)", () => {
  const type = (key: string) => d638.variants.find((v) => v.key === key)!;
  const tabbed = { ...blankForm(), test: "unnotched tension", standard: D638, tab_thickness: "1.5", tab_bevel: "7", tab_material: "glass" };
  const dogbone = presetRows(tabbed, d638, type("I"));
  assert.deepEqual([dogbone.tab_thickness, dogbone.tab_bevel, dogbone.tab_material], ["", "", ""]); // a dog-bone takes no bonded tabs
  const typeOne: Record<string, string> = { ...tabbed, ...dogbone };
  const strip = presetRows({ ...typeOne, standard: D3039 }, d3039, d3039.classes.find((c) => c.key === "0-ud")!);
  assert.deepEqual([strip.narrow_width, strip.narrow_length, strip.radius], ["", "", ""]); // a strip has no narrow section
  assert.equal(presetRows(blankForm(), d3039, d3039.classes.find((c) => c.key === "0-ud")!).narrow_width, undefined); // nothing to clear
  assert.equal(withStandard(typeOne, D3039).size_from, ""); // "ASTM D638-22, Fig. 1: Type I ..." no longer says where the size comes from
  assert.equal(withStandard(typeOne, D638).size_from, typeOne.size_from); // the same standard keeps it
  assert.equal(withStandard({ ...typeOne, size_from: "our drawing AB-12" }, D3039).size_from, "our drawing AB-12"); // the engineer's own words stay
  const moved = withTest(typeOne, "open-hole tension").form;
  assert.deepEqual([moved.standard, moved.size_from], [NO_STANDARD, ""]);
});

test("D638's types fill the dog-bone's rows, name the extensometer, and a type without Type IV's outer radius clears it (ADR-0075)", () => {
  const form = { ...blankForm(), test: "unnotched tension", standard: D638 };
  const type = (key: string) => d638.variants.find((v) => v.key === key)!;
  const one = presetRows(form, d638, type("I"));
  assert.deepEqual([one.width, one.length, one.tab_length, one.narrow_width, one.narrow_length, one.radius, one.strain_length, one.specimen],
    ["19", "165", "25", "13", "57", "76", "50", "I"]); // Fig. 1; the grips leave D = 115 mm between them
  assert.equal(one.strain_device, "extensometer"); // §5.2: the gage length is an extensometer's
  assert.equal(one.outer_radius, ""); // Type I has no outer radius
  assert.match(one.size_from, /^ASTM D638-22, Fig\. 1: Type I: 13 mm wide over 57 mm/);
  const four = presetRows(form, d638, type("IV"));
  assert.deepEqual([four.narrow_width, four.narrow_length, four.radius, four.outer_radius], ["6", "33", "14", "25"]);
  assert.equal(presetRows({ ...form, strain_device: "strain gauge" }, d638, type("I")).strain_device, undefined); // a typed device stays
  assert.deepEqual(presetsOf(d638).map((p) => p.key), ["I", "II", "III", "IV", "V"]);
});

test("a plastic is one isotropic material: its thickness, E and nu replace the plies, the ply material and the criterion (ADR-0075)", () => {
  const plastic = { ...blankForm(), test: "unnotched tension", material_kind: "isotropic", thickness: "3.2", own_E: "3000", own_nu: "0.35", own_name: "PC",
    own_source: "datasheet", ply_1: "0", symmetric: "yes", library: "im7-8552", criteria: "all", G13: "4000" };
  assert.ok(isIsotropic(plastic) && !isIsotropic({ ...plastic, test: "four-point bending" }) && !isIsotropic({ ...plastic, material_kind: "plies" }));
  const rows = visible(plastic);
  for (const key of ["material_kind", "thickness", "own_E", "own_nu", "own_name", "own_source"]) assert.ok(rows.has(key), key);
  for (const key of ["ply_1", "symmetric", "ply_thickness", "library", "own_E1", "G13", "G23", "criteria", "f12_star"]) assert.ok(!rows.has(key), key);
  const values = buildValues(plastic); // what is hidden is not sent, so the check never refuses a ply row left over from a laminate
  assert.deepEqual([values.material_kind, values.thickness, values.own_E, values.own_nu, values.ply_1, values.criteria, values.G13],
    ["isotropic", 3.2, 3000, 0.35, undefined, undefined, undefined]);
  const laminate = visible({ ...plastic, material_kind: "plies" });
  assert.ok(laminate.has("ply_1") && laminate.has("criteria") && !laminate.has("thickness") && !laminate.has("own_E"));
  assert.ok(!visible({ ...plastic, test: "three-point bending" }).has("material_kind"));
});

test("the sketch draws the dog-bone the engine meshes: narrow at mid-length, full at the ends, the fillet meeting the width where the circle says", () => {
  const form = { ...blankForm(), test: "unnotched tension", standard: D638, specimen: "I", width: "19", length: "165", tab_length: "25", narrow_width: "13",
    narrow_length: "57", radius: "76", strain_device: "extensometer", strain_length: "50", material_kind: "isotropic", thickness: "3.2" };
  const sketch = sketchOf(form)!;
  const bone = sketch.dogbone!;
  assert.deepEqual([bone.narrowWidth, bone.narrowLength, bone.radius, bone.outerRadius], [13, 57, 76, null]);
  assert.deepEqual([sketch.thickness, sketch.toScale, sketch.isotropic, sketch.plies], [3.2, true, true, 0]); // a plastic at its typed thickness
  const xs = (y: number) => bone.outline.filter(([, py]) => Math.abs(py - y) < 1e-9).map(([x]) => x).sort((a, b) => a - b);
  assert.deepEqual(xs(82.5 - 28.5), [3, 16]); // the narrow section's ends, 13 wide
  const corner = 82.5 - (28.5 + Math.sqrt(76 ** 2 - 73 ** 2)); // 32.857626 mm: the spec's partition line
  assert.ok(Math.abs(corner - 32.857626) < 1e-6);
  assert.deepEqual(xs(corner).map((x) => Math.round(x * 1e9) / 1e9), [0, 19]);
  assert.deepEqual(xs(0), [0, 19]);
  const o = dogboneOutline(6, 33, 14, 25, 19, 115)!; // Type IV: two arcs tangent to each other, no corner
  const near = (a: number, b: number) => Math.abs(a - b) < 1e-9;
  assert.ok(near(halfWidthAt(o, 0), 3) && near(halfWidthAt(o, 57), 9.5) && near(halfWidthAt(o, o.sFull), 9.5));
  const h = (d: number) => halfWidthAt(o, d);
  assert.ok(Math.abs((h(o.sTangent + 1e-6) - h(o.sTangent - 1e-6)) / 2e-6 - (h(o.sTangent + 2e-6) - h(o.sTangent)) / 2e-6) < 1e-3); // smooth where the arcs meet
  assert.equal(sketchOf({ ...form, radius: "2" })!.dogbone, null); // a fillet that cannot step out by 3 mm draws a plain strip; the check says why
  assert.equal(sketchOf({ ...form, test: "open-hole tension" })!.dogbone, null);
  assert.equal(sketchOf({ ...form, material_kind: "plies" })!.isotropic, false);
});
