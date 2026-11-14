import test from "node:test";
import assert from "node:assert/strict";
import { BEAT_COPY, everyLine, resultLines, summaryCells } from "../components/home/product-demo-copy";
import { BEATS, BEAT_IDS, DEMO_CLOCK_PER_SECOND, DEMO_STOPS, DEMO_TOTAL, MOVE, POSES, finalView, layupScript, poseAt, sceneAt, viewAt } from "../components/home/product-demo-timeline";
import { decide } from "../components/home/tour-stepper";
import { demoRun, demoScale, runProblems, standardName } from "../lib/demo-run";
import { bannedIn, DOWNLOAD_LABELS, RUN_STEPS } from "../lib/studio-copy";

// The product demo of the home page (ADR-0095): the recorded run it replays, its clock and its words.

const script = layupScript(demoRun.coupon.layup, demoRun.coupon.angles.length);
const counts = { cells: 5, stages: RUN_STEPS.length, files: 3 };
const at = (t: number) => viewAt(t, script, counts);

test("the recorded run is whole and agrees with itself", () => {
  assert.deepEqual(runProblems(demoRun), []);
  // The public example under ASTM D3039: eight plies of IM7 / 8552, symmetric, pulled 1 mm.
  assert.equal(demoRun.coupon.library, "im7-8552");
  assert.equal(standardName(demoRun), "ASTM D3039");
  assert.deepEqual(demoRun.coupon.angles, [45, 0, -45, 90, 90, -45, 0, 45]);
  assert.equal(demoRun.rows, "tests/fixtures/studio-standards/values.json");
  // A broken record is noticed.
  const short = { ...demoRun, field: { ...demoRun.field, plies: demoRun.field.plies.slice(1) } };
  assert.ok(runProblems(short).length > 0);
  const moved = { ...demoRun, field: { ...demoRun.field, max: demoRun.field.max + 1 } };
  assert.ok(runProblems(moved).length > 0);
  // The scale is the workspace's, diverging about zero because the stress along the fibres changes sign between plies.
  const scale = demoScale(demoRun);
  assert.equal(scale.kind, "diverging");
  assert.equal(scale.max, -scale.min);
  assert.deepEqual(scale.ends, [demoRun.field.min, demoRun.field.max]);
});

test("the demo's four beats abut, and at the clock's one speed a beat takes between 2 and 6 s and the model's move about 1.4 s", () => {
  assert.deepEqual(BEATS.map((beat) => beat.id), [...BEAT_IDS]);
  assert.equal(BEATS[0].start, 0);
  for (let i = 1; i < BEATS.length; i++) assert.equal(BEATS[i].start, BEATS[i - 1].end);
  assert.deepEqual(DEMO_STOPS, [0, ...BEATS.map((beat) => beat.end)]);
  assert.equal(DEMO_TOTAL, DEMO_STOPS[DEMO_STOPS.length - 1]);
  const seconds = BEATS.map((beat) => (beat.end - beat.start) / DEMO_CLOCK_PER_SECOND);
  assert.ok(Math.min(...seconds) >= 2 && Math.max(...seconds) <= 6, seconds.join(", "));
  const move = MOVE / DEMO_CLOCK_PER_SECOND;
  assert.ok(move >= 1.2 && move <= 1.6, String(move));
});

test("each stop shows its beat finished, and nothing a beat has shown goes back as the clock runs on", () => {
  const start = at(0);
  assert.deepEqual([start.beat, start.words, start.picked, start.standard, start.layupChars, start.cells, start.stage, start.files], [0, 0, false, false, 0, 0, 0, 0]);
  const [, described, built, analysed, reported] = DEMO_STOPS.map(at);
  assert.deepEqual([described.beat, described.words, described.picked, described.standard, described.layupChars], [0, 1, true, true, demoRun.coupon.layup.length]);
  assert.deepEqual([built.beat, built.words, built.cells], [1, 1, counts.cells]);
  assert.deepEqual([analysed.beat, analysed.words, analysed.stage, analysed.legend, analysed.result], [2, 1, counts.stages, true, true]);
  assert.deepEqual([reported.beat, reported.words, reported.files], [3, 1, counts.files]);
  assert.deepEqual(finalView(script, counts), reported);
  let before = at(0);
  for (let t = 0; t <= DEMO_TOTAL; t += 0.004) {
    const now = at(t);
    for (const key of ["beat", "layupChars", "cells", "stage", "files"] as const) assert.ok(now[key] >= before[key], `${key} at ${t}`);
    for (const key of ["picked", "standard", "legend", "result"] as const) assert.ok(!before[key] || now[key], `${key} at ${t}`);
    before = now;
  }
  // The stages light one after another, and the result follows the last of them.
  const firstResult = [...Array(1000).keys()].map((i) => (i / 1000) * DEMO_TOTAL).find((t) => at(t).result)!;
  assert.equal(at(firstResult).stage, counts.stages);
});

