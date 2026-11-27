import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  BEGINNING, firstPage, givenUp, mergeNewer, money, NO_ADDRESS, NOT_REACHED, NotHere, PAGE, PlanGone, planRows, poll, readActivity, readPlanStory,
  readWeekly, REFRESH_PAGE, refreshed, SHOWN_MAX, storyLines, toneOf, watchFeed, whoShort, withOlder,
  type ActivityEvent, type Feed, type FeedAsk, type FeedReader, type PlanStory, type PollEnv,
} from "../lib/oversight";

// The founders' AI activity page (ADR-0145): the readings the page draws from the API's answers, on the contract's own examples
// (tests/fixtures/oversight, which the API's tests hold its answers to).
const fixture = (name: string) => JSON.parse(readFileSync(new URL(`./fixtures/oversight/${name}`, import.meta.url), "utf-8"));
const events: ActivityEvent[] = fixture("activity.json").events;
const story: PlanStory = fixture("plan-story.json");

test("a call answered by a model outside the checked list is flagged, whatever its outcome", () => {
  const unchecked = events.find((e) => e.checked === false)!;
  assert.equal(toneOf(unchecked), "bad");
  assert.equal(toneOf({ ...unchecked, outcome: "kept" }), "bad");
  assert.equal(toneOf({ outcome: "kept", checked: true }), "good");
  assert.equal(toneOf({ outcome: "set aside", checked: true }), "bad");
  assert.equal(toneOf({ outcome: "question", checked: null }), "warn");
  assert.equal(toneOf({ outcome: "something new", checked: null }), "quiet");
});

test("a refresh puts the newer events on top, each once", () => {
  const shown = events.slice(2);
  const merged = mergeNewer(shown, events.slice(0, 3));
  assert.deepEqual(merged, events);
  assert.deepEqual(mergeNewer(events, []), events);
});

test("money and names print short", () => {
  assert.equal(money(null), "–");
  assert.equal(money(0.041), "$0.041");
  assert.equal(money(2.11), "$2.11");
  assert.equal(whoShort("founder@example.com"), "founder");
  assert.equal(whoShort("customer 3fa91c07be"), "customer 3fa91c07be");
  assert.equal(whoShort("robot"), "robot");
});

test("a plan's story reads in the order it happened, with what the checks turned back", () => {
  const lines = storyLines(story);
  const heads = lines.map((l) => l.head);
  assert.deepEqual(heads.slice(0, 4), ["Sentence read", "Answer 1 turned back by the checks", "Model call: plan_steps", "Model call: plan_steps"]);
  assert.equal(lines[0].detail, "set the width to 30 mm and run it");
  assert.match(lines[1].detail ?? "", /^step 1: in is not the unit/);
  assert.ok(heads.includes("Approved by founder") && heads.includes("New version 4, made by assistant"));
  assert.deepEqual(heads.filter((h) => /^(Geometry|Solver|QA):/.test(h)), ["Geometry: Set the width to 30 mm", "Solver: Check the setup before the run",
    "Solver: Run the analysis", "QA: Read the result's own checks"]);
  assert.equal(heads.at(-1), "Run on the solver pool: running");
  assert.equal(lines.at(-1)?.detail?.startsWith("2 of 6 stages"), true);
});

test("a customer's story shows the steps by tool, and a plan not approved shows no steps", () => {
  const hidden: PlanStory = { ...story, words_shown: false, ask: "a customer's words, not shown", steps: story.steps.map((s) => ({ ...s, line: null, note: null })) };
  assert.ok(storyLines(hidden).some((l) => l.head === "Solver: run"));
  const waiting: PlanStory = { ...story, state: "proposed", approved_at: null, version: null, job: null };
  const heads = storyLines(waiting).map((l) => l.head);
  assert.equal(heads.at(-1), "Waiting for the engineer's approval");
  assert.ok(!heads.some((h) => h.startsWith("Solver:")));
  const unchecked: PlanStory = { ...story, calls: [{ ...story.calls[0], checked: false, model: "claude-stand-in-1" }] };
  const call = storyLines(unchecked).find((l) => l.head.startsWith("Model call"))!;
  assert.equal(call.tone, "bad");
  assert.match(call.detail ?? "", /claude-stand-in-1, a model outside the checked list/);
});

