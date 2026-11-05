import { test, expect, type Page } from "@playwright/test";
import quasi from "../fixtures/home/response-im7-quasi.json";
import loaded from "../fixtures/home/response-im7-quasi-loaded.json";

// The home page's laminate calculator with the API played from tests/fixtures/home: two answers of the real engine for the
// IM7/8552 quasi-isotropic stack, unloaded and under Nx = 25 kN/m, captured on 2026-11-05 (the evaluation note says how).
// The service's inputs echo is replaced by the request's own, as the page checks them (readAnalysisResult).

type Posted = { plies: { angle_deg: number; thickness_m: number }[]; loads: Record<string, number>; material: Record<string, string> };

async function playApi(page: Page, posts: Posted[]) {
  await page.route("**/v1/laminates/response", async (route) => {
    const body = route.request().postDataJSON() as Posted;
    posts.push(body);
    const hasLoad = Object.values(body.loads).some((value) => value !== 0);
    await route.fulfill({ status: 200, json: { ...(hasLoad ? loaded : quasi), inputs: body } });
  });
}

const scene = (page: Page) => page.getByTestId("laminate-scene").or(page.getByTestId("webgl-missing"));

test("the home page draws the stack, posts it once and shows the engine's description", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.goto("/");
  await expect(scene(page)).toBeVisible();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0].material).toEqual({ library_id: "im7-8552", dataset_id: "ncamp-im7-8552-2019-rtd-measured-v1" });
  expect(posts[0].plies.map((ply) => ply.angle_deg)).toEqual([45, -45, 0, 90, 90, 0, -45, 45]);
  for (const ply of posts[0].plies) expect(ply.thickness_m).toBeCloseTo(0.00018288, 12);
  await expect(page.getByTestId("stack-row")).toHaveCount(8);
  const specs = page.getByTestId("specs");
  await expect(specs).toContainText("Quasi-isotropic");
  await expect(specs).toContainText("symmetric, balanced");
  await expect(specs).toContainText("1.463 mm");
  await expect(specs).toContainText("2.312 kg/m²");
  await expect(specs).toContainText("bending–twisting");
  await expect(page.getByTestId("failure-panel")).toHaveCount(0);
  await expect(page.getByTestId("abd-grid").getByRole("table", { name: "A matrix" })).toContainText("9.88e+7");
  await expect(page.getByTestId("property-row")).toContainText("1580");
  await expect(page.getByTestId("property-row")).toContainText("57.3");
  await page.waitForTimeout(700);
  expect(posts.length).toBe(1);
  expect(errors).toEqual([]);
});

test("typing a layup posts the expanded plies once the typing settles; an unreadable one posts nothing", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.goto("/");
  await expect.poll(() => posts.length).toBe(1);
  const layup = page.getByLabel("Layup", { exact: true });
  await layup.fill("[0/90]s");
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[1].plies.map((ply) => ply.angle_deg)).toEqual([0, 90, 90, 0]);
  await expect(page.getByTestId("stack-row")).toHaveCount(4);
  await layup.pressSequentially("x", { delay: 20 });
  await expect(page.locator("#hero-layup-hint")).toContainText("Could not read the layup");
  await expect(page.locator(".hero-laminate-results").getByRole("alert")).toContainText("Could not read the layup");
  await page.waitForTimeout(700);
  expect(posts.length).toBe(2);
  await layup.fill("[0/45/-45/90]");
  await layup.fill("[0/45]");
  await expect.poll(() => posts.length).toBe(3);
  expect(posts[2].plies.map((ply) => ply.angle_deg)).toEqual([0, 45]);
  await page.waitForTimeout(700);
  expect(posts.length).toBe(3);
});

test("a load turns on first-ply failure, with the engine's reasons for the criteria it did not run", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.goto("/");
  await expect.poll(() => posts.length).toBe(1);
  await page.getByText("Add loads per unit width").click();
  await page.getByLabel("Nx (N/m)", { exact: true }).fill("25000");
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[1].loads.Nx).toBe(25000);
  const panel = page.getByTestId("failure-panel");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Maximum stress");
  await expect(panel).toContainText("28.1");
  await expect(panel).toContainText("4 (+90°)");
  await expect(panel).toContainText("transverse tension");
  await expect(panel).toContainText("Tsai-Hill");
  await expect(panel).toContainText("Not computed: Maximum strain");
});

test("Want to check the math? carries the stack to the full calculator", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.goto("/");
  await expect.poll(() => posts.length).toBe(1);
  await page.getByRole("link", { name: "Want to check the math?" }).click();
  await expect(page).toHaveURL(/\/calculator\/?$/);
  await expect(page.getByLabel("Ply 1 angle (°)", { exact: true })).toHaveValue("45");
  await expect(page.getByLabel("Ply 8 angle (°)", { exact: true })).toHaveValue("45");
  await expect(page.getByLabel("Ply 1 thickness (mm)", { exact: true })).toHaveValue("0.18288");
  await expect(page.getByLabel("Library material", { exact: true })).toHaveValue("im7-8552::ncamp-im7-8552-2019-rtd-measured-v1");
  await expect(page.getByText("Inputs carried over from the home page")).toBeVisible();
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
});

test("the home page fits a phone without horizontal scroll", async ({ page }) => {
  const posts: Posted[] = [];
  await playApi(page, posts);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(scene(page)).toBeVisible();
  await expect.poll(() => posts.length).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
