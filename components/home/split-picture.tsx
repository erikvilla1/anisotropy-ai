"use client";

import type { PointerEvent } from "react";

/** A band's picture on the home page (ADR-0077 amendments 37, 48 and 53): the material photograph in black and white, and
 * under a mouse's pointer a small lens that shows the same photograph in the demo's colours. It is a picture and not a
 * link (amendment 53 ended amendment 39's): it leads nowhere, does not move under the pointer, and the pointer over it is
 * a crosshair, the lens's own. The band's worded link beside it is the way to the page, so the picture is hidden from
 * assistive technology and takes no focus.
 *
 * The lens is a picture effect and nothing more: the photograph's own light and dark, smoothed, drawn through the scale the
 * demo colours its analysis with (blue for the darkest, red for the lightest; the filter is `#home-fea` in app/page.tsx),
 * laid as colour over the photograph itself so the weave still shows, with a faint mesh of lines over it. It measures
 * nothing and states nothing: no number, no legend, no caption. It follows the pointer a little behind it, keeps inside the
 * picture, and is not there for a finger or the keyboard. The stylesheet (app/home.css) draws it from the place this writes
 * on the element as `--lens-x` and `--lens-y`. */
export function SplitPicture() {
  const place = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "touch") return;
    const picture = event.currentTarget;
    const lens = picture.querySelector<HTMLElement>(".home-split-lens");
    if (!lens) return;
    const box = picture.getBoundingClientRect();
    const wide = lens.offsetWidth, tall = lens.offsetHeight;
    const x = Math.min(picture.offsetWidth - wide, Math.max(0, event.clientX - box.left - wide / 2));
    const y = Math.min(picture.offsetHeight - tall, Math.max(0, event.clientY - box.top - tall / 2));
    picture.style.setProperty("--lens-wide", `${picture.offsetWidth}px`);
    picture.style.setProperty("--lens-tall", `${picture.offsetHeight}px`);
    picture.style.setProperty("--lens-x", `${x.toFixed(1)}px`);
    picture.style.setProperty("--lens-y", `${y.toFixed(1)}px`);
    picture.dataset.lens = "on";
  };
  const leave = (event: PointerEvent<HTMLDivElement>) => {
    delete event.currentTarget.dataset.lens;
  };
  return (
    <div className="home-split-picture" aria-hidden="true" onPointerEnter={place} onPointerMove={place} onPointerLeave={leave}>
      <span className="home-split-photo" />
      <span className="home-split-lens">
        <span className="home-split-lens-view is-photo" />
        <span className="home-split-lens-view is-field" />
      </span>
    </div>
  );
}
