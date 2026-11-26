import assert from "node:assert/strict";
import test from "node:test";
import { aboutAnswer, aboutAsked } from "../lib/chat-about";
import { routeMessage, type ChatState } from "../lib/chat-route";
import { modelFileAnswer, modelFileAsked, programNamed } from "../lib/model-file";
import { bannedIn } from "../lib/studio-copy";
import { MODEL_FILE_LABELS, MODEL_FILE_OPENING } from "../lib/studio-api";
import { exampleForm } from "../lib/studio-form";

const state = (results: boolean): ChatState => ({
  form: exampleForm("2026-11-20"), readOnly: false, results, facts: results, api: true, modelReads: true, onPlate: false, ready: true, step: null, about: null,
  thread: null, sections: true, plates: true,
});

test("a request for the model as a file is read, with the program it names (ADR-0129)", () => {
  const asked: [string, "abaqus" | "ansys" | null][] = [
    ["Download abaqus model", "abaqus"],
    ["download ansys model", "ansys"],
    ["donwload ansys modle", "ansys"], // typed fast
    ["Download the model", null],
    ["export model", null],
    ["can i get this as an ansys file?", "ansys"],
    ["export to Ansys", "ansys"],
    ["give me the inp", "abaqus"],
    ["i need the cdb", "ansys"],
    ["abaqus input file please", "abaqus"],
    ["how do i get the abaqus model", "abaqus"],
    ["send me the model for ansys", "ansys"],
    ["can I open this in ansys", "ansys"],
    ["save the model as abaqus", "abaqus"],
    ["get me the input file", null],
    ["download the model for abaqus and ansys", null], // both named: both offered
  ];
  for (const [text, program] of asked) {
    assert.deepEqual(modelFileAsked(text), { program }, text);
    for (const results of [false, true]) assert.deepEqual(routeMessage(text, state(results)), { route: "model-file", program }, text);
  }
});

test("a file coming in, work done elsewhere, a question about a file, and the report are not requests for the model's file (ADR-0129)", () => {
  for (const text of [
    "import an ansys model", "upload an abaqus model", "I have an ansys model, can I bring it in", "open my model",
    "can you run this in ansys", "how does this compare with ansys", "what is an abaqus input file", "what does abaqus call a fixed edge",
    "download the report", "download the pdf", "export the results", "download the step file",
    "which ply fails first", "change the width to 35 mm", "model the plate with a pressure", "get the modulus", "what is the model",
  ]) {
    assert.equal(modelFileAsked(text), null, text);
    for (const results of [false, true]) assert.notEqual(routeMessage(text, state(results)).route, "model-file", text);
  }
  assert.equal(programNamed("abaqus or ansys"), null);
  assert.equal(programNamed("the .cdb"), "ansys");
  assert.equal(programNamed("the inp"), "abaqus");
  assert.equal(programNamed("input"), null);
});