// ------------------------------------------------------------------------ the review of 2026-11-27: what it found, held fixed

/** An event of the feed at a second of one day; `row` tells apart two of one kind at one instant, as the row's id does. */
function event(second: number, kind: ActivityEvent["kind"] = "call", row = 0, more: Partial<ActivityEvent> = {}): ActivityEvent {
  const at = new Date(Date.UTC(2026, 10, 27, 12, 0, second)).toISOString().replace(".000Z", "+00:00");
  const id = `00000000-0000-4000-8000-${String(row).padStart(12, "0")}`;
  return { ...events[3], kind, at, key: `${at}|${kind}|${id}`, plan: null, run: null, ...more };
}

/** The feed's order: by time, then kind, then row, as the API orders it. */
const place = (key: string) => { const [at, kind, row] = key.split("|"); return [Date.parse(at), kind, row] as const; };
function after(a: string, b: string): boolean {
  const [x, y] = [place(a), place(b)];
  for (let i = 0; i < 3; i += 1) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
}

/** The records, and the feed route read over them as the API reads it (api/tests/test_oversight.py holds the route to the same
 * readings); `asked` is every read the page made. */
function records(kept: ActivityEvent[] = []) {
  const asked: FeedAsk[] = [];
  const read: FeedReader = async (ask) => {
    asked.push(ask);
    const sorted = [...kept].sort((a, b) => (after(a.key, b.key) ? -1 : 1));
    const there = sorted.filter((e) => (!ask.before || after(ask.before, e.key)) && (!ask.since || after(e.key, ask.since))
      && (!ask.from || e.key === ask.from || after(e.key, ask.from)));
    const limit = ask.limit ?? 50;
    return { events: there.slice(0, limit), older: there.length > limit };
  };
  const all = () => [...kept].sort((a, b) => (after(a.key, b.key) ? -1 : 1));
  return { kept, asked, read, all };
}

const keys = (feed: Feed | ActivityEvent[]) => (Array.isArray(feed) ? feed : feed.events).map((e) => e.key);

test("a refresh shows a call recorded after newer ones, which a read of what is newer than the newest never did", async () => {
  // a plan's first call is answered, its second takes a while, and both rows are written when the request ends; meanwhile someone
  // else's call is recorded and the page reads
  const db = records(Array.from({ length: PAGE + 5 }, (_, i) => event(i)));
  const other = event(120);
  db.kept.push(other);
  let feed = await firstPage(db.read);
  assert.equal(feed.events.length, PAGE);
  assert.equal(feed.floor, feed.events.at(-1)!.key);
  const first = event(100, "call", 1, { outcome: "turned back" });  // answered before the other's call, written after it
  db.kept.push(first, event(130, "call", 2), event(131, "plan", 3));
  const newer = await db.read({ since: other.key });
  assert.ok(!keys(newer.events).includes(first.key));  // what the page asked for before the review
  feed = await refreshed(db.read, feed);
  assert.deepEqual(keys(feed), keys(db.all()).slice(0, PAGE + 3));
  assert.ok(keys(feed).includes(first.key));
  assert.equal(feed.floor, feed.events.at(-1)!.key);  // the floor did not move: the page shows everything from it on
  assert.ok(db.asked.slice(1).every((ask) => ask.from !== undefined || ask.since !== undefined));
});

