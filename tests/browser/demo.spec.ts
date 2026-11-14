import { test, expect, type Page } from "@playwright/test";
import { demoWing } from "../../lib/demo-wing";
import { bannedIn } from "../../lib/studio-copy";

// The product demo under the hero (ADR-0095): a box the size of the hero's clip, black as the page is (amendment 2), in which one composite wing is shown in
// four beats from one recorded analysis (ADR-0098): whole, apart into its parts, analysed part by part, whole again. The page scrolls to the box as any page does; once the box stands in the
// window one scroll gesture plays one whole beat. `data-stop` on the box says where the demo's clock stands (0 while
// the box is empty, 1 to 4 at the end of each beat) and `data-moving` is there while a beat plays.

// The four beats take 3.2, 3.6, 4.8 and 3.2 s, and several cases play all of them.
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
// The record's analysis (scripts/demo-wing.py --solve). Without it the cases that read it fail, as they should.
const wing = { ...demoWing, field: demoWing.field!, solve: demoWing.solve!, load: demoWing.load! };
/** An end of the legend as the page prints it: a share as a percentage when the field has no unit. */
const legendEnd = (value: number) => (wing.field.unit ? String(Math.round(value)) : `${Math.round(value * 100)} %`);
const PARTS = ["UPPER SKIN", "LOWER SKIN", "FRONT SPAR", "REAR SPAR", "RIBS"];

test("the demo is a black stage as wide as the clip and a window tall, which starts half a window up behind the hero", async ({ page }) => {
  await openPinned(page);
  const rects = await page.evaluate(() => {
    const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; };
    return { clip: rect("#overview .home-hero-media"), box: rect("#demo .product-demo-box"), section: rect("#demo"), next: rect("#mission") };
  });
  // As wide as the clip, a window tall, and followed at once by the next band. With the page at its top it starts half a
  // window up, behind the hero, which lies over it (ADR-0095 amendment 4): half a window of scrolling brings it up.
  expect([rects.box.left, rects.box.right]).toEqual([rects.clip.left, rects.clip.right]);
  expect(rects.box.height).toBe(page.viewportSize()!.height);
  expect(rects.box.top).toBe(page.viewportSize()!.height / 2);
  // Until the demo has played through, the page ends at the stage (amendment 7): what follows is out of its height.
  await expect(page.locator("html")).toHaveAttribute("data-demo-gate", "true");
  const ends = await page.evaluate(() => [document.documentElement.scrollHeight, Math.round(window.scrollY + document.querySelector("#demo .product-demo-box")!.getBoundingClientRect().bottom)]);
  expect(ends[0]).toBe(ends[1]);
  expect(rects.next.height).toBeLessThanOrEqual(1);
  await expect(page.locator("#overview")).toHaveCSS("position", "sticky");
  const layers = await page.evaluate(() => ["#overview", "#demo"].map((selector) => Number(getComputedStyle(document.querySelector(selector)!).zIndex)));
  expect(layers[0]).toBeGreaterThan(layers[1]);
  await expect(page.locator("#overview")).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(box(page)).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(demo(page)).toHaveCSS("background-color", "rgb(0, 0, 0)");
  // The order of the page: the hero, the demo, then the bands.
  const order = await page.locator("main > .home-opening > *, main > *").evaluateAll((elements) => elements.map((element) => element.id).filter(Boolean));
  expect(order.slice(0, 3)).toEqual(["overview", "demo", "mission"]);
  // There is no timeline in it, and it asks nothing of the API.
  await expect(box(page).locator("[class*='rail'], [class*='tick']")).toHaveCount(0);
});

