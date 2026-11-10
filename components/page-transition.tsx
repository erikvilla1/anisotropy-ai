"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { prepareIntro, type IntroRun } from "@/components/intro-text";
import "@/app/intro.css";

const LEAVE_MS = 350; // Anduril fades to black for 350 ms before it shows the next page (ADR-0070 amendment 1)
const LEAVE_GRACE_MS = 200; // how long past the fade the navigation waits for the fade's end before going anyway
const STUCK_MS = 4000; // if the next page has not arrived by then, lift the veil anyway
const FONT_WAIT_MS = 800; // the longest the black waits for the page's fonts, so the text is measured in its own type

/** enter: the first paint, black until this component lifts it (the stylesheet lifts it alone after 2 s if no script runs);
 * lift: the first load's 300 ms out of black; leave: 350 ms into black, then held; arrive: 350 ms out of black on the next page. */
type Phase = "enter" | "lift" | "leave" | "arrive" | "idle";

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

/** The page veil (ADR-0070, amendment 1), after Anduril: a black layer over the whole screen. The first load starts under it
 * and it lifts once the page's text is ready for its load-in moves (components/intro-text.ts), which then play; a click on a
 * header or footer link fades it in before the next page, where it lifts the same way. The workspace, an app, opens without
 * it. Back and forward, other links and visitors who ask for reduced motion get no veil and no moves. */
export function PageTransition() {
  const pathname = usePathname();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>(() => (pathname.startsWith("/workspace") || pathname === "/chat" ? "idle" : "enter"));
  const veil = useRef<HTMLDivElement>(null);
  const leaving = useRef(false);
  const pending = useRef<string | null>(null); // where a header or footer link is going, until the veil is up
  const navigate = useRef<() => void>(() => {});
  const timers = useRef<number[]>([]);
  const intro = useRef<IntroRun | null>(null);
  const firstLoad = useRef(phase === "enter");

  // Lift the veil in the next frame as `next`, and play the load-in moves of the page now on screen with it.
  function liftWith(next: "lift" | "arrive", withMoves: boolean) {
    intro.current?.finish();
    intro.current = withMoves ? prepareIntro() : null;
    window.requestAnimationFrame(() => {
      setPhase(next);
      intro.current?.play();
    });
  }

  // The first load: hold the black until the fonts are in and the text is ready, then lift.
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
      const seen = !veil.current || getComputedStyle(veil.current).opacity !== "1";
      if (seen) return;
      // A page restored by the browser's back or forward button lifts without the moves.
      const entry = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      liftWith("lift", entry?.type !== "back_forward");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function go() {
      const to = pending.current;
      if (to === null) return;
      pending.current = null;
      router.push(to);
    }
    navigate.current = go;
    function onClick(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element | null)?.closest?.("a");
      if (!link || !link.closest(".site-header, .site-footer")) return;
      if ((link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.hash || url.pathname === window.location.pathname) return;
      if (reducedMotion()) return;
      // Still black from the first load: the link navigates at once, and the first load's lift shows the page it lands on.
      if (firstLoad.current) return;
      // Prevented here, in the capture phase, Next's Link still runs its own onClick (closing the mobile menu) but does not
      // navigate; the navigation follows once the veil is up.
      event.preventDefault();
      leaving.current = true;
      // The navigation follows when the veil's fade to black has ended (onAnimationEnd below), so the old page is fully
      // covered before the address changes; the timer is the fallback for a browser that never reports the fade's end.
      pending.current = url.pathname + url.search;
      setPhase("leave");
      timers.current.push(window.setTimeout(go, LEAVE_MS + LEAVE_GRACE_MS));
      timers.current.push(window.setTimeout(() => {
        if (leaving.current) { leaving.current = false; setPhase("arrive"); }
      }, LEAVE_MS + STUCK_MS));
    }
    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      timers.current.forEach((id) => window.clearTimeout(id));
      intro.current?.finish();
    };
  }, [router]);

  // The next page has arrived under the black: lift, and play its moves.
  useEffect(() => {
    if (!leaving.current) {
      // Back, forward or a link in the page: no veil, and any moves still playing on the page left behind end.
      intro.current?.finish();
      return;
    }
    leaving.current = false;
    liftWith("arrive", true);
  }, [pathname]);

  return (
    <div
      ref={veil}
      className={`page-transition is-${phase}`}
      aria-hidden="true"
      // A fade out has ended (the stylesheet's own, on a first load no script took over, included): the veil rests.
      // The fade to black has ended: the navigation that was waiting for it goes ahead, and the veil holds.
      onAnimationEnd={() => {
        if (leaving.current && pending.current !== null) navigate.current();
        else setPhase((now) => (now === "leave" ? now : "idle"));
      }}
    />
  );
}