test("a refresh shows every new event, however many came since the last one", async () => {
  const db = records([event(0)]);
  let feed = await firstPage(db.read);
  assert.deepEqual(feed, { events: [db.kept[0]], floor: null });  // the whole feed: the refresh reads from the beginning
  for (let i = 1; i <= 2 * REFRESH_PAGE + 30; i += 1) db.kept.push(event(i));
  assert.equal((await db.read({ limit: REFRESH_PAGE, since: feed.events[0].key })).events.length, REFRESH_PAGE);  // one read is one page of them
  db.asked.length = 0;
  feed = await refreshed(db.read, feed);
  assert.equal(feed.events.length, 2 * REFRESH_PAGE + 31);
  assert.deepEqual(keys(feed), keys(db.all()));
  assert.equal(new Set(keys(feed)).size, feed.events.length);
  assert.equal(feed.floor, null);
  assert.deepEqual(db.asked.map((ask) => [ask.since, ask.limit, ask.before !== undefined]),
    [[BEGINNING, REFRESH_PAGE, false], [BEGINNING, REFRESH_PAGE, true], [BEGINNING, REFRESH_PAGE, true]]);
});

test("events of one instant are each shown once, wherever a page ends among them", async () => {
  const db = records();
  for (let row = 0; row < PAGE + 20; row += 1) db.kept.push(event(7, "call", row));
  db.kept.push(event(7, "plan", 500), event(7, "approval", 500));
  let feed = await firstPage(db.read);  // the page ends inside the instant
  assert.equal(feed.events.length, PAGE);
  db.kept.push(event(7, "call", 900), event(7, "plan", 901));  // two more of that instant, one on each side of the page's end
  feed = await refreshed(db.read, feed);
  const all = keys(db.all());
  assert.deepEqual(keys(feed), all.slice(0, all.indexOf(feed.floor!) + 1));
  feed = await withOlder(db.read, feed);
  assert.deepEqual(keys(feed), all);
  assert.equal(new Set(keys(feed)).size, PAGE + 24);
  assert.equal(feed.floor, null);
  assert.deepEqual(await withOlder(db.read, feed), feed);  // nothing older: no read
});

test("an open page on an empty feed asks only for what the API keeps no view of", async () => {
  // the review: with nothing shown the refresh had no `since` to send, so each one, every ten seconds, was kept as a view of the page
  const db = records();
  let feed = await firstPage(db.read);
  assert.deepEqual(feed, { events: [], floor: null });
  for (let i = 0; i < 3; i += 1) feed = await refreshed(db.read, feed);
  assert.deepEqual(db.asked, [{ limit: PAGE }, ...Array(3).fill({ limit: REFRESH_PAGE, since: BEGINNING })]);
  db.kept.push(event(1));
  feed = await refreshed(db.read, feed);
  assert.equal(feed.events.length, 1);
  assert.ok(db.asked.slice(1).every((ask) => ask.since !== undefined || ask.from !== undefined));
});

test("new events grow the page to its most and no further, and Show older goes past it and stays", async () => {
  const db = records(Array.from({ length: SHOWN_MAX + 40 }, (_, i) => event(i)));
  let feed = await refreshed(db.read, { events: [], floor: null });
  let all = keys(db.all());
  assert.deepEqual(keys(feed), all.slice(0, SHOWN_MAX));
  assert.equal(feed.floor, all[SHOWN_MAX - 1]);  // the floor rose to the oldest kept: the page holds everything from it on
  feed = await withOlder(db.read, feed);
  assert.deepEqual(keys(feed), all);
  assert.equal(feed.floor, null);  // fewer than a page were older
  feed = await refreshed(db.read, feed);
  assert.deepEqual(keys(feed), all);  // a refresh does not take back what Show older brought
  for (let i = 0; i < 30; i += 1) db.kept.push(event(5000 + i));
  feed = await refreshed(db.read, feed);
  all = keys(db.all());
  assert.deepEqual(keys(feed), all.slice(0, SHOWN_MAX + 40));  // as many as before: the newest, and the oldest thirty let go
  assert.equal(feed.floor, all[SHOWN_MAX + 39]);
  feed = await refreshed(db.read, feed);
  assert.deepEqual(keys(feed), all.slice(0, SHOWN_MAX + 40));
});