test("the page scrolls to the box as any page does; the box comes up with the first beat's words alone, and the first beat plays once it fills the window", async ({ page }) => {
  const asked: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/v1/")) asked.push(request.url()); });
  await openPinned(page);
  // A notch moves the page by what it asks for. Nothing is carried and nothing plays.
  await notch(page);
  await expect.poll(() => scrollY(page)).toBe(100);
  await page.waitForTimeout(500);
  expect(await scrollY(page)).toBe(100);
  await expectStop(page, 0);
  // The model waits for the first beat. The first beat's words wait too, while the hero's clip is still growing (amendments
  // 4 and 6), and no other beat's are up.
  await expect(box(page).locator(".product-demo-view")).toHaveCSS("opacity", "0");
  await expect(page.getByTestId("demo-recorded")).toHaveCount(0);
  const wordsIn = () => beat(page, "describe").evaluate((element) => Number(getComputedStyle(element).opacity));
  expect(await wordsIn()).toBe(0);
  for (const id of ["model", "analysis", "report"]) await expect(beat(page, id)).toHaveCSS("opacity", "0");
  await expect(page.getByTestId("demo-facts").locator("[data-filled]")).toHaveCount(0);
  // Notch by notch: the page keeps to the wheel and nothing plays; near the stage the words are on their way in.
  for (let guard = 0; (await offLine(page)) > 100 && guard < 30; guard++) {
    const before = await scrollY(page);
    await notch(page);
    await expect.poll(() => scrollY(page)).toBe(before + 100);
    await expect(box(page)).not.toHaveAttribute("data-moving", "true");
  }
  await expectStop(page, 0);
  expect(await wordsIn()).toBeGreaterThan(0);
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
  // The first beat: the wing whole, and what it is filled in beside it.
  await expect(beat(page, "describe")).toHaveAttribute("data-active", "true");
  await expect(beat(page, "describe").getByRole("heading", { level: 3 })).toHaveText("Start from the part.");
  const facts = page.getByTestId("demo-facts");
  await expect(facts.locator("[data-filled]")).toHaveCount(5);
  await expect(facts.locator("dt")).toHaveText(["PART", "SPAN", "CHORD", "MATERIAL", "STRUCTURE"]);
  await expect(facts).toContainText("2.13 m");
  await expect(facts).toContainText("IM7 / 8552");
  await expect(facts).toContainText("0.45 m at the root, 0.23 m at the tip");
  await expect(facts).toContainText("2 skins, 2 spars, 9 ribs");
  await expect(box(page).locator("canvas")).toBeVisible();
  expect(asked).toEqual([]);
});

