import assert from "node:assert/strict";
import test from "node:test";
import { asksWhy, factsOf, headed, HEADING_ROOM, readAt, whyLines } from "../lib/result-why";
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

test("an answer is shown in the page's symbols, its first sentence the heading, with the sections it rests on named under it (ADR-0102 amendment 1)", () => {
  const lines = whyLines(answer(), false);
  assert.deepEqual(lines.prose, ["Ply 4 (90 degrees) fails first: σ₂ reaches 60.6 MPa at 1.032 times the applied loading."]);
  // a first sentence of 88 characters is too long for a heading: it stands whole under a fixed one (ADR-0121 amendment 7)
  assert.equal(lines.heading, "Answered in words from the results");
  assert.deepEqual(lines.more, lines.prose);
  assert.equal(lines.note, "From the results and our theory pages.");
  assert.deepEqual(lines.sources, ["Laminate theory, 5. Failure"]);
  const two = whyLines(answer({ sources: [FAILURE, PLIES], prose: ["Ply 4 fails first.", "It is loaded across its fibres."] }), true);
  assert.equal(two.heading, "Ply 4 fails first.");
  assert.deepEqual(two.more, ["It is loaded across its fibres."]);
  assert.equal(two.note, "From the results and our theory pages. Preview: run the analysis to verify.");
  // where the result is read, from the fact sheet, leads the line (ADR-0102 amendment 2)
  assert.equal(whyLines(answer(), false, readAt({ basis: "the gauge section" })).note, "Read in the gauge section. From the results and our theory pages.");
  assert.equal(readAt({ basis: "" }), null);
  assert.deepEqual(two.sources, ["Laminate theory, 5. Failure", "Finite element theory, 6. Ply stresses in material axes"]);
});

test("a first sentence that fits is the heading; a longer one stands whole under the fixed heading, never cut (ADR-0121 amendment 7)", () => {
  const abd = "It's the laminate's stiffness matrix, linking loads to deformation."; // the fourth real run's, 67 characters
  assert.ok(abd.length > HEADING_ROOM);
  assert.deepEqual(headed([abd, "Its inverse gives deformation from load."], "Answered in words"),
    { heading: "Answered in words", more: [abd, "Its inverse gives deformation from load."] });
  const fits = "x".repeat(HEADING_ROOM);
  assert.deepEqual(headed([fits, "More."], "Answered in words"), { heading: fits, more: ["More."] });
});

test("an answer the theory pages do not cover says so and cites nothing", () => {
  const lines = whyLines(answer({ covered: false, sources: [], prose: ["The results show ply 4 in compression along its fibres."] }), false);
  assert.equal(lines.note, "From the results only.");
  assert.deepEqual(lines.sources, []);
});

test("with no answer written the page says so and names the sections the question found", () => {
  const none = whyLines(answer({ writer: "template", model: null, prose: [], covered: false, sources: [FAILURE, PLIES] }), false);
  assert.deepEqual(none.prose, []);
  assert.equal(none.heading, "No answer in words");
  assert.equal(none.note, "Not answered in words yet. See: Laminate theory, 5. Failure; Finite element theory, 6. Ply stresses in material axes.");
  const withheld = whyLines(answer({ writer: "template", model: null, prose: [], covered: false, withheld: true, reason: "73", sources: [FAILURE] }), false);
  assert.equal(withheld.note, "The answer held a number the results do not, so it is not shown. See: Laminate theory, 5. Failure.");
  assert.equal(whyLines(answer({ prose: [], covered: false, sources: [] }), false).note, "Not answered in words yet.");
});

test("a sentence that names a program is left out, and an answer of only such sentences is no answer (ADR-0091)", () => {
  const mixed = whyLines(answer({ prose: ["Ply 4 fails first.", "Abaqus would show the same."] }), false);
  assert.deepEqual(mixed.prose, ["Ply 4 fails first."]);
  const all = whyLines(answer({ prose: ["Abaqus would show the same."] }), false);
  assert.deepEqual(all.prose, []);
  assert.match(all.note, /^Not answered in words yet\./);
});

test("an answer from the API is read only in its own shape", () => {
  assert.equal(readResultAnswer(answer()).prose.length, 1);
  for (const bad of [null, {}, { ...answer(), prose: "text" }, { ...answer(), sources: [{ id: "a" }] }, { ...answer(), covered: "yes" }, { ...answer(), withheld: undefined }]) {
    assert.throws(() => readResultAnswer(bad), StudioError);
  }
});
