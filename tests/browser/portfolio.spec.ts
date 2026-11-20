import { test, expect } from "@playwright/test";
import { sampleCSV } from "../../lib/demo";

test("overview, the home page's blurbs, and material source document", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  // The hero's statement is the heading, and the name stands beside the mark over it (ADR-0077 amendments 19, 27 and 47).
  await expect(page.getByRole("heading", { level: 1 })).toContainText("One engineering platform");
  await expect(page.locator(".site-header .wordmark")).toHaveText("Anisotropy");
  // The lab imagery carousel and its lightbox left the home page (audit of 2026-10-31, item 6).
  await expect(page.getByRole("button", { name: "Next research image" })).toHaveCount(0);
  for (const name of ["Five ways to use it.", "Every release, and what changed."])
    await expect(page.getByRole("heading", { name })).toBeVisible();
  // The team band left the home page for About (ADR-0077 amendment 73).
  await expect(page.getByRole("heading", { name: "From university to industry." })).toHaveCount(0);
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
  // This page is served with no API behind it, so it offers the unnotched tension coupon alone (ADR-0089) and its chat
  // asks for the material and the layup, the software choosing the rest (ADR-0090).
  await page.goto("/workspace/fea?for=coupon");
  const box = page.getByRole("textbox", { name: "Message the coupon assistant" });
  const size = page.getByTestId("panel-geometry").locator(".ws-panel-note"); // the tree says the setup tab by tab (ADR-0111)
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "material"); // no test to pick: the first question
  await box.fill("Open-hole tension 250 x 36 mm, 6 mm hole");
  await page.getByRole("button", { name: "Send message" }).click();
  // A test that is not offered is answered in words: its name and its hole stay out of the coupon, the size goes in.
  await expect(page.getByTestId("chat-not-available")).toContainText("Open-hole tension is not offered yet.");
  await expect(size).toHaveText("250 × 36 mm");
  await box.fill("AS4/8552, 20 kN");
  await box.press("Enter");
  await expect(page.getByTestId("panel-loads").locator(".ws-panel-note")).toHaveText("20000 N pull");
  await expect(page.getByTestId("panel-material").locator(".ws-panel-note")).toContainText("AS4");
  // The first message's size stands beside the second's rows, on the one test offered.
  await expect(size).toHaveText("250 × 36 mm");
  await expect(page.getByTestId("panel-test").locator(".ws-panel-note")).toContainText("Unnotched tension");
  await expect(size).not.toContainText("hole");
  await box.fill("hello");
  await box.press("Enter");
  // A message that names no value is answered with the next thing to state (ADR-0062 part 5), in the product's own words
  // (ADR-0091); this chat asks for no shear moduli, so with the material stated that is the layup. The panel the answer
  // names is not checked here: it is one of the full panels, which this screen does not have.
  await expect(page.getByText("Not sure what to change")).toBeVisible();
  await expect(page.getByTestId("chat-redirect").last()).toContainText("Next: what is the layup");
  await page.getByRole("button", { name: "Start a new coupon" }).click();
  await expect(page.locator(".chat-user")).toHaveCount(0);
  await expect(size).not.toContainText("250");
});

test("example data and local CSV imports are checked before the records are downloaded", async ({
  page,
}) => {
  await page.goto("/data");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  for (const part of [page.locator(".studio-heading"), page.locator("#data-panel")])
    await expect(part).not.toContainText(/PREVIEW|LAB LOOP|\bdemo\b|\btrain\b|submission/i);
  const intro = page.getByRole("heading", { level: 2, name: /Every coupon adds evidence/ });
  await expect(intro).toBeVisible();
  // The intro keeps its own size; the page's generic h2 rule (40 px) does not reach it.
  expect(await intro.evaluate(el => getComputedStyle(el).fontSize)).toBe("27px");
  await expect(page.locator(".data-workspace .studio-mode")).toHaveCSS("font-size", "11px");
  await page.getByRole("button", { name: "Load example data" }).click();
  await expect(page.getByText("File checked: ready for review.")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download checked records (JSON)" }).click();
  expect((await download).suggestedFilename()).toBe("example-coupons-checked.json");
  await expect(page.getByText("Checked records downloaded.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Remove dataset" }).click();
  await page.getByLabel("Choose a test CSV").setInputFiles({
    name: "invalid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(sampleCSV.replace("48.2", "-1")),
  });
  await expect(
    page.getByText("Failure load (kN) must be a positive number.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Download checked records (JSON)" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Remove dataset" }).click();
  await page.getByLabel("Choose a test CSV").setInputFiles({
    name: "valid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(sampleCSV),
  });
  await expect(
    page.getByRole("button", { name: "Download checked records (JSON)" }),
  ).toBeEnabled();
  await expect(page.locator(".data-steps li[aria-current=step]")).toContainText("Download checked records");
});

test("mobile navigation and workspaces fit the screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  // Inside the header's navigation: the footer has a Workspace link too (ADR-0077 amendment 13).
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/?$/);
  await page.getByTestId("workspace-tiles").locator("[data-workspace=fea]").click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await page.getByTestId("fea-start-kinds").locator("[data-kind=coupon]").click(); // FEA opens blank; a coupon is picked (ADR-0124)
  await expect(
    page.getByRole("textbox", { name: "Message the coupon assistant" }),
  ).toBeVisible();
  // One test is offered (ADR-0089), so the chat has none to pick and opens on the material; a tap on one moves it on to the layup.
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "material");
  await question.getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "layup");
  await page.screenshot({
    path: ".preview/mobile-workspace.png",
    fullPage: false,
  });
  await page.goto("/data");
  await expect(page.locator(".data-intro h2")).toHaveCSS("font-size", "24px");
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
