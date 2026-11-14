import { test, expect, type Page } from "@playwright/test";
import { SERVICES_PANEL_IN_HEADER } from "../../lib/site-nav";

// The site's shell after the audit of 2026-11-12 (ADR-0077 amendment 16, ADR-0058 amendment 2): the 404 page, the titles, the folded
// menu's keyboard order, Back to top and the workspace header's way back to the projects. Runs against the built site.
//
// And the header on scroll: it leaves as the page goes down and comes back as a black bar at the window's top as soon as the
// page goes up (components/header-scroll.ts, components/site-shell.tsx). `data-scroll` on the header says where it is: absent
// at the page's top, "away" or "hidden" while it is out of sight above the window, "shown" while it is the bar.

const header = (page: Page) => page.locator(".site-header");
/** Where the header is in the window, how it is drawn and what state it is in. */
const bar = (page: Page) =>
  header(page).evaluate((element) => {
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return { top: Math.round(box.top), bottom: Math.round(box.bottom), position: style.position, ground: style.backgroundColor, state: (element as HTMLElement).dataset.scroll ?? "top" };
  });
const pageY = (page: Page) => page.evaluate(() => Math.round(window.scrollY));
/** The bar has slid into the window, or out of it. */
const barIn = (page: Page) => expect.poll(async () => (await bar(page)).top).toBe(0);
const barOut = (page: Page) => expect.poll(async () => (await bar(page)).bottom).toBeLessThanOrEqual(0);
/** Across the window's top, at the bar's middle line, what is drawn is the header and not the page under it. */
const barOnTop = (page: Page) => page.evaluate(() => [0.05, 0.5, 0.95].every((share) => Boolean(document.elementFromPoint(window.innerWidth * share, 40)?.closest(".site-header"))));
/** Where the page's content and its foot start, and how tall the page is: none of it may change when the header leaves the page's flow. */
const places = (page: Page) =>
  page.evaluate(() => [
    Math.round(document.querySelector("main")!.getBoundingClientRect().top + window.scrollY),
    Math.round(document.querySelector(".site-footer")!.getBoundingClientRect().top + window.scrollY),
    document.documentElement.scrollHeight,
  ]);
/** The page has stopped scrolling. */
const atRest = (page: Page) =>
  expect.poll(async () => {
    const before = await pageY(page);
    await page.waitForTimeout(150);
    return (await pageY(page)) === before;
  }).toBe(true);
const dropFocus = (page: Page) => page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

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

test("an unknown address under an old one keeps the 404 page's own header and footer", async ({ page }) => {
  const hydration: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && /hydrat/i.test(m.text())) hydration.push(m.text()); });
  await page.goto("/studio/x");
  await expect(page.locator("main#main h1")).toHaveText("Page not found");
  await expect(page.locator(".site-header:not(.chat-site-header)")).toBeVisible();
  await expect(page.locator(".site-footer")).toBeVisible();
  expect(hydration).toEqual([]);
});

