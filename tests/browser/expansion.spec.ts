import { test, expect } from "@playwright/test";

test("a negative load stays negative so the setup check can refuse it (ADR-0003)", async ({ page }) => {
  await page.goto("/chat");
  await page.getByRole("textbox", { name: "Message the coupon assistant" }).fill("Unnotched tension, apply -20 kN");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".chat-understood").last()).toContainText("-20000 N force");
  await expect(page.getByTestId("chat-spec")).toContainText("-20000 N force");
});

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
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "test");
  expect(errors).toEqual([]);
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
  await expect(page).toHaveURL(/\/chat\/?$/); // not a library material of the engine: the chat asks from the start
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "test");
  await page.goto("/chat?material=im7-8552");
  await expect(page.getByTestId("chat-spec")).toContainText("IM7 / 8552");
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
