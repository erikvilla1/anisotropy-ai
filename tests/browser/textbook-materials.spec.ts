import { test, expect } from "@playwright/test";

test("textbook lookup identifies its book, printed page and units without pretending to host a PDF", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("M10E");
  await expect(page.getByRole("heading", { name: "M10E / 3783", exact: true })).toBeVisible();
  await expect(page.locator('[data-property="E1"]')).toContainText("24.5 GPa");
  await expect(page.locator('[data-property="E3"]')).toContainText("11.6 GPa");
  await expect(page.locator('[data-property="F23"]')).toContainText("44 MPa");
  await expect(page.locator('[data-property="density"]')).toContainText("1,900 kg/m³");
  await expect(page.locator(".property-reference")).toContainText("2006");
  await expect(page.locator(".dataset-summary")).toContainText("printed page 379");
  await expect(page.getByRole("link", { name: "Publisher & book" })).toHaveAttribute("href", /global.oup.com.*9780195150971$/);
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".reference-monitor-status")).not.toContainText("unavailable");
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export referenced values" }).click();
  const stream = await (await pending).createReadStream(); const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const data = JSON.parse(Buffer.concat(chunks).toString());
  expect(data.properties).toHaveLength(23);
  expect(data.source.printedPage).toBe(379);
  expect(data.properties.find((p: {key:string}) => p.key === "E3").printedPage).toBe(380);
  expect(data.properties.find((p: {key:string}) => p.key === "density").sourceValue).toBe(1.9);
  expect(data.properties[0].referenceUrl).not.toContain("#page=");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("qualified glass shows observed ranges and absolute-temperature conversions", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("7781 / E");
  await expect(page.locator('[data-property="density-WT"]')).toContainText("1,810–1,860 kg/m³");
  await expect(page.locator('[data-property="tply-WT"]')).toContainText("0.23114–0.25654 mm");
  await page.getByRole("button", { name: "Thermal & moisture", exact: true }).click();
  await expect(page.locator('[data-property="Tg-dry"]')).toContainText("335.2 °F");
  await expect(page.locator('[data-property="Tg-dry"]')).toContainText("168.444 °C");
  await expect(page.locator('[data-property="Tg-dry"] a')).toHaveAttribute("href", /#page=27$/);
  await expect(page.locator('[data-property="density-WT"]')).toHaveCount(0);
});

test("PEEK family is selectable and distinct from AS4 epoxy", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("combobox", { name: "Filter material family" }).selectOption("Carbon / PEEK");
  await expect(page.getByRole("heading", { name: "AS4 / APC2", exact: true })).toBeVisible();
  await expect(page.getByText("1 materials", { exact: true })).toBeVisible();
  await expect(page.locator('[data-property="E1"]')).toContainText("138 GPa");
});
