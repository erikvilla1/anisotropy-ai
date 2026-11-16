import assert from "node:assert/strict";
import test from "node:test";
import { asksWhy, factsOf, whyLines } from "../lib/result-why";
import { readResultAnswer, StudioError, type ResultAnswer } from "../lib/studio-api";

const FAILURE = { id: "engine:5-failure", document: "Laminate theory", title: "5. Failure" };
const PLIES = { id: "fea:6-ply-stresses-in-material-axes", document: "Finite element theory", title: "6. Ply stresses in material axes" };
const answer = (over: Partial<ResultAnswer> = {}): ResultAnswer => ({ run_id: null, writer: "anthropic", model: "m", covered: true, withheld: false, reason: null,
  prose: ["Ply 4 (90 degrees) fails first: sigma_2 reaches 60.6 MPa at 1.032 times the applied loading."], sources: [FAILURE], ...over });

test("a question of why or of meaning is told from a question about a value (ADR-0102)", () => {
  for (const text of ["why is ply 4 in compression?", "Why does the 90 fail first", "how come the shear is negative in ply 1?", "explain the Tsai-Hill index",
    "what causes the stress at the grips?", "what does the failure index mean?", "what is meant by first ply failure", "ply 4 is in compression, why?"]) {
    assert.equal(asksWhy(text), true, text);
  }
  for (const text of ["stress in ply 5 at element 120", "where is the shear stress highest?", "what is the stress here?", "which ply carries the most load?",
    "make it compression", "finer mesh", "I do not know why. Make it 300 mm long", "A. Whyte"]) {
    assert.equal(asksWhy(text), false, text);
  }
});

test("a question is answered from a fact sheet that holds facts, and an older result has none", () => {
  assert.deepEqual(factsOf({ facts: { reaction: 16220 } }), { reaction: 16220 });
  assert.equal(factsOf({ facts: {} }), null);
  assert.equal(factsOf(null), null);
});

test("an answer is shown in the page's symbols with the sections it rests on named under it", () => {
  const lines = whyLines(answer(), false);
  assert.deepEqual(lines.prose, ["Ply 4 (90 degrees) fails first: σ₂ reaches 60.6 MPa at 1.032 times the applied loading."]);
  assert.equal(lines.note, "From the results and the theory: Laminate theory, 5. Failure. Every number is the results’ own.");
  const two = whyLines(answer({ sources: [FAILURE, PLIES] }), true);
  assert.equal(two.note, "From the results and the theory: Laminate theory, 5. Failure; Finite element theory, 6. Ply stresses in material axes. Every number is the results’ own. From the preview: run the analysis to verify it.");
});

test("an answer the theory pages do not cover says so and cites nothing", () => {
  const lines = whyLines(answer({ covered: false, sources: [], prose: ["The results show ply 4 in compression along its fibres."] }), false);
  assert.equal(lines.note, "From the results; the theory pages do not explain this yet. Every number is the results’ own.");
  assert.deepEqual(lines.sources, []);
});

test("with no answer written the page says so and names the sections the question found", () => {
  const none = whyLines(answer({ writer: "template", model: null, prose: [], covered: false, sources: [FAILURE, PLIES] }), false);
  assert.deepEqual(none.prose, []);
  assert.equal(none.note, "A question like this is not answered in words here yet. Sections of the theory behind it: Laminate theory, 5. Failure; Finite element theory, 6. Ply stresses in material axes.");
  const withheld = whyLines(answer({ writer: "template", model: null, prose: [], covered: false, withheld: true, reason: "73", sources: [FAILURE] }), false);
  assert.equal(withheld.note, "An answer was written, but it held a number the results do not, so it is not shown. Section of the theory behind it: Laminate theory, 5. Failure.");
  assert.equal(whyLines(answer({ prose: [], covered: false, sources: [] }), false).note, "A question like this is not answered in words here yet.");
});

test("a sentence that names a program is left out, and an answer of only such sentences is no answer (ADR-0091)", () => {
  const mixed = whyLines(answer({ prose: ["Ply 4 fails first.", "Abaqus would show the same."] }), false);
  assert.deepEqual(mixed.prose, ["Ply 4 fails first."]);
  const all = whyLines(answer({ prose: ["Abaqus would show the same."] }), false);
  assert.deepEqual(all.prose, []);
  assert.match(all.note, /^A question like this is not answered in words here yet\./);
});

test("an answer from the API is read only in its own shape", () => {
  assert.equal(readResultAnswer(answer()).prose.length, 1);
  for (const bad of [null, {}, { ...answer(), prose: "text" }, { ...answer(), sources: [{ id: "a" }] }, { ...answer(), covered: "yes" }, { ...answer(), withheld: undefined }]) {
    assert.throws(() => readResultAnswer(bad), StudioError);
  }
});
