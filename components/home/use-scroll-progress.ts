"use client";

import { useEffect, useRef, type RefObject } from "react";

export type ScrollFrame = {
  /** How far the page has scrolled past the element's top edge, in viewport heights; negative before it. */
  screens: number;
  /** The viewport's height in pixels. */
  viewport: number;
};

/** Calls `onFrame` with the scroll position measured against an element, at most once per animation frame and only when the
 * page scrolled or was resized. The page scrolls natively: this only reads the position, it never sets it. */
export function useScrollProgress(target: RefObject<HTMLElement | null>, enabled: boolean, onFrame: (frame: ScrollFrame) => void) {
  const latest = useRef(onFrame);
  latest.current = onFrame;
  useEffect(() => {
    if (!enabled) return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const element = target.current;
      if (!element) return;
      const viewport = window.innerHeight || 1;
      latest.current({ screens: -element.getBoundingClientRect().top / viewport, viewport });
    };
    const request = () => {
      if (!frame) frame = window.requestAnimationFrame(measure);
    };
    request();
    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
    return () => {
      window.removeEventListener("scroll", request);
      window.removeEventListener("resize", request);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [target, enabled]);
}
