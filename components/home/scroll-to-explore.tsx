"use client";

import { ArrowDown } from "lucide-react";

/** "Scroll to explore" (ADR-0077 amendments 22 and 24): a small button in the bottom right corner of the hero's clip, the
 * words and then a down arrow in a square outline, as Scale's home page sets its own. It is hidden
 * while the hero's words stand and comes up once they have left (components/home/hero-outro.tsx marks the hero
 * `data-words="gone"`; app/home.css shows the button then). A visitor who asked for reduced motion keeps the words and sees
 * the button from the start. One press scrolls the page to the section that follows the hero; the page's own scrolling is
 * not taken over. */
export function ScrollToExplore() {
  function explore() {
    // The section that follows the hero, whatever it is: brought to the window's top, or to its middle if it is shorter
    // than the window.
    const next = document.getElementById("overview")?.nextElementSibling;
    if (!next) return;
    const box = next.getBoundingClientRect();
    const top = box.top + window.scrollY - Math.max(0, (window.innerHeight - box.height) / 2);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: Math.round(top), behavior: reduced ? "auto" : "smooth" });
  }
  return (
    <button type="button" className="home-hero-explore" onClick={explore}>
      <span>Scroll to explore</span>
      <span className="home-hero-explore-box" aria-hidden="true">
        <ArrowDown strokeWidth={1.5} />
      </span>
    </button>
  );
}
