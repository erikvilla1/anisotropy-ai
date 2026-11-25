import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ADHESIVE_FIELDS, answerWords, bondModelWords, bondNeedsWords, bondWords, DAMAGE_FIELDS, EXAMPLE_REPAIR, EXTERNAL_REPAIR, inSentence, kindOf, layupText, LET_GO_IS_NOT_THE_STRENGTH, LIMITS, materialMode, modelWords, needsWords, NOT_THE_STRENGTH, peakPlace, plyBefore,
  REPAIR_MATERIALS, REPAIR_UNIT_LABELS, repairFileName, repairToml, sameRepair, sentence, sliceWords, statedGroups, unitsOf, valueAt, withKind, withLaminateMaterial, withLibraryMaterial,
  withTypedMaterial, withValue, type RepairAnswer, type RepairBond, type RepairSolve,
} from "../lib/repair";

// The repair page's own words and its repair file (ADR-0135). Every number comes from the engine or the solver, in the answers
// scripts/repair-choices.py writes and api/tests/test_repairs_api.py checks; these only read, write and word them.
const read = <T>(name: string): T => JSON.parse(readFileSync(`tests/fixtures/repair/${name}.json`, "utf-8")) as T;
const ANSWER = read<RepairAnswer>("example-answer"), EXTERNAL = read<RepairAnswer>("external-answer");
const SOLVE = read<RepairSolve>("example-solve"), EXTERNAL_SOLVE = read<RepairSolve>("external-solve");
const BOND = read<RepairBond>("example-bond"), EXTERNAL_BOND = read<RepairBond>("external-bond");

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
  assert.equal(words.peel, "Largest peel 4.112 MPa, 62.45 mm from the middle (the adhesive under the cover plies); it reaches the peel strength at 972.6 N/mm.");
  assert.match(sliceWords({ ...SOLVE.report, peel_limit_load: null }).peel, /; not judged: the adhesive states no peel strength\.$/);
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
  // the ply's four fracture energies (ADR-0141), as the file states them
  assert.deepEqual(["fibre break, pulled", "fibre break, pressed", "matrix crack, opened", "matrix crack, slid"].map((name) => rows[`Laminate: Energy of a ${name}`]),
    ["80 N/mm", "80 N/mm", "0.3 N/mm", "0.8 N/mm"]);
  assert.equal(rows["Laminate: Plies, bottom ply first"], "[45/0/−45/90/90/−45/0/45], 8 plies");
  assert.equal(rows["Damage and steps: Step length"], "12.5 mm");
  assert.equal(rows["Damage and steps: Plies in each step"], undefined); // left out of the file, so left out of the report
  assert.equal(rows["Patch: Ply material"], "The laminate's");
  assert.equal(rows["Cover plies: Cover plies"], "[45], 1 ply");
  assert.equal(rows["Adhesive: Shear modulus"], "1000 MPa");
  assert.equal(rows["Adhesive: Peel strength"], "40 MPa");
  assert.equal(rows["Adhesive: Fracture energy, peel"], "0.5 N/mm");
  assert.equal(rows["Adhesive: Fracture energy, shear"], "2 N/mm");
  const without = statedGroups(withValue(withValue(EXAMPLE_REPAIR, "adhesive.peel_energy", undefined), "adhesive.shear_energy", undefined));
  assert.ok(!without.flatMap((g) => g.rows).some(([name]) => /Fracture energy/.test(name))); // left out of the file, so left out of the report
  assert.equal(rows["Panel and load: Load per unit width"], "100 N/mm");
  const onTop = statedGroups(EXTERNAL_REPAIR);
  assert.deepEqual(onTop.map((g) => g.title), ["Repair", "Laminate", "Hole and steps", "Patch", "Adhesive", "Panel and load"]);
  assert.deepEqual(onTop[3].rows, [["Ply material", "The laminate's"], ["Patch plies", "[0/45/−45/0/0/90], 6 plies"], ["Overlap past the hole", "15 mm"], ["Shape", "round"]]);
});

