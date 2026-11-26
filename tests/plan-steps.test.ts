import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { planCount, planDrawing, stepsToReport, stepViews, type PlanProgress } from "../lib/plan-steps";
import { readPlanApproval, readPlanOutput, type JobStatus } from "../lib/studio-api";
import type { QaReading } from "../lib/plan-qa";

// A plan's steps as they tick off (ADR-0144): the server's at approval, the run as the page follows it, the QA and the answer the page carries.
const planner = (name: string) => JSON.parse(readFileSync(`tests/fixtures/planner/${name}.json`, "utf8"));
const studio = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}.json`, "utf8")) as JobStatus;
const proposed = readPlanOutput(planner("plan-proposed"));
const approval = readPlanApproval(planner("approve-running"));
const PASS: QaReading = { verdict: "pass", headline: "Pass", checks: [] };
const STOP: QaReading = { verdict: "stop", headline: "Stop: the result does not hold up", checks: [] };
const states = (views: { tool: string; state: string }[]) => Object.fromEntries(views.map((v) => [v.tool, v.state]));
const at = (p: Partial<PlanProgress>): PlanProgress => ({ approved: true, job: approval.job, qa: null, answer: null, ...p });

test("before approval every step is planned, each under its role, in the plan's order", () => {
  const views = stepViews(proposed, { approved: false, job: null, qa: null, answer: null });
  assert.ok(views.every((v) => v.state === "planned"));
  assert.deepEqual(views.map((v) => [v.n, v.role]), [[1, "Setup"], [2, "Setup"], [3, "Solver"], [4, "Solver"], [5, "QA"], [6, "Report"]]);
  assert.deepEqual(planCount(views), { done: 0, of: 6, ended: false });
});

test("once approved the setup and the check are done, and the run follows the job the server started", () => {
  const queued = stepViews(approval.plan, at({}));
  assert.deepEqual(states(queued), { hold: "done", force: "done", check: "done", run: "running", qa: "planned", answer: "planned" });
  assert.equal(queued.find((v) => v.tool === "run")?.note, "Queued");
  const running = stepViews(approval.plan, at({ job: studio("job-running") }));
  assert.equal(running.find((v) => v.tool === "run")?.state, "running");
  const done = stepViews(approval.plan, at({ job: studio("job-done") }));
  assert.deepEqual(states(done), { hold: "done", force: "done", check: "done", run: "done", qa: "running", answer: "planned" });
  assert.deepEqual(stepsToReport(done, {}), []); // the QA is reported once it is read, not while it reads
});

test("the QA and the answer tick off, each reported once it ends and the answer also as it starts", () => {
  const job = studio("job-done");
  const checked = stepViews(approval.plan, at({ job, qa: PASS }));
  assert.equal(checked.find((v) => v.tool === "qa")?.state, "done");
  assert.deepEqual(stepsToReport(checked, {}), [{ n: 5, state: "done", note: "Pass" }]);
  const asking = stepViews(approval.plan, at({ job, qa: PASS, answer: { state: "running", line: null } }));
  assert.deepEqual(stepsToReport(asking, { 5: "done" }), [{ n: 6, state: "running", note: null }]);
  const answered = stepViews(approval.plan, at({ job, qa: PASS, answer: { state: "done", line: "Yes, it holds at 2 kN." } }));
  assert.deepEqual(stepsToReport(answered, { 5: "done", 6: "running" }), [{ n: 6, state: "done", note: "Yes, it holds at 2 kN." }]);
  assert.deepEqual(stepsToReport(answered, { 5: "done", 6: "done" }), []);
  assert.deepEqual(planCount(answered), { done: 6, of: 6, ended: true });
});

test("a stopped run fails its step and skips the QA and the answer; a QA that stops skips the answer", () => {
  const stopped = { ...studio("job-running"), state: "stopped" as const };
  const views = stepViews(approval.plan, at({ job: stopped }));
  assert.deepEqual(states(views), { hold: "done", force: "done", check: "done", run: "failed", qa: "skipped", answer: "skipped" });
  assert.match(views.find((v) => v.tool === "run")?.note ?? "", /^The analysis stopped/);
  assert.deepEqual(stepsToReport(views, {}).map((r) => [r.n, r.state]), [[5, "skipped"], [6, "skipped"]]);
  const halted = stepViews(approval.plan, at({ job: studio("job-done"), qa: STOP }));
  assert.deepEqual([halted[4].state, halted[5].state], ["failed", "skipped"]);
  assert.equal(planCount(halted).ended, true);
});

test("a plan the server stopped at its check fails the check and skips the run", () => {
  const plan = { ...approval.plan, state: "stopped" as const, steps: approval.plan.steps.map((s) => (s.tool === "check" ? { ...s, state: "failed" as const, note: "Width: missing" }
    : s.tool === "run" ? { ...s, state: "planned" as const } : s)) };
  const views = stepViews(plan, at({ job: null }));
  assert.deepEqual(states(views), { hold: "done", force: "done", check: "failed", run: "skipped", qa: "skipped", answer: "skipped" });
  assert.equal(views.find((v) => v.tool === "check")?.note, "Width: missing");
});

test("the plan's supports and loads are drawn before anything applies, a pull by its sense along the edge's outward normal", () => {
  assert.deepEqual(planDrawing(proposed), {
    supports: [{ region: "Edge-Bottom", dofs: [1, 2, 3, 4, 5, 6] }],
    loads: [{ region: "Edge-Top", kind: "force", dof: 2, value: "2", unit: "kN" }],
  });
  const step = (change: Record<string, unknown>) => ({ ...proposed.steps[0], change: { action: "force", value: "2", unit: "kN", ...change } });
  const drawn = planDrawing({ steps: [step({ region: "Edge-Left", sense: "tension" }), step({ region: "Edge-Bottom", sense: "compression" }),
    step({ region: "Edge-Right", sense: "compression" }), step({ region: "Face", sense: "tension" }), step({ region: "Edge-Top", dof: 3, value: "-5" }),
    { ...proposed.steps[0], change: { action: "pressure", region: "Face", value: "0.01", unit: "MPa" } },
    { ...proposed.steps[0], change: { action: "row", key: "width", value: "30", unit: "mm" } }] });
  assert.deepEqual(drawn?.loads.map((l) => [l.region, l.kind, l.dof, l.value]), [["Edge-Left", "force", 1, "-2"], ["Edge-Bottom", "force", 2, "2"],
    ["Edge-Right", "force", 1, "-2"], ["Edge-Top", "force", 3, "-5"], ["Face", "pressure", null, "0.01"]]);
  assert.equal(planDrawing({ steps: [{ ...proposed.steps[0], change: { action: "row", key: "width", value: "30" } }] }), null);
});
