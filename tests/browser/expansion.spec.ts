import { test, expect } from "@playwright/test";
import { SERVICES_PANEL_IN_HEADER } from "../../lib/site-nav";

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
  // The team band, which stood on the home page until ADR-0077 amendment 73, in place of the cards of names and seats.
  await expect(page.getByRole("heading", { name: "From university to industry." })).toBeVisible();
  await expect(page.locator("#team .team-face")).toHaveCount(5);
  await expect(page.getByRole("heading", { name: "Start small. Prove it. Build forward." })).toBeVisible();
  await nav.getByRole("link", { name: "Industries", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Aerospace" })).toBeVisible();
  await nav.getByRole("link", { name: "Services", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "documented answer",
  );
  await page.getByRole("link", { name: "Coupon analysis" }).click();
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
  await expect(page).toHaveURL(/[?&]material=7781-e765/); // the address names the selected material
  // Not a material the coupon workspace can analyse, so the library offers no link that would drop it.
  await expect(page.getByRole("link", { name: /Analyse in Workspace/ })).toHaveCount(0);
  await page.goto("/library?material=im7-8552");
  await expect(page.getByRole("heading", { name: "IM7 / 8552", exact: true })).toBeVisible();
  await page.getByRole("link", { name: /Analyse in Workspace/ }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("chat-spec")).toContainText("IM7 / 8552");
});

test("the Services disclosure lists the five service pages (ADR-0058)", async ({ page }) => {
  test.skip(!SERVICES_PANEL_IN_HEADER, "the Services panel is hidden from the header for now (ADR-0058 amendment 4)");
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
});

test("a service page leads to the workspace and the contact page has an address (ADR-0058)", async ({ page }) => {
  await page.goto("/services/finite-element-modeling");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ply by ply");
  await expect(page.getByRole("link", { name: "Open the workspace", exact: true })).toHaveAttribute("href", /\/workspace\/fea$/);
  await page.getByRole("link", { name: "Contact us", exact: true }).first().click();
  await expect(page).toHaveURL(/\/contact\/?$/);
  // One address, the words of its own mailto link (ADR-0058 amendment 6; the audit's decision D2 had three), and no
  // repository link (D3). The row of links that stood under the addresses is gone.
  // The page is white under the header's bar; its heading is one short line, not a statement, and in a laptop's window the
  // whole form is in view as the page opens (ADR-0058 amendment 7).
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Get in touch");
  await expect(page.locator("main")).not.toContainText(/Tell us about/i);
  await expect(page.locator("main")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await page.setViewportSize({ width: 1440, height: 789 });
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  expect(await page.evaluate(() => Math.round(document.querySelector(".contact-card")!.getBoundingClientRect().bottom))).toBeLessThanOrEqual(789);
  await page.setViewportSize({ width: 1280, height: 720 });
  expect(await page.evaluate(() => Math.round(document.querySelector(".contact-submit")!.getBoundingClientRect().bottom))).toBeLessThanOrEqual(720);
  await expect(page.getByRole("link", { name: "chvalerio@ucsd.edu" })).toHaveAttribute("href", "mailto:chvalerio@ucsd.edu");
  await expect(page.locator("main a[href^='mailto:']")).toHaveCount(1);
  await expect(page.locator("main")).not.toContainText(/e1villa|saucedo|outlook\.com|Before you write|Workspace access/i);
  await expect(page.locator("main")).toContainText("Christopher Valerio, co-founder and CEO");
  // Beside it, the upper half of a turning globe that is a drawing only: hidden from assistive technology, taking no pointer.
  const globe = page.locator(".contact-globe");
  await expect(globe).toHaveAttribute("aria-hidden", "true");
  await expect(globe).toHaveCSS("pointer-events", "none");
  expect(await globe.locator("canvas").evaluate((canvas: HTMLCanvasElement) => canvas.width)).toBeGreaterThan(200);
  expect(await page.locator(".contact-globe-window").evaluate((holder) => holder.getBoundingClientRect().height / holder.querySelector(".contact-globe")!.getBoundingClientRect().height)).toBeLessThan(0.65);
  // The form sends nothing and says so; it will not write an email with a field missing.
  const form = page.locator(".contact-form");
  await expect(form.locator(".contact-form-note")).toHaveText("Nothing is sent from this page. Your email app opens with the message written, and you send it from there.");
  await form.getByRole("button", { name: "Open in your email app" }).click();
  await expect(form.getByRole("link", { name: "open the email here" })).toHaveCount(0);
  expect(await form.getByLabel("Full name").evaluate((field: HTMLInputElement) => field.validity.valueMissing)).toBe(true);
  // Filled in, a press writes the email to that one address from what was typed, and gives it as a link as well.
  await form.getByLabel("Full name").fill("Ada Example");
  await form.getByLabel("Company").fill("Example Works");
  await form.getByLabel("Email address").fill("ada@example.com");
  await form.getByLabel("Message", { exact: true }).fill("IM7 / 8552 under D3039.\nWhat do you need from me?");
  await form.getByRole("button", { name: "Open in your email app" }).click();
  const written = form.getByRole("link", { name: "open the email here" });
  await expect(written).toHaveAttribute("href", /^mailto:chvalerio@ucsd\.edu\?subject=Inquiry%20from%20Ada%20Example%2C%20Example%20Works&body=/);
  const body = decodeURIComponent((await written.getAttribute("href"))!.split("&body=")[1]);
  expect(body).toBe("IM7 / 8552 under D3039.\r\nWhat do you need from me?\r\n\r\nAda Example\r\nExample Works\r\nada@example.com");
  await expect(page).toHaveURL(/\/contact\/?$/);
  await expect(page.locator("main")).not.toContainText(/gmail|for now|will follow/i);
  await expect(page.locator("main a[href*='github.com']")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Calculator", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Studio", exact: true })).toHaveCount(0);
  await expect(page.locator(".site-header .wordmark")).toHaveText("Anisotropy");
});

