import { readFileSync } from "node:fs";
import { test, expect, type Page, type Route } from "@playwright/test";
import { pageErrors } from "./page-errors";

/** The founders' AI activity page in a browser (ADR-0145), with the API played from the contract's own examples
 * (tests/fixtures/oversight, which the API's tests hold its answers to). What the review of 2026-11-27 found on the page is held
 * here: a plan's row is picked by keyboard and says so to a screen reader, a plan that is gone is said in the story's panel and the
 * feed stays, a first read that fails is tried again and its error goes, a hidden tab reads nothing, and "Show older" pressed twice
 * adds one page. Every read the page makes is recorded. */
const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/oversight/${name}.json`, "utf-8"));
const EVENTS: Record<string, unknown>[] = fixture("activity").events;
const STORY = fixture("plan-story");
const WEEKLY = fixture("weekly");
const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

type Answer = { status?: number; body: unknown };
type Played = {
  /** What the feed route answers the page's `n`th read of it. */
  events: (ask: URLSearchParams, n: number) => Answer | Promise<Answer>;
  plan?: (id: string) => Answer;
  weekly?: (n: number) => Answer;
};

/** Plays the oversight routes; returns the reads the page made of each. */
async function play(page: Page, played: Played) {
  const asked = { feed: [] as URLSearchParams[], plans: [] as string[], weekly: 0 };
  await page.route(/\/v1\/oversight\/.*/, async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/activity")) {
      asked.feed.push(url.searchParams);
      const answer = await played.events(url.searchParams, asked.feed.length);
      return json(route, answer.body, answer.status);
    }
    if (url.pathname.endsWith("/weekly")) {
      asked.weekly += 1;
      const answer: Answer = played.weekly?.(asked.weekly) ?? { body: WEEKLY };
      return json(route, answer.body, answer.status);
    }
    const id = url.pathname.split("/").at(-1)!;
    asked.plans.push(id);
    const answer: Answer = played.plan?.(id) ?? { body: { ...STORY, id } };
    return json(route, answer.body, answer.status);
  });
  return asked;
}

/** A feed of `n` calls a second apart, newest first, read as the route reads it: `limit`, `before` a key and `from` a key on. */
function calls(n: number) {
  const all = Array.from({ length: n }, (_, i) => {
    const at = new Date(Date.UTC(2026, 10, 27, 12, 0, n - i)).toISOString().replace(".000Z", "+00:00");
    return { ...EVENTS[3], at, key: `${at}|call|00000000-0000-4000-8000-${String(n - i).padStart(12, "0")}`, plan: null, what: `call ${n - i}` };
  });
  const read = (ask: URLSearchParams): Answer => {
    const [before, from] = [ask.get("before"), ask.get("from")];
    const start = before ? all.findIndex((e) => e.key === before) + 1 : 0;
    const end = from ? all.findIndex((e) => e.key === from) + 1 : all.length;
    return { body: { events: all.slice(start, end).slice(0, Number(ask.get("limit") ?? 50)) } };
  };
  return { all, read };
}

const rows = (page: Page) => page.locator("[data-testid=ai-feed] tbody tr");

test("a plan's row is picked with the keyboard, shows where the keyboard is, and says it is the one shown", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", pageErrors(errors));
  const asked = await play(page, { events: () => ({ body: { events: EVENTS } }) });
  await page.goto("/ai");
  await expect(rows(page)).toHaveCount(EVENTS.length);
  const picks = page.locator("[data-testid=ai-feed] button.ai-pick");
  await expect(picks).toHaveCount(EVENTS.filter((e) => e.plan !== null).length);  // every row of a plan, and no row without one
  const first = picks.first();
  await expect(first).toHaveAccessibleName("approve: show this plan's story");
  await expect(first).toHaveAttribute("aria-pressed", "false");
  // by keyboard alone: Tab from the views to the first plan's row
  await page.getByRole("button", { name: "Weekly" }).focus();
  await page.keyboard.press("Tab");
  await expect(first).toBeFocused();
  const outline = await first.evaluate((node) => { const style = getComputedStyle(node); return `${style.outlineStyle} ${style.outlineWidth}`; });
  expect(outline).toBe("solid 2px");  // where the keyboard is can be seen
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("ai-story").getByRole("heading", { name: "One plan’s story" })).toBeVisible();
  expect(asked.plans).toEqual([EVENTS[0].plan]);
  // the rows of the plan shown say so, and the others do not
  const pressed = await picks.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-pressed")));
  expect(pressed).toEqual(EVENTS.filter((e) => e.plan !== null).map((e) => String(e.plan === EVENTS[0].plan)));
  await expect(first).toHaveAttribute("aria-controls", "ai-story");
  await expect(page.locator("#ai-story")).toHaveAttribute("aria-live", "polite");
  // Space on another plan's row
  const other = picks.last();
  await other.focus();
  await page.keyboard.press("Space");
  await expect(other).toHaveAttribute("aria-pressed", "true");
  await expect(first).toHaveAttribute("aria-pressed", "false");
  expect(asked.plans).toEqual([EVENTS[0].plan, EVENTS[5].plan]);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);  // Space picked the row and did not scroll the page
  // a click anywhere on a plan's row still works, and a row with no plan has nothing to pick
  await rows(page).nth(1).locator("td").first().click();
  await expect(picks.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(rows(page).nth(3).locator("button")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("a plan that is gone is said in the story's panel, and the feed stays", async ({ page }) => {
  const asked = await play(page, {
    events: () => ({ body: { events: EVENTS } }),
    plan: (id) => (id === EVENTS[0].plan ? { status: 404, body: { detail: "There is no such plan." } } : { body: { ...STORY, id } }),
  });
  await page.goto("/ai");
  await page.locator("button.ai-pick").first().click();
  await expect(page.getByTestId("ai-story-error")).toHaveText("This plan is no longer in the records: its project was deleted.");
  await expect(rows(page)).toHaveCount(EVENTS.length);  // before the review the whole page became "Page not found"
  await expect(page.getByRole("heading", { name: "Page not found" })).toHaveCount(0);
  await expect(page.getByTestId("ai-feed-error")).toHaveCount(0);
  // and the next plan picked reads as usual: the panel's error goes with it
  await page.locator("button.ai-pick").last().click();
  await expect(page.getByTestId("ai-story").getByRole("heading", { name: "One plan’s story" })).toBeVisible();
  await expect(page.getByTestId("ai-story-error")).toHaveCount(0);
  expect(asked.plans).toEqual([EVENTS[0].plan, EVENTS[5].plan]);
});

test("a first read that fails is tried again, and its error goes when a read succeeds", async ({ page }) => {
  await page.clock.install();
  const asked = await play(page, {
    events: (_ask, n) => (n === 1 ? { status: 503, body: { detail: "The records could not be read." } } : { body: { events: EVENTS } }),
  });
  await page.goto("/ai");
  await expect(page.getByTestId("ai-feed-error")).toHaveText("The API answered with an error (503), so this could not be read. The page keeps trying.");
  await expect(page.getByTestId("ai-feed")).toHaveCount(0);
  await page.clock.fastForward(10_000);
  await expect(rows(page)).toHaveCount(EVENTS.length);
  await expect(page.getByTestId("ai-feed-error")).toHaveCount(0);
  expect(asked.feed.length).toBe(2);
  expect(asked.feed[1].toString()).toBe("limit=50");  // the first page again, not a refresh of a page that never came
});

test("a request that gets no answer is said in plain words, and the page goes on", async ({ page }) => {
  await page.clock.install();
  let down = true;
  await page.route(/\/v1\/oversight\/activity.*/, (route: Route) => (down ? route.abort("connectionrefused") : json(route, { events: EVENTS })));
  await page.goto("/ai");
  await expect(page.getByTestId("ai-feed-error")).toHaveText("The API could not be reached. Check the connection. The page keeps trying.");
  down = false;
  await page.clock.fastForward(10_000);
  await expect(rows(page)).toHaveCount(EVENTS.length);
  await expect(page.getByTestId("ai-feed-error")).toHaveCount(0);
  down = true;  // and a refresh that fails later leaves the feed in place under its error, until the next one succeeds
  await page.clock.fastForward(10_000);
  await expect(page.getByTestId("ai-feed-error")).toBeVisible();
  await expect(rows(page)).toHaveCount(EVENTS.length);
  down = false;
  await page.clock.fastForward(10_000);
  await expect(page.getByTestId("ai-feed-error")).toHaveCount(0);
});

test("anyone the API answers 404 sees a page that is not there, and the page stops asking", async ({ page }) => {
  await page.clock.install();
  const asked = await play(page, { events: () => ({ status: 404, body: { detail: "Not Found" } }) });
  await page.goto("/ai");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.clock.fastForward(30_000);
  expect(asked.feed.length).toBe(1);
});

test("an open page reads again every ten seconds, a hidden one does not, and a refresh is never kept as a view", async ({ page }) => {
  await page.clock.install();
  const asked = await play(page, { events: () => ({ body: { events: [] } }) });  // an empty feed: before the review each refresh was a view
  await page.goto("/ai");
  await expect(page.getByText("Nothing yet.")).toBeVisible();
  expect(asked.feed.map(String)).toEqual(["limit=50"]);
  await page.clock.fastForward(10_000);
  await expect.poll(() => asked.feed.length).toBe(2);
  await page.clock.fastForward(10_000);
  await expect.poll(() => asked.feed.length).toBe(3);
  for (const refresh of asked.feed.slice(1)) expect(refresh.get("since") ?? refresh.get("from")).toBeTruthy();  // the API keeps no view of these
  const show = (hidden: boolean) => page.evaluate((to) => {
    Object.defineProperty(document, "hidden", { configurable: true, get: () => to });
    document.dispatchEvent(new Event("visibilitychange"));
  }, hidden);
  await show(true);
  await page.clock.fastForward(60_000);
  await page.clock.fastForward(60_000);
  expect(asked.feed.length).toBe(3);  // two minutes hidden: nothing was read
  await show(false);
  await expect.poll(() => asked.feed.length).toBe(4);  // shown again: read at once
  await page.clock.fastForward(10_000);
  await expect.poll(() => asked.feed.length).toBe(5);
});

test("Show older pressed twice adds one page, and the refresh after it keeps the page", async ({ page }) => {
  await page.clock.install();
  const feed = calls(120);
  let release: (() => void) | null = null;
  const asked = await play(page, {
    events: async (ask) => {
      if (ask.get("before") && !ask.get("from")) await new Promise<void>((go) => { release = go; });  // "Show older" waits for the test
      return feed.read(ask);
    },
  });
  await page.goto("/ai");
  await expect(rows(page)).toHaveCount(50);
  const older = page.getByRole("button", { name: "Show older" });
  await older.dblclick();
  await expect(page.getByRole("button", { name: "Reading older…" })).toBeDisabled();
  await page.getByRole("button", { name: "Reading older…" }).click({ force: true });  // and once more while it reads
  await expect.poll(() => release !== null).toBe(true);
  release!();
  await expect(rows(page)).toHaveCount(100);
  expect(asked.feed.filter((ask) => ask.get("before") && !ask.get("from")).length).toBe(1);
  const shown = await rows(page).evaluateAll((nodes) => nodes.map((node) => node.querySelectorAll("td")[2].textContent));
  expect(shown).toEqual(feed.all.slice(0, 100).map((e) => e.what));  // each event once and in order: a page added twice would show fifty of them twice
  await page.clock.fastForward(10_000);  // the refresh reads from the lowered floor
  await expect.poll(() => asked.feed.at(-1)!.get("from")).toBe(feed.all[99].key);
  await expect(rows(page)).toHaveCount(100);
  release = null;
  await page.getByRole("button", { name: "Show older" }).click();
  await expect.poll(() => release !== null).toBe(true);
  release!();
  await expect(rows(page)).toHaveCount(120);
  await expect(page.getByRole("button", { name: "Show older" })).toHaveCount(0);  // the feed's beginning: nothing older to ask for
});

test("the weeks say what went wrong where they show, and read again when asked", async ({ page }) => {
  const asked = await play(page, {
    events: () => ({ body: { events: EVENTS } }),
    weekly: (n) => (n === 1 ? { status: 503, body: { detail: "x" } } : { body: WEEKLY }),
  });
  await page.goto("/ai");
  await expect(rows(page)).toHaveCount(EVENTS.length);
  await page.getByRole("button", { name: "Weekly" }).click();
  await expect(page.getByTestId("ai-week-error")).toContainText("The API answered with an error (503), so this could not be read.");
  await page.getByRole("button", { name: "Now" }).click();
  await expect(rows(page)).toHaveCount(EVENTS.length);  // the feed is as it was, with no error of the weeks' over it
  await expect(page.getByTestId("ai-feed-error")).toHaveCount(0);
  await page.getByRole("button", { name: "Weekly" }).click();
  await expect(page.getByTestId("ai-week")).toContainText(`Since ${WEEKLY.since}`);  // opening the tab again asked again
  await expect(page.getByTestId("ai-week-error")).toHaveCount(0);
  expect(asked.weekly).toBe(2);
});
