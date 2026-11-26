import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { qaNote, qaReady, readQa } from "../lib/plan-qa";
import { readFields, type Fields, type JobStatus } from "../lib/studio-api";
import { bannedIn } from "../lib/studio-copy";

// The QA step of a plan (ADR-0144): the result's own checks read into pass, warning or stop, with the evidence named, no number computed.
const read = (path: string) => JSON.parse(readFileSync(path, "utf8"));
const coupon = readFields(read("tests/fixtures/studio/fields.json"));
const plate = readFields(read("tests/fixtures/studio-plate/fields.json"));
const done = read("tests/fixtures/studio/job-done.json") as JobStatus;
const lines = (reading: ReturnType<typeof readQa>) => Object.fromEntries(reading.checks.map((c) => [c.id, `${c.verdict}: ${c.line}`]));
const withSummary = (fields: Fields, summary: Record<string, unknown>): Fields => ({ ...fields, summary: { ...fields.summary, ...summary } as Fields["summary"] });

test("the coupon's result: the reference solver agrees, the mesh study settled but for the answer's own R, the forces balance, read in the gauge section", () => {
  const qa = readQa(done, coupon);
  assert.deepEqual(lines(qa), {
    reference: "pass: Verified against reference solver: 57 of 57 values agree",
    mesh: "warning: Mesh study: the reaction, the gauge strain and the gauge ply stresses changed by less than 1 %; the first-ply failure R is still moving",
    equilibrium: "pass: Equilibrium: reaction 16220 N, out of balance by 1.599 × 10⁻⁹ N",
    place: "pass: Read in the gauge section, at least 6.25 mm from each tab line; an earlier failure at a grip edge, R = 1.013, is reported apart: stress there grows with a finer mesh",
  });
  assert.equal(qa.verdict, "warning");
  assert.equal(qa.headline, "Pass with a warning");
  assert.match(qaNote(qa), /^Pass with a warning\. Mesh study: /);
});

test("the plate's result: no second solver and no mesh study yet are warnings, the forces balance, and no answer means no place to read", () => {
  const qa = readQa({ result: null }, plate);
  assert.deepEqual(qa.checks.map((c) => [c.id, c.verdict]), [["reference", "warning"], ["mesh", "warning"], ["equilibrium", "pass"]]);
  assert.equal(qa.checks[0].line, "Reference solver: no second solver checked this result");
  assert.equal(qa.checks[1].line, "Mesh study: not studied, the study covers gripped in-plane coupons; plate is a later step");
  assert.match(qa.checks[2].line, /^Equilibrium: reaction 100 N, out of balance by /);
  assert.equal(qa.headline, "Pass with 2 warnings");
});

test("a result whose forces do not balance stops the plan; a slight imbalance is a warning", () => {
  const off = readQa(done, withSummary(coupon, { equilibrium_residual: 50 }));
  assert.equal(off.verdict, "stop");
  assert.equal(off.headline, "Stop: the result does not hold up");
  assert.equal(qaNote(off), "Stop: the result does not hold up. Equilibrium: reaction 16220 N, out of balance by 50 N.");
  assert.equal(readQa(done, withSummary(coupon, { equilibrium_residual: 1 })).checks.find((c) => c.id === "equilibrium")?.verdict, "warning");
  const unloaded = readQa(done, withSummary(coupon, { reaction: { ...coupon.summary.reaction, value: 0 } }));
  assert.equal(unloaded.checks.find((c) => c.id === "equilibrium")?.line, "Equilibrium: no reaction to balance the loads against");
});

test("a reference solver that differs, an earlier failure away from a grip and a plate read away from its held corners are each named", () => {
  const differs = readQa({ result: "50 of 57 recorded values agree with the reference" }, coupon);
  assert.equal(differs.checks[0].verdict, "warning");
  assert.equal(differs.checks[0].line, "Reference solver check: 50 of 57 values agree");
  const verdict = coupon.summary.verdict!;
  const elsewhere = readQa(done, withSummary(coupon, { verdict: { ...verdict, outside_earlier: { ...verdict.outside_earlier!, touches_grip: false, near_tab: false } } }));
  assert.equal(elsewhere.checks.find((c) => c.id === "place")?.verdict, "warning");
  // a plate read away from its held corners (ADR-0108 amendment 2), as a later package writes it
  const away = readQa(done, withSummary(coupon, { verdict: { ...verdict, basis: "away", outside_earlier: null }, held_corners: { stand_off: 5, fraction: 0.1, of: "width", corners: [], elements: 90, left_out: 10 } }));
  assert.equal(away.checks.find((c) => c.id === "place")?.line, "Read in the plate away from its held corners, at least 5 mm from each held corner");
  const corner = readQa(done, withSummary(coupon, { verdict: { ...verdict, basis: "whole", outside_earlier: null }, fpf: { ...coupon.summary.fpf, [verdict.earliest]: { ...coupon.summary.fpf[verdict.earliest], touches_grip: true } } }));
  assert.equal(corner.checks.find((c) => c.id === "place")?.verdict, "warning");
});

test("the QA waits for the run to end and the mesh study it wrote; no line names a tool or a vendor", () => {
  assert.equal(qaReady({ state: "running", outputs: { fields: "f" } }, coupon), false);
  assert.equal(qaReady({ state: "done", outputs: { fields: "f" } }, null), false);
  assert.equal(qaReady({ state: "done", outputs: { fields: "f", convergence: "c" } }, withSummary(coupon, { convergence: null })), false);
  assert.equal(qaReady({ state: "done", outputs: { fields: "f", convergence: "c" } }, coupon), true);
  assert.equal(qaReady({ state: "done", outputs: { fields: "f" } }, plate), true);
  for (const qa of [readQa(done, coupon), readQa({ result: null }, plate)]) {
    for (const c of qa.checks) assert.deepEqual(bannedIn(c.line), [], c.line);
    assert.deepEqual(bannedIn(qaNote(qa)), []);
  }
});
