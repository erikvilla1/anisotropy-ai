import { readdirSync, readFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { devices, expect, test, type Browser, type BrowserContext, type TestInfo } from "@playwright/test";
import { pageErrors } from "./page-errors";

// Every page on a phone as a phone is, not only a narrow window (ADR-0114): its screen, pixel density, touch and user agent. In
// WebKit it is an iPhone, as Safari on one is; in Chromium an Android phone. Firefox has no phone mode (isMobile), so it gets the
// Android phone's screen and touch without it. The specs that set a phone's width keep checking each page's own layout; this one
// checks that nothing breaks on any page when the browser is a phone.

const APP = join(process.cwd(), "app");

/** Every page of the site, from the app's page files: the pages that only send the visitor on (RedirectTo) are left out. */
function pages(): string[] {
  const found: string[] = [];
  const walk = (folder: string) => {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      const path = join(folder, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith("[") && !entry.name.startsWith("(") && !entry.name.startsWith("_")) walk(path);
      else if (entry.name === "page.tsx" && !readFileSync(path, "utf-8").includes("RedirectTo")) {
        found.push("/" + relative(APP, folder).split(sep).join("/"));
      }
    }
  };
  walk(APP);
  return found.map((page) => (page === "/" ? page : page.replace(/\/$/, ""))).sort();
}

async function phone(browser: Browser, browserName: string, info: TestInfo): Promise<BrowserContext> {
  const { defaultBrowserType: _engine, ...profile } = browserName === "webkit" ? devices["iPhone 15"] : devices["Pixel 7"];
  return browser.newContext({ ...profile, isMobile: browserName !== "firefox", baseURL: info.project.use.baseURL });
}

test("every page fits a phone's screen with no sideways scroll and no script error", async ({ browser, browserName }, info) => {
  const all = pages();
  expect(all).toContain("/");
  expect(all).toContain("/workspace/fea");
  const context = await phone(browser, browserName, info);
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", pageErrors(errors, () => page.url()));
  for (const path of all) {
    await page.goto(path);
    await expect(page.locator("main").first(), path).toBeVisible();
    const width = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, window: innerWidth }));
    expect(width.page, `${path} is wider than the phone's screen`).toBeLessThanOrEqual(width.window);
  }
  expect(errors).toEqual([]);
  await context.close();
});

test("on a phone the menu opens with a tap and leads to the workspace, where a tap answers the chat", async ({ browser, browserName }, info) => {
  const context = await phone(browser, browserName, info);
  const page = await context.newPage();
  await page.goto("/about");
  await page.getByRole("button", { name: "Open menu" }).tap();
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav).toBeVisible();
  await nav.getByRole("link", { name: "Workspace", exact: true }).tap();
  await expect(page).toHaveURL(/\/workspace\/?$/);
  await page.goto("/workspace/fea");
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "material"); // one test offered, so the chat opens on the material (ADR-0089)
  await question.getByRole("button", { name: "IM7 / 8552", exact: true }).tap();
  await expect(question).toHaveAttribute("data-step", "layup");
  await expect(page.getByRole("textbox", { name: "Message the coupon assistant" })).toBeVisible();
  await context.close();
});
