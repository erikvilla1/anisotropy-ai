import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  answerWords, EXAMPLE_WING, FE_STOPPED, feProgress, feWords, handAndModel, marginText, newSparCaps, newZone, readNumber, readNumbers, ruleTitle, spanWords,
  valueAt, wingFileName, wingToml, withValue, withZones, zonesOf, type WingFeCheck, type WingReport,
} from "../lib/wing";

// The wing page's own words and its wing file (ADR-0118). Every number comes from the engine; these only read, write and word it.
const ANSWER = JSON.parse(readFileSync("tests/fixtures/wing/example-answer.json", "utf-8"));
const CHECK = JSON.parse(readFileSync("tests/fixtures/wing/example-check.json", "utf-8"));
/** The example with spar caps and a cap zone from the root to 40 % (ADR-0125), written by scripts/wing-choices.py like ANSWER. */
const CAPS = JSON.parse(readFileSync("tests/fixtures/wing/caps-answer.json", "utf-8"));
const STACK_RULES = ["ten_percent", "in_a_row", "balance", "symmetry"];

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

test("the example's design rules come with its answer: four per layup, its laminates short of 90° plies, named by their limits (ADR-0123)", () => {
  const report = ANSWER.report as WingReport;
  assert.deepEqual(report.rule_limits, { min_percent: 10, max_in_a_row: 4, drop_ratio: 20, max_dropped: 2 });
  assert.deepEqual(report.rules.map((r) => `${r.part} ${r.rule}`), ["skin", "spar", "rib"].flatMap((part) => STACK_RULES.map((rule) => `${part} ${rule}`)));
  assert.ok(report.rules.every((r) => r.at === null && r.span?.join() === "0,1")); // one stretch each, root to tip
  assert.deepEqual(report.rules.filter((r) => !r.met).map((r) => r.part), ["skin", "spar", "rib"]); // the 10 % rule only
  assert.ok(report.rules.filter((r) => !r.met).every((r) => r.rule === "ten_percent" && r.words.includes("90°")));
  assert.equal(ruleTitle("ten_percent", report.rule_limits), "10 % rule");
  assert.equal(ruleTitle("ten_percent", { min_percent: 12.5 }), "12.5 % rule");
  assert.equal(ruleTitle("in_a_row", report.rule_limits), "Plies of one angle in a row");
  const limits = withValue(withValue(EXAMPLE_WING, "design_rules.min_percent", 15), "design_rules.max_in_a_row", 3);
  assert.match(wingToml(limits), /\[design_rules\]\nmin_percent = 15\nmax_in_a_row = 3\n/);
  assert.equal(valueAt(withValue(limits, "design_rules.min_percent", undefined), "design_rules.max_in_a_row"), 3);
  assert.equal(valueAt(withValue(withValue(limits, "design_rules.min_percent", undefined), "design_rules.max_in_a_row", undefined), "design_rules"), undefined);
});

test("spar caps and zones: the page adds caps from the skin, a zone outboard of the last, and saves the zones inline (ADR-0125)", () => {
  const caps = newSparCaps(EXAMPLE_WING);
  assert.deepEqual(caps, { front_width: 0.045, rear_width: 0.045, half_stack: [0, 0, 45, -45, 0] }); // a tenth of the chord, one more 0° outside
  const capped = { ...EXAMPLE_WING, spar_caps: caps };
  const first = newZone(capped, "spar_caps");
  assert.deepEqual(first, { start: 0, end: 0.4, half_stack: [0, 0, 45, -45, 0] }); // from the root, with the part's own plies
  const zoned = withZones(capped, "spar_caps", [{ ...first, half_stack: [0, 0, 0, 45, -45, 0] }]);
  assert.deepEqual(zoned, CAPS.wing); // what the browser test sends, and the engine's answer to it
  assert.deepEqual(newZone(zoned, "spar_caps"), { start: 0.4, end: 0.8, half_stack: [0, 0, 45, -45, 0] });
  assert.deepEqual(newZone(withZones(zoned, "spar_caps", [{ start: 0.7, end: 0.95, half_stack: [0] }]), "spar_caps").start, 0.9); // room for a stretch
  assert.equal(zonesOf(EXAMPLE_WING, "skin").length, 0);
  assert.equal(valueAt(withZones(zoned, "spar_caps", []), "spar_caps.zones"), undefined); // none left, the key goes
  assert.match(wingToml(zoned), /\n\[spar_caps\]\nfront_width = 0\.045\nrear_width = 0\.045\nhalf_stack = \[0, 0, 45, -45, 0\]\n/);
  assert.match(wingToml(zoned), /\nzones = \[\{ start = 0, end = 0\.4, half_stack = \[0, 0, 0, 45, -45, 0\] \}\]\n/);
  assert.equal(spanWords(0, 1), "root to tip");
  assert.equal(spanWords(0, 0.4), "root to 40 %");
  assert.equal(spanWords(0.4, 1), "40 % to tip");
  assert.equal(spanWords(0.2, 0.4), "20 to 40 %");
  assert.equal(spanWords(0.125, 0.5), "12.5 to 50 %");
});

