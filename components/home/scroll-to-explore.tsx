"use client";

import { ArrowDown } from "lucide-react";

/** "Scroll to explore" (ADR-0077 amendments 22 and 24): a small button in the bottom right corner of the hero's clip, the
 * words and then a down arrow in a square outline, as Scale's home page sets its own. It is hidden
 * while the hero's words stand and comes up once they have left (components/home/hero-outro.tsx marks the hero
 * `data-words="gone"`; app/home.css shows the button then). A visitor who asked for reduced motion keeps the words and sees
 * the button from the start. One press scrolls the page to the tour (components/home/demo-tour.tsx), whose first step
 * plays when its stage fills the window; the page's own scrolling is not taken over. */
export function ScrollToExplore() {
  function explore() {
    const tour = document.getElementById("tour");
    if (!tour) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: Math.round(tour.getBoundingClientRect().top + window.scrollY), behavior: reduced ? "auto" : "smooth" });
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
