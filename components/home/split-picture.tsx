"use client";

import Link from "next/link";
import type { PointerEvent } from "react";

/** A band's picture on the home page (ADR-0077 amendments 37, 39 and 48): a link to where the band's own link goes, the
 * material photograph in black and white, and under a mouse's pointer a small lens that shows the same photograph in the
 * demo's colours.
 *
 * The lens is a picture effect and nothing more: the photograph's own light and dark, smoothed, drawn through the scale the
 * demo colours its analysis with (blue for the darkest, red for the lightest; the filter is `#home-fea` in app/page.tsx),
 * laid as colour over the photograph itself so the weave still shows, with a faint mesh of lines over it. It measures nothing and states nothing: no number, no legend, no caption. It follows
 * the pointer a little behind it, keeps inside the picture, and is not there for a finger or the keyboard. The stylesheet
 * (app/home.css) draws it from the place this writes on the element as `--lens-x` and `--lens-y`. */
export function SplitPicture({ href }: { href: string }) {
  const place = (event: PointerEvent<HTMLAnchorElement>) => {
    if (event.pointerType === "touch") return;
    const picture = event.currentTarget;
    const lens = picture.querySelector<HTMLElement>(".home-split-lens");
    if (!lens) return;
    const box = picture.getBoundingClientRect();
    // Under the pointer the picture is drawn a little larger: the lens is placed in the picture's own measure.
    const scale = box.width / picture.offsetWidth || 1;
    const wide = lens.offsetWidth, tall = lens.offsetHeight;
    const x = Math.min(picture.offsetWidth - wide, Math.max(0, (event.clientX - box.left) / scale - wide / 2));
    const y = Math.min(picture.offsetHeight - tall, Math.max(0, (event.clientY - box.top) / scale - tall / 2));
    picture.style.setProperty("--lens-wide", `${picture.offsetWidth}px`);
    picture.style.setProperty("--lens-tall", `${picture.offsetHeight}px`);
    picture.style.setProperty("--lens-x", `${x.toFixed(1)}px`);
    picture.style.setProperty("--lens-y", `${y.toFixed(1)}px`);
    picture.dataset.lens = "on";
  };
  const leave = (event: PointerEvent<HTMLAnchorElement>) => {
    delete event.currentTarget.dataset.lens;
  };
  return (
    <Link className="home-split-picture" href={href} aria-hidden="true" tabIndex={-1} onPointerEnter={place} onPointerMove={place} onPointerLeave={leave}>
      <span className="home-split-photo" />
      <span className="home-split-lens">
        <span className="home-split-lens-view is-photo" />
        <span className="home-split-lens-view is-field" />
      </span>
    </Link>
  );
}