test("the caps' rules come for each stretch and at each ply drop, every one met but the 10 % rule, with the run-out (ADR-0125)", () => {
  const report = CAPS.report as WingReport;
  const cap = report.rules.filter((r) => r.part === "cap");
  assert.deepEqual(cap.map((r) => `${r.span?.join("-") ?? `at ${r.at}`} ${r.rule}`), [
    ...STACK_RULES.map((rule) => `0-0.4 ${rule}`), ...STACK_RULES.map((rule) => `0.4-1 ${rule}`), "at 0.4 drop_count", "at 0.4 drop_ratio", "at 0.4 drop_cover",
  ]);
  assert.deepEqual(cap.filter((r) => !r.met).map((r) => r.rule), ["ten_percent", "ten_percent"]);
  const ratio = cap.find((r) => r.rule === "drop_ratio");
  assert.equal(ratio?.words, "The plies ending at 40 % of the span need 7.32 mm of run-out at 20 to 1; the thicker side runs 800 mm.");
  assert.equal(ruleTitle("drop_count", report.rule_limits), "Plies ending at one place");
  assert.equal(ruleTitle("drop_ratio", report.rule_limits), "Ply drop ratio");
  assert.equal(ruleTitle("drop_cover", report.rule_limits), "Outside ply over the drop");
  assert.deepEqual(report.design.stretches.map((s) => [s.start, s.end]), [[0, 0.8], [0.8, 2]]); // in metres, the change at 40 % of 2 m
  assert.ok(report.design.stretches[0].bending_stiffness > report.design.stretches[1].bending_stiffness);
  assert.ok(report.design.mass_caps > 0);
  assert.deepEqual(CAPS.views.changes, [0.8]);
  assert.deepEqual(CAPS.views.caps.map((c: { name: string }) => c.name), ["upper front spar cap", "lower front spar cap", "upper rear spar cap", "lower rear spar cap"]);
});

test("the finite element check is worded from its report: both lowest margins, where the model's is, and its root (ADR-0119)", () => {
  const at = (look: Partial<WingFeCheck>): WingFeCheck => ({ job_id: "j", state: "running", wing: "w", started_at: "", finished_at: null, stage: null,
    stages_done: [], stages: ["build", "solve", "modes"], message: null, run_id: null, report: null, ...look });
  assert.equal(feProgress(at({ state: "queued" })), "Waiting to start…");
  assert.equal(feProgress(at({ stage: null })), "Starting…");
  assert.equal(feProgress(at({ stage: "build" })), "Building the model (1 of 3)…");
  assert.equal(feProgress(at({ stage: "modes" })), "Vibration modes and flutter (3 of 3)…");
  assert.equal(feProgress(at({ state: "done", report: CHECK })), "Checked in 28 s.");
  assert.equal(feProgress(at({ state: "refused", message: "The wing has ribs but no rib layup" })), "The wing has ribs but no rib layup");
  assert.equal(feProgress(at({ state: "stopped" })), FE_STOPPED);
  const words = feWords(CHECK);
  assert.equal(words.headline, "Lowest margin +0.146 by the finite element model, +0.154 by the hand calculation.");
  assert.equal(words.where, "The model's: skin strength, upper skin, 0.0611 m from the root, 0.139 m from the leading edge, 0° ply, longitudinal compression, "
    + "case 6 (Positive high angle of attack). Both are read from 0.046 m out, one web height from the root.");
  assert.match(words.root, /At the root itself the model's lowest is −0\.142 \(skin strength, lower skin, case 7\)\.$/);
  assert.equal(handAndModel({ hand: 0.15379, fe: null }, marginText), "+0.154\u00a0· –");
});
