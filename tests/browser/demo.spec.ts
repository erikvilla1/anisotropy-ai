import { test, expect, type Page } from "@playwright/test";
import run from "../../lib/demo-run.json";
import { bannedIn } from "../../lib/studio-copy";

// The product demo under the hero (ADR-0094): a box the size of the hero's clip, black as the page is (amendment 2), in which the coupon workspace is shown in
// four beats from one recorded run of the solver. The page scrolls to the box as any page does; once the box stands in the
// window one scroll gesture plays one whole beat. `data-stop` on the box says where the demo's clock stands (0 while
// the box is empty, 1 to 4 at the end of each beat) and `data-moving` is there while a beat plays.

// The four beats take 4.4, 3.2, 5.6 and 2.8 s, and several cases play all of them.
test.describe.configure({ timeout: 120_000 });

const demo = (page: Page) => page.locator("#demo");
const box = (page: Page) => page.locator("#demo .product-demo-box");
const beat = (page: Page, id: string) => box(page).locator(`[data-beat="${id}"]`);
/** How far the stage's top edge is from where it holds the window: the window's top, for a stage a window tall (the formula
 * is the middle's, which is the same line). */
const offLine = (page: Page) => box(page).evaluate((element) => {
  const rect = element.getBoundingClientRect();
  return Math.round(rect.top - Math.round((window.innerHeight - rect.height) / 2));
});
const scrollY = (page: Page) => page.evaluate(() => Math.round(window.scrollY));
async function expectStop(page: Page, stop: number) {
  await expect(box(page)).toHaveAttribute("data-stop", String(stop), { timeout: 15_000 });
  await expect(box(page)).not.toHaveAttribute("data-moving", "true");
}
const notch = (page: Page, direction: 1 | -1 = 1) => page.mouse.wheel(0, 100 * direction);
/** Scrolls the page down onto the box's line with the one wheel event that asks for all that is left, and waits for the first beat. */
async function reachBox(page: Page) {
  await page.mouse.wheel(0, await offLine(page));
  await expectStop(page, 1);
  expect(await offLine(page)).toBe(0);
  await page.waitForTimeout(350);
}
async function playTo(page: Page, stop: number) {
  let at = Number(await box(page).getAttribute("data-stop"));
  if (at === 0 && stop > 0) {
    await reachBox(page);
    at = 1;
  }
  for (; at < stop; at++) {
    await notch(page);
    await expectStop(page, at + 1);
  }
}
/** A trackpad swipe as the page gets it, sent in one go; returns how many of its wheel events the demo took from the browser. */
const swipe = (page: Page, direction: 1 | -1 = 1) =>
  page.evaluate((sign) => {
    let taken = 0;
    for (const size of [4, 18, 46, 80, 96, 90, 78, 66, 55, 46, 38, 31, 26, 21, 17, 14, 11, 9, 7, 6, 5, 4, 3, 2, 2, 1, 1, 1]) {
      const event = new WheelEvent("wheel", { deltaY: sign * size, bubbles: true, cancelable: true });
      document.body.dispatchEvent(event);
      if (event.defaultPrevented) taken += 1;
    }
    return taken;
  }, direction);
async function openPinned(page: Page) {
  await page.goto("/");
  await expect(demo(page)).toHaveAttribute("data-mode", "pinned");
  await expectStop(page, 0);
  const viewport = page.viewportSize()!;
  await page.mouse.move(viewport.width / 2, viewport.height / 2);
}
const kilonewtons = (newtons: number) => (newtons / 1000).toFixed(1);

test("the demo is a black stage under the hero, as wide as the clip and a window tall", async ({ page }) => {
  await openPinned(page);
  const rects = await page.evaluate(() => {
    const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; };
    return { clip: rect("#overview .home-hero-media"), box: rect("#demo .product-demo-box"), section: rect("#demo"), next: rect("#mission") };
  });
  // As wide as the clip, a window tall, straight after the hero (whose own foot is the 32 px of black under the clip), and
  // followed at once by the next band.
  expect([rects.box.left, rects.box.right]).toEqual([rects.clip.left, rects.clip.right]);
  expect(rects.box.height).toBe(page.viewportSize()!.height);
  expect(rects.box.top - rects.clip.bottom).toBe(32);
  expect(rects.next.top).toBe(rects.box.bottom);
  await expect(box(page)).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(demo(page)).toHaveCSS("background-color", "rgb(0, 0, 0)");
  // The order of the page: the hero, the demo, then the bands.
  const order = await page.locator("main > *").evaluateAll((elements) => elements.map((element) => element.id).filter(Boolean));
  expect(order.slice(0, 3)).toEqual(["overview", "demo", "mission"]);
  // There is no timeline in it, and it asks nothing of the API.
  await expect(box(page).locator("[class*='rail'], [class*='tick']")).toHaveCount(0);
});

