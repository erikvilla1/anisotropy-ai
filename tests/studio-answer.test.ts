import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Fields } from "../lib/studio-api";
import { answerOf, answerStat, extremeRows } from "../lib/studio-answer";

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
  assert.deepEqual(a.appliedNow, { applied: s.applied.value, reaction: s.reaction.value }); // the state as applied, beside the state at failure
  assert.equal(a.appliedUnit, "mm");
  assert.equal(a.forceUnit, "N");
  assert.ok(a.outside, "the public coupon's clamped edge fails earlier than its gauge section");
  assert.equal(a.outside!.touches_grip, true);
  assert.equal(a.outside!.near_tab, false);
  assert.ok(a.outside!.factor < a.earliest.factor);
  // where the gauge section is read (ADR-0108), as the package wrote it: a quarter of the 25 mm width from each tab line
  assert.deepEqual(s.gauge_reading, { stand_off: 6.25, fraction: 0.25, of: "width", tab_lines: [56, 194], elements: 130, left_out: 10 });
  assert.equal(fields.mesh.gauge_elements!.length, 130);
  for (const r of a.rows) assert.ok(fields.mesh.gauge_elements!.includes(r.element) && Math.min(r.xy[1] - 56, 194 - r.xy[1]) >= 6.25);
});

test("a coupon without a gauge section is answered over the whole model", () => {
  const fields = fixture("studio-bending");
  const a = answerOf(fields)!;
  assert.equal(a.basis, "whole");
  assert.equal(a.earliest.criterion, fields.summary.earliest);
  assert.equal(a.outside, null);
  assert.equal(a.rows.length, Object.keys(fields.summary.fpf).length);
});

test("a plate clamped at one end is answered away from its held corners, the clamped corner's earlier failure said apart (ADR-0108 amendment 2)", () => {
  const print = (value: number) => String(Number(value.toPrecision(4)));
  const fields = fixture("studio-plate-clamped");
  const s = fields.summary;
  const a = answerOf(fields)!;
  assert.equal(a.basis, "away");
  assert.equal(a.basisWords, "the plate away from its held corners");
  assert.equal(a.earliest.factor, s.fpf_away![s.verdict!.earliest].factor);
  assert.deepEqual(a.rows.map((r) => r.criterion), Object.entries(s.fpf_away!).sort(([, x], [, y]) => x.factor - y.factor).map(([c]) => c));
  // where the plate is read, as the package wrote it: a quarter of the 25 mm width from the clamped end's two corners
  assert.deepEqual(s.held_corners, { stand_off: 6.25, fraction: 0.25, of: "width", corners: [[0, 0], [25, 0]], elements: 158, left_out: 2 });
  for (const r of a.rows) assert.ok(fields.mesh.away_elements!.includes(r.element) && Math.min(...s.held_corners!.corners.map(([x, y]) => Math.hypot(r.xy[0] - x, r.xy[1] - y))) >= 6.25);
  assert.ok(a.outside && a.outside.near_corner && !a.outside.touches_grip && a.outside.factor < a.earliest.factor);
  const stat = answerStat(fields, print)!;
  assert.equal(stat.factor, print(s.verdict!.factor));
  assert.equal(stat.facts, `${a.earliest.name}, ply ${a.earliest.ply} · ${a.earliest.angle}°, the plate away from its held corners`);
  assert.equal(stat.outside, `Beside a held corner R = ${print(a.outside!.factor)}, reported apart: stress there grows with a finer mesh.`);
});

test("an older job without the package's answer shows none rather than one the page would compute", () => {
  const fields = fixture("studio");
  const older = { ...fields, summary: { ...fields.summary, verdict: undefined } } as Fields;
  assert.equal(answerOf(older), null);
});

test("the chat's results card leads with the page's answer, the earlier failure at the grip said apart", () => {
  const print = (value: number) => String(Number(value.toPrecision(4)));
  const fields = fixture("studio");
  const a = answerOf(fields)!;
  const stat = answerStat(fields, print)!;
  assert.equal(stat.verdict, a.earliest.fails ? "Fails" : "Holds");
  assert.equal(stat.fails, fields.summary.verdict!.fails);
  assert.equal(stat.factor, print(fields.summary.verdict!.factor)); // the gauge section's factor, not the whole model's lower one
  assert.notEqual(stat.factor, print(fields.summary.fpf[fields.summary.earliest!].factor));
  assert.equal(stat.facts, `${a.earliest.name}, ply ${a.earliest.ply} · ${a.earliest.angle}°, the gauge section`);
  assert.equal(stat.outside, `At a grip edge R = ${print(a.outside!.factor)}, reported apart: stress there grows with a finer mesh.`);
  const whole = answerStat(fixture("studio-bending"), print)!;
  assert.match(whole.facts, /, the whole model$/);
  assert.equal(whole.outside, null);
  const older = { ...fields, summary: { ...fields.summary, verdict: undefined } } as Fields;
  assert.equal(answerStat(older, print), null); // the card then keeps the whole model's first failure, as before
});

test("the largest ply stresses come one per component and sign, a sign never reached left out", () => {
  const set = fixture("studio").summary.ply_extremes!.overall;
  const rows = extremeRows(set);
  assert.deepEqual(rows.map((r) => r.key), ["S11-tension", "S11-compression", "S22-tension", "S22-compression", "S12-largest"]);
  assert.ok(rows[0].extreme.value > 0 && rows[1].extreme.value < 0);
  const none = extremeRows({ ...set, S22: { tension: set.S22.tension, compression: null } });
  assert.deepEqual(none.map((r) => r.key), ["S11-tension", "S11-compression", "S22-tension", "S12-largest"]);
});
