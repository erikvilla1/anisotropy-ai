import { test, expect, type Page } from "@playwright/test";
import quasi from "../fixtures/home/response-im7-quasi.json";
import loaded from "../fixtures/home/response-im7-quasi-loaded.json";

// The stepped tour between the hero and the calculator (ADR-0084 amendment 4), with the API played from tests/fixtures/home as
// tests/browser/home.spec.ts plays it: two answers of the real engine for the IM7/8552 quasi-isotropic stack, unloaded and
// under Nx = 25 kN/m. One scroll gesture plays one whole step; `data-stop` on the tour says where its clock stands (0 before
// the first step, 1 to 5 at the end of each) and `data-moving` is there while a step plays or the page is carried.

type Posted = { plies: { angle_deg: number; thickness_m: number }[]; loads: Record<string, number>; material: Record<string, string> };

async function playApi(page: Page, posts: Posted[]) {
  await page.route("**/v1/laminates/response", async (route) => {
    const body = route.request().postDataJSON() as Posted;
    posts.push(body);
    const hasLoad = Object.values(body.loads).some((value) => value !== 0);
    await route.fulfill({ status: 200, json: { ...(hasLoad ? loaded : quasi), inputs: body } });
  });
}

const tour = (page: Page) => page.locator("#tour");
const step = (page: Page, id: string) => tour(page).locator(`[data-step="${id}"]`);
/** Where the stage's top edge is in the window, and how far the page is scrolled, in whole pixels. */
const stageTop = (page: Page) => tour(page).evaluate((element) => Math.round(element.getBoundingClientRect().top));
const scrollY = (page: Page) => page.evaluate(() => Math.round(window.scrollY));
/** The clock stands at a stop and nothing is playing. */
async function expectStop(page: Page, stop: number) {
  await expect(tour(page)).toHaveAttribute("data-stop", String(stop), { timeout: 10_000 });
  await expect(tour(page)).not.toHaveAttribute("data-moving", "true");
}
/** One notch of a mouse wheel: down by default. */
const notch = (page: Page, direction: 1 | -1 = 1) => page.mouse.wheel(0, 100 * direction);
/** Plays the tour on to a stop, one notch a step, as a visitor would. */
async function playTo(page: Page, stop: number) {
  for (let at = Number(await tour(page).getAttribute("data-stop")); at < stop; at++) {
    await notch(page);
    await expectStop(page, at + 1);
  }
}
/** A swipe on a trackpad as the page gets it: wheel events that grow while the fingers move and shrink while it coasts. They
 * are sent in one go, so a busy machine cannot stretch them into separate gestures (two events more than 200 ms apart are
 * two gestures, components/home/tour-stepper.ts). Returns how many of them the tour took from the browser. */
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
/** Sets the scroll position at once, as the scroll bar or a link does: no wheel, no key, no touch. */
const jumpTo = (page: Page, top: number) => page.evaluate((value) => window.scrollTo({ top: value, behavior: "instant" }), top);
/** Opens the home page and waits until the tour is stepped and at its start. Before the page's script runs, the markup is the
 * unpinned tour with everything shown (and the stage hidden by the stylesheet), which is not what these tests read. */
async function openPinned(page: Page) {
  await page.goto("/");
  await expect(tour(page)).toHaveAttribute("data-mode", "pinned");
  await expectStop(page, 0);
  const viewport = page.viewportSize()!;
  await page.mouse.move(viewport.width / 2, viewport.height / 2);
}

