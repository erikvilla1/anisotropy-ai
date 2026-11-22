import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  answerWords, DAMAGE_FIELDS, EXAMPLE_REPAIR, EXTERNAL_REPAIR, inSentence, kindOf, layupText, LIMITS, materialMode, modelWords, needsWords, NOT_THE_STRENGTH, peakPlace,
  REPAIR_MATERIALS, repairFileName, repairToml, sameRepair, sentence, sliceWords, statedGroups, unitsOf, valueAt, withKind, withLaminateMaterial, withLibraryMaterial,
  withTypedMaterial, withValue, type RepairAnswer, type RepairSolve,
} from "../lib/repair";

// The repair page's own words and its repair file (ADR-0135). Every number comes from the engine or the solver, in the answers
// scripts/repair-choices.py writes and api/tests/test_repairs_api.py checks; these only read, write and word them.
const read = <T>(name: string): T => JSON.parse(readFileSync(`tests/fixtures/repair/${name}.json`, "utf-8")) as T;
const ANSWER = read<RepairAnswer>("example-answer"), EXTERNAL = read<RepairAnswer>("external-answer");
const SOLVE = read<RepairSolve>("example-solve"), EXTERNAL_SOLVE = read<RepairSolve>("external-solve");

test("each example saves as the repair file the engine reads back as the example (api/tests/test_repairs_api.py reads the same files)", () => {
  assert.equal(repairToml(EXAMPLE_REPAIR), readFileSync("tests/fixtures/repair/example-saved.toml", "utf-8"));
  assert.equal(repairToml(EXTERNAL_REPAIR), readFileSync("tests/fixtures/repair/external-saved.toml", "utf-8"));
  assert.equal(repairFileName(EXAMPLE_REPAIR), "example-stepped-patch-repair.toml");
  assert.equal(repairFileName({}, "step"), "repair.step");
  assert.deepEqual(ANSWER.repair, EXAMPLE_REPAIR); // the engine's answer is to the description the page holds
  assert.deepEqual(EXTERNAL.repair, EXTERNAL_REPAIR);
});

test("the two kinds: a description says which it is, and changing kind keeps what both share and takes the rest from the other's example", () => {
  assert.equal(kindOf(EXAMPLE_REPAIR), "flush");
  assert.equal(kindOf(EXTERNAL_REPAIR), "external");
  assert.equal(unitsOf(EXAMPLE_REPAIR), "mm-MPa");
  const onTop = withKind(EXAMPLE_REPAIR, "external");
  assert.equal(kindOf(onTop), "external");
  assert.equal(valueAt(onTop, "cover.layup"), undefined); // a patch on top has no cover plies
  assert.deepEqual(valueAt(onTop, "parent.layup"), valueAt(EXAMPLE_REPAIR, "parent.layup"));
  assert.equal(valueAt(onTop, "adhesive.thickness"), valueAt(EXAMPLE_REPAIR, "adhesive.thickness"));
  assert.equal((valueAt(onTop, "patch.layup") as number[]).length, 4); // one ply for each of the example's four steps: nothing the steps do not hold
  assert.equal(valueAt(onTop, "patch.overlap"), 12.5);
  assert.deepEqual(Object.keys(onTop).slice(0, 4), ["title", "source", "units", "kind"]); // the kind before the tables, as the engine's example
  const back = withKind(EXTERNAL_REPAIR, "flush");
  assert.equal(kindOf(back), "flush");
  assert.equal(back.patch, undefined); // a flush patch repeats the plies removed unless it says otherwise
  assert.equal(withKind(EXAMPLE_REPAIR, "flush"), EXAMPLE_REPAIR); // the same kind changes nothing
  assert.deepEqual(DAMAGE_FIELDS.flush.map((f) => f.path), DAMAGE_FIELDS.external.map((f) => f.path));
});

