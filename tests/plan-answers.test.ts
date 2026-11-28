import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as planSteps from "../lib/plan-steps";
import type { PlanProgress } from "../lib/plan-steps";
import { readPlanApproval, type JobStatus } from "../lib/studio-api";
import type { QaReading } from "../lib/plan-qa";

// A plan with more than one answer step (ADR-0144 amendment 2; the planner keeps "one run, the changes before it and the answers after
// it"): every answer step is carried, in the plan's order, each asked once and each with its own words.
const { planCount, stepsToReport, stepViews } = planSteps;
const planner = (name: string) => JSON.parse(readFileSync(`tests/fixtures/planner/${name}.json`, "utf8"));
const studio = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}.json`, "utf8")) as JobStatus;
const approval = readPlanApproval(planner("approve-running"));
const second = { ...approval.plan.steps[5], n: 7, question: "What is the largest deflection?", line: "Answer: What is the largest deflection?" };
const plan = { ...approval.plan, steps: [...approval.plan.steps, second] };
const PASS: QaReading = { verdict: "pass", headline: "Pass", checks: [] };
const STOP: QaReading = { verdict: "stop", headline: "Stop: the result does not hold up", checks: [] };
const job = studio("job-done");
const at = (p: Partial<PlanProgress>): PlanProgress => ({ approved: true, job, qa: PASS, answer: null, ...p });
const answers = (views: { n: number; tool: string; state: string; note: string | null }[]) => views.filter((v) => v.tool === "answer").map((v) => [v.n, v.state, v.note]);
const HOLDS = "Yes, it holds at 2 kN.", DEFLECTS = "The largest deflection is 0.4 mm.";

test("the plan of this test is the contract's with a second answer after the first", () => {
  assert.deepEqual(plan.steps.map((s) => s.tool), ["hold", "force", "check", "run", "qa", "answer", "answer"]);
  assert.notEqual(plan.steps[5].question, plan.steps[6].question);
});

test("a second answer step never takes the first one's words, and is not done because the first is", () => {
  // a caller that holds one answer holds the first answer step's
  const one = stepViews(plan, at({ answer: { state: "done", line: HOLDS } }));
  assert.deepEqual(answers(one), [[6, "done", HOLDS], [7, "planned", null]]);
  assert.deepEqual(stepsToReport(one, { 5: "done", 6: "running" }), [{ n: 6, state: "done", note: HOLDS }]);
  assert.equal(planCount(one).ended, false); // one answer is still to give
  const asking = stepViews(plan, at({ answer: { state: "running", line: null } }));
  assert.deepEqual(answers(asking), [[6, "running", null], [7, "planned", null]]);
});

test("each answer step is given by its own number, and reported with its own words", () => {
  const first = stepViews(plan, at({ answers: { 6: { state: "done", line: HOLDS } } }));
  assert.deepEqual(answers(first), [[6, "done", HOLDS], [7, "planned", null]]);
  const next = stepViews(plan, at({ answers: { 6: { state: "done", line: HOLDS }, 7: { state: "running", line: null } } }));
  assert.deepEqual(stepsToReport(next, { 5: "done", 6: "done" }), [{ n: 7, state: "running", note: null }]);
  const both = stepViews(plan, at({ answers: { 6: { state: "done", line: HOLDS }, 7: { state: "done", line: DEFLECTS } } }));
  assert.deepEqual(answers(both), [[6, "done", HOLDS], [7, "done", DEFLECTS]]);
  assert.deepEqual(stepsToReport(both, { 5: "done", 6: "done", 7: "running" }), [{ n: 7, state: "done", note: DEFLECTS }]);
  assert.deepEqual(planCount(both), { done: 7, of: 7, ended: true });
});

test("the answers are asked one at a time, in the plan's order, each once", () => {
  const due = (p: Partial<PlanProgress>) => planSteps.answerDue(stepViews(plan, at({ answers: {}, ...p })));
  assert.equal(due({ qa: null }), null); // not before the QA has read the result
  assert.equal(due({ job: studio("job-running"), qa: null }), null);
  assert.equal(due({}), 6);
  assert.equal(due({ answers: { 6: { state: "running", line: null } } }), null); // one under way: the next waits
  assert.equal(due({ answers: { 6: { state: "done", line: HOLDS } } }), 7);
  assert.equal(due({ answers: { 6: { state: "done", line: HOLDS }, 7: { state: "running", line: null } } }), null);
  assert.equal(due({ answers: { 6: { state: "done", line: HOLDS }, 7: { state: "done", line: DEFLECTS } } }), null); // none left
});

test("no answer is asked after one that was not given, or on a result the QA stopped", () => {
  const failed = stepViews(plan, at({ answers: { 6: { state: "failed", line: "No answer to read in this result" } } }));
  assert.deepEqual(answers(failed), [[6, "failed", "No answer to read in this result"], [7, "skipped", null]]);
  assert.equal(planSteps.answerDue(failed), null);
  assert.deepEqual(stepsToReport(failed, { 5: "done", 6: "running" }).map((r) => [r.n, r.state]), [[6, "failed"], [7, "skipped"]]);
  assert.equal(planCount(failed).ended, true);
  const stopped = stepViews(plan, at({ qa: STOP, answers: {} }));
  assert.deepEqual(answers(stopped), [[6, "skipped", null], [7, "skipped", null]]);
  assert.equal(planSteps.answerDue(stopped), null);
});

test("a plan with one answer is asked as before", () => {
  const due = (p: Partial<PlanProgress>) => planSteps.answerDue(stepViews(approval.plan, at({ answers: {}, ...p })));
  assert.equal(due({ qa: null }), null);
  assert.equal(due({}), 6);
  assert.equal(due({ answers: { 6: { state: "running", line: null } } }), null);
  assert.equal(due({ answers: { 6: { state: "done", line: HOLDS } } }), null);
});
