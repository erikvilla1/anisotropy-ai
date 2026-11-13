"use client";

import { useEffect, useRef } from "react";
import { ArrowDown } from "lucide-react";
import { STEPS } from "./tour-timeline";
import "@/app/home-tour.css";

/** How long the button's scroll takes, so the bridge from the clip into the 3D view is seen on the way. */
const DURATION_MS = 1500;
/** Where the button stops: the tour's first step, with its words up. */
const FIRST_STEP_AT = STEPS[0].at(0.14);
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);
/** Sets the scroll position at once, whatever `scroll-behavior` the page has; a browser that does not know "instant" gets the plain call. */
function jumpTo(top: number) {
  try {
    window.scrollTo({ top, behavior: "instant" });
  } catch {
    window.scrollTo(0, top);
  }
}

/** "Scroll to explore", the second small line under the hero's statement (ADR-0077 amendment 19): one press scrolls the
 * page to the first step of the tour (components/home/demo-tour.tsx). It scrolls only when pressed, and lets go at once if the
 * visitor scrolls, touches or presses a key; the page's own scrolling is never taken over. A visitor who asked for reduced
 * motion is taken there without the move. */
export function ScrollToExplore() {
  const stop = useRef<(() => void) | null>(null);
  useEffect(() => () => stop.current?.(), []);
  function explore() {
    const tour = document.getElementById("tour");
    if (!tour) return;
    stop.current?.();
    const top = tour.getBoundingClientRect().top + window.scrollY;
    const pinned = tour.dataset.mode === "pinned";
    const target = Math.round(pinned ? top + FIRST_STEP_AT * window.innerHeight : top);
    // Unpinned, the tour is an ordinary section: the page's own scroll behaviour takes the visitor to its top.
    if (!pinned) {
      window.scrollTo({ top: target });
      return;
    }
    const from = window.scrollY;
    const started = performance.now();
    let frame = 0;
    const events = ["wheel", "touchstart", "keydown", "pointerdown"] as const;
    const cancel = () => {
      window.cancelAnimationFrame(frame);
      for (const name of events) window.removeEventListener(name, cancel);
      stop.current = null;
    };
    const step = (now: number) => {
      const share = Math.min(1, (now - started) / DURATION_MS);
      jumpTo(from + (target - from) * easeInOut(share));
      if (share < 1) frame = window.requestAnimationFrame(step);
      else cancel();
    };
    for (const name of events) window.addEventListener(name, cancel, { passive: true });
    stop.current = cancel;
    frame = window.requestAnimationFrame(step);
  }
  return (
    <button type="button" className="home-hero-explore" aria-label="Scroll to explore" onClick={explore}>
      <ArrowDown aria-hidden="true" strokeWidth={1.5} />
      <span>Explore</span>
    </button>
  );
}
