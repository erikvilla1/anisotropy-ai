import { test } from "node:test";
import assert from "node:assert/strict";
import { CHAT_TOOLS, chatTool, toolNamed } from "../lib/chat-tools";

test("the chat's tools are one list, each with a title, a line and the words that open it", () => {
  assert.deepEqual(CHAT_TOOLS.map((t) => t.id), ["laminate", "coupon"]);
  for (const tool of CHAT_TOOLS) {
    assert.ok(tool.title.length > 0 && tool.detail.length > 0);
    assert.ok(tool.words.test(tool.title), `${tool.id}: its own title opens it`);
  }
  assert.equal(chatTool("coupon").title, "Coupon FEA"); // the workspace's one name (audit fea-screens-10)
  assert.throws(() => chatTool("stl" as never), /no chat tool stl/);
});

test("a typed message names a tool, or none", () => {
  assert.equal(toolNamed("I have a homework problem"), "laminate");
  assert.equal(toolNamed("ABD matrices of [0/90]s"), "laminate");
  assert.equal(toolNamed("Open-hole tension, AS4/8552, 10 kN"), "coupon");
  assert.equal(toolNamed("a plate with pressure"), "coupon");
  assert.equal(toolNamed("hello"), null);
});