test("every page's title is its name and the site's, and the home's is the tagline", async ({ page }) => {
  for (const [path, title] of [
    ["/", "Anisotropy | Composites. Calculated."],
    ["/about", "About | Anisotropy"],
    ["/services/test-plans", "Test plans | Anisotropy"],
    ["/workspace", "Workspace | Anisotropy"],
    ["/workspace/cad", "CAD | Anisotropy"],
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
    test.skip(!SERVICES_PANEL_IN_HEADER, "the Services panel is hidden from the header for now (ADR-0058 amendment 4)");
    await page.goto("/services/test-plans");
    await page.getByRole("button", { name: "Open menu" }).click();
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    const row = nav.getByRole("link", { name: "Test plans", exact: true });
    await expect(row).toHaveAttribute("aria-current", "page");
    expect(await row.evaluate((a) => getComputedStyle(a).textDecorationLine)).toContain("underline");
    await expect(nav.getByRole("link", { name: "Services", exact: true })).toHaveAttribute("aria-current", "true");
  });

  test("the CAD page's header links back to the projects", async ({ page }) => {
    await page.goto("/workspace/cad");
    await expect(page.locator(".site-header").getByRole("link", { name: "All projects" })).toHaveAttribute("href", "/workspace");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test("the bar stays while its menu is open, with the menu hanging from it; closed, it goes on the way down", async ({ page }) => {
    await page.goto("/about");
    await page.mouse.move(195, 700);
    await page.mouse.wheel(0, 1500);
    await expect(header(page)).toHaveAttribute("data-scroll", "away");
    await page.mouse.wheel(0, -150);
    await barIn(page);
    await page.getByRole("button", { name: "Open menu" }).click();
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav).toBeVisible();
    // Scrolling down with the menu open takes neither away.
    await page.mouse.wheel(0, 400);
    await expect.poll(() => pageY(page)).toBe(1750);
    await page.waitForTimeout(400);
    expect(await bar(page)).toMatchObject({ top: 0, position: "fixed", state: "shown" });
    await expect(nav).toBeVisible();
    const hang = await nav.evaluate((element) => Math.round(element.getBoundingClientRect().top));
    expect(Math.abs(hang - (await bar(page)).bottom)).toBeLessThanOrEqual(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // Closed by Escape, the keyboard's focus is on the menu's button: the bar stays for it.
    await page.keyboard.press("Escape");
    await expect(nav).toBeHidden();
    await page.mouse.wheel(0, 200);
    await expect.poll(() => pageY(page)).toBe(1950);
    await page.waitForTimeout(400);
    expect((await bar(page)).state).toBe("shown");
    // The focus gone, the next scroll down sends it away.
    await dropFocus(page);
    await page.mouse.wheel(0, 200);
    await barOut(page);
    await expect(header(page)).toHaveAttribute("data-scroll", "hidden");
  });

  test("a menu opened at the page's top scrolls away with the page, as before", async ({ page }) => {
    await page.goto("/about");
    await page.getByRole("button", { name: "Open menu" }).click();
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav).toBeVisible();
    await page.mouse.move(195, 700);
    await page.mouse.wheel(0, 500);
    await expect.poll(() => pageY(page)).toBe(500);
    expect(await bar(page)).toMatchObject({ top: -500, position: "relative", state: "top" });
  });
});

test("Services is a plain link in the header for now, wide or folded, with no panel; the footer still lists its five pages (ADR-0058 amendment 4)", async ({ page }) => {
  test.skip(SERVICES_PANEL_IN_HEADER, "the Services panel is back in the header");
  const five = ["Computer-aided design", "Finite element modeling", "Test plans", "Documentation", "Manufacturing plans"];
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  const services = nav.getByRole("link", { name: "Services", exact: true });
  // the header's own links, in order, standing in the middle of the page
  const row = await nav.evaluate((el) => {
    const links = [...el.querySelectorAll(":scope > a")].filter((a) => !a.classList.contains("mobile-chat-cta") && a.getBoundingClientRect().width > 0);
    const boxes = links.map((a) => a.getBoundingClientRect());
    return { names: links.map((a) => a.textContent?.trim()), off: (boxes[0].left + boxes[boxes.length - 1].right) / 2 - window.innerWidth / 2 };
  });
  expect(row.names).toEqual(["About", "Industries", "Resources", "Services", "Contact us"]);
  expect(Math.abs(row.off)).toBeLessThanOrEqual(2);
  // no plus, no button, no panel
  await expect(page.getByRole("button", { name: "Show services" })).toHaveCount(0);
  await expect(page.locator(".services-menu, .services-menu-plus, .services-panel")).toHaveCount(0);
  for (const name of five) await expect(nav.getByRole("link", { name, exact: true })).toHaveCount(0);
  // the link goes to the Services page, and marks the section on a service's own page
  await services.click();
  await expect(page).toHaveURL(/\/services\/?$/);
  await expect(services).toHaveAttribute("aria-current", "page");
  const footer = page.getByRole("navigation", { name: "Footer" });
  for (const name of five) await expect(footer.getByRole("link", { name, exact: true })).toBeVisible();
  await footer.getByRole("link", { name: "Test plans", exact: true }).focus(); // on the home page focus opens what follows the demo
  await footer.getByRole("link", { name: "Test plans", exact: true }).click();
  await expect(page).toHaveURL(/\/services\/test-plans\/?$/);
  await expect(services).toHaveAttribute("aria-current", "true");
  // the folded menu: the one link, without the five under it
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(services).toBeVisible();
  for (const name of five) await expect(nav.getByRole("link", { name, exact: true })).toHaveCount(0);
});

test("Back to top takes the focus to the top with the page", async ({ page }) => {
  await page.goto("/about");
  await page.getByRole("link", { name: "Back to top" }).click();
  await expect(page.locator(".site-header .wordmark")).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  expect(new URL(page.url()).hash).toBe("");
  // The logo that took the focus is the header's at the page's top, in the page's flow, not the bar.
  await expect(header(page)).not.toHaveAttribute("data-scroll", /.+/);
  await expect(header(page)).toHaveCSS("position", "relative");
});

test("on an inner page the header leaves as the page scrolls down and comes back as a black bar on the way up, wherever the page is", async ({ page }) => {
  await page.goto("/about");
  // At the page's top it is what it was: in the page's flow, on the page's own ground.
  const atTop = await bar(page);
  expect(atTop).toEqual({ top: 0, bottom: 84, position: "relative", ground: "rgba(0, 0, 0, 0)", state: "top" });
  const before = await places(page);
  await page.mouse.move(720, 500);
  // Down: it scrolls away with the page as it always did, and is then kept above the window.
  await page.mouse.wheel(0, 1200);
  await expect.poll(() => pageY(page)).toBe(1200);
  await expect(header(page)).toHaveAttribute("data-scroll", "away");
  expect((await bar(page)).bottom).toBeLessThanOrEqual(0);
  // A few pixels back up are not a scroll up.
  await page.mouse.wheel(0, -3);
  await expect.poll(() => pageY(page)).toBe(1197);
  await expect(header(page)).toHaveAttribute("data-scroll", "away");
  // Up: the bar slides in at the window's top, black, over the page, with the page nowhere near its top.
  await page.mouse.wheel(0, -100);
  await expect(header(page)).toHaveAttribute("data-scroll", "shown");
  await expect(header(page)).toHaveCSS("transition-property", "transform");
  await expect(header(page)).toHaveCSS("transition-duration", "0.24s");
  await barIn(page);
  expect(await bar(page)).toEqual({ top: 0, bottom: 84, position: "fixed", ground: "rgb(0, 0, 0)", state: "shown" });
  expect(await pageY(page)).toBe(1097);
  expect(await barOnTop(page)).toBe(true);
  // Nothing in the page has moved for it.
  expect(await places(page)).toEqual(before);
  // A few pixels down do not send it away; a scroll down does, and it slides out.
  await page.mouse.wheel(0, 3);
  await expect.poll(() => pageY(page)).toBe(1100);
  await expect(header(page)).toHaveAttribute("data-scroll", "shown");
  await page.mouse.wheel(0, 100);
  await expect(header(page)).toHaveAttribute("data-scroll", "hidden");
  await barOut(page);
  expect(await places(page)).toEqual(before);
  // Back at the page's top it is the header in the page's flow again, where and as it was.
  await page.mouse.wheel(0, -5000);
  await expect.poll(() => pageY(page)).toBe(0);
  await expect(header(page)).not.toHaveAttribute("data-scroll", /.+/);
  await expect.poll(() => bar(page)).toEqual(atTop);
  expect(await places(page)).toEqual(before);
});

test("the focus brings the bar in without moving the page and keeps it there, and what takes the focus further up the page is not left under it", async ({ page }) => {
  await page.goto("/about");
  await page.mouse.move(720, 500);
  await page.mouse.wheel(0, 4000);
  await expect.poll(() => pageY(page)).toBe(4000);
  await expect(header(page)).toHaveAttribute("data-scroll", "away");
  // Tab from the page's start: the skip link, then the logo. The bar comes for it, and the page stays where it is.
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.locator(".site-header .wordmark")).toBeFocused();
  await barIn(page);
  expect(await bar(page)).toMatchObject({ position: "fixed", state: "shown" });
  expect(await pageY(page)).toBe(4000);
  // With the keyboard's focus in it the bar stays on the way down as well.
  await page.mouse.wheel(0, 400);
  await expect.poll(() => pageY(page)).toBe(4400);
  await page.waitForTimeout(400);
  expect(await bar(page)).toMatchObject({ top: 0, state: "shown" });
  // Once the focus has left, a scroll down sends it away.
  await dropFocus(page);
  await page.mouse.wheel(0, 100);
  await barOut(page);
  // A link further up the page takes the focus: the browser scrolls up to it, which brings the bar in, and the link
  // stands under the bar's foot with room for its focus ring, not behind the bar.
  const link = page.locator("main a").first();
  await link.focus();
  await barIn(page);
  await atRest(page);
  expect(await pageY(page)).toBeGreaterThan(500);
  const top = await link.evaluate((element) => element.getBoundingClientRect().top);
  expect(top).toBeGreaterThanOrEqual((await bar(page)).bottom + 7);
});

