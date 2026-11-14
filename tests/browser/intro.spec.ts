import { test, expect, type Page } from "@playwright/test";

// The load-in (ADR-0070 amendments 1 and 4): the page starts under a black veil, the veil lifts once the hero's text is ready,
// and the statement and the small lines are typed in by a copy laid over the page's own text, a text cursor riding the
// statement's last line. The veil and the copies are read on every frame from the first paint, because they are gone again
// within a few seconds.
//
// Every page of the site comes out of black when a visitor lands on it, by a load or by a link, and no link waits for it:
// the cases from "a link goes to its page at once" on read the same frames for the address, the page's heading and the veil.

type Frame = {
  at: number; // ms since the document started
  path: string;
  title: string; // the text of the page's main heading
  phase: string;
  shown: boolean; // the veil is displayed at all
  opacity: number;
  colour: string;
  ring: boolean; // the keyboard's focus is shown on something other than the skip link
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
    const store = window as unknown as { __intro: unknown[]; __pressed: number };
    store.__intro = frames;
    // When a press last reached the page, before anything in the page has acted on it.
    document.addEventListener("click", () => (store.__pressed = performance.now()), true);
    const tick = () => {
      const veil = document.querySelector(".page-transition");
      if (veil) {
        const style = getComputedStyle(veil);
        const headline = document.querySelector("#overview h1");
        const copies = Array.from(document.querySelectorAll(".intro-overlay"));
        const focused = document.activeElement;
        frames.push({
          at: performance.now(),
          path: location.pathname,
          title: document.querySelector("main h1")?.textContent?.trim() ?? "",
          phase: veil.className.replace("page-transition ", ""),
          shown: style.display !== "none",
          opacity: Number(style.opacity),
          colour: style.backgroundColor,
          ring: !!focused && focused !== document.body && focused.matches(":focus-visible") && !focused.classList.contains("skip-link"),
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

const STATEMENT = "One engineering platform for composite theory and real test data";

async function expectHeroWhole(page: Page, blink = "type-caret-blink") {
  const hero = page.locator("#overview");
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero.locator("[data-intro-run]")).toHaveCount(0);
  await expect(hero.locator("h1")).toHaveText("One engineering platformfor composite theoryand real test data");
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
  await expect(hero.locator("h1")).toHaveText(/One engineering platform/);
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

test("each time the clip starts again the hero's words are typed in again, stand three seconds and leave again (ADR-0077 amendment 40)", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("#overview");
  await expect(hero).toHaveAttribute("data-words", "gone", { timeout: 20_000 });
  await expect(hero.locator("h1")).toHaveCSS("opacity", "0");
  await expect(hero).not.toHaveAttribute("data-words-round", /.+/);
  // The clip reports a time earlier than its last, as it does when it loops: the test's browser may not play the clip at
  // all, so the two reports are made for it.
  const startsAgain = () =>
    page.evaluate(() => {
      const video = document.querySelector<HTMLVideoElement>("#overview .home-hero-video video")!;
      const report = (seconds: number) => {
        Object.defineProperty(video, "currentTime", { configurable: true, get: () => seconds });
        video.dispatchEvent(new Event("timeupdate"));
      };
      report(21);
      report(0.1);
      delete (video as unknown as { currentTime?: number }).currentTime; // the clip's own time again
    });
  // Away from the page's top nothing comes back: the round is left out.
  await page.evaluate(() => window.scrollTo({ top: 60, behavior: "instant" }));
  await startsAgain();
  await page.waitForTimeout(300);
  await expect(hero).not.toHaveAttribute("data-words-round", /.+/);
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  // At the top the words are typed in again by the load-in's copies, the mark rising with them.
  await startsAgain();
  await expect(hero).toHaveAttribute("data-words-round", "2");
  expect(await hero.locator(".intro-overlay").count()).toBeGreaterThanOrEqual(3);
  const began = Date.now();
  await expect(hero.locator(".intro-overlay")).toHaveCount(0, { timeout: 6_000 });
  for (const selector of ["h1", ".home-hero-tagline", ".home-hero-note", ".home-hero-mark", ".home-hero-backed"])
    await expect(hero.locator(selector), selector).toHaveCSS("opacity", "1");
  await expect(hero.locator("h1")).toHaveText(/One engineering platform/);
  // "Scroll to explore" stays up through the round.
  await expect(hero.locator(".home-hero-explore")).toBeVisible();
  // A second report while the words stand changes nothing.
  await startsAgain();
  await expect(hero).toHaveAttribute("data-words-round", "2");
  // They stand about three seconds and are taken away again.
  await expect(hero.locator("h1")).toHaveCSS("opacity", "0", { timeout: 9_000 });
  expect(Date.now() - began).toBeGreaterThan(2_900);
  await expect(hero.locator(".intro-overlay")).toHaveCount(0);
  await expect(hero).toHaveAttribute("data-words", "gone");
  // And the next time round they come again.
  await startsAgain();
  await expect(hero).toHaveAttribute("data-words-round", "3");
});

/** When a press last reached the page, in ms since the document started. */
const pressedAt = (page: Page) => page.evaluate(() => (window as unknown as { __pressed: number }).__pressed);

/** What the frames say of a page that came in without a reload. While the page being left is still there nothing fades: the
 * black belongs to the page that comes in. That page's first frame has its address, its heading and the black together, at
 * most one frame into the lift; the black only ever lifts from there, and the veil is out of the way within a second. Returns
 * when the page's first frame was read and when the veil was first out of the way. */
function expectLanding(seen: Frame[], path: string, title: string) {
  const first = seen.findIndex((frame) => frame.path === path);
  expect(first, `a frame of ${path}`).toBeGreaterThanOrEqual(0);
  expect(seen.slice(0, first).every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
  expect(seen[first]).toMatchObject({ phase: "is-lift", shown: true, colour: "rgb(1, 1, 1)" });
  expect(seen[first].opacity).toBeGreaterThanOrEqual(0.9);
  expect(seen[first].title).toContain(title);
  const here = seen.slice(first);
  expect(here.every((frame) => frame.path === path)).toBe(true);
  expect(here.every((frame, index) => index === 0 || frame.opacity <= here[index - 1].opacity)).toBe(true);
  const idle = here.find((frame) => frame.phase === "is-idle");
  expect(idle, "the veil out of the way").toBeTruthy();
  expect(idle!.opacity).toBe(0);
  expect(idle!.at - here[0].at).toBeLessThanOrEqual(1000);
  expect(here[here.length - 1]).toMatchObject({ phase: "is-idle", opacity: 0 });
  return { at: here[0].at, clear: idle!.at };
}

const ABOUT = "Engineering built";
const INDUSTRIES = "Built for research.";

test("a link goes to its page at once, and the page comes out of black; Back and Forward too (ADR-0070)", async ({ page }) => {
  await record(page);
  await page.goto("/");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  // From the home page to About, then to Industries, as the lead's recording goes, and round once more.
  const waits: { toPage: number; toClear: number }[] = [];
  for (const [path, title] of [
    ["/about", ABOUT],
    ["/industries", INDUSTRIES],
    ["/about", ABOUT],
    ["/industries", INDUSTRIES],
  ]) {
    await frames(page);
    await page.locator(`.site-header a[href='${path}']`).first().click();
    await expect(page).toHaveURL(new RegExp(`${path}/?$`));
    await expect(veil).toHaveClass(/is-idle/);
    const landing = expectLanding(await frames(page), path, title);
    const pressed = await pressedAt(page);
    waits.push({ toPage: landing.at - pressed, toClear: landing.clear - pressed });
    // No load-in moves on these pages: nothing of theirs is tagged for them.
    await expect(page.locator(".intro-overlay, [data-intro-run]")).toHaveCount(0);
  }
  // A link is not held back. The delay that amendment 3 took away kept every link for 350 to 550 ms before its page was even
  // asked for; the fastest of the four presses here has the new page on screen in less than that, and clear of the black
  // within the 600 ms lift after it. The fastest is taken because one slow answer from the server is not a delay of ours.
  expect(Math.min(...waits.map((wait) => wait.toPage))).toBeLessThan(350);
  expect(Math.min(...waits.map((wait) => wait.toClear))).toBeLessThan(350 + 1000);
  // Back and Forward bring their pages out of black as well.
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/about");
  await expect(veil).toHaveClass(/is-idle/);
  expectLanding(await frames(page), "/about", ABOUT);
  await page.goForward();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/industries");
  await expect(veil).toHaveClass(/is-idle/);
  expectLanding(await frames(page), "/industries", INDUSTRIES);
});

test("the home page reached by a link comes out of black with its words typed in; brought back by Back, with its words whole", async ({ page }) => {
  await record(page);
  await page.goto("/about");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await frames(page);
  await page.locator(".site-header .wordmark").click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(veil).toHaveClass(/is-idle/);
  await expectHeroWhole(page);
  const seen = await frames(page);
  // As on its first load: the copies are ready in the page's first frame, under the black, and play as it lifts.
  const first = seen.findIndex((frame) => frame.path === "/");
  expect(seen.slice(0, first).every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
  expect(seen[first]).toMatchObject({ phase: "is-lift", shown: true, copies: 3, hiddenCopies: 3, riders: 1, running: 5, ownHeadline: STATEMENT });
  expect(seen[first].opacity).toBeGreaterThanOrEqual(0.9);
  const gone = seen.findIndex((frame, index) => index > first && frame.copies === 0);
  expect(gone).toBeGreaterThan(first);
  expect(seen.slice(first, gone).every((frame) => frame.ownHeadline === STATEMENT)).toBe(true);
  expect(seen[seen.length - 1]).toMatchObject({ phase: "is-idle", opacity: 0, copies: 0, running: 0 });
  // On to About and back with the browser's button: out of black again, and the words are there whole, not typed.
  await page.locator(".site-header a[href='/about']").first().click();
  await expect(page).toHaveURL(/\/about\/?$/);
  await expect(veil).toHaveClass(/is-idle/);
  await frames(page);
  await page.goBack();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(page.locator("#overview h1")).toBeVisible();
  await expect(veil).toHaveClass(/is-idle/);
  const back = await frames(page);
  expectLanding(back, "/", "One engineering platform");
  expect(back.every((frame) => frame.copies === 0 && frame.running === 0)).toBe(true);
  await expectHeroWhole(page);
});

test("a page loaded on its own starts black and is clear of it within about a second; the 404 page too", async ({ page }) => {
  await record(page);
  const veil = page.locator(".page-transition");
  for (const [path, title] of [
    ["/about", ABOUT],
    ["/industries", INDUSTRIES],
    ["/no-such-page", "Page not found"],
  ]) {
    await page.goto(path);
    await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText(title);
    const seen = await frames(page);
    // The first paint is black, #010101, as the page was served.
    expect(seen[0], path).toMatchObject({ phase: "is-hold", shown: true, opacity: 1, colour: "rgb(1, 1, 1)", copies: 0 });
    // The black holds for the fonts, 600 ms at the most (the stylesheet lifts it by itself then), and lifts in 600 ms: it
    // has begun to lift within 0.8 s of the first frame and the veil is out of the way within 1.5 s, on a busy machine too.
    const lifting = seen.find((frame) => frame.opacity < 1)!;
    const idle = seen.find((frame) => frame.phase === "is-idle")!;
    expect(lifting.at - seen[0].at, path).toBeLessThanOrEqual(800);
    expect(idle.at - seen[0].at, path).toBeLessThanOrEqual(1500);
    expect(seen.every((frame, index) => index === 0 || frame.opacity <= seen[index - 1].opacity)).toBe(true);
    expect(seen[seen.length - 1]).toMatchObject({ phase: "is-idle", opacity: 0, copies: 0, running: 0 });
  }
});

test("the workspace has no veil, and an old address shows none on its way there", async ({ page }) => {
  await record(page);
  for (const [path, lands] of [
    ["/workspace", "/workspace"],
    ["/studio", "/workspace/fea"],
    ["/chat/view", "/workspace/fea/view"],
    ["/studio/view", "/workspace/fea/view"],
  ]) {
    await page.goto(path);
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 15_000 }).toBe(lands);
    await page.waitForTimeout(400);
    const seen = await frames(page);
    expect(seen.length, path).toBeGreaterThan(0);
    expect(seen.every((frame) => frame.phase === "is-idle" && frame.opacity === 0), path).toBe(true);
  }
  // From the workspace back to the site by its link: that page comes out of black like any other.
  await page.goto("/workspace");
  await expect(page.locator(".site-header .is-website")).toBeVisible();
  await frames(page);
  await page.locator(".site-header .is-website").click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(page.locator(".page-transition")).toHaveClass(/is-idle/);
  const home = await frames(page);
  const first = home.findIndex((frame) => frame.path === "/");
  expect(home[first]).toMatchObject({ phase: "is-lift", shown: true });
  expect(home[first].opacity).toBeGreaterThanOrEqual(0.9);
});

test("the veil hides no focus: the skip link lies over the black, and it takes no press and is hidden from assistive technology", async ({ page }) => {
  // Without the page's scripts the veil is the stylesheet's alone, and the keyboard's focus is live from the first paint. Its
  // lift is held at its start here, so the black stays while the page is read.
  await page.route(/\/_next\/.*\.js(\?.*)?$/, (route) => route.abort());
  await page.goto("/about", { waitUntil: "domcontentloaded" });
  const veil = page.locator(".page-transition");
  await veil.evaluate((layer) => {
    for (const lift of layer.getAnimations()) {
      lift.pause();
      lift.currentTime = 0;
    }
  });
  await expect(veil).toHaveClass("page-transition is-hold");
  await expect(veil).toHaveCSS("opacity", "1");
  await expect(veil).toHaveCSS("pointer-events", "none");
  await expect(veil).toHaveAttribute("aria-hidden", "true");
  // The window's top left corner is as black as its middle: the veil covers the header.
  const corner = { x: 0, y: 0, width: 260, height: 70 };
  const black = await page.screenshot({ clip: corner });
  expect(black.equals(await page.screenshot({ clip: { ...corner, x: 600, y: 400 } }))).toBe(true);
  // Tab: the skip link takes the focus and is drawn in that corner, over the black, which has not moved.
  await page.keyboard.press("Tab");
  const skip = page.locator(".skip-link");
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport({ ratio: 1 });
  await expect(veil).toHaveCSS("opacity", "1");
  const layers = await page.evaluate(() => ({
    skip: Number(getComputedStyle(document.querySelector(".skip-link")!).zIndex),
    veil: Number(getComputedStyle(document.querySelector(".page-transition")!).zIndex),
    siblings: document.querySelector(".skip-link")!.parentElement === document.querySelector(".page-transition")!.parentElement,
  }));
  expect(layers.skip).toBeGreaterThan(layers.veil);
  expect(layers.siblings).toBe(true);
  const lit = await page.screenshot({ clip: corner });
  expect(lit.equals(black)).toBe(false);
  expect(black.equals(await page.screenshot({ clip: { ...corner, x: 600, y: 400 } }))).toBe(true);
});

test("where the page's scripts never run the stylesheet lifts the black by itself: after 600 ms on a page of the site, after 2 s on the home page", async ({ page }) => {
  await record(page);
  await page.route(/\/_next\/.*\.js(\?.*)?$/, (route) => route.abort());
  for (const [path, phase, holds] of [
    ["/about", "is-hold", 600],
    ["/", "is-enter", 2000],
  ] as const) {
    await page.goto(path, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".page-transition")).toHaveCSS("opacity", "0", { timeout: 10_000 });
    const seen = await frames(page);
    // No script took the veil over: it keeps the class it was served with, and nobody is left under the black.
    expect(seen.every((frame) => frame.phase === phase), path).toBe(true);
    expect(seen[0], path).toMatchObject({ shown: true, opacity: 1, colour: "rgb(1, 1, 1)" });
    // The hold is counted from the veil's first style, a little before the first frame read here; then 600 ms out of black.
    const lifting = seen.find((frame) => frame.opacity < 1)!;
    const clear = seen.find((frame) => frame.opacity === 0)!;
    expect(lifting.at - seen[0].at, path).toBeGreaterThan(holds - 250);
    expect(lifting.at - seen[0].at, path).toBeLessThanOrEqual(holds + 200);
    expect(clear.at - seen[0].at, path).toBeLessThanOrEqual(holds + 600 + 300);
  }
});

test.describe("in a browser with scripting off", () => {
  test.use({ javaScriptEnabled: false });

  test("the stylesheet lifts the black at once, on the home page and on any other", async ({ page }) => {
    for (const [path, phase] of [
      ["/about", "is-hold"],
      ["/", "is-enter"],
    ]) {
      await page.goto(path, { waitUntil: "commit" });
      const veil = page.locator(".page-transition");
      await expect(veil).toHaveCount(1);
      // From the moment the veil is in the page it is clear 600 ms later: nothing holds the black.
      const began = Date.now();
      await expect.poll(() => veil.evaluate((layer) => getComputedStyle(layer).opacity), { intervals: [50], timeout: 5_000 }).toBe("0");
      expect(Date.now() - began, path).toBeLessThan(1000);
      await expect(veil).toHaveClass(`page-transition ${phase}`);
    }
  });
});

test("no focus ring is ever under the black: a link pressed from the keyboard brings its page in without it, and Tab ends it", async ({ page }) => {
  await record(page);
  await page.goto("/industries");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  // Tab to the header's About link and press Enter: the link keeps the focus and its ring, so the page comes in unveiled.
  const about = page.locator(".site-header a[href='/about']").first();
  for (let presses = 0; presses < 12 && !(await about.evaluate((link) => link === document.activeElement)); presses++) await page.keyboard.press("Tab");
  await expect(about).toBeFocused();
  await frames(page);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/about\/?$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(ABOUT);
  await page.waitForTimeout(300);
  const byKeyboard = await frames(page);
  expect(byKeyboard.some((frame) => frame.path === "/about" && frame.ring)).toBe(true);
  expect(byKeyboard.every((frame) => frame.phase === "is-idle" && frame.opacity === 0)).toBe(true);
  // A press with the pointer brings the next page out of black; Tab while it lifts moves the focus on, and the black goes
  // in that frame. Whenever the Tab lands, no frame has a ring under a veil that is not out of the way.
  await page.locator(".site-header a[href='/industries']").first().click();
  await expect(page).toHaveURL(/\/industries\/?$/);
  await page.keyboard.press("Tab");
  await expect(veil).toHaveClass(/is-idle/);
  await page.waitForTimeout(300);
  const byPointer = await frames(page);
  expect(byPointer.some((frame) => frame.path === "/industries" && frame.ring)).toBe(true);
  expect(byPointer.every((frame) => !frame.ring || (frame.phase === "is-idle" && frame.opacity === 0))).toBe(true);
});

test("links pressed one after the other end on the last page, whole, with the veil out of the way and nothing left of the moves", async ({ page }) => {
  await record(page);
  await page.goto("/about");
  const veil = page.locator(".page-transition");
  await expect(veil).toHaveClass(/is-idle/, { timeout: 10_000 });
  await frames(page);
  // To the home page, whose words begin to be typed in, and on to Industries while its black is still lifting.
  await page.locator(".site-header .wordmark").click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await page.locator(".site-header a[href='/industries']").first().click();
  await expect(page).toHaveURL(/\/industries\/?$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(INDUSTRIES);
  await expect(veil).toHaveClass(/is-idle/);
  const seen = await frames(page);
  // The second page starts from black again, wherever the first one's lift had got to, and ends clear.
  const second = seen.findIndex((frame) => frame.path === "/industries");
  expect(seen[second]).toMatchObject({ phase: "is-lift", shown: true, copies: 0, running: 0 });
  expect(seen[second].opacity).toBeGreaterThanOrEqual(0.9);
  expect(seen[seen.length - 1]).toMatchObject({ path: "/industries", phase: "is-idle", opacity: 0, copies: 0, running: 0 });
  await expect(veil).toHaveCount(1);
  await expect(page.locator(".intro-overlay, [data-intro-run]")).toHaveCount(0);
  // Three in a row, ending on the home page: its words are typed in and stand whole, and the veil is out of the way.
  await page.locator(".site-header a[href='/about']").first().click();
  await expect(page).toHaveURL(/\/about\/?$/);
  await page.locator(".site-header .wordmark").click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await page.locator(".site-header a[href='/industries']").first().click();
  await expect(page).toHaveURL(/\/industries\/?$/);
  await page.locator(".site-header .wordmark").click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  await expect(veil).toHaveClass(/is-idle/);
  await expectHeroWhole(page);
  await expect(veil).toHaveCSS("opacity", "0");
  await expect(veil).toHaveCount(1);
  await expect(page.locator(".intro-overlay, [data-intro-run]")).toHaveCount(0);
});

test("a page the browser brings back as it was left is shown at once, never left black", async ({ page }) => {
  await page.goto("/about");
  await expect(page.locator(".page-transition")).toHaveClass(/is-idle/, { timeout: 10_000 });
  // The test's browser keeps no page whole, so the browser's word that it brought one back is given for it: in the first
  // frame of a page that has just come in by a link, while its black is at its fullest.
  const restored = await page.evaluate(
    () =>
      new Promise<{ before: string; after: string; opacity: string }>((resolve) => {
        document.querySelector<HTMLElement>(".site-header a[href='/industries']")!.click();
        const tick = () => {
          if (location.pathname !== "/industries") return void requestAnimationFrame(tick);
          const veil = document.querySelector(".page-transition")!;
          const before = veil.className;
          window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
          resolve({ before, after: veil.className, opacity: getComputedStyle(veil).opacity });
        };
        requestAnimationFrame(tick);
      }),
  );
  expect(restored).toEqual({ before: "page-transition is-lift", after: "page-transition is-idle", opacity: "0" });
  await page.waitForTimeout(400);
  await expect(page.locator(".page-transition")).toHaveClass("page-transition is-idle");
  await expect(page.locator(".page-transition")).toHaveCSS("opacity", "0");
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

  test("no page is veiled: not on its own load, not after a link, not after Back", async ({ page }) => {
    await record(page);
    await page.goto("/about");
    const veil = page.locator(".page-transition");
    await expect(veil).toBeHidden();
    await expect(veil).toHaveClass(/is-idle/);
    await page.waitForTimeout(700);
    await page.locator(".site-header a[href='/industries']").first().click();
    await expect(page).toHaveURL(/\/industries\/?$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(INDUSTRIES);
    await page.waitForTimeout(700);
    await page.locator(".site-header .wordmark").click();
    await expect.poll(() => new URL(page.url()).pathname).toBe("/");
    await expectHeroWhole(page, "none");
    await page.goBack();
    await expect.poll(() => new URL(page.url()).pathname).toBe("/industries");
    await page.waitForTimeout(700);
    const seen = await frames(page);
    for (const path of ["/about", "/industries", "/"]) expect(seen.some((frame) => frame.path === path), path).toBe(true);
    expect(seen.every((frame) => !frame.shown && frame.copies === 0 && frame.running === 0)).toBe(true);
    // A page that came in by a link or by Back never had the veil's class for black at all.
    expect(seen.filter((frame) => frame.path !== "/about").every((frame) => frame.phase === "is-idle")).toBe(true);
    await expect(veil).toHaveClass(/is-idle/);
  });
});