test("a refreshed event shows its new outcome, and one whose plan was deleted goes", async () => {
  const db = records([event(1, "plan", 1, { outcome: "proposed" }), event(2, "plan", 2), event(3)]);
  let feed = await firstPage(db.read);
  db.kept[0] = { ...db.kept[0], outcome: "done" };
  db.kept.splice(1, 1);
  feed = await refreshed(db.read, feed);
  assert.deepEqual(feed.events.map((e) => e.outcome), [db.kept[1].outcome, "done"]);
});

/** A reader whose answers wait until the test lets them go, one at a time. */
function held(read: FeedReader) {
  const waiting: (() => void)[] = [];
  let open = 0;
  let most = 0;
  const slow: FeedReader = async (ask) => {
    open += 1;
    most = Math.max(most, open);
    await new Promise<void>((go) => waiting.push(go));
    open -= 1;
    return read(ask);
  };
  const settle = () => new Promise((done) => setTimeout(done, 0));
  return { slow, most: () => most, pending: () => waiting.length, release: async () => { waiting.shift()?.(); await settle(); }, settle };
}

test("the feed is read by one request at a time, and Show older asked twice adds one page", async () => {
  const db = records(Array.from({ length: 3 * PAGE }, (_, i) => event(i)));
  const io = held(db.read);
  const shown: Feed[] = [];
  const watch = watchFeed(io.slow, { feed: (feed) => shown.push(feed), error: (e) => assert.fail(String(e)) });
  void watch.refresh();
  void watch.refresh();  // the timer again, and the tab shown again, while the first read is out
  void watch.older();  // nothing is shown yet: there is no floor to go below
  await io.settle();
  assert.equal(io.pending(), 1);
  await io.release();
  assert.equal(shown.length, 1);
  assert.equal(shown[0].events.length, PAGE);
  void watch.older();
  void watch.older();  // a second click before the first page is back
  void watch.refresh();  // and the timer: it waits its turn, and does not undo the older page
  await io.settle();
  assert.equal(io.pending(), 1);
  await io.release();
  assert.equal(io.pending(), 0);  // one page asked for, and the refresh behind it was skipped
  assert.equal(shown.length, 2);
  assert.equal(shown[1].events.length, 2 * PAGE);
  assert.equal(new Set(keys(shown[1])).size, 2 * PAGE);
  void watch.refresh();
  await io.settle();
  await io.release();
  assert.deepEqual(keys(shown[2]), keys(shown[1]));  // the refresh reads from the lowered floor, so the older page stays
  void watch.older();
  await io.settle();
  await io.release();
  assert.equal(shown[3].events.length, 3 * PAGE);
  assert.equal(io.most(), 1);
  assert.equal(db.asked.filter((ask) => ask.before !== undefined && ask.from === undefined && ask.since === undefined).length, 2);
});

test("a first read that fails is tried again, and what failed is told once for each failure", async () => {
  const db = records([event(1)]);
  let down = true;
  const told: string[] = [];
  const watch = watchFeed(async (ask) => { if (down) throw new Error(NOT_REACHED); return db.read(ask); },
    { feed: (feed) => told.push(`read ${feed.events.length}`), error: (e) => told.push((e as Error).message) });
  await watch.refresh();
  await watch.refresh();
  down = false;
  await watch.refresh();  // the first page again, not a refresh of nothing
  assert.deepEqual(db.asked, [{ limit: PAGE }]);
  await watch.refresh();
  down = true;
  await watch.refresh();
  down = false;
  await watch.refresh();
  assert.deepEqual(told, [NOT_REACHED, NOT_REACHED, "read 1", "read 1", NOT_REACHED, "read 1"]);  // each success is the page's cue to drop the error
  watch.stop();
  await watch.refresh();
  await watch.older();
  assert.equal(told.length, 6);
});

