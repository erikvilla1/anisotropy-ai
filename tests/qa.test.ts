import assert from "node:assert/strict";
import test from "node:test";
import { QA_UNRECORDED, qaItems, qaLine, readQARecord, type QACheck } from "../lib/qa";
import { BANNED_TERMS } from "../lib/studio-copy";

const check = (verdict: QACheck["verdict"], label = "Units consistent"): QACheck =>
  ({ layer: "data", check: "DATA-UNITS", version: 1, verdict, label, message: "fine", evidence: {}, basis: "ADR-0002" });
const record = (verdict: string, checks: QACheck[]) => readQARecord({ job_id: "j", verdict, counts: {}, checks });

test("a QA record is read only when it is one, and its counts come from its checks (ADR-0137)", () => {
  const read = record("needs engineer", [check("pass"), check("warn"), check("pass")]);
  assert.deepEqual(read?.counts, { pass: 2, warn: 1, block: 0 });
  assert.equal(readQARecord(null), null);
  assert.equal(readQARecord({ job_id: "j", verdict: "fine", checks: [] }), null);
  assert.equal(record("ready", [{ ...check("pass"), verdict: "ok" as QACheck["verdict"] }]), null);
});

test("the run's line says what to do with the result, with counts for the founders and without for customers", () => {
  const ready = record("ready", [check("pass"), check("pass")]);
  assert.deepEqual(qaLine(ready), { line: "All 2 quality checks passed", tone: "ok" });
  assert.deepEqual(qaLine(ready, true), { line: "Every quality check passed", tone: "ok" });
  const notes = record("needs engineer", [check("pass"), check("warn")]);
  assert.deepEqual(qaLine(notes), { line: "1 of 2 quality checks passed; 1 needs an engineer's review", tone: "warn" });
  assert.equal(qaLine(notes, true)?.line, "Quality checks passed with notes for an engineer to review");
  const blocked = record("blocked", [check("pass"), check("block"), check("block")]);
  assert.deepEqual(qaLine(blocked), { line: "2 quality checks block this result; 1 of 3 passed", tone: "block" });
  assert.equal(qaLine(record("unchecked", [])), null);
  assert.equal(qaLine(null), null);
  assert.ok(!BANNED_TERMS.some((term) => term.pattern.test(QA_UNRECORDED)));
  for (const r of [ready, notes, blocked]) {
    for (const brief of [true, false]) {
      const line = qaLine(r, brief)!.line;
      assert.ok(!BANNED_TERMS.some((term) => term.pattern.test(line)), line);  // the customer's words (ADR-0091)
    }
  }
});

test("the checks that need attention come first, in the run's order within each verdict", () => {
  const r = record("blocked", [check("pass", "A"), check("warn", "B"), check("block", "C"), check("warn", "D")]);
  assert.deepEqual(qaItems(r).map((i) => i.label), ["C", "B", "D", "A"]);
  assert.deepEqual(qaItems(null), []);
  // the product's view gives each check's verdict in words, not its message, which may hold counts (verificationOf's rule)
  assert.deepEqual(qaItems(r, true).map((i) => i.message), ["stops this result", "for an engineer to review", "for an engineer to review", "passed"]);
  assert.deepEqual(qaItems(r).map((i) => i.message), ["fine", "fine", "fine", "fine"]);
});
