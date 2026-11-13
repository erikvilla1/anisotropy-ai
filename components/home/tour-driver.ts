"use client";

import { useEffect, useRef, type RefObject } from "react";
import { CLOCK_PER_SECOND as TOUR_CLOCK_PER_SECOND, STOPS as TOUR_STOPS } from "./tour-timeline";
import { HOLD_PX, crossed, decide, startsGesture, wheelPixels, type WheelMemory } from "./tour-stepper";

/** How fast the page is put on the stage over the last of the way, when one event asks for more than is left: window heights
 * a second, at constant speed. */
const PAGE_SCREENS_PER_SECOND = 2;
/** That move takes at least this long, so it is seen as a move and not a jump; under ARRIVE_JUMP_PX there is nothing to see. */
const PAGE_MIN_MS = 150;
const ARRIVE_JUMP_PX = 24;
/** For this long after the page has come onto the stage, scrolling that was already on its way is undone; and for this long
 * after any move, only a pause begins a new wheel gesture (tour-stepper.ts). */
const SETTLE_MS = 300;
/** A scroll this soon after a wheel, key or touch event is that gesture's own, and may be stopped on the stage. The scroll
 * bar, a link and a restored position come without one. */
const INPUT_MS = 600;
/** After a finger has scrolled the stage into place, the page may still be coasting on that throw for a while: for this
 * long, a scroll that takes the stage off the window's top edge again is the throw's and is undone, unless a new gesture
 * has let the stage go. */
const FLING_MS = 3000;
/** What a scrolling key asks for, as browsers answer it: about 40 px for an arrow, most of a window for the others. */
const ARROW_PX = 40;
const PAGE_KEY_SHARE = 0.85;
/** The page counts as at rest this long after its last scroll event. */
const REST_MS = 140;

export type TourFrame = {
  /** The tour's clock (tour-timeline.ts). */
  clock: number;
  /** At least half of the stage is in the window. */
  onStage: boolean;
};

/** Drives the stepped tour (ADR-0084 amendments 4 and 5). `tour` is the element that is one window tall in the page's flow.
 * The page scrolls to it and away from it as any page does. A scroll that brings the stage's top edge onto the window's is
 * stopped there, and the first step plays; from then, while `enabled`, a wheel gesture, a swipe or a scrolling key is taken
 * from the browser and answered with one move at constant speed, the clock from one stop to the next. Up from the first
 * step and down from the last are the browser's again, and so is the way back up from the calculator. `onFrame` is called whenever the clock moves or the stage comes on or
 * goes off; the element carries `data-stop` (where the clock stands) and `data-moving` (while a move plays). */
export type TourPlay = {
  /** Where the clock stands still, from 0. Default: the calculator tour's stops. */
  stops?: number[];
  /** The clock's speed while a step plays, in units a second. Default: the calculator tour's. */
  clockPerSecond?: number;
  /** Where in the window the element's top edge is while it holds the window, in pixels from the window's top. Default 0;
   * the product demo's box is held in the middle of the window (ADR-0094). */
  anchor?: () => number;
  /** A page that comes to rest within this many pixels of where the element holds the window, by a link, the scroll bar or a
   * restored position (no wheel, key or finger just before), is put there. Default 0: only a page already there counts. */
  settleWithin?: number;
};

