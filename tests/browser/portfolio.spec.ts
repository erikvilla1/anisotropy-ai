import { test, expect, type Page } from "@playwright/test";
import { sampleCSV } from "../../lib/demo";

/** The workspace as the product shows it (ADR-0089, ADR-0090): one test is offered, the unnotched tension coupon, so the assistant has no
 * test to ask for and opens on the material. Nothing in this file stands in for the API, so the page shows what the API offers; one started
 * with ANISOTROPY_ALL_TESTS=on shows every test, development's view, whose scenarios are studio.spec.ts's with its stand-in API. The first
 * question is asked once the API has answered about the switch, so waiting for it also waits for that answer. */
const expectProductView = (page: Page) =>
  expect(page.getByTestId("chat-question"), "the workspace should offer the unnotched tension coupon only: is the API running with ANISOTROPY_ALL_TESTS=on?")
    .toHaveAttribute("data-step", "material");

test("overview, the home page's blurbs, and material source document", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Calculated",
  );
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
  await expectProductView(page);
  const box = page.getByRole("textbox", { name: "Message the coupon assistant" });
  // The unnotched tension coupon, the test the workspace offers; the chat of the hidden tests, the open hole among them, is
  // studio.spec.ts's, with the switch on.
  await box.fill("Unnotched tension 250 x 25 mm, 56 mm tabs");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByTestId("chat-spec")).toContainText("250 × 25 mm, 56 mm tabs");
  await box.fill("AS4/8552, 20 kN");
  await box.press("Enter");
  await expect(page.getByTestId("chat-spec")).toContainText("20000 N force");
  await expect(page.getByTestId("chat-spec")).toContainText("AS4");
  await expect(page.getByTestId("chat-spec")).toContainText("250 × 25 mm, 56 mm tabs"); // the first message's size and tabs, kept by the second
  await box.fill("hello");
  await box.press("Enter");
  // A message that names no value changes nothing and is answered with the next thing to state (ADR-0062 part 5, in ADR-0091's words):
  // the layup, since the tension screen leaves G13 and G23 to the software (ADR-0090). The panel the answer names is not asserted here:
  // the tension screen has no step panels; studio.spec.ts follows that link on the full panels.
  await expect(page.getByText("Not sure what to change")).toBeVisible();
  await expect(page.getByTestId("chat-redirect").last()).toContainText("Next: what is the layup");
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
  // No test to tap: one is offered (ADR-0089), so the assistant opens on the material. A tap on one of its choices moves it on.
  await expectProductView(page);
  await page.getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "layup");
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