test("the answer offers the files this visitor may have, says to compare the Ansys file's reaction, and stays in the product's words (ADR-0129, ADR-0091)", () => {
  const all = modelFileAnswer(null, { ansys: true, readOnly: false });
  assert.equal(all.title, "Download the model");
  assert.deepEqual(all.offers, ["abaqus", "ansys"]);
  assert.match(all.lines.join(" "), /Compare the Ansys file's reaction with the one shown here/);

  const one = modelFileAnswer("abaqus", { ansys: true, readOnly: false });
  assert.deepEqual(one.offers, ["abaqus"]);
  assert.doesNotMatch(one.lines.join(" "), /Ansys/);

  // a customer: the Ansys file is not offered yet, and the answer says so instead of handing over the other file in silence
  assert.deepEqual(modelFileAnswer(null, { ansys: false, readOnly: false }).offers, ["abaqus"]);
  const notYet = modelFileAnswer("ansys", { ansys: false, readOnly: false });
  assert.equal(notYet.title, "Not as an Ansys file yet");
  assert.deepEqual(notYet.offers, ["abaqus"]);

  // an imported model or a past run: its rows are not the setup's, so no file is offered
  const readOnly = modelFileAnswer("ansys", { ansys: true, readOnly: true });
  assert.deepEqual(readOnly.offers, []);
  assert.match(readOnly.lines[0], /imported model or a past run/);

  for (const answer of [all, one, notYet, readOnly]) {
    for (const sentence of [answer.title, ...answer.lines, ...answer.offers.map((p) => MODEL_FILE_LABELS[p])]) assert.deepEqual(bannedIn(sentence), [], sentence);
    assert.ok(answer.lines.length <= 2, answer.title);
  }
});

test("how the downloaded file opens in the engineer's own program is answered in fixed words, and so is the error a job gives when only its mesh came in (ADR-0129 amendment 5)", () => {
  const asked: [string, string | null][] = [
    ["how do I open the inp in abaqus", "model-file-open"], ["how do i import this model into Abaqus?", "model-file-open"],
    ["where do I load the downloaded file in abaqus cae", "model-file-open"], ["how do I run it in abaqus", "model-file-open"],
    ["THIS MODEL HAS EITHER INCORRECT OR NO ELEMENT DEFINITIONS", "model-file-open"], ["abaqus says no element definitions", "model-file-open"],
    ["why is the imported model empty in abaqus", "model-file-open"], ["why won't the job run in abaqus after I import the file", "model-file-open"],
    // a request for the file, a model brought in here, what a file is and a question of the results are read by others
    ["what is an abaqus input file", "model-file-what"], ["import an abaqus model", null], ["why is ply 4 in compression", null],
    ["how does this compare with abaqus", null], ["what element type does abaqus use", null],
  ];
  for (const [text, topic] of asked) assert.equal(aboutAsked(text), topic, text);
  assert.deepEqual(modelFileAsked("can I open this in Abaqus?"), { program: "abaqus" }); // still an offer of the file
  for (const text of ["how do I open the inp in abaqus", "abaqus says no element definitions"]) assert.equal(modelFileAsked(text), null, text);
  const form = exampleForm("2026-11-25");
  const said = aboutAnswer("model-file-open", "how do I open the inp in abaqus", { form, results: false, readOnly: false });
  assert.equal(said.title, "Open it with File > Import > Model");
  assert.match(said.lines.join(" "), /File > Import > Part brings in the mesh only/);
  assert.match(said.lines.join(" "), /download the model/);
  assert.ok(!aboutAnswer("model-file-open", "", { form, results: true, readOnly: true }).lines.some((line) => /download the model/.test(line)));
  for (const line of [said.title, ...said.lines, MODEL_FILE_OPENING.abaqus ?? ""]) assert.deepEqual(bannedIn(line), [], line); // the customer's words (ADR-0091)
  assert.match(MODEL_FILE_OPENING.abaqus ?? "", /^Open it with File > Import > Model/);
  assert.equal(MODEL_FILE_OPENING.ansys, undefined); // its menus were not tried with the file: nothing is said
});

test("what a model file is, where the report is and a model brought in from another program are answered in fixed words, and are no request for a file (ADR-0129 amendment 1)", () => {
  const asked: [string, string | null][] = [
    ["what is an abaqus input file", "model-file-what"], ["whats a cdb file", "model-file-what"], ["what is a deck?", "model-file-what"],
    ["download the report", "report"], ["where is the pdf", "report"], ["how do i get the report", "report"],
    ["import an ansys model", "bring-in"], ["can i upload a nastran file?", "bring-in"],
    // a value asked for with the verb "report", a question of why, a load and an Abaqus file brought in are read by others
    ["report the stress in ply 3", null], ["why is the report empty", null], ["load 10 kN", null], ["import an abaqus model", null], ["what is in the report", null],
  ];
  for (const [text, topic] of asked) {
    assert.equal(aboutAsked(text), topic, text);
    assert.equal(modelFileAsked(text), null, text);
  }
  const form = exampleForm("2026-11-20");
  const report = aboutAnswer("report", "download the report", { form, results: false, readOnly: false });
  assert.equal(report.title, "The report is under Files");
  assert.ok(report.lines.some((line) => line.includes("no result yet")));
  for (const topic of ["model-file-what", "report", "bring-in"] as const) {
    const said = aboutAnswer(topic, "import an ansys model", { form, results: true, readOnly: false });
    for (const line of [said.title, ...said.lines]) assert.deepEqual(bannedIn(line), [], line); // the customer's words (ADR-0091)
    assert.ok(![said.title, ...said.lines].some((line) => /nastran/i.test(line)), topic); // another program is not named back
  }
});
