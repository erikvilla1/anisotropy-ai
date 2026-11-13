import { test, expect, type Page } from "@playwright/test";
import quasi from "../fixtures/home/response-im7-quasi.json";
import loaded from "../fixtures/home/response-im7-quasi-loaded.json";
import { BRIDGE, STEPS, TOTAL } from "../../components/home/tour-timeline";

// The scroll-driven tour between the hero and the calculator, with the API played from tests/fixtures/home as
// tests/browser/home.spec.ts plays it: two answers of the real engine for the IM7/8552 quasi-isotropic stack, unloaded and
// under Nx = 25 kN/m. The tour's clock is scroll, in screens (viewport heights) from the top of the page.

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
const range = (id: (typeof STEPS)[number]["id"]) => STEPS.find((item) => item.id === id)!;
/** Puts the page at a moment of the tour, as a visitor's scroll would: only the scroll position is set. */
async function scrollToScreens(page: Page, screens: number) {
  await page.evaluate((value) => window.scrollTo({ top: Math.round(value * window.innerHeight), behavior: "instant" }), screens);
}
const scrolledScreens = (page: Page) => page.evaluate(() => window.scrollY / window.innerHeight);
/** Opens the home page and waits until the tour is pinned and has read the scroll once. Before the page's script runs, the
 * markup is the unpinned tour with everything shown (and the stage hidden by the stylesheet), which is not what these tests read. */
async function openPinned(page: Page) {
  await page.goto("/");
  await expect(tour(page)).toHaveAttribute("data-mode", "pinned");
  await expect(tour(page)).toHaveAttribute("data-phase", "bridge");
}

test("Scroll to explore, under the hero's statement, scrolls to the tour's first step", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  const button = page.locator("#overview").getByRole("button", { name: "Scroll to explore" });
  await expect(button).toBeVisible();
  // It is the second small line of the row under the statement, inside the box the clip plays in (ADR-0077 amendment 19).
  const box = (await button.boundingBox())!;
  const clip = (await page.locator("#overview .home-hero-media").boundingBox())!;
  const statement = (await page.locator("#overview h1").boundingBox())!;
  expect(box.y).toBeGreaterThan(statement.y + statement.height);
  expect(box.x).toBeGreaterThan(clip.x + clip.width / 2);
  expect(box.y + box.height).toBeLessThan(clip.y + clip.height);
  await button.click();
  await expect.poll(() => scrolledScreens(page), { timeout: 8000 }).toBeCloseTo(range("material").at(0.14), 2);
  await expect(step(page, "material")).toHaveAttribute("data-active", "true");
  await expect(tour(page).getByRole("heading", { name: "Start from a cited material." })).toBeVisible();
  await expect(tour(page).locator(".demo-tour-stage")).toHaveCSS("position", "sticky");
});

test("the bridge holds the hero in the window while its clip is carried onto the 3D view, then lets it go", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  const hero = page.locator("#overview");
  const ground = () => hero.evaluate((element) => getComputedStyle(element, "::before").opacity);
  await expect(hero.locator(".home-hero-media")).toHaveCSS("transform", "none");
  await expect(hero.locator(".home-hero-media")).toHaveCSS("border-radius", "0px");
  expect(await ground()).toBe("1");
  await scrollToScreens(page, BRIDGE * 0.5);
  await expect(tour(page)).toHaveAttribute("data-phase", "bridge");
  await expect(hero).toHaveCSS("position", "sticky");
  expect(await hero.evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(0);
  await expect(hero.locator(".home-hero-media")).not.toHaveCSS("transform", "none");
  // The clip path draws the corners now, and the hero's black ground has gone so the stage shows around the clip.
  await expect(hero.locator(".home-hero-media")).toHaveCSS("border-radius", "0px");
  expect(await ground()).toBe("0");
  await expect(hero.getByRole("heading", { level: 1 })).not.toBeVisible();
  await scrollToScreens(page, BRIDGE + 0.3);
  await expect(tour(page)).toHaveAttribute("data-phase", "steps");
  await expect(hero).toHaveCSS("position", "relative");
  // Back at the top the hero is as its own stylesheet sets it.
  await scrollToScreens(page, 0);
  await expect(hero.locator(".home-hero-media")).toHaveCSS("transform", "none");
  expect(await ground()).toBe("1");
  await expect(hero.getByRole("heading", { level: 1 })).toBeVisible();
});

