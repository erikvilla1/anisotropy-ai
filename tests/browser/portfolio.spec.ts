import { test, expect } from "@playwright/test";
import { sampleCSV } from "../../lib/demo";

test("overview, source images, modal dismissal, and material source document", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "understanding",
  );
  await page.getByRole("button", { name: "Next research image" }).click();
  await expect(
    page.getByRole("heading", { name: "One specimen. More context." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Enlarge CSAI-04 · Source coupon image" })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  for (const name of [
    "Vacuum jig setup",
    "Twist drill surface evaluation",
    "Research visualization study",
  ]) {
    await page.getByRole("button", { name, exact: false }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect
      .poll(() =>
        page
          .getByRole("dialog")
          .locator("img")
          .evaluate(
            (img: HTMLImageElement) => img.complete && img.naturalWidth > 0,
          ),
      )
      .toBeTruthy();
    await page.getByRole("button", { name: "Close image viewer" }).click();
  }
  // Course material is never served as a public asset (ADR-0018).
  for (const path of ["/assets/documents/material-properties-2026-v2.pdf"])
    expect((await request.get(path)).status()).toBe(404);
  expect(errors).toEqual([]);
});

test("scoping conversation preserves inputs, varies formats, and downloads JSON", async ({
  page,
}) => {
  await page.goto("/chat");
  await page
    .getByRole("textbox", { name: "Message the scope assistant" })
    .fill("Scope a carbon epoxy D5766 coupon 250 x 36 mm at 20 kN");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".scope-fields").last()).toContainText(
    "250 × 36 mm",
  );
  await page
    .getByRole("textbox", { name: "Message the scope assistant" })
    .fill("Factor of safety 1.5");
  await page
    .getByRole("textbox", { name: "Message the scope assistant" })
    .press("Enter");
  await expect(page.locator(".scope-fields").last()).toContainText("20 kN");
  await expect(page.locator(".scope-fields").last()).toContainText("1.5");
  await page.getByLabel("Response format").selectOption("json");
  await page
    .getByRole("textbox", { name: "Message the scope assistant" })
    .fill("Export my scope");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("pre")).toContainText('"width_mm": 36');
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download scope JSON" }).click();
  expect((await download).suggestedFilename()).toBe("anisotropy-ai-scope.json");
  await page.getByRole("button", { name: "Reset conversation" }).click();
  await expect(page.locator(".conversation-turn")).toHaveCount(0);
  await page.getByLabel("Response format").selectOption("auto");
  await page
    .getByRole("button", { name: "Compare D3039 and D5766", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Two tests. Different questions." }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "What test data should I submit?",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Build a traceable test record." }),
  ).toBeVisible();
});

test("example data and local CSV imports validate before submission", async ({
  page,
}) => {
  await page.goto("/data");
  await page.getByRole("button", { name: "Load example data" }).click();
  await expect(page.getByText("Preview schema checks passed")).toBeVisible();
  await page.getByRole("button", { name: "Preview submission" }).click();
  await expect(
    page.getByRole("heading", { name: "Submission preview complete." }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download review package" }).click();
  expect((await download).suggestedFilename()).toBe("submission-preview.json");
  await page.getByRole("button", { name: "Remove dataset" }).click();
  await page.getByLabel("Upload test CSV").setInputFiles({
    name: "invalid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(sampleCSV.replace("48.2", "-1")),
  });
  await expect(
    page.getByText("failure_load_kN must be a positive number.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Preview submission" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Remove dataset" }).click();
  await page.getByLabel("Upload test CSV").setInputFiles({
    name: "valid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(sampleCSV),
  });
  await expect(
    page.getByRole("button", { name: "Preview submission" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Preview submission" }).click();
  await expect(
    page.getByText("No records were sent to a server.", { exact: false }),
  ).toBeVisible();
});

test("mobile navigation and workspaces fit the screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Open chat", exact: true }).click();
  await expect(page).toHaveURL(/\/chat\/?$/);
  await expect(
    page.getByRole("textbox", { name: "Message the scope assistant" }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Scope an open-hole tension coupon",
      exact: true,
    })
    .click();
  await expect(page.locator(".scope-fields")).toContainText("ASTM D5766");
  await page.screenshot({
    path: ".preview/mobile-workspace.png",
    fullPage: false,
  });
  await page.goto("/data");
  await page.getByRole("button", { name: "Load example data" }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: ".preview/mobile-full.png", fullPage: true });
  await page.setViewportSize({ width: 320, height: 740 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
