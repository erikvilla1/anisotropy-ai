import type { Page } from "@playwright/test";

/** Turns the mouse wheel by `deltaY` pixels, as `page.mouse.wheel(0, deltaY)` does in Chromium and WebKit. Firefox scrolls at
 * most about a page for one wheel event, whatever it asks (Firefox's own rule; 866 px of a 1,000 px window on a CI runner), so
 * there the turn is sent a little under a window at a time, one event after another, as a quick hand on a wheel sends it
 * (ADR-0114). */
export async function wheel(page: Page, deltaY: number) {
  const firefox = page.context().browser()?.browserType().name() === "firefox";
  const most = firefox ? Math.max(100, Math.floor((page.viewportSize()?.height ?? 800) * 0.75)) : Infinity;
  let left = deltaY;
  do {
    const part = Math.sign(left) * Math.min(Math.abs(left), most);
    await page.mouse.wheel(0, part);
    left -= part;
  } while (left !== 0);
}
