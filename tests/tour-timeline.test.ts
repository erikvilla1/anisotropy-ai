import test from "node:test";
import assert from "node:assert/strict";
import { HOLD_PX, LAST_STOP, WHEEL_GAP_MS, crossed, decide, startsGesture, wheelPixels, type WheelMemory } from "../components/home/tour-stepper";
import { CLOCK_PER_SECOND, STEPS, STOPS, TOTAL, finalView, layupScript, viewAt } from "../components/home/tour-timeline";
import { DEFAULT_LAYUP } from "../lib/home-calculator";
import { expandLayup } from "../lib/layup";

// The tour's clock and the stepper's rules (components/home/tour-timeline.ts, tour-stepper.ts): what is on screen at a moment
// of the clock, and what a scroll gesture does. No laminate quantity is involved.

const parsed = expandLayup(DEFAULT_LAYUP).layup!;
const script = layupScript(DEFAULT_LAYUP, parsed.angles.length, parsed.symmetric);
const at = (t: number) => viewAt(t, script, parsed.angles.length, "25000");
const range = (id: string) => STEPS.find((step) => step.id === id)!;

test("a listed ply starts when the slash or bracket that ends its angle is typed; the mirrored plies follow the s, in order", () => {
  assert.deepEqual(script.starts.slice(0, 4), [4, 8, 10, 13]); // "[45/", "[45/-45/", "[45/-45/0/", "[45/-45/0/90]"
  assert.equal(script.starts.length, 8);
  for (let i = 1; i < script.starts.length; i++) assert.ok(script.starts[i] > script.starts[i - 1]);
  assert.ok(script.starts[4] > DEFAULT_LAYUP.length);
  // A notation the plain reading does not follow lays every ply after the typing.
  const repeated = expandLayup("[±45]2").layup!;
  const other = layupScript("[±45]2", repeated.angles.length, repeated.symmetric);
  assert.equal(other.starts.length, repeated.angles.length);
  assert.ok(other.starts.every((start) => start > "[±45]2".length));
});

test("the steps follow one another from 0 and fill the tour's length; the clock stops before the first and at the end of each", () => {
  assert.equal(STEPS[0].start, 0);
  for (let i = 1; i < STEPS.length; i++) assert.equal(STEPS[i].start, STEPS[i - 1].end);
  assert.equal(STEPS[STEPS.length - 1].end, TOTAL);
  assert.deepEqual(STEPS.map((step) => step.id), ["material", "layup", "engine", "loads", "handover"]);
  assert.deepEqual(STOPS, [0, ...STEPS.map((step) => step.end)]);
  assert.equal(LAST_STOP, 5);
  // At the clock's one speed no step takes less than 1.5 s or more than 5 s (ADR-0084 amendment 5).
  const seconds = STEPS.map((step) => (step.end - step.start) / CLOCK_PER_SECOND);
  assert.ok(Math.min(...seconds) >= 1.5 && Math.max(...seconds) <= 5, seconds.join(", "));
});

test("a step only ever adds: typing, laid plies and the engine's stages never go back as the clock runs on", () => {
  let before = at(range("layup").at(0.14));
  for (let t = range("layup").at(0.14); t <= TOTAL; t += 0.005) {
    const now = at(t);
    assert.ok(now.layupChars >= before.layupChars);
    assert.ok(now.laid >= before.laid - 1e-9);
    assert.ok(now.engine >= before.engine);
    assert.ok(now.loadChars >= before.loadChars);
    assert.ok(now.step >= before.step);
    before = now;
  }
});