test("the page scrolls to the box as any page does; the box comes up empty and the first beat plays once it fills the window", async ({ page }) => {
  const asked: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/v1/")) asked.push(request.url()); });
  await openPinned(page);
  // A notch moves the page by what it asks for. Nothing is carried and nothing plays.
  await notch(page);
  await expect.poll(() => scrollY(page)).toBe(100);
  await page.waitForTimeout(500);
  expect(await scrollY(page)).toBe(100);
  await expectStop(page, 0);
  for (const part of [".product-demo-view", ".product-demo-beats", ".product-demo-recorded"]) await expect(box(page).locator(part), part).toHaveCSS("opacity", "0");
  // Notch by notch: the page keeps to the wheel and the box stays empty.
  for (let guard = 0; (await offLine(page)) > 100 && guard < 30; guard++) {
    const before = await scrollY(page);
    await notch(page);
    await expect.poll(() => scrollY(page)).toBe(before + 100);
    await expect(box(page)).not.toHaveAttribute("data-moving", "true");
  }
  await expectStop(page, 0);
  const left = await offLine(page);
  expect(left).toBeGreaterThan(0);
  expect(left).toBeLessThanOrEqual(100);
  // The notch that would pass the line is stopped on it: the stage fills the window, and the first beat plays.
  await notch(page);
  await expect(box(page)).toHaveAttribute("data-moving", "true");
  await expectStop(page, 1);
  expect(await offLine(page)).toBe(0);
  const placed = await box(page).evaluate((element) => { const r = element.getBoundingClientRect(); return [Math.round(r.top), Math.round(window.innerHeight - r.bottom)]; });
  expect(placed[0]).toBe(placed[1]);
  for (const part of [".product-demo-view", ".product-demo-beats"]) await expect(box(page).locator(part), part).toHaveCSS("opacity", "1");
  // The first beat: the assistant's question, the material picked, the standard, and the layup typed.
  await expect(beat(page, "describe")).toHaveAttribute("data-active", "true");
  await expect(beat(page, "describe").getByRole("heading", { level: 3 })).toHaveText("Describe the coupon.");
  const assistant = page.getByTestId("demo-assistant");
  await expect(assistant).toContainText("Which material?");
  await expect(assistant.locator(".demo-chips li")).toHaveCount(4);
  await expect(assistant.locator(".demo-chips li[data-picked]")).toHaveText("IM7 / 8552");
  await expect(assistant).toContainText("ASTM D3039");
  await expect(page.getByTestId("demo-layup")).toHaveText(run.coupon.layup);
  expect(asked).toEqual([]);
});

