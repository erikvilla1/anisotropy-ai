import { test, expect, type Page } from "@playwright/test";

// The home page's hero. The laminate calculator and its tour left the page on 2026-11-13 (ADR-0095); the cases that read
// them, and the tour's own browser cases, went with them; they are in the history before that commit.

/** Every request the page makes to the API, so a case can say the page asks the engine for nothing. */
function apiRequests(page: Page): string[] {
  const asked: string[] = [];
  page.on("request", (request) => {
    if (/\/v1\//.test(new URL(request.url()).pathname)) asked.push(request.url());
  });
  return asked;
}

test("the hero opens the page, and the laminate calculator and its tour are not on it (ADR-0095)", async ({ page }) => {
  const asked = apiRequests(page);
  await page.goto("/");
  // The hero and the demo share a wrapper (ADR-0095 amendment 4); the hero is the first section in it.
  expect(await page.locator("main > .home-opening > *").first().getAttribute("id")).toBe("overview");
  expect(await page.locator("main > *").first().getAttribute("class")).toBe("home-opening");
  await expect(page.locator("main").locator("h1, h2").first()).toHaveText(/one engineering platform\s*for composite theory/);
  await expect(page.locator("#laminate, #tour")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Your layup, calculated." })).toHaveCount(0);
  // With the calculator gone the page asks the engine for nothing.
  await page.waitForTimeout(1200);
  expect(asked).toEqual([]);
});

/** Until the demo has played through, what follows it is out of the page's height (ADR-0095 amendment 7). Focus moving past
 * the demo opens the page, as it does for a keyboard: the cases about the sections below go there that way. */
async function pastTheDemo(page: import("@playwright/test").Page) {
  await expect(page.locator("#demo")).toHaveAttribute("data-mode", /^(pinned|static)$/); // the page's script has started
  await expect(async () => {
    await page.locator("#mission a").first().focus();
    await expect(page.locator("html")).not.toHaveAttribute("data-demo-gate", /.+/, { timeout: 500 });
  }).toPass({ timeout: 10_000 });
}

const STATEMENT = /^\s*one engineering platform\s*for composite theory\s*and real test data\s*$/;

test("the hero's words are one statement and a row of the year, the mark and the name (ADR-0077 amendments 19, 21, 27 and 28)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText(STATEMENT);
  await expect(hero.getByRole("heading", { level: 1 })).toHaveCSS("text-transform", "uppercase");
  // The row under it: the year, the triangle, the name (amendment 28).
  await expect(hero.locator(".home-hero-note")).toHaveText("Est 2026");
  await expect(hero.locator(".home-hero-tagline")).toHaveText("Anisotropy");
  const row = await hero.evaluate((el) => ["note", "mark", "tagline"].map((part) => Math.round(el.querySelector(`.home-hero-${part}`)!.getBoundingClientRect().left)));
  expect(row[0]).toBeLessThan(row[1]);
  expect(row[1]).toBeLessThan(row[2]);
  // The cohort stands beside the mark of the place that runs it, in the clip's bottom left corner.
  await expect(hero.getByAltText("UC San Diego, The Basement")).toBeVisible();
  await expect(hero.locator(".home-hero-backed .home-hero-cohort")).toHaveText("Fall 2026 Launchpad cohort");
  // No 3D view, chat box or link in the hero: the header's Workspace button is the way in. Its one button, "Scroll to explore", is hidden while the words stand (tests/browser/intro.spec.ts).
  await expect(hero.getByRole("button", { includeHidden: true })).toHaveCount(1);
  await expect(hero.locator("canvas, [data-testid='laminate-scene']")).toHaveCount(0);
  await expect(hero.getByRole("textbox")).toHaveCount(0);
  await expect(hero.getByRole("link")).toHaveCount(0);
  // The header lies over the hero's black ground on the home page; elsewhere it is the same header in the page's flow, 84 px
  // tall, with its links in the middle of the page (ADR-0077 amendments 8 and 19).
  await expect(page.locator(".site-header")).toHaveCSS("position", "absolute");
  await page.goto("/about");
  await expect(page.locator(".site-header")).toHaveCSS("position", "relative");
  await expect(page.locator(".site-header")).toHaveCSS("height", "84px");
  const nav = await page.locator(".site-header .main-nav").evaluate((el) => {
    const box = el.getBoundingClientRect();
    return Math.round(box.left + box.width / 2);
  });
  expect(Math.abs(nav - page.viewportSize()!.width / 2)).toBeLessThanOrEqual(1);
});

test("the hero's clip plays in a square box on the black page, under the header, with the words in its middle (ADR-0077 amendment 19)", async ({ page }) => {
  await page.goto("/");
  const rect = (selector: string) => page.locator(selector).first().evaluate((el) => {
    const box = el.getBoundingClientRect();
    return { left: Math.round(box.left), top: Math.round(box.top), right: Math.round(box.right), bottom: Math.round(box.bottom) };
  });
  const viewport = page.viewportSize()!;
  const clip = await rect("#overview .home-hero-media");
  const header = await rect(".site-header");
  // The box stands on the page's 32 px margin at the sides and the foot, and starts under the header.
  expect([clip.left, viewport.width - clip.right, viewport.height - clip.bottom]).toEqual([32, 32, 32]);
  expect(clip.top).toBe(header.bottom);
  expect(clip.left).toBe((await rect(".site-header .wordmark")).left);
  await expect(page.locator("#overview .home-hero-media")).toHaveCSS("border-radius", "0px");
  // The page around it is the site's black, and the words sit inside the box, the statement and the mark on its middle line.
  expect(await page.locator("#overview").evaluate((el) => getComputedStyle(el, "::before").backgroundColor)).toBe("rgb(0, 0, 0)");
  for (const selector of ["#overview h1", "#overview .home-hero-row", "#overview .home-hero-backed"]) {
    const part = await rect(selector);
    expect(part.left, selector).toBeGreaterThanOrEqual(clip.left + 16);
    expect(part.right, selector).toBeLessThanOrEqual(clip.right - 16);
    expect(part.top, selector).toBeGreaterThanOrEqual(clip.top + 16);
    expect(part.bottom, selector).toBeLessThanOrEqual(clip.bottom - 16);
  }
  for (const selector of ["#overview h1", "#overview .home-hero-mark"]) {
    const part = await rect(selector);
    expect(Math.abs((part.left + part.right) / 2 - viewport.width / 2), selector).toBeLessThanOrEqual(1);
  }
  // On a phone the box follows the narrower margin.
  await page.setViewportSize({ width: 390, height: 844 });
  const phone = await rect("#overview .home-hero-media");
  expect([phone.left, 390 - phone.right]).toEqual([20, 20]);
  expect(phone.top).toBeGreaterThanOrEqual((await rect(".site-header")).bottom);
});

test("after the demo the page is white, and Mission and Services are two short blocks that lead on (ADR-0077 amendments 33 and 34)", async ({ page }) => {
  await page.goto("/");
  await pastTheDemo(page);
  for (const id of ["mission", "platform", "working"]) await expect(page.locator(`#${id}`), id).toHaveCSS("background-color", "rgb(255, 255, 255)");
  // The team band's head stands on the feed's light grey from edge to edge, and the portraits under it on white (amendment 41).
  const team = await page.locator("#working").evaluate((band) => {
    const head = band.querySelector(".band-head")!;
    const frame = band.querySelector(".home-face-frame")!;
    const box = head.getBoundingClientRect();
    return { head: getComputedStyle(head).backgroundColor, left: box.left, right: box.right, wide: document.documentElement.clientWidth, top: box.top - band.getBoundingClientRect().top, facesBelow: frame.getBoundingClientRect().top >= box.bottom };
  });
  expect(team.head).toBe("rgb(243, 243, 244)");
  expect([team.left, team.right]).toEqual([0, team.wide]);
  expect(team.top).toBeLessThanOrEqual(1);
  expect(team.facesBelow).toBe(true);
  // What is new is a band on light grey (amendment 36) that is empty for now: its head alone, saying so, and no card
  // (amendment 41).
  await expect(page.locator("#news")).toHaveCSS("background-color", "rgb(243, 243, 244)");
  await expect(page.locator("#news").getByRole("heading", { level: 2 })).toHaveText("Lately.");
  await expect(page.locator("#news .band-statement p")).toHaveText("Nothing posted yet. News from the team will appear here.");
  await expect(page.locator("#news article")).toHaveCount(0);
  await expect(page.locator("#news .home-news")).toHaveCount(0);
  await expect(page.locator("#news")).not.toContainText(/coming soon|closed beta|CalculiX|studio/i);
  // Mission: the label, the statement and one link, to About; the strip of four principles is gone.
  const mission = page.locator("#mission");
  await expect(mission.locator(".band-label")).toHaveText("Mission");
  await expect(mission.getByRole("heading", { level: 2 })).toHaveText("One record, from the layup to the test.");
  await expect(mission.getByRole("link")).toHaveCount(1);
  await expect(mission.getByRole("link", { name: "Learn more about us" })).toHaveAttribute("href", /\/about\/?$/);
  await expect(page.locator(".home-principles")).toHaveCount(0);
  await expect(page.getByText("Physics at the core", { exact: false })).toHaveCount(0);
  // Services: the five by name, each to its page, and the way to all of them; no cards and no status marks.
  const services = page.locator("#platform");
  await expect(services.locator(".band-label")).toHaveText("Services");
  const five = services.getByRole("list", { name: "Services" }).getByRole("link");
  await expect(five).toHaveText(["Computer-aided design", "Finite element modeling", "Test plans", "Documentation", "Manufacturing plans"]);
  await expect(five.nth(1)).toHaveAttribute("href", /\/services\/finite-element-modeling\/?$/);
  await expect(services.getByRole("link", { name: "Explore the services" })).toHaveAttribute("href", /\/services\/?$/);
  await expect(services.locator(".band-card, .home-status")).toHaveCount(0);
  // Mission and Services stand side by side with a picture each (amendment 37): Mission's words at the left of its picture,
  // Services' at the right of theirs; the picture has round corners and is the carbon weave for now.
  for (const [id, wordsFirst] of [["mission", true], ["platform", false]] as const) {
    const places = await page.locator(`#${id}`).evaluate((band) => {
      const words = band.querySelector(".band-head")!.getBoundingClientRect();
      const picture = band.querySelector(".home-split-picture")!;
      const box = picture.getBoundingClientRect();
      const style = getComputedStyle(picture);
      return { words: [words.left, words.right], picture: [box.left, box.right], width: box.width, radius: style.borderTopLeftRadius, image: style.backgroundImage };
    });
    if (wordsFirst) expect(places.words[1], id).toBeLessThanOrEqual(places.picture[0]);
    else expect(places.picture[1], id).toBeLessThanOrEqual(places.words[0]);
    expect(places.width, id).toBeGreaterThan(400);
    expect(places.radius, id).toBe("20px");
    // The picture is a link to where its band's own link goes, and lifts under the pointer as a portrait does (amendment
    // 39). The keyboard and a screen reader meet the worded link only.
    const picture = page.locator(`#${id} .home-split-picture`);
    await expect(picture).toHaveAttribute("href", id === "mission" ? /\/about\/?$/ : /\/services\/?$/);
    await expect(picture).toHaveAttribute("tabindex", "-1");
    await expect(picture).toHaveAttribute("aria-hidden", "true");
    await picture.scrollIntoViewIfNeeded();
    expect(await picture.evaluate((element) => getComputedStyle(element).transform), id).toBe("none");
    await picture.hover();
    await expect.poll(() => picture.evaluate((element) => getComputedStyle(element).transform), { message: id }).toBe("matrix(1.02, 0, 0, 1.02, 0, -4)");
    await page.mouse.move(2, 2);
    expect(places.image, id).toContain("/assets/images/carbon-weave.jpg");
  }
  // Team and What is new keep their heads in the middle, as the demo's words are.
  for (const id of ["working", "news"]) {
    const off = await page.locator(`#${id} .band-statement h2`).evaluate((h) => { const r = h.getBoundingClientRect(); return (r.left + r.right) / 2 - window.innerWidth / 2; });
    expect(Math.abs(off), id).toBeLessThanOrEqual(2);
  }
  // The team's names carry no arrow, and there is no link to the About page under the cards (amendment 37).
  await expect(page.locator("#working .home-face h3 svg")).toHaveCount(0);
  await expect(page.locator("#working").getByRole("link", { name: /About page/ })).toHaveCount(0);
});

test("the hero's lens is hidden for now (ADR-0071 amendment 1)", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#overview .home-hero-lens")).toHaveCount(0);
  // The recording stays committed, ready for the lens's return.
  expect((await page.request.get("/assets/hero-lens/lens.mp4")).status()).toBe(200);
});

