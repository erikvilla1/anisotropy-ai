import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { changeLine, lowestOf, previewRows, previewWarnings, readWingAsk, wingAnswer, type PlyChange, type WingChangePreview } from "../lib/wing-chat";
import type { WingReport } from "../lib/wing";

// The wing's chat (ADR-0128): what the page reads in a message by its own patterns, and how it answers from the engine's report. The reports
// and the preview are the engine's own, written by scripts/wing-choices.py and checked against the API by api/tests/test_wings_api.py.
const EXAMPLE: WingReport = JSON.parse(readFileSync("tests/fixtures/wing/example-answer.json", "utf8")).report;
const CAPS: WingReport = JSON.parse(readFileSync("tests/fixtures/wing/caps-answer.json", "utf8")).report;
const PREVIEW: WingChangePreview = JSON.parse(readFileSync("tests/fixtures/wing/caps-preview.json", "utf8"));
const FOUNDERS: PlyChange = { action: "add_plies", part: "spar_caps", angle: 0, count: 2, start: 0, end: 0.4, placement: "beside" };

const changeOf = (message: string) => {
  const ask = readWingAsk(message);
  assert.equal(ask.route, "wing-change", `“${message}” is read as a change`);
  return ask as Extract<ReturnType<typeof readWingAsk>, { route: "wing-change" }>;
};

test("the founder's ask is read into the engine's change, every number from the words", () => {
  for (const message of ["Add 2 0 plies to the spar caps from the root to 40% span", "Add 2 0° plies to the spar caps from the root to 40% span",
    "add two 0 degree plies to the caps, root to 40 %", "please add 2 plies at 0° to the spar caps up to 40% of the span", "add 2x 0-degree plies to the spar caps from 0% to 40%"]) {
    const ask = changeOf(message);
    assert.deepEqual(ask.change, FOUNDERS, message);
    assert.equal(ask.whole, false);
  }
  assert.equal(changeLine(FOUNDERS, false), "Two 0° plies added to the spar caps from the root to 40 % of the half span.");
});

test("a change reads its part, its angle, its stretch and where the plies go, and a removal takes its verb", () => {
  assert.deepEqual(changeOf("remove 2 45 plies from the webs").change, { action: "remove_plies", part: "spar", angle: 45, count: 2, start: 0, end: 1, placement: "beside" });
  assert.equal(changeOf("remove 2 45 plies from the webs").whole, true, "no stretch named: the whole span, said so on the card");
  assert.deepEqual(changeOf("take out two -45 plies from the skin outboard of 60%").change,
    { action: "remove_plies", part: "skin", angle: -45, count: 2, start: 0.6, end: 1, placement: "beside" });
  assert.deepEqual(changeOf("add 4 plies at 0 deg to the spar caps between 10% and 50%").change, { ...FOUNDERS, count: 4, start: 0.1, end: 0.5 });
  assert.deepEqual(changeOf("add 2 90 plies to the skin in the middle").change, { action: "add_plies", part: "skin", angle: 90, count: 2, start: 0, end: 1, placement: "middle" });
  assert.equal(changeOf("what if I add 2 0 plies to the skin from 40% to the tip").change?.start, 0.4, "a question of what if is previewed too");
  assert.equal(changeOf("add 2 −45° plies to the spar web").change?.angle, -45);
});

test("a change it cannot read whole asks once, with an example; one it does not make says where it is made", () => {
  const asks = (message: string, words: string) => {
    const ask = changeOf(message);
    assert.equal(ask.change, null, message);
    assert.ok(ask.problem?.includes(words), `“${message}”: ${ask.problem}`);
    return ask;
  };
  assert.equal(asks("make the spar caps thicker near the root", "How many plies, and at what angle?").asks, true);
  asks("add one 0 ply to the caps", "cannot keep the laminate symmetric");
  asks("add 2 0 plies near the root of the caps", "as a percentage");
  asks("add 2 ±45 plies to the web", "One angle at a time");
  asks("add 2 0 plies to the skin and the caps", "One part at a time");
  asks("add 2 0 plies from the root to 40%", "Which part");
  assert.equal(asks("add a rib at 60% span", "Geometry step").asks, false);
});

