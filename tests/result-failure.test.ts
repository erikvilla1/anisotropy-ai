import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { asksFailure, failureAnswer, failureLines, failureLoading } from "../lib/result-failure";
import { readResultQuestion, questionFrom } from "../lib/result-question";
import { asksWhy } from "../lib/result-why";
import { asksWorking } from "../lib/result-working";
import { readResultReading, type Fields } from "../lib/studio-api";

const fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8")) as Fields;
const print = (value: number) => String(Number(value.toPrecision(4)));

test("a question of which ply fails, whether it fails or at what load is told from a value, a why, a formula and a setup line (ADR-0099 amendment 1)", () => {
  for (const text of ["what is the the ply that fails", "which ply fails first?", "what ply fails", "does it fail?", "will it fail", "when does it fail",
    "at what load does it fail?", "where does it fail", "which layer breaks first", "what fails first", "first ply failure", "the first ply to fail?", "fpf",
    "will it hold?", "does the coupon hold", "what is the failure load", "what is the strength ratio?", "failure load", "is the laminate going to fail",
    "which ply fails first by tsai-wu?", "does it fail in compression?", "What Ply Is Failing"]) {
    assert.equal(asksFailure(text), true, text);
  }
  for (const text of ["stress in ply 5 at element 120", "where is the shear stress highest?", "make it [0/90]2s", "use the Tsai-Wu failure criterion",
    "add max strain failure", "finer mesh", "A. Engineer", "run", "check", "10 kN in tension", "did the run fail?", "is the mesh failing", "the upload failed, what now?",
    "which failure criteria can I use?", "what criteria are available for failure", "hold this edge", "pull it 2 mm", "tsai-hill and max stress"]) {
    assert.equal(asksFailure(text), false, text);
  }
  // the readers before it in the chat keep their own: a why, a formula and a value are not taken for it, and it is not taken for them
  assert.equal(asksWhy("why does ply 4 fail first?"), true);
  assert.equal(asksWorking("show me the formula for the failure"), true);
  for (const text of ["what is the the ply that fails", "which ply fails first?", "does it fail?"]) {
    assert.equal(asksWhy(text), false, text);
    assert.equal(asksWorking(text), false, text);
    assert.equal(readResultQuestion(text), null, text);
  }
});

test("the answer is the package's own first-ply failure: the governing criterion, or the one the message names", () => {
  const found = failureAnswer(fields, "what is the the ply that fails");
  assert.ok(found);
  const gauge = fields.summary.fpf_gauge!;
  assert.equal(found.answer.basis, "gauge");
  assert.equal(found.row.criterion, fields.summary.verdict!.earliest);
  assert.equal(found.row.ply, gauge[found.row.criterion].ply);
  assert.equal(found.row.factor, gauge[found.row.criterion].factor);
  assert.equal(found.missing, null);

  const named = failureAnswer(fields, "which ply fails first by maximum stress?");
  assert.equal(named?.row.criterion, "max_stress");
  assert.equal(named?.row.factor, gauge.max_stress.factor);

  const others = { ...fields, summary: { ...fields.summary, fpf_gauge: { tsai_hill: gauge.tsai_hill } } } as Fields;
  const missing = failureAnswer(others, "does it fail by tsai-wu?");
  assert.equal(missing?.row.criterion, "tsai_hill");
  assert.equal(missing?.missing, "Tsai-Wu");

  assert.equal(failureAnswer({ ...fields, summary: { ...fields.summary, verdict: undefined } } as Fields, "does it fail?"), null); // a result solved before the answer was written
});

test("the answer is three short lines: the ply, the loading with the verdict, and what it rests on, in the package's numbers", () => {
  const found = failureAnswer(fields, "which ply fails first?")!;
  const row = fields.summary.fpf_gauge!.tsai_hill;
  const loading = `${print(row.at_failure!.applied)} mm, ${print(row.at_failure!.reaction)} N`;
  const lines = failureLines(found, print);
  assert.equal(lines.headline, "Ply 4 (90°) fails first");
  assert.equal(lines.loading, `At ${print(row.factor)} × the applied load (${loading}). The coupon holds.`);
  assert.deepEqual(lines.facts, ["Tsai-Hill", "combined stresses", "element 183", "gauge section", "tied with ply 5"]);
  assert.equal(failureLoading(found.answer, found.row, print), loading);
  assert.ok(lines.headline.length + lines.loading.length < 100, "short enough to read at a glance");

  // a coupon that fails says so in the same line
  const failing = { ...found, row: { ...found.row, fails: true, factor: 0.9435 } };
  assert.match(failureLines(failing, print).loading, /^At 0\.9435 × the applied load \(.+\)\. The coupon fails\.$/);
  // a criterion that is named is the one the lines are of
  const named = failureAnswer(fields, "by max stress, which ply fails?")!;
  assert.equal(failureLines(named, print).facts[0], "Maximum stress");
  assert.match(failureLines(named, print).loading, new RegExp(`^At ${String(print(fields.summary.fpf_gauge!.max_stress.factor)).replace(".", "\\.")} ×`));
});

test("a model's reading of the kind failure is kept as read and is no question of the probe table (ADR-0100 amendment 1)", () => {
  const request = { kind: "failure", quantities: [], plies: [], element: null, here: false, sense: null, region: "default" };
  const reading = readResultReading({ run_id: null, writer: "anthropic", model: "m", request, question: null, dropped: [], reason: null });
  assert.equal(reading.request?.kind, "failure");
  assert.equal(questionFrom(reading.request!), null);
  assert.throws(() => readResultReading({ run_id: null, writer: "anthropic", model: "m", request: { ...request, kind: "verdict" }, question: null, dropped: [], reason: null }));
});