test("the home page fits a phone without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator("#overview h1")).toBeVisible();
  await page.locator("#mission").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("the About cards show the five portraits in the lead's order, and under the pointer the portrait lifts and LinkedIn's mark comes up as a link (ADR-0077 amendments 29 and 35)", async ({ page }) => {
  await page.goto("/");
  await pastTheDemo(page);
  const cards = page.locator("#working .home-face");
  await cards.first().scrollIntoViewIfNeeded();
  await expect(cards.locator("h3")).toHaveText(["Christopher Valerio", "Erik Villa", "Tabassum Zaman", "Jusung Park", "Kai Saucedo"]);
  // Every frame holds a portrait that has loaded, from the site's own files, and no initials.
  await expect.poll(() => cards.locator("img").evaluateAll((images) => images.map((image) => (image as HTMLImageElement).naturalWidth))).toEqual([800, 800, 800, 800, 800]);
  expect(await cards.locator("img").evaluateAll((images) => images.every((image) => new URL((image as HTMLImageElement).src).pathname.startsWith("/assets/team/")))).toBe(true);
  await expect(cards.locator(".home-face-frame > span:not(.home-face-in)")).toHaveCount(0);
  // The mark is drawn in the frame's bottom right corner only for the card under the pointer, where the portrait also lifts.
  const badge = (index: number) => cards.nth(index).locator(".home-face-in");
  await expect(badge(2)).toHaveCSS("opacity", "0");
  await cards.nth(2).hover();
  await expect(badge(2)).toHaveCSS("opacity", "1");
  await expect(badge(0)).toHaveCSS("opacity", "0");
  await expect(badge(2)).toHaveCSS("border-radius", "50%");
  // The mark is the picture the lead uploaded, drawn in black and white (amendment 39).
  expect(await badge(2).evaluate((mark) => getComputedStyle(mark).backgroundImage)).toContain("/assets/brand/round-linkedin-logo");
  expect(await badge(2).evaluate((mark) => getComputedStyle(mark).filter)).toContain("grayscale(1)");
  const corner = await cards.nth(2).evaluate((card) => {
    const frame = card.querySelector(".home-face-frame")!.getBoundingClientRect();
    const mark = card.querySelector(".home-face-in")!.getBoundingClientRect();
    return [Math.round(frame.right - mark.right), Math.round(frame.bottom - mark.bottom)];
  });
  expect(corner[0]).toBeLessThanOrEqual(14);
  expect(corner[1]).toBeLessThanOrEqual(14);
  expect(await cards.nth(2).locator(".home-face-frame").evaluate((frame) => getComputedStyle(frame).transform)).not.toBe("none");
  expect(await cards.nth(0).locator(".home-face-frame").evaluate((frame) => getComputedStyle(frame).transform)).toBe("none");
  // The badge and the name both go to that person's LinkedIn profile, in a new tab (amendment 35).
  const profiles = ["christopher-valerio-916116225", "erik-villa-4b329b261", "tabassum-zaman-51659a264", "jusung-park-a46b43226", "kaisaucedo"];
  for (let index = 0; index < profiles.length; index++) {
    const address = new RegExp(`^https://www\\.linkedin\\.com/in/${profiles[index]}/$`);
    await expect(cards.nth(index).locator("a.home-face-in")).toHaveAttribute("href", address);
    await expect(cards.nth(index).locator("a.home-face-in")).toHaveAttribute("target", "_blank");
    await expect(cards.nth(index).locator("a.home-face-in")).toHaveAttribute("rel", /noopener/);
    await expect(cards.nth(index).locator("h3 a")).toHaveAttribute("href", address);
  }
  // Black with the mark in white; white with the mark in black under the pointer itself.
  expect(await badge(2).evaluate((mark) => getComputedStyle(mark).filter)).not.toContain("invert");
  await badge(2).hover();
  await expect.poll(() => badge(2).evaluate((mark) => getComputedStyle(mark).filter)).toContain("invert(1)");
});

