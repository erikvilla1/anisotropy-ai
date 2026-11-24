import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  changeLine, previewPlace, previewRows, readRepairAsk, repairAnswer, REPAIR_EXAMPLES, REPAIR_ROUTES, sweepHeading, sweepLine, sweepTable,
  type RepairAsk, type RepairChangePreview, type RepairHeld, type RepairSweepAnswer,
} from "../lib/repair-chat";
import { EXAMPLE_REPAIR, EXTERNAL_REPAIR, LET_GO_IS_NOT_THE_STRENGTH, NOT_THE_STRENGTH, withValue, type RepairAnswer, type RepairBond, type RepairSolve } from "../lib/repair";
import { bannedIn } from "../lib/studio-copy";

// The repair's chat (ADR-0136): what the page reads in a message by its own patterns, and how it answers from the engine's report and
// the solved slice. The answers, the previews, the sweep and its check are the engine's and the solver's own, written by
// scripts/repair-choices.py and checked against the API by api/tests/test_repairs_api.py.
const read = <T>(name: string): T => JSON.parse(readFileSync(`tests/fixtures/repair/${name}.json`, "utf8")) as T;
const ANSWER = read<RepairAnswer>("example-answer"), EXTERNAL = read<RepairAnswer>("external-answer"), SOLVE = read<RepairSolve>("example-solve");
const PREVIEW = read<RepairChangePreview>("example-change"), STEP = read<RepairChangePreview>("example-step-change");
const SWEEP: RepairSweepAnswer = { ...read<RepairSweepAnswer>("example-sweep"), check: read<RepairSweepAnswer["check"]>("example-sweep-check") };

const HAND: RepairHeld = { repair: EXAMPLE_REPAIR, report: ANSWER.report, slice: null, sliceStale: false, needs: [] };
const SOLVED: RepairHeld = { ...HAND, slice: SOLVE.report };
// the bond followed until it lets go (ADR-0137): the page that can follow it, and the page that has
const BOND = read<RepairBond>("example-bond");
const CAN_FOLLOW: RepairHeld = { ...HAND, bondNeeds: [] };
const FOLLOWED: RepairHeld = { ...SOLVED, bond: BOND.report, bondNeeds: [] };
const ON_TOP: RepairHeld = { repair: EXTERNAL_REPAIR, report: EXTERNAL.report, slice: null, sliceStale: false, needs: [] };
const say = (message: string, held: RepairHeld = HAND) => repairAnswer(readRepairAsk(message, held.report?.kind ?? "flush"), held);

const changeOf = (message: string, kind: "flush" | "external" = "flush") => {
  const ask = readRepairAsk(message, kind);
  assert.equal(ask.route, "repair-change", `“${message}” is read as a change`);
  return ask as Extract<RepairAsk, { route: "repair-change" }>;
};
const sweepOf = (message: string, kind: "flush" | "external" = "flush") => {
  const ask = readRepairAsk(message, kind);
  assert.equal(ask.route, "repair-sweep", `“${message}” is read as a sweep`);
  return ask as Extract<RepairAsk, { route: "repair-sweep" }>;
};

test("the plan's two changes are read into the engine's form, every number and its unit from the words", () => {
  for (const message of ["Add a step", "add a step", "add one step", "one more step", "add another step please", "Can you add another step?", "what if I add a step?", "ad a step"]) {
    assert.deepEqual(changeOf(message).change, { action: "add_steps", count: 1 }, message);
  }
  for (const message of ["make each step 0.5 in", "Make each step 0.5 in.", "set the step length to 0.5 in", "make the steps 1/2 in", 'make each step 0.5"', "0.5 in steps", "0.5 inch step length"]) {
    assert.deepEqual(changeOf(message).change, { action: "set", quantity: "step_length", value: 0.5, unit: "in" }, message);
  }
  assert.equal(changeLine({ action: "set", quantity: "step_length", value: 0.5, unit: "in" }), "The step length set to 0.5 in.");
  assert.equal(changeLine({ action: "add_steps", count: 1 }), "1 step added.");
});

test("a change of the steps reads its count, its new plies' angles and whether the same plies are regrouped", () => {
  assert.deepEqual(changeOf("add 2 steps").change, { action: "add_steps", count: 2 });
  assert.deepEqual(changeOf("add a step of 45/-45", "external").change, { action: "add_steps", count: 1, angles: [45, -45] });
  assert.deepEqual(changeOf("add a step with a 0° ply").change, { action: "add_steps", count: 1, angles: [0] });
  assert.deepEqual(changeOf("remove a step").change, { action: "remove_steps", count: 1 });
  assert.deepEqual(changeOf("take off 2 steps").change, { action: "remove_steps", count: 2 });
  for (const message of ["make it 5 steps", "use 5 steps", "set the number of steps to 5", "steps: 5", "5 steps", "how about 5 steps", "I want 5 steps", "go back to 5 steps"]) {
    assert.deepEqual(changeOf(message).change, { action: "set_steps", count: 5 }, message);
  }
  assert.deepEqual(changeOf("2 plies per step").change, { action: "regroup", count: 2 });
  assert.deepEqual(changeOf("use two plies a step").change, { action: "regroup", count: 2 });
  assert.deepEqual(changeOf("cut the same plies in 2 steps").change, { action: "regroup_steps", count: 2 });
  assert.equal(changeLine({ action: "regroup_steps", count: 2 }), "The same plies cut in 2 steps.");
  assert.equal(changeLine({ action: "add_steps", count: 1, angles: [45, -45] }), "1 step added, of plies at 45°, −45°.");
});

