import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { approveRepairPlan, askRepairPlan, readPlanApproval, readPlanOutput, readRepairPlan, readRepairPlanApproval, reportRepairPlanStep, StudioError,
  type ReferenceSection } from "../lib/studio-api";
import { kindReports, kindViews, newKindFlow, readyToAnswer, refusalLines, repairPlanAnswer, repairRuns, waitingWords, wingPlanAnswer, wingRuns, withSection,
  type KindProgress } from "../lib/plan-kinds";
import { planCount } from "../lib/plan-steps";
import { asksWingPlan, routeWingAsk } from "../lib/wing-chat";
import { asksRepairPlan, routeRepairAsk, type RepairHeld } from "../lib/repair-chat";
import { isQuestion } from "../lib/chat-route";
import { bannedIn } from "../lib/studio-copy";
import { feWords, type WingFeCheck } from "../lib/wing";
import type { RepairDescription } from "../lib/repair";

// A wing's and a repair's plan on the page (ADR-0144, step 5): which sentences go to the planner, the contract's answers as the page reads
// them (tests/fixtures/planner/, written by api/tests/test_planner_kinds.py), and the steps as they tick off.
const planner = (name: string) => JSON.parse(readFileSync(`tests/fixtures/planner/${name}.json`, "utf8"));
const wingProposed = readPlanOutput(planner("wing-plan-answered"));
const wingApproval = readPlanApproval(planner("wing-approve-answered"));
const repairProposed = readPlanOutput(planner("repair-plan-answered"));
const repairApproval = readRepairPlanApproval(planner("repair-approve-answered"));
const CHECK_REPORT = JSON.parse(readFileSync("tests/fixtures/wing/plan-check.json", "utf8"));
const states = (views: { tool: string; state: string }[]) => views.map((v) => `${v.tool} ${v.state}`);
const checkAt = (state: WingFeCheck["state"], more: Partial<WingFeCheck> = {}): WingFeCheck => ({ ...wingRuns(wingApproval.runs).check!, state, ...more });
const wingAt = (p: Partial<KindProgress>): KindProgress => ({ approved: true, check: checkAt("queued"), analyze: wingRuns(wingApproval.runs).analyze?.report ?? null,
  answers: {}, ...p });

test("a sentence of a change of plies with a run, a check or an answer goes to the planner where a model reads; one change alone does not", () => {
  for (const sentence of ["add 2 0-degree plies to the spar caps and run the check", "add 2 0° plies to the spar caps, work it by hand and tell me the lowest margin",
    "remove 2 45 plies from the skin then run the fea", "can you add 2 0 plies to the spar caps and run the check?"]) {
    assert.ok(asksWingPlan(sentence), sentence);
    assert.deepEqual(routeWingAsk(sentence, true), { route: "wing-plan" }, sentence);
    assert.notEqual(routeWingAsk(sentence, false).route, "wing-plan", sentence); // no model: the patterns, as before
  }
  for (const sentence of ["add 2 0° plies to the spar caps from the root to 40% span", "run the finite element check", "which part fails first?",
    "does the wing pass if I add 2 0 plies to the caps and run the check?", "make the wing pass, whatever it takes"]) {
    assert.ok(!asksWingPlan(sentence), sentence);
  }
});

test("a repair's sentence of a change or a sweep with a solve, the bond or an answer goes to the planner; a change or a sweep alone does not", () => {
  for (const sentence of ["find the smallest repair that stays elastic at 300 N/mm, then solve it", "find the shortest step length that stays elastic at 300 N/mm and solve it",
    "add a step and solve the slice", "set the load to 300 N/mm and follow the bond", "sweep the step length for 250 N/mm, use the pick and tell me what fails first"]) {
    assert.ok(asksRepairPlan(sentence), sentence);
    assert.deepEqual(routeRepairAsk(sentence, "flush", undefined, true), { route: "repair-plan" }, sentence);
    assert.notEqual(routeRepairAsk(sentence, "flush", undefined, false).route, "repair-plan", sentence);
  }
  // the founder's bare sweep stays with the sweep card, which says the same "None of these keeps…" when nothing picks
  for (const sentence of ["find the smallest repair that stays elastic at 300 N/mm", "sweep the step length for 250 N/mm", "add a step", "solve the slice",
    "solve the slice and tell me the peel stress", "what fails first?", "and at 250?", "tell me the repair is strong enough for certification"]) {
    assert.ok(!asksRepairPlan(sentence), sentence);
  }
  assert.ok(isQuestion("how did you get 16740 N") && !isQuestion("can you make it 30 wide?"), "the coupon's chat keeps its words for a question");
});