test("the hero scrolls away as any section does, and the stage stands under it in the page's flow", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  const viewport = page.viewportSize()!;
  const hero = page.locator("#overview");
  const heroHeight = await hero.evaluate((element) => element.getBoundingClientRect().height);
  // The stage is one window tall and starts where the hero ends; the order after it is the page's own.
  expect(await stageTop(page)).toBe(Math.round(heroHeight));
  expect(await tour(page).evaluate((element) => element.getBoundingClientRect().height)).toBe(viewport.height);
  const order = await page.locator("main > *").evaluateAll((elements) => elements.map((element) => element.id).filter(Boolean));
  expect(order.slice(0, 4)).toEqual(["overview", "tour", "laminate", "mission"]);
  // Part of the way down, by the scroll bar: the hero has moved up with the page and nothing has been done to it.
  await jumpTo(page, 300);
  await expect(hero).toHaveCSS("position", "relative");
  expect(await hero.evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(-300);
  await expect(hero.locator(".home-hero-media")).toHaveCSS("transform", "none");
  await expect(hero.locator(".home-hero-media")).toHaveCSS("clip-path", "none");
  expect(await hero.evaluate((element) => getComputedStyle(element, "::before").opacity)).toBe("1");
  expect(await hero.getAttribute("style")).toBeNull();
  expect(await stageTop(page)).toBe(Math.round(heroHeight) - 300);
  // The tour has not started: its clock does not follow the scroll.
  await page.waitForTimeout(400);
  await expectStop(page, 0);
});

test("one scroll gesture on the hero brings the stage into the window and plays the first step", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  const heroHeight = await page.locator("#overview").evaluate((element) => Math.round(element.getBoundingClientRect().height));
  await notch(page);
  await expect(tour(page)).toHaveAttribute("data-moving", "true");
  await expectStop(page, 1);
  expect(await stageTop(page)).toBe(0);
  expect(await scrollY(page)).toBe(heroHeight);
  await expect(step(page, "material")).toHaveAttribute("data-active", "true");
  // The library record's values, as the calculator shows them before the engine has cited them.
  const properties = step(page, "material").getByTestId("property-row");
  await expect(properties).toContainText("162.096");
  await expect(properties).toContainText("1580");
  await expect(properties).toContainText("57.3");
  await expect(step(page, "material").locator(".tour-library li[data-picked]")).toHaveCount(1);
});

test("each gesture plays one whole step: the layup is typed and the plies laid, a swipe's burst of events plays one step, and gestures during a step are not kept", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  await playTo(page, 1);
  const layup = step(page, "layup").locator(".tour-field-box").first();
  const rows = step(page, "layup").getByTestId("stack-row");
  // A swipe on a trackpad is one gesture: every one of its events is taken from the browser, and one step plays.
  const before = await scrollY(page);
  expect(await swipe(page)).toBe(28);
  await expect(step(page, "layup")).toHaveAttribute("data-active", "true");
  // Partly typed and partly laid on the way.
  await expect.poll(async () => ((await layup.textContent()) ?? "").length, { intervals: [25] }).toBeGreaterThan(1);
  const typed = (await layup.textContent()) ?? "";
  expect("[45/-45/0/90]s".startsWith(typed)).toBe(true);
  await expectStop(page, 2);
  await expect(layup).toHaveText("[45/-45/0/90]s");
  await expect(rows).toHaveCount(8);
  await expect(step(page, "layup").locator(".tour-field-box").nth(1)).toHaveText("0.18288");
  // The page has not moved, and the swipe's later events did not play a second step.
  await page.waitForTimeout(700);
  await expectStop(page, 2);
  expect(await scrollY(page)).toBe(before);
  // Three notches of a wheel, two of them while the step plays: one step.
  await notch(page);
  await expect(tour(page)).toHaveAttribute("data-moving", "true");
  await notch(page);
  await notch(page);
  await expectStop(page, 3);
  await page.waitForTimeout(700);
  await expectStop(page, 3);
  await expect(step(page, "engine")).toHaveAttribute("data-active", "true");
  // A swipe up plays the step backwards: the layup's finished state is back.
  expect(await swipe(page, -1)).toBe(28);
  await expectStop(page, 2);
  await page.waitForTimeout(700);
  await expectStop(page, 2);
  await expect(step(page, "layup")).toHaveAttribute("data-active", "true");
  await expect(layup).toHaveText("[45/-45/0/90]s");
  await expect(rows).toHaveCount(8);
  expect(await scrollY(page)).toBe(before);
});