test("each gesture plays one whole beat, a swipe's burst plays one, and the analysis shows the recorded field with its legend and what it found", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await openPinned(page);
  await playTo(page, 1);
  const held = await scrollY(page);
  // A swipe is one gesture: every one of its events is taken, and one beat plays.
  expect(await swipe(page)).toBe(28);
  await expectStop(page, 2);
  await expect(beat(page, "model")).toHaveAttribute("data-active", "true");
  const summary = page.getByTestId("demo-summary");
  await expect(summary.locator("[data-filled]")).toHaveCount(5);
  await expect(summary).toContainText("unnotched tension");
  await expect(summary).toContainText(`${run.coupon.length} × ${run.coupon.width} mm, per D3039`);
  await expect(summary).toContainText(`${run.summary.elements} elements`);
  await page.waitForTimeout(700);
  await expectStop(page, 2);
  expect(await scrollY(page)).toBe(held);
  // Three notches, two of them while the beat plays: one beat.
  await notch(page);
  await expect(box(page)).toHaveAttribute("data-moving", "true");
  await notch(page);
  await notch(page);
  await expectStop(page, 3);
  await page.waitForTimeout(700);
  await expectStop(page, 3);
  // The analysis: the run's five stages done, the field's legend in its unit, the first ply to fail, and what the demo is.
  const analysis = page.getByTestId("demo-run");
  await expect(analysis.locator(".demo-stages li")).toHaveText(["Queued", "Meshing", "Solving", "Post-processing", "Report ready"]);
  await expect(analysis.locator(".demo-stages li[data-state='done']")).toHaveCount(5);
  const legend = page.getByTestId("demo-legend");
  await expect(legend).toHaveCSS("opacity", "1");
  await expect(legend).toContainText(`Stress along the fibres, ${run.field.unit}`);
  const bound = Math.round(Math.max(-run.field.min, run.field.max));
  await expect(legend.locator(".demo-legend-ends span")).toHaveText([String(-bound), "0", String(bound)]);
  const first = run.summary.first_failure;
  const result = page.getByTestId("demo-result");
  await expect(result).toHaveCSS("opacity", "1");
  await expect(result).toContainText(`First ply to fail: ply ${first.ply} (${first.angle}°), in ${first.mode} ${first.place}.`);
  await expect(result).toContainText(`${kilonewtons(run.summary.reaction)} kN`);
  await expect(result).toContainText(`${first.applied.toFixed(2)} ${first.applied_unit} (${kilonewtons(first.reaction)} kN)`);
  await expect(page.getByTestId("demo-recorded")).toHaveText(`A recorded run of the public IM7 / 8552 tension example · version ${run.solver_version} · ${run.recorded}`);
  await expect(page.getByTestId("demo-recorded")).toHaveCSS("opacity", "1");
  await expect(box(page).locator("canvas")).toBeVisible();
  // The last beat: the files a run writes, by the workspace's names, and the way into the workspace.
  await notch(page);
  await expectStop(page, 4);
  const report = page.getByTestId("demo-report");
  await expect(report.locator(".demo-files li[data-shown]")).toHaveText(["Report (PDF)", "Full package (ZIP)", "Solver input (.inp)"]);
  await expect(report.getByRole("link", { name: "Open the workspace" })).toHaveAttribute("href", /\/workspace\/fea\/?$/);
  // A swipe up plays a beat backwards.
  expect(await swipe(page, -1)).toBe(28);
  await expectStop(page, 3);
  expect(await scrollY(page)).toBe(held);
  expect(errors).toEqual([]);
});

test("nothing the demo shows is a word the product's view bans", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(demo(page)).toHaveAttribute("data-mode", "static");
  const text = await demo(page).innerText();
  expect(text.length).toBeGreaterThan(400);
  expect(bannedIn(text)).toEqual([]);
});

test("a beat takes its own time: the second about 3.2 s, measured in the page", async ({ page }) => {
  await openPinned(page);
  await playTo(page, 1);
  await page.evaluate(() => {
    const stage = document.querySelector<HTMLElement>("#demo .product-demo-box")!;
    const marks = { start: 0, end: 0 };
    (window as unknown as { __beat: typeof marks }).__beat = marks;
    new MutationObserver(() => {
      if (stage.dataset.moving && !marks.start) marks.start = performance.now();
      if (!stage.dataset.moving && marks.start && !marks.end) marks.end = performance.now();
    }).observe(stage, { attributes: true, attributeFilter: ["data-moving"] });
  });
  await notch(page);
  await expectStop(page, 2);
  const marks = await page.evaluate(() => (window as unknown as { __beat: { start: number; end: number } }).__beat);
  expect(marks.end - marks.start).toBeGreaterThan(3000);
  expect(marks.end - marks.start).toBeLessThan(4400);
});

test("up from the first beat and down from the last the page scrolls as any page does, and on the way back up the box is passed", async ({ page }) => {
  await openPinned(page);
  await playTo(page, 1);
  const held = await scrollY(page);
  // Up from the first beat: the page moves, and the box keeps its first beat while part of it shows.
  await notch(page, -1);
  await expect.poll(() => scrollY(page)).toBe(held - 100);
  await page.waitForTimeout(400);
  await expectStop(page, 1);
  // Down again: the box holds the window, and the first beat is not played twice.
  await notch(page);
  await expect.poll(() => offLine(page)).toBe(0);
  await page.waitForTimeout(400);
  await expectStop(page, 1);
  await playTo(page, 4);
  // Past the last beat nothing takes the scroll over.
  await page.waitForTimeout(350);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(held + 240);
  await page.waitForTimeout(300);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(held + 480);
  await expectStop(page, 4);
  // Back up: the page keeps to the wheel across the box's line and on, and the demo stays at its end.
  await page.waitForTimeout(300);
  await page.mouse.wheel(0, -720);
  await expect.poll(() => scrollY(page)).toBe(held - 240);
  await page.waitForTimeout(500);
  expect(await scrollY(page)).toBe(held - 240);
  await expectStop(page, 4);
  // All the way up, out of sight: the demo is at its start again.
  await page.mouse.wheel(0, -(held - 240));
  await expect.poll(() => scrollY(page)).toBe(0);
  await expectStop(page, 0);
});

