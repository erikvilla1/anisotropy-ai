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
  markFrom: string; // where the hero's triangle starts its fade from, while it fades in
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
          markFrom: String((document.querySelector("#overview .home-hero-mark")?.getAnimations()[0]?.effect as KeyframeEffect | undefined)?.getKeyframes()[0]?.transform ?? ""),
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

const STATEMENT = "one engineering platform for composite theory and real test data";

async function expectHeroWhole(page: Page, blink = "type-caret-blink") {
  const hero = page.locator("#overview");
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero.locator("[data-intro-run]")).toHaveCount(0);
  await expect(hero.locator("h1")).toHaveText("one engineering platformfor composite theoryand real test data");
  await expect(hero.locator("h1")).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(hero.locator(".home-hero-tagline")).toHaveText("Anisotropy");
  await expect(hero.locator(".home-hero-note")).toHaveText("Est 2026");
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
  // The triangle comes up as it fades in: it starts its own height low (ADR-0070 amendment 9).
  expect(seen.some((frame) => frame.markFrom === "translateY(100%)")).toBe(true);
});

test("three seconds after the load-in the hero's words are taken away and the clip plays alone (ADR-0077 amendments 20 and 26)", async ({ page }) => {
  // The page itself notes when the load-in is over and when the exit's copies appear, so the hold is read without the test's pace.
  await page.addInitScript(() => {
    const marks = { settled: 0, leaving: 0 };
    (window as unknown as { __hold: typeof marks }).__hold = marks;
    const tick = () => {
      const hero = document.getElementById("overview");
      const veil = document.querySelector(".page-transition");
      if (hero && veil) {
        const copies = hero.querySelectorAll(".intro-overlay").length;
        if (!marks.settled && veil.classList.contains("is-idle") && copies === 0) marks.settled = performance.now();
        else if (marks.settled && !marks.leaving && copies > 0) marks.leaving = performance.now();
      }
      if (!marks.leaving) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(page.locator(".page-transition")).toHaveClass(/is-idle/, { timeout: 10_000 });
  await expectHeroWhole(page);
  await expect(hero.locator("h1")).toHaveCSS("opacity", "1");
  await expect(hero.locator(".home-hero-backed")).toHaveCSS("opacity", "1");
  // "Scroll to explore" is not there while the words stand.
  const explore = hero.locator(".home-hero-explore");
  await expect(explore).toBeHidden();
  // They stand for three seconds, then are untyped in about a second, while the mark turns (ADR-0070 amendments 4 to 9).
  const turn = await page.waitForFunction(
    () => {
      const move = document.querySelector("#overview .home-hero-mark")?.getAnimations()[0];
      if (!move) return null;
      // The windows of the typed lines: when the first begins to go and when the last has gone (the letters' flicker never ends).
      const lines = Array.from(document.querySelectorAll("#overview .intro-overlay .intro-win"))
        .flatMap((box) => box.getAnimations())
        .map((line) => line.effect!.getComputedTiming())
        .filter((timing) => Number.isFinite(Number(timing.endTime)));
      if (!lines.length) return null;
      const mark = move.effect!.getComputedTiming();
      // Each typed line's window that shows its text: how far it is drawn back while the line still waits its turn. A copy
      // of the window's own animation, held at its first moment, says so whenever this is read.
      const shown = Array.from(document.querySelectorAll<HTMLElement>("#overview .intro-overlay .intro-line > .intro-win:not(.is-front)"));
      const waiting = shown.map((box) => {
        const live = box.getAnimations()[0];
        const probe = box.animate((live.effect as KeyframeEffect).getKeyframes(), live.effect!.getTiming());
        probe.pause();
        probe.currentTime = 0;
        const drawnBack = new DOMMatrixReadOnly(getComputedStyle(box).transform).m41;
        probe.cancel();
        return drawnBack;
      });
      return {
        waiting,
        whole: shown.map(() => 0),
        steps: (move.effect as KeyframeEffect).getKeyframes().map((step) => String(step.transform ?? "")),
        markStart: Number(mark.delay),
        markEnd: Number(mark.endTime),
        linesStart: Math.min(...lines.map((timing) => Number(timing.delay))),
        linesEnd: Math.max(...lines.map((timing) => Number(timing.endTime))),
      };
    },
    null,
    { timeout: 12_000 },
  );
  const exit = (await turn.jsonValue())!;
  // The hold: three seconds, counted by a check every 0.2 s from the first one after the load-in is over.
  const hold = await page.evaluate(() => (window as unknown as { __hold: { settled: number; leaving: number } }).__hold);
  expect(hold.leaving - hold.settled).toBeGreaterThanOrEqual(2900);
  expect(hold.leaving - hold.settled).toBeLessThan(4200);
  expect(exit.steps).toEqual(["rotate(0deg)", "", "rotate(-90deg)"]); // a quarter turn, anticlockwise
  // The mark is the first to move and has gone before the last character does (ADR-0070 amendment 9).
  expect(exit.markStart).toBe(0);
  expect(exit.linesStart).toBeGreaterThanOrEqual(300);
  expect(exit.markEnd).toBeLessThan(exit.linesEnd);
  expect(exit.markEnd).toBeGreaterThan(exit.linesStart);
  // While the lines wait for the mark every one of them is whole: no character goes before its line's turn (amendment 10).
  expect(exit.waiting).toEqual(exit.whole);
  await expect(hero).toHaveAttribute("data-words", "gone", { timeout: 12_000 });
  for (const selector of ["h1", ".home-hero-tagline", ".home-hero-note", ".home-hero-mark", ".home-hero-backed"])
    await expect(hero.locator(selector), selector).toHaveCSS("opacity", "0");
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero.locator(".home-hero-mark")).toHaveCSS("transform", "none");
  // The statement and the Basement's mark are still in the page for a screen reader.
  await expect(hero.locator("h1")).toHaveText(/one engineering platform/);
  await expect(hero.getByAltText("UC San Diego, The Basement")).toHaveCount(1);
  // With the words gone, "Scroll to explore" comes up in the clip's bottom right corner, as far in as the Basement's mark is
  // on the left: the words, then an arrow in a square outline (ADR-0077 amendments 22 and 24) ...
  await expect(explore).toBeVisible();
  await expect(explore).toHaveText("Scroll to explore");
  await expect(explore).toHaveCSS("opacity", "1");
  const placed = await page.evaluate(() => {
    const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
    const button = box("#overview .home-hero-explore");
    const square = box("#overview .home-hero-explore-box");
    const clip = box("#overview .home-hero-media");
    const mark = box("#overview .home-hero-backed");
    const outline = getComputedStyle(document.querySelector("#overview .home-hero-explore-box")!);
    return {
      fromRight: clip.right - button.right,
      fromFoot: clip.bottom - button.bottom,
      markFromLeft: mark.left - clip.left,
      markFromFoot: clip.bottom - mark.bottom,
      square: [square.width, square.height],
      squareLast: Math.abs(square.right - button.right),
      border: outline.borderTopWidth,
      radius: outline.borderTopLeftRadius,
    };
  });
  expect(placed.fromRight).toBe(placed.markFromLeft);
  expect(placed.fromFoot).toBe(placed.markFromFoot);
  expect(placed.square).toEqual([34, 34]);
  expect(placed.squareLast).toBeLessThanOrEqual(0.5);
  expect([placed.border, placed.radius]).toEqual(["1px", "5px"]);
  // ... and a press scrolls the page to the section that follows the hero: to the window's top, or its middle if it is shorter.
  await explore.click();
  const off = () =>
    page.evaluate(() => {
      const box = document.getElementById("overview")!.nextElementSibling!.getBoundingClientRect();
      return Math.round(Math.abs(box.top - Math.max(0, (window.innerHeight - box.height) / 2)));
    });
  await expect.poll(off, { timeout: 10_000 }).toBeLessThanOrEqual(1);
});

test("a header link goes to its page at once, Back too, and only the home page's first load is veiled (ADR-0070 amendment 3)", async ({ page }) => {
  await record(page);
  await page.goto("/");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await frames(page);
  await page.locator(".site-header a[href='/about']").first().click();
  await expect(page).toHaveURL(/\/about\/?$/);
  await page.waitForTimeout(600);
  const forward = await frames(page);
  // No fade to black before the next page and none after it: every frame from the click on shows the page.
  expect(forward.some((frame) => frame.path.startsWith("/about"))).toBe(true);
  expect(forward.every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(page.locator("#overview h1")).toBeVisible();
  await page.waitForTimeout(600);
  const back = await frames(page);
  expect(back.every((frame) => frame.phase === "is-idle" && frame.opacity === 0 && frame.copies === 0)).toBe(true);
  await expectHeroWhole(page);
  // Another page loaded on its own starts without the veil, from its first frame.
  await page.goto("/about");
  await page.waitForTimeout(300);
  const direct = await frames(page);
  expect(direct.length).toBeGreaterThan(0);
  expect(direct.every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
});

test.describe("for a visitor who asks for reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("there is no veil and no typing: everything is there at once (ADR-0070 amendment 1)", async ({ page }) => {
    await record(page);
    await page.goto("/");
    await expectHeroWhole(page, "none");
    await expect(page.locator(".page-transition")).toBeHidden();
    // The words stay, so "Scroll to explore" is there from the start.
    await expect(page.locator("#overview .home-hero-explore")).toBeVisible();
    await page.waitForTimeout(1500);
    const seen = await frames(page);
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((frame) => !frame.shown && frame.copies === 0 && frame.running === 0)).toBe(true);
    await expectHeroWhole(page, "none");
  });
});