test("a value is set by its quantity, with the unit as written or the repair's own", () => {
  const set = (message: string, kind: "flush" | "external" = "flush") => changeOf(message, kind).change;
  assert.deepEqual(set("set the step length to 10 mm"), { action: "set", quantity: "step_length", value: 10, unit: "mm" });
  assert.deepEqual(set("step length 10"), { action: "set", quantity: "step_length", value: 10 });
  assert.deepEqual(set("what if the step length were 6 mm?"), { action: "set", quantity: "step_length", value: 6, unit: "mm" });
  assert.deepEqual(set("change the bondline to 0.15 mm"), { action: "set", quantity: "bondline", value: 0.15, unit: "mm" });
  assert.deepEqual(set("make the adhesive thickness 0.006 in"), { action: "set", quantity: "bondline", value: 0.006, unit: "in" });
  assert.deepEqual(set("increase the load to 150 N/mm"), { action: "set", quantity: "load", value: 150, unit: "N/mm" });
  assert.deepEqual(set("set the load to 800 lb/in"), { action: "set", quantity: "load", value: 800, unit: "lb/in" });
  assert.deepEqual(set("load = 150"), { action: "set", quantity: "load", value: 150 });
  assert.deepEqual(set("make the hole 1 in"), { action: "set", quantity: "damage", value: 1, unit: "in" });
  assert.deepEqual(set("set the overlap to 15 mm"), { action: "set", quantity: "cover_overlap", value: 15, unit: "mm" });
  assert.deepEqual(set("set the overlap to 15 mm", "external"), { action: "set", quantity: "patch_overlap", value: 15, unit: "mm" });
  // a unit the engine has no name for, or of the wrong kind, goes to it as written: the engine refuses it in words (ADR-0002)
  assert.deepEqual(set("set the step length to 5 psi"), { action: "set", quantity: "step_length", value: 5, unit: "psi" });
  assert.deepEqual(set("set the step length to 1 ft"), { action: "set", quantity: "step_length", value: 1, unit: "ft" });
});

test("a change with no value is asked for one, and what the chat does not change is said", () => {
  for (const message of ["make the steps longer", "double the step length", "increase the bondline by 0.05 mm", "thicker bondline", "raise the load 10%"]) {
    const ask = changeOf(message);
    assert.equal(ask.change, null, message);
    assert.ok(ask.asks && ask.problem?.startsWith("To what value?"), message);
  }
  assert.equal(say("double the step length").kind, "ask");
  assert.match(say("double the step length").lines[0], /does not work one out: for example “set the step length to 10 mm”/);
  for (const message of ["remove the cover plies", "change the patch layup to 0/90", "use a different material", "swap the adhesive", "replace the patch plies", "switch the laminate", "add a ply"]) {
    const ask = changeOf(message);
    assert.ok(ask.change === null && !ask.asks && ask.problem?.includes("model tree on the left"), message);
    assert.equal(say(message).heading, "Not a change the chat makes");
  }
});

test("a fragment takes its question, its sweep or its change from the message before it, with the new value", () => {
  const elastic = readRepairAsk("is the adhesive still elastic at 200 N/mm");
  assert.equal(elastic.route, "repair-result");
  for (const message of ["and at 250?", "now 250", "what about 250", "at 250 N/mm"]) {
    const next = readRepairAsk(message, "flush", elastic) as Extract<RepairAsk, { route: "repair-result" }>;
    assert.equal(next.route, "repair-result", message);
    assert.equal(next.topic, (elastic as typeof next).topic, message);
    assert.equal(next.load?.value, 250, message);
  }
  assert.equal(repairAnswer(readRepairAsk("and at 250?", "flush", elastic), HAND).heading, "No, by hand: past its elastic limit at 250 N/mm");
  assert.equal(repairAnswer(elastic, HAND).heading, "Yes, by hand: still elastic at 200 N/mm");
  const swept = sweepOf("sweep step length 3 to 25 mm at 230 N/mm");
  assert.deepEqual((readRepairAsk("and at 200?", "flush", swept) as typeof swept).sweep, { quantity: "step_length", start: 3, end: 25, unit: "mm", load: 200 });
  assert.deepEqual((readRepairAsk("now 1.3 kN/mm", "flush", swept) as typeof swept).sweep, { quantity: "step_length", start: 3, end: 25, unit: "mm", load: 1.3, load_unit: "kN/mm" });
  const set = changeOf("set the bondline to 0.15 mm");
  assert.deepEqual((readRepairAsk("now 0.2 mm", "flush", set) as typeof set).change, { action: "set", quantity: "bondline", value: 0.2, unit: "mm" });
  assert.deepEqual((readRepairAsk("try 0.1", "flush", set) as typeof set).change, { action: "set", quantity: "bondline", value: 0.1 });
  // A value of another kind, a message that says more than a value, or no message before, is read on its own.
  assert.deepEqual(changeOf("200 N/mm").change, (readRepairAsk("200 N/mm", "flush", set) as typeof set).change);
  assert.deepEqual(readRepairAsk("and at 10 mm?", "flush", elastic), readRepairAsk("and at 10 mm?"));
  assert.deepEqual(changeOf("add a step", "flush").change, (readRepairAsk("add a step", "flush", elastic) as typeof set).change);
  assert.deepEqual(readRepairAsk("and at 250?"), readRepairAsk("and at 250?", "flush", undefined));
});