test("a wing's plan names its kind and project, a repair's names no project, and each approval's runs are read by their own routes' readers", () => {
  assert.deepEqual([wingProposed.kind, typeof wingProposed.project, wingProposed.state], ["wing", "string", "proposed"]);
  assert.deepEqual(wingProposed.steps.map((s) => [s.role, s.tool]), [["Setup", "add_plies"], ["Solver", "analyze"], ["Solver", "check"], ["Report", "answer"]]);
  assert.deepEqual([repairProposed.kind, repairProposed.project], ["repair", null]);
  assert.deepEqual(repairProposed.steps.map((s) => [s.role, s.tool]), [["Solver", "sweep"], ["Geometry", "use_pick"], ["Solver", "solve"], ["Solver", "bond"],
    ["Report", "answer"]]);
  assert.throws(() => readPlanOutput({ ...planner("wing-plan-answered"), project: null }), StudioError); // only a repair's plan has none
  assert.throws(() => readRepairPlanApproval({ plan: planner("repair-plan-answered"), runs: [] }), StudioError); // no repair

  const wing = wingRuns(wingApproval.runs);
  assert.deepEqual(wingApproval.runs.map((r) => [r.n, r.tool]), [[2, "analyze"], [3, "check"]]);
  assert.deepEqual(wing.analyze?.wing, wingApproval.project.content.wing, "the hand calculation of the wing the plan left");
  assert.deepEqual([wing.check?.job_id, wing.check?.state], [wingApproval.plan.job, "queued"]);

  const repair = repairRuns(repairApproval.plan, repairApproval.runs);
  assert.deepEqual(repairApproval.repair, repair.sweep?.picked, "the page's repair from then on is the sweep's own pick");
  assert.deepEqual([repair.sweep?.pick, repair.sweep?.target, repair.cutFaces], [1, 300, "open"]);
  assert.equal(repair.check?.holds, false, "the slice may not hold the pick, and says so");
  assert.match(repair.check?.words.join(" ") ?? "", /does not hold the pick/);
  assert.ok(repair.solve?.headline && repair.solve.report.bond && repair.bond?.report.onset);
  assert.deepEqual(repairRuns(repairApproval.plan, []), { sweep: null, solve: null, cutFaces: "open", check: null, bond: null });
});

test("a wing's steps tick off: the server's at approval, the check as it is followed, then the answer the page gives", () => {
  const before = kindViews(wingProposed, { approved: false, check: null, answers: {} });
  assert.ok(before.every((v) => v.state === "planned"));
  const queued = kindViews(wingApproval.plan, wingAt({}));
  assert.deepEqual(states(queued), ["add_plies done", "analyze done", "check running", "answer planned"]);
  assert.equal(queued.find((v) => v.tool === "check")?.note, "Waiting to start…");
  assert.match(queued.find((v) => v.tool === "analyze")?.note ?? "", /^(Passes|Fails) /, "the hand calculation's verdict, in the engine's numbers");
  assert.ok(!readyToAnswer(queued, 4));
  assert.deepEqual(kindReports("wing", queued, {}), [], "a check is the server's while it runs");

  const done = kindViews(wingApproval.plan, wingAt({ check: checkAt("done", { report: CHECK_REPORT }) }));
  assert.deepEqual(states(done), ["add_plies done", "analyze done", "check done", "answer planned"]);
  assert.equal(done.find((v) => v.tool === "check")?.note, feWords(CHECK_REPORT).headline);
  assert.ok(readyToAnswer(done, 4));
  assert.deepEqual(kindReports("wing", done, {}), [{ n: 3, state: "done", note: feWords(CHECK_REPORT).headline }]);

  const answered = kindViews(wingApproval.plan, wingAt({ check: checkAt("done", { report: CHECK_REPORT }),
    answers: { 4: { state: "done", heading: "Lowest margin +0.1", more: [], note: null } } }));
  assert.deepEqual(planCount(answered), { done: 4, of: 4, ended: true });
  assert.deepEqual(kindReports("wing", answered, { 3: "done" }), [{ n: 4, state: "done", note: "Lowest margin +0.1" }]);

  const stopped = kindViews(wingApproval.plan, wingAt({ check: checkAt("stopped", { message: "The solver stopped." }) }));
  assert.deepEqual(states(stopped), ["add_plies done", "analyze done", "check failed", "answer skipped"]);
  assert.equal(stopped.find((v) => v.tool === "check")?.note, "The solver stopped.");
  assert.deepEqual(kindReports("wing", stopped, {}), [{ n: 3, state: "failed", note: "The solver stopped." }, { n: 4, state: "skipped", note: null }]);
});

test("a repair's steps are the server's once approved; the page gives and reports each answer only", () => {
  const approved = kindViews(repairApproval.plan, { approved: true, check: null, answers: {} });
  assert.deepEqual(states(approved), ["sweep done", "use_pick done", "solve done", "bond done", "answer planned"]);
  assert.ok(readyToAnswer(approved, 5));
  assert.deepEqual(kindReports("repair", approved, {}), []);
  const running = kindViews(repairApproval.plan, { approved: true, check: null, answers: { 5: { state: "running", heading: null, more: [], note: null } } });
  assert.deepEqual(kindReports("repair", running, {}), [{ n: 5, state: "running", note: null }]);
  assert.deepEqual(newKindFlow(repairProposed).stage, "proposed");
});

