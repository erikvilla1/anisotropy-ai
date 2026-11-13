import { test, expect, type Page } from "@playwright/test";

// The home page's hero. The laminate calculator and its tour left the page on 2026-11-13 (ADR-0094); the cases that read
// them, and the tour's own browser cases, went with them; they are in the history before that commit.

/** Every request the page makes to the API, so a case can say the page asks the engine for nothing. */
function apiRequests(page: Page): string[] {
  const asked: string[] = [];
  page.on("request", (request) => {
    if (/\/v1\//.test(new URL(request.url()).pathname)) asked.push(request.url());
  });
  return asked;
}

test("the hero opens the page, and the laminate calculator and its tour are not on it (ADR-0094)", async ({ page }) => {
  const asked = apiRequests(page);
  await page.goto("/");
  expect(await page.locator("main > *").first().getAttribute("id")).toBe("overview");
  await expect(page.locator("main").locator("h1, h2").first()).toHaveText(/one engineering platform\s*for composite theory/);
  await expect(page.locator("#laminate, #tour")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Your layup, calculated." })).toHaveCount(0);
  // With the calculator gone the page asks the engine for nothing.
  await page.waitForTimeout(1200);
  expect(asked).toEqual([]);
});

const STATEMENT = /^\s*one engineering platform\s*for composite theory\s*and real test data\s*$/;

test("the hero's words are one statement and a row of the year, the mark and the name (ADR-0077 amendments 19, 21, 27 and 28)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText(STATEMENT);
  await expect(hero.getByRole("heading", { level: 1 })).toHaveCSS("text-transform", "uppercase");
  // The row under it: the year, the triangle, the name (amendment 28).
  await expect(hero.locator(".home-hero-note")).toHaveText("Established 2026");
  await expect(hero.locator(".home-hero-tagline")).toHaveText("Anisotropy");
  const row = await hero.evaluate((el) => ["note", "mark", "tagline"].map((part) => Math.round(el.querySelector(`.home-hero-${part}`)!.getBoundingClientRect().left)));
  expect(row[0]).toBeLessThan(row[1]);
  expect(row[1]).toBeLessThan(row[2]);
  // The cohort stands beside the mark of the place that runs it, in the clip's bottom left corner.
  await expect(hero.getByAltText("UC San Diego, The Basement")).toBeVisible();
  await expect(hero.locator(".home-hero-backed .home-hero-cohort")).toHaveText("Fall 2026 Launchpad cohort");
  // No 3D view, chat box or link in the hero: the header's Workspace button is the way in. Its one button, "Scroll to explore", is hidden while the words stand (tests/browser/intro.spec.ts).
  await expect(hero.getByRole("button", { includeHidden: true })).toHaveCount(1);
  await expect(hero.locator("canvas, [data-testid='laminate-scene']")).toHaveCount(0);
  await expect(hero.getByRole("textbox")).toHaveCount(0);
  await expect(hero.getByRole("link")).toHaveCount(0);
  // The header lies over the hero's black ground on the home page; elsewhere it is the same header in the page's flow, 84 px
  // tall, with its links in the middle of the page (ADR-0077 amendments 8 and 19).
  await expect(page.locator(".site-header")).toHaveCSS("position", "absolute");
  await page.goto("/about");
  await expect(page.locator(".site-header")).toHaveCSS("position", "relative");
  await expect(page.locator(".site-header")).toHaveCSS("height", "84px");
  const nav = await page.locator(".site-header .main-nav").evaluate((el) => {
    const box = el.getBoundingClientRect();
    return Math.round(box.left + box.width / 2);
  });
  expect(Math.abs(nav - page.viewportSize()!.width / 2)).toBeLessThanOrEqual(1);
});

test("the hero's clip plays in a square box on the black page, under the header, with the words in its middle (ADR-0077 amendment 19)", async ({ page }) => {
  await page.goto("/");
  const rect = (selector: string) => page.locator(selector).first().evaluate((el) => {
    const box = el.getBoundingClientRect();
    return { left: Math.round(box.left), top: Math.round(box.top), right: Math.round(box.right), bottom: Math.round(box.bottom) };
  });
  const viewport = page.viewportSize()!;
  const clip = await rect("#overview .home-hero-media");
  const header = await rect(".site-header");
  // The box stands on the page's 32 px margin at the sides and the foot, and starts under the header.
  expect([clip.left, viewport.width - clip.right, viewport.height - clip.bottom]).toEqual([32, 32, 32]);
  expect(clip.top).toBe(header.bottom);
  expect(clip.left).toBe((await rect(".site-header .wordmark")).left);
  await expect(page.locator("#overview .home-hero-media")).toHaveCSS("border-radius", "0px");
  // The page around it is the site's black, and the words sit inside the box, the statement and the mark on its middle line.
  expect(await page.locator("#overview").evaluate((el) => getComputedStyle(el, "::before").backgroundColor)).toBe("rgb(0, 0, 0)");
  for (const selector of ["#overview h1", "#overview .home-hero-row", "#overview .home-hero-backed"]) {
    const part = await rect(selector);
    expect(part.left, selector).toBeGreaterThanOrEqual(clip.left + 16);
    expect(part.right, selector).toBeLessThanOrEqual(clip.right - 16);
    expect(part.top, selector).toBeGreaterThanOrEqual(clip.top + 16);
    expect(part.bottom, selector).toBeLessThanOrEqual(clip.bottom - 16);
  }
  for (const selector of ["#overview h1", "#overview .home-hero-mark"]) {
    const part = await rect(selector);
    expect(Math.abs((part.left + part.right) / 2 - viewport.width / 2), selector).toBeLessThanOrEqual(1);
  }
  // On a phone the box follows the narrower margin.
  await page.setViewportSize({ width: 390, height: 844 });
  const phone = await rect("#overview .home-hero-media");
  expect([phone.left, 390 - phone.right]).toEqual([20, 20]);
  expect(phone.top).toBeGreaterThanOrEqual((await rect(".site-header")).bottom);
});

test("the hero's lens is hidden for now (ADR-0071 amendment 1)", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#overview .home-hero-lens")).toHaveCount(0);
  // The recording stays committed, ready for the lens's return.
  expect((await page.request.get("/assets/hero-lens/lens.mp4")).status()).toBe(200);
});

test("the home page fits a phone without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator("#overview h1")).toBeVisible();
  await page.locator("#mission").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
