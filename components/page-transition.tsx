"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { prepareIntro, type IntroRun } from "@/components/intro-text";
import { isAppPath } from "@/lib/site-nav";
import "@/app/intro.css";

const LIFT_MS = 600; // the way out of black, as app/globals.css has it (ADR-0070 amendment 8)
const HOME_FONT_WAIT_MS = 800; // the longest the home page's black waits for the fonts, so the hero's words are measured in their own type
const HOLD_MS = 600; // the longest any other page stays black after its first paint: the stylesheet lifts the veil by itself then
const REST_GRACE_MS = 250; // how long past a lift's length the veil waits to hear the lift's end before it rests anyway

/** enter: the home page's first paint, black until this component has the hero's words ready and lifts it (the stylesheet lifts it
 * alone after 2 s if no script runs); hold: any other page's first paint, black until the fonts are in (the stylesheet lifts it
 * alone after 600 ms); lift: the 600 ms out of black, on a first load and on every page that comes in by a link, Back or Forward;
 * idle: out of the way. components/home/hero-outro.tsx and the browser tests read `is-idle` to know the load-in is over. */
type Phase = "enter" | "hold" | "lift" | "idle";
/** The veil's state: the page it stands for, its phase, and how many pages have come in without a reload since the first. */
type Veil = { pathname: string; phase: Phase; landing: number };

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const withoutSlash = (path: string) => (path.length > 1 ? path.replace(/\/+$/, "") : path);

/** Whether the keyboard's focus is shown on something in the page. The skip link does not count: it lies over the veil. */
function focusRingShown() {
  const focused = document.activeElement;
  return !!focused && focused !== document.body && focused.matches(":focus-visible") && !focused.classList.contains("skip-link");
}

/** How a page that was loaded starts: the workspace, an app, and the old addresses that only pass on to it start without the
 * veil; every page of the site starts black. */
function firstPhase(pathname: string): Phase {
  if (isAppPath(pathname)) return "idle";
  return pathname === "/" ? "enter" : "hold";
}

/** Resolves when the page's fonts are in, or after `longest` ms, whichever is first. */
function fontsReady(longest: number) {
  return new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, longest);
    const done = () => {
      window.clearTimeout(timer);
      resolve();
    };
    if (document.fonts?.ready) document.fonts.ready.then(done, done);
    else done();
  });
}

/** The page veil (ADR-0070): a black layer over the whole screen that every page of the site comes out of when a visitor lands
 * on it. Nothing waits for it: a link goes to its page at once, and the black belongs to the page that comes in.
 *
 * - A page that was loaded or reloaded starts black in its served HTML. The home page stays black until its fonts are in and
 *   the hero's words are ready, then lifts and plays the load-in moves (components/intro-text.ts). Any other page lifts as soon
 *   as its fonts are in, so its text is not seen to change type, and after 600 ms at the latest.
 * - A page that comes in without a reload (a link, Back or Forward) is black from its first frame and lifts at once. If it has
 *   elements tagged for the load-in moves they play as on a first load; a page brought back by Back or Forward lifts without.
 * - The workspace and the old addresses that pass on to it have no veil. A visitor who asks for reduced motion never gets one.
 * - The veil takes no pointer events and is hidden from assistive technology. A focused skip link lies over it. Wherever else
 *   the keyboard's focus is shown there is no veil, so no focus ring is under the black: a page reached by a link that was
 *   pressed from the keyboard comes in without it, and the veil goes at once when the focus lands in the page. */
