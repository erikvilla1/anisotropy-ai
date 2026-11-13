"use client";

import type { MouseEvent } from "react";
import { ArrowDown } from "lucide-react";

/** "Scroll to explore" (ADR-0077 amendments 22, 24 and 32; Kai's words, kept by the founder on 2026-11-13): a small link in the
 * bottom right corner of the hero's clip, the words and then a down arrow in a square outline. It is hidden while the hero's
 * words stand and comes up once they have left (components/home/hero-outro.tsx marks the hero `data-words="gone"`; app/home.css
 * shows it then). A visitor who asked for reduced motion keeps the words and sees the link from the start. It is a link to the
 * product demo (components/home/product-demo.tsx, ADR-0095), so it works without a script; with one, the page scrolls to the
 * section that follows the hero and the focus moves to the demo's heading, so a keyboard or a screen reader carries on from
 * there. The page's own scrolling is not taken over. */
export function ScrollToExplore() {
  function explore(event: MouseEvent<HTMLAnchorElement>) {
    // The section that follows the hero, whatever it is: brought to the window's top, or to its middle if it is shorter
    // than the window.
    const next = document.getElementById("overview")?.nextElementSibling;
    if (!next) return;
    event.preventDefault();
    const box = next.getBoundingClientRect();
    const top = box.top + window.scrollY - Math.max(0, (window.innerHeight - box.height) / 2);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: Math.round(top), behavior: reduced ? "auto" : "smooth" });
    document.getElementById("demo-title")?.focus({ preventScroll: true });
  }
  return (
    <a className="home-hero-explore" href="#demo" onClick={explore}>
      <span>Scroll to explore</span>
      <span className="home-hero-explore-box" aria-hidden="true">
        <ArrowDown strokeWidth={1.5} />
      </span>
    </a>
  );
}
