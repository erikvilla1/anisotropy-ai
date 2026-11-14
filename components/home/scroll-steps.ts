/** The rule of a stage that follows the page's scroll (ADR-0095 amendment 10): the page scrolls freely past a stage that
 * stays in the window, and where the scroll stands says which beat is wanted; the clock then plays to that beat's end on
 * its own, forwards or backwards. This file decides; it touches no page. components/home/scroll-stage.ts reads the page,
 * asks here, and plays. */

/** The stop the scroll asks for, 0 to `beats`: 0 before the stage has come to hold the window, then one more for every
 * zone of scroll gone since it did. `offset` is how far the page has scrolled past the place where the stage begins to
 * hold the window, in pixels (negative before it); `zone` is the scroll a beat takes; `lead` is how far before that place
 * the first beat already starts, so a scroll that stops a little short of the stage still gets the first beat. */
export function stopAt(offset: number, zone: number, beats: number, lead = 0): number {
  if (!(zone > 0) || offset < -lead) return 0;
  return Math.min(beats, 1 + Math.floor(Math.max(0, offset) / zone));
}

/** How the clock runs after the scroll. Times are seconds at the clock's own pace. */
export const CHASE = {
  /** A beat that the scroll has already left behind is run through: what remains is covered in about this long, however
   * much it is. */
  through: 1,
  /** On the way back up a beat is unplayed at this many times its own pace at least, */
  back: 2.5,
  /** and whatever remains is covered in about this long. */
  backWithin: 0.8,
};

/** The clock after `seconds` more. `stops` are the clock's values where it rests, in order; `target` is the one the scroll
 * asks for; `perSecond` is the clock's own pace. Forwards, the beat that ends on the target plays at its own pace, so a
 * visitor who stays sees it as it was made; any beat before it, which the scroll has left behind, is run through fast.
 * Backwards it runs fast all the way. The clock never passes its target. */
export function clockAfter(clock: number, target: number, seconds: number, perSecond: number, stops: readonly number[]): number {
  if (clock === target || !(seconds > 0)) return clock;
  if (target > clock) {
    // The stop that ends the beat the clock is in.
    const next = stops.find((stop) => stop > clock + 1e-9) ?? target;
    const left = (target - clock) / perSecond;
    const pace = next >= target ? 1 : Math.max(1, left / CHASE.through);
    return Math.min(target, clock + pace * perSecond * seconds);
  }
  const left = (clock - target) / perSecond;
  const pace = Math.max(CHASE.back, left / CHASE.backWithin);
  return Math.max(target, clock - pace * perSecond * seconds);
}

/** The stop the clock stands on or has last passed on its way up: what the stage carries as `data-stop`. */
export function stopUnder(clock: number, stops: readonly number[]): number {
  let under = 0;
  for (let index = 0; index < stops.length; index++) if (stops[index] <= clock + 1e-9) under = index;
  return under;
}
