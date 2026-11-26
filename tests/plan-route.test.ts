import { test } from "node:test";
import assert from "node:assert/strict";
import { asksPlan, routeMessage, type ChatState } from "../lib/chat-route";
import { exampleForm, PLATE_TEST } from "../lib/studio-form";
import { emptyPlate } from "../lib/studio-plate";

// Which sentences go to the planner (ADR-0144): a change and a run or an answer in one sentence, where a model reads and the project is
// kept on the server; a single edit stays with the page's own readers, and a question is never a plan.
const coupon = exampleForm("2026-11-26");
const plate = { ...coupon, test: PLATE_TEST };
const state = (over: Partial<ChatState> = {}): ChatState => ({
  form: plate, readOnly: false, results: false, facts: false, api: true, modelReads: true, onPlate: true, plates: true, plate: emptyPlate(), here: [],
  ready: true, step: null, about: null, thread: null, sections: true, kept: true, ...over,
});

test("a change with a run or an answer is a plan; a change alone, a run alone or a question is not", () => {
  for (const text of ["clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds", "clamp teh bottom edge and run the analysis",
    "hold Edge-Left, push Edge-Right with 500 N, solve"]) assert.equal(asksPlan(text, plate), true, text);
  for (const text of ["set the width to 30 mm and run it", "make it [0/90]2s and run it", "use 4 mm elements then run", "pull it with 2 kN and tell me if it holds",
    "change the layup to [0/90]2s, run it and tell me which ply fails first", "can you set the width to 30 mm and solve it?", "make it 3 mm thick and see if it fails",
    "please set the length to 200 and run the model"]) assert.equal(asksPlan(text, coupon), true, text);
  for (const text of ["fix the left edge", "set width 30 mm", "run it", "run the analysis", "what happens if I clamp the bottom edge?",
    "does it hold if I pull it with 2 kN?", "is it ready to run?", "tell me about first ply failure", "which ply fails first?"]) assert.equal(asksPlan(text, coupon), false, text);
  assert.equal(asksPlan("fix the left edge", plate), false);
});

test("the planner takes the sentence only where a model reads, the project is kept, and the page is not read-only", () => {
  const ask = "clamp the bottom edge, pull the top edge with 2 kN and tell me if it holds";
  assert.deepEqual(routeMessage(ask, state()), { route: "plan", reply: false });
  assert.equal(routeMessage(ask, state({ kept: false })).route, "plate-edit");
  assert.equal(routeMessage(ask, state({ kept: undefined })).route, "plate-edit");
  assert.equal(routeMessage(ask, state({ modelReads: false, onPlate: false })).route, "plate-edit");
  assert.equal(routeMessage(ask, state({ api: false })).route, "plate-edit");
  assert.equal(routeMessage(ask, state({ readOnly: true })).route, "read-only");
  assert.equal(routeMessage("fix the left edge", state()).route, "plate-edit");
  assert.equal(routeMessage("set the width to 30 mm and run it", state({ form: coupon, onPlate: false })).route, "plan");
  assert.equal(routeMessage("set the width to 30 mm and run it", state({ form: coupon, onPlate: false, kept: false })).route, "model");
});

test("a reply to the plan's question is planned again with it; a question, a new plan or a drop is not a reply", () => {
  assert.deepEqual(routeMessage("the bottom one", state({ planAsks: true })), { route: "plan", reply: true });
  assert.deepEqual(routeMessage("Edge-Bottom", state({ planAsks: true })), { route: "plan", reply: true });
  assert.deepEqual(routeMessage("clamp the top edge and run it", state({ planAsks: true })), { route: "plan", reply: false });
  assert.notEqual(routeMessage("what is an encastre?", state({ planAsks: true })).route, "plan");
  assert.notEqual(routeMessage("never mind", state({ planAsks: true })).route, "plan");
  assert.notEqual(routeMessage("the bottom one", state({ planAsks: false })).route, "plan");
  assert.equal(routeMessage("start over", state({ planAsks: true })).route, "start-over");
});
