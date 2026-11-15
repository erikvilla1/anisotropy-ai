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
  await expect(page.locator("main").locator("h1, h2").first()).toHaveText(/One engineering platform\s*for composite theory/);
  await expect(page.locator("#laminate, #tour")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Your layup, calculated." })).toHaveCount(0);
  // With the calculator gone the page asks the engine for nothing.
  await page.waitForTimeout(1200);
  expect(asked).toEqual([]);
});

/** The cases about the sections below the demo wait for the page's script to have started; what follows the demo is always
 * in the page (ADR-0095 amendment 10 ended amendment 7's gate). */
async function pastTheDemo(page: import("@playwright/test").Page) {
  await expect(page.locator("#demo")).toHaveAttribute("data-mode", /^(pinned|static)$/);
  await expect(page.locator("html")).not.toHaveAttribute("data-demo-gate", /.+/);
}

const STATEMENT = /^\s*One engineering platform\s*for composite theory\s*and real test data\s*$/;

test("the hero's words are one statement and a line of the mark, the name, a hairline and the year (ADR-0077 amendments 19, 21, 27, 28, 47 and 52)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText(STATEMENT);
  // Written as a sentence, not in capitals (amendment 51).
  await expect(hero.getByRole("heading", { level: 1 })).toHaveCSS("text-transform", "none");
  // The line over it: the triangle, the name, the year (amendment 47; until then a row under the statement with the mark
  // between the year and the name).
  await expect(hero.locator(".home-hero-note")).toHaveText("Est 2026");
  await expect(hero.locator(".home-hero-tagline")).toHaveText("Anisotropy");
  // One tidy line (amendment 52): the mark, the name, a hairline of its own and the year, in that order, with equal gaps
  // between them, the name, the hairline and the year on one centre line and the mark a hair above it; the hairline is a
  // little taller than the name's capitals and no taller than its line; the mark about one and three quarters of them.
  // Read once the load-in has ended (the black has lifted and no move is left): until then the mark is still on its way
  // up to its place.
  await expect(page.locator(".page-transition")).toHaveClass(/is-idle/, { timeout: 10_000 });
  await expect(hero.locator("[data-intro-run]")).toHaveCount(0, { timeout: 10_000 });
  const line = await hero.evaluate((el) => {
    const part = (name: string) => {
      const box = el.querySelector(`.home-hero-${name}`)!.getBoundingClientRect();
      return { left: box.left, right: box.right, middle: (box.top + box.bottom) / 2, width: box.width, height: box.height };
    };
    const name = el.querySelector<HTMLElement>(".home-hero-tagline")!;
    const year = el.querySelector<HTMLElement>(".home-hero-note")!;
    // Where each text ends as it is drawn: its box less the tracking after its last letter.
    const ends = (text: HTMLElement) => text.getBoundingClientRect().right - parseFloat(getComputedStyle(text).letterSpacing);
    return { mark: part("mark"), name: part("tagline"), rule: part("rule"), year: part("note"), nameEnds: ends(name), size: parseFloat(getComputedStyle(name).fontSize) };
  });
  expect(line.mark.left).toBeLessThan(line.name.left);
  expect(line.name.left).toBeLessThan(line.rule.left);
  expect(line.rule.left).toBeLessThan(line.year.left);
  const gaps = [line.name.left - line.mark.right, line.rule.left - line.nameEnds, line.year.left - line.rule.right];
  for (const gap of gaps) expect(Math.abs(gap - gaps[0]), `gaps ${gaps.map((value) => value.toFixed(1)).join(", ")}`).toBeLessThan(1);
  expect(Math.abs(line.rule.middle - line.name.middle)).toBeLessThan(1);
  expect(Math.abs(line.year.middle - line.name.middle)).toBeLessThan(1);
  expect(line.name.middle - line.mark.middle).toBeGreaterThanOrEqual(0);
  expect(line.name.middle - line.mark.middle).toBeLessThan(0.1 * line.size);
  expect(line.rule.width).toBe(1);
  expect(line.rule.height).toBeGreaterThan(0.72 * line.size); // the capitals of the name's face stand about 0.73 of its size
  expect(line.rule.height).toBeLessThanOrEqual(line.name.height);
  expect(line.mark.height / (0.727 * line.size)).toBeGreaterThan(1.5);
  expect(line.mark.height / (0.727 * line.size)).toBeLessThan(2);
  const over = await hero.evaluate((el) => [el.querySelector(".home-hero-row")!.getBoundingClientRect().bottom, el.querySelector("h1")!.getBoundingClientRect().top]);
  expect(over[0]).toBeLessThanOrEqual(over[1]);
  // The cohort stands beside the place that runs it, in the clip's bottom left corner; the place is named in words until
  // written permission for The Basement's mark is recorded (ADR-0081 amendment 2).
  await expect(hero.locator(".home-hero-backed")).toHaveText("The Basement, UC San Diego Fall 2026 Launchpad cohort");
  await expect(hero.locator(".home-hero-backed .home-hero-cohort")).toHaveText("Fall 2026 Launchpad cohort");
  await expect(hero.locator("img")).toHaveCount(0);
  // No 3D view, chat box or text field in the hero: the header's Workspace button is the way in. Its one link, "See how it
  // works", goes to the product demo and is hidden while the words stand (tests/browser/intro.spec.ts). Its one button, once
  // the clip has a source, pauses the clip (ADR-0077 amendment 50; shown only to the keyboard's focus, amendment 57); a build
  // without the clip has neither.
  await expect(hero.getByRole("link", { includeHidden: true })).toHaveCount(1);
  await expect(hero.getByRole("link", { includeHidden: true })).toHaveAttribute("href", "#demo");
  const clips = await hero.locator(".home-hero-video").count();
  const buttons = hero.getByRole("button", { includeHidden: true });
  expect(await buttons.count()).toBeLessThanOrEqual(clips);
  if (await buttons.count()) await expect(buttons).toHaveAccessibleName("Pause background video");
  await expect(hero.locator("canvas, [data-testid='laminate-scene']")).toHaveCount(0);
  await expect(hero.getByRole("textbox")).toHaveCount(0);
  // The header lies over the hero's black ground on the home page; elsewhere it is the same header in the page's flow, 84 px
  // tall. Its links stand at the right, ending just before the Workspace button (ADR-0077 amendments 8, 19 and 50).
  await expect(page.locator(".site-header")).toHaveCSS("position", "absolute");
  await page.goto("/about");
  await expect(page.locator(".site-header")).toHaveCSS("position", "relative");
  await expect(page.locator(".site-header")).toHaveCSS("height", "84px");
  const bar = await page.locator(".site-header").evaluate((header) => {
    const box = (selector: string) => header.querySelector(selector)!.getBoundingClientRect();
    return { navLeft: box(".main-nav").left, navRight: box(".main-nav").right, ctaLeft: box(".header-cta").left, markRight: box(".wordmark").right, middle: window.innerWidth / 2 };
  });
  expect(bar.ctaLeft - bar.navRight).toBeGreaterThanOrEqual(24);
  expect(bar.ctaLeft - bar.navRight).toBeLessThanOrEqual(48);
  expect(bar.navLeft).toBeGreaterThan(bar.middle);
  expect(bar.navLeft).toBeGreaterThan(bar.markRight);
});

