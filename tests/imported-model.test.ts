import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { importModel, MAX_MODEL_BYTES, MODEL_NAME_HEADER, MODEL_UNITS, readImportedModel, readPreview, StudioError } from "../lib/studio-api";
import { bannedIn, bannedInAbaqusCard, importProblemWords, importText, importUnreadLines } from "../lib/studio-copy";
import { resultsOnPage } from "../components/studio/use-imported-model";
import formDefinition from "../lib/coupon-form-definition.json";

const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio-import/${name}.json`, "utf8"));
/** The API's answer for the public gripped coupon, as `studio_tool.py import` wrote its parts (ADR-0105). */
const answer = (changes: Record<string, unknown> = {}) => ({ run_id: null, ...fixture("import"), solver: "kernel", warm: true, seconds: 0.4, timings: {},
  preview: fixture("preview"), fields: fixture("fields"), explanation: fixture("explanation"), ...changes });
const refused = { run_id: "r2", state: "refused", name: "solid.inp", units: "mm-MPa", solver: "kernel", warm: true, seconds: 0.1, timings: {},
  problem: { message: "line 15: this version does not read solid elements (C3D8R). It reads flat four-node shells (S4, S4R, S4R5)", line: 15,
    unread: [{ what: "solid elements", keyword: "C3D8R", lines: [15] }] },
  reading: null, preview: null, fields: null, explanation: null };

test("the import's answer is read as the package wrote it, and other shapes are refused", () => {
  const solved = readImportedModel(answer());
  assert.equal(solved.state, "solved");
  assert.equal(solved.reading?.elements, 16);
  assert.equal(solved.reading?.layup, "[0/30/-30/30/0]s");
  assert.equal(solved.fields?.mesh.element_count, 16);
  assert.equal(solved.preview?.coupon.kind, "imported");
  assert.ok(solved.explanation?.sentences.length);
  const not = readImportedModel(refused);
  assert.deepEqual([not.state, not.problem?.line, not.reading, not.fields], ["refused", 15, null, null]);
  assert.deepEqual(not.problem?.unread, [{ what: "solid elements", keyword: "C3D8R", lines: [15] }]);
  // an answer written before the survey has no list, and an entry that is not one is left out
  assert.deepEqual(readImportedModel({ ...refused, problem: { message: "line 3: no", line: 3 } }).problem?.unread, []);
  assert.deepEqual(readImportedModel({ ...refused, problem: { message: "no", line: 3, unread: [{ what: "contact" }, { what: "contact", keyword: "*Tie", lines: [4] }] } }).problem?.unread.length, 1);
  const read = readImportedModel(answer({ state: "read", fields: null, explanation: null, problem: { message: "the stiffness matrix is singular", line: null } }));
  assert.deepEqual([read.state, read.fields, read.problem?.line], ["read", null, null]);
  assert.throws(() => readImportedModel(answer({ fields: null })), StudioError); // solved, with nothing solved
  assert.throws(() => readImportedModel(answer({ reading: null })), StudioError); // taken, with no account of what was taken
  assert.throws(() => readImportedModel({ ...refused, problem: null }), StudioError); // refused, with no reason
  assert.throws(() => readImportedModel(answer({ state: "ready" })), StudioError);
});

test("an imported model is drawn with or without a load; a coupon's preview still needs one", () => {
  const preview = fixture("preview");
  assert.equal(readPreview({ ...preview, loaded: null, loads: [] }).loaded, null);
  assert.throws(() => readPreview({ ...preview, loaded: null, coupon: { ...preview.coupon, kind: "unnotched_tension" } }), StudioError);
});

test("the file goes as the body, the units in the address and the name in a header, never in the address", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(answer()), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  try {
    const file = new Blob(["*Heading\n"]);
    const model = await importModel("http://api.test/", file, "wing panel é.inp", "in-psi");
    assert.equal(model.state, "solved");
    assert.equal(calls[0].url, "http://api.test/v1/imported-models?units=in-psi");
    assert.equal(calls[0].init.method, "POST");
    assert.equal(calls[0].init.body, file);
    const headers = calls[0].init.headers as Record<string, string>;
    assert.equal(headers[MODEL_NAME_HEADER], "wing%20panel%20%C3%A9.inp");
    assert.equal(headers["X-Anisotropy-Actor"], "studio");
    // a file past the size is refused here, before it is sent
    await assert.rejects(() => importModel("http://api.test", { size: MAX_MODEL_BYTES + 1 } as Blob, "big.inp", "mm-MPa"), /larger than 20 MB/);
    assert.equal(calls.length, 1);
    globalThis.fetch = (async () => new Response(JSON.stringify({ detail: "This model took too long to solve here. Try a coarser mesh." }), { status: 422 })) as typeof fetch;
    await assert.rejects(() => importModel("http://api.test", file, "slow.inp", "mm-MPa"), (error: StudioError) => error.message === "This model took too long to solve here. Try a coarser mesh.");
    globalThis.fetch = (async () => new Response(JSON.stringify({ detail: "Importing a model is not offered yet." }), { status: 403 })) as typeof fetch;
    await assert.rejects(() => importModel("http://api.test", file, "m.inp", "mm-MPa"), /The model could not be imported\. Reload/);
  } finally {
    globalThis.fetch = original;
  }
});

test("the units offered for a model are the package's four", () => {
  assert.deepEqual([...MODEL_UNITS], Object.keys(formDefinition.unit_systems));
});

test("why a file was not read is said in the reader's words when they are fit to show, with its line", () => {
  assert.equal(importProblemWords(refused), "Line 15: this version does not read solid elements (C3D8R). It reads flat four-node shells (S4, S4R, S4R5)");
  // several kinds of thing that are not read: the count, and each on a line of its own with the keyword the file writes and where
  const several = [{ what: "second-order shell elements", keyword: "S8R", lines: [15] }, { what: "contact", keyword: "*Contact Pair", lines: [212, 230] },
    { what: "a tie between surfaces", keyword: "*Tie", lines: [190, 194, 198, 202, 206] }, { what: "the keyword *Thing", keyword: "*Thing", lines: [7] }];
  assert.equal(importProblemWords({ state: "refused", problem: { message: "this file holds 4 things that this version does not read: ...", line: 15, unread: several } }),
    "This file holds 4 things that are not read yet:");
  assert.deepEqual(importUnreadLines(several), ["Second-order shell elements (S8R), line 15", "Contact (*Contact Pair), lines 212 and 230",
    "A tie between surfaces (*Tie), lines 190, 194 and 198, and 2 more", "The keyword *Thing, line 7"]);
  assert.deepEqual(importUnreadLines([{ what: "the keyword *Claude", keyword: "*Claude", lines: [1] }]), []); // a banned word is not shown, whoever wrote it
  assert.equal(importProblemWords({ state: "solved", problem: null }), null);
  // words that name our own files or tools are not shown: the plain thing instead, still with the line
  assert.equal(importProblemWords({ state: "refused", problem: { message: "line 8: see fea/README.md for the supported subset", line: 8 } }),
    "This file holds something that is not read yet. The problem is on line 8.");
  assert.equal(importProblemWords({ state: "read", problem: { message: "CalculiX would be needed", line: null } }), "This model could not be solved as it stands.");
  // the engineer's own Abaqus may be named, as on the card of their own Abaqus; nothing else that is banned may
  const note = "line 106: reference node Assembly.2 is listed inside its own coupled set; it is dropped (Abaqus runs the deck as written)";
  assert.equal(importText(note), note);
  assert.deepEqual(bannedIn(note), ["Abaqus"]);
  assert.deepEqual(bannedInAbaqusCard(note), []);
  assert.equal(importText("our engine refused it"), null);
});

test("while a model is open the stage and the assistant are its; closed, the coupon's results stand", () => {
  const model = readImportedModel(answer());
  const live = { fields: model.fields, explanation: { writer: "template", facts: { a: 1 }, sentences: ["live"], setup_sentences: [] } };
  const run = { fields: null, live: live as never, liveAt: 5, fieldsAt: 0, explanation: null };
  const open = resultsOnPage(run, { open: true, model });
  assert.deepEqual([open.imported, open.live, open.fields === model.fields, open.explanation === model.explanation], [true, false, true, true]);
  // open with nothing solved (a refusal, or before a file is sent): no results to answer from, never the coupon's behind it
  assert.deepEqual(resultsOnPage(run, { open: true, model: null }), { fields: null, live: false, explanation: null, imported: true, past: false, readOnly: true });
  const closed = resultsOnPage(run, { open: false, model });
  assert.deepEqual([closed.imported, closed.live, closed.explanation?.sentences[0], closed.readOnly], [false, true, "live", false]);
  // a past run opened again (ADR-0109) has the stage as it was solved: its own fields and words, never the project's live answer behind it
  const stored = { open: true, fields: model.fields, explanation: { writer: "template", facts: { a: 2 }, sentences: ["as it was solved"], setup_sentences: [] } as never };
  const past = resultsOnPage(run, { open: false, model }, stored);
  assert.deepEqual([past.past, past.readOnly, past.live, past.imported, past.fields === model.fields, past.explanation?.sentences[0]], [true, true, false, false, true, "as it was solved"]);
  assert.equal(resultsOnPage(run, { open: true, model }, stored).imported, true); // a model being imported keeps the stage
  assert.equal(resultsOnPage(run, { open: false, model }, { ...stored, open: false }).past, false);
});
