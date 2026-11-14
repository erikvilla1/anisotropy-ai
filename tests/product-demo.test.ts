import test from "node:test";
import assert from "node:assert/strict";
import { BEAT_COPY, everyLine, resultLines, wingFacts, wingParts } from "../components/home/product-demo-copy";
import { BEATS, BEAT_IDS, DEMO_CLOCK_PER_SECOND, DEMO_STOPS, DEMO_TOTAL, MOVE, POSES, finalView, poseAt, sceneAt, viewAt } from "../components/home/product-demo-timeline";
import { decide } from "../components/home/tour-stepper";
import { demoWing, wingColour, wingProblems, type DemoWing } from "../lib/demo-wing";
import { bannedIn, DOWNLOAD_LABELS, RUN_STEPS } from "../lib/studio-copy";

// The product demo of the home page (ADR-0095, ADR-0098): the example wing it shows, its clock and its words.

const counts = { facts: 5, parts: demoWing.parts.length, stages: RUN_STEPS.length, files: 3 };
const at = (t: number) => viewAt(t, counts);

test("the wing's record is whole and agrees with itself", () => {
  assert.deepEqual(wingProblems(demoWing), []);
  // The example: one side of a tapered, swept wing, 7 ft long, two skins over two spars and nine ribs, in the library's IM7 / 8552.
  assert.equal(demoWing.wing.span, 2133.6);
  assert.equal(demoWing.wing.library, "im7-8552");
  assert.deepEqual(demoWing.parts.map((part) => part.id), ["upper-skin", "lower-skin", "front-spar", "rear-spar", "ribs"]);
  assert.equal(demoWing.wing.ribs.length, 9);
  assert.deepEqual([demoWing.wing.root_chord, demoWing.wing.tip_chord, demoWing.wing.sweep], [450, 225, 400]);
  // Every layup is symmetric about its middle.
  for (const part of demoWing.parts) assert.deepEqual([...part.angles].reverse(), part.angles, part.name);
  // A broken record is noticed.
  const torn: DemoWing = { ...demoWing, mesh: { ...demoWing.mesh, part: demoWing.mesh.part.slice(1) } };
  assert.ok(wingProblems(torn).length > 0);
  const moved: DemoWing = { ...demoWing, parts: demoWing.parts.map((part, index) => (index === 1 ? { ...part, first: part.first + 1 } : part)) };
  assert.ok(wingProblems(moved).length > 0);
});

test("the wing's analysis is recorded whole: one value a face from a named solver, and the root holds what was applied", () => {
  const { field, solve, load } = demoWing;
  assert.ok(field && solve && load, "the analysis is not recorded: run scripts/demo-wing.py --solve");
  assert.equal(field.values.length, demoWing.mesh.quads.length);
  assert.ok(Math.abs(solve.reaction - load.total) <= 0.01 * load.total, `${solve.reaction} N at the root for ${load.total} N applied`);
  assert.ok(solve.tip_deflection > 0 && solve.tip_deflection < 0.15 * demoWing.wing.span, `the tip rises ${solve.tip_deflection} mm`);
  assert.match(solve.recorded, /^\d{4}-\d{2}-\d{2}$/);
  assert.ok(solve.solver.length > 0);
  // The page's colours: the rainbow over the recorded range, blue at its smallest value and red at its largest.
  assert.deepEqual(wingColour(field, field.min), [0, 0, 1]);
  assert.deepEqual(wingColour(field, field.max), [1, 0, 0]);
  assert.deepEqual(wingColour(field, (field.min + field.max) / 2), [0, 1, 0]);
  // A record whose stated range is not its values' is noticed.
  assert.ok(wingProblems({ ...demoWing, field: { ...field, max: field.max * 2 } }).length > 0);
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
  assert.deepEqual([start.beat, start.words, start.facts, start.parts, start.stage, start.files], [0, 0, 0, 0, 0, 0]);
  const [, whole, apart, analysed, closed] = DEMO_STOPS.map(at);
  assert.deepEqual([whole.beat, whole.words, whole.facts, whole.parts], [0, 1, counts.facts, 0]);
  assert.deepEqual([apart.beat, apart.words, apart.parts], [1, 1, counts.parts]);
  assert.deepEqual([analysed.beat, analysed.words, analysed.stage, analysed.legend, analysed.result], [2, 1, counts.stages, true, true]);
  assert.deepEqual([closed.beat, closed.words, closed.files], [3, 1, counts.files]);
  assert.deepEqual(finalView(counts), closed);
  let before = at(0);
  for (let t = 0; t <= DEMO_TOTAL; t += 0.004) {
    const now = at(t);
    for (const key of ["beat", "facts", "parts", "stage", "files"] as const) assert.ok(now[key] >= before[key], `${key} at ${t}`);
    for (const key of ["legend", "result"] as const) assert.ok(!before[key] || now[key], `${key} at ${t}`);
    before = now;
  }
  // The stages light one after another, and the result follows the last of them.
  const firstResult = [...Array(1000).keys()].map((i) => (i / 1000) * DEMO_TOTAL).find((t) => at(t).result)!;
  assert.equal(at(firstResult).stage, counts.stages);
});