test("a sweep reads its quantity, its range and the load, each with its unit", () => {
  assert.deepEqual(sweepOf("sweep the step length").sweep, { quantity: "step_length" });
  assert.deepEqual(sweepOf("sweep the step length from 3 to 25 mm").sweep, { quantity: "step_length", start: 3, end: 25, unit: "mm" });
  assert.deepEqual(sweepOf("vary the bondline between 0.05 and 0.15 mm").sweep, { quantity: "bondline", start: 0.05, end: 0.15, unit: "mm" });
  assert.deepEqual(sweepOf("sweep step length 3 to 25 mm at 230 N/mm").sweep, { quantity: "step_length", start: 3, end: 25, unit: "mm", load: 230, load_unit: "N/mm" });
  assert.deepEqual(sweepOf("what is the smallest step length that keeps the adhesive elastic at 230 N/mm?").sweep, { quantity: "step_length", load: 230, load_unit: "N/mm" });
  assert.deepEqual(sweepOf("how many steps do I need for 200 N/mm").sweep, { quantity: "steps", load: 200, load_unit: "N/mm" });
  assert.deepEqual(sweepOf("compare 1, 2 and 4 steps").sweep, { quantity: "steps" });
  assert.deepEqual(sweepOf("what bondline keeps it elastic at 260").sweep, { quantity: "bondline", load: 260 });
  assert.deepEqual(sweepOf("sweep the overlap from 5 to 20 mm").sweep, { quantity: "cover_overlap", start: 5, end: 20, unit: "mm" });
  assert.deepEqual(sweepOf("sweep the overlap from 5 to 20 mm", "external").sweep, { quantity: "patch_overlap", start: 5, end: 20, unit: "mm" });
  assert.deepEqual(sweepOf("smallest repair that stays elastic at 3000 lb/in").sweep, { quantity: "step_length", load: 3000, load_unit: "lb/in" });
});

test("the plan's sweep is run as the smallest repair whose adhesive stays elastic, never as a strength", () => {
  // "the smallest repair that brings back a strength you name": with a load, the step length is swept and the reading says so
  for (const message of ["smallest repair that stays elastic at 230 N/mm", "the smallest repair that restores a strength of 230 N/mm", "bring back 230 N/mm with the smallest repair",
    "what is the smallest repair that carries 230 N/mm"]) {
    const ask = sweepOf(message);
    assert.deepEqual(ask.sweep, { quantity: "step_length", load: 230, load_unit: "N/mm" }, message);
    assert.equal(ask.assumed, true);
    const said = say(message);
    assert.equal(said.kind, "sweep");
    assert.match(said.lines[0], /^The step length, from a fifth of its value to twice it, for the smallest repair whose adhesive is still elastic at 230 N\/mm\. No quantity was named/);
    assert.doesNotMatch(said.lines.join(" "), /strength|carr/);
  }
  assert.equal(sweepLine({ quantity: "steps", load: 200, load_unit: "N/mm" }), "The same plies in every number of steps that divides them, for the smallest repair whose adhesive is still elastic at 200 N/mm.");
  // with no load, or a strength as a share, it asks once what load, in words that give an example
  assert.match(sweepOf("smallest repair").problem ?? "", /^Smallest for what load\? Name the load per unit width/);
  assert.match(sweepOf("the smallest repair that brings back 90% of the strength").problem ?? "", /^The page has no strength to bring back\. Name a load per unit width/);
  assert.match(sweepOf("smallest repair that takes 300 MPa").problem ?? "", /not a stress/);
  assert.equal(say("smallest repair").kind, "ask");
  // a sweep that would show nothing is declined with the reason
  const load = sweepOf("sweep the load");
  assert.ok(load.sweep === null && !load.asks && load.problem?.includes("every stress grows in step with the load"));
  assert.match(sweepOf("sweep the step length from 25 to 3 mm").problem ?? "", /from its smaller value up to its larger/);
});