test("the engine step shows the calculator's own answer: one POST before the loads step, two after it, none repeated", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const posts: Posted[] = [];
  await playApi(page, posts);
  await openPinned(page);
  await expect.poll(() => posts.length).toBe(1);
  await playTo(page, 3);
  await expect(step(page, "engine")).toHaveAttribute("data-active", "true");
  const specs = step(page, "engine").getByTestId("specs");
  await expect(specs).toContainText("Quasi-isotropic");
  await expect(specs).toContainText("symmetric, balanced");
  await expect(specs).toContainText("1.463 mm");
  await expect(specs).toContainText("2.312 kg/m²");
  await expect(step(page, "engine").getByTestId("abd-grid").getByRole("table", { name: "A matrix" })).toContainText("9.88e+7");
  await expect(step(page, "engine")).toContainText(`Engine ${quasi.engine_version}`);
  await page.waitForTimeout(900);
  expect(posts.length).toBe(1);
  await expect(tour(page).getByTestId("failure-panel")).toHaveCount(0);

  await playTo(page, 4);
  await expect(step(page, "loads")).toHaveAttribute("data-active", "true");
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[1].loads).toEqual({ Nx: 25000, Ny: 0, Nxy: 0, Mx: 0, My: 0, Mxy: 0 });
  expect(posts[1].plies.map((ply) => ply.angle_deg)).toEqual([45, -45, 0, 90, 90, 0, -45, 45]);
  expect(posts[1].material).toEqual(posts[0].material);
  const panel = step(page, "loads").getByTestId("failure-panel");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("28.1");
  await expect(panel).toContainText("4 (+90°)");
  await expect(panel).toContainText("transverse tension");
  await expect(tour(page).locator(".demo-tour-note")).toHaveText("Marked: ply 4 (+90°), the first ply to fail.");

  // Back a step and on again, then through the last step and on to the calculator: nothing is asked twice.
  await notch(page, -1);
  await expectStop(page, 3);
  await expect(step(page, "engine")).toHaveAttribute("data-active", "true");
  await playTo(page, 4);
  await expect(panel).toBeVisible();
  await page.waitForTimeout(900);
  await playTo(page, 5);
  await expect(step(page, "handover")).toHaveAttribute("data-active", "true");
  await page.mouse.wheel(0, 700);
  await expect(page.locator("#laminate")).toBeInViewport();
  await page.waitForTimeout(900);
  expect(posts.length).toBe(2);
  expect(errors).toEqual([]);
});

test("after the last step the stage lets go and the page scrolls on to the calculator; a gesture back up brings the stage in again", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  await playTo(page, 5);
  await expect(step(page, "handover")).toHaveAttribute("data-active", "true");
  expect(await stageTop(page)).toBe(0);
  const held = await scrollY(page);
  const viewport = page.viewportSize()!;
  // Nothing takes the scroll over now: a wheel moves the page by what it asks for, and the calculator comes in under the stage.
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(held + 240);
  expect(await stageTop(page)).toBe(-240);
  expect(await page.locator("#laminate").evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(viewport.height - 240);
  await page.waitForTimeout(300);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(held + 480);
  await expectStop(page, 5);
  // Up again while the stage still touches the window: it is carried back in, at its last step.
  await page.waitForTimeout(300);
  await notch(page, -1);
  await expect.poll(() => stageTop(page)).toBe(0);
  await expectStop(page, 5);
  expect(await scrollY(page)).toBe(held);
  // And the next gesture up plays the last step backwards.
  await page.waitForTimeout(400);
  await notch(page, -1);
  await expectStop(page, 4);
  await expect(step(page, "loads")).toHaveAttribute("data-active", "true");
});

