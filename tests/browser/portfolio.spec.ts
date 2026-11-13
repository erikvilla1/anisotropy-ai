import { test, expect } from "@playwright/test";
import { sampleCSV } from "../../lib/demo";

test("overview, the home page's blurbs, and material source document", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  // The hero's statement is the heading, and the name stands beside the mark under it (ADR-0077 amendments 19 and 27).
  await expect(page.getByRole("heading", { level: 1 })).toContainText("one engineering platform");
  await expect(page.locator(".home-hero-tagline")).toHaveText("Anisotropy");
  // The lab imagery carousel and its lightbox left the home page (audit of 2026-10-31, item 6).
  await expect(page.getByRole("button", { name: "Next research image" })).toHaveCount(0);
  for (const name of ["Your layup, calculated.", "Five ways to use it.", "Five people, two seats each.", "Lately."])
    await expect(page.getByRole("heading", { name })).toBeVisible();
  // The Impact section left the home page (ADR-0077 amendment 14).
  await expect(page.getByRole("heading", { name: "Knowledge worth building on." })).toHaveCount(0);
  // Course material is never served as a public asset (ADR-0018).
  for (const path of ["/assets/documents/material-properties-2026-v2.pdf"])
    expect((await request.get(path)).status()).toBe(404);
  expect(errors).toEqual([]);
});

test("the chat keeps a coupon across messages and starts over on request", async ({
  page,
}) => {
  await page.goto("/workspace/fea");
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
  // A message that names no value is sent to the panel holding the next thing to state (ADR-0062 part 5);
  // the library lists no G13 or G23 for AS4/8552, so that is the shear moduli, on the layup and material panel.
  await expect(page.getByText("Pick a step on the left, or describe one thing")).toBeVisible();
  const redirect = page.getByTestId("chat-redirect").last();
  await expect(redirect).toHaveAttribute("data-panel", "layup");
  await expect(redirect).toContainText("The next thing to state is out-of-plane shear moduli, under the Layup and material panel.");
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
  // Inside the header's navigation: the footer has a Workspace link too (ADR-0077 amendment 13).
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/?$/);
  await page.getByRole("button", { name: /New coupon fea project/i }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
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