test("two descriptions are the same repair value for value, and the limits are said the same wherever a number is read", () => {
  assert.ok(sameRepair(EXAMPLE_REPAIR, JSON.parse(JSON.stringify(EXAMPLE_REPAIR))));
  assert.ok(!sameRepair(EXAMPLE_REPAIR, withValue(EXAMPLE_REPAIR, "applied.load", 120)));
  assert.ok(!sameRepair(null, EXAMPLE_REPAIR));
  assert.equal(LIMITS.length, 7);
  assert.ok(LIMITS.some((line) => /Plies parting from each other and crushing across the fibres are not followed/.test(line) && /the load it carries in this model is not the repair's strength/.test(line)));
  assert.ok(LIMITS.some((line) => /not where the repair fails/.test(line)));
  assert.ok(LIMITS.some((line) => /the load at which the bond lets go is not the repair's strength/.test(line)));
});

test("the bond followed until it lets go, in the page's words: the load in this model, where it first softens, never a strength (ADR-0140)", () => {
  const words = bondWords(BOND.report);
  assert.equal(words.headline, "The bond lets go at 1,340 N/mm in this model");
  assert.equal(words.short, `It first softens at 184 N/mm. ${LET_GO_IS_NOT_THE_STRENGTH}`);
  assert.equal(words.card, "it first softens at 184 N/mm and lets go at 1,340 N/mm in this model. Not the repair's strength.");
  assert.equal(words.softens, "The bond first softens at 184 N/mm, 37.38 mm from the middle (the adhesive on the ledge of step 2): the shear stress there is 30 MPa, with the bond pressed together by 14.03 MPa.");
  assert.equal(words.letsGo, "In this model the bond lets go at 1,340 N/mm: the load grows no further, and falls as the bond parts. The panel's end has then moved 2.227 mm.");
  assert.equal(words.extent, "At that load 18.65 mm of the bond's 62.1 mm is softening and none has parted.");
  assert.equal(words.after, "The run went on until the load had fallen to 1,153 N/mm; by then 1.589 mm had parted, first 35.25 mm from the middle (the adhesive on the ledge of step 2).");
  assert.equal(words.law, "The bond starts to soften at 30 MPa in shear and 40 MPa in peel, and has parted once 2 N/mm in shear or 0.5 N/mm in peel is spent on it.");
  assert.match(bondModelWords(BOND.report), /^Followed as 3,045 eight-node plane elements held flat, with the bond as 319 pairs of points along its 62\.1 mm, through 46 states of growing damage, in 10 s\. /);
  assert.doesNotMatch(bondModelWords(BOND.report), /anisotropy_fea|solver|moose|calculix/i); // the page names no tool (ADR-0091)
  for (const text of Object.values(words)) assert.doesNotMatch(text.replace(LET_GO_IS_NOT_THE_STRENGTH, ""), /strength of the repair|the repair fails|failure load|margin|passes|carries the load/i);
  // the patch bonded on top: softens first at the patch's edge
  const onTop = bondWords(EXTERNAL_BOND.report);
  assert.equal(onTop.headline, "The bond lets go at 873.2 N/mm in this model");
  assert.match(onTop.softens, /^The bond first softens at 161\.9 N\/mm, 52\.5 mm from the middle \(the adhesive under the patch\): the shear stress there is /);
  // a run that ended before the load fell names no such load
  const held = bondWords({ ...BOND.report, let_go: null, ended: "stalled" });
  assert.equal(held.headline, "No load at which the bond lets go was found");
  assert.equal(held.short, "The path could not be followed further. The largest load reached is 1,340 N/mm.");
  assert.equal(held.extent, "");
  assert.equal(held.card, "no load at which it lets go was found. The path could not be followed further. The largest load reached is 1,340 N/mm.");
  // a run cut short by its time says so, and what makes a model it finishes (ADR-0140 amendment 4)
  assert.equal(bondWords({ ...BOND.report, let_go: null, ended: "time" }).short,
    "The run reached the time it is given before the load fell; a shorter panel, longer steps or fewer plies make a model it finishes. The largest load reached is 1,340 N/mm.");
  // the path's states: the load, the panel's end and the bond past its strength, one of each a state, the last three never falling
  const curve = BOND.report.curve;
  assert.deepEqual([curve.end_movement.length, curve.damaged_length.length, curve.parted_length.length], [curve.load.length, curve.load.length, curve.load.length]);
  assert.ok(curve.damaged_length.every((v, i) => i === 0 || v >= curve.damaged_length[i - 1]));
  assert.equal(BOND.report.let_go!.damaged_length, BOND.report.let_go!.softening_length + BOND.report.let_go!.parted_length);
  // beside the bond's load: a ply of the solved slice that reaches a strength at a lower one, since the run leaves the plies' damage out
  assert.equal(plyBefore(BOND.report, SOLVE.report), "Before that load, in the solved slice, laminate ply 6 (−45°) reaches a strength at 466.1 N/mm: from there the plies' damage, which this run leaves out, would change the answer.");
  assert.equal(plyBefore(BOND.report, null), "");
  assert.equal(plyBefore(BOND.report, { ...SOLVE.report, first_ply: null }), "");
  assert.equal(plyBefore(BOND.report, { ...SOLVE.report, first_ply: { ...SOLVE.report.first_ply!, load: 2000 } }), "");
  assert.equal(plyBefore({ ...BOND.report, let_go: null }, SOLVE.report), "");
  // what following the bond needs is one sentence, and the answer says there is nothing more to state for the examples
  assert.deepEqual([ANSWER.bond_needs, EXTERNAL.bond_needs], [[], []]);
  assert.equal(bondNeedsWords([]), "");
  assert.equal(bondNeedsWords([{ path: "adhesive.peel_energy", words: "the bond's fracture energy in peel" }, { path: "adhesive.shear_energy", words: "the bond's fracture energy in shear" }]),
    "To follow the bond until it lets go, the repair still needs the bond's fracture energy in peel; the bond's fracture energy in shear.");
  // a fracture energy is stated as a force per length, the load's unit in every system
  assert.deepEqual(ADHESIVE_FIELDS.slice(5).map((f) => [f.path, f.unit, f.optional]), [["adhesive.peel_energy", "energy", true], ["adhesive.shear_energy", "energy", true]]);
  for (const system of ["mm-MPa", "SI", "US", "psi"] as const) assert.equal(REPAIR_UNIT_LABELS[system].energy, REPAIR_UNIT_LABELS[system].load);
});