test("each stop shows its step complete, and the next step's words come up as its move starts", () => {
  // Before the first step: the material's words, nothing picked, the whole stack standing closed.
  const start = at(STOPS[0]);
  assert.deepEqual([start.step, start.picked, start.constants, start.laid, start.explode, start.azimuth], [0, false, 0, 8, 0, -24]);
  const material = at(STOPS[1]);
  assert.deepEqual([material.step, material.picked, material.constants, material.layupChars, material.laid], [0, true, 1, 0, 8]);
  assert.ok(material.explode > 0.5);
  // The layup's move: its words are up at once, the standing stack goes, then the typing lays it again.
  const opening = at(STOPS[1] + 0.001);
  assert.deepEqual([opening.step, opening.layupChars], [1, 0]);
  assert.equal(at(range("layup").at(0.15)).laid, 0);
  const typing = at(range("layup").at(0.45));
  assert.equal(typing.step, 1);
  assert.ok(typing.layupChars > 0 && typing.layupChars < DEFAULT_LAYUP.length);
  assert.ok(typing.laid > 0 && typing.laid < 8);
  const laid = at(STOPS[2]);
  assert.deepEqual([laid.step, laid.layupChars, laid.laid, laid.thickness, laid.engine], [1, DEFAULT_LAYUP.length, 8, true, 0]);
  assert.deepEqual([0.1, 0.3, 0.6, 0.9].map((u) => at(range("engine").at(u)).engine), [0, 1, 2, 3]);
  const answered = at(STOPS[3]);
  assert.deepEqual([answered.step, answered.engine, answered.explode, answered.loaded], [2, 3, 0, false]);
  const typed = at(range("loads").at(0.4));
  assert.deepEqual([typed.step, typed.loaded, typed.mark], [3, false, false]);
  assert.ok(typed.loadChars > 0 && typed.loadChars < 5);
  const loaded = at(STOPS[4]);
  assert.deepEqual([loaded.step, loaded.loadChars, loaded.loaded, loaded.mark, loaded.explode], [3, 5, true, true, 0.6]);
  const end = at(STOPS[5]);
  assert.deepEqual([end.step, end.explode, end.mark, end.laid, end.azimuth], [4, 0, false, 8, 0]);
  const whole = finalView(script, 8, "25000");
  assert.deepEqual([whole.layupChars, whole.laid, whole.engine, whole.loadChars, whole.loaded], [DEFAULT_LAYUP.length, 8, 3, 5, true]);
});

// The wheel: a swipe on a trackpad as the browser reports it, one event a frame, growing while the fingers move and shrinking
// while it coasts; and a wheel's notches.
function gestures(events: [time: number, delta: number][], quietUntil = -Infinity): number[] {
  let last: WheelMemory = null;
  const starts: number[] = [];
  for (const [time, delta] of events) {
    if (startsGesture(last, time, delta, time >= quietUntil)) starts.push(time);
    last = { time, delta };
  }
  return starts;
}

test("one swipe is one gesture, its coasting included; a pause, a turn back or a new push begins another", () => {
  const swipe = (from: number): [number, number][] =>
    [4, 18, 46, 80, 96, 90, 78, 66, 55, 46, 38, 31, 26, 21, 17, 14, 11, 9, 7, 6, 5, 4, 3, 2, 2, 1, 1, 1].map((delta, index) => [from + index * 16, delta]);
  // The first event begins it. While the fingers still speed up (46, 80, 96) the events count as pushes, which the driver
  // ignores because the step is playing; the coasting begins nothing.
  assert.deepEqual(gestures(swipe(1000)), [1000, 1048, 1064]);
  assert.deepEqual(gestures(swipe(1000).slice(5)), [1080]);
  // A second swipe after a pause, and one that turns back at once.
  assert.deepEqual(gestures([...swipe(1000).slice(5), ...swipe(1000 + 27 * 16 + WHEEL_GAP_MS + 1).slice(0, 1)]).length, 2);
  assert.deepEqual(gestures([[0, 30], [16, 24], [32, -3], [48, -9]]), [0, 32]);
  // A wheel: the notches of one flick are one gesture after the first, a notch after a pause is another, and a wheel still
  // being turned when a step has just ended begins the next only once the moment after the step has passed.
  assert.deepEqual(gestures([[0, 100], [40, 100], [90, 100]], 200), [0]);
  assert.deepEqual(gestures([[0, 100], [40, 100], [400, 100]], 200), [0, 400]);
  assert.deepEqual(gestures([[0, 100], [150, 100], [300, 100]], 200), [0, 300]);
  // The browser's other units: lines and pages.
  assert.deepEqual([wheelPixels(3, 1, 900), wheelPixels(1, 2, 900), wheelPixels(-53, 0, 900)], [120, 900, -53]);
});

