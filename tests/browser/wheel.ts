import type { Page } from "@playwright/test";

/** Turns the mouse wheel by `deltaY` pixels, as `page.mouse.wheel(0, deltaY)` does in Chromium, where the page is where the wheel
 * sent it by the next frame. The other two engines are let reach the same place (ADR-0114):
 * - Firefox scrolls at most about a page for one wheel event, whatever it asks (866 px of a 1,000 px window on a CI runner), so there
 *   the turn is sent a little under a window at a time, one event after another, as a quick hand on a wheel sends it.
 * - WebKit glides to where a wheel event sends it over about a tenth of a second, and a second event in that time retargets the glide
 *   instead of turning it: 900 px down then 100 px up is one glide to 800, never a move up. So there each event is let come to rest. */
export async function wheel(page: Page, deltaY: number) {
  const engine = page.context().browser()?.browserType().name();
  const most = engine === "firefox" ? Math.max(100, Math.floor((page.viewportSize()?.height ?? 800) * 0.75)) : Infinity;
  let left = deltaY;
  do {
    const part = Math.sign(left) * Math.min(Math.abs(left), most);
    await page.mouse.wheel(0, part);
    if (engine === "webkit") await atRest(page);
    left -= part;
  } while (left !== 0);
}

/** Waits until the page stops moving: two readings 50 ms apart that agree, once it has moved or 200 ms have gone by (a glide starts on
 * the next frame, and a wheel at the page's end moves nothing). Two seconds at most. */
async function atRest(page: Page) {
  const scrollY = () => page.evaluate(() => window.scrollY);
  const start = await scrollY();
  let last = start;
  for (let waited = 50; waited <= 2_000; waited += 50) {
    await page.waitForTimeout(50);
    const now = await scrollY();
    if (now === last && (now !== start || waited >= 200)) return;
    last = now;
  }
}
