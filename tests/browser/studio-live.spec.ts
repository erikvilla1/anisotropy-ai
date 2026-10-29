import { test, expect } from "@playwright/test";

// The whole chain on this machine: the public example through the real API, our engine, CalculiX and the package. It writes a
// coupon under .local/fea (IM7-UNT-L<n>, the next free layup code), so it runs only when asked for: STUDIO_LIVE=1.
test.skip(!process.env.STUDIO_LIVE, "set STUDIO_LIVE=1 to run the studio against the real API and CalculiX");

test("the example coupon solves end to end from the studio", async ({ page }) => {
  await page.goto("/studio");
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByLabel("Material code", { exact: true }).fill("IM7");
  await page.getByLabel("Layup code", { exact: true }).fill("");
  await page.getByLabel("Filled in by", { exact: true }).fill("Studio live test");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
  await page.getByLabel("Run by", { exact: true }).fill("Studio live test");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 300_000 });
  await expect(page.getByTestId("summary-reaction")).toContainText("N (tension)");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 300_000 });
  await expect(page.getByTestId("job-message")).toContainText("recorded values agree with CalculiX");
  await page.screenshot({ path: ".local/website/screenshots/studio-live.png", fullPage: true });
});
