import { test } from "node:test";
import assert from "node:assert/strict";
import { blankForm, exampleForm } from "../lib/studio-form";
import { builtLines, D3039, needsPlyThickness, tensionMissing, tensionReady, tensionValues, underD3039 } from "../lib/tension-screen";
import { missingIn, nextStep } from "../lib/studio-chat";

const reference = { ...blankForm(), library: "im7-8552", ply_1: "45", ply_2: "0", ply_3: "-45", ply_4: "90", symmetric: "yes" };

test("a new form is under D3039 and needs only the material and the layup (ADR-0090)", () => {
  const fresh = blankForm();
  assert.equal(underD3039(fresh), true, "the blank form's Standard row says none, but a form with no test is new: D3039");
  assert.deepEqual(tensionMissing(fresh), ["the material", "the layup"]);
  assert.equal(tensionReady(reference), true);
  assert.equal(underD3039({ ...reference, test: "unnotched tension", standard: "none" }), false);
  assert.deepEqual(tensionMissing({ ...reference, test: "unnotched tension", standard: "none" }), ["Length (mm)", "Width (mm)", "Tab length (mm)"]);
});

test("the screen sends its own rows only, and leaves the rest to the package", () => {
  const values = tensionValues({ ...reference, grips: "coupling", mesh_partitions: "56, 194", name_part: "X", hole_diameter: "6" });
  assert.equal(values.input, "tension");
  assert.equal(values.library, "im7-8552");
  assert.deepEqual([values.ply_1, values.ply_2, values.ply_3, values.ply_4, values.symmetric], [45, 0, -45, 90, "yes"]);
  for (const key of ["grips", "mesh_partitions", "name_part", "hole_diameter", "units", "test", "standard", "criteria", "element_size"]) {
    assert.equal(values[key], undefined, key);
  }
  const changed = tensionValues({ ...reference, element_size: "1.5", control: "force", value: "5000", test: "unnotched tension", standard: D3039 });
  assert.deepEqual([changed.element_size, changed.control, changed.value, changed.standard], [1.5, "force", 5000, D3039]);
});

test("an own material sends its constants and no library id; a library material sends none of them", () => {
  const own = tensionValues({ ...reference, library: "", own_name: "X840", own_E1: "80000", own_source: "a sheet", ply_thickness: "0.2" });
  assert.equal(own.library, undefined);
  assert.deepEqual([own.own_name, own.own_E1, own.ply_thickness], ["X840", 80000, 0.2]);
  assert.equal(tensionValues({ ...reference, own_E1: "80000" }).own_E1, undefined);
  assert.ok(tensionMissing({ ...reference, library: "", own_name: "X840" }).includes("Own material: E1 (MPa)"));
});

test("a library material whose record gives no ply thickness asks for it, and sends it", () => {
  const as4 = { ...reference, library: "as4-8552" };
  assert.equal(needsPlyThickness(as4), true, "AS4/8552's record gives no ply thickness");
  assert.equal(needsPlyThickness(reference), false, "IM7/8552's does");
  assert.equal(needsPlyThickness({ ...reference, library: "" }), false, "an own material has its own row");
  assert.deepEqual(tensionMissing(as4), ["Ply thickness (mm)"]);
  assert.equal(tensionReady({ ...as4, ply_thickness: "0.19" }), true);
  assert.equal(tensionValues({ ...as4, ply_thickness: "0.19" }).ply_thickness, 0.19);
});

test("How we built it reads the checklist's list: the row's label, the value and the reason", () => {
  const lines = builtLines({ items: [], designation: null, coupon_exists: false, attempts: 0, state: "ready", problems: [],
    built: [{ row: "width", value: 25, reason: "ASTM D3039/D3039M-17, Table 2, balanced and symmetric" }, { row: "grips", value: "nodal", reason: "clamped" }] });
  assert.deepEqual(lines.map((l) => [l.key, l.label, l.value]), [["width", "Width (mm)", "25"], ["grips", "Grip kind", "nodal"]]);
  assert.deepEqual(builtLines(null), []);
});

test("the tension screen's chat asks for the material and the layup, the size only under no standard", () => {
  const fresh = blankForm();
  assert.equal(nextStep(fresh, true), "material");
  assert.equal(nextStep({ ...fresh, library: "im7-8552" }, true), "layup");
  assert.equal(nextStep(reference, true), "review");
  assert.equal(nextStep({ ...reference, test: "unnotched tension", standard: "none" }, true), "geometry");
  assert.deepEqual(missingIn("loading", fresh, true), []);
  assert.equal(nextStep({ ...exampleForm("2026-11-11"), filled_by: "A. Engineer" }), "review", "the full panels' chat is as before");
  assert.equal(nextStep(exampleForm("2026-11-11")), "name");
});