test("fixed to the window the header keeps its room in the page, at each of its heights, so nothing moves", async ({ page }) => {
  for (const [width, height, tall] of [[1440, 1000, 84], [1100, 800, 86], [800, 900, 75], [390, 844, 70]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/industries");
    expect((await bar(page)).bottom, `${width} px`).toBe(tall);
    const before = await places(page);
    await page.mouse.move(width / 2, height / 2);
    await page.mouse.wheel(0, 900);
    await expect(header(page), `${width} px`).toHaveAttribute("data-scroll", "away");
    expect(await places(page), `${width} px`).toEqual(before);
    await page.mouse.wheel(0, -100);
    await barIn(page);
    expect(await bar(page), `${width} px`).toMatchObject({ top: 0, bottom: tall, position: "fixed", state: "shown" });
    expect(await places(page), `${width} px`).toEqual(before);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${width} px`).toBe(true);
  }
});

test("what stays in view under the window's top keeps clear of the bar: the Resources page's two lists", async ({ page }) => {
  await page.goto("/library");
  await page.mouse.move(720, 500);
  for (const [tab, name] of [["Materials", ".material-list"], ["Physics & references", ".topic-list"]]) {
    await page.getByRole("tab", { name: tab }).click();
    const list = page.locator(name).first();
    await expect(list).toBeVisible();
    // Far enough down for the list to be held under the window's top, then up a little for the bar.
    const start = await list.evaluate((element) => Math.round(element.getBoundingClientRect().top + window.scrollY));
    await page.evaluate((top) => window.scrollTo({ top, behavior: "instant" }), start + 400);
    await page.mouse.wheel(0, -100);
    await barIn(page);
    await atRest(page);
    const top = await list.evaluate((element) => Math.round(element.getBoundingClientRect().top));
    expect(top, name).toBeGreaterThanOrEqual((await bar(page)).bottom);
    expect(top, name).toBeLessThan(200);
  }
});

test.describe("for a visitor who asks for reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("the bar comes and goes on scroll as for anyone, without a slide", async ({ page }) => {
    await page.goto("/about");
    await page.mouse.move(720, 500);
    await page.mouse.wheel(0, 1200);
    await expect(header(page)).toHaveAttribute("data-scroll", "away");
    await page.mouse.wheel(0, -100);
    await expect(header(page)).toHaveAttribute("data-scroll", "shown");
    await expect(header(page)).toHaveCSS("transition-property", "none");
    expect(await bar(page)).toMatchObject({ top: 0, bottom: 84, position: "fixed", ground: "rgb(0, 0, 0)" });
    await page.mouse.wheel(0, 100);
    await expect(header(page)).toHaveAttribute("data-scroll", "hidden");
    expect((await bar(page)).bottom).toBeLessThanOrEqual(0);
  });
});

test.describe("on the home page", () => {
  /** Keeps, in the page, every state the header takes from now on. */
  const watch = (page: Page) =>
    page.evaluate(() => {
      const seen: string[] = [];
      (window as unknown as { headerStates: string[] }).headerStates = seen;
      const element = document.querySelector<HTMLElement>(".site-header")!;
      new MutationObserver(() => seen.push(element.dataset.scroll ?? "top")).observe(element, { attributes: true, attributeFilter: ["data-scroll"] });
    });
  /** The states the header has taken since the last look. */
  const seen = (page: Page) => page.evaluate(() => (window as unknown as { headerStates: string[] }).headerStates.splice(0));

  test("the header lies over the hero at the top as before and leaves with it; a scroll up or the keyboard's focus brings it in as the bar, and at the top it is the hero's header again", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#overview h1")).toBeVisible();
    const atTop = await bar(page);
    expect(atTop).toEqual({ top: 0, bottom: 84, position: "absolute", ground: "rgba(0, 0, 0, 0)", state: "top" });
    await watch(page);
    await page.mouse.move(720, 500);
    // A little way down: the header has left with the page, and is kept above the window.
    await page.mouse.wheel(0, 300);
    await expect.poll(() => pageY(page)).toBe(300);
    await expect(header(page)).toHaveAttribute("data-scroll", "away");
    expect((await bar(page)).bottom).toBeLessThanOrEqual(0);
    // Up a little: the bar, black, over what the window shows, with the page still off its top.
    await page.mouse.wheel(0, -100);
    await barIn(page);
    expect(await bar(page)).toEqual({ top: 0, bottom: 84, position: "fixed", ground: "rgb(0, 0, 0)", state: "shown" });
    expect(await pageY(page)).toBe(200);
    expect(await barOnTop(page)).toBe(true);
    // Down: gone.
    await page.mouse.wheel(0, 100);
    await barOut(page);
    expect(await seen(page)).toEqual(["away", "shown", "hidden"]);
    // The keyboard: Tab to the logo brings the bar in, and the page stays where it is.
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await expect(page.locator(".site-header .wordmark")).toBeFocused();
    await barIn(page);
    expect(await pageY(page)).toBe(300);
    await dropFocus(page);
    // Back at the page's top it is the header over the hero, as it was when the page opened.
    await page.mouse.wheel(0, -1000);
    await expect.poll(() => pageY(page)).toBe(0);
    await expect(header(page)).not.toHaveAttribute("data-scroll", /.+/);
    await expect.poll(() => bar(page)).toEqual(atTop);
  });

  // The whole page below the hero, the demo and the bands after it, at the two sizes the header has most to do with: a
  // desktop window, and a narrower one where the demo is an ordinary section.
  for (const [name, width, height, tall] of [["a desktop window", 1440, 1000, 84], ["a narrower window", 1000, 800, 86]] as const) {
    test(`far down the page, on ${name}, a scroll up brings the bar in over the page and a scroll down sends it away`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.goto("/");
      await expect(page.locator("#overview h1")).toBeVisible();
      const atTop = await bar(page);
      expect(atTop).toEqual({ top: 0, bottom: tall, position: "absolute", ground: "rgba(0, 0, 0, 0)", state: "top" });
      await page.mouse.move(width / 2, height / 2);
      // To the page's foot in one move, as the scroll bar makes.
      await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
      await atRest(page);
      const foot = await pageY(page);
      expect(foot).toBeGreaterThan(3 * height);
      await expect(header(page)).toHaveAttribute("data-scroll", "away");
      // Up a little: the bar, black, over the page.
      await page.mouse.wheel(0, -100);
      await expect.poll(() => pageY(page)).toBe(foot - 100);
      await barIn(page);
      expect(await bar(page)).toEqual({ top: 0, bottom: tall, position: "fixed", ground: "rgb(0, 0, 0)", state: "shown" });
      expect(await barOnTop(page)).toBe(true);
      // Down: gone.
      await page.mouse.wheel(0, 100);
      await barOut(page);
      // Half way up the page in one move: that is a scroll up too.
      await page.evaluate((top) => window.scrollTo({ top, behavior: "instant" }), Math.round(foot / 2));
      await barIn(page);
      expect(await barOnTop(page)).toBe(true);
      await page.mouse.wheel(0, 100);
      await barOut(page);
      // At the page's top it is the header over the hero again.
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
      await expect.poll(() => pageY(page)).toBe(0);
      await expect(header(page)).not.toHaveAttribute("data-scroll", /.+/);
      await expect.poll(() => bar(page)).toEqual(atTop);
    });
  }

  test("Scroll to explore takes the page down by itself, and the header does not come in on the way", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#overview h1")).toBeVisible();
    await watch(page);
    // The button comes up once the hero's words have left (tests/browser/intro.spec.ts).
    const explore = page.locator("#overview .home-hero-explore");
    await expect(explore).toBeVisible({ timeout: 15_000 });
    await explore.click();
    await expect.poll(() => pageY(page)).toBeGreaterThan(100);
    await atRest(page);
    expect(await seen(page)).not.toContain("shown");
    expect((await bar(page)).bottom).toBeLessThanOrEqual(0);
  });
});
