import { test, expect } from "@playwright/test";

test("a negative load stays negative so the setup check can refuse it (ADR-0003)", async ({ page }) => {
  await page.goto("/workspace/fea");
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
  // The footer repeats the header's links (ADR-0077 amendment 13), so the header's are found inside its navigation.
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await nav.getByRole("link", { name: "About", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "physical evidence",
  );
  await expect(page.locator(".technology-section")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "The team." })).toBeVisible();
  await expect(page.locator(".team-card")).toHaveCount(5);
  await expect(page.getByRole("heading", { name: "Start small. Prove it. Build forward." })).toBeVisible();
  await nav.getByRole("link", { name: "Industries", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Aerospace" })).toBeVisible();
  await nav.getByRole("link", { name: "Services", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "documented answer",
  );
  await page.getByRole("link", { name: "Development process streamlining" }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await page.reload();
  // One test is offered for now (ADR-0089), so the assistant's first question is the material, as workspace.spec.ts reads it.
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "material");
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
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/); // not a library material of the engine: the assistant asks from the start
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "material"); // the start, with one test offered (ADR-0089)
  await page.goto("/workspace/fea?material=im7-8552");
  await expect(page.getByTestId("chat-spec")).toContainText("IM7 / 8552");
});

test("the Services disclosure lists the five service pages and the contact page has an address (ADR-0058)", async ({
  page,
}) => {
  await page.goto("/");
  const button = page.getByRole("button", { name: "Show services" });
  // The footer lists the service pages too (ADR-0077 amendment 13); the disclosure's links are the header's.
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(button).toHaveAttribute("aria-expanded", "false");
  await expect(nav.getByRole("link", { name: "Finite element modeling", exact: true })).toBeHidden();
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(button).toHaveAttribute("aria-expanded", "true");
  const fem = nav.getByRole("link", { name: "Finite element modeling", exact: true });
  await expect(fem).toBeVisible();
  // Anduril's panel (ADR-0082 amendment 1): no rule under it, no status beside a link, the list named by its label and
  // starting under the header's first link.
  const panel = nav.locator(".services-panel");
  await expect(panel).toHaveCSS("border-bottom-width", "0px");
  await expect(panel.locator(".services-panel-list")).not.toContainText(/In part|Available|Planned/i);
  await expect(panel.locator(".services-panel-list li > :not(a)")).toHaveCount(0);
  await expect(nav.getByRole("list", { name: "Services" }).getByRole("link")).toHaveCount(5);
  const lefts = await nav.evaluate((el) => [
    el.querySelector(":scope > a")!.getBoundingClientRect().left,
    el.querySelector(".services-panel-list")!.getBoundingClientRect().left,
  ]);
  expect(Math.abs(lefts[0] - lefts[1])).toBeLessThanOrEqual(1);
  await page.keyboard.press("Escape");
  await expect(button).toHaveAttribute("aria-expanded", "false");
  await expect(button).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(nav.getByRole("link", { name: "Computer-aided design", exact: true })).toBeFocused();
  await fem.click();
  await expect(page).toHaveURL(/\/services\/finite-element-modeling\/?$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ply by ply");
  await expect(page.getByRole("link", { name: "Open the workspace", exact: true })).toHaveAttribute("href", /\/workspace\/fea$/);
  await page.getByRole("link", { name: "Contact us", exact: true }).first().click();
  await expect(page).toHaveURL(/\/contact\/?$/);
  await expect(page.getByRole("link", { name: /erikvilla947@gmail\.com/ })).toHaveAttribute("href", "mailto:erikvilla947@gmail.com");
  await expect(page.getByRole("link", { name: "Calculator", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Studio", exact: true })).toHaveCount(0);
  await expect(page.locator(".site-header .wordmark")).toHaveText("Anisotropy");
});

test("the mobile menu lists the five services under Services", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  const nav = page.getByRole("navigation", { name: "Main navigation" }); // the footer lists the same pages
  for (const name of ["Computer-aided design", "Finite element modeling", "Test plans", "Documentation", "Manufacturing plans"])
    await expect(nav.getByRole("link", { name, exact: true })).toBeVisible();
  await nav.getByRole("link", { name: "Test plans", exact: true }).click();
  await expect(page).toHaveURL(/\/services\/test-plans\/?$/);
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
      "/services/finite-element-modeling",
      "/contact",
      "/library",
      "/workspace",
      "/workspace/fea",
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