test("a question is never a change: rules, strengths, tests and results go to their own answers", () => {
  const routes: [string, string][] = [
    ["what allowables are you using for the spar caps?", "wing-strengths"], ["which ASTM test gives the compression allowable?", "wing-reference"],
    ["what ply drop ratio should I use?", "wing-rules"], ["how many 0° plies can I stack together?", "wing-rules"], ["does my skin meet the 10% rule?", "wing-rules"],
    ["is the spar cap laminate balanced and symmetric?", "wing-rules"], ["which part fails first", "wing-result"], ["what is the margin of safety of the web?", "wing-result"],
    ["why does the web buckle first?", "wing-reference"], ["what is the tip deflection", "wing-result"], ["whats the weight of the wing box", "wing-result"],
    ["export the STEP", "wing-command"], ["what is a B-basis value?", "wing-reference"], ["hello", "wing-unread"], ["does it pass?", "wing-result"],
  ];
  for (const [message, route] of routes) assert.equal(readWingAsk(message).route, route, message);
});

test("a question of the results is answered from the engine's report, the number as the page prints it, its basis in one line", () => {
  const which = wingAnswer(readWingAsk("which part fails first"), EXAMPLE);
  assert.equal(which.heading, "Upper skin first: +0.059");
  assert.match(which.lines[0], /^Lowest margin \+0\.059 on B-basis strengths: skin strength, upper skin, at the root, 0° ply/);
  assert.equal(which.lines[1], "At ultimate load, on B-basis strengths, by the hand calculation of the 34 cases run.");
  assert.equal(wingAnswer(readWingAsk("does it pass?"), EXAMPLE).heading, "Yes: passes the 34 cases run");
  const web = wingAnswer(readWingAsk("what is the margin of safety of the web?"), EXAMPLE);
  assert.equal(web.heading, `Web: lowest margin +${lowestOf(EXAMPLE, "spar plies")!.margin.toFixed(3)}`);
  assert.ok(web.lines.some((l) => l.startsWith("Web buckling +")) && web.lines.some((l) => l.startsWith("Spar web strength +")), "both checks of the web");
  const mass = wingAnswer(readWingAsk("whats the weight of the wing box"), EXAMPLE);
  assert.equal(mass.heading, "2.225 kg, one side of the wing");
  assert.match(mass.lines[0], /Ribs, fittings and the parts ahead of and behind the box are not counted/);
  const tip = wingAnswer(readWingAsk("what is the tip deflection"), EXAMPLE);
  const largest = EXAMPLE.cases.reduce((a, b) => (Math.abs(b.tip_deflection) > Math.abs(a.tip_deflection) ? b : a));
  assert.equal(tip.heading, `Tip deflection ${Number(largest.tip_deflection.toPrecision(4))} mm, case ${largest.number}`);
  assert.equal(wingAnswer(readWingAsk("first bending frequency?"), EXAMPLE).heading, "First bending frequency 19.63 Hz");
});

