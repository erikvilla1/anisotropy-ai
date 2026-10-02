import { test, expect } from "@playwright/test";

test("physics foundations show source locations, units and explicitly deferred research", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("tab", { name: "Physics & references" }).click();
  await expect(page.locator(".physics-intro")).toContainText("29 reference cards");
  await page.getByRole("button", { name: /Constituents & material estimates/ }).click();
  await page.getByRole("textbox", { name: "Search this physics topic" }).fill("Halpin");
  const card = page.locator(".method-entry").filter({ hasText: "Halpin–Tsai estimate" });
  await expect(card).toContainText("Eqs. 3.17–3.20, p. 48");
  await expect(card).toContainText("no universal ξ");
  await expect(card.locator(".equation-units")).toContainText("nonzero");
  await expect(card.locator(".equation-reference a")).toHaveAttribute("href", /global.oup.com/);
  await page.getByRole("button", { name: /Ply failure criteria/ }).click();
  await page.locator("summary").filter({ hasText: "Maximum strain" }).click();
  await expect(page.locator(".method-entry[open]")).toContainText("missing compression or shear");
  await page.locator("summary").filter({ hasText: "Worked examples & equation checks" }).click();
  await expect(page.locator(".physics-review-panel[open]")).toContainText("154.199 GPa");
  await page.locator("summary").filter({ hasText: "Later research:" }).click();
  await expect(page.locator(".physics-review-panel").last()).toContainText("CAD & finite elements");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
