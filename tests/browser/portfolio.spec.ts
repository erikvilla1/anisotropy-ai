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

test("the chat keeps a coupon across messages and starts over on request", async ({
  page,
}) => {
  await page.goto("/chat");
  const box = page.getByRole("textbox", { name: "Message the coupon assistant" });
  await box.fill("Open-hole tension 250 x 36 mm, 6 mm hole");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByTestId("chat-spec")).toContainText("250 × 36 mm");
  await box.fill("AS4/8552, 20 kN");
  await box.press("Enter");
  await expect(page.getByTestId("chat-spec")).toContainText("Ø6 mm hole");
  await expect(page.getByTestId("chat-spec")).toContainText("20000 N force");
  await expect(page.getByTestId("chat-spec")).toContainText("AS4");
  await box.fill("hello");
  await box.press("Enter");
  await expect(page.getByText("I could not read a coupon value in that")).toBeVisible();
  await page.getByRole("button", { name: "Start a new coupon" }).click();
  await expect(page.locator(".chat-user")).toHaveCount(0);
  await expect(page.getByTestId("chat-spec")).not.toContainText("250");
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
    page.getByRole("textbox", { name: "Message the coupon assistant" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /^Open-hole tension/ }).click();
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "material");
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