export function useTourDriver(tour: RefObject<HTMLElement | null>, enabled: boolean, onFrame: (frame: TourFrame) => void, play?: TourPlay) {
  const latest = useRef(onFrame);
  latest.current = onFrame;
  const options = useRef(play);
  options.current = play;
  useEffect(() => {
    const element = tour.current;
    if (!enabled || !element) return;
    const STOPS = options.current?.stops ?? TOUR_STOPS;
    const CLOCK_PER_SECOND = options.current?.clockPerSecond ?? TOUR_CLOCK_PER_SECOND;
    const LAST_STOP = STOPS.length - 1;
    const anchor = () => options.current?.anchor?.() ?? 0;
    let stop = 0;
    let clock = 0;
    let moving = false; // a step is playing, or the page is being put on the stage
    let carrying = false; // the page is being put on the stage: the scroll events are this file's own
    let lastInput = -Infinity; // when a wheel, key or touch event last came
    let lastTouch = -Infinity; // when a finger last moved on the page
    let lastTop: number | null = null; // where the stage's top edge was at the last scroll event
    let holding = false; // the step that is playing began with the stage holding the window
    let held = false; // the stage held the window when the page last scrolled
    let clampUntil = 0;
    let quietUntil = 0;
    let frame = 0;
    let rest = 0;
    let onStage: boolean | null = null;
    let wheel: WheelMemory = null;
    let touch: { x: number; y: number; ours: boolean | null } | null = null;

    const place = () => ({ top: element.getBoundingClientRect().top - anchor(), viewport: window.innerHeight || 1 });
    /** Where the page must be scrolled to for the stage to stand where it holds the window. */
    const stageY = () => Math.round(window.scrollY + element.getBoundingClientRect().top - anchor());
    // "instant": the site's `scroll-behavior: smooth` would otherwise ease every one of these.
    const scrollPage = (top: number) => window.scrollTo({ top, behavior: "instant" });
    const align = () => {
      scrollPage(stageY());
      held = true;
    };
    const tell = () => {
      const { top, viewport } = place();
      onStage = Math.abs(top) < viewport / 2;
      latest.current({ clock, onStage });
    };
    const mark = () => {
      element.dataset.stop = String(stop);
      if (moving) element.dataset.moving = "true";
      else delete element.dataset.moving;
    };
    const jump = (to: number) => {
      stop = to;
      clock = STOPS[to];
      mark();
      tell();
    };

    /** Plays the clock from where it stands to a stop, at its one speed. */
    function play(to: number) {
      const from = clock;
      const target = STOPS[to];
      const duration = (Math.abs(target - from) / CLOCK_PER_SECOND) * 1000;
      let started = 0;
      moving = true;
      holding = Math.abs(place().top) <= HOLD_PX;
      mark();
      const tick = (now: number) => {
        if (!started) started = now;
        const share = duration > 0 ? Math.min(1, (now - started) / duration) : 1;
        // The stage holds the window for the whole step. A finger's scroll can still move the page after the last scroll
        // event has been answered (the browser applies it on another thread and reports no change), so the hold is
        // checked on every frame and not only when the page says it scrolled.
        if (holding && Math.abs(place().top) > HOLD_PX) align();
        // The last frame lands on the stop itself, not on a sum beside it: which step is up depends on it.
        clock = share < 1 ? from + (target - from) * share : target;
        if (share < 1) {
          tell();
          frame = window.requestAnimationFrame(tick);
          return;
        }
        frame = 0;
        stop = to;
        moving = holding = false;
        quietUntil = performance.now() + SETTLE_MS;
        mark();
        tell();
      };
      frame = window.requestAnimationFrame(tick);
    }

    /** Carries the page to a scroll position at constant speed, then calls `then`. */
    function carry(to: number, then: () => void) {
      const from = window.scrollY;
      const viewport = window.innerHeight || 1;
      const duration = Math.max(PAGE_MIN_MS, (Math.abs(to - from) / (viewport * PAGE_SCREENS_PER_SECOND)) * 1000);
      let started = 0;
      moving = carrying = true;
      mark();
      const tick = (now: number) => {
        if (!started) started = now;
        const share = Math.min(1, (now - started) / duration);
        scrollPage(from + (to - from) * share);
        if (share < 1) {
          frame = window.requestAnimationFrame(tick);
          return;
        }
        frame = 0;
        moving = carrying = false;
        quietUntil = performance.now() + SETTLE_MS;
        then();
      };
      frame = window.requestAnimationFrame(tick);
    }
    /** The stage has come onto the window's top edge: it holds the window, and if the tour has not started its first step
     * plays. What is left of the gesture that brought it begins no step. */
    const settle = () => {
      align();
      lastTop = 0;
      const now = performance.now();
      quietUntil = now + SETTLE_MS;
      clampUntil = now + (now - lastTouch < INPUT_MS ? FLING_MS : SETTLE_MS);
      if (stop === 0) play(1);
      else {
        mark();
        tell();
      }
    };
    /** One event asked for more than was left to the stage: the page goes the rest of the way and stops there. */
    const arrive = (by: number) => (Math.abs(by) <= ARRIVE_JUMP_PX ? settle() : carry(stageY(), settle));

    /** Asks the rules what a gesture means and plays it. True when the tour took it, so the browser must not scroll. */
    function act(direction: 1 | -1, fresh: boolean, reach: number): boolean {
      lastInput = performance.now();
      const action = decide(stop, moving, place(), direction, fresh, reach, LAST_STOP);
      if (action.kind === "native") {
        clampUntil = 0;
        return false;
      }
      if (action.kind === "step") play(action.to);
      else if (action.kind === "arrive") arrive(action.by);
      return true;
    }

    const onWheel = (event: WheelEvent) => {
      // Not a pinch (the browser reports it as a wheel with Ctrl), not a sideways scroll, not one a control already took.
      if (event.ctrlKey || event.defaultPrevented || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      const delta = wheelPixels(event.deltaY, event.deltaMode, window.innerHeight || 1);
      if (!delta) return;
      const fresh = startsGesture(wheel, event.timeStamp, delta, performance.now() >= quietUntil);
      wheel = { time: event.timeStamp, delta };
      if (act(delta > 0 ? 1 : -1, fresh, Math.abs(delta)) && event.cancelable) event.preventDefault();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) return;
      let direction: 1 | -1;
      const arrow = event.key === "ArrowDown" || event.key === "ArrowUp";
      if (event.key === "ArrowDown" || event.key === "PageDown") direction = 1;
      else if (event.key === "ArrowUp" || event.key === "PageUp") direction = -1;
      else if (event.key === " ") {
        // On a button or a link the space bar presses it.
        if (target?.closest("button, a[href], summary, [role='button']")) return;
        direction = event.shiftKey ? -1 : 1;
      } else return;
      if (act(direction, true, arrow ? ARROW_PX : (window.innerHeight || 1) * PAGE_KEY_SHARE)) event.preventDefault();
    };
    // A swipe: the first move says which way it goes, and the whole touch is then the tour's or the browser's.
    const onTouchStart = (event: TouchEvent) => {
      touch = event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY, ours: null } : null;
    };
    const onTouchMove = (event: TouchEvent) => {
      if (!touch || event.touches.length !== 1) {
        touch = null;
        return;
      }
      if (touch.ours === null) {
        const dx = touch.x - event.touches[0].clientX;
        const dy = touch.y - event.touches[0].clientY;
        if (!dx && !dy) return;
        // A finger moving up scrolls the page down. How far it will go is not known yet: away from the stage the touch is
        // the browser's, and the scroll it makes is stopped on the stage when it gets there (onScroll).
        touch.ours = Math.abs(dy) > Math.abs(dx) && event.cancelable ? act(dy > 0 ? 1 : -1, true, 0) : false;
      }
      lastInput = lastTouch = performance.now();
      if (touch.ours && event.cancelable) event.preventDefault();
    };
    const onTouchEnd = () => {
      touch = null;
    };

    const onRest = () => {
      if (moving) return;
      const off = Math.abs(place().top);
      // The page came to rest with the stage filling the window by some other way (a link to it, the scroll bar, a restored
      // position) and the tour has not started: its first step plays.
      if (off <= HOLD_PX) {
        if (stop === 0) play(1);
        return;
      }
      // Or it came to rest near there without a wheel, a key or a finger: it is put there, as a link to the stage means.
      if (off <= (options.current?.settleWithin ?? 0) && performance.now() - lastInput > INPUT_MS) carry(stageY(), settle);
    };
    const onScroll = () => {
      window.clearTimeout(rest);
      const { top, viewport } = place();
      const before = lastTop;
      lastTop = top;
      if (carrying) return;
      const off = Math.abs(top) > HOLD_PX;
      // While a step plays on a stage that held the window, and just after the page was carried there, nothing else may
      // scroll it: what does is scrolling that was already on its way, and it is undone.
      if (off && ((moving && holding) || performance.now() < clampUntil)) {
        align();
        return;
      }
      // A wheel, a key or a finger has just scrolled the stage's top edge down onto or across the window's: it stops there.
      if (!moving && before !== null && performance.now() - lastInput < INPUT_MS && crossed(before, top, viewport)) {
        settle();
        return;
      }
      held = !off;
      if (!moving) {
        // Out of sight, the tour is where a visitor coming back to it expects it: at its start from above, at its end from below.
        // (Read from the element's own edges: where it holds the window need not be the window's top.)
        const edges = element.getBoundingClientRect();
        if (edges.top >= viewport && stop !== 0) jump(0);
        else if (edges.bottom <= 0 && stop !== LAST_STOP) jump(LAST_STOP);
      }
      if (Math.abs(top) < viewport / 2 !== onStage) tell();
      rest = window.setTimeout(onRest, REST_MS);
    };
    const onResize = () => {
      if (held && !carrying) align();
      tell();
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", onTouchEnd);
    window.addEventListener("touchcancel", onTouchEnd);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    mark();
    tell();
    onScroll();
    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("touchcancel", onTouchEnd);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      window.clearTimeout(rest);
      if (frame) window.cancelAnimationFrame(frame);
      delete element.dataset.stop;
      delete element.dataset.moving;
    };
  }, [tour, enabled]);
}
