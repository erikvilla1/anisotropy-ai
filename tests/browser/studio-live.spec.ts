import { test, expect } from "@playwright/test";

// The whole chain: the public example through the real API, our engine, CalculiX and the package. On this machine it writes a
// coupon under .local/fea (IM7-UNT-L<n>, the next free layup code); against the hosted site (PREVIEW_URL, with a service token for
// Cloudflare Access) it writes one in the hosted tier's store. So it runs only when asked for: STUDIO_LIVE=1 or PREVIEW_URL.
test.skip(!process.env.STUDIO_LIVE && !process.env.PREVIEW_URL, "set STUDIO_LIVE=1 for the API on this machine, or PREVIEW_URL for the hosted site");

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
  await expect(page.getByTestId("summary-reaction")).toContainText("N (in tension)");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 300_000 });
  await expect(page.getByTestId("job-message")).toContainText("recorded values agree with CalculiX");
  await page.screenshot({ path: ".local/website/screenshots/studio-live.png", fullPage: true });
});