test("on the way to the stage the hero stays in the window, its clip grows to the whole window and dims, then the first beat's words come up through it; the window is never empty (ADR-0095 amendments 4 to 6)", async ({ page }) => {
  await openPinned(page);
  const opening = page.locator(".home-opening");
  const read = () => page.evaluate(() => {
    const hero = document.getElementById("overview")!;
    const words = document.querySelector<HTMLElement>('.product-demo-beat[data-beat="describe"]')!;
    const style = getComputedStyle(hero);
    const box = words.getBoundingClientRect();
    const clip = hero.querySelector(".home-hero-media")!.getBoundingClientRect();
    return {
      // how far the clip's edges are from the window's: top, sides, foot
      clip: [clip.top, clip.left, window.innerWidth - clip.right, window.innerHeight - clip.bottom].map((edge) => Math.round(edge)),
      // "Scroll to explore", as the eye gets it: its own opacity times the hero's
      button: Number(getComputedStyle(hero.querySelector(".home-hero-explore")!).opacity),
      heroTop: Math.round(hero.getBoundingClientRect().top),
      hero: style.visibility === "hidden" ? 0 : Number(style.opacity),
      words: Number(getComputedStyle(words).opacity),
      wordsInWindow: box.top < window.innerHeight && box.bottom > 0,
    };
  });
  // The hero's words have left and "Scroll to explore" is up, as when a visitor starts to scroll.
  await expect(page.locator("#overview")).toHaveAttribute("data-words", "gone", { timeout: 15_000 });
  await expect(page.locator(".home-hero-explore")).toHaveCSS("opacity", "1");
  // At the top: the hero whole, the stage behind it, nothing of the demo's words yet.
  await expect(opening).toHaveAttribute("data-handover", "ready");
  expect(await read()).toMatchObject({ heroTop: 0, hero: 1, words: 0, clip: [84, 32, 32, 32] });
  // Down by the wheel in steps of a tenth of the way. The hero does not move. First its clip grows to the whole window, at
  // full strength and with nothing of the demo up (amendments 5 and 6); then it dims; and the first beat's words come in only
  // once it is well on its way to black. At every step something is on the screen: the clip, or the words, or both.
  const way = await offLine(page);
  expect(way).toBe(page.viewportSize()!.height / 2);
  let before = await read();
  for (let step = 1; step <= 9; step++) {
    await page.mouse.wheel(0, way / 10);
    await expect.poll(() => scrollY(page)).toBe(Math.round((way * step) / 10));
    await expect(opening).toHaveAttribute("data-handover", "going");
    await page.waitForTimeout(80);
    const now = await read();
    expect(now.heroTop, `the hero's place at ${step}/10`).toBe(0);
    expect(now.hero, `the hero at ${step}/10`).toBeLessThanOrEqual(before.hero);
    expect(now.words, `the words at ${step}/10`).toBeGreaterThanOrEqual(before.words);
    for (let edge = 0; edge < 4; edge++) expect(now.clip[edge], `the clip's edge ${edge} at ${step}/10`).toBeLessThanOrEqual(before.clip[edge]);
    if (step < 4) expect(now.clip[0], `the clip's top at ${step}/10`).toBeGreaterThan(0);
    else expect(now.clip, `the clip at ${step}/10`).toEqual([0, 0, 0, 0]);
    // growing: the clip at full strength, no words yet
    if (step <= 4) expect([now.hero, now.words], `growing at ${step}/10`).toEqual([1, 0]);
    // "Scroll to explore" goes as the clip grows and is gone once it is whole-window
    expect(now.button, `the button at ${step}/10`).toBeLessThan(before.button === 0 ? 0.001 : before.button);
    if (step >= 4) expect(now.button, `the button at ${step}/10`).toBe(0);
    // the words wait for the clip to be well on its way to black
    if (now.words > 0) expect(now.hero, `the clip when the words begin, at ${step}/10`).toBeLessThan(0.6);
    expect(now.hero > 0.3 || (now.words > 0.3 && now.wordsInWindow), `something on the screen at ${step}/10: ${JSON.stringify(now)}`).toBe(true);
    before = now;
  }
  expect(before.hero).toBeLessThan(0.2);
  expect(before.words).toBeGreaterThan(0.8);
  // The box is not moving yet: all of this was the scroll's.
  await expectStop(page, 0);
  // On the stage: the hero is out of the way, the words stand, and the first beat plays.
  await reachBox(page);
  await expect(opening).toHaveAttribute("data-handover", "done");
  await expect(page.locator("#overview")).toHaveCSS("visibility", "hidden");
  expect((await read()).words).toBe(1);
  // Back at the top the hero is whole again and the demo is at its start.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await expect(opening).toHaveAttribute("data-handover", "ready");
  expect(await read()).toMatchObject({ heroTop: 0, hero: 1, words: 0, clip: [84, 32, 32, 32] });
  await expectStop(page, 0);
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
  // The second beat: the wing apart, and its five parts named with their layups.
  const parts = page.getByTestId("demo-parts");
  await expect(parts.locator("[data-filled]")).toHaveCount(5);
  await expect(parts.locator("dt")).toHaveText(PARTS);
  await expect(parts.locator("dd")).toHaveText(wing.parts.map((part) => part.layup));
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
  // The analysis: the run's five stages done, the legend over the recorded range, and what the analysis found.
  const analysis = page.getByTestId("demo-run");
  await expect(analysis.locator(".demo-stages li")).toHaveText(["Queued", "Meshing", "Solving", "Post-processing", "Report ready"]);
  await expect(analysis.locator(".demo-stages li[data-state='done']")).toHaveCount(5);
  const legend = page.getByTestId("demo-legend");
  await expect(legend).toHaveCSS("opacity", "1");
  await expect(legend).toContainText(wing.field.unit ? `${wing.field.label}, ${wing.field.unit}` : wing.field.label);
  await expect(legend.locator(".demo-legend-ends span")).toHaveText([legendEnd(wing.field.min), legendEnd(wing.field.max)]);
  const result = page.getByTestId("demo-result");
  await expect(result).toHaveCSS("opacity", "1");
  const governing = wing.parts.find((part) => part.id === wing.solve.governing.part)!;
  await expect(result).toContainText(`Most loaded: the ${governing.name.toLowerCase()}`);
  await expect(result).toContainText(`${wing.load.total} ${wing.load.unit} pushed up at the ribs`);
  await expect(result).toContainText(`the tip rises ${Math.round(wing.solve.tip_deflection)} mm`);
  await expect(box(page).locator("canvas")).toBeVisible();
  // A swipe up plays a beat backwards, and a swipe down plays it again.
  expect(await swipe(page, -1)).toBe(28);
  await expectStop(page, 2);
  expect(await scrollY(page)).toBe(held);
  await page.waitForTimeout(400);
  expect(await swipe(page)).toBe(28);
  await expectStop(page, 3);
  await page.waitForTimeout(400);
  await expect(box(page)).not.toHaveAttribute("data-turnable", /.+/); // not while the demo still plays
  // The last beat: the files a run writes, by the workspace's names, and the way into the workspace.
  await notch(page);
  await expectStop(page, 4);
  const report = page.getByTestId("demo-report");
  await expect(report.locator(".demo-files li[data-shown]")).toHaveText(["Report (PDF)", "Full package (ZIP)", "Solver input (.inp)"]);
  await expect(report.getByRole("link", { name: "Open the workspace" })).toHaveAttribute("href", /\/workspace\/fea\/?$/);
  // Played through, once (amendment 7): the stage is an ordinary section now, the rest of the page is there, and a swipe
  // is the browser's again.
  await expect(box(page)).toHaveAttribute("data-done", "true");
  await expect(page.locator("html")).not.toHaveAttribute("data-demo-gate", /.+/);
  const after = await page.evaluate(() => [document.getElementById("mission")!.getBoundingClientRect().top, document.querySelector("#demo .product-demo-box")!.getBoundingClientRect().bottom]);
  expect(after[0]).toBe(after[1]);
  await page.waitForTimeout(400);
  expect(await swipe(page, -1)).toBe(0);
  await expectStop(page, 4);
  // The finished wing can be turned by hand (ADR-0098 amendment 1): the stage shows a hand and says so, and a drag on it
  // draws the wing from another side.
  await expect(box(page)).toHaveAttribute("data-turnable", "true");
  await expect(box(page).locator(".product-demo-hint")).toHaveText("Drag the wing to turn it");
  await expect(box(page)).toHaveCSS("cursor", "grab");
  const canvas = box(page).locator("canvas");
  const drawn = await canvas.screenshot();
  await page.mouse.move(300, 200);
  await page.mouse.down();
  await page.mouse.move(520, 260, { steps: 8 });
  await page.mouse.up();
  await expect(box(page)).toHaveAttribute("data-turned", "true");
  await page.waitForTimeout(250);
  expect(Buffer.compare(drawn, await canvas.screenshot())).not.toBe(0);
  expect(await scrollY(page)).toBe(await page.evaluate(() => Math.round(window.scrollY)));
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

test("a beat takes its own time: the second about 3.6 s, measured in the page", async ({ page }) => {
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
  expect(marks.end - marks.start).toBeGreaterThan(3400);
  expect(marks.end - marks.start).toBeLessThan(4800);
});

test("up from the first beat the page scrolls; once played through, the demo never plays again: down, back up to the hero and down again the stage is passed", async ({ page }) => {
  await openPinned(page);
  await playTo(page, 1);
  const held = await scrollY(page);
  // Up from the first beat: the page moves, and the box keeps its first beat while part of it shows.
  await notch(page, -1);
  await expect.poll(() => scrollY(page)).toBe(held - 100);
  await page.waitForTimeout(400);
  await expectStop(page, 1);
  // Down again: the box holds the window, and the first beat is not played twice. The page ends there: it cannot go on.
  await notch(page);
  await expect.poll(() => offLine(page)).toBe(0);
  await page.waitForTimeout(400);
  await expectStop(page, 1);
  expect(await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)).toBe(held);
  await playTo(page, 4);
  await expect(box(page)).toHaveAttribute("data-done", "true");
  // The hand-over is over with the demo (amendment 8): the hero is an ordinary section straight above the stage, whole, and
  // the stage has not moved in the window.
  await expect(page.locator(".home-opening")).toHaveAttribute("data-played", "true");
  expect(await offLine(page)).toBe(0);
  await expect(page.locator("#overview")).toHaveCSS("position", "relative");
  await expect(page.locator("#overview")).toHaveCSS("opacity", "1");
  await expect(page.locator("#overview")).toHaveCSS("visibility", "visible");
  const seam = await page.evaluate(() => [document.getElementById("overview")!.getBoundingClientRect().bottom, document.querySelector("#demo .product-demo-box")!.getBoundingClientRect().top]);
  expect(seam).toEqual([0, 0]);
  const done = await scrollY(page);
  expect(done).toBe(page.viewportSize()!.height);
  // Past the last beat nothing takes the scroll over.
  await page.waitForTimeout(350);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(done + 240);
  await page.waitForTimeout(300);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(done + 480);
  await expectStop(page, 4);
  // Back up past the stage: the hero comes down as a block, in its box and at full strength, with no fade and nothing held.
  await page.waitForTimeout(300);
  await page.mouse.wheel(0, -780);
  await expect.poll(() => scrollY(page)).toBe(done - 300);
  await page.waitForTimeout(500);
  expect(await scrollY(page)).toBe(done - 300);
  const up = await page.evaluate(() => {
    const hero = document.getElementById("overview")!;
    const clip = hero.querySelector(".home-hero-media")!.getBoundingClientRect();
    const box = hero.getBoundingClientRect();
    return { bottom: Math.round(box.bottom), opacity: getComputedStyle(hero).opacity, clipInBox: [Math.round(clip.left - box.left), Math.round(box.right - clip.right), Math.round(box.bottom - clip.bottom)] };
  });
  expect(up).toEqual({ bottom: 300, opacity: "1", clipInBox: [32, 32, 32] });
  await expect(page.locator(".home-opening")).not.toHaveAttribute("data-handover", /.+/);
  // All the way to the top, and the demo stays at its end.
  await page.mouse.wheel(0, -(done - 300));
  await expect.poll(() => scrollY(page)).toBe(0);
  await page.waitForTimeout(500);
  await expectStop(page, 4);
  // Down again: the stage does not stop the page and nothing plays. The wheel is the browser's all the way.
  await page.mouse.wheel(0, done - 20);
  await expect.poll(() => scrollY(page)).toBe(done - 20);
  await page.mouse.wheel(0, 300);
  await expect.poll(() => scrollY(page)).toBe(done + 280);
  await page.waitForTimeout(600);
  expect(await scrollY(page)).toBe(done + 280);
  await expectStop(page, 4);
  await expect(beat(page, "report")).toHaveAttribute("data-active", "true");
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
  // No hand-over: the hero is an ordinary section and the demo starts where the hero ends.
  await expect(page.locator(".home-opening")).not.toHaveAttribute("data-handover", /.+/);
  await expect(page.locator("#overview")).toHaveCSS("position", "relative");
  const seam = await page.evaluate(() => [document.getElementById("overview")!.getBoundingClientRect().bottom, document.getElementById("demo")!.getBoundingClientRect().top]);
  expect(seam[1]).toBe(seam[0]);
  await page.mouse.move(700, 500);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(240);
  await expect(page.locator("#overview")).toHaveCSS("opacity", "1");
  await expect(demo(page).getByRole("heading", { level: 2 })).toHaveText("A wing, analysed part by part.");
  for (const title of ["Start from the part.", "It comes apart into its parts.", "Every part is analysed.", "Back together, with the report."]) await expect(demo(page).getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByTestId("demo-facts").locator("[data-filled]")).toHaveCount(5);
  await expect(page.getByTestId("demo-parts").locator("[data-filled]")).toHaveCount(5);
  await expect(page.getByTestId("demo-run").locator(".demo-stages li[data-state='done']")).toHaveCount(5);
  await expect(page.getByTestId("demo-result")).toContainText("Most loaded");
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