/** A tab and a clock for the poll: the test hides and shows the tab and lets the timers fire. */
function tab() {
  let hidden = false;
  let shown: (() => void) | null = null;
  const timers = new Map<number, { run: () => void; ms: number }>();
  let next = 1;
  const env: PollEnv = {
    hidden: () => hidden,
    onShown: (cb) => { shown = cb; return () => { shown = null; }; },
    later: (run, ms) => { timers.set(next, { run, ms }); next += 1; return next - 1; },
    cancel: (timer) => { timers.delete(timer as number); },
  };
  const settle = () => new Promise((done) => setTimeout(done, 0));
  return {
    env, timers, settle,
    hide: () => { hidden = true; },
    show: async () => { hidden = false; shown?.(); await settle(); },
    fire: async () => { const [id, timer] = [...timers.entries()][0]; timers.delete(id); timer.run(); await settle(); },
    listening: () => shown !== null,
  };
}

test("the poll waits while the tab is hidden, reads at once when it is shown, and never runs two reads at a time", async () => {
  const page = tab();
  let runs = 0;
  let open = 0;
  let most = 0;
  let finish: (() => void) | null = null;
  const task = async () => {
    runs += 1; open += 1; most = Math.max(most, open);
    await new Promise<void>((done) => { finish = done; });
    open -= 1;
  };
  const end = async () => { finish?.(); await page.settle(); };
  const stop = poll(task, 10_000, page.env);
  await page.settle();
  assert.equal(runs, 1);  // at once
  assert.equal(page.timers.size, 0);  // and no timer while the read is out: the next is counted from its end
  await page.show();  // the tab is shown again while the read is out
  assert.equal(runs, 1);
  await end();
  assert.deepEqual([...page.timers.values()].map((t) => t.ms), [10_000]);
  await page.fire();
  assert.equal(runs, 2);
  await end();
  page.hide();
  await page.fire();  // the timer of a hidden tab: nothing is read, and nothing is set to read later
  assert.equal(runs, 2);
  assert.equal(page.timers.size, 0);
  await page.show();
  assert.equal(runs, 3);  // shown again: at once
  await end();
  await page.show();  // shown with a timer waiting: the read is now, and the timer is not left to fire as well
  assert.equal(runs, 4);
  assert.equal(page.timers.size, 0);
  await end();
  assert.equal(page.timers.size, 1);
  assert.equal(most, 1);
  stop();
  assert.equal(page.timers.size, 0);
  assert.equal(page.listening(), false);
  await page.show();
  assert.equal(runs, 4);
  const failing = poll(async () => { runs += 1; throw new Error("down"); }, 10_000, page.env);  // a read that fails is tried again
  await page.settle();
  assert.equal(page.timers.size, 1);
  failing();
});

/** `fetch` for one test: what was asked, and the answer the test gives. */
async function fetching<T>(answer: (url: string) => Response | Promise<Response>, run: (asked: string[]) => Promise<T>): Promise<T> {
  const real = globalThis.fetch;
  const asked: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => { asked.push(String(input)); return answer(String(input)); }) as typeof fetch;
  try { return await run(asked); } finally { globalThis.fetch = real; }
}
const answered = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

test("a plan that is gone is not a page that is not there", async () => {
  // the review: any 404 turned the whole page into "Page not found", so a row whose plan had been deleted took the feed away
  await fetching(() => answered(404, { detail: "There is no such plan." }), async () => {
    await assert.rejects(readPlanStory("http://api.test", "6f1c2a9e-1b7d-4c55-9a51-3d7f2b1e8c40"), (e) => e instanceof PlanGone && !(e instanceof NotHere));
  });
  await fetching(() => answered(404, { detail: "Not Found" }), async () => {
    await assert.rejects(readPlanStory("http://api.test", "6f1c2a9e-1b7d-4c55-9a51-3d7f2b1e8c40"), (e) => e instanceof NotHere && !(e instanceof PlanGone));
    await assert.rejects(readActivity("http://api.test"), NotHere);
    await assert.rejects(readWeekly("http://api.test"), NotHere);
  });
  await fetching(() => new Response("<html>no such page</html>", { status: 404 }), async () => {
    await assert.rejects(readPlanStory("http://api.test", "x"), NotHere);  // a 404 that is not the API's
  });
});

