import { test, expect, type Page } from "@playwright/test";

// The load-in (ADR-0070 amendment 1): the page starts under a black veil, the veil lifts once the hero's text is ready, the
// headline rises and the paragraphs are typed in by a copy laid over the page's own text. The veil and the copies are read on
// every frame from the first paint, because they are gone again within a few seconds.

type Frame = {
  path: string;
  phase: string;
  shown: boolean; // the veil is displayed at all
  opacity: number;
  colour: string;
  copies: number; // the copies that play the moves
  hiddenCopies: number; // of those, the ones hidden from assistive technology
  running: number; // elements whose own text is transparent while a copy plays
  ownHeadline: string; // the headline's own text nodes, without any copy
};

async function record(page: Page) {
  await page.addInitScript(() => {
    const frames: unknown[] = [];
    (window as unknown as { __intro: unknown[] }).__intro = frames;
    const tick = () => {
      const veil = document.querySelector(".page-transition");
      if (veil) {
        const style = getComputedStyle(veil);
        const headline = document.querySelector("#overview h1");
        const copies = Array.from(document.querySelectorAll(".intro-overlay"));
        frames.push({
          path: location.pathname,
          phase: veil.className.replace("page-transition ", ""),
          shown: style.display !== "none",
          opacity: Number(style.opacity),
          colour: style.backgroundColor,
          copies: copies.length,
          hiddenCopies: copies.filter((copy) => copy.getAttribute("aria-hidden") === "true" && copy.hasAttribute("inert")).length,
          running: document.querySelectorAll("[data-intro-run]").length,
          ownHeadline: headline
            ? Array.from(headline.childNodes)
                .filter((node) => node.nodeType === Node.TEXT_NODE)
                .map((node) => node.nodeValue)
                .join(" ")
            : "",
        });
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

/** The frames read since the last call, after two more have been read so the latest state is among them. */
const frames = (page: Page) =>
  page.evaluate(async () => {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const store = window as unknown as { __intro: Frame[] };
    const taken = store.__intro.slice();
    store.__intro.length = 0;
    return taken;
  });

const paragraphs = [
  "We're bringing composite theory and real test data into one engineering platform, changing how laminates and coupons are set up, analyzed and documented.",
  "Spend less time on setup and reports. Spend more time on the structure. Trace every number back to its source.",
];

async function expectHeroWhole(page: Page) {
  const hero = page.locator("#overview");
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero.locator("[data-intro-run]")).toHaveCount(0);
  await expect(hero.locator("h1")).toHaveText("Composites.Calculated.");
  await expect(hero.locator("h1")).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(hero.locator(".home-hero-copy p")).toHaveText(paragraphs);
  for (const paragraph of await hero.locator(".home-hero-copy p").all()) await expect(paragraph).toHaveCSS("color", "rgb(244, 244, 244)");
}

test("the home page loads out of black and the hero's words are typed in (ADR-0070 amendment 1)", async ({ page }) => {
  await record(page);
  await page.goto("/");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await expectHeroWhole(page);
  await expect(veil).toHaveCSS("opacity", "0");
  const seen = await frames(page);
  // The first paint is black, #010101.
  expect(seen[0]).toMatchObject({ phase: "is-enter", shown: true, opacity: 1, colour: "rgb(1, 1, 1)", copies: 0 });
  // The headline and the two paragraphs are made ready while the black still covers the page, so the finished text is never
  // seen before its move: a copy each, hidden from assistive technology, over the page's own text, which stays in place.
  const ready = seen.findIndex((frame) => frame.copies > 0);
  expect(ready).toBeGreaterThan(0);
  expect(seen[ready]).toMatchObject({ opacity: 1, copies: 3, hiddenCopies: 3, running: 3, ownHeadline: "Composites. Calculated." });
  expect(seen.slice(0, ready).every((frame) => frame.opacity === 1)).toBe(true);
  // The copies go once the moves have played: the headline's 1.6 s, with room for a busy machine.
  const lifting = seen.findIndex((frame) => frame.phase === "is-lift");
  const gone = seen.findIndex((frame, index) => index > ready && frame.copies === 0);
  expect(lifting).toBeGreaterThanOrEqual(ready);
  expect(gone).toBeGreaterThan(lifting);
  expect(seen.slice(ready, gone).every((frame) => frame.ownHeadline === "Composites. Calculated.")).toBe(true);
  expect(seen[seen.length - 1]).toMatchObject({ phase: "is-idle", opacity: 0, copies: 0, running: 0 });
});

test("a header link goes to its page at once, Back too, and only the home page's first load is veiled (ADR-0070 amendment 3)", async ({ page }) => {
  await record(page);
  await page.goto("/");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await frames(page);
  await page.locator(".site-header a[href='/about']").first().click();
  await expect(page).toHaveURL(/\/about\/?$/);
  await page.waitForTimeout(600);
  const forward = await frames(page);
  // No fade to black before the next page and none after it: every frame from the click on shows the page.
  expect(forward.some((frame) => frame.path.startsWith("/about"))).toBe(true);
  expect(forward.every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(page.locator("#overview h1")).toBeVisible();
  await page.waitForTimeout(600);
  const back = await frames(page);
  expect(back.every((frame) => frame.phase === "is-idle" && frame.opacity === 0 && frame.copies === 0)).toBe(true);
  await expectHeroWhole(page);
  // Another page loaded on its own starts without the veil, from its first frame.
  await page.goto("/about");
  await page.waitForTimeout(300);
  const direct = await frames(page);
  expect(direct.length).toBeGreaterThan(0);
  expect(direct.every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
});

test.describe("for a visitor who asks for reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("there is no veil and no typing: everything is there at once (ADR-0070 amendment 1)", async ({ page }) => {
    await record(page);
    await page.goto("/");
    await expectHeroWhole(page);
    await expect(page.locator(".page-transition")).toBeHidden();
    await page.waitForTimeout(1500);
    const seen = await frames(page);
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((frame) => !frame.shown && frame.copies === 0 && frame.running === 0)).toBe(true);
    await expectHeroWhole(page);
  });
});
