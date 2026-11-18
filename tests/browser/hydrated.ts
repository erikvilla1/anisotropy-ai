import { expect, type Locator } from "@playwright/test";

/** Waits until React has taken `element` over from the page's prepared HTML; it then carries React's `__reactProps$…` key.
 * A line typed into a box before then is lost: React keeps its own empty value, and the box is empty again at its next render
 * (a click is replayed once the page has hydrated; typing is not). WebKit in Playwright's image got there 1.2 s after the
 * page's load event, and lost the line each time (ADR-0114). */
export const hydrated = (element: Locator) =>
  expect
    .poll(() => element.evaluate((node) => Object.keys(node).some((key) => key.startsWith("__reactProps$"))), { timeout: 15_000 })
    .toBe(true);
