"use client";

import { useEffect } from "react";

/** Keeps the hero clip playing (ADR-0069). The clip loops by itself; this restarts it if a browser ends it anyway or pauses it,
 * as phones can in power saving, and when the tab comes back. It never tries more than once a second, and does nothing for
 * visitors who asked for reduced motion, whose clip has no source and stays on its poster. */
export function HeroVideoKeeper() {
  useEffect(() => {
    const video = document.querySelector<HTMLVideoElement>(".home-hero-video video");
    if (!video) return;
    let lastTry = 0;
    const resume = () => {
      const now = performance.now();
      if (!video.currentSrc || !video.paused || document.visibilityState !== "visible" || now - lastTry < 1000) return;
      lastTry = now;
      video.play().catch(() => {});
    };
    const restart = () => {
      video.currentTime = 0;
      resume();
    };
    video.addEventListener("ended", restart);
    video.addEventListener("pause", resume);
    document.addEventListener("visibilitychange", resume);
    return () => {
      video.removeEventListener("ended", restart);
      video.removeEventListener("pause", resume);
      document.removeEventListener("visibilitychange", resume);
    };
  }, []);
  return null;
}
