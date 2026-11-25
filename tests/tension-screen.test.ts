import { test } from "node:test";
import assert from "node:assert/strict";
import { blankForm, exampleForm, fieldByKey, libraryConstantsIn, libraryValuesIn } from "../lib/studio-form";
import { bannedIn } from "../lib/studio-copy";
import {
  builtLines, D3039, fixRowWords, libraryValueLines, needsPlyThickness, ownFromLibrary, ownNameFromLibrary, OWN_MATERIAL_KEYS, TENSION_HINTS, tensionLabel,
  tensionMissing, tensionReady, tensionValues,
  underD3039, valuesInUse,
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
  // a blank field under Change settings shows the number in use (ADR-0090 amendment 1); text rows have no placeholder
  assert.deepEqual(valuesInUse(checklist), { width: "25", value: "1" });
  assert.deepEqual(valuesInUse({ ...checklist, built: [{ row: "length", value: 250.0, reason: "Table 2" }, { row: "tab_length", value: 56, reason: "ours" },
    { row: "element_size", value: 1.5, reason: "a structured mesh" }] }), { length: "250", tab_length: "56", element_size: "1.5" });
  assert.deepEqual(valuesInUse(null), {});
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

test("the Material step shows the chosen library material's numbers as the engine wrote them, in the coupon's units (ADR-0111 amendment 4)", () => {
  const shown = (form: Record<string, string>) => {
    const lines = libraryValueLines(form);
    return lines && { stiffness: lines.stiffness.map((l) => `${l.label} ${l.value}`), strengths: lines.strengths?.map((l) => `${l.label} ${l.value}`) ?? null };
  };
  // IM7/8552 (NCAMP): the mockup's numbers, printed by the one number rule
  assert.deepEqual(shown(reference), {
    stiffness: ["E1 162.1 GPa", "E2 8.963 GPa", "G12 4.688 GPa", "G13 4.688 GPa", "G23 2.988 GPa", "ν12 0.316", "Ply 0.1829 mm"],
    strengths: ["F1t 2559 MPa", "F1c 1731 MPa", "F2t 64.05 MPa", "F2c 285.7 MPa", "F6 91.15 MPa"],
  });
  // in inches the moduli are in Msi and the strengths in psi, as the engine converted them: the page converts nothing
  assert.deepEqual(shown({ ...reference, units: "in-psi" })?.stiffness,
    ["E1 23.51 Msi", "E2 1.3 Msi", "G12 0.68 Msi", "G13 0.68 Msi", "G23 0.4333 Msi", "ν12 0.316", "Ply 0.0072 in"]);
  assert.equal(shown({ ...reference, units: "in-psi" })?.strengths?.[0], "F1t 371100 psi");
  // a record with no ply thickness has no Ply line (the field to type it is below); one with no strengths has no strength column
  assert.deepEqual(shown({ ...reference, library: "as4-8552" })?.stiffness.map((l) => l.split(" ")[0]), ["E1", "E2", "G12", "G13", "G23", "ν12"]);
  assert.equal(shown({ ...reference, library: "as4-8552s-pw" })?.strengths, null);
  // the engineer's own material and no choice show nothing: their numbers are the fields they typed
  assert.equal(libraryValueLines({ ...reference, library: "" }), null);
  assert.equal(libraryValueLines({ ...reference, library: "no-such-material" }), null);
});

test("G13 and G23 show as the coupon's estimates until the engineer gives their own, which a library material then sends (ADR-0111 amendment 5)", () => {
  const lines = libraryValueLines(reference)!;
  // the library gives neither: the estimates the package builds the coupon with (G13 = G12, G23 = E2 / 3 for a tape), marked as estimates
  assert.deepEqual(lines.stiffness.filter((l) => l.estimate).map((l) => l.key), ["G13", "G23"]);
  assert.deepEqual(lines.transverse.estimates, { G13: "4688", G23: "2988" }); // the fields' placeholders, in the rows' MPa
  assert.match(lines.transverse.rule, /G23 = E2 \/ 3/);
  assert.match(libraryValueLines({ ...reference, library: "hts40-tc250" })!.transverse.rule, /fabric/); // a fabric: G23 = G12
  // the engineer's own: the two rows give way to the fields, and the values go to the check with the library material
  assert.deepEqual(libraryValueLines(reference, { ownTransverse: true })!.stiffness.map((l) => l.key), ["E1", "E2", "G12", "nu12", "ply_thickness"]);
  const sent = tensionValues({ ...reference, G13: "5200", G23: "3400" });
  assert.equal(sent.library, "im7-8552");
  assert.deepEqual([sent.G13, sent.G23], [5200, 3400]);
  assert.equal(tensionValues(reference).G13, undefined, "left blank, the package estimates them");
  assert.equal(tensionValues({ ...reference, own_E1: "9" }).own_E1, undefined, "other own-material rows still stay out for a library material");
});


test("editing a library material copies its record into the engineer's own rows, changing no number (ADR-0111 amendment 6)", () => {
  const copied = ownFromLibrary(reference)!;
  // the record is no longer cited: the coupon carries the engineer's own constants, named after it and saying where they came from
  assert.equal(copied.library, "");
  assert.equal(copied.own_name, "IM7-8552");
  assert.match(copied.own_source!, /IM7 \/ 8552 from our library, edited here/);
  // every constant goes across exactly as the engine wrote it, in the row's own unit (MPa, not the GPa the step prints)
  const constants = libraryConstantsIn("im7-8552", "mm-MPa")!;
  const values = libraryValuesIn("im7-8552", "mm-MPa")!;
  assert.equal(Number(copied.own_E1), constants.E1);
  assert.equal(Number(copied.own_E2), constants.E2);
  assert.equal(Number(copied.own_G12), constants.G12);
  assert.equal(Number(copied.own_nu12), values.nu12);
  assert.equal(Number(copied.ply_thickness), constants.ply_thickness);
  assert.deepEqual([copied.own_F1t, copied.own_F1c, copied.own_F2t, copied.own_F2c, copied.own_F6].map(Number),
    [values.strengths!.F1t, values.strengths!.F1c, values.strengths!.F2t, values.strengths!.F2c, values.strengths!.F6]);
  // G13 and G23 carry the estimates the coupon was already built with, now the engineer's to change
  assert.deepEqual([copied.G13, copied.G23].map(Number), [values.estimates.G13, values.estimates.G23]);
  // what the check is sent: the own constants, no library id, and every number as it stood
  const sent = tensionValues({ ...reference, ...copied });
  assert.equal(sent.library, undefined);
  assert.equal(sent.own_E1, constants.E1);
  assert.equal(sent.own_F1t, values.strengths!.F1t);
  assert.equal(sent.G13, values.estimates.G13);
  // the engineer's own G13 is kept rather than overwritten by the estimate
  assert.equal(ownFromLibrary({ ...reference, G13: "5200" })!.G13, "5200");
  // a record whose id starts with a digit still gives a name a deck accepts (a letter first)
  assert.equal(ownNameFromLibrary("7781-5245c"), "M7781-5245C");
  assert.equal(ownFromLibrary({ ...reference, library: "" }), null);
  assert.equal(ownFromLibrary({ ...reference, library: "no-such-material" }), null);
});