test("the hero's clip plays in a square box on the black page, under the header, with the words in its lower left (ADR-0077 amendments 19 and 47)", async ({ page }) => {
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
  // The words stand in the box's lower left, set from the left (amendment 47): the statement and the line over it start on
  // one edge, the box's own padding in, and lie in the box's lower half, over the Basement's mark.
  const [statement, line, backed] = [await rect("#overview h1"), await rect("#overview .home-hero-row"), await rect("#overview .home-hero-backed")];
  expect(statement.left).toBe(clip.left + 32);
  expect(line.left).toBe(statement.left);
  expect(backed.left).toBe(statement.left);
  expect(statement.top).toBeGreaterThan((clip.top + clip.bottom) / 2 - 40);
  expect(statement.bottom).toBeLessThan(backed.top);
  expect(statement.right).toBeLessThan(viewport.width * 0.75);
  await expect(page.locator("#overview h1")).toHaveCSS("text-align", "left");
  // On a phone the box follows the narrower margin.
  await page.setViewportSize({ width: 390, height: 844 });
  const phone = await rect("#overview .home-hero-media");
  expect([phone.left, 390 - phone.right]).toEqual([20, 20]);
  expect(phone.top).toBeGreaterThanOrEqual((await rect(".site-header")).bottom);
});

