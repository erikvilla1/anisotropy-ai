import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Fields } from "../lib/studio-api";
import { answerOf, extremeRows } from "../lib/studio-answer";

// The answer card reads what the package wrote (ADR-0085); the fixtures are the package's own output (`studio_tool.py fixtures`).
const fixture = (dir: string) => JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", dir, "fields.json"), "utf8")) as Fields;

test("a gripped coupon is answered in its gauge section, every number the package's, the clamped edge apart", () => {
  const fields = fixture("studio");
  const s = fields.summary;
  const a = answerOf(fields)!;
  assert.equal(a.basis, "gauge");
  assert.equal(a.basisWords, "the gauge section");
  assert.equal(a.earliest.criterion, s.verdict!.earliest);
  assert.equal(a.earliest.factor, s.fpf_gauge![s.verdict!.earliest].factor);
  assert.deepEqual(a.rows.map((r) => r.criterion), Object.entries(s.fpf_gauge!).sort(([, x], [, y]) => x.factor - y.factor).map(([c]) => c));
  for (const r of a.rows) {
    const f = s.fpf_gauge![r.criterion];
    assert.equal(r.fails, f.fails);
    assert.equal(r.applied, f.at_failure!.applied); // the package's R times the applied pull, not the page's
    assert.equal(r.reaction, f.at_failure!.reaction);
    assert.equal(r.tied.includes(r.ply), false);
  }
  assert.equal(a.control, "displacement");
  assert.equal(a.appliedUnit, "mm");
  assert.equal(a.forceUnit, "N");
  assert.ok(a.outside, "the public coupon's clamped edge fails earlier than its gauge section");
  assert.equal(a.outside!.touches_grip, true);
  assert.ok(a.outside!.factor < a.earliest.factor);
});

test("a coupon without a gauge section is answered over the whole model", () => {
  const fields = fixture("studio-bending");
  const a = answerOf(fields)!;
  assert.equal(a.basis, "whole");
  assert.equal(a.earliest.criterion, fields.summary.earliest);
  assert.equal(a.outside, null);
  assert.equal(a.rows.length, Object.keys(fields.summary.fpf).length);
});

test("an older job without the package's answer shows none rather than one the page would compute", () => {
  const fields = fixture("studio");
  const older = { ...fields, summary: { ...fields.summary, verdict: undefined } } as Fields;
  assert.equal(answerOf(older), null);
});

test("the largest ply stresses come one per component and sign, a sign never reached left out", () => {
  const set = fixture("studio").summary.ply_extremes!.overall;
  const rows = extremeRows(set);
  assert.deepEqual(rows.map((r) => r.key), ["S11-tension", "S11-compression", "S22-tension", "S22-compression", "S12-largest"]);
  assert.ok(rows[0].extreme.value > 0 && rows[1].extreme.value < 0);
  const none = extremeRows({ ...set, S22: { tension: set.S22.tension, compression: null } });
  assert.deepEqual(none.map((r) => r.key), ["S11-tension", "S11-compression", "S22-tension", "S12-largest"]);
});
