import { test, expect } from "@playwright/test";
const source = {
  id: "diab-divinycell-h-si", name: "Divinycell H", kind: "datasheet",
  sourceUrl: "https://diabgroup.com/products-services/divinycell-pvc/divinycell-h/",
  documentUrl: "https://diabgroup.com/fixture.pdf", fingerprint: "a".repeat(64),
  revision: "Revision 27", revisionDate: "2026-10", datePrecision: "month",
  dateMeaning: "Test fixture", lastChecked: "2026-10-01T12:00:00Z", lastSuccess: "2026-10-01T12:00:00Z",
  nextCheck: "2099-01-01T00:00:00Z", outcome: "changed", failed: false, review: "pending", propertyExtraction: "ready-for-review",
};
// The revision monitor runs only in a build made with NEXT_PUBLIC_MATERIAL_MONITOR=on; the hosted build leaves it off.
const monitor = process.env.NEXT_PUBLIC_MATERIAL_MONITOR === "on";

test("without the monitor the library fetches no status feed and says the values are pinned", async ({ page }) => {
  test.skip(monitor, "this build runs the monitor");
  const asked: string[] = [];
  page.on("request", request => { if (request.url().includes("catalog-status.json")) asked.push(request.url()); });
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("H45");
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".reference-monitor-status")).toHaveText("Values are pinned to the cited edition.");
  expect(asked).toEqual([]);
});

test("a changed supporting process specification is reported without changing carbon values", async ({ page }) => {
  test.skip(!monitor, "the monitor is off in this build");
  await page.route("**/materials/catalog-status.json", route => route.fulfill({ json: {
    schemaVersion: 1, generatedAt: new Date().toISOString(), sources: [{ ...source, id: "ncamp-8552-process", kind: "reference-document" }], candidates: [], releases: [],
  } }));
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("8552");
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".reference-monitor-status")).toContainText("changed document has been detected");
  await expect(page.locator('[data-property="E1t"]')).toContainText("19.09 Msi");
});
test("changed publication does not overwrite the cited property release", async ({ page }) => {
  test.skip(!monitor, "the monitor is off in this build");
  await page.route("**/materials/catalog-status.json", route => route.fulfill({ json: {
    schemaVersion: 1, generatedAt: new Date().toISOString(), sources: [source], candidates: [], releases: [],
  } }));
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("H45");
  await expect(page.locator(".property-reference")).toContainText("May 2026");
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".reference-monitor-status")).toContainText("changed document has been detected");
  await expect(page.locator('[data-property="compression-strength-nominal"]')).toContainText("0.6 MPa");
});
test("a changed document stays reported on the check after the change, until it is reviewed", async ({ page }) => {
  test.skip(!monitor, "the monitor is off in this build");
  await page.route("**/materials/catalog-status.json", route => route.fulfill({ json: {
    schemaVersion: 1, generatedAt: new Date().toISOString(), sources: [{ ...source, outcome: "unchanged", changedSinceReview: true }], candidates: [], releases: [],
  } }));
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("H45");
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".reference-monitor-status")).toContainText("changed document has been detected");
});
test("offline monitor retains referenced data and reports its state within reference details", async ({ page }) => {
  test.skip(!monitor, "the monitor is off in this build");
  await page.setViewportSize({ width:390, height:844 });
  await page.route("**/materials/catalog-status.json", route => route.fulfill({ status:503, body:"offline" }));
  await page.goto("/library");
  await page.getByRole("textbox", { name: "Search materials" }).fill("H45");
  await page.getByText("Reference & test details", { exact: true }).click();
  await expect(page.locator(".reference-monitor-status")).toContainText("currently unavailable");
  await expect(page.locator(".property-reference")).toContainText("May 2026");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
