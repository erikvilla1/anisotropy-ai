import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { ALL_ROUTES, banks, faults, KINDS, PAGES, pageGap, STYLES, talk, type Bank, type Question } from "./assistant-questions/harness";

// The question banks of the assistant (ADR-0121), played against the page's own readers: who answers each question, and what the page
// says when no model reads it. A question of the results is answered from the stored results the browser tests use; a question a model
// reads is held here only to falling back honestly, and to the real model by `scripts/assistant-live.py`.

const all = banks();
const live = all.filter((bank) => !bank.waiting);
const MODEL_FALLBACK = new Set(["patterns", "unread"]);

/** Everything wrong with one question: its route with a model and without, and the page's answer. */
function problems(question: Question): string[] {
  const out: string[] = [];
  const withModel = talk(question, true);
  if (withModel.route !== question.route) out.push(`with a model it goes to ${withModel.route}, expected ${question.route}`);
  const without = talk(question, false);
  const expected = question.offline ?? (question.route === "model" ? null : question.route);
  if (expected !== null && without.route !== expected) out.push(`with no model it goes to ${without.route}, expected ${expected}`);
  if (expected === null && !MODEL_FALLBACK.has(without.route)) out.push(`with no model it goes to ${without.route}, not to the patterns or “Not a question I can read yet”`);
  // a question a model reads is held to its fallback only when the bank says what the fallback must hold, or for the rules every answer keeps
  out.push(...faults(question, without.said));
  return out;
}

test("every bank is well formed: its kinds, styles and pages are known, it names its records, and the files it watches exist", () => {
  assert.ok(all.length >= 10, "the banks are in tests/assistant-questions/");
  for (const bank of all) {
    assert.ok(bank.feature && bank.title && bank.records.length, `${bank.feature}: a feature, a title and its records`);
    for (const path of bank.watches) assert.ok(existsSync(path), `${bank.feature} watches ${path}, which does not exist`);
    for (const q of bank.questions) {
      const where = `${bank.feature}: “${q.ask}”`;
      assert.ok((KINDS as readonly string[]).includes(q.kind), `${where}: kind ${q.kind}`);
      assert.ok((STYLES as readonly string[]).includes(q.style), `${where}: style ${q.style}`);
      assert.ok((PAGES as readonly string[]).includes(q.page), `${where}: page ${q.page}`);
      assert.ok((ALL_ROUTES as readonly string[]).includes(q.route), `${where}: route ${q.route}`);
      if (q.offline) assert.ok((ALL_ROUTES as readonly string[]).includes(q.offline), `${where}: offline route ${q.offline}`);
      if (q.route === "model" && !bank.waiting) assert.ok(q.live || q.answer || q.offline || q.mcp, `${where}: a question a model reads says what the model should make of it`);
    }
  }
});

test("each bank asks enough, in enough ways: ten questions or more, two kinds, three styles and at least one typo", () => {
  for (const bank of live) {
    const kinds = new Set(bank.questions.map((q) => q.kind)), styles = new Set(bank.questions.map((q) => q.style));
    assert.ok(bank.questions.length >= 10, `${bank.feature}: ${bank.questions.length} questions, ten at least`);
    assert.ok(kinds.size >= 2, `${bank.feature}: kinds ${[...kinds].join(", ")}, two at least`);
    assert.ok(styles.size >= 3, `${bank.feature}: styles ${[...styles].join(", ")}, three at least`);
    assert.ok(styles.has("typo"), `${bank.feature}: no question typed with a typo`);
  }
});

test("every way the chat answers is asked at least once: a new route brings its questions", () => {
  const taken = new Set(live.flatMap((bank) => bank.questions.flatMap((q) => [q.route, ...(q.offline ? [q.offline] : [])])));
  const missing = ALL_ROUTES.filter((route) => !taken.has(route));
  assert.deepEqual(missing, [], `routes no question takes: ${missing.join(", ")}`);
});

for (const bank of live) {
  test(`${bank.title} (${bank.feature}): every question is answered as its bank says`, () => {
    const failed: string[] = [], closed: string[] = [];
    for (const question of bank.questions) {
      const found = problems(question);
      if (pageGap(question) && !found.length) closed.push(`“${question.ask}”: the gap “${question.gap}” is closed; take the mark off`);
      if (!pageGap(question) && found.length) failed.push(`“${question.ask}” (${question.page}): ${found.join("; ")}`);
    }
    assert.deepEqual([...failed, ...closed], [], `\n${[...failed, ...closed].join("\n")}`);
  });
}

test("a bank written before its feature says why it waits, and asks what a model must make of each question", () => {
  for (const bank of all.filter((b: Bank) => b.waiting)) {
    assert.ok(bank.waiting!.length > 20, `${bank.feature}: why it waits`);
    for (const q of bank.questions) assert.ok(q.live?.judge || q.live?.request || q.live?.proposals, `${bank.feature}: “${q.ask}” says what a good answer holds`);
  }
});
