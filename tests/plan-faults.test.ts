import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { banks, liveFaults, modelAnswer, modelRequests, type Question, type Reading } from "./assistant-questions/harness";
import { contractFaults, planFaults, planHeading, planSeen } from "./assistant-questions/plan-faults";

// How a plan is graded wherever it is seen (ADR-0144, build step 4): the contract every plan keeps before its approval, what a bank's
// question expects of it (`live.plan`), and how the real-model run asks for one and shows it. Nothing here calls a model.
const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/planner/${name}`, "utf8")) as Record<string, unknown>;
const PROPOSED = fixture("plan-proposed.json"), QUESTION = fixture("plan-question.json"), RUNNING = fixture("approve-running.json");
const planner = banks().find((b) => b.feature === "planner")!;
const asked = (ask: string, page = "plate"): Question => planner.questions.find((q) => q.ask === ask && q.page === page)!;

test("the contract's own plans keep the contract, and a plan approved by nobody does not", () => {
  assert.deepEqual(contractFaults(planSeen(PROPOSED)), []);
  assert.deepEqual(contractFaults(planSeen(QUESTION)), []);
  assert.deepEqual(contractFaults(planSeen(RUNNING.plan as Record<string, unknown>)), ["the plan is running, though nobody approved it",
    "the running plan shows 6 steps"]);
  assert.equal(planHeading(planSeen(PROPOSED)), "Plan · 6 steps");
  assert.equal(planHeading(planSeen(QUESTION)), "One question first");
});

test("a plan that runs with no check, runs twice, changes after its run or holds more than twelve steps breaks the contract", () => {
  const step = (tool: string, role = "Setup", state = "planned") => ({ tool, role, state });
  const plan = (...steps: ReturnType<typeof step>[]) => ({ state: "proposed", steps });
  assert.deepEqual(contractFaults(plan(step("row"), step("run", "Solver"))), ["the run is not between the setup check and the result's checks"]);
  assert.ok(contractFaults(plan(step("check", "Solver"), step("run", "Solver"), step("qa", "QA"), step("run", "Solver"))).includes("2 runs; a plan runs once"));
  assert.deepEqual(contractFaults(plan(step("check", "Solver"), step("run", "Solver"), step("qa", "QA"), step("row"))), ["the change row comes after the run"]);
  assert.deepEqual(contractFaults(plan(step("answer", "Report"))), ["an answer before any run"]);
  assert.deepEqual(contractFaults(plan(step("row", "Admin"), step("row", "Setup", "done"))), ["step row has the role Admin", "step row is done before the approval"]);
  const long = plan(...Array.from({ length: 10 }, () => step("hold")), step("check", "Solver"), step("run", "Solver"), step("qa", "QA"));
  assert.deepEqual(contractFaults(long), ["13 steps; a plan has at most 12"]);
  assert.deepEqual(contractFaults({ state: "refused", steps: [], reason: "" }), ["a refused plan gives no reason"]);
  assert.deepEqual(contractFaults({ state: "question", steps: [], question: "Which edge." }), ["the question back is no question"]);
});

test("a bank's plan is held to its state, steps, rows, regions and words", () => {
  const seen = planSeen(PROPOSED);
  assert.deepEqual(planFaults({ state: "proposed", tools: ["hold", "force", "check", "run", "qa", "answer"], regions: ["Edge-Bottom", "Edge-Top"] }, seen), []);
  assert.deepEqual(planFaults({ state: "question" }, seen), ["the plan is proposed, expected question"]);
  assert.deepEqual(planFaults({ state: "proposed", never: ["force"], regions: ["Edge-Left"] }, seen),
    ["a force step", "no step on the Edge-Left; regions: Edge-Bottom, Edge-Top"]);
  const refused = { state: "refused", steps: [], reason: "step 1: steel is not a material of the library; the materials are given by id" };
  assert.deepEqual(planFaults({ state: ["refused", "question"], says: ["not a material of the library"], leaves: ["library"] }, refused), []);
  assert.deepEqual(planFaults({ state: "proposed" }, null), ["no plan was made; expected proposed"]);
  assert.deepEqual(planFaults(undefined, null), []);
});

test("the real-model run asks the planner for a sentence the page plans, with the setup the page holds, and shows the card's words", () => {
  const question = asked("clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds");
  const [request] = modelRequests(question);
  assert.equal(request.reader, "plans");
  assert.equal(request.body.ask, question.ask);
  const content = request.body.content as { form: Record<string, string>; plate: Record<string, unknown[]> };
  assert.equal(content.form.test, "plate");
  assert.deepEqual(content.plate, { supports: [], loads: [], regions: [] });
  assert.deepEqual(modelRequests(asked("the bottom one")), []); // a reply with no sentence before it in the bank: nothing to plan again
  const readings: Reading[] = [{ reader: "plans", response: PROPOSED }];
  const said = modelAnswer(question, readings);
  assert.equal(said.kind, "plan");
  assert.equal(said.heading, "Plan · 6 steps");
  assert.equal(said.lines[0], "Setup: Edge-Bottom: fixed (encastre)");
  assert.deepEqual(liveFaults(question, readings, said), []);
  const question2 = modelAnswer(question, [{ reader: "plans", response: QUESTION }]);
  assert.equal(question2.heading, "One question first");
  assert.ok(liveFaults(question, [{ reader: "plans", response: QUESTION }], question2).includes("the plan is question, expected proposed"));
  const none = modelAnswer(question, [{ reader: "plans", response: { ...PROPOSED, state: "unavailable", steps: [] } }]);
  assert.notEqual(none.kind, "plan"); // no model: the page reads the sentence as before
  assert.equal(modelAnswer(question, [{ reader: "plans", response: null, error: "no answer" }]).heading, "No plan right now");
});
