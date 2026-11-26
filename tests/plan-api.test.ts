import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { approvePlan, askPlan, noPlanner, readPlan, readPlanApproval, readPlanOutput, RECORDS_HEADER, reportPlanStep, StudioError } from "../lib/studio-api";
import { FAILED_WORDS } from "../lib/studio-copy";

// The planner's contract (ADR-0144), as the page reads it: the files in tests/fixtures/planner/ are the API's answers.
const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/planner/${name}.json`, "utf8"));
const PROJECT = "0b3c6a1e-1111-4222-8333-944455556666";
const PLAN = "5d1f2c3a-7777-4888-9999-aaaabbbbcccc";

type Call = { url: string; init: RequestInit };
async function answering<T>(answers: { status?: number; body: unknown; headers?: Record<string, string> }[], run: (calls: Call[]) => Promise<T>): Promise<T> {
  const calls: Call[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const next = answers.shift()!;
    return new Response(JSON.stringify(next.body), { status: next.status ?? 200, headers: { "Content-Type": "application/json", ...(next.headers ?? {}) } });
  }) as typeof fetch;
  try { return await run(calls); } finally { globalThis.fetch = original; }
}

test("a plan, a question back and an approval are read as the fixtures hold them, and keys the API adds are ignored", () => {
  const plan = readPlanOutput({ ...fixture("plan-proposed"), later_key: 1 });
  assert.equal(plan.state, "proposed");
  assert.deepEqual(plan.steps.map((s) => [s.n, s.role, s.tool]), [[1, "Setup", "hold"], [2, "Setup", "force"], [3, "Solver", "check"], [4, "Solver", "run"],
    [5, "QA", "qa"], [6, "Report", "answer"]]);
  assert.equal(plan.steps[1].change?.sense, "tension");
  assert.equal(plan.steps[5].question, "Does it hold at 2 kN?");
  assert.equal(plan.base, "9f1c000000000000000000000000000000000000000000000000000000000000");
  assert.equal(plan.requests_left, 29);
  assert.ok(!("later_key" in plan));

  const asked = readPlanOutput(fixture("plan-question"));
  assert.equal(asked.state, "question");
  assert.match(asked.question ?? "", /^Which end do you mean/);
  assert.deepEqual(asked.steps, []);

  const approval = readPlanApproval(fixture("approve-running"));
  assert.equal(approval.plan.state, "running");
  assert.equal(approval.plan.job, "7a7a7a7a-1111-4222-8333-944455556666");
  assert.equal(approval.job?.state, "queued");
  assert.equal(approval.project.id, PROJECT);
  assert.deepEqual((approval.project.content.plate as { supports: { region: string }[] }).supports.map((s) => s.region), ["Edge-Bottom"]);
  assert.equal(approval.check, null);
  assert.equal((approval.version as { by: string }).by, "assistant");
});

test("a step the page cannot read is left out, an unknown step state is planned, and a plan with no id or a state of its own is refused", () => {
  const plan = readPlanOutput({ ...fixture("plan-proposed"), steps: [{ n: 1, tool: "qa", line: "Check the result", state: "later" }, { n: "two" }, null] });
  assert.deepEqual(plan.steps.map((s) => [s.role, s.state]), [["QA", "planned"]]);
  assert.throws(() => readPlanOutput({ ...fixture("plan-proposed"), id: 4 }), StudioError);
  assert.throws(() => readPlanOutput({ ...fixture("plan-proposed"), state: "thinking" }), StudioError);
  assert.throws(() => readPlanApproval({ plan: fixture("plan-proposed") }), StudioError); // no project
});

test("the plan is asked, read, approved and its steps reported at the project's own routes, with the studio's actor", async () => {
  await answering([{ body: fixture("plan-proposed") }, { body: fixture("plan-proposed") }, { body: fixture("approve-running") }, { body: fixture("approve-running").plan }, { body: { ok: true } }],
    async (calls) => {
      const plan = await askPlan("http://api.test/", PROJECT, "clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds");
      assert.equal(calls[0].url, `http://api.test/v1/projects/${PROJECT}/plans`);
      assert.equal(calls[0].init.method, "POST");
      assert.deepEqual(JSON.parse(String(calls[0].init.body)), { ask: "clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds" });
      assert.equal((calls[0].init.headers as Record<string, string>)["X-Anisotropy-Actor"], "studio");

      await readPlan("http://api.test", PROJECT, plan.id);
      assert.equal(calls[1].url, `http://api.test/v1/projects/${PROJECT}/plans/${PLAN}`);
      assert.equal(calls[1].init.method, "GET");

      const approval = await approvePlan("http://api.test", PROJECT, plan.id, plan.base);
      assert.equal(calls[2].url, `http://api.test/v1/projects/${PROJECT}/plans/${PLAN}/approve`);
      assert.deepEqual(JSON.parse(String(calls[2].init.body)), { base: plan.base });
      assert.equal(approval.job?.job_id, "7a7a7a7a-1111-4222-8333-944455556666");

      const after = await reportPlanStep("http://api.test", PROJECT, plan.id, 5, "done", "Pass.");
      assert.equal(calls[3].url, `http://api.test/v1/projects/${PROJECT}/plans/${PLAN}/steps/5`);
      assert.deepEqual(JSON.parse(String(calls[3].init.body)), { state: "done", note: "Pass." });
      assert.equal(after?.state, "running");
      assert.equal(await reportPlanStep("http://api.test", PROJECT, plan.id, 6, "running", null), null); // an answer that is no plan is none
    });
});

test("no planner here is a 404 or an API that keeps no projects; a model changed since the plan is a 409 in the API's own words", async () => {
  await answering([{ status: 404, body: { detail: "Not Found" } }, { status: 503, body: { detail: "no database" }, headers: { [RECORDS_HEADER]: "off" } },
    { status: 409, body: { detail: "The model changed since this plan was made. Plan it again." } }, { status: 502, body: { detail: "upstream" } }], async () => {
    await assert.rejects(askPlan("http://api.test", PROJECT, "set the width to 30 mm and run it"), (error) => noPlanner(error));
    await assert.rejects(askPlan("http://api.test", PROJECT, "set the width to 30 mm and run it"), (error) => noPlanner(error));
    await assert.rejects(approvePlan("http://api.test", PROJECT, PLAN, "9f1c"),
      (error: StudioError) => !noPlanner(error) && error.status === 409 && error.message === "The model changed since this plan was made. Plan it again.");
    await assert.rejects(askPlan("http://api.test", PROJECT, "x"), (error: StudioError) => !noPlanner(error) && error.status === 502);
  });
  for (const what of ["the plan", "reading the plan", "approving the plan", "reporting the plan's step"]) assert.ok(what in FAILED_WORDS, what);
});
