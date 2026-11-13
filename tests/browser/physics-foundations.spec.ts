import { test, expect } from "@playwright/test";

test("physics foundations show source locations and units, and nothing internal or deferred", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("tab", { name: "Physics & references" }).click();
  await expect(page).toHaveURL(/\/library\/?\?tab=physics$/);
  await page.reload(); // the address reopens the same tab
  await expect(page.getByRole("tab", { name: "Physics & references" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".library-intro")).toContainText("42 equations for lamina and laminate analysis");
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
  await page.locator("summary").filter({ hasText: "Strength ratio with fixed & variable loads" }).click();
  await expect(page.locator(".method-entry[open]").filter({ hasText: "fixed & variable" })).toContainText("Eqs. 9.26–9.28, p. 256");
  await expect(page.locator(".method-entry[open]").filter({ hasText: "fixed & variable" }).locator(".physics-equation .katex")).not.toHaveCount(0);
  await page.getByRole("button", { name: /Classical Laminate Theory/ }).click();
  await page.getByRole("textbox", { name: "Search this physics topic" }).fill("Mixed load");
  await expect(page.locator(".method-entry").filter({ hasText: "Mixed load & deformation conditions" })).toContainText("known-load and known-deformation rows");
  await expect(page.locator(".physics-catalog")).not.toContainText(/ADR-\d|\bEngine\b|mixed_response/) // "Engine" the word, not "Engineering";
  await page.getByRole("button", { name: /Thermal & moisture effects/ }).click();
  await page.getByRole("textbox", { name: "Search this physics topic" }).fill("Residual");
  await expect(page.locator(".method-entry").filter({ hasText: "Residual ply stress" })).toContainText("Eq. 8.16, p. 213");
  await expect(page.locator(".physics-review-panel")).toHaveCount(0); // no textbook worked examples, no "Later research" (D6)
  await expect(page.locator("main")).not.toContainText(/Later research|Worked examples/);
  const references = page.locator(".references-panel");
  await expect(references.getByRole("heading", { name: "Sources we cite." })).toBeVisible();
  await expect(references).toContainText("NASA RP-1351");
  await expect(references).not.toContainText("User supplied");
  await expect(references.getByRole("link", { name: /^Search escholarship\.org/ })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
