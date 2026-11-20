import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { asksWorking, criterionNamed, givenText, stepAsked, workingFor, workingOf } from "../lib/result-working";
import { asksWhy } from "../lib/result-why";
import type { Fields } from "../lib/studio-api";

const fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8")) as Fields;
const without = { summary: { ...fields.summary, working: undefined } } as Pick<Fields, "summary">;

test("a request for the formula, the proof or the steps is told from a question of why and from a setup line (ADR-0103)", () => {
  for (const text of ["send me the formula", "the proof of it being solved", "show me the formula", "prove it", "how was that calculated?", "what is the formula for tsai hill?",
    "can I see the working?", "step by step please", "show the calculation for maximum stress", "Show the working", "formula?", "derivation please", "how did you get the factor",
    "give me the equations", "where is the proof"]) {
    assert.equal(asksWorking(text), true, text);
  }
  for (const text of ["stress in ply 5 at element 120", "why does ply 4 fail first?", "make it [0/90]2s", "it is not working", "finer mesh", "A. Engineer", "run", "check",
    "where is the shear stress highest?", "what is the stress here?", "10 kN in tension", "is the mesh working"]) {
    assert.equal(asksWorking(text), false, text);
  }
  assert.equal(asksWhy("show me the formula"), false); // the two readers do not both claim it
});

test("a criterion is read by its name", () => {
  assert.equal(criterionNamed("the formula for Tsai-Hill"), "tsai_hill");
  assert.equal(criterionNamed("show the max stress working"), "max_stress");
  assert.equal(criterionNamed("maximum stress proof"), "max_stress");
  assert.equal(criterionNamed("tsai wu please"), "tsai_wu");
  assert.equal(criterionNamed("show me the formula"), null);
});

test("the working asked for is the criterion named, else the earliest of the answer", () => {
  const plain = workingFor(fields, "show me the formula");
  assert.ok(plain && plain.kind === "chain");
  assert.equal(plain.criterion, fields.summary.verdict?.earliest);
  assert.equal(plain.criterion, "tsai_hill");
  assert.equal(plain.name, "Tsai-Hill");
  assert.equal(plain.basis, "the gauge section");
  assert.deepEqual(plain.others, ["Maximum stress"]);
  assert.deepEqual(plain.chain.steps.map((s) => s.id), ["strain", "stress", "criterion", "loading"]);
  assert.equal(plain.chain.factor, Number(fields.summary.fpf_gauge?.tsai_hill.factor.toPrecision(4))); // the answer the page shows
  const named = workingFor(fields, "the proof for maximum stress");
  assert.ok(named && named.kind === "chain" && named.criterion === "max_stress" && named.others[0] === "Tsai-Hill");
  assert.deepEqual(workingFor(fields, "formula for tsai-wu"), { kind: "not-worked", name: "Tsai-Wu", others: ["Maximum stress", "Tsai-Hill"] });
});

test("a quantity asked by name is answered with its one step; a criterion, none or two ask for the whole working (ADR-0103 amendment 1)", () => {
  // the founder's question on the live site, 2026-11-20: shown the whole Tsai-Hill working, "didnt really answer my question"
  for (const [text, step] of [["equation for stress", "stress"], ["whats the stress equation", "stress"], ["show me the equation for σ2", "stress"],
    ["how was the strain calculated?", "strain"], ["formula for the failure index", "criterion"], ["how did you get the load at failure", "loading"],
    ["show me the formula", null], ["derive the failure factor", null], ["how did you get 16740 N", null], ["the working for max stress", null],
    ["equation for stress and strain", null]] as const) {
    assert.equal(stepAsked(text), step, text);
  }
  for (const text of ["equation for stress", "whats the stress equation", "stress formula?"]) assert.equal(asksWorking(text), true, text);
  const stress = workingFor(fields, "equation for stress");
  assert.ok(stress && stress.kind === "chain");
  assert.equal(stress.criterion, "tsai_hill"); // the earliest criterion's chain, its one step
  assert.equal(stress.step?.id, "stress");
  assert.equal(stress.step?.title, "The ply's stress from its strain");
  const whole = workingFor(fields, "show me the formula");
  assert.ok(whole && whole.kind === "chain" && whole.step === null);
});

test("a result with no working, or one in another shape, has none to show", () => {
  assert.equal(workingOf(without), null);
  assert.equal(workingFor(without, "show me the formula"), null);
  assert.equal(workingFor(null, "show me the formula"), null);
  const broken = { summary: { ...fields.summary, working: { basis: "gauge", digits: { given: 6, result: 4 }, criteria: { tsai_hill: { steps: [] } } } } } as unknown as Pick<Fields, "summary">;
  assert.equal(workingOf(broken), null);
  const half = structuredClone(fields.summary.working!);
  (half.criteria.max_stress.steps[0] as unknown as { given: unknown }).given = "none";
  assert.deepEqual(Object.keys(workingOf({ summary: { ...fields.summary, working: half } } as Pick<Fields, "summary">)!.criteria), ["tsai_hill"]); // the chain that reads is kept
});

test("a value put into a formula is printed with the figures the package wrote and the page's own minus", () => {
  assert.equal(givenText(-0.0021751), "−0.0021751");
  assert.equal(givenText(162996), "162996");
  assert.equal(givenText(1.03206), "1.03206");
  assert.equal(givenText(64.0523), "64.0523");
  assert.equal(givenText(0), "0");
});

test("every formula of the example's working is one the typesetter reads", async () => {
  const katex = (await import("katex")).default;
  for (const chain of Object.values(fields.summary.working!.criteria)) {
    for (const step of chain.steps) {
      for (const row of step.given) katex.renderToString(row.symbol, { throwOnError: true, strict: "error" });
      for (const equation of step.equations) {
        if (equation.formula) katex.renderToString(equation.formula, { displayMode: true, throwOnError: true, strict: "error" });
        katex.renderToString(equation.substituted, { displayMode: true, throwOnError: true, strict: "error" });
      }
    }
  }
});
