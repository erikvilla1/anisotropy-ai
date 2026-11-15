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

test("the hero's words are one statement, with nothing over it (ADR-0077 amendments 19, 21, 27, 47 and 74)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText(STATEMENT);
  // Written as a sentence, not in capitals (amendment 51).
  await expect(hero.getByRole("heading", { level: 1 })).toHaveCSS("text-transform", "none");
  // Nothing stands over it since amendment 74: the line of the mark, the name, a hairline and the year is gone, and the
  // name is said once at the top of the page, by the header's logo.
  await expect(hero.locator(".home-hero-row, .home-hero-mark, .home-hero-tagline, .home-hero-note, .home-hero-rule")).toHaveCount(0);
  await expect(hero).not.toContainText(/Est\.? 2026/i);
  expect(await hero.locator(".home-hero-stack > *").count()).toBe(1);
  await expect(page.locator(".site-header .wordmark")).toHaveText("Anisotropy");
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
  // The header lies over the hero's clip on the home page; elsewhere it is the same header in the page's flow, 84 px
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

test("the hero's clip fills the first screen from edge to edge with the header over it, and the words stand in its lower left on the page's margin (ADR-0077 amendments 47 and 66)", async ({ page }) => {
  await page.goto("/");
  const rect = (selector: string) => page.locator(selector).first().evaluate((el) => {
    const box = el.getBoundingClientRect();
    return { left: Math.round(box.left), top: Math.round(box.top), right: Math.round(box.right), bottom: Math.round(box.bottom) };
  });
  const viewport = page.viewportSize()!;
  const clip = await rect("#overview .home-hero-media");
  const header = await rect(".site-header");
  // The clip reaches the window's four edges: no black stands round it (amendment 66; until then it played in a box
  // under the header, on the page's margin).
  expect([clip.left, clip.top, viewport.width - clip.right, viewport.height - clip.bottom]).toEqual([0, 0, 0, 0]);
  // The header lies over the clip's top, with no ground of its own, and the clip is shaded there for its links: a shade
  // deepest at the window's edge and gone a quarter of the way down, over the even one.
  expect([header.top, header.bottom]).toEqual([0, 84]);
  await expect(page.locator(".site-header")).toHaveCSS("position", "absolute");
  await expect(page.locator(".site-header")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  const shade = await page.locator("#overview .home-hero-media").evaluate((el) => getComputedStyle(el, "::after").backgroundImage);
  expect(shade).toMatch(/^linear-gradient\((to bottom, )?rgba\(0, 0, 0, 0\.[5-9]\d*\) 0%, rgba\(0, 0, 0, 0\) 26%\)(, none)?$/);
  // The words stand inside the clip, clear of the header and of the window's edges.
  for (const selector of ["#overview h1", "#overview .home-hero-backed"]) {
    const part = await rect(selector);
    expect(part.left, selector).toBeGreaterThanOrEqual(clip.left + 16);
    expect(part.right, selector).toBeLessThanOrEqual(clip.right - 16);
    expect(part.top, selector).toBeGreaterThanOrEqual(header.bottom + 16);
    expect(part.bottom, selector).toBeLessThanOrEqual(clip.bottom - 16);
  }
  // They stand in the lower left, set from the left (amendment 47): the statement and the cohort's line
  // start on one edge, the page's margin, where the header's logo starts, and lie in the lower half, over the cohort's line,
  // which stands the same margin up from the window's foot.
  const [statement, backed] = [await rect("#overview h1"), await rect("#overview .home-hero-backed")];
  expect(statement.left).toBe(32);
  expect(statement.left).toBe((await rect(".site-header .wordmark")).left);
  expect(backed.left).toBe(statement.left);
  await expect(page.locator("#overview .home-hero-backed")).toHaveCSS("bottom", "32px");
  expect(statement.top).toBeGreaterThan((clip.top + clip.bottom) / 2 - 40);
  expect(statement.bottom).toBeLessThan(backed.top);
  expect(statement.right).toBeLessThan(viewport.width * 0.75);
  await expect(page.locator("#overview h1")).toHaveCSS("text-align", "left");
  // "Scroll to explore" (not shown yet; its place is read) stands in the middle of the foot from 1200 px (amendment 70),
  // and narrower in the bottom right corner on the page's margin, clear of the cohort's line.
  const explore = () => page.evaluate(() => {
    const [link, cohort] = [document.querySelector("#overview .home-hero-explore")!.getBoundingClientRect(), document.querySelector("#overview .home-hero-backed")!.getBoundingClientRect()];
    return { offMiddle: Math.round(Math.abs((link.left + link.right) / 2 - window.innerWidth / 2)), fromRight: Math.round(window.innerWidth - link.right), clear: Math.round(link.left - cohort.right) };
  });
  expect(await explore()).toMatchObject({ offMiddle: 0 });
  expect((await explore()).clear).toBeGreaterThanOrEqual(24);
  await page.setViewportSize({ width: 1199, height: 720 });
  expect(await explore()).toMatchObject({ fromRight: 32 });
  expect((await explore()).clear).toBeGreaterThanOrEqual(24);
  // On a phone the picture is edge to edge too, and the words follow the narrower margin.
  await page.setViewportSize({ width: 390, height: 844 });
  const phone = await rect("#overview .home-hero-media");
  expect([phone.left, phone.top, 390 - phone.right]).toEqual([0, 0, 0]);
  expect((await rect("#overview h1")).left).toBe(20);
  expect((await rect("#overview h1")).left).toBe((await rect(".site-header .wordmark")).left);
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
  // The team band is not on this page: since amendment 73 it is on About alone (tests/browser/team.spec.ts).
  await expect(page.locator("#working, #team, .team-band, .team-face")).toHaveCount(0);
  // Where it stood, between Services and the changelog, is the library's band (amendment 77): light grey from edge to
  // edge, its head across the page, the label and the heading at the left and the words with the way to the library from
  // the halfway line, and under it how much the library holds, three figures counted from the library's own lists.
  const library = page.locator("#resources");
  expect(await page.locator("main > section").evaluateAll((sections) => sections.map((section) => section.id).filter(Boolean))).toEqual(["mission", "platform", "resources", "changelog"]); // after the opening, which holds the hero and the demo
  await expect(library).toHaveCSS("background-color", "rgb(243, 243, 244)");
  await expect(library.locator(".band-label")).toHaveText("Resources");
  await expect(library.getByRole("heading", { level: 2 })).toHaveText("Every value, with its source.");
  await expect(library.getByRole("link")).toHaveCount(1);
  await expect(library.getByRole("link", { name: "Open the library" })).toHaveAttribute("href", /\/library\/?$/);
  await expect(library.locator("dt")).toHaveText(["Materials", "Equations", "References"]);
  const counts = (await library.locator("dd").allTextContents()).map(Number);
  expect(counts.every((count) => Number.isInteger(count) && count > 0)).toBe(true);
  const placedLibrary = await library.evaluate((band) => {
    const box = (selector: string) => band.querySelector(selector)!.getBoundingClientRect();
    const cells = [...band.querySelectorAll(".home-library-counts > div")].map((cell) => cell.getBoundingClientRect());
    return {
      edges: [band.getBoundingClientRect().left, document.documentElement.clientWidth - band.getBoundingClientRect().right],
      title: Math.round(box(".home-library-title").left), text: Math.round(box(".home-library-text").left - window.innerWidth / 2),
      first: Math.round(cells[0].left), last: Math.round(document.documentElement.clientWidth - cells[cells.length - 1].right), row: new Set(cells.map((cell) => Math.round(cell.top))).size,
      under: cells[0].top > box(".home-library-head").bottom,
    };
  });
  expect(placedLibrary).toMatchObject({ edges: [0, 0], title: 32, first: 32, last: 32, row: 1, under: true });
  expect(Math.abs(placedLibrary.text)).toBeLessThanOrEqual(20);
  // The figures are the library's own: its page says the same number of materials.
  const libraryPage = await page.context().newPage();
  await libraryPage.goto("/library");
  await expect(libraryPage.getByText(`${counts[0]} materials`, { exact: true })).toBeVisible();
  await libraryPage.close();
  // The changelog is a white band (amendment 59; light grey under amendments 36 and 46) with nothing published yet: its
  // head alone, saying so, and no list. It is not a news feed: no card, no "What is new".
  const changelog = page.locator("#changelog");
  await expect(changelog).toHaveCSS("background-color", "rgb(255, 255, 255)");
  // Its words stand in white on a card that is the pictures' lens at the card's size (amendment 77; until then the demo's
  // colours blurred into one another over a dark blue, under a wider grid): the material photograph, a little lighter, and
  // over it the same photograph drawn through the lens's own filter and laid on as colour alone, both pictures only.
  const card = changelog.locator(".home-feed-card");
  await expect(changelog.getByRole("heading", { level: 2 })).toHaveCSS("color", "rgb(255, 255, 255)");
  const inset = await card.evaluate((element) => { const box = element.getBoundingClientRect(); return [box.left, document.documentElement.clientWidth - box.right]; });
  expect(inset).toEqual([32, 32]);
  const [cardViews, lensViews] = await page.evaluate(() => {
    const read = (selector: string) => [...document.querySelectorAll(selector)].map((view) => {
      const style = getComputedStyle(view);
      return { photo: /carbon-weave\.jpg/.test(style.backgroundImage), filter: style.filter, blend: style.mixBlendMode };
    });
    return [read("#changelog .home-feed-view"), read("#mission .home-split-lens-view")];
  });
  expect(cardViews).toEqual([
    { photo: true, filter: "grayscale(1) brightness(1.45) contrast(0.85)", blend: "normal" },
    { photo: true, filter: 'url("#home-fea")', blend: "color" },
  ]);
  expect(cardViews).toEqual(lensViews); // the card's two views are drawn exactly as the lens's two
  await expect(page.locator("#home-fea")).toHaveCount(1);
  const views = await card.evaluate((element) => [...element.querySelectorAll(".home-feed-view")].map((view) => {
    const [box, outer, style] = [view.getBoundingClientRect(), element.getBoundingClientRect(), getComputedStyle(view)];
    return { hidden: view.getAttribute("aria-hidden"), press: style.pointerEvents, whole: Math.round(box.width) === Math.round(outer.width) && Math.round(box.height) === Math.round(outer.height) };
  }));
  expect(views).toEqual([{ hidden: "true", press: "none", whole: true }, { hidden: "true", press: "none", whole: true }]);
  // Over the picture lies the lens's fine mesh: hairlines 18 px apart both ways, the same as the lens draws, over the whole
  // card, taking no press. And one thing the lens has not: a shade under the words, so white reads on every colour.
  const layers = await page.evaluate(() => {
    const card = document.querySelector("#changelog .home-feed-card")!;
    const [mesh, shade, lens] = [getComputedStyle(card, "::before"), getComputedStyle(card, "::after"), getComputedStyle(document.querySelector("#mission .home-split-lens")!, "::after")];
    return { mesh: mesh.backgroundImage, lens: lens.backgroundImage, press: [mesh.pointerEvents, shade.pointerEvents], shade: shade.backgroundImage, own: getComputedStyle(card).isolation, ground: getComputedStyle(card).backgroundColor };
  });
  expect(layers.mesh).toBe(layers.lens);
  expect(layers.mesh).toMatch(/^repeating-linear-gradient\(to right, rgba\(255, 255, 255, 0\.18\) 0px, rgba\(255, 255, 255, 0\.18\) 1px, rgba\(0, 0, 0, 0\) 1px, rgba\(0, 0, 0, 0\) 18px\), repeating-linear-gradient\((to bottom, )?rgba\(255, 255, 255, 0\.18\) 0px,/);
  expect(layers).toMatchObject({ press: ["none", "none"], own: "isolate", ground: "rgb(0, 0, 0)" });
  expect(layers.shade).toMatch(/^radial-gradient\(/);
  // The closing band under it is dark grey (amendment 54, which ended amendment 49's light grey; lighter since
  // amendments 56, 58 and 59): lighter than the black footer under it, with light words and a white button with black words. Every text on it clears
  // WCAG AA's 4.5 to 1.
  // Since amendment 67 the grey is a box on a white band, as the changelog's card over it is: the two boxes have the same
  // left and right edges, 32 px of white stands between them and at the grey one's sides and foot. Both have corners a
  // little round (amendment 75).
  const closing = page.locator(".closing-band");
  await expect(closing).toHaveClass(/\bis-dark\b/);
  await expect(closing).not.toHaveClass(/\bis-light\b/);
  await expect(closing).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(closing).toHaveCSS("border-top-width", "0px");
  const boxes = await closing.evaluate((band) => {
    const layer = getComputedStyle(band, "::before");
    const card = document.querySelector(".home-feed-card")!;
    const [outer, above] = [band.getBoundingClientRect(), card.getBoundingClientRect()];
    const px = (value: string) => Math.round(parseFloat(value));
    return {
      ground: layer.backgroundColor, own: getComputedStyle(band).isolation,
      inset: [px(layer.top), px(layer.right), px(layer.bottom), px(layer.left)],
      gap: Math.round(outer.top - above.bottom), cardEdges: [Math.round(above.left), Math.round(outer.right - above.right)],
      round: [layer.borderTopLeftRadius, getComputedStyle(card).borderTopLeftRadius],
      footer: Math.round(document.querySelector(".site-footer")!.getBoundingClientRect().top - outer.bottom),
    };
  });
  expect(boxes).toEqual({ ground: "rgb(112, 112, 117)", own: "isolate", inset: [0, 32, 32, 32], gap: 32, cardEdges: [32, 32], round: ["12px", "12px"], footer: 0 });
  await expect(page.locator(".site-footer")).toHaveCSS("background-color", "rgb(0, 0, 0)");
  // The band is set in the site's own way (amendment 75; until then on twelve columns, the statement at the left, the
  // action from the halfway line and a ruled row of links under them): a small label, the statement and the actions, one
  // under another in the middle of the box, and no rule and no row's label. The button is the band's one link: the link to
  // the materials library that stood beside it is gone (amendment 76).
  await expect(closing.locator(".closing-band-label")).toHaveText("THE NEXT LAYER STARTS WITH A QUESTION.");
  await expect(closing.getByRole("heading", { level: 2 })).toHaveText("Let’s define whatcomes next.");
  await expect(closing.getByRole("link")).toHaveText(["Contact us"]);
  await expect(closing.getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "/contact");
  await expect(closing).not.toContainText(/materials library/i);
  await expect(closing.locator(".band-label, .band-grid, .closing-band-links")).toHaveCount(0);
  await expect(closing).not.toContainText(/explore the research/i);
  const set = await closing.evaluate((band) => {
    const middle = (selector: string) => { const box = band.querySelector(selector)!.getBoundingClientRect(); return Math.round((box.left + box.right) / 2 - window.innerWidth / 2); };
    const top = (selector: string) => band.querySelector(selector)!.getBoundingClientRect().top;
    return {
      off: [middle(".closing-band-label"), middle(".closing-band-statement"), middle(".closing-band-action")],
      inOrder: top(".closing-band-label") < top(".closing-band-statement") && top(".closing-band-statement") < top(".closing-band-actions"),
      weight: getComputedStyle(band.querySelector(".closing-band-statement")!).fontWeight, align: getComputedStyle(band).textAlign,
    };
  });
  for (const off of set.off) expect(Math.abs(off)).toBeLessThanOrEqual(2);
  expect(set).toMatchObject({ inOrder: true, weight: "500", align: "center" });
  // Across the box's foot lie the plies: seven hairlines, a picture only, inside the box and under its words.
  const plies = await closing.locator(".closing-band-plies").evaluate((element) => {
    const [box, outer, style] = [element.getBoundingClientRect(), element.parentElement!.getBoundingClientRect(), getComputedStyle(element)];
    return {
      hidden: element.getAttribute("aria-hidden"), press: style.pointerEvents, under: style.zIndex, lines: style.backgroundImage.split("linear-gradient").length - 1,
      inset: [Math.round(box.left - outer.left), Math.round(outer.right - box.right), Math.round(outer.bottom - box.bottom)], tall: Math.round(box.height),
      clearOfWords: box.top > element.parentElement!.querySelector(".closing-band-actions")!.getBoundingClientRect().bottom,
    };
  });
  expect(plies).toEqual({ hidden: "true", press: "none", under: "-1", lines: 7, inset: [32, 32, 32], tall: 84, clearOfWords: true });
  const tones = await closing.evaluate((band) => {
    const of = (selector: string, property: "color" | "backgroundColor") => getComputedStyle(band.querySelector(selector)!)[property];
    return {
      ground: getComputedStyle(band, "::before").backgroundColor,
      label: of(".closing-band-label", "color"), statement: of(".closing-band-statement", "color"),
      button: of(".closing-band-action", "backgroundColor"), buttonWords: of(".closing-band-action", "color"),
    };
  });
  expect(tones).toMatchObject({ label: "rgb(255, 255, 255)", statement: "rgb(255, 255, 255)", button: "rgb(255, 255, 255)", buttonWords: "rgb(0, 0, 0)" });
  const light = (colour: string) => {
    const [red, green, blue] = colour.match(/[\d.]+/g)!.slice(0, 3).map((value) => { const share = Number(value) / 255; return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  const contrast = (a: string, b: string) => { const [high, low] = [light(a), light(b)].sort((x, y) => y - x); return (high + 0.05) / (low + 0.05); };
  for (const [name, words, ground] of [["label", tones.label, tones.ground], ["statement", tones.statement, tones.ground], ["button", tones.buttonWords, tones.button]] as const)
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
    // The picture stands on the page's margin, its outer edge the changelog card's, and takes half the page's columns;
    // the words start on the other margin, or on the halfway line beside a picture at the left (amendment 77; until
    // then both stood in a narrower block in the page's middle).
    const wide = page.viewportSize()!.width;
    const half = (wide - 64 - 32) / 2;
    expect(Math.abs(places.width - half), id).toBeLessThanOrEqual(1);
    if (wordsFirst) expect([Math.round(places.words[0]), Math.round(wide - places.picture[1])], id).toEqual([32, 32]);
    else expect([Math.round(places.picture[0]), Math.round(places.words[0] - places.picture[1])], id).toEqual([32, 32]);
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