test("a gesture up from the first step goes back to the hero, and the tour starts over from there", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  await playTo(page, 1);
  await notch(page, -1);
  await expect.poll(() => scrollY(page)).toBe(0);
  await expectStop(page, 0);
  await expect(page.locator("#overview")).toBeInViewport({ ratio: 0.99 });
  await expect(step(page, "material").locator(".tour-library li[data-picked]")).toHaveCount(0);
  await page.waitForTimeout(400);
  await notch(page);
  await expectStop(page, 1);
  expect(await stageTop(page)).toBe(0);
  await expect(step(page, "material").locator(".tour-library li[data-picked]")).toHaveCount(1);
});

test("the scrolling keys step the tour as the wheel does", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  const press = async (key: string, stop: number) => {
    await page.keyboard.press(key);
    await expectStop(page, stop);
  };
  await press("ArrowDown", 1);
  expect(await stageTop(page)).toBe(0);
  await press("PageDown", 2);
  await press("Space", 3);
  await press("ArrowUp", 2);
  await press("PageUp", 1);
  await press("Shift+Space", 0);
  expect(await scrollY(page)).toBe(0);
  // A key pressed in a field is the field's: with the calculator's first box focused, the arrow key plays no step.
  await press("ArrowDown", 1);
  await page.locator("#laminate input").first().evaluate((field: HTMLElement) => field.focus({ preventScroll: true }));
  await page.keyboard.press("ArrowDown");
  await page.waitForTimeout(400);
  await expectStop(page, 1);
});

test("the scroll bar and links move the page, never the tour's clock: it is always at a stop, at its start from above and its end from below", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  const viewport = page.viewportSize()!;
  await playTo(page, 2);
  const held = await scrollY(page);
  // Dragged past the tour: out of sight it stands at its end, so coming back up meets the last step.
  await jumpTo(page, held + 2 * viewport.height);
  await expectStop(page, 5);
  await jumpTo(page, held + 0.4 * viewport.height);
  await page.waitForTimeout(400);
  await expectStop(page, 5);
  await expect(step(page, "handover")).toHaveAttribute("data-active", "true");
  expect(await scrollY(page)).toBe(held + 0.4 * viewport.height);
  // Dragged back to the top: it starts over.
  await jumpTo(page, 0);
  await expectStop(page, 0);
  await expect(step(page, "material")).toHaveAttribute("data-active", "true");
  // Put exactly on the stage, as a link to it would: the first step plays.
  await jumpTo(page, held);
  await expectStop(page, 1);
  expect(await stageTop(page)).toBe(0);
  // A jump while a step plays is undone: the stage holds the window until the step is over.
  await notch(page);
  await expect(tour(page)).toHaveAttribute("data-moving", "true");
  await jumpTo(page, held + 180);
  await expect.poll(() => scrollY(page)).toBe(held);
  await expectStop(page, 2);
});

test.describe("on a touch screen", () => {
  test.use({ hasTouch: true });

  test("a swipe plays one step, on the words or on the 3D view, and at the last step it scrolls the page on", async ({ page }) => {
    await playApi(page, []);
    await openPinned(page);
    const viewport = page.viewportSize()!;
    const client = await page.context().newCDPSession(page);
    // A finger dragged from one height to another, at x.
    const swipe = async (x: number, from: number, to: number) => {
      await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: from }] });
      for (let part = 1; part <= 10; part++) {
        await client.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: from + ((to - from) * part) / 10 }] });
        await page.waitForTimeout(16);
      }
      await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    };
    const side = 200;
    const middle = Math.round(viewport.width * 0.47);
    await swipe(side, 700, 400);
    await expectStop(page, 1);
    expect(await stageTop(page)).toBe(0);
    const held = await scrollY(page);
    await expect(tour(page).locator("canvas")).toBeVisible({ timeout: 15_000 });
    await swipe(middle, 600, 300);
    await expectStop(page, 2);
    await swipe(side, 300, 600);
    await expectStop(page, 1);
    expect(await scrollY(page)).toBe(held);
    await playTo(page, 5);
    await swipe(middle, 600, 300);
    await expect.poll(() => scrollY(page)).toBeGreaterThan(held + 100);
    await expectStop(page, 5);
  });
});

