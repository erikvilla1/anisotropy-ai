import assert from "node:assert/strict";
import test from "node:test";
import { routeMessage, type ChatState } from "../lib/chat-route";
import { modelFileAnswer, modelFileAsked, programNamed } from "../lib/model-file";
import { bannedIn } from "../lib/studio-copy";
import { MODEL_FILE_LABELS } from "../lib/studio-api";
import { exampleForm } from "../lib/studio-form";

const state = (results: boolean): ChatState => ({
  form: exampleForm("2026-11-20"), readOnly: false, results, facts: results, api: true, modelReads: true, onPlate: false, ready: true, step: null, about: null,
  thread: null, sections: true,
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

test("the answer offers the files this visitor may have, says what the Ansys file is not yet, and stays in the product's words (ADR-0129, ADR-0091)", () => {
  const all = modelFileAnswer(null, { ansys: true, readOnly: false });
  assert.equal(all.title, "Download the model");
  assert.deepEqual(all.offers, ["abaqus", "ansys"]);
  assert.match(all.lines.join(" "), /has not been run in Ansys yet/);

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