test("the wing: whole, then apart and meshed, then coloured, then whole again with its colours", () => {
  assert.equal(sceneAt(0).presence, 0);
  const [, whole, apart, analysed, closed] = DEMO_STOPS.map(sceneAt);
  assert.deepEqual([whole.presence, whole.mesh, whole.field], [1, 0, 0]);
  assert.deepEqual([apart.mesh, apart.field], [1, 0]);
  assert.deepEqual([analysed.mesh, analysed.field], [1, 1]);
  assert.deepEqual([closed.presence, closed.field], [1, 1]);
  // Whole, apart, apart, whole: the lead's order of 2026-11-14.
  assert.deepEqual(BEAT_IDS.map((id) => POSES[id].explode), [0, 1, 1, 0]);
  BEATS.forEach((beat) => assert.deepEqual(poseAt(beat.end), POSES[beat.id]));
  // The move is over well before its beat ends, and the pose never jumps.
  BEATS.forEach((beat) => assert.deepEqual(poseAt(beat.start + MOVE), POSES[beat.id]));
  let last = poseAt(0);
  for (let t = 0; t <= DEMO_TOTAL; t += 0.002) {
    const now = poseAt(t);
    assert.ok(Math.abs(now.x - last.x) < 0.01 && Math.abs(now.yaw - last.yaw) < 0.04 && Math.abs(now.explode - last.explode) < 0.03, `a jump at ${t}`);
    last = now;
  }
  // Scale's arrangement: in the middle first, then at one side, then at the other, then in the middle again.
  assert.deepEqual(BEAT_IDS.map((id) => Math.sign(Math.round((POSES[id].x - 0.5) * 10))), [0, 1, -1, 0]);
});

test("every word the demo shows is fit for the product's view, and its numbers are the record's", () => {
  const lines = [...everyLine(demoWing, "IM7 / 8552"), ...RUN_STEPS.map((step) => step.label), ...DOWNLOAD_LABELS.slice(0, 3).map(([, label]) => label)];
  for (const line of lines) assert.deepEqual(bannedIn(line), [], line);
  assert.equal(BEAT_COPY.report.text, "Less time on repetitive setup and documentation, more time optimizing the structure.");
  assert.deepEqual(wingFacts(demoWing, "IM7 / 8552").map(([name]) => name), ["PART", "SPAN", "CHORD", "MATERIAL", "STRUCTURE"]);
  assert.deepEqual(wingFacts(demoWing, "IM7 / 8552")[1], ["SPAN", "2.13 m"]);
  assert.deepEqual(wingFacts(demoWing, "IM7 / 8552")[2], ["CHORD", "0.45 m at the root, 0.23 m at the tip"]);
  assert.deepEqual(wingFacts(demoWing, "IM7 / 8552")[4], ["STRUCTURE", "2 skins, 2 spars, 9 ribs"]);
  assert.deepEqual(wingParts(demoWing)[0], ["UPPER SKIN", "[45/0/-45/90]s"]);
  const result = resultLines(demoWing);
  assert.ok(result, "the analysis is not recorded");
  const governing = demoWing.parts.find((part) => part.id === demoWing.solve!.governing.part)!;
  assert.ok(result.first.includes(governing.name.toLowerCase()), result.first);
  assert.ok(result.when.includes(`${demoWing.load!.total} ${demoWing.load!.unit}`) && result.when.includes(`${Math.round(demoWing.solve!.tip_deflection)} mm`), result.when);
  // A wing without its analysis says nothing about one.
  assert.equal(resultLines({ ...demoWing, field: undefined, displacement: undefined, solve: undefined, load: undefined }), null);
});

test("the stepper plays a caller's own stops: past the demo's fourth the page scrolls on", () => {
  const onStage = { top: 0, viewport: 900 };
  const last = DEMO_STOPS.length - 1;
  assert.deepEqual(decide(3, false, onStage, 1, true, 0, last), { kind: "step", to: 4 });
  assert.deepEqual(decide(last, false, onStage, 1, true, 0, last), { kind: "native" });
  assert.deepEqual(decide(1, false, onStage, -1, true, 0, last), { kind: "native" });
});