test("the hero's clip can be paused from the keyboard, its button is not on the clip otherwise, and a clip the visitor paused stays paused (ADR-0077 amendments 50 and 57)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  test.skip(!(await hero.locator(".home-hero-video").count()), "no clip in this build");
  const video = hero.locator(".home-hero-video video");
  // The clip's source is for windows 768 px and wider, without reduced motion; the page loads no more than its first frame
  // and length before it plays.
  await expect(hero.locator(".home-hero-video source")).toHaveAttribute("media", "(min-width: 768px) and (prefers-reduced-motion: no-preference)");
  await expect(video).toHaveAttribute("preload", "metadata");
  // The button comes once the clip has a source (components/home/hero-video-keeper.tsx).
  const chosen = await video.evaluate((clip: HTMLVideoElement) => new Promise<boolean>((resolve) => {
    if (clip.currentSrc) return resolve(true);
    clip.addEventListener("loadstart", () => resolve(true), { once: true });
    setTimeout(() => resolve(Boolean(clip.currentSrc)), 3000);
  }));
  test.skip(!chosen, "this browser chose no source for the clip");
  // The button is in the page, with its name, for the keyboard and a screen reader; it is not on the clip for the eye or the
  // pointer (amendment 57).
  const pause = hero.getByRole("button", { name: "Pause background video" });
  await expect(pause).toHaveCount(1);
  await expect(pause).toHaveAttribute("aria-pressed", "false");
  await expect(pause).toHaveCSS("opacity", "0");
  await expect(pause).toHaveCSS("pointer-events", "none");
  // The keyboard's focus shows it, and Enter pauses the clip.
  await pause.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await expect(pause).toBeFocused();
  await expect(pause).toHaveCSS("opacity", "1");
  await expect(pause).toHaveCSS("pointer-events", "auto");
  await page.keyboard.press("Enter");
  await expect(pause).toHaveAttribute("aria-pressed", "true");
  // The keeper tries again at most once a second: after two seconds a paused clip is still paused.
  await page.waitForTimeout(2000);
  expect(await video.evaluate((clip: HTMLVideoElement) => clip.paused)).toBe(true);
  // While the clip stands paused the button stays on it, wherever the focus goes, so a press can play it again.
  await page.keyboard.press("Shift+Tab");
  await expect(pause).not.toBeFocused();
  await expect(pause).toHaveCSS("opacity", "1");
  await pause.click();
  await expect(pause).toHaveAttribute("aria-pressed", "false");
  // Playing again, with the focus elsewhere, it is off the clip once more.
  await page.mouse.move(5, 400);
  await page.locator("body").click({ position: { x: 5, y: 400 } });
  await expect(pause).toHaveCSS("opacity", "0");
  // A window narrowed after the clip has its source keeps the clip, so it keeps the button in the page.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(pause).toHaveCount(1);
  // A page opened on a phone gives the clip no source, so nothing plays and there is no button.
  await page.reload();
  await expect(video).toHaveJSProperty("currentSrc", "");
  await page.waitForTimeout(500);
  await expect(hero.getByRole("button", { includeHidden: true })).toHaveCount(0);
});