test("a refused plan's reasons are the engine's own words, a line each, with the step's number taken off", () => {
  const refused = readPlanOutput(planner("repair-plan-refused"));
  assert.deepEqual([refused.state, refused.kind, refused.steps], ["refused", "repair", []]);
  const [line] = refusalLines(refused.reason);
  assert.match(line, /^The sweep picks nothing to use: None of these keeps the adhesive elastic at 300 N\/mm\. The most is [\d.]+ N\/mm, with a step length of [\d.]+ mm\.$/);
  assert.deepEqual(refusalLines(readPlanOutput(planner("wing-plan-refused")).reason), ["[0/45/-45/0]s has 0 plies at 90°: 2 cannot be taken out."]);
  assert.deepEqual(refusalLines("step 1: one; with a semicolon; step 3: two"), ["One; with a semicolon", "Two"]);
  assert.deepEqual(refusalLines(null), []);
  assert.deepEqual(refusalLines("step 2: written with C:\\Users\\path"), [], "a line not fit to show is left out");
});

test("while the approval runs the card says what runs and about how long", () => {
  assert.equal(waitingWords(repairProposed),
    "The sweep, the solve of the slice and the bond until it lets go run now: a few seconds, up to about two minutes. Stay on this page.");
  assert.equal(waitingWords(wingProposed), "The hand calculation and the start of the check run now: a moment. Stay on this page.");
});

test("an answer step is answered as each page's chat answers the question, in the engine's numbers and the product's words", () => {
  const { analyze } = wingRuns(wingApproval.runs);
  const wing = wingApproval.project.content.wing as Parameters<typeof wingPlanAnswer>[2];
  const hand = wingPlanAnswer("What is the lowest margin?", analyze!.report, wing, null);
  assert.equal(hand.state, "done");
  assert.match(hand.heading ?? "", /[+−]\d\.\d{3}/, "a margin the engine worked");
  const checked = wingPlanAnswer("What is the lowest margin?", analyze!.report, wing, checkAt("done", { report: CHECK_REPORT }));
  assert.deepEqual(checked.more.slice(-2), [feWords(CHECK_REPORT).headline, feWords(CHECK_REPORT).where]);
  assert.equal(wingPlanAnswer("hello there", analyze!.report, wing, null).state, "failed");

  const runs = repairRuns(repairApproval.plan, repairApproval.runs);
  const worked = JSON.parse(readFileSync("tests/fixtures/repair/example-answer.json", "utf8")); // a hand calculation, as the page holds one
  const held: RepairHeld = { repair: repairApproval.repair as RepairDescription, report: worked.report, slice: runs.solve!.report, sliceStale: false, needs: [],
    bond: runs.bond!.report, bondStale: false };
  const first = repairPlanAnswer("What fails first?", held);
  assert.equal(first.state, "done");
  for (const said of [hand, checked, first]) assert.deepEqual(bannedIn([said.heading, ...said.more].join("\n")), []);

  const section: ReferenceSection = { id: "repair:peel", document: "Bonded repairs", title: "Peel stress", text: "Peel pulls the adhesive apart.\n\n$$x$$" };
  assert.deepEqual(withSection({ state: "done", heading: "Answered from our reference pages", more: ["a"], note: null }, "reference", [section]),
    { state: "done", heading: "Peel stress", more: ["Peel pulls the adhesive apart.", "a"], note: "From our pages: Bonded repairs, Peel stress" });
  assert.equal(withSection(first, "reference", []).state, "failed");
});

test("a repair's plan is asked with the repair the page holds, read, approved with it and its answer reported at the repair's own routes", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const answers = [planner("repair-plan-answered"), planner("repair-plan-answered"), planner("repair-approve-answered"), planner("repair-approve-answered").plan];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(answers.shift()), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  try {
    const repair = { title: "a repair" } as unknown as RepairDescription;
    const plan = await askRepairPlan("http://api.test/", "find the smallest repair that stays elastic at 300 N/mm, then solve it", repair);
    assert.equal(calls[0].url, "http://api.test/v1/workspace/repair-plans");
    assert.deepEqual(JSON.parse(String(calls[0].init.body)), { ask: "find the smallest repair that stays elastic at 300 N/mm, then solve it", repair });
    await readRepairPlan("http://api.test", plan.id);
    assert.deepEqual([calls[1].url, calls[1].init.method], [`http://api.test/v1/workspace/repair-plans/${plan.id}`, "GET"]);
    const approval = await approveRepairPlan("http://api.test", plan.id, repair, plan.base);
    assert.equal(calls[2].url, `http://api.test/v1/workspace/repair-plans/${plan.id}/approve`);
    assert.deepEqual(JSON.parse(String(calls[2].init.body)), { repair, base: plan.base });
    assert.equal(approval.runs.length, 3);
    const after = await reportRepairPlanStep("http://api.test", plan.id, 5, "done", "The adhesive, in shear.");
    assert.equal(calls[3].url, `http://api.test/v1/workspace/repair-plans/${plan.id}/steps/5`);
    assert.deepEqual(JSON.parse(String(calls[3].init.body)), { state: "done", note: "The adhesive, in shear." });
    assert.equal(after?.kind, "repair");
  } finally {
    globalThis.fetch = original;
  }
});
