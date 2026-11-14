"use client";

import { useEffect, useRef, type RefObject } from "react";
import { clockAfter, stopAt, stopUnder } from "./scroll-steps";

export type ScrollStageOptions = {
  /** The clock's values where it rests, in order, the first of them its start. */
  stops: readonly number[];
  /** The clock's own pace, in its units a second. */
  clockPerSecond: number;
  /** The scroll a beat takes, as a share of the stage's height. The stage's section is that much taller for every beat
   * (the stylesheet reads the same number), so the stage holds the window for exactly the beats' zones. */
  zone: number;
  /** How far before the stage holds the window the first beat already starts, as a share of the stage's height. */
  lead: number;
};

/** A stage that follows the page's scroll (ADR-0095 amendment 10; the rule is components/home/scroll-steps.ts). The stage is
 * `position: sticky` in a taller section (the stylesheet's doing), so the page scrolls past it freely while it stays in
 * the window. This takes no wheel, touch or key, and never moves or holds the page: it reads where the page stands, at
 * every scroll and resize, and plays the clock to the beat that place asks for, forwards or backwards, reporting each
 * frame to `onFrame`. A fast scroll runs through the beats it leaves behind; scrolling back up unplays them.
 *
 * The stage carries `data-stop`, the stop the clock stands on or last passed, and `data-moving` while the clock runs, as
 * the stylesheet and the tests read them. While the stage is out of the window the clock goes straight to where the
 * scroll asks, so nothing is drawn for no one and a page opened further down starts with the demo finished. */
export function useScrollStage(stage: RefObject<HTMLElement | null>, enabled: boolean, onFrame: (state: { clock: number }) => void, options: ScrollStageOptions) {
  const report = useRef(onFrame);
  useEffect(() => {
    report.current = onFrame;
  });
  const { stops, clockPerSecond, zone, lead } = options;
  useEffect(() => {
    const element = stage.current;
    const section = element?.parentElement;
    if (!enabled || !element || !section) return;
    const beats = stops.length - 1;
    let clock = stops[0];
    let target = stops[0];
    let frame = 0;
    let last = 0;
    const mark = () => {
      element.dataset.stop = String(stopUnder(clock, stops));
      if (clock === target) delete element.dataset.moving;
      else element.dataset.moving = "true";
    };
    const tell = () => {
      mark();
      report.current({ clock });
    };
    const play = (now: number) => {
      frame = 0;
      // A tab that was away, or a frame that was long: no more than a twentieth of a second is played at once.
      clock = clockAfter(clock, target, Math.min(0.05, Math.max(0, (now - last) / 1000)), clockPerSecond, stops);
      last = now;
      tell();
      if (clock !== target) frame = window.requestAnimationFrame(play);
    };
    const read = () => {
      const box = section.getBoundingClientRect();
      const tall = element.offsetHeight;
      target = stops[stopAt(-box.top, zone * tall, beats, lead * tall)];
      const stageBox = element.getBoundingClientRect();
      const seen = stageBox.bottom > 0 && stageBox.top < window.innerHeight;
      if (!seen && clock !== target) {
        // Out of the window: there straight away.
        if (frame) window.cancelAnimationFrame(frame);
        frame = 0;
        clock = target;
        tell();
        return;
      }
      if (clock !== target && !frame) {
        last = performance.now();
        mark();
        frame = window.requestAnimationFrame(play);
      }
    };
    tell();
    read();
    window.addEventListener("scroll", read, { passive: true });
    window.addEventListener("resize", read);
    return () => {
      window.removeEventListener("scroll", read);
      window.removeEventListener("resize", read);
      if (frame) window.cancelAnimationFrame(frame);
      delete element.dataset.stop;
      delete element.dataset.moving;
    };
  }, [stage, enabled, stops, clockPerSecond, zone, lead]);
}
