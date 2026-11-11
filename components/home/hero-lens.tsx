"use client";

import { useEffect, useRef, useState } from "react";
import { LENS_CAPTIONS, LENS_TIMING, lensModelAt } from "@/lib/hero-lens";
import { keepPlaying } from "./hero-video-keeper";

// Plain HTML so the browser sees "muted" before React runs, which autoplay requires. The source is only offered where the lens
// shows (wide screens) and to visitors who have not asked for reduced motion; everyone else keeps the poster or nothing.
const lensHtml =
  '<video autoplay muted loop playsinline preload="auto" poster="/assets/hero-lens/lens.jpg" disablepictureinpicture tabindex="-1">' +
  '<source src="/assets/hero-lens/lens.mp4" type="video/mp4" media="(min-width: 1024px) and (prefers-reduced-motion: no-preference)"></video>';

/** The hero's lens (ADR-0071): a framed window over the material clip that plays our own results, recorded from the workspace's
 * viewer by scripts/hero-lens.ts, with a caption naming the model on screen. Decorative, so hidden from assistive technology;
 * shown on wide screens only. */
export function HeroLens() {
  const clip = useRef<HTMLDivElement>(null);
  const [model, setModel] = useState(LENS_TIMING.segments[0].id);
  useEffect(() => {
    const video = clip.current?.querySelector("video");
    if (!video) return;
    const follow = () => setModel(lensModelAt(video.currentTime));
    video.addEventListener("timeupdate", follow);
    const release = keepPlaying(video);
    return () => {
      video.removeEventListener("timeupdate", follow);
      release();
    };
  }, []);
  const [title, detail] = LENS_CAPTIONS[model];
  return (
    <div className="home-hero-lens" aria-hidden="true">
      <div className="home-hero-lens-glass" />
      <div className="home-hero-lens-clip" ref={clip} dangerouslySetInnerHTML={{ __html: lensHtml }} />
      <p className="home-hero-lens-caption" data-model={model}>
        <b key={`${model}-title`}>{title}</b>
        <br />
        <span key={`${model}-detail`}>{detail}</span>
      </p>
    </div>
  );
}
