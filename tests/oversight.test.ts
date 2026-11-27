import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { mergeNewer, money, storyLines, toneOf, whoShort, type ActivityEvent, type PlanStory } from "../lib/oversight";

// The founders' AI activity page (ADR-0145): the readings the page draws from the API's answers, on the contract's own examples
// (tests/fixtures/oversight, which the API's tests hold its answers to).
const fixture = (name: string) => JSON.parse(readFileSync(new URL(`./fixtures/oversight/${name}`, import.meta.url), "utf-8"));
const events: ActivityEvent[] = fixture("activity.json").events;
const story: PlanStory = fixture("plan-story.json");

test("a call answered by a model outside the checked list is flagged, whatever its outcome", () => {
  const unchecked = events.find((e) => e.checked === false)!;
  assert.equal(toneOf(unchecked), "bad");
  assert.equal(toneOf({ ...unchecked, outcome: "kept" }), "bad");
  assert.equal(toneOf({ outcome: "kept", checked: true }), "good");
  assert.equal(toneOf({ outcome: "set aside", checked: true }), "bad");
  assert.equal(toneOf({ outcome: "question", checked: null }), "warn");
  assert.equal(toneOf({ outcome: "something new", checked: null }), "quiet");
});

test("a refresh puts the newer events on top, each once", () => {
  const shown = events.slice(2);
  const merged = mergeNewer(shown, events.slice(0, 3));
  assert.deepEqual(merged, events);
  assert.deepEqual(mergeNewer(events, []), events);
});

test("money and names print short", () => {
  assert.equal(money(null), "–");
  assert.equal(money(0.041), "$0.041");
  assert.equal(money(2.11), "$2.11");
  assert.equal(whoShort("founder@example.com"), "founder");
  assert.equal(whoShort("customer 3fa91c"), "customer 3fa91c");
  assert.equal(whoShort("robot"), "robot");
});

test("a plan's story reads in the order it happened, with what the checks turned back", () => {
  const lines = storyLines(story);
  const heads = lines.map((l) => l.head);
  assert.deepEqual(heads.slice(0, 4), ["Sentence read", "Answer 1 turned back by the checks", "Model call: plan_steps", "Model call: plan_steps"]);
  assert.equal(lines[0].detail, "set the width to 30 mm and run it");
  assert.match(lines[1].detail ?? "", /^step 1: in is not the unit/);
  assert.ok(heads.includes("Approved by founder") && heads.includes("New version 4, made by assistant"));
  assert.deepEqual(heads.filter((h) => /^(Geometry|Solver|QA):/.test(h)), ["Geometry: Set the width to 30 mm", "Solver: Check the setup before the run",
    "Solver: Run the analysis", "QA: Read the result's own checks"]);
  assert.equal(heads.at(-1), "Run on the solver pool: running");
  assert.equal(lines.at(-1)?.detail?.startsWith("2 of 6 stages"), true);
});

test("a customer's story shows the steps by tool, and a plan not approved shows no steps", () => {
  const hidden: PlanStory = { ...story, words_shown: false, ask: "a customer's words, not shown", steps: story.steps.map((s) => ({ ...s, line: null, note: null })) };
  assert.ok(storyLines(hidden).some((l) => l.head === "Solver: run"));
  const waiting: PlanStory = { ...story, state: "proposed", approved_at: null, version: null, job: null };
  const heads = storyLines(waiting).map((l) => l.head);
  assert.equal(heads.at(-1), "Waiting for the engineer's approval");
  assert.ok(!heads.some((h) => h.startsWith("Solver:")));
  const unchecked: PlanStory = { ...story, calls: [{ ...story.calls[0], checked: false, model: "claude-stand-in-1" }] };
  const call = storyLines(unchecked).find((l) => l.head.startsWith("Model call"))!;
  assert.equal(call.tone, "bad");
  assert.match(call.detail ?? "", /claude-stand-in-1, a model outside the checked list/);
});
