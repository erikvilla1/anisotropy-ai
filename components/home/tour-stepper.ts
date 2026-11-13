/** The stepped tour's rules (ADR-0084 amendment 4): one scroll gesture plays one whole step. This file decides; it touches
 * no page. components/home/tour-driver.ts listens to the wheel, the keys and touches, asks here what a gesture means, and
 * plays the answer.
 *
 * The stage is one window tall and stands in the page's flow between the hero and the calculator. While its top edge is on
 * the window's top edge it holds the window: a gesture then plays the next step, or the one before, and the page does not
 * scroll. Away from the stage the page scrolls as usual, until a gesture moves towards a stage that touches the window:
 * that gesture brings the stage in. */

import { STOPS } from "./tour-timeline";

/** The last stop: the end of the last step. */
export const LAST_STOP = STOPS.length - 1;
/** The stage holds the window when its top edge is within this many pixels of the window's top edge. */
export const HOLD_PX = 1.5;

/** The wheel event before this one: when it came, in ms, and how far it asked to scroll, in pixels. */
export type WheelMemory = { time: number; delta: number } | null;
/** Wheel events further apart than this belong to different gestures. A trackpad swipe and its coasting send one every
 * frame or so; the notches of one flick of a wheel are closer than this too. */
export const WHEEL_GAP_MS = 200;
/** A wheel event at least this large that is not smaller than the one before is a new push: a wheel that is still being
 * turned, or a second swipe begun while the first still coasts. A coasting swipe only ever gets smaller. */
export const WHEEL_PUSH_PX = 50;

/** How far a wheel event asks to scroll, in pixels, whatever unit the browser reports it in. */
export function wheelPixels(delta: number, mode: number, viewport: number): number {
  return mode === 1 ? delta * 40 : mode === 2 ? delta * viewport : delta;
}

/** Whether a wheel event begins a new gesture, given the event before it. `push` is false for a moment after a step has
 * played, when only a pause may begin one, so the events still arriving from the swipe that played it cannot. */
export function startsGesture(last: WheelMemory, time: number, delta: number, push = true): boolean {
  if (!last) return true;
  if (time - last.time > WHEEL_GAP_MS) return true;
  if (Math.sign(delta) !== Math.sign(last.delta)) return true;
  return push && Math.abs(delta) >= WHEEL_PUSH_PX && Math.abs(delta) >= Math.abs(last.delta);
}

/** Where the stage is: its top edge measured from the window's top edge, and the window's height, in pixels. */
export type Place = { top: number; viewport: number };

export type Action =
  /** The browser scrolls the page as it would. */
  | { kind: "native" }
  /** Nothing happens and the page does not scroll: a step is playing, or this is the tail of the gesture that played one. */
  | { kind: "swallow" }
  /** The clock plays to this stop. */
  | { kind: "step"; to: number }
  /** The page is carried so that the stage fills the window. */
  | { kind: "enter" }
  /** The page is carried back up to the hero. */
  | { kind: "leave" };

/** What a gesture does. `stop` is where the clock stands, `moving` is true while a step plays or the page is being carried,
 * `direction` is 1 for down (on in the page) and -1 for up, and `fresh` is false for the later events of one wheel gesture. */
export function decide(stop: number, moving: boolean, place: Place, direction: 1 | -1, fresh: boolean): Action {
  if (moving) return { kind: "swallow" };
  if (Math.abs(place.top) <= HOLD_PX) {
    if (!fresh) return { kind: "swallow" };
    // Past the last step the stage lets go, and the page scrolls on to the calculator.
    if (direction > 0) return stop < LAST_STOP ? { kind: "step", to: stop + 1 } : { kind: "native" };
    return stop > 1 ? { kind: "step", to: stop - 1 } : { kind: "leave" };
  }
  // The stage touches the window from below and the gesture goes down, or from above and it goes up.
  if (direction > 0 && place.top > 0 && place.top <= place.viewport + 1) return { kind: "enter" };
  if (direction < 0 && place.top < 0 && place.top >= -place.viewport - 1) return { kind: "enter" };
  return { kind: "native" };
}
