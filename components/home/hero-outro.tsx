"use client";

import { useEffect } from "react";
import { prepareOutro, type IntroRun } from "@/components/intro-text";

/** How long the hero's words stand once they have loaded in, before they are taken away. */
const HOLD_MS = 5000;
const CHECK_MS = 200;

/** Takes the hero's words away five seconds after they have loaded in, so the clip plays alone, as Anduril's hero does
 * (ADR-0077 amendment 19; the lead's request and recording of 2026-11-12). The words are untyped by
 * components/intro-text.ts: the statement, the tagline and the two small lines lose their characters from the end of each
 * line, then the mark fades. The five seconds count only while the load-in is over and the page is at its top, so a visitor
 * who has scrolled into the tour still finds the words on the way back. They stay in the page for a screen reader; the
 * Explore button leaves the tab order with them. A visitor who asked for reduced motion keeps the words. Renders nothing. */
export function HeroOutro() {
  useEffect(() => {
    const hero = document.getElementById("overview");
    if (!hero || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let run: IntroRun | null = null;
    let since: number | null = null;
    let after = 0;
    const settled = () => {
      const veil = document.querySelector(".page-transition");
      return !hero.querySelector("[data-intro-run]") && (!veil || veil.classList.contains("is-idle")) && window.scrollY <= 8;
    };
    const check = window.setInterval(() => {
      if (!settled()) {
        since = null;
        return;
      }
      const now = performance.now();
      if (since === null) since = now;
      if (now - since < HOLD_MS) return;
      window.clearInterval(check);
      run = prepareOutro(hero);
      if (!run) return;
      run.play();
      after = window.setTimeout(() => hero.setAttribute("data-words", "gone"), run.totalMs + 80);
    }, CHECK_MS);
    return () => {
      window.clearInterval(check);
      window.clearTimeout(after);
      run?.finish();
    };
  }, []);
  return null;
}