test("when the engine does not answer, the tour still shows the material, the layup and the plies, and says what needs the engine", async ({ page }) => {
  const posts: Posted[] = [];
  await page.route("**/v1/laminates/response", async (route) => {
    posts.push(route.request().postDataJSON() as Posted);
    await route.fulfill({ status: 500, json: { detail: "down" } });
  });
  await openPinned(page);
  await expect.poll(() => posts.length).toBe(1);
  await playTo(page, 2);
  await expect(step(page, "layup").getByTestId("stack-row")).toHaveCount(8);
  await playTo(page, 3);
  await expect(step(page, "engine")).toContainText("The engine did not answer.");
  await expect(step(page, "engine").getByRole("note")).toContainText("nothing here stands in for them");
  await expect(step(page, "engine").getByTestId("specs")).toHaveCount(0);
  await expect(step(page, "engine").getByTestId("abd-grid")).toHaveCount(0);
  await playTo(page, 4);
  await expect(step(page, "loads").getByRole("note")).toContainText("nothing here stands in for them");
  await expect(tour(page).getByTestId("failure-panel")).toHaveCount(0);
});

test("with reduced motion every step is shown, no gesture is taken, and the loaded case is asked for when its step comes into view", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(tour(page)).toHaveAttribute("data-mode", "static");
  await expect(tour(page).locator(".demo-tour-stage")).toHaveCSS("position", "static");
  await expect(page.locator("#overview")).toHaveCSS("position", "relative");
  // The wheel is the page's own: it scrolls by what it asks for, and the tour has no clock to play.
  expect(await tour(page).getAttribute("data-stop")).toBeNull();
  await page.mouse.move(700, 500);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => scrollY(page)).toBe(240);
  for (const title of ["Start from a cited material.", "Type the stacking.", "The engine answers.", "Add a load.", "Now it is yours."]) {
    await expect(tour(page).getByRole("heading", { name: title })).toBeVisible();
  }
  await expect(step(page, "material").getByTestId("property-row")).toContainText("162.096");
  await expect(step(page, "layup").locator(".tour-field-box").first()).toHaveText("[45/-45/0/90]s");
  await expect(step(page, "layup").getByTestId("stack-row")).toHaveCount(8);
  await expect(step(page, "engine").getByTestId("specs")).toContainText("Quasi-isotropic");
  await expect(step(page, "engine").getByTestId("abd-grid")).toBeVisible();
  await page.waitForTimeout(900);
  expect(posts.length).toBe(1);
  await step(page, "loads").scrollIntoViewIfNeeded();
  await expect.poll(() => posts.length).toBe(2);
  await expect(step(page, "loads").getByTestId("failure-panel")).toContainText("28.1");
  // The tour is as tall as its content, and the calculator follows it.
  const heights = await page.evaluate(() => ({
    tour: document.getElementById("tour")!.getBoundingClientRect().height,
    stage: document.querySelector("#tour .demo-tour-stage")!.getBoundingClientRect().height,
  }));
  expect(Math.round(heights.tour)).toBe(Math.round(heights.stage));
});

test("on a phone the tour is one column and nothing overflows sideways", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(tour(page)).toHaveAttribute("data-mode", "static");
  await expect.poll(() => posts.length).toBe(1);
  await expect(step(page, "engine").getByTestId("specs")).toContainText("Quasi-isotropic");
  await step(page, "loads").scrollIntoViewIfNeeded();
  await expect(step(page, "loads").getByTestId("failure-panel")).toBeVisible();
  await page.locator("#mission").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const widest = await tour(page).locator(".demo-tour-card").evaluateAll((cards) => Math.max(...cards.map((card) => card.getBoundingClientRect().right)));
  expect(widest).toBeLessThanOrEqual(390);
});