export function PageTransition() {
  const pathname = usePathname();
  const [veil, setVeil] = useState<Veil>(() => ({ pathname, phase: firstPhase(pathname), landing: 0 }));
  // Another page has come in without a reload. The veil's phase is set here, while rendering, so the black is in the same
  // update of the screen as the page itself: there is no frame of the new page without it. The element is a new one for each
  // such page (its key), so the lift starts again from black even when the last one had not ended.
  if (veil.pathname !== pathname) {
    const plain = isAppPath(pathname) || reducedMotion() || focusRingShown();
    setVeil({ pathname, phase: plain ? "idle" : "lift", landing: veil.landing + 1 });
  }
  const element = useRef<HTMLDivElement>(null);
  const intro = useRef<IntroRun | null>(null);
  const started = useRef(veil.phase); // how the page that was loaded started
  const firstLoad = useRef(started.current !== "idle");
  const traversed = useRef<string | null>(null); // the address the browser's Back or Forward button last went to

  /** The veil rests. With `landing`, only if that page is still the one on screen. */
  const rest = (landing?: number) =>
    setVeil((now) => (now.phase === "idle" || (landing !== undefined && now.landing !== landing) ? now : { ...now, phase: "idle" }));

  // The first load: hold the black until the fonts are in and the tagged text is ready, then lift and play the moves.
  useEffect(() => {
    if (!firstLoad.current) return;
    if (reducedMotion()) {
      firstLoad.current = false;
      rest(0);
      return;
    }
    let cancelled = false;
    fontsReady(started.current === "enter" ? HOME_FONT_WAIT_MS : HOLD_MS).then(() => {
      if (cancelled || !firstLoad.current) return;
      firstLoad.current = false;
      // If the stylesheet has already started to lift the veil, the page has been seen: its text is left alone and the
      // stylesheet's lift goes on. When that lift had already ended before this script ran, its end was never heard.
      const opacity = element.current ? getComputedStyle(element.current).opacity : "0";
      if (opacity !== "1") {
        if (opacity === "0") rest(0);
        else window.setTimeout(() => rest(0), LIFT_MS + REST_GRACE_MS);
        return;
      }
      // A page restored by the browser's back or forward button lifts without the moves.
      const entry = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      intro.current?.finish();
      intro.current = entry?.type !== "back_forward" ? prepareIntro() : null;
      window.requestAnimationFrame(() => {
        setVeil((now) => (now.phase === "enter" || now.phase === "hold" ? { ...now, phase: "lift" } : now));
        intro.current?.play();
      });
    });
    return () => {
      cancelled = true;
    };
    // Once, for the page that was loaded.
  }, []);

  // A page that came in without a reload: its tagged text is made ready before the screen is next drawn, and its moves start
  // with the lift. Next has sent the page to its top by now (its own layout effect runs before this one), and only what is
  // in the window takes part. The moves of the page left behind end, whichever way it was left.
  useLayoutEffect(() => {
    if (veil.landing > 0) {
      firstLoad.current = false;
      const restored = traversed.current === withoutSlash(pathname);
      traversed.current = null;
      if (veil.phase === "lift" && !restored) {
        intro.current = prepareIntro();
        intro.current?.play();
      }
    }
    return () => {
      intro.current?.finish();
      intro.current = null;
    };
    // Once for each such page: the phase and the address read here are its own.
  }, [veil.landing]);

  // A lift whose end is never heard (the tab was in the background, or the element was not drawn) still ends.
  useEffect(() => {
    if (veil.phase !== "lift") return;
    const landing = veil.landing;
    const timer = window.setTimeout(() => rest(landing), LIFT_MS + REST_GRACE_MS);
    return () => window.clearTimeout(timer);
  }, [veil.phase, veil.landing]);

  useEffect(() => {
    // The page is to be seen as it is, now: no moves start on it any more and the veil rests. The class is written on the
    // element here as well, so the black is gone in this frame and not only when React next updates the screen.
    const show = () => {
      firstLoad.current = false;
      if (element.current) element.current.className = "page-transition is-idle";
      rest();
    };
    // The keyboard's focus has landed in the page: its ring must not be under the black.
    const onFocus = () => {
      if (focusRingShown()) show();
    };
    // A page the browser kept whole and brings back as it was left (its back-forward cache) is shown at once, never black.
    const onShow = (event: PageTransitionEvent) => {
      if (!event.persisted) return;
      intro.current?.finish();
      show();
    };
    // Back or Forward: the address is already the one gone to, and its page comes in after this.
    const onTraverse = () => {
      traversed.current = withoutSlash(window.location.pathname);
    };
    if (focusRingShown()) show();
    document.addEventListener("focusin", onFocus);
    window.addEventListener("pageshow", onShow);
    window.addEventListener("popstate", onTraverse, true);
    return () => {
      document.removeEventListener("focusin", onFocus);
      window.removeEventListener("pageshow", onShow);
      window.removeEventListener("popstate", onTraverse, true);
    };
  }, []);

  return (
    <div
      key={veil.landing}
      ref={element}
      className={`page-transition is-${veil.phase}`}
      aria-hidden="true"
      // A lift has ended (the stylesheet's own, on a first load no script took over, included): the veil rests.
      onAnimationEnd={() => rest()}
    />
  );
}