test("Scroll to explore brings the stage to fill the window, and the first beat plays", async ({ page }) => {
  await page.goto("/");
  await expect(demo(page)).toHaveAttribute("data-mode", "pinned");
  const explore = page.locator("#overview .home-hero-explore");
  await expect(explore).toBeVisible({ timeout: 15_000 });
  await explore.click();
  await expect.poll(() => offLine(page), { timeout: 10_000 }).toBe(0);
  await expectStop(page, 1);
});

test.describe("on a touch screen", () => {
  test.use({ hasTouch: true });

  test("a finger scrolls the page to the box, which then holds; a swipe plays one beat, and at the last it scrolls the page on", async ({ page }) => {
    await openPinned(page);
    const client = await page.context().newCDPSession(page);
    const drag = async (x: number, from: number, to: number) => {
      await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: from }] });
      for (let part = 1; part <= 10; part++) {
        await client.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: from + ((to - from) * part) / 10 }] });
        await page.waitForTimeout(16);
      }
      await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    };
    await drag(300, 700, 400);
    await expect.poll(() => scrollY(page)).toBeGreaterThan(150);
    await expectStop(page, 0);
    for (let guard = 0; (await offLine(page)) > 1 && guard < 10; guard++) await drag(300, 700, 400);
    await expectStop(page, 1);
    // On its line to the pixel the driver holds to: a finger leaves the page between two whole pixels.
    expect(Math.abs(await offLine(page))).toBeLessThanOrEqual(1);
    await page.waitForTimeout(350);
    const held = await scrollY(page);
    await drag(700, 600, 300);
    await expectStop(page, 2);
    await drag(300, 300, 600);
    await expectStop(page, 1);
    expect(await scrollY(page)).toBe(held);
    await playTo(page, 4);
    await drag(700, 600, 300);
    await expect.poll(() => scrollY(page)).toBeGreaterThan(held + 100);
    await expectStop(page, 4);
  });
});

test("with reduced motion the beats lie one under another in the box, finished, and no gesture is taken", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(demo(page)).toHaveAttribute("data-mode", "static");
  expect(await box(page).getAttribute("data-stop")).toBeNull();
  await expect(box(page)).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await page.mouse.move(700, 500);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(240);
  await expect(demo(page).getByRole("heading", { level: 2 })).toHaveText("A coupon analysis, set up for you.");
  for (const title of ["Describe the coupon.", "The model builds itself.", "Run the analysis.", "It comes with the report."]) await expect(demo(page).getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByTestId("demo-layup")).toHaveText(run.coupon.layup);
  await expect(page.getByTestId("demo-summary").locator("[data-filled]")).toHaveCount(5);
  await expect(page.getByTestId("demo-run").locator(".demo-stages li[data-state='done']")).toHaveCount(5);
  await expect(page.getByTestId("demo-result")).toContainText("First ply to fail");
  await expect(page.getByTestId("demo-recorded")).toBeVisible();
  // The beats follow each other down the page.
  const tops = await demo(page).locator(".product-demo-beat").evaluateAll((beats) => beats.map((b) => b.getBoundingClientRect().top));
  expect([...tops].sort((a, b) => a - b)).toEqual(tops);
  expect(new Set(tops).size).toBe(4);
});

test("on a phone the demo is one column in the box and nothing overflows sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(demo(page)).toHaveAttribute("data-mode", "static");
  await page.locator("#mission").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const edges = await page.evaluate(() => {
    const frame = document.querySelector("#demo .product-demo-box")!.getBoundingClientRect();
    const cards = Array.from(document.querySelectorAll("#demo .demo-card")).map((card) => card.getBoundingClientRect());
    return { frame: [frame.left, frame.right], widest: Math.max(...cards.map((card) => card.right)), least: Math.min(...cards.map((card) => card.left)) };
  });
  expect(edges.frame).toEqual([20, 370]);
  expect(edges.least).toBeGreaterThanOrEqual(edges.frame[0]);
  expect(edges.widest).toBeLessThanOrEqual(edges.frame[1]);
});