test("the model: laid with the layup, meshed in the second beat, coloured in the third, and at each stop in that beat's pose", () => {
  assert.equal(sceneAt(0, script).presence, 0);
  const [, described, built, analysed, reported] = DEMO_STOPS.map((t) => sceneAt(t, script));
  assert.deepEqual([described.presence, described.laid, described.mesh, described.field], [1, demoRun.coupon.angles.length, 0, 0]);
  assert.deepEqual([built.mesh, built.field], [1, 0]);
  assert.deepEqual([analysed.mesh, analysed.field], [1, 1]);
  assert.deepEqual([reported.laid, reported.field], [demoRun.coupon.angles.length, 1]);
  BEATS.forEach((beat) => assert.deepEqual(poseAt(beat.end), POSES[beat.id]));
  // The move is over well before its beat ends, and the pose never jumps.
  BEATS.forEach((beat) => assert.deepEqual(poseAt(beat.start + MOVE), POSES[beat.id]));
  let last = poseAt(0);
  for (let t = 0; t <= DEMO_TOTAL; t += 0.002) {
    const now = poseAt(t);
    assert.ok(Math.abs(now.x - last.x) < 0.01 && Math.abs(now.yaw - last.yaw) < 0.03 && Math.abs(now.explode - last.explode) < 0.03, `a jump at ${t}`);
    last = now;
  }
  // Scale's arrangement: in the middle first, then at one side, then at the other, then in the middle again.
  assert.deepEqual(BEAT_IDS.map((id) => Math.sign(Math.round((POSES[id].x - 0.5) * 10))), [0, 1, -1, 0]);
});

test("every word the demo shows is fit for the product's view, and its numbers are the recorded run's", () => {
  const lines = [...everyLine(demoRun, "IM7 / 8552"), ...RUN_STEPS.map((step) => step.label), ...DOWNLOAD_LABELS.slice(0, 3).map(([, label]) => label)];
  for (const line of lines) assert.deepEqual(bannedIn(line), [], line);
  assert.equal(BEAT_COPY.report.text, "Less time on repetitive setup and documentation, more time optimizing the structure.");
  const first = demoRun.summary.first_failure;
  const result = resultLines(demoRun);
  assert.equal(result.first, `First ply to fail: ply ${first.ply} (${first.angle}°), in ${first.mode} ${first.place}.`);
  assert.ok(result.when.includes(`${(demoRun.summary.reaction / 1000).toFixed(1)} kN`) && result.when.includes(`${first.applied.toFixed(2)} ${first.applied_unit}`), result.when);
  assert.equal(result.when.startsWith("It holds"), !first.fails);
  assert.deepEqual(summaryCells(demoRun, "IM7 / 8552").map(([name]) => name), ["TEST", "MATERIAL", "LAYUP", "SIZE", "MESH"]);
  assert.ok(summaryCells(demoRun, "IM7 / 8552")[4][1].startsWith(String(demoRun.summary.elements)));
  // The page does not print what the record is (the lead's choice, ADR-0095 amendment 6); the record still says it.
  assert.equal(demoRun.what, "A recorded run of the public IM7 / 8552 tension example");
});

test("the stepper plays a caller's own stops: past the demo's fourth the page scrolls on", () => {
  const onStage = { top: 0, viewport: 900 };
  const last = DEMO_STOPS.length - 1;
  assert.deepEqual(decide(3, false, onStage, 1, true, 0, last), { kind: "step", to: 4 });
  assert.deepEqual(decide(last, false, onStage, 1, true, 0, last), { kind: "native" });
  assert.deepEqual(decide(1, false, onStage, -1, true, 0, last), { kind: "native" });
});
