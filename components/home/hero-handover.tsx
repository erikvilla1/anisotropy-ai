"use client";

import { useEffect } from "react";

/** The windows on which the demo is a stepped stage (the same query as components/home/product-demo.tsx). */
const STAGED = "(min-width: 1024px) and (min-height: 600px) and (prefers-reduced-motion: no-preference)";
const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const span = (value: number, from: number, to: number) => clamp01((value - from) / (to - from));
const smooth = (x: number) => x * x * (3 - 2 * x);

/** How far the page has scrolled from the hero to the demo's stage, 0 to 1, and from which share each side starts and ends. */
export const HANDOVER = {
  /** The hero's clip begins to dim here and has gone when the stage fills the window. */
  heroFrom: 0.05,
  heroTo: 1,
  /** The first beat's words come in over this stretch, so they stand when the stage arrives. */
  wordsFrom: 0.1,
  wordsTo: 0.9,
};

/** The hand-over from the hero to the product demo (ADR-0095 amendment 4). Where the demo is a stepped stage, the hero stays
 * where it is while the page scrolls to the stage, which starts half a window up behind it: the hero dims away as the scroll
 * goes, and the first beat's words come up through it, so the window is never an empty black one. The stylesheets lay the
 * two sections out (app/home.css, app/home-demo.css); this writes how far the scroll has gone on their wrapper:
 * `data-handover` is "ready" at the top, "going" on the way and "done" once the stage fills the window, `--hero-left` is how
 * far the hero has gone and `--demo-arrived` how far the first beat's words are in. With reduced motion or on a small window
 * the two sections are ordinary ones, one under the other, and this writes nothing. Renders nothing. */
export function HeroHandover() {
  useEffect(() => {
    const opening = document.querySelector<HTMLElement>(".home-opening");
    const demo = document.getElementById("demo");
    if (!opening || !demo) return;
    const media = window.matchMedia(STAGED);
    let frame = 0;
    const clear = () => {
      delete opening.dataset.handover;
      opening.style.removeProperty("--hero-left");
      opening.style.removeProperty("--demo-arrived");
    };
    const write = () => {
      frame = 0;
      if (!media.matches) {
        clear();
        return;
      }
      // How far the wrapper has scrolled, as a share of the way that brings the stage's top edge onto the window's.
      const start = opening.getBoundingClientRect().top;
      const travel = Math.max(1, demo.getBoundingClientRect().top - start);
      const share = clamp01(-start / travel);
      opening.dataset.handover = share >= 1 ? "done" : share > 0 ? "going" : "ready";
      opening.style.setProperty("--hero-left", smooth(span(share, HANDOVER.heroFrom, HANDOVER.heroTo)).toFixed(3));
      opening.style.setProperty("--demo-arrived", smooth(span(share, HANDOVER.wordsFrom, HANDOVER.wordsTo)).toFixed(3));
    };
    const ask = () => {
      if (!frame) frame = window.requestAnimationFrame(write);
    };
    write();
    window.addEventListener("scroll", ask, { passive: true });
    window.addEventListener("resize", ask);
    media.addEventListener("change", ask);
    return () => {
      window.removeEventListener("scroll", ask);
      window.removeEventListener("resize", ask);
      media.removeEventListener("change", ask);
      if (frame) window.cancelAnimationFrame(frame);
      clear();
    };
  }, []);
  return null;
}