test("a ply material is the library's, typed in full, or the laminate's own; changing how it is named guesses no constant", () => {
  assert.equal(materialMode(EXAMPLE_REPAIR, "parent"), "library");
  assert.equal(materialMode(EXAMPLE_REPAIR, "patch"), "laminate");
  assert.equal(materialMode(EXTERNAL_REPAIR, "patch"), "laminate"); // its patch states plies and an overlap, no material
  const typed = withTypedMaterial(EXAMPLE_REPAIR, "parent");
  assert.equal(materialMode(typed, "parent"), "typed");
  assert.equal(valueAt(typed, "parent.library"), undefined);
  assert.equal(valueAt(typed, "parent.E1"), undefined); // waits to be typed: the engine names what is missing
  assert.deepEqual(valueAt(typed, "parent.layup"), valueAt(EXAMPLE_REPAIR, "parent.layup"));
  const library = withLibraryMaterial(withValue(typed, "parent.E1", 150000), "parent", REPAIR_MATERIALS[0].id);
  assert.equal(valueAt(library, "parent.library"), REPAIR_MATERIALS[0].id);
  assert.equal(valueAt(library, "parent.E1"), undefined);
  const patched = withLibraryMaterial(EXTERNAL_REPAIR, "patch", REPAIR_MATERIALS[0].id);
  assert.equal(materialMode(patched, "patch"), "library");
  assert.deepEqual(withLaminateMaterial(patched), EXTERNAL_REPAIR);
  assert.ok(REPAIR_MATERIALS.some((m) => m.id === "im7-8552" && m.strengths));
});

test("the hand calculation's answer in the page's short form: the largest shear under the stated load and the adhesive's limit, never a strength", () => {
  const words = answerWords(ANSWER.report);
  assert.equal(words.headline, "Largest bondline shear 12.58 MPa under 100 N/mm");
  assert.equal(words.detail, `By hand, at the inner end of the ledge of step 1. The adhesive reaches its elastic limit in shear at 238.5 N/mm. ${NOT_THE_STRENGTH}`);
  assert.deepEqual(words.facts, ["4 plies cut in 4 steps, 125 mm across", "laminate 1.463 mm thick"]);
  assert.equal(peakPlace(ANSWER.report), "at the inner end of the ledge of step 1");
  const onTop = answerWords(EXTERNAL.report);
  assert.equal(onTop.headline, "Largest bondline shear 21.09 MPa under 100 N/mm");
  assert.match(onTop.detail, /^By hand, at the inner end of the whole patch\. The adhesive reaches its elastic limit in shear at 142\.2 N\/mm\./);
  assert.deepEqual(onTop.facts, ["6-ply round patch on top, 105 mm across", "laminate 1.463 mm thick"]);
  for (const text of [words.headline, words.detail, onTop.headline, onTop.detail]) assert.doesNotMatch(text.replace(NOT_THE_STRENGTH, ""), /strength of the repair|fails at|failure load|margin|passes/i);
  // with no load the repair is described and drawn, and the page says what is missing
  const { answer: _answer, load: _load, ...lap } = ANSWER.report.lap;
  const described = answerWords({ ...ANSWER.report, lap });
  assert.equal(described.headline, "No load stated yet");
  assert.match(described.detail, /State a load per unit width/);
  // an adhesive that states no shear strength gets no limit load
  const { elastic_limit_load: _limit, ...noLimit } = ANSWER.report.lap.answer!;
  assert.match(answerWords({ ...ANSWER.report, lap: { ...ANSWER.report.lap, answer: noLimit } }).detail, /states no shear strength, so no elastic limit load is given\.$/);
});

test("the engine's names read inside a sentence, and a headline closes as one", () => {
  assert.equal(inSentence("Ledge of step 2"), "the ledge of step 2");
  assert.equal(inSentence("The whole patch"), "the whole patch");
  assert.equal(inSentence("Laminate ply 6 (-45°)"), "laminate ply 6 (−45°)");
  assert.equal(layupText([45, 0, -45, 90]), "[45/0/−45/90]");
  assert.equal(sentence("Under 100 N/mm: largest bondline shear 11.5 MPa"), "Under 100 N/mm: largest bondline shear 11.5 MPa.");
  assert.equal(sentence("Done. "), "Done.");
});

test("what a solve of the slice still needs is one sentence, and nothing when it can be solved", () => {
  assert.equal(needsWords(ANSWER.needs), "");
  assert.equal(needsWords([{ path: "adhesive.poisson", words: "the adhesive's Poisson's ratio" }, { path: "applied.load", words: "a load per unit width that is not zero" }]),
    "The solve of the slice still needs the adhesive's Poisson's ratio; a load per unit width that is not zero.");
});