test("a question of the result is answered from the report, the answer as the heading and every number the engine's", () => {
  const shear = say("what is the largest shear?");
  assert.equal(shear.heading, "12.58 MPa by hand, at the inner end of the ledge of step 1");
  assert.deepEqual(shear.lines, ["The largest shear stress in the adhesive under 100 N/mm.", "The solved slice gives it too, with the peel stress."]);
  for (const message of ["where is the shear highest", "peak shear stress", "whta is the peak sheer", "what's the max shear stres", "stress in the adhesive"]) assert.equal(say(message).heading, shear.heading, message);
  const limit = say("at what load does the adhesive yield");
  assert.equal(limit.heading, "238.5 N/mm by hand");
  assert.deepEqual(limit.lines, ["The load at which the adhesive reaches its elastic limit in shear, at the inner end of the ledge of step 1.", NOT_THE_STRENGTH]);
  assert.equal(say("what is the elastic limit load").heading, limit.heading);
  assert.equal(say("how wide is the repair").heading, "125 mm across");
  assert.deepEqual(say("how deep is the cut").lines, ["4 plies cut 0.7315 mm deep; 4 plies are left under the patch.", "The laminate is 1.463 mm thick."]);
  assert.equal(say("how many steps are there").heading, "4 steps of 1 ply each");
  assert.equal(say("what is the patch layup").heading, "Patch [90/−45/0/45], deepest ply first");
  assert.equal(say("what is the patch layup", ON_TOP).heading, "Patch [0/45/−45/0/0/90], from the laminate upward");
  const forces = say("how much load does the patch carry");
  assert.equal(forces.heading, "The patch carries 53.03 of the 100 N/mm at the middle");
  assert.equal(forces.lines[0], "At the repair's middle the plies left under the patch carry the rest.");
  assert.equal(forces.lines[1], "By hand, at the inner end of each step: cover overlap 8.608, ledge of step 1 24.66, ledge of step 2 47.58, ledge of step 3 52.24, floor 53.03 N/mm.");
  assert.equal(say("how much load does the patch carry", ON_TOP).heading, "The patch carries 100 of the 100 N/mm at the hole");
  assert.equal(say("how much load does the patch carry", ON_TOP).lines[0], "At the edge of the hole the laminate ends, so the patch carries all of it.");
});

test("a value the repair states is read back as stated, with its unit and its step", () => {
  assert.deepEqual([say("what is the bondline thickness").heading, say("what is the bondline thickness").panel], ["Bondline thickness: 0.1 mm", "repair-adhesive"]);
  assert.equal(say("what is the step length").heading, "Step length: 12.5 mm");
  assert.equal(say("what is the adhesive's shear strength").heading, "Shear strength: 30 MPa");
  assert.equal(say("what is the load").heading, "Load per unit width: 100 N/mm");
  assert.equal(say("what is the peel strength").heading, "Peel strength: 40 MPa");
  assert.equal(say("what is the peel strength", { ...HAND, repair: withValue(EXAMPLE_REPAIR, "adhesive.peel_strength", undefined) }).heading, "Peel strength: not stated");
  // the bond's two fracture energies (ADR-0137), by the names an engineer gives them
  assert.deepEqual([say("what is the fracture energy in peel").heading, say("what is the fracture energy in peel").panel], ["Fracture energy, peel: 0.5 N/mm", "repair-adhesive"]);
  assert.equal(say("what is the shear fracture energy").heading, "Fracture energy, shear: 2 N/mm");
  assert.equal(say("what is the mode II toughness").heading, "Fracture energy, shear: 2 N/mm");
  assert.equal(say("what GIc does it use").heading, "Fracture energy, peel: 0.5 N/mm");
});

test("what only the solved slice holds is answered from it, and asked for when it is not solved", () => {
  const none = say("what is the peel stress");
  assert.deepEqual([none.kind, none.heading, none.lines[0], none.offer], ["none", "The hand calculation has no peel stress", "Solve the slice to get it: a few seconds.", "solve"]);
  assert.equal(say("what is the peel stress", { ...HAND, sliceStale: true }).lines[0], "The slice was solved for the repair as it was: solve it again for the repair as it stands.");
  const needs = say("what is the peel stress", { ...HAND, needs: [{ path: "adhesive.poisson", words: "the adhesive's Poisson's ratio" }] });
  assert.deepEqual([needs.lines[0], needs.offer], ["The solve of the slice still needs the adhesive's Poisson's ratio.", undefined]);
  const peel = say("what is the peel stress", SOLVED);
  assert.equal(peel.heading, "4.112 MPa in the solved slice");
  assert.deepEqual(peel.lines, ["The largest peel stress, 62.45 mm from the middle (the adhesive under the cover plies).", "It reaches the peel strength at 972.6 N/mm.", "The hand calculation has no peel stress."]);
  assert.equal(say("where is the peel stress highest", SOLVED).heading, peel.heading);
  assert.equal(say("which ply fails first", SOLVED).heading, "Laminate ply 6 (−45°) at 466.1 N/mm");
  const first = say("what fails first", SOLVED);
  assert.equal(first.heading, "The adhesive's elastic limit in shear, at 260.8 N/mm");
  assert.deepEqual(first.lines, ["In the solved slice, as the load grows, the adhesive reaches its elastic limit in shear first.", NOT_THE_STRENGTH]);
  assert.equal(say("what fails first").heading, "By hand, only the adhesive's shear is worked");
  assert.equal(say("what is the largest shear?", SOLVED).lines[1], "Solved as a slice: 11.5 MPa, 37.29 mm from the middle (the adhesive on the ledge of step 2).");
  assert.equal(say("what is the elastic limit load", SOLVED).lines[1], "Solved as a slice: 260.8 N/mm.");
});

