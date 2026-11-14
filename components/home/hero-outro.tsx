"use client";

import { useEffect } from "react";
import { prepareIntro, prepareOutro, type IntroRun } from "@/components/intro-text";

/** How long the hero's words stand once they have loaded in, before they are taken away. */
const HOLD_MS = 3000;
const CHECK_MS = 200;
/** The clip has started again when its time is this much earlier than it last was, in seconds. */
const BACK_S = 1;

/** Takes the hero's words away three seconds after they have loaded in (five until ADR-0077 amendment 26), so the clip plays alone, as Anduril's hero does
 * (ADR-0077 amendment 19; the lead's request and recording of 2026-11-12). The words are untyped by
 * components/intro-text.ts: the statement, the tagline and the small line lose their characters from the end of each
 * line; the mark starts first, with a quarter turn, and has faded just before the last of them goes. The three seconds count only while the load-in is over and
 * the page is at its top, so a visitor who has scrolled into the tour still finds the words on the way back. They stay in the page for a screen reader. A
 * visitor who asked for reduced motion keeps the words. Renders nothing.
 *
 * Each time the clip starts again the words come back the way they first came, typed in, stand their three seconds and are
 * taken away again (ADR-0077 amendment 40; the lead's request of 2026-11-14). That happens only while the words are away, the
 * page is at its top and the tab is showing; a round the visitor was not there for is left out. The hero keeps
 * `data-words="gone"` from the first time the words leave, so "Scroll to explore" stays up through the later rounds. */
export function HeroOutro() {
  useEffect(() => {
    const hero = document.getElementById("overview");
    if (!hero || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const video = hero.querySelector<HTMLVideoElement>(".home-hero-video video");
    let run: IntroRun | null = null;
    let since: number | null = null;
    let check = 0;
    let after = 0;
    let away = false; // the words have been taken away and nothing is moving
    let last = 0; // the clip's time when it last reported it
    const settled = () => {
      const veil = document.querySelector(".page-transition");
      return !hero.querySelector("[data-intro-run]") && (!veil || veil.classList.contains("is-idle")) && window.scrollY <= 8;
    };
    // The words stand: count their three seconds, then take them away.
    const hold = () => {
      since = null;
      check = window.setInterval(() => {
        if (!settled()) {
          since = null;
          return;
        }
        const now = performance.now();
        if (since === null) since = now;
        if (now - since < HOLD_MS) return;
        window.clearInterval(check);
        check = 0;
        run = prepareOutro(hero);
        if (!run) return;
        run.play();
        after = window.setTimeout(() => {
          run = null;
          away = true;
          hero.setAttribute("data-words", "gone");
        }, run.totalMs + 80);
      }, CHECK_MS);
    };
    // The clip has started again: the words come back as they first came, then stand and go as before.
    const again = () => {
      if (!away || window.scrollY > 8 || document.visibilityState !== "visible") return;
      const gone = Array.from(hero.querySelectorAll<HTMLElement>("[data-outro-done]"));
      for (const element of gone) element.removeAttribute("data-outro-done");
      // Made ready in the same step, so the words are never seen whole between the two.
      run = prepareIntro(hero);
      if (!run) {
        for (const element of gone) element.setAttribute("data-outro-done", "");
        return;
      }
      away = false;
      hero.setAttribute("data-words-round", String(Number(hero.getAttribute("data-words-round") ?? 1) + 1));
      run.play();
      after = window.setTimeout(() => {
        run = null;
        hold();
      }, run.totalMs + 80);
    };
    const onTime = () => {
      if (!video) return;
      const now = video.currentTime;
      if (now + BACK_S < last) again();
      last = now;
    };
    video?.addEventListener("timeupdate", onTime);
    hold();
    return () => {
      video?.removeEventListener("timeupdate", onTime);
      window.clearInterval(check);
      window.clearTimeout(after);
      run?.finish();
    };
  }, []);
  return null;
}
