"use client";

import { useEffect } from "react";

/** Keeps a looping clip playing (ADR-0069). The clip loops by itself; this restarts it if a browser ends it anyway or pauses it,
 * as phones can in power saving, and when the tab comes back. It never tries more than once a second, and does nothing for a clip
 * with no source, such as one shown to a visitor who asked for reduced motion, which stays on its poster. Returns the clean-up. */
export function keepPlaying(video: HTMLVideoElement): () => void {
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
}

/** Keeps the hero clip playing. */
export function HeroVideoKeeper() {
  useEffect(() => {
    const video = document.querySelector<HTMLVideoElement>(".home-hero-video video");
    return video ? keepPlaying(video) : undefined;
  }, []);
  return null;
}