test("when the bond lets go is answered from the bond followed, never as a strength, and offered or asked for when it is not followed (ADR-0137)", () => {
  for (const message of ["when does the bond let go?", "at what load does the patch come off", "when does the adhesive fail", "what is the debond load", "bond failure load",
    "progressive failure load?", "whne does the patch debond", "does the bond break", "what is the bond's strength"]) {
    const ask = readRepairAsk(message);
    assert.deepEqual([ask.route, ask.route === "repair-result" ? ask.topic : null], ["repair-result", "bond"], message);
  }
  const fell = say("when does the bond let go?", FOLLOWED);
  assert.deepEqual([fell.kind, fell.heading, fell.panel], ["result", "The bond lets go at 1,340 N/mm in this model", "repair-solve"]);
  assert.deepEqual(fell.lines, [
    "The bond first softens at 184 N/mm, 37.38 mm from the middle (the adhesive on the ledge of step 2): the shear stress there is 30 MPa, with the bond pressed together by 14.03 MPa.",
    "At that load 18.65 mm of the bond's 62.1 mm is softening and none has parted.",
    "Before that load, in the solved slice, laminate ply 6 (−45°) reaches a strength at 466.1 N/mm: from there the plies' damage, which this run leaves out, would change the answer.",
    LET_GO_IS_NOT_THE_STRENGTH,
  ]);
  assert.equal(say("when does the bond let go?", { ...FOLLOWED, slice: null }).lines.length, 3); // no solved slice, so nothing is said of the plies
  assert.doesNotMatch([fell.heading, ...fell.lines].join(" ").replace(LET_GO_IS_NOT_THE_STRENGTH, ""), /strength of the repair|fails at|failure load|margin|passes|carries/i);
  // where or when it starts leads with the start
  const starts = say("where does the bond soften first", FOLLOWED);
  assert.equal(starts.heading, "The bond first softens at 184 N/mm, 37.38 mm from the middle");
  assert.deepEqual(starts.lines, ["In the adhesive on the ledge of step 2: the shear stress there is 30 MPa, with the bond pressed together by 14.03 MPa.",
    `The bond lets go at 1,340 N/mm in this model. ${LET_GO_IS_NOT_THE_STRENGTH}`]);
  assert.equal(say("when does damage start in the adhesive", FOLLOWED).heading, starts.heading);
  // not followed yet: offered where it can be, what it needs where it cannot, and nothing offered where the service follows no bonds
  const offer = say("when does the bond let go?", CAN_FOLLOW);
  assert.deepEqual([offer.kind, offer.heading, offer.lines[0], offer.offer], ["none", "The bond is not followed yet", "Follow the bond to get it: about ten seconds.", "bond"]);
  assert.equal(say("when does the bond let go?", { ...CAN_FOLLOW, bondStale: true }).lines[0], "The bond was followed for the repair as it was: follow it again for the repair as it stands.");
  const needs = say("when does the bond let go?", { ...HAND, bondNeeds: [{ path: "adhesive.peel_energy", words: "the bond's fracture energy in peel" }] });
  assert.deepEqual([needs.lines[0], needs.offer, needs.panel], ["To follow it until it lets go, the repair still needs the bond's fracture energy in peel.", undefined, "repair-adhesive"]);
  assert.deepEqual([say("when does the bond let go?").offer, say("when does the bond let go?").kind], [undefined, "none"]);
  // a run that ended before the load fell names no load at which the bond lets go
  const held = say("when does the bond let go?", { ...FOLLOWED, bond: { ...BOND.report, let_go: null, ended: "steps" } });
  assert.equal(held.heading, "No load at which the bond lets go was found");
  assert.match(held.lines.join(" "), /The run reached its limit of steps before the load fell\. The largest load reached is 1,340 N\/mm\./);
  // the stresses of the slice keep their own answers
  assert.equal(say("what is the peel stress", FOLLOWED).heading, "4.112 MPa in the solved slice");
  assert.equal(say("which ply fails first", FOLLOWED).heading, "Laminate ply 6 (−45°) at 466.1 N/mm");
  // why it lets go is the pages', with the repair's own loads beside them
  const why = readRepairAsk("why does the bond let go before it has all parted?");
  assert.deepEqual([why.route, why.route === "repair-reference" ? why.topic : null], ["repair-reference", "bond"]);
  assert.deepEqual(repairAnswer(why, FOLLOWED).lines, ["Here: the bond first softens at 184 N/mm and lets go at 1,340 N/mm in this model."]);
});

test("the bond is followed on a command, when the repair states what that needs (ADR-0137)", () => {
  for (const message of ["follow the bond", "follow the bond until it lets go", "run the bond to failure", "run a progressive failure analysis", "progressive failure", "take the bond to failure"]) {
    assert.deepEqual(readRepairAsk(message), { route: "repair-command", command: "bond" }, message);
  }
  const started = say("follow the bond", CAN_FOLLOW);
  assert.deepEqual([started.kind, started.heading, started.panel], ["bond", "Following the bond until it lets go", "repair-solve"]);
  const needs = say("follow the bond", { ...HAND, bondNeeds: [{ path: "parent.nu23", words: "the laminate ply's constants through the thickness" }] });
  assert.deepEqual([needs.kind, needs.heading, needs.panel], ["none", "The bond cannot be followed yet", "repair-solve"]);
  assert.equal(say("follow the bond").heading, "The bond cannot be followed here");
  // the slice is still solved by its own command, and a change of the bondline is still a change
  assert.deepEqual(readRepairAsk("solve the slice"), { route: "repair-command", command: "solve" });
  assert.equal(readRepairAsk("make the bondline 0.2 mm").route, "repair-change");
});

