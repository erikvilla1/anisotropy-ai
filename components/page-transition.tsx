"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

const LEAVE_MS = 400; // PhysicsX navigates 400 ms after the click (ADR-0070)
const STUCK_MS = 4000; // if the next page has not arrived by then, lift the veil anyway

type Phase = "enter" | "leave" | "idle";

/** The page veil (ADR-0070), after PhysicsX: a pale layer over the whole screen that the first load fades out of, and that a click
 * on a header or footer link fades in before the next page and out after it. The first load's fade is CSS only; the workspace,
 * an app, opens without it. Back and forward, other links and visitors who ask for reduced motion get no veil. */
export function PageTransition() {
  const pathname = usePathname();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>(() => (pathname.startsWith("/workspace") || pathname === "/chat" ? "idle" : "enter"));
  const leaving = useRef(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element | null)?.closest?.("a");
      if (!link || !link.closest(".site-header, .site-footer")) return;
      if ((link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.hash || url.pathname === window.location.pathname) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      // Prevented here, in the capture phase, Next's Link still runs its own onClick (closing the mobile menu) but does not
      // navigate; the navigation follows once the veil is up.
      event.preventDefault();
      leaving.current = true;
      setPhase("leave");
      timers.current.push(window.setTimeout(() => router.push(url.pathname + url.search), LEAVE_MS));
      timers.current.push(window.setTimeout(() => {
        if (leaving.current) { leaving.current = false; setPhase("enter"); }
      }, LEAVE_MS + STUCK_MS));
    }
    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      timers.current.forEach((id) => window.clearTimeout(id));
    };
  }, [router]);

  useEffect(() => {
    if (!leaving.current) return;
    leaving.current = false;
    setPhase("enter");
  }, [pathname]);

  return <div className={`page-transition is-${phase}`} aria-hidden="true" />;
}
