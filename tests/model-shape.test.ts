import assert from "node:assert/strict";
import test from "node:test";
import { modelFileAnswer } from "../lib/model-file";
import { modelDownloadsOffered, readShapeParts, savedLine, shapePartLines, STEP_FILE, STEP_FILE_NOTE, STEP_FILE_NOTE_ALONE, STEP_FILE_NOTE_ONE_MATERIAL, stepFileNote, type ShapeParts } from "../lib/model-shape";
import { MODEL_FILE_LABELS, modelFile, StudioError } from "../lib/studio-api";
import { ANALYSIS_UNAVAILABLE, bannedIn } from "../lib/studio-copy";

/** The part table as the API sends it in `X-Anisotropy-Model-Parts`: JSON in ASCII, so the cubed sign travels escaped. These are the
 * values `fea/tools/studio_tool.py model --program step` wrote for a tension coupon with bonded tabs. */
const TABBED = String.raw`{"title":"IM7-UNT-L1","units":{"length":"mm","volume":"mm³","step":"mm"},"parts":[` +
  `{"name":"Laminate","kind":"laminate","layup":"[45/0/-45/90]s","plies":8,"ply_thickness":0.18288,"thickness":1.46304,"material":"IM7-8552","volume":9144.0,"in_model":true},` +
  ["Bottom tab, top face", "Bottom tab, bottom face", "Top tab, top face", "Top tab, bottom face"].map((name) =>
    `{"name":"${name}","kind":"tab","layup":null,"plies":null,"ply_thickness":null,"thickness":1.5,"material":"E-glass/epoxy","volume":1870.94,"in_model":false}`).join(",") + "]}";

const table = (parts: Partial<ShapeParts["parts"][number]>[], length = "mm"): ShapeParts => ({
  title: "T", units: { length, volume: `${length}³`, step: "mm" },
  parts: parts.map((part) => ({ name: "Laminate", kind: "laminate", layup: "[0/90]s", plies: 4, ply_thickness: 0.125, thickness: 0.5, material: "IM7-8552", volume: 1, in_model: true, ...part })),
});

test("the menu offers the shape after the solver files this visitor is offered, to everyone, under the name CAD (STEP) (ADR-0146)", () => {
  assert.deepEqual(modelDownloadsOffered(["abaqus", "ansys"]), ["abaqus", "ansys", "step"]);
  assert.deepEqual(modelDownloadsOffered(["abaqus"]), ["abaqus", "step"]); // where the Ansys file is closed, the shape is still offered
  assert.equal(STEP_FILE, "step");
  assert.equal(MODEL_FILE_LABELS.step, "CAD (STEP)");
  assert.equal(MODEL_FILE_LABELS.abaqus, "Abaqus input file (.inp)"); // the other two keep their names (ADR-0129)
  assert.equal(MODEL_FILE_LABELS.ansys, "Ansys input file (.cdb)");
});

test("the assistant's answer still offers the two solver files alone: the shape is the menu's (ADR-0146)", () => {
  assert.deepEqual(modelFileAnswer(null, { ansys: true, readOnly: false }).offers, ["abaqus", "ansys"]);
});

test("the part table that comes with the file is read as sent, and anything else is no table at all", () => {
  const read = readShapeParts(TABBED);
  assert.ok(read);
  assert.equal(read.title, "IM7-UNT-L1");
  assert.deepEqual(read.units, { length: "mm", volume: "mm³", step: "mm" });
  assert.equal(read.parts.length, 5);
  assert.deepEqual(read.parts[0], { name: "Laminate", kind: "laminate", layup: "[45/0/-45/90]s", plies: 8, ply_thickness: 0.18288, thickness: 1.46304,
    material: "IM7-8552", volume: 9144, in_model: true });
  assert.deepEqual(read.parts[4], { name: "Top tab, bottom face", kind: "tab", layup: null, plies: null, ply_thickness: null, thickness: 1.5,
    material: "E-glass/epoxy", volume: 1870.94, in_model: false });
  for (const raw of [null, undefined, "", "not json", "[]", "{}", '{"units":{"length":"mm","step":"mm"},"parts":[]}',
    '{"units":{"length":"mm","step":"mm"},"parts":[{"name":"Laminate"}]}', // no thickness: half a line is not printed
    '{"units":{"length":"mm","step":"mm"},"parts":[{"name":"","thickness":1}]}',
    '{"units":{"step":"mm"},"parts":[{"name":"Laminate","thickness":1}]}']) assert.equal(readShapeParts(raw), null, String(raw));
});

test("each solid has one line: its name, its layup as the coupon writes it, its plies, its thickness and its material", () => {
  const lines = shapePartLines(readShapeParts(TABBED)!);
  assert.equal(lines.length, 5);
  assert.equal(lines[0], "Laminate: [45/0/-45/90]s, 8 plies of 0.1829 mm, 1.463 mm thick, IM7-8552.");
  assert.equal(lines[1], "Bottom tab, top face: 1.5 mm thick, E-glass/epoxy. Drawn as stated. The analysis grips this length and does not include the tab's material.");
  assert.equal(new Set(lines).size, 5, "the lines are the list's keys: each is its own");
  // one material and no plies; one ply; a material that was not stated; inches
  assert.deepEqual(shapePartLines(table([{ name: "Coupon", kind: "coupon", layup: null, plies: null, ply_thickness: null, thickness: 3.2, material: "Nylon 6" }])),
    ["Coupon: one material, 3.2 mm thick, Nylon 6."]);
  assert.deepEqual(shapePartLines(table([{ layup: "[0]", plies: 1, ply_thickness: 1, thickness: 1 }])), ["Laminate: [0], 1 ply of 1 mm, 1 mm thick, IM7-8552."]);
  assert.deepEqual(shapePartLines(table([{ name: "Top tab, top face", kind: "tab", layup: null, plies: null, ply_thickness: null, thickness: 1.5, material: null, in_model: false }]))[0]
    .startsWith("Top tab, top face: 1.5 mm thick, material not stated. Drawn as stated."), true);
  assert.deepEqual(shapePartLines(table([{ ply_thickness: 0.0072, thickness: 0.0288 }], "in")), ["Laminate: [0/90]s, 4 plies of 0.0072 in, 0.0288 in thick, IM7-8552."]);
});