test("on the stage one gesture plays one step, and nothing is taken while a step plays or from the tail of the gesture that played it", () => {
  const onStage = { top: 0, viewport: 900 };
  for (let stop = 1; stop < LAST_STOP; stop++) assert.deepEqual(decide(stop, false, onStage, 1, true), { kind: "step", to: stop + 1 });
  for (let stop = 2; stop <= LAST_STOP; stop++) assert.deepEqual(decide(stop, false, onStage, -1, true), { kind: "step", to: stop - 1 });
  for (const direction of [1, -1] as const) {
    assert.deepEqual(decide(2, true, onStage, direction, true), { kind: "swallow" });
    assert.deepEqual(decide(2, false, onStage, direction, false), { kind: "swallow" });
    assert.deepEqual(decide(LAST_STOP, false, onStage, direction, false), { kind: "swallow" });
  }
  // The stage holds the window within a pixel and a half.
  assert.deepEqual(decide(2, false, { top: HOLD_PX, viewport: 900 }, 1, true), { kind: "step", to: 3 });
});

test("the ends of the tour: up from the first step and down from the last let the page scroll on", () => {
  const onStage = { top: 0, viewport: 900 };
  assert.deepEqual(decide(1, false, onStage, -1, true), { kind: "native" });
  assert.deepEqual(decide(LAST_STOP, false, onStage, 1, true), { kind: "native" });
  // Reached by a link before the first step has played: down plays it, up is the page's.
  assert.deepEqual(decide(0, false, onStage, 1, true), { kind: "step", to: 1 });
  assert.deepEqual(decide(0, false, onStage, -1, true), { kind: "native" });
});

test("away from the stage the page scrolls as usual; on the way down, the event that would pass the stage is stopped on it", () => {
  const viewport = 900;
  // From the hero, whose foot is the window's foot: the page scrolls, whatever the gesture.
  assert.deepEqual(decide(0, false, { top: 900, viewport }, 1, true, 100), { kind: "native" });
  assert.deepEqual(decide(0, false, { top: 420, viewport }, 1, false, 96), { kind: "native" });
  assert.deepEqual(decide(0, false, { top: 420, viewport }, -1, true, 100), { kind: "native" });
  // The event that asks for what is left, or more, is stopped on the stage; one that asks for less is the page's.
  assert.deepEqual(decide(0, false, { top: 80, viewport }, 1, false, 100), { kind: "arrive", by: 80 });
  assert.deepEqual(decide(0, false, { top: 100, viewport }, 1, true, 100), { kind: "arrive", by: 100 });
  assert.deepEqual(decide(3, false, { top: 30, viewport }, 1, true, 40), { kind: "arrive", by: 30 });
  assert.deepEqual(decide(0, false, { top: 101, viewport }, 1, true, 100), { kind: "native" });
  // How far a touch will go is not known when it starts: it is the page's, and its scroll is stopped when it gets there.
  assert.deepEqual(decide(0, false, { top: 80, viewport }, 1, true), { kind: "native" });
  // On the way up from the calculator the stage is passed like any section, both ways.
  assert.deepEqual(decide(LAST_STOP, false, { top: -100, viewport }, -1, true, 240), { kind: "native" });
  assert.deepEqual(decide(LAST_STOP, false, { top: -100, viewport }, 1, false, 240), { kind: "native" });
  // The stage out of sight: the page's, both ways. While the page is being put on the stage: nothing.
  for (const top of [940, 2400, -940, -5000]) for (const direction of [1, -1] as const) assert.deepEqual(decide(0, false, { top, viewport }, direction, true, 100), { kind: "native" });
  assert.deepEqual(decide(0, true, { top: 420, viewport }, 1, true, 500), { kind: "swallow" });
});

test("a scroll is stopped on the stage only when it brings the stage's top edge down onto the window's from where it showed", () => {
  const viewport = 900;
  assert.equal(crossed(60, 0, viewport), true);
  assert.equal(crossed(60, -45, viewport), true); // it overshot: the page is put back on the stage
  assert.equal(crossed(900, 1, viewport), true);
  assert.equal(crossed(60, 12, viewport), false); // not there yet
  assert.equal(crossed(0, -40, viewport), false); // leaving the stage downwards
  assert.equal(crossed(-60, 0, viewport), false); // coming back up from the calculator
  assert.equal(crossed(-60, 30, viewport), false);
  assert.equal(crossed(2400, 0, viewport), false); // a jump from out of sight
  assert.equal(crossed(300, -900, viewport), false); // a jump right past it
});
