import { test, expect, type Page } from "@playwright/test";

// The load-in (ADR-0070 amendments 1 and 4): the page starts under a black veil, the veil lifts once the hero's text is ready,
// and the statement and the small lines are typed in by a copy laid over the page's own text, a text cursor riding the
// statement's last line. The veil and the copies are read on every frame from the first paint, because they are gone again
// within a few seconds.

type Frame = {
  path: string;
  phase: string;
  shown: boolean; // the veil is displayed at all
  opacity: number;
  colour: string;
  copies: number; // the copies that play the moves
  riders: number; // the copies' own text cursors
  hiddenCopies: number; // of those, the ones hidden from assistive technology
  running: number; // elements whose own text is transparent while a copy plays
  ownHeadline: string; // the headline's own text nodes, without any copy
};

async function record(page: Page) {
  await page.addInitScript(() => {
    const frames: unknown[] = [];
    (window as unknown as { __intro: unknown[] }).__intro = frames;
    const tick = () => {
      const veil = document.querySelector(".page-transition");
      if (veil) {
        const style = getComputedStyle(veil);
        const headline = document.querySelector("#overview h1");
        const copies = Array.from(document.querySelectorAll(".intro-overlay"));
        frames.push({
          path: location.pathname,
          phase: veil.className.replace("page-transition ", ""),
          shown: style.display !== "none",
          opacity: Number(style.opacity),
          colour: style.backgroundColor,
          copies: copies.length,
          riders: document.querySelectorAll(".intro-overlay .intro-caret").length,
          hiddenCopies: copies.filter((copy) => copy.getAttribute("aria-hidden") === "true" && copy.hasAttribute("inert")).length,
          running: document.querySelectorAll("[data-intro-run]").length,
          ownHeadline: headline
            ? Array.from(headline.childNodes)
                .filter((node) => node.nodeType === Node.TEXT_NODE)
                .map((node) => node.nodeValue)
                .join(" ")
            : "",
        });
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

/** The frames read since the last call, after two more have been read so the latest state is among them. */
const frames = (page: Page) =>
  page.evaluate(async () => {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const store = window as unknown as { __intro: Frame[] };
    const taken = store.__intro.slice();
    store.__intro.length = 0;
    return taken;
  });

const STATEMENT = "Anisotropy one engineering platform for composite theory and real test data";

async function expectHeroWhole(page: Page, blink = "type-caret-blink") {
  const hero = page.locator("#overview");
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero.locator("[data-intro-run]")).toHaveCount(0);
  await expect(hero.locator("h1")).toHaveText("Anisotropyone engineering platformfor composite theoryand real test data");
  await expect(hero.locator("h1")).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(hero.locator(".home-hero-tagline")).toHaveText("Composites.Calculated.");
  await expect(hero.locator(".home-hero-note")).toHaveText("Fall 2026 Launchpad cohort");
  for (const line of await hero.locator(".home-hero-tagline, .home-hero-note").all()) await expect(line).toHaveCSS("color", "rgb(255, 255, 255)");
  // The text cursor: on the statement's last line, at its end, taking no room, and blinking unless the visitor asked for
  // reduced motion.
  const caret = await hero.locator("h1 > .type-caret").evaluate((own) => {
    const last = Array.from(own.parentElement!.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .pop()!;
    const range = document.createRange();
    range.selectNodeContents(last);
    const text = range.getBoundingClientRect();
    const box = own.getBoundingClientRect();
    const line = getComputedStyle(own, "::after");
    return {
      gap: Math.abs(box.left - text.right),
      onLine: box.top > text.top && box.top <= text.bottom,
      width: box.width,
      blink: line.animationName,
      colour: line.backgroundColor,
    };
  });
  expect(caret).toMatchObject({ onLine: true, width: 0, blink, colour: "rgb(255, 255, 255)" });
  expect(caret.gap).toBeLessThanOrEqual(1);
}

test("the home page loads out of black and the hero's words are typed in (ADR-0070 amendment 1)", async ({ page }) => {
  await record(page);
  await page.goto("/");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await expectHeroWhole(page);
  await expect(veil).toHaveCSS("opacity", "0");
  const seen = await frames(page);
  // The first paint is black, #010101.
  expect(seen[0]).toMatchObject({ phase: "is-enter", shown: true, opacity: 1, colour: "rgb(1, 1, 1)", copies: 0 });
  // The statement, the tagline and the small line are made ready while the black still covers the page, so the finished text is never
  // seen before its move: a copy each, hidden from assistive technology, over the page's own text, which stays in place.
  const ready = seen.findIndex((frame) => frame.copies > 0);
  expect(ready).toBeGreaterThan(0);
  // The triangle and the Basement's mark wait with them to fade in, and the statement's copy carries the one text cursor.
  expect(seen[ready]).toMatchObject({ opacity: 1, copies: 3, hiddenCopies: 3, riders: 1, running: 5, ownHeadline: STATEMENT });
  expect(seen.slice(0, ready).every((frame) => frame.opacity === 1)).toBe(true);
  // The copies go once the moves have played: the headline's 1.6 s, with room for a busy machine.
  const lifting = seen.findIndex((frame) => frame.phase === "is-lift");
  const gone = seen.findIndex((frame, index) => index > ready && frame.copies === 0);
  expect(lifting).toBeGreaterThanOrEqual(ready);
  expect(gone).toBeGreaterThan(lifting);
  expect(seen.slice(ready, gone).every((frame) => frame.ownHeadline === STATEMENT)).toBe(true);
  expect(seen[seen.length - 1]).toMatchObject({ phase: "is-idle", opacity: 0, copies: 0, running: 0 });
});

test("five seconds after the load-in the hero's words are taken away and the clip plays alone (ADR-0077 amendment 20)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(page.locator(".page-transition")).toHaveClass(/is-idle/, { timeout: 10_000 });
  await expectHeroWhole(page);
  await expect(hero.locator("h1")).toHaveCSS("opacity", "1");
  await expect(hero.locator(".home-hero-backed")).toHaveCSS("opacity", "1");
  // They stand for five seconds, then are untyped in about a second, while the mark turns once (amendment 4 of ADR-0070).
  const turn = await page.waitForFunction(
    () => {
      const move = document.querySelector("#overview .home-hero-mark")?.getAnimations()[0];
      const steps = move ? (move.effect as KeyframeEffect).getKeyframes().map((step) => String(step.transform ?? "")) : [];
      return steps.length ? steps : null;
    },
    null,
    { timeout: 12_000 },
  );
  expect(await turn.jsonValue()).toEqual(["rotate(0deg)", "", "rotate(-360deg)"]); // one turn, anticlockwise
  await expect(hero).toHaveAttribute("data-words", "gone", { timeout: 12_000 });
  for (const selector of ["h1", ".home-hero-tagline", ".home-hero-note", ".home-hero-mark", ".home-hero-backed"])
    await expect(hero.locator(selector), selector).toHaveCSS("opacity", "0");
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero.locator(".home-hero-mark")).toHaveCSS("transform", "none");
  // The statement and the Basement's mark are still in the page for a screen reader.
  await expect(hero.locator("h1")).toHaveText(/one engineering platform/);
  await expect(hero.getByAltText("UC San Diego, The Basement")).toHaveCount(1);
});

test("a header link goes to black before the next page, and Back does not (ADR-0070 amendment 1)", async ({ page }) => {
  await record(page);
  await page.goto("/");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await frames(page);
  await page.locator(".site-header a[href='/about']").first().click();
  await expect(page).toHaveURL(/\/about\/?$/);
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  const forward = await frames(page);
  // The old page is fully covered before the address changes, and the new page starts covered.
  const arrived = forward.findIndex((frame) => frame.path.startsWith("/about"));
  expect(arrived).toBeGreaterThan(0);
  expect(forward[arrived - 1]).toMatchObject({ phase: "is-leave", opacity: 1, colour: "rgb(1, 1, 1)" });
  expect(forward[arrived].opacity).toBe(1);
  expect(forward[forward.length - 1]).toMatchObject({ phase: "is-idle", opacity: 0 });
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(page.locator("#overview h1")).toBeVisible();
  await page.waitForTimeout(600);
  const back = await frames(page);
  expect(back.every((frame) => frame.phase === "is-idle" && frame.opacity === 0 && frame.copies === 0)).toBe(true);
  await expectHeroWhole(page);
});

test.describe("for a visitor who asks for reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("there is no veil and no typing: everything is there at once (ADR-0070 amendment 1)", async ({ page }) => {
    await record(page);
    await page.goto("/");
    await expectHeroWhole(page, "none");
    await expect(page.locator(".page-transition")).toBeHidden();
    await page.waitForTimeout(1500);
    const seen = await frames(page);
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((frame) => !frame.shown && frame.copies === 0 && frame.running === 0)).toBe(true);
    await expectHeroWhole(page, "none");
  });
});
