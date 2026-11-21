import { test } from "node:test";
import assert from "node:assert/strict";
import { readIntent, readRepair, routeStart, saysMore, sectionOf, TARGET_TITLES } from "../lib/work-intent";
import { HANDOFF_KEY, putHandoff, takeHandoff } from "../lib/handoff";
import { ASKED_KINDS, COUPON_HREF, FEA_KINDS, WORKSPACES, workspace } from "../lib/workspaces";

// ADR-0124: what a message asks to work on, read by fixed words the same way on the start screen and in every section's chat

test("the workspace has three sections, FEA, CAD and Laminate, in that order, and FEA is set up for a coupon test or a wing", () => {
  assert.deepEqual(WORKSPACES.map((w) => w.title), ["FEA", "CAD", "Laminate"]);
  assert.deepEqual(WORKSPACES.map((w) => w.href), ["/workspace/fea", "/workspace/cad", "/workspace/laminate"]);
  assert.equal(workspace("cad").planned, true);
  assert.deepEqual(FEA_KINDS.map((k) => k.id), ["coupon", "wing", "repair"]); // the wing and the repair on their own pages under FEA (ADR-0118 amendment 1, ADR-0135)
  assert.deepEqual(FEA_KINDS.map((k) => k.href), [undefined, "/workspace/wing", "/workspace/repair"]);
  assert.deepEqual(ASKED_KINDS, ["coupon", "wing"]); // a model is offered only the kinds whose page it has been taught
  assert.equal(COUPON_HREF, "/workspace/fea?for=coupon");
});

test("a request to start work is read as one, the founder's own examples first", () => {
  const cases: [string, string][] = [
    ["you know what I want to start a wing analysis", "wing"],
    ["I want to test some coupons", "coupon"],
    ["coupon testing", "coupon"],
    ["analyze a wing", "wing"],
    ["Laminate", "laminate"],
    ["CAD please", "cad"],
    ["can you set up an open-hole coupon?", "coupon"],
    ["ABD matrix of a [0/90]s laminate", "laminate"],
    ["let's do a hand calc", "laminate"],
    ["run it in FEA", "fea"],
    ["unnotched tension, IM7/8552, [45/0/-45/90]s", "coupon"],
    ["I have a step file of a bracket", "cad"],
  ];
  for (const [text, target] of cases) assert.deepEqual(readIntent(text), { target, start: true }, text);
});

test("a question names its subject but starts nothing, and a message that names nothing is no intent", () => {
  for (const [text, target] of [["What is a coupon test?", "coupon"], ["How do I test a coupon?", "coupon"], ["what is the ABD matrix?", "laminate"],
    ["why does a wing spar carry bending?", "wing"], ["Is FEA better than a hand calc for this", "laminate"]] as const) {
    assert.deepEqual(readIntent(text), { target, start: false }, text);
  }
  for (const text of ["", "   ", "hello", "What is a mesh convergence study?", "make the laminate [0/90]s", "finer mesh", "10 kN"]) assert.equal(readIntent(text), null, text);
});

test("each target is worked in one section, and has one name", () => {
  assert.deepEqual(["coupon", "wing", "fea", "laminate", "cad"].map((t) => sectionOf(t as never)), ["fea", "fea", "fea", "laminate", "cad"]);
  assert.equal(TARGET_TITLES.coupon, "Coupon test");
});

test("a message is carried only when it says more than the kind of work", () => {
  assert.equal(saysMore("I want to test some coupons"), false);
  assert.equal(saysMore("test a coupon at 10 kN"), true);
  assert.equal(saysMore("ABD of [0/90]s"), true);
  assert.equal(saysMore("an IM7/8552 open-hole coupon", () => true), true); // the receiving chat's own patterns read rows in it
});

test("a message carried to another page is read once, and nothing is left when there is nothing to carry", () => {
  const store = new Map<string, string>();
  const session = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k) };
  assert.equal(putHandoff(session, { setUp: "  I want to test some coupons ", prompt: "" }), true);
  assert.deepEqual(JSON.parse(store.get(HANDOFF_KEY)!), { prompt: "", setUp: "I want to test some coupons" });
  assert.deepEqual(takeHandoff(session), { prompt: "", setUp: "I want to test some coupons" });
  assert.deepEqual(takeHandoff(session), { prompt: "", setUp: "" }); // once
  putHandoff(session, {});
  assert.equal(store.size, 0);
  store.set(HANDOFF_KEY, "{not json");
  assert.deepEqual(takeHandoff(session), { prompt: "", setUp: "" });
  assert.deepEqual(takeHandoff(null), { prompt: "", setUp: "" });
  putHandoff(session, { prompt: "x".repeat(3000) });
  assert.equal(takeHandoff(session).prompt.length, 2000);
});

test("words a coupon's own chat uses about its setup ask for no other section", () => {
  for (const text of ["show the sketch", "make the laminate [0/90]s", "finer mesh", "check", "run", "what is ply 4's stress?", "coupon"]) {
    const read = readIntent(text);
    assert.ok(!read || read.target === "coupon" || !read.start, text);
  }
});

test("a patch repair is asked for by its own words, first: a statement starts it, a question only names it (ADR-0135)", () => {
  for (const text of ["step patch repair", "I need to analyse a bonded patch repair", "a bonded repair over an open hole", "set up a scarf repair", "repair",
    "Patch repair", "scraf repair", "can you start a stepped patch?", "a step-lap joint in IM7/8552", "external patch on a 25 mm hole"]) {
    assert.equal(readRepair(text), "start", text);
    assert.deepEqual(routeStart(text), { route: "set-up", kind: "repair" }, text);
  }
  for (const text of ["what is a scarf repair?", "how is a bonded repair analysed?", "why does a stepped patch peel at its edge"]) {
    assert.equal(readRepair(text), "about", text);
    assert.equal(routeStart(text).route, "general", text);
  }
  // words that are not a repair's: a coupon, a question about repairing something else, a patch of a mesh
  for (const text of ["I want to test some coupons", "an open-hole coupon", "how do I repair a failed run?", "refine the mesh in a patch near the hole", ""]) assert.equal(readRepair(text), null, text);
  assert.deepEqual(routeStart("an open-hole coupon"), { route: "set-up", kind: "coupon" });
});