test("after the demo the page is white, and Mission and Services are two short blocks that lead on (ADR-0077 amendments 33 and 34)", async ({ page }) => {
  await page.goto("/");
  await pastTheDemo(page);
  for (const id of ["mission", "platform"]) await expect(page.locator(`#${id}`), id).toHaveCSS("background-color", "rgb(255, 255, 255)");
  // The team band is one light grey block from edge to edge: its head has no ground of its own, and the portraits stand
  // close under it on the same grey (amendment 59, which ended amendment 41's grey head over white).
  const team = await page.locator("#working").evaluate((band) => {
    const head = band.querySelector(".band-head")!;
    const frame = band.querySelector(".home-face-frame")!;
    const box = band.getBoundingClientRect();
    return {
      band: getComputedStyle(band).backgroundColor, head: getComputedStyle(head).backgroundColor, left: box.left, right: box.right, wide: document.documentElement.clientWidth,
      gap: frame.getBoundingClientRect().top - head.getBoundingClientRect().bottom, framesInside: frame.getBoundingClientRect().bottom < box.bottom,
    };
  });
  expect(team.band).toBe("rgb(243, 243, 244)");
  expect(team.head).toBe("rgba(0, 0, 0, 0)");
  expect([team.left, team.right]).toEqual([0, team.wide]);
  expect(team.framesInside).toBe(true);
  expect(team.gap).toBeGreaterThan(0);
  expect(team.gap).toBeLessThan(80); // the head and the portraits are one block
  // Names and titles on the grey keep 4.5 to 1.
  const faceTones = await page.locator("#working .home-face").first().evaluate((card) => ({ name: getComputedStyle(card.querySelector("h3")!).color, title: getComputedStyle(card.querySelector("p")!).color }));
  const lightOf = (colour: string) => {
    const [red, green, blue] = colour.match(/[\d.]+/g)!.slice(0, 3).map((value) => { const share = Number(value) / 255; return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  for (const [name, colour] of Object.entries(faceTones)) expect((lightOf("rgb(243, 243, 244)") + 0.05) / (lightOf(colour) + 0.05), name).toBeGreaterThanOrEqual(4.5);
  // The head spans the page as the portraits do (amendment 61): the band's label over its heading at the portraits' left
  // edge, and from the halfway line who the team is and the programme it is part of. Nothing of how the team is run, no
  // one's degree by name, and The Basement in words, not as a picture (ADR-0081 amendment 2).
  const teamHead = page.locator("#working .band-head");
  await expect(teamHead.locator(".band-label")).toHaveText("Team");
  await expect(teamHead.getByRole("heading", { level: 2 })).toHaveText("From university to industry.");
  await expect(teamHead.locator(".home-team-text p").first()).toHaveText(
    "Five engineers trained in structures and mechanics: two are pursuing PhDs in structural engineering, two hold a BS in structural engineering and one a BS in mechanical engineering. Between them they cover modeling and validation, fabrication and mechanical testing, and the software and AI that connect them.",
  );
  await expect(teamHead.locator(".home-team-cohort")).toHaveText("Part of the Fall 2026 Launchpad cohort at The Basement, UC San Diego");
  await expect(teamHead).not.toContainText(/seats?\b|decides|spending|repository|\bCEO\b/i);
  await expect(teamHead.locator("img")).toHaveCount(0);
  await expect(page.locator("#working .home-faces-label")).toHaveCount(0);
  await expect(page.locator("#working .home-faces")).not.toContainText(/PhD|\bBS\b/);
  const placed = await page.locator("#working").evaluate((band) => {
    const box = (selector: string) => band.querySelector(selector)!.getBoundingClientRect();
    const words = (selector: string) => {
      const range = document.createRange();
      range.selectNodeContents(band.querySelector(selector)!);
      return range.getBoundingClientRect();
    };
    return {
      label: words(".band-head .band-label"), heading: words(".band-head h2"), text: box(".home-team-text"), head: box(".band-head"),
      frameLeft: Math.round(box(".home-face-frame").left), lastRight: Math.round([...band.querySelectorAll(".home-face-frame")].pop()!.getBoundingClientRect().right), wide: document.documentElement.clientWidth,
    };
  });
  expect(Math.round(placed.label.left)).toBe(placed.frameLeft);
  expect(Math.round(placed.heading.left)).toBe(placed.frameLeft);
  expect(placed.label.bottom).toBeLessThan(placed.heading.top);
  expect(Math.abs(placed.text.left - placed.wide / 2)).toBeLessThanOrEqual(20); // from the halfway line
  expect(Math.round(placed.text.right)).toBeLessThanOrEqual(placed.lastRight + 1);
  expect(placed.text.bottom).toBeLessThanOrEqual(placed.head.bottom + 1);
  // The changelog is a white band (amendment 59; light grey under amendments 36 and 46) with nothing published yet: its
  // head alone, saying so, and no list. It is not a news feed: no card, no "What is new".
  const changelog = page.locator("#changelog");
  await expect(changelog).toHaveCSS("background-color", "rgb(255, 255, 255)");
  // Its words stand in white on a card whose ground is the demo's colours blurred into one another (amendment 49).
  const card = changelog.locator(".home-feed-card");
  expect(await card.evaluate((element) => getComputedStyle(element).backgroundImage)).toMatch(/radial-gradient.*radial-gradient.*linear-gradient/);
  await expect(changelog.getByRole("heading", { level: 2 })).toHaveCSS("color", "rgb(255, 255, 255)");
  const inset = await card.evaluate((element) => { const box = element.getBoundingClientRect(); return [box.left, document.documentElement.clientWidth - box.right]; });
  expect(inset).toEqual([32, 32]);
  // Over the colours lies a thin grid (amendment 54): a layer of its own under the card's words, two sets of hairlines
  // 36 px apart, masked so it is whole at the card's foot and gone half way up, and it takes no press.
  const grid = await card.evaluate((element) => {
    const layer = getComputedStyle(element, "::before");
    return { content: layer.content, position: layer.position, under: layer.zIndex, press: layer.pointerEvents, lines: layer.backgroundImage, apart: layer.backgroundSize, mask: layer.maskImage || layer.webkitMaskImage, own: getComputedStyle(element).isolation };
  });
  expect(grid).toMatchObject({ content: '""', position: "absolute", under: "-1", press: "none", apart: "36px 36px, 36px 36px", own: "isolate" });
  expect(grid.lines).toMatch(/^linear-gradient\(to right, rgba\(255, 255, 255, 0\.\d+\) 1px, rgba\(0, 0, 0, 0\) 1px\), linear-gradient\(to top, rgba\(255, 255, 255, 0\.\d+\) 1px, rgba\(0, 0, 0, 0\) 1px\)$/);
  expect(grid.mask).toMatch(/^linear-gradient\(to top, rgb\(0, 0, 0\) 0%, rgb\(0, 0, 0\) 6%, rgba\(0, 0, 0, 0\) 50%\)$/);
  // The closing band under it is dark grey (amendment 54, which ended amendment 49's light grey; lighter since
  // amendments 56, 58 and 59): lighter than the black footer under it, with light words, a faint light rule and a white button with black words. Every text on it clears
  // WCAG AA's 4.5 to 1.
  const closing = page.locator(".closing-band");
  await expect(closing).toHaveClass(/\bis-dark\b/);
  await expect(closing).not.toHaveClass(/\bis-light\b/);
  await expect(closing).toHaveCSS("background-color", "rgb(112, 112, 117)");
  await expect(closing).toHaveCSS("border-top-width", "0px");
  await expect(page.locator(".site-footer")).toHaveCSS("background-color", "rgb(0, 0, 0)");
  const tones = await closing.evaluate((band) => {
    const of = (selector: string, property: "color" | "backgroundColor" | "borderTopColor") => getComputedStyle(band.querySelector(selector)!)[property];
    return {
      ground: getComputedStyle(band).backgroundColor,
      label: of(".band-label", "color"), statement: of(".closing-band-statement", "color"), aside: of(".closing-band-links > span", "color"), link: of(".closing-band-links a", "color"),
      rule: of(".closing-band-links", "borderTopColor"), button: of(".closing-band-action", "backgroundColor"), buttonWords: of(".closing-band-action", "color"),
    };
  });
  expect(tones).toMatchObject({ label: "rgb(255, 255, 255)", statement: "rgb(255, 255, 255)", link: "rgb(255, 255, 255)", rule: "rgba(255, 255, 255, 0.24)", button: "rgb(255, 255, 255)", buttonWords: "rgb(0, 0, 0)" });
  const light = (colour: string) => {
    const [red, green, blue] = colour.match(/[\d.]+/g)!.slice(0, 3).map((value) => { const share = Number(value) / 255; return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  const contrast = (a: string, b: string) => { const [high, low] = [light(a), light(b)].sort((x, y) => y - x); return (high + 0.05) / (low + 0.05); };
  for (const [name, words, ground] of [["label", tones.label, tones.ground], ["statement", tones.statement, tones.ground], ["aside", tones.aside, tones.ground], ["link", tones.link, tones.ground], ["button", tones.buttonWords, tones.button]] as const)
    expect(contrast(words, ground), name).toBeGreaterThanOrEqual(4.5);
  expect(contrast(tones.ground, "rgb(0, 0, 0)")).toBeGreaterThan(1.2); // the band can be told from the footer
  // Only the home page's: the industries and the services pages keep their light closing band.
  const elsewhere = await page.context().newPage();
  for (const address of ["/industries", "/services"]) {
    await elsewhere.goto(address);
    await expect(elsewhere.locator(".closing-band"), address).toHaveClass(/\bis-light\b/);
    await expect(elsewhere.locator(".closing-band"), address).toHaveCSS("background-color", "rgb(255, 255, 255)");
  }
  await elsewhere.close();
  await expect(changelog.locator(".band-label")).toHaveText("Changelog");
  await expect(changelog.getByRole("heading", { level: 2 })).toHaveText("Every release, and what changed.");
  await expect(changelog.locator(".band-statement p")).toHaveText("No releases published yet. Each version and what changed in it will be listed here.");
  await expect(changelog.locator(".home-changelog, article")).toHaveCount(0);
  await expect(page.locator("#news")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText(/what is new|coming soon|closed beta/i);
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
    expect(places.radius, id).toBe("0px"); // square corners (amendment 48)
    // The picture is a picture, not a link (amendment 53, which ended amendment 39's): no address, no role, no place in the
    // keyboard's order, and nothing in it is a link. The keyboard and a screen reader meet the band's worded link only.
    const picture = page.locator(`#${id} .home-split-picture`);
    expect(await picture.evaluate((element) => [element.tagName, element.hasAttribute("href"), element.hasAttribute("role"), element.hasAttribute("tabindex"), element.querySelectorAll("a, button").length]), id).toEqual(["DIV", false, false, false, 0]);
    await expect(page.locator(`#${id} a.home-split-picture, #${id} .home-split-picture a`)).toHaveCount(0);
    await expect(picture).toHaveAttribute("aria-hidden", "true");
    // The pointer over it is a crosshair, the lens's own.
    await expect(picture).toHaveCSS("cursor", "crosshair");
    await picture.scrollIntoViewIfNeeded();
    const still = () => picture.evaluate((element) => { const style = getComputedStyle(element); return [style.transform, style.boxShadow, style.transitionDuration]; });
    expect(await still(), id).toEqual(["none", "none", "0s"]);
    // Away from the pointer there is no lens over it.
    const lens = picture.locator(".home-split-lens");
    await expect(lens).toHaveCSS("opacity", "0");
    const before = (await picture.boundingBox())!;
    await picture.hover();
    // Under the pointer the picture itself does not lift, grow or take a shadow: only the lens comes.
    await page.waitForTimeout(350); // longer than the lift took
    expect(await still(), id).toEqual(["none", "none", "0s"]);
    expect(await picture.boundingBox(), id).toEqual(before);
    // Under the pointer a small lens shows the photograph in the demo's colours (amendment 48): a 4:3 window with the
    // pointer in its middle, inside the picture, drawn through the page's own filter, and gone when the pointer leaves.
    await expect(picture).toHaveAttribute("data-lens", "on");
    await expect(lens).toHaveCSS("opacity", "1");
    const box = (await picture.boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.6, { steps: 4 });
    await expect.poll(async () => {
      const at = (await lens.boundingBox())!;
      return [Math.abs(at.x + at.width / 2 - (box.x + box.width * 0.3)) < 6, Math.abs(at.y + at.height / 2 - (box.y + box.height * 0.6)) < 6];
    }, { message: `${id}: the lens under the pointer` }).toEqual([true, true]);
    const window = (await lens.boundingBox())!;
    expect(Math.abs(window.width / window.height - 4 / 3), id).toBeLessThan(0.02);
    expect(window.width, id).toBeGreaterThanOrEqual(150);
    expect(await picture.locator(".home-split-lens-view.is-field").evaluate((view) => getComputedStyle(view).filter), id).toContain("#home-fea");
    // At the picture's corner it keeps inside the picture.
    await page.mouse.move(box.x + 3, box.y + 3, { steps: 4 });
    await expect.poll(async () => { const at = (await lens.boundingBox())!; return at.x >= box.x - 1 && at.y >= box.y - 1; }, { message: `${id}: the lens in the picture` }).toBe(true);
    // A press on the picture leads nowhere.
    const address = page.url();
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(250);
    expect(page.url(), id).toBe(address);
    await page.mouse.move(2, 2);
    await expect(picture).not.toHaveAttribute("data-lens", /.+/);
    await expect(lens).toHaveCSS("opacity", "0");
    // The photograph is the carbon weave for now, in black and white.
    const photo = picture.locator(".home-split-photo");
    expect(await photo.evaluate((element) => getComputedStyle(element).backgroundImage), id).toContain("/assets/images/carbon-weave.jpg");
    expect(await photo.evaluate((element) => getComputedStyle(element).filter), id).toContain("grayscale(1)");
  }
  // The changelog keeps its head in the middle, as the demo's words are; the team's stands at the left since amendment 61
  // (checked above).
  for (const id of ["changelog"]) {
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
  // Under each name, one short line (amendment 43).
  await expect(cards.locator("h3 + p")).toHaveText(["Co-Founder, CEO", "Co-Founder, AI Lead", "Fabrication & Test Lead", "Simulation & Validation Lead", "Software & Growth Engineer"]);
  expect(await cards.locator("h3 + p").evaluateAll((lines) => lines.map((line) => Math.round(line.getBoundingClientRect().height)))).toEqual([24, 24, 24, 24, 24]);
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

