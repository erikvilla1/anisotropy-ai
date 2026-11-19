import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { answerWords, EXAMPLE_WING, marginText, readNumber, readNumbers, valueAt, wingFileName, wingToml, withValue, type WingReport } from "../lib/wing";

// The wing page's own words and its wing file (ADR-0118). Every number comes from the engine; these only read, write and word it.
const ANSWER = JSON.parse(readFileSync("tests/fixtures/wing/example-answer.json", "utf-8"));

test("the example saves as the wing file the engine reads back as the example (api/tests/test_wings_api.py reads the same file)", () => {
  assert.equal(wingToml(EXAMPLE_WING), readFileSync("tests/fixtures/wing/example-saved.toml", "utf-8"));
  assert.equal(wingFileName(EXAMPLE_WING), "example-straight-wing.toml");
  assert.equal(wingFileName({ geometry: { half_span: 2 } }), "wing.toml");
  assert.equal(wingToml({ "two words": "a \"quoted\" title" }), '"two words" = "a \\"quoted\\" title"\n');
  assert.throws(() => wingToml({ geometry: { chord: Number.NaN } }), /finite/);
});

test("a value is set along its path, the tables made on the way, and an emptied optional table leaves the file", () => {
  const changed = withValue(EXAMPLE_WING, "geometry.half_span", 2.5);
  assert.equal(valueAt(changed, "geometry.half_span"), 2.5);
  assert.equal(valueAt(EXAMPLE_WING, "geometry.half_span"), 2); // the description is never changed in place
  const made = withValue({}, "envelope.gust.wing_area", 1.8);
  assert.deepEqual(made, { envelope: { gust: { wing_area: 1.8 } } });
  assert.deepEqual(withValue(made, "envelope.gust.wing_area", undefined), {});
  assert.equal(valueAt(EXAMPLE_WING, "geometry.half_span.more"), undefined);
});

test("typed numbers: a comma for the decimal point, the minus sign, lists in either notation, and nothing guessed", () => {
  assert.equal(readNumber(" 2,5 "), 2.5);
  assert.equal(readNumber("−1.52"), -1.52);
  assert.equal(readNumber("two"), null);
  assert.equal(readNumber(""), null);
  assert.deepEqual(readNumbers("[0/45/-45/0]"), [0, 45, -45, 0]);
  assert.deepEqual(readNumbers("0, 45, −45"), [0, 45, -45]);
  assert.equal(readNumbers("0, x"), null);
  assert.equal(readNumbers(" "), null);
});

test("the answer is worded from the engine's report: passes or how many fail, the lowest margin and where", () => {
  const report = ANSWER.report as WingReport;
  const words = answerWords(report);
  assert.equal(words.verdict, "Passes the 34 cases run");
  assert.equal(words.detail, "Lowest margin +0.097: skin strength, upper skin, at the root, 0° ply, longitudinal compression, 0.152 m from the leading edge, case 6 (Positive high angle of attack).");
  const first = report.cases[0];
  const failing: WingReport = { ...report, passes: false, cases: [{ ...first, checks: { ...first.checks, "web buckling": { ...first.checks["web buckling"], margin_ultimate: -0.25 } } }, ...report.cases.slice(1)] };
  assert.equal(answerWords(failing).verdict, "Fails 1 of the 34 cases run");
  assert.equal(answerWords({ ...report, cases: [], governing: null }).verdict, "No case could run yet");
  assert.equal(marginText(-0.25), "−0.250");
  assert.equal(marginText(null), "–");
});
