"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";

/** Keeps a looping clip playing (ADR-0069). The clip loops by itself; this restarts it if a browser ends it anyway or pauses it,
 * as phones can in power saving, and when the tab comes back. It never tries more than once a second, never resumes a clip the
 * visitor paused (`held` says so), and does nothing for a clip with no source, such as one shown to a visitor who asked for
 * reduced motion, which stays on its poster. Returns the clean-up. */
export function keepPlaying(video: HTMLVideoElement, held: () => boolean = () => false): () => void {
  let lastTry = 0;
  const resume = () => {
    const now = performance.now();
    if (held() || !video.currentSrc || !video.paused || document.visibilityState !== "visible" || now - lastTry < 1000) return;
    lastTry = now;
    video.play().catch(() => {});
  };
  const restart = () => {
    if (held()) return;
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

const heroClip = () => document.querySelector<HTMLVideoElement>(".home-hero-video video");

/** Keeps the hero clip playing, and gives the visitor a button that pauses it and plays it again (WCAG 2.2.2): a clip the
 * visitor paused stays paused. The button is drawn once the clip has a source, which only a window 768 px wide or more without
 * reduced motion gives it (app/page.tsx), and stays when the window narrows afterwards, since the clip then plays on. */
export function HeroVideoKeeper() {
  const [paused, setPaused] = useState(false);
  const [playable, setPlayable] = useState(false);
  const held = useRef(false);
  useEffect(() => {
    const video = heroClip();
    if (!video) return undefined;
    // The browser picks the source once, before "loadstart"; a clip with none stays on its poster and needs no button.
    const chosen = () => {
      if (video.currentSrc) setPlayable(true);
    };
    const events = ["loadstart", "loadedmetadata", "play"] as const;
    for (const type of events) video.addEventListener(type, chosen);
    chosen();
    const stop = keepPlaying(video, () => held.current);
    return () => {
      for (const type of events) video.removeEventListener(type, chosen);
      stop();
    };
  }, []);
  function toggle() {
    const next = !held.current;
    held.current = next;
    setPaused(next);
    const video = heroClip();
    if (!video) return;
    if (next) video.pause();
    else video.play().catch(() => {});
  }
  if (!playable) return null;
  return (
    <button type="button" className="home-hero-pause" aria-pressed={paused} aria-label="Pause background video" onClick={toggle}>
      {paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
    </button>
  );
}