test("a request that gets no answer, and a page built without the API's address, are said in fixed words", async () => {
  await fetching(() => { throw new TypeError("Failed to fetch"); }, async () => {
    await assert.rejects(readActivity("http://api.test"), { message: NOT_REACHED });
    await assert.rejects(readWeekly("http://api.test"), { message: NOT_REACHED });
  });
  await fetching(() => { throw new TypeError("NetworkError when attempting to fetch resource."); }, async () => {
    await assert.rejects(readPlanStory("http://api.test", "x"), { message: NOT_REACHED });
  });
  await fetching(() => answered(200, { events: [] }), async (asked) => {
    for (const none of ["", "  "]) {
      await assert.rejects(readActivity(none), { message: NO_ADDRESS });
      await assert.rejects(readPlanStory(none, "x"), { message: NO_ADDRESS });
      await assert.rejects(readWeekly(none), { message: NO_ADDRESS });
    }
    assert.deepEqual(asked, []);  // nothing is asked of the page's own address, whose 404 read as "Page not found"
  });
  await fetching(() => answered(503, { detail: "x" }), async () => {
    await assert.rejects(readActivity("http://api.test"), { message: "The API answered with an error (503), so this could not be read." });
  });
  const left = Object.assign(new Error("The operation was aborted."), { name: "AbortError" });
  await fetching(() => { throw left; }, async () => {
    await assert.rejects(readActivity("http://api.test"), (e) => e === left && givenUp(e));  // a reading the page gave up is not an error to show
  });
  assert.equal(givenUp(new Error(NOT_REACHED)), false);
});

test("a read of the feed asks the route for its places by name", async () => {
  await fetching((url) => answered(200, url.includes("since=") ? { events, older: true } : fixture("activity.json")), async (asked) => {
    assert.deepEqual(await readActivity("http://api.test/", { limit: 200, from: events[5].key, before: events[1].key }), { events, older: false });
    assert.equal((await readActivity("http://api.test", { limit: 200, since: BEGINNING })).older, true);
    await readActivity("http://api.test");
    const [first, second, third] = asked.map((url) => new URL(url));
    assert.equal(first.pathname, "/v1/oversight/activity");
    assert.deepEqual(Object.fromEntries(first.searchParams), { limit: "200", from: events[5].key, before: events[1].key });
    assert.deepEqual(Object.fromEntries(second.searchParams), { limit: "200", since: BEGINNING });
    assert.equal(third.search, "");
  });
});

test("two events alike in all but their key are two", () => {
  // the review: rows were told apart by kind, time, plan, run and feature, which two calls of one plan can share
  const twins = [event(5, "call", 2, { plan: "p", run: "r" }), event(5, "call", 1, { plan: "p", run: "r" })];
  assert.deepEqual(mergeNewer([twins[1]], twins), twins);
  assert.deepEqual(mergeNewer(twins, twins), twins);
});

test("a call says what became of its own answer", () => {
  assert.deepEqual(story.calls.map((c) => c.outcome), ["turned back", "running"]);
  const calls = storyLines(story).filter((l) => l.head.startsWith("Model call"));
  assert.match(calls[0].detail ?? "", /claude-opus-5-5 · turned back · 5\.8 s/);
  assert.match(calls[1].detail ?? "", /claude-opus-5-5 · running · 6\.2 s/);
  assert.deepEqual(calls.map((l) => l.tone), ["warn", "good"]);
  assert.equal(toneOf({ outcome: "turned back", checked: true }), "warn");
  assert.equal(toneOf({ outcome: "plan done", checked: true }), "good");  // the records do not say which call it was: it reads as its plan
  assert.equal(toneOf({ outcome: "plan refused", checked: null }), "bad");
  assert.equal(toneOf({ outcome: "declined", checked: true }), "bad");
});

// ------------------------------------------------------------------ the second review of 2026-11-27: what it found, held fixed

