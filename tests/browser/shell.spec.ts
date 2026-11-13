import { test, expect } from "@playwright/test";

// The site's shell after the audit of 2026-11-12 (ADR-0077 amendment 16, ADR-0058 amendment 2): the 404 page, the titles, the folded
// menu's keyboard order, Back to top and the workspace header's way back to the projects. Runs against the built site.

test("an unknown address gets the site's own 404 page, with one title and the skip link's target", async ({ page }) => {
  const answer = await page.goto("/this-page-does-not-exist");
  expect(answer?.status()).toBe(404);
  await expect(page).toHaveTitle("Page not found | Anisotropy");
  expect(await page.locator("title").count()).toBe(1);
  await expect(page.locator("main#main h1")).toHaveText("Page not found");
  await expect(page.locator("main#main").getByRole("link", { name: "Home", exact: true })).toHaveAttribute("href", "/");
  await expect(page.locator("main#main").getByRole("link", { name: "Workspace", exact: true })).toHaveAttribute("href", "/workspace");
  // the site's dark ground, not the framework's white page
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).not.toBe("rgb(255, 255, 255)");
});

test("an unknown address under an old one or under the workspace keeps the 404 page's own header and footer", async ({ page }) => {
  const hydration: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && /hydrat/i.test(m.text())) hydration.push(m.text()); });
  // /workspace/cad was the CAD placeholder until decision D5 (ADR-0091 amendment 2)
  for (const path of ["/studio/x", "/workspace/cad"]) {
    await page.goto(path);
    await expect(page.locator("main#main h1"), path).toHaveText("Page not found");
    await expect(page.locator(".site-header:not(.chat-site-header)"), path).toBeVisible();
    await expect(page.locator(".site-footer"), path).toBeVisible();
  }
  expect(hydration).toEqual([]);
});

test("every page's title is its name and the site's, and the home's is the tagline", async ({ page }) => {
  for (const [path, title] of [
    ["/", "Anisotropy | Composites. Calculated."],
    ["/about", "About | Anisotropy"],
    ["/services/test-plans", "Test plans | Anisotropy"],
    ["/workspace", "Workspace | Anisotropy"],
    ["/workspace/fea/view", "Viewer | Anisotropy"],
  ]) {
    await page.goto(path);
    await expect(page, path).toHaveTitle(title);
    expect(await page.locator("meta[name=description]").getAttribute("content"), path).toBeTruthy();
  }
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the menu's button comes before its links, takes the focus to them, and Escape or a press outside closes it", async ({ page }) => {
    await page.goto("/about");
    const toggle = page.getByRole("button", { name: "Open menu" });
    await expect(toggle).toHaveAttribute("aria-controls", "site-menu");
    // in the page's order the button is first, so the next Tab after it reaches the links
    expect(await page.evaluate(() => {
      const button = document.querySelector(".menu-toggle")!;
      return Boolean(button.compareDocumentPosition(document.getElementById("site-menu")!) & Node.DOCUMENT_POSITION_FOLLOWING);
    })).toBe(true);
    await toggle.click();
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav.getByRole("link", { name: "About", exact: true })).toBeFocused();
    const row = await nav.getByRole("link", { name: "Industries", exact: true }).boundingBox();
    expect(row!.height).toBeGreaterThanOrEqual(44);
    await page.keyboard.press("Escape");
    await expect(nav).toBeHidden();
    await expect(page.getByRole("button", { name: "Open menu" })).toBeFocused();
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(nav).toBeVisible();
    await page.locator("main#main").dispatchEvent("pointerdown"); // a press on the page outside the header
    await expect(nav).toBeHidden();
    // Tab past the menu's last link, into the page, closes it too
    await page.getByRole("button", { name: "Open menu" }).click();
    await nav.getByRole("link", { name: "Workspace" }).focus();
    await page.keyboard.press("Tab");
    await expect(nav).toBeHidden();
  });

  test("in the folded menu the current service's row is underlined, and Services marks the section", async ({ page }) => {
    await page.goto("/services/test-plans");
    await page.getByRole("button", { name: "Open menu" }).click();
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    const row = nav.getByRole("link", { name: "Test plans", exact: true });
    await expect(row).toHaveAttribute("aria-current", "page");
    expect(await row.evaluate((a) => getComputedStyle(a).textDecorationLine)).toContain("underline");
    await expect(nav.getByRole("link", { name: "Services", exact: true })).toHaveAttribute("aria-current", "true");
  });

  test("the viewer's header links back to the projects", async ({ page }) => {
    await page.goto("/workspace/fea/view"); // the CAD page that also did is gone (decision D5, ADR-0091 amendment 2)
    await expect(page.locator(".site-header").getByRole("link", { name: "All projects" })).toHaveAttribute("href", "/workspace");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});

test("Back to top takes the focus to the top with the page", async ({ page }) => {
  await page.goto("/about");
  await page.getByRole("link", { name: "Back to top" }).click();
  await expect(page.locator(".site-header .wordmark")).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  expect(new URL(page.url()).hash).toBe("");
});
