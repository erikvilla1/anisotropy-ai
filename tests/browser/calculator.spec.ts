import { test, expect } from "@playwright/test";
import example from "../../api/examples/zero-degree-tension.json";

test("calculator sends converted inputs to the real engine and displays its response", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.goto("/");
  await page.getByRole("link", { name: "Calculator", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("From layup to response.");
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
  const posted = page.waitForRequest((r) => r.url().endsWith("/v1/laminates/response") && r.method() === "POST");
  const answered = page.waitForResponse((r) => r.url().endsWith("/v1/laminates/response") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  expect((await posted).postDataJSON()).toEqual(example);
  const response = await answered;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.midplane_strain[0]).toBeCloseTo(100e6 / 147e9, 12);
  await expect(page.getByTestId("strain-0")).toHaveText(result.midplane_strain[0].toExponential(6));
  await expect(page.getByTestId("curvature-0")).toHaveText("0");
  for (const name of ["A matrix", "B matrix", "D matrix"]) await expect(page.getByRole("table", { name, exact: true })).toBeVisible();
  await page.getByLabel("Nx (N/m)", { exact: true }).fill("-25000");
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByTestId("strain-0")).toHaveText((-100e6 / 147e9).toExponential(6));
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/calculator-desktop.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("blank inputs and new plies need explicit values; the API reports invalid material compliance", async ({ page }) => {
  await page.goto("/calculator");
  let posts = 0;
  page.on("request", (r) => { if (r.method() === "POST") posts++; });
  await page.getByLabel("Ny (N/m)", { exact: true }).fill("");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByLabel("Ny (N/m)", { exact: true })).toHaveAttribute("aria-invalid", "true");
  expect(posts).toBe(0);
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByRole("button", { name: "Add ply" }).click();
  await expect(page.getByLabel("Ply 2 angle (°)", { exact: true })).toHaveValue("");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByLabel("Ply 2 thickness (mm)", { exact: true })).toHaveAttribute("aria-invalid", "true");
  expect(posts).toBe(0);
  await page.getByRole("button", { name: "Remove ply 2" }).click();
  await page.getByLabel("ν₁₂", { exact: true }).fill("10");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByText(/Elastic constants violate positive compliance/)).toBeVisible();
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
});

test("a multi-ply mixed-load request preserves stacking and uses the real engine", async ({ page }) => {
  await page.goto("/calculator");
  await page.getByRole("button", { name: "Add ply" }).click();
  await page.getByLabel("Ply 2 angle (°)", { exact: true }).fill("90");
  await page.getByLabel("Ply 2 thickness (mm)", { exact: true }).fill("0.25");
  await page.getByLabel("Mx (N·m/m)", { exact: true }).fill("2");
  const answered = page.waitForResponse((r) => r.url().endsWith("/v1/laminates/response") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  const response = await answered;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.inputs.plies.map((p: { angle_deg: number }) => p.angle_deg)).toEqual([0, 90]);
  expect(result.inputs.loads.Mx).toBe(2);
  expect(Math.abs(result.B_N[0][0])).toBeGreaterThan(0);
  await expect(page.getByTestId("curvature-0")).toHaveText(result.curvature_per_m[0].toExponential(6));
});

test("network failure and malformed success responses never display a result", async ({ page }) => {
  await page.goto("/calculator");
  await page.route("**/v1/laminates/response", (route) => route.abort("failed"));
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByRole("form", { name: "Laminate inputs" }).getByRole("alert")).toContainText("Cannot reach the calculation service");
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
  await page.unroute("**/v1/laminates/response");
  await page.route("**/v1/laminates/response", (route) => route.fulfill({ status: 200, json: { midplane_strain: [42] } }));
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByRole("form", { name: "Laminate inputs" }).getByRole("alert")).toContainText("unexpected result");
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
});

test("pending requests freeze inputs and can be cancelled without restoring stale results", async ({ page }) => {
  await page.goto("/calculator");
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/v1/laminates/response", async (route) => { await held; await route.abort().catch(() => {}); });
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByRole("button", { name: "Calculating…", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Nx (N/m)", { exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("form", { name: "Laminate inputs" }).getByRole("alert")).toContainText("Calculation cancelled");
  await expect(page.getByRole("button", { name: "Analyze laminate" })).toBeEnabled();
  release();
  await expect(page.getByTestId("calculation-results")).toHaveCount(0);
});

test("calculator fits a mobile viewport and remains usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/calculator");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  await expect(page.getByTestId("strain-0")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/calculator-mobile.png", fullPage: true });
  for (const width of [768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("picking a library material sends the dataset reference and shows the engine's cited values", async ({ page }) => {
  await page.goto("/calculator");
  await page.getByLabel("Library material", { exact: true }).selectOption("im7-8552::ncamp-im7-8552-2019-rtd-measured-v1");
  await expect(page.getByLabel("E₁ (GPa)", { exact: true })).toHaveValue("162.096");
  await expect(page.getByLabel("Ply 1 thickness (mm)", { exact: true })).toHaveValue("0.18288");
  const posted = page.waitForRequest((r) => r.url().endsWith("/v1/laminates/response") && r.method() === "POST");
  const answered = page.waitForResponse((r) => r.url().endsWith("/v1/laminates/response") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Analyze laminate" }).click();
  expect((await posted).postDataJSON().material).toEqual({ library_id: "im7-8552", dataset_id: "ncamp-im7-8552-2019-rtd-measured-v1" });
  const result = await (await answered).json();
  expect(result.material_provenance.dataset_id).toBe("ncamp-im7-8552-2019-rtd-measured-v1");
  // Uniaxial check with the engine's own SI values: eps_x = (Nx/h)/E1.
  expect(result.midplane_strain[0]).toBeCloseTo(25000 / result.material_provenance.ply_thickness_m / result.material_provenance.E1_pa, 12);
  await expect(page.getByTestId("material-provenance")).toContainText("CAM-RP-2009-015");
  await expect(page.getByTestId("material-provenance")).toContainText("E1 = 23.51 Msi");
  await page.getByLabel("E₁ (GPa)", { exact: true }).fill("150");
  await expect(page.getByLabel("Library material", { exact: true })).toHaveValue("");
});
