import test from "node:test";
import assert from "node:assert/strict";
import { CHASE, clockAfter, stopAt, stopUnder } from "../components/home/scroll-steps";
import { DEMO_CLOCK_PER_SECOND, DEMO_STOPS } from "../components/home/product-demo-timeline";

// The rule of a stage that follows the page's scroll (ADR-0095 amendment 10): which beat the scroll asks for, and how the
// clock plays to it.

test("where the scroll stands says which beat is wanted", () => {
  // Before the stage holds the window nothing is wanted; a little before it, within the lead, the first beat already is.
  assert.equal(stopAt(-400, 360, 4, 58), 0);
  assert.equal(stopAt(-59, 360, 4, 58), 0);
  assert.equal(stopAt(-58, 360, 4, 58), 1);
  assert.equal(stopAt(0, 360, 4, 58), 1);
  // One more for every zone gone, and never more than there are beats.
  assert.equal(stopAt(359, 360, 4), 1);
  assert.equal(stopAt(360, 360, 4), 2);
  assert.equal(stopAt(2 * 360 + 1, 360, 4), 3);
  assert.equal(stopAt(3 * 360, 360, 4), 4);
  assert.equal(stopAt(40 * 360, 360, 4), 4);
  // A stage without a zone asks for nothing.
  assert.equal(stopAt(500, 0, 4), 0);
});

test("the beat the scroll stands in plays at its own pace; beats left behind are run through; back up it is unplayed fast", () => {
  const stops = DEMO_STOPS;
  const pace = DEMO_CLOCK_PER_SECOND;
  // From a stop to the next: the clock's own pace, to the hundredth of a second, and it ends on the stop itself.
  assert.ok(Math.abs(clockAfter(stops[1], stops[2], 1, pace, stops) - (stops[1] + pace)) < 1e-12);
  assert.equal(clockAfter(stops[2] - 1e-6, stops[2], 1, pace, stops), stops[2]);
  // With the target two stops on, the beat the clock is in is run through, faster the more there is left.
  const far = clockAfter(stops[0], stops[4], 0.05, pace, stops) - stops[0];
  const near = clockAfter(stops[0], stops[2], 0.05, pace, stops) - stops[0];
  assert.ok(far > near && near > 0.05 * pace * 1.5, `${far} ${near}`);
  // Run from the start to the end: three beats run through, then the last at its own pace.
  let clock: number = stops[0], seconds = 0;
  while (clock < stops[3] && seconds < 60) { clock = clockAfter(clock, stops[4], 1 / 60, pace, stops); seconds += 1 / 60; }
  assert.ok(seconds < 4, `three beats were run through in ${seconds} s`);
  const before = clock;
  clock = clockAfter(clock, stops[4], 1, pace, stops);
  assert.ok(Math.abs(clock - before - pace) < 1e-9, "the last beat plays at its own pace");
  // Backwards: at least CHASE.back times the pace, and never past the target.
  const back = stops[3] - clockAfter(stops[3], stops[2], 0.1, pace, stops);
  assert.ok(back >= CHASE.back * pace * 0.1 - 1e-12);
  assert.equal(clockAfter(stops[1] + 1e-6, stops[1], 1, pace, stops), stops[1]);
  let down: number = stops[4], took = 0;
  while (down > stops[0] && took < 60) { down = clockAfter(down, stops[0], 1 / 60, pace, stops); took += 1 / 60; }
  assert.ok(took < 3.5, `the whole demo is unplayed in ${took} s`);
  // Standing on its target, or with no time gone, the clock does not move.
  assert.equal(clockAfter(stops[2], stops[2], 1, pace, stops), stops[2]);
  assert.equal(clockAfter(stops[1], stops[3], 0, pace, stops), stops[1]);
});

test("the stage carries the stop the clock stands on or has last passed", () => {
  const stops = DEMO_STOPS;
  assert.equal(stopUnder(stops[0], stops), 0);
  assert.equal(stopUnder((stops[0] + stops[1]) / 2, stops), 0);
  assert.equal(stopUnder(stops[1], stops), 1);
  assert.equal(stopUnder((stops[3] + stops[4]) / 2, stops), 3);
  assert.equal(stopUnder(stops[4], stops), 4);
});
