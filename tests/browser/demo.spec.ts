import { test, expect, type Page } from "@playwright/test";
import { demoWing } from "../../lib/demo-wing";
import { bannedIn } from "../../lib/studio-copy";

// The product demo under the hero (ADR-0095): a stage the size of the window, black as the page is (amendment 2), on which one
// composite wing is shown in four beats from one recorded analysis (ADR-0098): whole, apart into its parts, analysed part by
// part, whole again. The stage follows the page's scroll (amendment 10): it stays in the window while the page scrolls
// past it, freely, and where the scroll stands says which beat plays; nothing takes the wheel or holds the page.
// `data-stop` on the stage says where the demo's clock stands (0 at its start, 1 to 4 at the end of each beat) and
// `data-moving` is there while the clock runs.

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
/** The scroll a beat takes: half the stage's height (ZONE in components/home/product-demo.tsx). */
const zone = (page: Page) => box(page).evaluate((element) => Math.round(element.getBoundingClientRect().height / 2));
/** Where the page stands when the stage's top edge first lies on the window's: the start of the first beat's zone. */
const stageAt = (page: Page) => demo(page).evaluate((section) => Math.round(window.scrollY + section.getBoundingClientRect().top));
/** Wheels the page to a place and checks it went exactly there: nothing holds it, nothing carries it on. */
async function wheelTo(page: Page, y: number) {
  await page.mouse.wheel(0, y - (await scrollY(page)));
  await expect.poll(() => scrollY(page)).toBe(y);
}
/** Wheels the page onto the stage's line with the one wheel event that asks for all that is left, and waits for the first beat. */
async function reachBox(page: Page) {
  await wheelTo(page, await stageAt(page));
  await expectStop(page, 1);
  expect(await offLine(page)).toBe(0);
}
/** Wheels the page into the middle of a beat's zone (1 to 4) and waits for the clock to stand at that beat's end. */
async function playTo(page: Page, stop: number) {
  await wheelTo(page, (await stageAt(page)) + Math.round((stop - 0.5) * (await zone(page))));
  await expectStop(page, stop);
}
/** A trackpad swipe as the page gets it, sent in one go; returns how many of its wheel events were taken from the browser. */
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

