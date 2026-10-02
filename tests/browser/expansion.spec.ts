import { test, expect } from "@playwright/test";

test("navigation routes load directly with research-focused About", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("link", { name: "About", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "physical evidence",
  );
  await expect(page.locator(".technology-section")).toHaveCount(0);
  await page.getByRole("link", { name: "Industries", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Aerospace" })).toBeVisible();
  await page.getByRole("link", { name: "Services", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "documented answer",
  );
  await page.getByRole("link", { name: "Development process streamlining" }).click();
  await expect(page).toHaveURL(/\/chat\/?$/);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Edit specification", exact: false }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("spec editor validates and feeds the chat and downloadable report outline", async ({
  page,
}) => {
  await page.goto("/chat");
  await page
    .getByRole("button", { name: "Edit specification", exact: false })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("combobox", { name: "Test method", exact: true })
    .selectOption("ASTM D5766");
  await dialog
    .getByLabel("Material system", { exact: true })
    .fill("CF-EP sample");
  await dialog.getByLabel("Width (mm)", { exact: true }).fill("36");
  await dialog.getByLabel("Length (mm)", { exact: true }).fill("250");
  await dialog.getByLabel("Hole diameter (mm)", { exact: true }).fill("40");
  await dialog.getByRole("button", { name: "Save draft" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "less than coupon width",
  );
  await dialog.getByLabel("Hole diameter (mm)", { exact: true }).fill("6");
  await dialog.getByLabel("Ply count", { exact: true }).fill("16");
  await dialog
    .getByLabel("Ply stacking sequence", { exact: true })
    .fill("[45/-45/0/90]2s");
  await dialog.getByRole("button", { name: "Save draft" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".scope-fields").last()).toContainText(
    "[45/-45/0/90]2s",
  );
  await page.getByLabel("Response format").selectOption("report");
  await page
    .getByRole("textbox", { name: "Message the scope assistant" })
    .fill("Prepare my report outline");
  await page.getByRole("button", { name: "Send message" }).click();
  const event = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download LaTeX outline" }).click();
  const file = await event;
  expect(file.suggestedFilename()).toBe("anisotropy-ai-report-outline.tex");
  const stream = await file.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const text = Buffer.concat(chunks).toString();
  expect(text).toContain("CF-EP sample");
  expect(text).toContain("250");
  expect(text).toContain("No engineering conclusion is available");
});

test("material filters, empty state, references and scope handoff", async ({
  page,
}) => {
  await page.goto("/library");
  await page
    .getByRole("textbox", { name: "Search materials" })
    .fill("unobtainium");
  await expect(
    page.getByRole("heading", { name: "No material records match." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await page
    .getByLabel("Filter material family")
    .selectOption("Sandwich cores");
  await expect(
    page.getByRole("heading", { name: "Nomex · HRH10-1/8-1.8", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Filter material family").selectOption("All families");
  await page.getByRole("tab", { name: "Physics & references" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Classical Laminate Theory",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Materials", exact: true }).click();
  await page
    .getByRole("button", { name: "7781 / E-765", exact: false })
    .click();
  await page.getByRole("link", { name: "Discuss this material" }).click();
  await page
    .getByRole("button", { name: "Edit specification", exact: false })
    .click();
  await expect(
    page.getByRole("dialog").getByLabel("Material system", { exact: true }),
  ).toHaveValue(
    "7781 / E-765",
  );
});

test("expanded pages fit phones and tablets with local-only visual assets", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const width of [390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    for (const path of [
      "/",
      "/about",
      "/industries",
      "/services",
      "/library",
      "/chat",
      "/data",
    ]) {
      await page.goto(path);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path: `.preview/${path.slice(1)}-${width}.png`,
        fullPage: true,
      });
    }
  }
  expect(errors).toEqual([]);
});