test("what the page says of a STEP file states where the layup is and stays in the product's words (ADR-0146, ADR-0091)", () => {
  assert.match(STEP_FILE_NOTE, /one solid at its thickness, in millimetres/);
  assert.match(STEP_FILE_NOTE, /holds no plies, so the layup is listed here and in the file's first lines/);
  assert.equal(stepFileNote(readShapeParts(TABBED)), STEP_FILE_NOTE);
  // a coupon of one material has no layup to list: the note names the material, as its part line does
  const plastic = table([{ name: "Coupon", kind: "coupon", layup: null, plies: null, ply_thickness: null, thickness: 3.2, material: "Nylon 6" }]);
  assert.equal(stepFileNote(plastic), STEP_FILE_NOTE_ONE_MATERIAL);
  assert.equal(STEP_FILE_NOTE_ONE_MATERIAL, "Each part is one solid at its thickness, in millimetres. The file holds the shape only, so the material is listed here and in the file's first lines.");
  assert.doesNotMatch(STEP_FILE_NOTE_ONE_MATERIAL, /layup|plies/);
  // a plastic coupon with tabs is still one material and no layup; a laminate beside a part without plies still has its layup listed
  assert.equal(stepFileNote(table([{ layup: null, plies: null }, { name: "Top tab, top face", kind: "tab", layup: null, plies: null, in_model: false }])), STEP_FILE_NOTE_ONE_MATERIAL);
  assert.equal(stepFileNote(table([{}, { name: "Top tab, top face", kind: "tab", layup: null, plies: null, in_model: false }])), STEP_FILE_NOTE);
  // no table came with the file (it is left out past the header's limit): the note lists nothing "here" and is true of either model
  assert.equal(stepFileNote(null), STEP_FILE_NOTE_ALONE);
  assert.equal(STEP_FILE_NOTE_ALONE, "Each part is one solid at its thickness, in millimetres. The file holds the shape only; what each part is made of is in the file's first lines.");
  assert.doesNotMatch(STEP_FILE_NOTE_ALONE, /here|layup/);
  assert.equal(savedLine("step", MODEL_FILE_LABELS.step), "Saved the STEP file.");
  assert.equal(savedLine("ansys", MODEL_FILE_LABELS.ansys), "Saved the Ansys input file (.cdb)."); // as before (ADR-0129)
  const said = [MODEL_FILE_LABELS.step, STEP_FILE_NOTE, STEP_FILE_NOTE_ONE_MATERIAL, STEP_FILE_NOTE_ALONE, savedLine("step", MODEL_FILE_LABELS.step), ...shapePartLines(readShapeParts(TABBED)!)];
  for (const line of said) {
    assert.deepEqual(bannedIn(line), [], line);
    assert.doesNotMatch(line, /[—–]/, line); // no dash used as punctuation
  }
});

test("the page asks for the shape as it asks for the other files, and reads the name and the part table from the answer's headers", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const original = globalThis.fetch;
  const step = "ISO-10303-21;\nHEADER;\n";
  try {
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(step, { status: 200, headers: { "Content-Type": "model/step", "X-Anisotropy-Model-File": "IM7-UNT-L1.step", "X-Anisotropy-Model-Parts": TABBED } });
    }) as typeof fetch;
    const file = await modelFile("http://api.test/", { test: "unnotched tension" }, "step");
    assert.equal(calls[0].url, "http://api.test/v1/coupon-jobs/model?program=step");
    assert.equal(calls[0].init.method, "POST");
    assert.deepEqual(JSON.parse(String(calls[0].init.body)), { values: { test: "unnotched tension" } });
    assert.equal(file.name, "IM7-UNT-L1.step");
    assert.equal(file.text, step);
    assert.equal(file.parts?.parts.length, 5);
    // a solver file has no part table, whatever the answer carries; a STEP file without its name or table is still saved, under a plain name
    assert.equal((await modelFile("http://api.test", {}, "abaqus")).parts, null);
    globalThis.fetch = (async () => new Response(step, { status: 200 })) as typeof fetch;
    const bare = await modelFile("http://api.test", {}, "step");
    assert.deepEqual({ name: bare.name, parts: bare.parts }, { name: "model.step", parts: null });
    // a shape that cannot be drawn is said in the service's words; where the shape cannot be built at all, the outage line
    const refusal = "This model cannot be drawn as a STEP file yet: The tabs cannot be drawn: they are 60 mm long and the dog-bone's full width ends 20 mm from each end, so they reach the fillet, where their outline is not stated.";
    globalThis.fetch = (async () => new Response(JSON.stringify({ detail: refusal }), { status: 422 })) as typeof fetch;
    await assert.rejects(() => modelFile("http://api.test", {}, "step"), (error: StudioError) => error.message === refusal && error.status === 422);
    assert.deepEqual(bannedIn(refusal), []);
    globalThis.fetch = (async () => new Response(JSON.stringify({ detail: "The shape builder is not installed here" }), { status: 503 })) as typeof fetch;
    await assert.rejects(() => modelFile("http://api.test", {}, "step"), (error: StudioError) => error.message === ANALYSIS_UNAVAILABLE && error.status === 503);
  } finally {
    globalThis.fetch = original;
  }
});