test("the solved slice beside the hand calculation: the two peaks, the limit loads and what comes first, the limit never called a strength", () => {
  const words = sliceWords(SOLVE.report);
  assert.equal(words.shear, "Largest shear 11.5 MPa, 37.29 mm from the middle (the adhesive on the ledge of step 2); by hand 12.58 MPa.");
  assert.match(words.peel, /^Largest peel 4\.112 MPa, 62\.45 mm from the middle \(the adhesive under the cover plies\); not judged: the adhesive states no peel strength\.$/);
  assert.equal(words.limit, `The adhesive reaches its elastic limit in shear at 260.8 N/mm; by hand 238.5 N/mm. ${NOT_THE_STRENGTH}`);
  assert.match(words.ply, /^First ply by maximum stress: laminate ply 6 \(−45°\), transverse tension, at 466\.1 N\/mm, 37\.46 mm from the middle\.$/);
  assert.equal(words.first, "First, the adhesive reaches its elastic limit in shear, at 260.8 N/mm.");
  assert.match(modelWords(SOLVE.report), /^Solved as 6,344 eight-node plane elements held flat, 38,838 equations, elements [\d.]+ to [\d.]+ mm long, in 3 s\. /);
  assert.doesNotMatch(modelWords(SOLVE.report), /calculix/i); // the page names no tool (ADR-0091)
  const onTop = sliceWords(EXTERNAL_SOLVE.report);
  assert.match(onTop.shear, /^Largest shear 13\.38 MPa, .*; by hand 21\.09 MPa\.$/);
  assert.match(onTop.limit, /at 224\.2 N\/mm; by hand 142\.2 N\/mm\. Not the repair's strength/);
  // the headline the solver tool writes is the same answer
  assert.match(SOLVE.headline, /largest bondline shear 11\.5 MPa \(hand calculation 12\.58\), largest peel 4\.112 MPa/);
});

test("the report lists what the description states, grouped as the page's steps, and only what it states", () => {
  const groups = statedGroups(EXAMPLE_REPAIR);
  assert.deepEqual(groups.map((g) => g.title), ["Repair", "Laminate", "Damage and steps", "Patch", "Cover plies", "Adhesive", "Panel and load"]);
  const rows = Object.fromEntries(groups.flatMap((g) => g.rows.map(([name, value]) => [`${g.title}: ${name}`, value])));
  assert.equal(rows["Repair: Kind"], "Flush, in a stepped cut");
  assert.equal(rows["Laminate: Ply material"], "IM7 / 8552");
  assert.equal(rows["Laminate: ν23"], "0.45");
  assert.equal(rows["Laminate: Plies, bottom ply first"], "[45/0/−45/90/90/−45/0/45], 8 plies");
  assert.equal(rows["Damage and steps: Step length"], "12.5 mm");
  assert.equal(rows["Damage and steps: Plies in each step"], undefined); // left out of the file, so left out of the report
  assert.equal(rows["Patch: Ply material"], "The laminate's");
  assert.equal(rows["Cover plies: Cover plies"], "[45], 1 ply");
  assert.equal(rows["Adhesive: Shear modulus"], "1000 MPa");
  assert.equal(rows["Adhesive: Peel strength"], undefined);
  assert.equal(rows["Panel and load: Load per unit width"], "100 N/mm");
  const onTop = statedGroups(EXTERNAL_REPAIR);
  assert.deepEqual(onTop.map((g) => g.title), ["Repair", "Laminate", "Hole and steps", "Patch", "Adhesive", "Panel and load"]);
  assert.deepEqual(onTop[3].rows, [["Ply material", "The laminate's"], ["Patch plies", "[0/45/−45/0/0/90], 6 plies"], ["Overlap past the hole", "15 mm"], ["Shape", "round"]]);
});

test("two descriptions are the same repair value for value, and the limits are said the same wherever a number is read", () => {
  assert.ok(sameRepair(EXAMPLE_REPAIR, JSON.parse(JSON.stringify(EXAMPLE_REPAIR))));
  assert.ok(!sameRepair(EXAMPLE_REPAIR, withValue(EXAMPLE_REPAIR, "applied.load", 120)));
  assert.ok(!sameRepair(null, EXAMPLE_REPAIR));
  assert.equal(LIMITS.length, 5);
  assert.ok(LIMITS.some((line) => /not where the repair fails/.test(line)));
});
