"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { prepareIntro, type IntroRun } from "@/components/intro-text";
import "@/app/intro.css";

const FONT_WAIT_MS = 800; // the longest the black waits for the page's fonts, so the text is measured in its own type

/** enter: the home page's first paint, black until this component lifts it (the stylesheet lifts it alone after 2 s if no script
 * runs); lift: the first load's 300 ms out of black. */
type Phase = "enter" | "lift" | "idle";

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Resolves when the page's fonts are in, or after FONT_WAIT_MS, whichever is first. */
function fontsReady() {
  return new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, FONT_WAIT_MS);
    const done = () => {
      window.clearTimeout(timer);
      resolve();
    };
    if (document.fonts?.ready) document.fonts.ready.then(done, done);
    else done();
  });
}

/** The page veil (ADR-0070, amendments 1 and 3), after Anduril: a black layer over the whole screen on the home page's first load
 * only. The page starts under it and it lifts once the page's text is ready for its load-in moves (components/intro-text.ts), which
 * then play. Every other page, every navigation (links, back and forward) and visitors who ask for reduced motion get no veil and no
 * delay: since amendment 3 a link goes to its page at once. */
export function PageTransition() {
  const pathname = usePathname();
  const [phase, setPhase] = useState<Phase>(() => (pathname === "/" ? "enter" : "idle"));
  const veil = useRef<HTMLDivElement>(null);
  const intro = useRef<IntroRun | null>(null);
  const firstLoad = useRef(phase === "enter");

  // The first load of the home page: hold the black until the fonts are in and the text is ready, then lift and play the moves.
  useEffect(() => {
    if (!firstLoad.current) return;
    if (reducedMotion()) {
      firstLoad.current = false;
      setPhase("idle");
      return;
    }
    let cancelled = false;
    fontsReady().then(() => {
      if (cancelled || !firstLoad.current) return;
      firstLoad.current = false;
      // If the stylesheet has already started to lift the veil, the page has been seen: leave its text alone.
      // When that fade has already ended before this script ran, its animationend was never heard: rest the veil here.
      const seen = !veil.current || getComputedStyle(veil.current).opacity !== "1";
      if (seen) {
        if (!veil.current || getComputedStyle(veil.current).opacity === "0") setPhase("idle");
        return;
      }
      // A page restored by the browser's back or forward button lifts without the moves.
      const entry = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      intro.current?.finish();
      intro.current = entry?.type !== "back_forward" ? prepareIntro() : null;
      window.requestAnimationFrame(() => {
        setPhase("lift");
        intro.current?.play();
      });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Another page: any moves still playing on the page left behind end.
  useEffect(() => {
    return () => intro.current?.finish();
  }, [pathname]);

  return (
    <div
      ref={veil}
      className={`page-transition is-${phase}`}
      aria-hidden="true"
      // A fade out has ended (the stylesheet's own, on a first load no script took over, included): the veil rests.
      onAnimationEnd={() => setPhase("idle")}
    />
  );
}