test("the material's constants and the layup are typed in by the scroll, the plies laid one by one, and scrolling back undoes it", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  await scrollToScreens(page, range("material").at(0.75));
  await expect(step(page, "material")).toHaveAttribute("data-active", "true");
  // The library record's values, as the calculator shows them before the engine has cited them.
  const properties = step(page, "material").getByTestId("property-row");
  await expect(properties).toContainText("162.096");
  await expect(properties).toContainText("1580");
  await expect(properties).toContainText("57.3");
  const layup = step(page, "layup").locator(".tour-field-box").first();
  const rows = step(page, "layup").getByTestId("stack-row");
  await scrollToScreens(page, range("layup").at(0.4));
  await expect(step(page, "layup")).toHaveAttribute("data-active", "true");
  const typed = (await layup.textContent()) ?? "";
  expect(typed.length).toBeGreaterThan(1);
  expect(typed.length).toBeLessThan("[45/-45/0/90]s".length);
  expect("[45/-45/0/90]s".startsWith(typed)).toBe(true);
  const laid = await rows.count();
  expect(laid).toBeGreaterThan(0);
  expect(laid).toBeLessThan(8);
  await scrollToScreens(page, range("layup").at(0.95));
  await expect(layup).toHaveText("[45/-45/0/90]s");
  await expect(rows).toHaveCount(8);
  await expect(step(page, "layup").locator(".tour-field-box").nth(1)).toHaveText("0.18288");
  await scrollToScreens(page, range("layup").at(0.4));
  await expect(layup).toHaveText(typed);
  await expect(rows).toHaveCount(laid);
});

test("the engine step shows the calculator's own answer: one POST before the loads step, two after it, none repeated", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const posts: Posted[] = [];
  await playApi(page, posts);
  await openPinned(page);
  await expect.poll(() => posts.length).toBe(1);
  await scrollToScreens(page, range("engine").at(0.8));
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

  await scrollToScreens(page, range("loads").at(0.75));
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

  // Back up and down again, then on to the calculator: nothing is asked twice.
  await scrollToScreens(page, range("engine").at(0.8));
  await expect(step(page, "engine")).toHaveAttribute("data-active", "true");
  await scrollToScreens(page, range("loads").at(0.75));
  await expect(panel).toBeVisible();
  await page.waitForTimeout(900);
  await scrollToScreens(page, TOTAL + 1);
  await expect(page.locator("#laminate")).toBeInViewport();
  await page.waitForTimeout(900);
  expect(posts.length).toBe(2);
  expect(errors).toEqual([]);
});

test("after the last step the stage lets go and the page scrolls on to the calculator and the mission", async ({ page }) => {
  await playApi(page, []);
  await openPinned(page);
  await scrollToScreens(page, TOTAL - 0.1);
  await expect(step(page, "handover")).toHaveAttribute("data-active", "true");
  const stage = tour(page).locator(".demo-tour-stage");
  expect(await stage.evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(0);
  // Half a screen on, the stage has moved up by half a screen with the page, and the calculator has come in under it.
  await scrollToScreens(page, TOTAL + 0.5);
  const viewport = page.viewportSize()!;
  expect(await stage.evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(-Math.round(viewport.height / 2));
  expect(await page.locator("#laminate").evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(Math.round(viewport.height / 2));
  // The order after the tour is the page's own: the calculator, then the mission.
  const order = await page.locator("main > *").evaluateAll((elements) => elements.map((element) => element.id).filter(Boolean));
  expect(order.slice(0, 4)).toEqual(["overview", "tour", "laminate", "mission"]);
  // Nothing takes the scroll over: a wheel moves the page by what it asks for.
  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.move(viewport.width / 2, viewport.height / 2);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(before + 240);
});

test("when the engine does not answer, the tour still shows the material, the layup and the plies, and says what needs the engine", async ({ page }) => {
  const posts: Posted[] = [];
  await page.route("**/v1/laminates/response", async (route) => {
    posts.push(route.request().postDataJSON() as Posted);
    await route.fulfill({ status: 500, json: { detail: "down" } });
  });
  await openPinned(page);
  await expect.poll(() => posts.length).toBe(1);
  await scrollToScreens(page, range("layup").at(0.95));
  await expect(step(page, "layup").getByTestId("stack-row")).toHaveCount(8);
  await scrollToScreens(page, range("engine").at(0.8));
  await expect(step(page, "engine")).toContainText("The engine did not answer.");
  await expect(step(page, "engine").getByRole("note")).toContainText("nothing here stands in for them");
  await expect(step(page, "engine").getByTestId("specs")).toHaveCount(0);
  await expect(step(page, "engine").getByTestId("abd-grid")).toHaveCount(0);
  await scrollToScreens(page, range("loads").at(0.75));
  await expect(step(page, "loads").getByRole("note")).toContainText("nothing here stands in for them");
  await expect(tour(page).getByTestId("failure-panel")).toHaveCount(0);
});

test("with reduced motion every step is shown, nothing is pinned, and the loaded case is asked for when its step comes into view", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(tour(page)).toHaveAttribute("data-mode", "static");
  await expect(tour(page).locator(".demo-tour-stage")).toHaveCSS("position", "static");
  await expect(page.locator("#overview")).toHaveCSS("position", "relative");
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
  // Scroll to explore takes the visitor to the top of the section, without the move.
  await page.locator("#overview").getByRole("button", { name: "Scroll to explore" }).click();
  await expect.poll(() => tour(page).evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(0);
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