test("a question of a rule answers yes or no from the wing's own rules, or gives the wing's limit and where it is set", () => {
  const ten = wingAnswer(readWingAsk("does my skin meet the 10% rule?"), EXAMPLE);
  assert.equal(ten.heading, "No: the skin misses the 10 % rule");
  assert.deepEqual(ten.lines[0], "Skin: No plies at 90°: each of 0°, +45°, −45° and 90° should have at least 10 %.");
  const caps = wingAnswer(readWingAsk("is the spar cap laminate balanced and symmetric?"), CAPS);
  assert.equal(caps.heading, "Yes: the spar caps meet balance and symmetry");
  assert.ok(caps.lines.some((l) => l.startsWith("Spar caps, from the root to 40 %: ")), "each stretch of the caps");
  assert.equal(wingAnswer(readWingAsk("is the spar cap laminate balanced and symmetric?"), EXAMPLE).heading, "No spar caps on this wing yet");
  const drop = wingAnswer(readWingAsk("what ply drop ratio should I use?"), CAPS);
  assert.equal(drop.heading, "A run-out 20 times the thickness dropped");
  assert.match(drop.lines[0], /Design rules box of the Layup step and checked at every change of layup along the span/);
  assert.equal(drop.lines[1], "Every layup of this wing meets it.");
  assert.equal(wingAnswer(readWingAsk("what ply drop ratio should I use?"), EXAMPLE).lines[1], "No ply drop on this wing yet: its layups do not change along the span.");
  assert.equal(wingAnswer(readWingAsk("how many 0° plies can I stack together?"), EXAMPLE).heading, "At most 4 plies of one angle in a row");
});

test("the strengths are named with their basis, page and report, and the estimates say why", () => {
  const said = wingAnswer(readWingAsk("what allowables are you using for the spar caps?"), EXAMPLE);
  assert.equal(said.heading, "B-basis strengths of IM7 / 8552");
  assert.equal(said.lines[0], "Every part uses the same ply material, so the spar caps use these.");
  assert.ok(said.lines.includes("Compression along the fibres 1,504 MPa, B-estimate, p. 46"));
  assert.ok(said.lines.some((l) => l.startsWith("Compression along the fibres and in-plane shear: B-estimates")));
  assert.ok(said.lines.some((l) => l.startsWith("From: Hexcel 8552 IM7")));
});

test("a question of why names the wing's own facts on what it asks, and says when another check governs", () => {
  const said = wingAnswer(readWingAsk("why does the web buckle first?"), EXAMPLE);
  assert.equal(said.kind, "reference");
  assert.match(said.lines[0], /^Web buckling \+\d\.\d{3}: front spar/);
  assert.match(said.lines[1], /^Skin strength governs this wing, not web buckling: \+0\.059\.$/);
});

test("every heading is short, and none names a tool or a file", () => {
  for (const message of ["which part fails first", "does it pass?", "what is the margin of safety of the web?", "whats the weight of the wing box",
    "does the wing meet the design rules?", "is the spar cap laminate balanced and symmetric?", "what allowables are you using?", "export the STEP", "hello",
    "make the spar caps thicker near the root", "divergence speed", "does the spar web meet the 10% rule"]) {
    for (const report of [EXAMPLE, CAPS]) {
      const said = wingAnswer(readWingAsk(message), report);
      assert.ok(said.heading.length <= 60, `“${message}”: ${said.heading}`);
      assert.doesNotMatch([said.heading, ...said.lines].join("\n"), /calculix|abaqus|claude|\.toml|\.py\b/i);
    }
  }
});

test("the preview's table and warnings are the engine's numbers, which way each moved, and the changed part's unmet rules", () => {
  const rows = previewRows(PREVIEW);
  assert.equal(rows[0].label, "Lowest margin");
  assert.equal(rows[0].better, true, "two 0° plies in the caps raise the lowest margin");
  const mass = rows.find((r) => r.label.startsWith("Mass"))!;
  assert.equal(mass.better, false, "and add mass");
  assert.equal(mass.before, String(Number(PREVIEW.before.mass.toPrecision(4))));
  const unmet = PREVIEW.rules.filter((r) => !r.met);
  assert.equal(previewWarnings(PREVIEW).length, unmet.length);
  previewWarnings(PREVIEW).forEach((w, i) => assert.ok(w.startsWith("Spar caps") && w.endsWith(unmet[i].words), w));
  assert.equal(PREVIEW.words, "Two 0° plies added to the spar caps from the root to 40 % of the half span, beside the 0° plies: [0/0/0/45/-45/0]s there.");
});