test("the demo is a black stage as wide as the clip and a window tall, which starts half a window up behind the hero and stays in the window through its section", async ({ page }) => {
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
  // The stage stays in the window while the page scrolls through its section, which is the stage and half a stage of
  // scroll for each of the four beats tall (amendment 10). The page goes on under it: the next band follows the section.
  await expect(box(page)).toHaveCSS("position", "sticky");
  expect(rects.section.height).toBe(3 * page.viewportSize()!.height);
  expect(rects.next.top).toBe(rects.section.bottom);
  expect(rects.next.height).toBeGreaterThan(200);
  await expect(page.locator("html")).not.toHaveAttribute("data-demo-gate", /.+/);
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

test("the page scrolls to the stage as any page does; the first beat's words come up alone on the way, and the first beat plays as the stage arrives", async ({ page }) => {
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
  // Notch by notch: the page keeps to the wheel, and nothing plays while the stage is still more than a notch and its
  // lead (0.08 of its height) from the window's top.
  const lead = 0.08 * page.viewportSize()!.height;
  for (let guard = 0; (await offLine(page)) > lead + 100 && guard < 30; guard++) {
    const before = await scrollY(page);
    await notch(page);
    await expect.poll(() => scrollY(page)).toBe(before + 100);
    await expect(box(page)).not.toHaveAttribute("data-moving", "true");
  }
  await expectStop(page, 0);
  // The notch that brings the stage within its lead starts the first beat. The page is where the wheel put it: it is not
  // carried onto the stage's line, and not stopped there.
  const before = await scrollY(page);
  await notch(page);
  await expect.poll(() => scrollY(page)).toBe(before + 100);
  await expect(box(page)).toHaveAttribute("data-moving", "true");
  expect(await wordsIn()).toBeGreaterThan(0);
  await expectStop(page, 1);
  expect(await scrollY(page)).toBe(before + 100);
  // On to the line: from there the stage stays at the window's top.
  await reachBox(page);
  const placed = await box(page).evaluate((element) => { const r = element.getBoundingClientRect(); return [Math.round(r.top), Math.round(window.innerHeight - r.bottom)]; });
  expect(placed).toEqual([0, 0]);
  for (const part of [".product-demo-view", ".product-demo-beats"]) await expect(box(page).locator(part), part).toHaveCSS("opacity", "1");
  // The first beat: the wing whole, and what it is filled in beside it.
  await expect(beat(page, "describe")).toHaveAttribute("data-active", "true");
  await expect(beat(page, "describe").getByRole("heading", { level: 3 })).toHaveText("Start from the part.");
  const facts = page.getByTestId("demo-facts");
  await expect(facts.locator("[data-filled]")).toHaveCount(6);
  await expect(facts.locator("dt")).toHaveText(["PART", "SPAN", "CHORD", "MATERIAL", "STRUCTURE", "WINGLET"]);
  await expect(facts).toContainText("2.13 m");
  await expect(facts).toContainText("IM7 / 8552");
  await expect(facts).toContainText("0.45 m at the root, 0.23 m at the tip");
  await expect(facts).toContainText("2 skins, 2 spars, 11 ribs");
  await expect(facts).toContainText("0.33 m tall, canted 75°");
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
  // On the stage: the hero is out of the way, the words stand, and the first beat plays (it began as the stage came within
  // its lead).
  await reachBox(page);
  await expect(opening).toHaveAttribute("data-handover", "done");
  await expect(page.locator("#overview")).toHaveCSS("visibility", "hidden");
  expect((await read()).words).toBe(1);
  // Back at the top the hero is whole again and the demo has run back to its start.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await expect(opening).toHaveAttribute("data-handover", "ready");
  await expectStop(page, 0);
  expect(await read()).toMatchObject({ heroTop: 0, hero: 1, words: 0, clip: [84, 32, 32, 32] });
});

test("if the hero's words still stand when the page scrolls, they go as the clip grows and never lie over the demo's first words (ADR-0095 amendment 9)", async ({ page }) => {
  await openPinned(page);
  const hero = page.locator("#overview");
  // Before the words have left: the load-in is over and they stand.
  await expect(page.locator(".page-transition")).toHaveClass(/is-idle/, { timeout: 10_000 });
  await expect(hero.locator(".intro-overlay")).toHaveCount(0, { timeout: 6_000 });
  await expect(hero).not.toHaveAttribute("data-words", "gone");
  const read = () => page.evaluate(() => {
    const strength = (selector: string) => {
      const style = getComputedStyle(document.querySelector(selector)!);
      const through = /opacity\(([\d.]+)\)/.exec(style.filter);
      return Number(style.opacity) * (through ? Number(through[1]) : 1);
    };
    return {
      statement: strength("#overview .home-hero-stack") * strength("#overview h1"),
      backed: strength("#overview .home-hero-backed"),
      demo: Number(getComputedStyle(document.querySelector('.product-demo-beat[data-beat="describe"]')!).opacity),
    };
  });
  expect(await read()).toEqual({ statement: 1, backed: 1, demo: 0 });
  const way = await offLine(page);
  // A fifth of the way: the clip is half grown and the words half gone. Nothing of the demo is up.
  await page.mouse.wheel(0, way / 5);
  await expect.poll(() => scrollY(page)).toBe(Math.round(way / 5));
  await expect.poll(async () => (await read()).statement).toBeCloseTo(0.5, 1);
  expect((await read()).demo).toBe(0);
  // From two fifths on the clip is whole-window and the hero's words are gone, before the demo's first words begin.
  let seen = { statement: 1, backed: 1, demo: 0 };
  for (let step = 4; step <= 9; step++) {
    await page.mouse.wheel(0, step === 4 ? way / 5 : way / 10);
    await expect.poll(() => scrollY(page)).toBe(Math.round((way * step) / 10));
    await page.waitForTimeout(80);
    seen = await read();
    expect([seen.statement, seen.backed], `the hero's words at ${step}/10`).toEqual([0, 0]);
  }
  expect(seen.demo).toBeGreaterThan(0.8);
  // Back at the top they stand again, whole.
  await page.mouse.wheel(0, -way);
  await expect.poll(() => scrollY(page)).toBe(0);
  await expect.poll(async () => (await read()).statement).toBe(1);
});

test("each zone of scroll plays its beat and the page is never held; the analysis shows the recorded field with its legend and what it found", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await openPinned(page);
  await reachBox(page);
  const start = await scrollY(page);
  const step = await zone(page);
  // The wheel is the browser's: none of a swipe's events is taken, on the stage or off it, and it plays nothing by itself.
  expect(await swipe(page)).toBe(0);
  // A zone further down, the second beat: the wing apart, and its five parts named with their layups. The page is where
  // the wheel put it.
  await wheelTo(page, start + step);
  await expect(box(page)).toHaveAttribute("data-moving", "true");
  await expectStop(page, 2);
  await expect(beat(page, "model")).toHaveAttribute("data-active", "true");
  const parts = page.getByTestId("demo-parts");
  await expect(parts.locator("[data-filled]")).toHaveCount(5);
  await expect(parts.locator("dt")).toHaveText(PARTS);
  await expect(parts.locator("dd")).toHaveText(wing.parts.map((part) => part.layup));
  expect(await scrollY(page)).toBe(start + step);
  expect(await offLine(page)).toBe(0);
  // A notch inside the same zone moves the page and plays nothing.
  await notch(page);
  await expect.poll(() => scrollY(page)).toBe(start + step + 100);
  await page.waitForTimeout(500);
  await expectStop(page, 2);
  // The third zone.
  await wheelTo(page, start + 2 * step);
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
  await expect(result).toContainText(`${wing.load.total} ${wing.load.unit} pushed up at the wing's ribs`);
  await expect(result).toContainText(`the winglet's tip rises ${Math.round(wing.solve.tip_deflection)} mm`);
  await expect(box(page).locator("canvas")).toBeVisible();
  // Back up a zone the third beat is unplayed, faster than it played, and down again it plays again.
  await wheelTo(page, start + step);
  await expect(box(page)).toHaveAttribute("data-moving", "true");
  await expectStop(page, 2);
  await expect(legend).toHaveCSS("opacity", "0");
  await wheelTo(page, start + 2 * step);
  await expectStop(page, 3);
  await expect(box(page)).not.toHaveAttribute("data-turnable", /.+/); // not while the demo still plays
  // The last zone: the files a run writes, by the workspace's names, and the way into the workspace.
  await wheelTo(page, start + 3 * step);
  await expectStop(page, 4);
  const report = page.getByTestId("demo-report");
  await expect(report.locator(".demo-files li[data-shown]")).toHaveText(["Report (PDF)", "Full package (ZIP)", "Solver input (.inp)"]);
  await expect(report.getByRole("link", { name: "Open the workspace" })).toHaveAttribute("href", /\/workspace\/fea\/?$/);
  expect(await offLine(page)).toBe(0);
  // The finished wing can be turned by hand (ADR-0098 amendment 1): the stage shows a hand and says so, and a drag on it
  // draws the wing from another side.
  await expect(box(page)).toHaveAttribute("data-turnable", "true");
  await expect(box(page).locator(".product-demo-hint")).toHaveText("Drag the wing to turn it");
  await expect(box(page)).toHaveCSS("cursor", "grab");
  const canvas = box(page).locator("canvas");
  const drawn = await canvas.screenshot();
  const hint = box(page).locator(".product-demo-hint");
  const words = box(page).locator(".product-demo-beats");
  await expect(words).toHaveCSS("opacity", "1");
  await page.mouse.move(300, 200);
  await page.mouse.down();
  // While the pointer holds the wing (amendments 2 and 5): its axes are drawn, before it has moved at all, and the line
  // that says it can be turned steps back. The beat's words and its card stay.
  await expect(box(page)).toHaveAttribute("data-turning", "true");
  await expect(hint).toHaveCSS("opacity", "0");
  await page.waitForTimeout(300);
  await expect(words).toHaveCSS("opacity", "1");
  await expect(beat(page, "report")).toHaveCSS("opacity", "1");
  await page.waitForTimeout(350);
  const holding = await canvas.screenshot();
  expect(Buffer.compare(drawn, holding)).not.toBe(0);
  await page.mouse.move(520, 260, { steps: 8 });
  await page.mouse.up();
  await expect(box(page)).toHaveAttribute("data-turned", "true");
  // Let go: the line comes back, the axes go, and the wing stays turned.
  await expect(box(page)).not.toHaveAttribute("data-turning", /.+/);
  await expect(words).toHaveCSS("opacity", "1");
  await expect(hint).not.toHaveCSS("opacity", "0");
  await page.waitForTimeout(500);
  const turned = await canvas.screenshot();
  expect(Buffer.compare(drawn, turned)).not.toBe(0);
  expect(Buffer.compare(holding, turned)).not.toBe(0);
  // Scrolled back into the third beat the wing is the demo's again: it cannot be turned, and the line goes.
  await wheelTo(page, start + 2 * step);
  await expectStop(page, 3);
  await expect(box(page)).not.toHaveAttribute("data-turnable", /.+/);
  await expect(hint).toBeHidden();
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
  await wheelTo(page, (await scrollY(page)) + (await zone(page)));
  await expectStop(page, 2);
  const marks = await page.evaluate(() => (window as unknown as { __beat: { start: number; end: number } }).__beat);
  expect(marks.end - marks.start).toBeGreaterThan(3400);
  expect(marks.end - marks.start).toBeLessThan(4800);
});

test("a fast scroll goes straight through the stage: the page is not held, what follows is there at once, and the demo stands finished", async ({ page }) => {
  await openPinned(page);
  const start = await stageAt(page);
  const step = await zone(page);
  // One wheel event for the whole way: past the hero, through the four zones and on until the stage is out of the window.
  const far = start + 4 * step + page.viewportSize()!.height + 120;
  await wheelTo(page, far);
  await page.waitForTimeout(300);
  expect(await scrollY(page)).toBe(far);
  // The stage has gone up out of the window with its section, and the next band follows it.
  const seen = await page.evaluate(() => ({ stage: Math.round(document.querySelector("#demo .product-demo-box")!.getBoundingClientRect().bottom), next: Math.round(document.getElementById("mission")!.getBoundingClientRect().top) }));
  expect(seen.stage).toBe(seen.next);
  expect(seen.stage).toBeLessThan(0);
  // Out of sight the clock went straight to its end: nothing is played for no one.
  await expect(box(page)).toHaveAttribute("data-stop", "4", { timeout: 2_000 });
  await expect(box(page)).not.toHaveAttribute("data-moving", "true");
  // Through the stage in a few quick steps, a visitor still sees it run: each beat left behind is run through, and the
  // clock is at the last beat's end soon after the page is.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await expectStop(page, 0);
  const began = Date.now();
  for (let part = 1; part <= 4; part++) {
    await wheelTo(page, start + Math.round((part - 0.5) * step));
    await page.waitForTimeout(120);
  }
  await expectStop(page, 4);
  // Four beats take 14.8 s at their own pace; run through, the first three take about a second each at most.
  expect(Date.now() - began).toBeLessThan(9_000);
  expect(await offLine(page)).toBe(0);
  await expect(beat(page, "report")).toHaveAttribute("data-active", "true");
});

test("on the way back up the beats are unplayed one by one, down to the hero, and on the way down they play again", async ({ page }) => {
  await openPinned(page);
  const start = await stageAt(page);
  const step = await zone(page);
  await playTo(page, 4);
  await expect(box(page)).toHaveAttribute("data-turnable", "true");
  // Up a zone at a time: the clock runs back to the beat before, and its words and card stand again.
  const titles = ["Start from the part.", "It comes apart into its parts.", "Every part is analysed.", "Back together, with the report."];
  const ids = ["describe", "model", "analysis", "report"];
  for (let stop = 3; stop >= 1; stop--) {
    await wheelTo(page, start + Math.round((stop - 0.5) * step));
    await expect(box(page)).toHaveAttribute("data-moving", "true");
    await expectStop(page, stop);
    await expect(beat(page, ids[stop - 1])).toHaveAttribute("data-active", "true");
    await expect(beat(page, ids[stop - 1]).getByRole("heading", { level: 3 })).toHaveText(titles[stop - 1]);
    await expect(beat(page, ids[stop - 1])).toHaveCSS("opacity", "1");
    expect(await offLine(page)).toBe(0);
  }
  await expect(page.getByTestId("demo-parts").locator("[data-filled]")).toHaveCount(0);
  await expect(page.getByTestId("demo-facts").locator("[data-filled]")).toHaveCount(6);
  // Up off the stage: the hero comes back as it went (the hand-over, backwards), and the demo runs back to its start.
  const opening = page.locator(".home-opening");
  await wheelTo(page, start - Math.round(step / 2));
  await expect(opening).toHaveAttribute("data-handover", "going");
  await expectStop(page, 0);
  await wheelTo(page, 0);
  await expect(opening).toHaveAttribute("data-handover", "ready");
  await expect(page.locator("#overview")).toHaveCSS("opacity", "1");
  await expect(page.locator("#overview")).toHaveCSS("visibility", "visible");
  await expect(page.getByTestId("demo-facts").locator("[data-filled]")).toHaveCount(0);
  await expect(box(page).locator(".product-demo-view")).toHaveCSS("opacity", "0");
  // And down again it plays again, from its first beat.
  await wheelTo(page, start);
  await expect(box(page)).toHaveAttribute("data-moving", "true");
  await expectStop(page, 1);
  await expect(page.getByTestId("demo-facts").locator("[data-filled]")).toHaveCount(6);
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

  test("a finger scrolls the page through the stage as it scrolls any page, and the beats play as it goes", async ({ page }) => {
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
    const start = await stageAt(page);
    const step = await zone(page);
    // Every drag moves the page: on the way to the stage, on it, and off it again.
    let before = await scrollY(page);
    for (let guard = 0; before < start + 4 * step + 100 && guard < 40; guard++) {
      await drag(300, 600, 300);
      await expect.poll(() => scrollY(page), { message: `a drag from ${before}` }).toBeGreaterThan(before + 100);
      await page.waitForTimeout(250);
      before = await scrollY(page);
    }
    expect(before).toBeGreaterThanOrEqual(start + 4 * step + 100);
    await expectStop(page, 4);
    // And back up onto the stage, where the last beat stands.
    await drag(300, 300, 620);
    await expect.poll(() => scrollY(page)).toBeLessThan(before - 100);
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
  await expect(page.getByTestId("demo-facts").locator("[data-filled]")).toHaveCount(6);
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
