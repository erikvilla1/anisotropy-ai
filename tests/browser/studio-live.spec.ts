import { test, expect } from "@playwright/test";

// The whole chain on this machine: the public example through the real API, our engine, CalculiX and the package. It writes a
// coupon under .local/fea (IM7-UNT-L<n>, the next free layup code), so it runs only when asked for: STUDIO_LIVE=1.
test.skip(!process.env.STUDIO_LIVE, "set STUDIO_LIVE=1 to run the studio against the real API and CalculiX");

test("the example coupon solves end to end from the studio", async ({ page }) => {
  await page.goto("/workspace/fea"); // the rows are the left column of the workspace (ADR-0062)
  await page.getByRole("button", { name: "Load example" }).click();
  // the coupon's codes are derived or reused (ADR-0038 amendment 1); "Filled in by" sits under Advanced and takes the Run by name when blank
  await page.getByLabel("Run by", { exact: true }).fill("Studio live test"); // names who fills and who runs the coupon
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 300_000 });
  await expect(page.getByTestId("summary-reaction")).toContainText("N (in tension)");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 300_000 });
  await expect(page.getByTestId("job-message")).toContainText("recorded values agree with CalculiX");
  await page.screenshot({ path: ".local/website/screenshots/studio-live.png", fullPage: true });
});