test("a feed that fits its page exactly has no floor, and a refresh of a full read is one request", async () => {
  // the second review: a full page was taken to mean there are older events, so a feed of exactly a page kept "Show older" with
  // nothing behind it, and a refresh that came back full asked once more for nothing
  const exact = records(Array.from({ length: PAGE }, (_, i) => event(i)));
  let feed = await firstPage(exact.read);
  assert.equal(feed.events.length, PAGE);
  assert.equal(feed.floor, null);  // so the page shows no "Show older"
  feed = await refreshed(exact.read, feed);
  assert.deepEqual(exact.asked, [{ limit: PAGE }, { limit: REFRESH_PAGE, since: BEGINNING }]);
  exact.kept.push(event(PAGE));  // one more, and there is an older one
  assert.equal((await firstPage(exact.read)).floor, keys(exact.all())[PAGE - 1]);

  const db = records(Array.from({ length: REFRESH_PAGE }, (_, i) => event(i)));  // exactly what one read of a refresh gives
  feed = await firstPage(db.read);
  for (let i = 0; i < 2; i += 1) feed = await withOlder(db.read, feed);
  assert.equal(feed.floor, keys(db.all())[3 * PAGE - 1]);
  feed = await withOlder(db.read, feed);  // the last page is exactly full, and nothing is past it
  assert.equal(feed.events.length, REFRESH_PAGE);
  assert.equal(feed.floor, null);
  db.asked.length = 0;
  feed = await refreshed(db.read, feed);
  assert.deepEqual(db.asked, [{ limit: REFRESH_PAGE, since: BEGINNING }]);
  assert.deepEqual(keys(feed), keys(db.all()));

  const more = records(Array.from({ length: REFRESH_PAGE + PAGE }, (_, i) => event(i)));  // a floor with exactly one read above it
  feed = await firstPage(more.read);
  for (let i = 0; i < 3; i += 1) feed = await withOlder(more.read, feed);
  const floor = keys(more.all())[REFRESH_PAGE - 1];
  assert.equal(feed.floor, floor);
  more.asked.length = 0;
  feed = await refreshed(more.read, feed);
  assert.deepEqual(more.asked, [{ limit: REFRESH_PAGE, from: floor }]);
  assert.equal(feed.events.length, REFRESH_PAGE);
  assert.equal(feed.floor, floor);
});

test("what the feed shows of a plan changes when one of its rows does, and not when another plan's does", () => {
  // the second review: the story's panel kept the story it read when the row was picked, whatever the feed showed of the plan since
  const shown = [event(3, "call", 1, { plan: "p", outcome: "proposed" }), event(2, "plan", 2, { plan: "p", outcome: "proposed" }),
    event(1, "plan", 3, { plan: "q", outcome: "proposed" }), event(0)];
  const before = planRows(shown, "p");
  assert.equal(planRows([...shown], "p"), before);  // a refresh that changed nothing
  assert.equal(planRows([event(9), ...shown.map((e) => (e.plan === "q" ? { ...e, outcome: "refused" } : e))], "p"), before);
  assert.notEqual(planRows(shown.map((e) => (e.kind === "plan" && e.plan === "p" ? { ...e, outcome: "running" } : e)), "p"), before);
  assert.notEqual(planRows([event(5, "approval", 2, { plan: "p", outcome: "proposed" }), ...shown], "p"), before);  // it was approved
  assert.notEqual(planRows(shown.slice(1), "p"), before);
  assert.equal(planRows(shown, "nobody's"), "");
});

test("the contract's examples carry what the page reads", () => {
  assert.ok(events.every((e) => e.key === `${e.at}|${e.kind}|${e.key.split("|")[2]}` && /^[0-9a-f-]{36}$/.test(e.key.split("|")[2])));
  assert.equal(new Set(events.map((e) => e.key)).size, events.length);
  assert.ok(events.filter((e) => !e.words_shown).every((e) => /^customer [0-9a-f]{10}$/.test(e.who)));
  assert.equal(new Date(`${fixture("weekly.json").since}T00:00:00Z`).getUTCDay(), 1);  // a Monday
  assert.equal(fixture("activity.json").older, false);
});
