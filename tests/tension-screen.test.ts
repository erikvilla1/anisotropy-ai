import { test } from "node:test";
import assert from "node:assert/strict";
import { blankForm, exampleForm, fieldByKey } from "../lib/studio-form";
import { bannedIn } from "../lib/studio-copy";
import {
  builtLines, D3039, fixRowWords, needsPlyThickness, OWN_MATERIAL_KEYS, TENSION_HINTS, tensionLabel, tensionMissing, tensionReady, tensionValues, underD3039,
} from "../lib/tension-screen";
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

test("How we built it reads the checklist's list: the row's label, the value in words and the reason, engineering rows only", () => {
  const checklist = { items: [], designation: null, coupon_exists: false, attempts: 0, state: "ready" as const, problems: [],
    built: [{ row: "units", value: "mm-MPa", reason: "results and files use these units" }, { row: "filled_by", value: "studio", reason: "set up here" },
      { row: "date", value: "2026-11-13", reason: "the day" }, { row: "width", value: 25, reason: "ASTM D3039/D3039M-17, Table 2, balanced and symmetric" },
      { row: "size_from", value: "ASTM D3039", reason: "where the size comes from" }, { row: "grips", value: "nodal", reason: "clamped" },
      { row: "region", value: "tabs", reason: "the grips hold the whole tab" }, { row: "control", value: "displacement", reason: "the top grip moves" },
      { row: "value", value: 1, reason: "the model is linear" }, { row: "criteria", value: "all", reason: "all criteria the material's strengths allow" },
      { row: "strain_device", value: "extensometer", reason: "strain is measured over a gauge length" }] };
  const lines = builtLines(checklist);
  assert.deepEqual(lines.map((l) => [l.key, l.label, l.value]), [["units", "Units", "mm, MPa and N"], ["width", "Width (mm)", "25"], ["grips", "Grip kind", "Clamped"],
    ["control", "Loading type", "Displacement"], ["value", "Applied displacement (mm)", "1"], ["criteria", "Failure criterion", "All"],
    ["strain_device", "Strain measurement", "Extensometer"]]); // fea-run-12, fea-run-15: every text value in sentence case
  assert.deepEqual(builtLines(null), []);
});

test("the screen's own hints and labels are the customer's words (audit fea-run-6)", () => {
  assert.equal(tensionLabel("own_nu12"), "Own material: ν₁₂");
  assert.equal(tensionLabel("own_E1"), "Own material: E1 (MPa)");
  for (const key of OWN_MATERIAL_KEYS) assert.ok(TENSION_HINTS[key], key);
  for (const [key, hint] of Object.entries(TENSION_HINTS)) {
    assert.deepEqual(bannedIn(hint), [], key);
    assert.match(hint, /^[A-Z].*\.$/, key);
  }
  assert.equal(TENSION_HINTS.own_F1t, "Give all five strengths, or none (then no failure check).");
  assert.ok(tensionMissing({ ...reference, library: "", own_name: "PREPREG-01" }).includes("Own material: ν₁₂"));
  assert.equal(TENSION_HINTS.own_name, "Letters, digits, - and _; no spaces, e.g. PREPREG-01."); // a neutral example, no material of the team's
});

test("a row the setup check offers in the assistant reads as it does on the rail (audit fea-run-6, review R2-1)", () => {
  for (const key of [...OWN_MATERIAL_KEYS, "length", "width", "tab_length", "element_size"]) {
    const shown = fixRowWords(fieldByKey[key], "mm-MPa", false);
    assert.deepEqual(bannedIn(`${shown.label}\n${shown.hint}`), [], key);
    assert.equal(shown.hint, TENSION_HINTS[key] ?? shown.hint, key);
  }
  assert.equal(fixRowWords(fieldByKey.own_nu12, "mm-MPa", false).label, "Own material: ν₁₂");
  assert.equal(fixRowWords(fieldByKey.own_name, "mm-MPa", false).hint, "Letters, digits, - and _; no spaces, e.g. PREPREG-01.");
  assert.equal(fixRowWords(fieldByKey.G13, "mm-MPa", false).hint, "Out-of-plane shear modulus, fibre-thickness plane. Optional: G12 is used if blank.");
  // with every test offered (the development view) the form's own label, and its help only where it is fit to show
  assert.equal(fixRowWords(fieldByKey.own_nu12, "mm-MPa", true).label, "Own material: nu12");
  assert.equal(fixRowWords(fieldByKey.own_name, "mm-MPa", true).hint, ""); // the form's help names Abaqus
  // the form's own example no longer names a material of the team's (the definition ships in the page)
  assert.doesNotMatch(fieldByKey.own_name.help, /X840/);
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