test("the inner pages are white under the header's black bar, and their footer is black (ADR-0077 amendment 69)", async ({ page }) => {
  for (const address of ["/about", "/industries", "/services", "/services/finite-element-modeling", "/contact", "/no-such-page"]) {
    await page.goto(address);
    await expect(page.locator(".site-header"), address).toHaveCSS("background-color", "rgb(0, 0, 0)");
    await expect(page.locator(".site-footer"), address).toHaveCSS("background-color", "rgb(0, 0, 0)");
    await expect(page.locator("main"), address).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await expect(page.locator("main h1"), address).toHaveCSS("color", "rgb(17, 17, 17)");
    // The opening and every band: white, or the team band's light grey. No band is dark.
    const grounds = await page.locator("main").evaluate((main) => [...main.querySelectorAll(".page-opening, .band")].map((part) => getComputedStyle(part).backgroundColor));
    expect(grounds.length, address).toBeGreaterThan(0);
    for (const ground of grounds) expect(["rgb(255, 255, 255)", "rgb(243, 243, 244)"], address).toContain(ground);
  }
});

test("the mobile menu lists the five services under Services", async ({ page }) => {
  test.skip(!SERVICES_PANEL_IN_HEADER, "the Services panel is hidden from the header for now (ADR-0058 amendment 4)");
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
      "/services/computer-aided-design",
      "/services/finite-element-modeling",
      "/services/test-plans",
      "/services/documentation",
      "/services/manufacturing-plans",
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
      // No empty picture slot reaches a visitor (components/media-slot.tsx draws nothing without a file).
      await expect(page.locator(".media-slot-placeholder")).toHaveCount(0);
      await expect(page.locator("main")).not.toContainText(/IMAGE SLOT|CLIP SLOT/);
      await page.screenshot({
        path: `.preview/${path.slice(1)}-${width}.png`,
        fullPage: true,
      });
    }
  }
  expect(errors).toEqual([]);
});
