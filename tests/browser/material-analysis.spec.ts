import { test, expect } from "@playwright/test";

test("curated lookup has dated original references, dual units and no classroom fallback", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByText("20 materials", { exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "English / imperial", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "SI / metric", exact: true })).toBeVisible();
  await expect(page.locator(".cited-properties")).not.toContainText(/Appendix F|School source|identity needed|unverified/i);
  await expect(page.locator('[data-property="E1"]')).toContainText("147 GPa");
  await expect(page.locator('[data-property="F1t"]')).toContainText("2,280 MPa");
  await expect(page.locator('[data-property="E3"]')).toContainText("10.3 GPa");
  await page.getByRole("combobox", { name: "Property dataset" }).selectOption("maddocks-1995-table-6-2");
  await expect(page.locator('[data-property="F1t"]')).toHaveCount(0);
  await expect(page.locator(".property-reference")).toContainText("May 1995");
  await expect(page.getByRole("link", { name: "Open reference" })).toHaveAttribute("href", /ntrs.nasa.gov.+#page=95$/);
  await expect(page.locator('[data-property="E1"]')).toContainText("142 GPa");
  await expect(page.locator('[data-property="alpha1"]')).toContainText("-0.2 10⁻⁶/°F");
  await page.getByRole("button", { name: "Stiffness", exact: true }).click();
  await expect(page.locator('[data-property="alpha1"]')).toHaveCount(0);
  await page.getByRole("textbox", { name: "Search materials" }).fill("carbon fiber");
  await expect(page.getByRole("heading", { name: "AS4 / 3501-6", exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Search materials" }).fill("CF0302");
  await expect(page.getByRole("heading", { name: "No material records match." })).toBeVisible();
});

test("NCAMP export preserves measured basis, methods, conditions and exact page references", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("7781");
  await expect(page.locator('[data-property="nu12"]')).toContainText("0.157");
  await expect(page.locator('[data-property="E1t"]')).toContainText("3.73 Msi");
  await expect(page.locator(".property-reference")).toContainText("September 2001");
  await page.getByRole("combobox", { name: "Property dataset" }).selectOption("ncamp-e765-2025-rtd-measured-v2");
  await expect(page.locator('[data-property="nu12"]')).toHaveCount(0);
  await expect(page.locator('[data-property="E1t"]')).toContainText("3.7 Msi");
  await expect(page.locator('[data-property="F12-offset"]')).toContainText("5.002 ksi");
  await expect(page.locator(".property-reference")).toContainText("Feb 25, 2025");
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".cited-reference-details")).toContainText("ASTM D3039/D3039M-17");
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export referenced values" }).click();
  const stream = await (await pending).createReadStream(); const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const data = JSON.parse(Buffer.concat(chunks).toString());
  expect(data.properties).toHaveLength(17);
  expect(data.source.date).toBe("2025-02-25");
  expect(data.properties[0].basis).toBe("Measured mean");
  expect(data.properties[0].referenceUrl).toMatch(/#page=18$/);
  expect(data.conditions).toContain("NMS 765/5");
  expect(data.designAllowables).toBe(false);
});

test("supplier dataset remains available offline and conflicting values are absent", async ({ page }) => {
  await page.route("**/materials/catalog-status.json", route => route.fulfill({ status:503, body:"offline" }));
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("M55J");
  await expect(page.locator(".dataset-summary")).toContainText("121°C autoclave");
  await expect(page.locator(".simple-property-table")).not.toContainText("Tensile Modulus");
  await expect(page.locator(".simple-property-table [data-property]")).toHaveCount(7);
  await expect(page.locator(".property-reference")).toContainText("Jan 28, 2020");
  await page.setViewportSize({ width:390, height:844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator(".simple-property-table").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
});

test("carbon qualification exports its complete elastic set and supporting specifications", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("8552");
  await expect(page.getByRole("heading", { name: "AS4 / 8552", exact: true })).toBeVisible();
  await expect(page.locator('[data-property="E1t"]')).toContainText("19.09 Msi");
  await expect(page.locator('[data-property="nu12"]')).toContainText("0.302");
  await expect(page.locator('[data-property="F1c-derived"]')).toContainText("Derived lamina mean");
  await expect(page.locator('[data-property="E1t"] a')).toHaveAttribute("href", /AS4-Unitape-2.pdf#page=32$/);
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".cited-reference-details")).toContainText("NMS 128/1 · Rev B");
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export referenced values" }).click();
  const stream = await (await pending).createReadStream(); const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const data = JSON.parse(Buffer.concat(chunks).toString());
  expect(data.properties).toHaveLength(21);
  expect(data.elasticInputs).toEqual({ E1: "E1t", E2: "E2t", G12: "G12", nu12: "nu12" });
  expect(data.supportingReferences).toHaveLength(4);
  expect(data.source.date).toBe("2011-05-06");
  expect(data.properties.find((p: { key: string }) => p.key === "SBS").conditions).toContain("70°F");
  await page.setViewportSize({ width:390, height:844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