test("the bond is set against the plies with the earlier named first, a fragment asks where, and a fracture energy is never read as the load (ADR-0137)", () => {
  // "does the bond fail before the plies?" opens with No where a ply of the solved slice comes first (criterion 1)
  assert.deepEqual(readRepairAsk("does the bond fail before the plies?"), { route: "repair-result", topic: "bond", plies: "yes-no" });
  assert.deepEqual(readRepairAsk("which fails first, the bond or the plies"), { route: "repair-result", topic: "bond", plies: "which" });
  const no = say("does the bond fail before the plies?", FOLLOWED);
  assert.equal(no.heading, "No: a ply reaches a strength first, at 466.1 N/mm");
  assert.match(no.lines[0], /^Laminate ply 6 \(−45°\), in the solved slice\. The bond lets go later in this model, at 1,340 N\/mm, with every ply kept elastic\.$/);
  assert.equal(no.lines[1], "The bond first softens at 184 N/mm and goes on carrying load while it softens.");
  assert.equal(say("which fails first, the bond or the plies", FOLLOWED).heading, "A ply reaches a strength first, at 466.1 N/mm");
  // a bond that lets go below the first ply's load says Yes, and still not as a strength
  const weak = { ...BOND.report, let_go: { ...BOND.report.let_go!, load: 400 } };
  const yes = say("does the bond fail before the plies?", { ...FOLLOWED, bond: weak });
  assert.equal(yes.heading, "Yes: the bond lets go first in this model, at 400 N/mm");
  assert.match(yes.lines.join(" "), /reaches a strength at 466\.1 N\/mm.*Not the repair's strength/);
  // without the slice there is nothing to set it against, and the solve is offered
  const alone = say("does the bond fail before the plies?", { ...FOLLOWED, slice: null });
  assert.deepEqual([alone.kind, alone.offer], ["none", "solve"]);
  assert.match(alone.heading, /^The bond lets go at 1,340 N\/mm in this model; the plies' loads are not worked here$/);
  // "and where?" after a question of the bond is where it first softens
  const asked = readRepairAsk("when does the bond let go?");
  assert.deepEqual(readRepairAsk("and where?", "flush", asked), { route: "repair-result", topic: "bond", onset: true });
  assert.equal(readRepairAsk("and where?", "flush").route, "repair-reference");
  // more of the words a user has for it
  for (const message of ["how much of the bond has failed", "has the adhesive failed", "will the adhesive fail"]) assert.equal((readRepairAsk(message) as { topic?: string }).topic, "bond", message);
  assert.deepEqual(readRepairAsk("what is the damage initiation load"), { route: "repair-result", topic: "bond", onset: true });
  // a fracture energy is written in the load's unit: the chat changes neither energy and never reads one as the load
  for (const message of ["set the peel fracture energy to 0.3 N/mm", "make GIIc 3", "change the shear toughness to 2.5 N/mm"]) {
    const read = readRepairAsk(message);
    assert.equal(read.route, "repair-change", message);
    const refused = repairAnswer(read, HAND);
    assert.deepEqual([refused.kind, refused.heading, refused.panel], ["refused", "Not a change the chat makes", "repair-adhesive"], message);
  }
  assert.deepEqual((readRepairAsk("set the load to 0.3 N/mm") as { change: unknown }).change, { action: "set", quantity: "load", value: 0.3, unit: "N/mm" });
});

test("a question that asks for a verdict is told the page gives none, with what it does give", () => {
  for (const message of ["is it strong enough?", "what is the strength of the repair", "does it pass", "will it hold", "what is the margin", "is the repair safe", "what is the failure load", "does it restore the strength?"]) {
    const said = say(message, SOLVED);
    assert.equal(said.kind, "verdict", message);
    assert.equal(said.heading, "This page gives no strength or verdict", message);
    assert.equal(said.lines[0], "By hand, the adhesive reaches its elastic limit in shear at 238.5 N/mm; the load stated is 100 N/mm.");
    assert.equal(said.lines[1], "In the solved slice, the adhesive reaches its elastic limit in shear first, at 260.8 N/mm.");
    assert.match(said.lines[2], /^Neither is a failure load/);
  }
  // with the bond followed, the load at which it lets go is given too, and still no verdict (ADR-0137)
  const followed = say("is it strong enough?", FOLLOWED);
  assert.deepEqual([followed.kind, followed.heading], ["verdict", "This page gives no strength or verdict"]);
  assert.deepEqual(followed.lines.slice(2), ["With the bond followed, it lets go at 1,340 N/mm in this model.",
    "None of these is the repair's strength: the plies are not checked for damage, and what the analysis leaves out is listed under the results."]);
  // with a load named in the repair's unit, the page compares it with the engine's limit load: still not a verdict
  assert.equal(say("can it carry 200 N/mm?").lines[0], "By hand, the adhesive is still elastic at 200 N/mm: it reaches that limit at 238.5 N/mm.");
  assert.equal(say("will it fail at 300 N/mm").lines[0], "By hand, the adhesive is past its elastic limit at 300 N/mm: it reaches that limit at 238.5 N/mm.");
  assert.equal(say("can it carry 1500 lb/in?").lines[0], "By hand, the adhesive reaches its elastic limit in shear at 238.5 N/mm; the load stated is 100 N/mm.", "another unit is not converted on the page");
  assert.equal(say("is it strong enough?").offer, "solve");
  // a yes or no about the elastic limit opens with it
  assert.equal(say("is the adhesive still elastic at 200 N/mm?").heading, "Yes, by hand: still elastic at 200 N/mm");
  assert.equal(say("is the adhesive still elastic at 200 N/mm?").lines[0], "The adhesive reaches its elastic limit in shear at 238.5 N/mm, at the inner end of the ledge of step 1.");
  assert.equal(say("does it stay elastic at 250").heading, "No, by hand: past its elastic limit at 250 N/mm");
  assert.equal(say("is the adhesive still elastic?").heading, "Yes, by hand: still elastic at 100 N/mm");
  assert.equal(say("is the adhesive still elastic at 1500 lb/in").heading, "The adhesive reaches its elastic limit at 238.5 N/mm by hand");
});

test("a question of why, how or what a thing is goes to the reference pages, beside the repair's own number", () => {
  const why = say("why does the shear peak at the ends of a step?");
  assert.deepEqual([why.kind, why.lines], ["reference", ["Here: 12.58 MPa by hand, at the inner end of the ledge of step 1."]]);
  assert.deepEqual(say("why is it not the strength").lines, ["Here: the adhesive reaches its elastic limit at 238.5 N/mm by hand."]);
  assert.deepEqual(say("what is peel stress?", SOLVED).lines, ["Here: 4.112 MPa in the solved slice (the adhesive under the cover plies)."]);
  for (const message of ["what is peel stress?", "what are cover plies for", "what does the pick mean", "explain shear lag", "should I add a step?", "does a longer step help?",
    "how does the bondline thickness change the shear", "what is the difference between a flush and an external patch", "is there a rule for step length?"]) {
    assert.equal(readRepairAsk(message).route, "repair-reference", message);
  }
  assert.equal(readRepairAsk("what is the peel stress").route, "repair-result", "with its article it asks for this repair's value");
});

test("a command is started or pointed to, and what cannot be read is said with examples", () => {
  for (const message of ["solve the slice", "solve it", "Solve", "run the finite element check", "please solve the slice"]) assert.deepEqual(readRepairAsk(message), { route: "repair-command", command: "solve" }, message);
  assert.equal(say("solve the slice").kind, "solve");
  assert.deepEqual([say("solve the slice", { ...HAND, needs: [{ path: "adhesive.poisson", words: "the adhesive's Poisson's ratio" }] }).kind], ["none"]);
  assert.deepEqual([say("open the report").offer, say("open the report").panel], ["report", "repair-report"]);
  assert.equal(say("download the step file").heading, "The STEP file is built in Report and shape");
  for (const message of ["undo", "undo that", "revert", "go back"]) assert.deepEqual(readRepairAsk(message), { route: "repair-command", command: "undo" }, message);
  for (const message of ["hello", "thanks", "asdf"]) {
    assert.equal(readRepairAsk(message).route, "repair-unread", message);
    assert.deepEqual(say(message).lines, [REPAIR_EXAMPLES]);
  }
  assert.equal(say("what is the largest shear?", { ...HAND, report: null }).heading, "The repair is being worked");
  const unloaded = { ...ANSWER.report, lap: { ...ANSWER.report.lap, load: undefined, answer: undefined } };
  assert.deepEqual([say("what is the largest shear?", { ...HAND, report: unloaded }).heading, say("is it strong enough", { ...HAND, report: unloaded }).panel], ["No load stated yet", "repair-loads"]);
});

test("every route is reached, and no answer names a tool or calls a number a strength", () => {
  const messages: Record<(typeof REPAIR_ROUTES)[number], string> = {
    "repair-change": "add a step", "repair-sweep": "sweep the step length", "repair-result": "what is the largest shear?", "repair-reference": "why does the shear peak?",
    "repair-command": "solve the slice", "repair-unread": "hello",
  };
  for (const route of REPAIR_ROUTES) assert.equal(readRepairAsk(messages[route]).route, route);
  const asked = ["what is the largest shear?", "what is the elastic limit load", "what is the peel stress", "what fails first", "which ply fails first", "how wide is the repair",
    "how much load does the patch carry", "is it strong enough?", "can it carry 200 N/mm?", "is the adhesive still elastic at 200 N/mm?", "add a step", "double the step length",
    "smallest repair", "sweep the load", "solve the slice", "open the report", "hello", "why is it not the strength"];
  for (const held of [HAND, SOLVED, ON_TOP]) {
    for (const message of asked) {
      const said = say(message, held);
      const text = [said.heading, ...said.lines].join("\n");
      assert.deepEqual(bannedIn(text), [], `${message}: ${text}`);
      assert.doesNotMatch(text.replace(NOT_THE_STRENGTH, "").replace(/no strength|gives no strength or verdict|Not judged|peel strength|shear strength|no strength to bring back/g, ""),
        /\bthe repair's strength\b|\bstrength of the repair\b|\bmargin\b|\bwill (?:fail|hold)\b|\bis safe\b|\bpasses\b/, `${message}: ${text}`);
    }
  }
});

test("a preview's table sets the repair as it is beside the repair as changed, in the engine's numbers", () => {
  assert.equal(PREVIEW.words, "The step length goes from 12.5 mm to 12.7 mm (0.5 in as written).");
  assert.deepEqual(previewRows(PREVIEW), [
    { label: "Steps", before: "4 of 1 ply", after: "4 of 1 ply", better: null },
    { label: "Repair width (mm)", before: "125", after: "126.2", better: null },
    { label: "Load (N/mm)", before: "100", after: "100", better: null },
    { label: "Largest shear (MPa)", before: "12.58", after: "12.58", better: null },
    { label: "Elastic limit load (N/mm)", before: "238.5", after: "238.5", better: null },
  ]);
  // where the largest shear is stands under the table in a sentence: stays, or moves from one place to another
  assert.equal(previewPlace(PREVIEW), "The largest shear stays at the inner end of the ledge of step 1.");
  assert.equal(previewPlace({ ...PREVIEW, after: { ...PREVIEW.after, peak_shear: { ...PREVIEW.after.peak_shear!, name: "Ledge of step 2", end: "start" } } }),
    "The largest shear moves from the inner end of the ledge of step 1 to the outer end of the ledge of step 2.");
  assert.equal(previewPlace({ ...PREVIEW, after: { ...PREVIEW.after, peak_shear: null } }), null);
  // a change that moves a number is marked the better or the worse way: a thicker bondline lowers the shear
  assert.deepEqual(previewRows({ ...PREVIEW, after: { ...PREVIEW.after, peak_shear: { ...PREVIEW.after.peak_shear!, value: 10.27 }, elastic_limit_load: 292.1 } }).filter((r) => r.better !== null)
    .map((r) => [r.after, r.better]), [["10.27", true], ["292.1", true]]);
  assert.equal(STEP.words, "Five steps in place of four: the cut goes five plies deep, and three plies of the laminate's eight are left under the patch; the patch takes the angles of the plies removed.");
  const rows = previewRows(STEP);
  assert.deepEqual(rows.slice(0, 2), [{ label: "Steps", before: "4 of 1 ply", after: "5 of 1 ply", better: null }, { label: "Repair width (mm)", before: "125", after: "150", better: null }]);
  assert.deepEqual(bannedIn([PREVIEW.words, STEP.words, ...rows.flatMap((r) => [r.label, r.before, r.after])].join("\n")), []);
});

test("a sweep's heading is its pick, its table marks the pick and the repair as it stands, and its words are the engine's", () => {
  assert.equal(sweepHeading(SWEEP), "Step length 4 mm: still elastic at 230 N/mm");
  const table = sweepTable(SWEEP);
  assert.deepEqual(table.head, ["Step length (mm)", "Width (mm)", "Largest shear (MPa)", "Elastic limit load (N/mm)", "Elastic at 230 N/mm"]);
  assert.equal(table.rows.length, 24);
  assert.deepEqual(table.rows[0], { cells: ["3", "68", "13.15", "228.1", "No"], refused: null, pick: false, current: false, elastic: false });
  assert.deepEqual(table.rows[1], { cells: ["4", "74", "12.85", "233.5", "Yes"], refused: null, pick: true, current: false, elastic: true });
  assert.deepEqual(table.rows.filter((row) => row.current).map((row) => row.cells[0]), ["12.5"]);
  const last = table.rows[table.rows.length - 1];
  assert.ok(last.cells.length === 1 && last.cells[0] === "25" && last.refused?.startsWith("The repair is"));
  assert.equal(SWEEP.words[2], "The smallest of these whose adhesive is still elastic at 230 N/mm: a step length of 4 mm, the repair 74 mm across. Its adhesive reaches its elastic limit at 233.5 N/mm.");
  assert.deepEqual(SWEEP.cautions, ["Not the repair's strength: the adhesive yields before it fails, and the hand calculation has no peel stress.",
    "A short step that keeps the adhesive elastic in this model is not a rule for choosing a step length."]);
  assert.ok(SWEEP.check?.holds === true && SWEEP.check.words[2] === "That is at or above the 230 N/mm named: the slice holds the pick.");
  assert.deepEqual(bannedIn([...SWEEP.words, ...SWEEP.cautions, ...(SWEEP.check?.words ?? []), sweepHeading(SWEEP), ...table.head].join("\n")), []);
  // the pick is the hand calculation's: where its solved slice does not hold it, or is too close to say, the heading says so
  assert.equal(sweepHeading({ ...SWEEP, check: { state: "solved", holds: false, close: false, words: [] } }), "Step length 4 mm by hand; the slice says no");
  assert.equal(sweepHeading({ ...SWEEP, check: { state: "solved", holds: null, close: true, words: [] } }), "Step length 4 mm by hand; too close in the slice");
  assert.equal(sweepHeading({ ...SWEEP, check: { state: "failed", holds: null, words: [] } }), "Step length 4 mm: still elastic at 230 N/mm");
  assert.equal(sweepHeading({ ...SWEEP, pick: null, picked: null, target: 300 }), "None of these stays elastic at 300 N/mm");
  assert.equal(sweepHeading({ ...SWEEP, pick: null, picked: null, target: null }), "23 values of the step length worked by hand");
  const steps = { ...SWEEP, quantity: { name: "steps" as const, words: "the number of steps", unit: "" }, pick: 0, rows: [{ ...SWEEP.rows[1], value: 2, steps: 2, plies_per_step: 2 }] };
  assert.equal(sweepHeading(steps), "2 steps of 2 plies: still elastic at 230 N/mm");
  assert.deepEqual([sweepTable(steps).head[0], sweepTable(steps).rows[0].cells[0]], ["Steps", "2 of 2 plies"]);
});
