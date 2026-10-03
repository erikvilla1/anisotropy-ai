import { test, expect } from "@playwright/test";

test("textbook lookup opens citations and property-specific source units without page scans", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("M10E");
  await expect(page.getByRole("heading", { name: "M10E / 3783", exact: true })).toBeVisible();
  await expect(page.locator('[data-property="E1"]')).toContainText("24.5 GPa");
  await expect(page.locator('[data-property="E3"]')).toContainText("11.6 GPa");
  await expect(page.locator('[data-property="F23"]')).toContainText("44 MPa");
  await expect(page.locator('[data-property="density"]')).toContainText("1,900 kg/m³");
  await expect(page.locator(".property-reference")).toContainText("2006");
  await expect(page.locator(".dataset-summary")).toContainText("printed page 379");
  await expect(page.getByRole("link", { name: "View source details" })).toHaveAttribute("href", /\/sources\?source=daniel-ishai-2006&page=399/);
  await page.locator('[data-property="density"] a').click();
  const sourcePage = page;
  await expect(sourcePage.getByRole("heading", { name: "Density", exact: true })).toBeVisible();
  await expect(sourcePage.locator(".source-values")).toContainText("1.9 g/cm³");
  await expect(sourcePage.locator(".source-values")).toContainText("1,900 kg/m³");
  await expect(sourcePage.locator(".source-location")).toContainText("Printed page 379");
  await expect(sourcePage.locator(".source-document-note")).toContainText("Table A.5, printed page 379");
  await expect(sourcePage.locator(".source-content img")).toHaveCount(0);
  await expect(sourcePage.getByRole("link", { name: "Find the book at the publisher" })).toHaveAttribute("href", /global\.oup\.com/);
  await sourcePage.setViewportSize({ width: 390, height: 844 });
  expect(await sourcePage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Material library", exact: true }).click();
  await page.getByRole("textbox", { name: "Search materials" }).fill("M10E");
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
  expect(data.properties[0].referenceUrl).toContain("/sources?source=daniel-ishai-2006&page=399");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("AS4 property citations route out-of-plane values to A.6", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("AS4 / 3501");
  await page.locator('[data-property="E1"] a').click();
  const source = page;
  await expect(source.locator(".source-location")).toContainText("Printed page 377");
  await expect(source.locator(".source-values")).toContainText("147 GPa");
  await expect(source.locator(".source-values")).toContainText("21.3205 Msi");
  await expect(source.locator(".source-document-note")).toContainText("Table A.4, printed page 377");
  await page.getByRole("link", { name: "Material library", exact: true }).click();
  await page.getByRole("textbox", { name: "Search materials" }).fill("AS4 / 3501");
  await page.locator('[data-property="E3"] a').click();
  const outOfPlane = page;
  await expect(outOfPlane.locator(".source-location")).toContainText("Table A.6");
  await expect(outOfPlane.locator(".source-location")).toContainText("Printed page 380");
  await expect(outOfPlane.locator(".source-document-note")).toContainText("Table A.6, printed page 380");
});

test("invalid citation links report an explicit error and source scans are not served", async ({ page }) => {
  await page.goto("/sources?source=daniel-ishai-2006&page=1");
  await expect(page.getByRole("heading", { name: "Source reference not available" })).toBeVisible();
  await page.goto("/sources?source=daniel-ishai-2006&page=400&dataset=daniel-ishai-2006-as4-3501-v2&property=E1");
  await expect(page.getByRole("heading", { name: "Source reference not available" })).toBeVisible();
  await page.goto("/sources?source=daniel-ishai-2006&page=397");
  await expect(page.locator(".source-document-note")).toContainText("Page scans are not distributed here");
  const scan = await page.request.get("/assets/documents/daniel-ishai-2006/page-397.png");
  expect(scan.status()).toBe(404);
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
