/** The founders' AI activity page (ADR-0145): what the API's oversight routes answer, how the page asks for it, how it keeps its feed
 * whole while it stays open (the refresh, the poll), and the pure readings the page draws from it (a row's tone, a plan's story as
 * lines, the money and the times). Read only: the page changes nothing and calls no model. The API decides who may read it; anyone but
 * a founder is answered 404, which the page shows as a page that is not there. */

export type ActivityEvent = {
  /** The event's place in the feed (its time, kind and row), as the API gives it: no two events share one, and a read can start or
   * end exactly at one. */
  key: string;
  kind: "call" | "plan" | "approval";
  at: string;
  who: string;
  words_shown: boolean;
  actor: string;
  what: string;
  model: string | null;
  checked: boolean | null;
  outcome: string;
  seconds: number | null;
  cost_usd: number | null;
  plan: string | null;
  run: string | null;
  ask: string | null;
};

export type StoryCall = {
  at: string; what: string; model: string; checked: boolean | null; input_tokens: number; output_tokens: number; seconds: number;
  cost_usd: number | null; stop_reason: string | null; outcome: string; sent: string | null; run: string | null;
};
export type StoryStep = { n: number; role: string; tool: string; state: string; line: string | null; note: string | null };
export type PlanStory = {
  id: string; kind: string; who: string; words_shown: boolean; actor: string; state: string; ask: string; question: string | null;
  reason: string | null; unread: number; writer: string; model: string | null; created_at: string; approved_at: string | null; updated_at: string;
  turned_back: { plan: unknown; reasons: string[] }[];
  calls: StoryCall[];
  steps: StoryStep[];
  version: { n: number; made_by: string; why: string | null; changes: number; change_lines: string[]; at: string } | null;
  job: { id: string; state: string; stage: string | null; stages_done: number; stages: number; started_at: string; finished_at: string | null;
    message: string | null } | null;
};

type Row = Record<string, string | number | boolean | null>;
export type Weekly = { since: string; guards: Row[]; costs: Row[]; plans: Row[]; refused: { reason: string; plans: number }[]; unchecked: Row[] };

export type Tone = "good" | "warn" | "bad" | "quiet";

/** Not a founder, or no such page: the API answers 404 and the page says only that there is nothing here. */
export class NotHere extends Error {}

/** A founder asked for a plan that is not in the records (its project was deleted since the feed was read): the story's panel says
 * so, and the rest of the page stays. */
export class PlanGone extends Error {}

/** The page was built with no address for the API, so no reading can be asked for. */
export const NO_ADDRESS = "The page was built without the API's address (NEXT_PUBLIC_ANISOTROPY_API_URL), so the activity cannot be read.";
/** The request got no answer at all: the network, or the API's address. */
export const NOT_REACHED = "The API could not be reached. Check the connection.";
/** What the API answers a founder who asks for a plan there is not; any other 404 is the route's own, which is all anyone else gets. */
const NO_SUCH_PLAN = "There is no such plan.";

const ACTOR = "studio";
const REFRESH_MS = 10_000;
export { REFRESH_MS };

function base(url: string): string { return url.replace(/\/+$/, ""); }

/** Whether a failure is a reading given up on purpose (the page was left, or the plan picked changed): it is nothing to show. */
export function givenUp(e: unknown): boolean {
  return typeof e === "object" && e !== null && (e as { name?: unknown }).name === "AbortError";
}

async function read<T>(apiBase: string, path: string, signal?: AbortSignal): Promise<T> {
  if (!apiBase.trim()) throw new Error(NO_ADDRESS);
  let response: Response;
  try {
    // Same-origin credentials: hosted, the page and /api share anisotropy.dev and the Access sign-in cookie goes with the call (ADR-0056).
    response = await fetch(`${base(apiBase)}${path}`, { headers: { "X-Anisotropy-Actor": ACTOR }, credentials: "same-origin", cache: "no-store", signal });
  } catch (e) {
    if (givenUp(e)) throw e;
    throw new Error(NOT_REACHED);  // the browser's own words for it differ by browser and say nothing a reader can use
  }
  if (response.status === 404) {
    const detail = await response.json().then((body) => (body as { detail?: unknown } | null)?.detail, () => undefined);
    throw detail === NO_SUCH_PLAN ? new PlanGone() : new NotHere();
  }
  if (!response.ok) throw new Error(`The API answered with an error (${response.status}), so this could not be read.`);
  return (await response.json()) as T;
}

/** What one read of the feed asks for: at most `limit` events, newest first; `before` a place (older ones), `since` a place (what is
 * after it) or `from` a place on (that place included). A place is an event's key, or a time with its offset. */
export type FeedAsk = { limit?: number; before?: string; since?: string; from?: string };
export type FeedReader = (ask: FeedAsk) => Promise<ActivityEvent[]>;

/** One read of the feed. The API keeps a read as a view of the page unless it has `since` or `from`, which only a refresh sends. */
export async function readActivity(apiBase: string, ask: FeedAsk = {}, signal?: AbortSignal): Promise<ActivityEvent[]> {
  const query = new URLSearchParams();
  if (ask.limit) query.set("limit", String(ask.limit));
  for (const name of ["before", "since", "from"] as const) {
    const place = ask[name];
    if (place) query.set(name, place);
  }
  const tail = query.toString();
  return (await read<{ events: ActivityEvent[] }>(apiBase, `/v1/oversight/activity${tail ? `?${tail}` : ""}`, signal)).events;
}

export function readPlanStory(apiBase: string, plan: string, signal?: AbortSignal): Promise<PlanStory> {
  return read<PlanStory>(apiBase, `/v1/oversight/plans/${encodeURIComponent(plan)}`, signal);
}

export function readWeekly(apiBase: string, signal?: AbortSignal): Promise<Weekly> {
  return read<Weekly>(apiBase, "/v1/oversight/weekly", signal);
}

// ------------------------------------------------------------------------------------------------------------------ the feed

/** The feed as the page holds it: its events, newest first, and its floor. The floor is the key of the oldest event shown while
 * there may be older ones in the records; null when the page holds the feed from its beginning. The page holds every event from
 * its floor on that was recorded when it last read, and "Show older" lowers the floor. */
export type Feed = { events: ActivityEvent[]; floor: string | null };

export const PAGE = 50;  // the first read's size, and each "Show older"
export const REFRESH_PAGE = 200;  // one read of a refresh: the most the API gives
export const SHOWN_MAX = 1000;  // new events grow the page to this many and no further; "Show older" goes past it, a page at a time
/** A place before every event: a refresh of a page that holds the whole feed reads from here. It is a `since`, so the API keeps no
 * view of it, however often an open page on an empty feed refreshes. */
export const BEGINNING = "1970-01-01T00:00:00+00:00";

const oldest = (events: ActivityEvent[]): string => events[events.length - 1].key;

/** The first read: the newest events, and whether there may be older ones. */
export async function firstPage(read: FeedReader): Promise<Feed> {
  const events = await read({ limit: PAGE });
  return { events, floor: events.length === PAGE ? oldest(events) : null };
}

/** The feed read again from its floor on, whole: page by page, each `before` the last event of the one before, until a page is not
 * full. It replaces what was shown, so nothing is missed whenever its row was written (a plan's first call is recorded when the
 * request ends, after calls that came later), however many new events there are and however many share one instant; an event whose
 * outcome changed shows the new one, and a plan since deleted goes. The page holds at most SHOWN_MAX events, or as many as it
 * already shows when "Show older" took it further: when there are more from the floor on, the newest that many are kept and the
 * floor rises to the oldest of them, so the page still holds everything from its floor on. */
export async function refreshed(read: FeedReader, feed: Feed): Promise<Feed> {
  const start: FeedAsk = feed.floor === null ? { since: BEGINNING } : { from: feed.floor };
  const most = Math.max(SHOWN_MAX, feed.events.length);
  let events: ActivityEvent[] = [];
  for (;;) {
    const limit = Math.min(REFRESH_PAGE, most - events.length);
    const page = await read({ limit, ...start, ...(events.length ? { before: oldest(events) } : {}) });
    events = events.concat(page);
    if (page.length < limit) return { events, floor: feed.floor };
    if (events.length >= most) return { events, floor: oldest(events) };
  }
}

/** The feed with the page of events before its floor added, each event once. With no floor there is nothing older to read. */
export async function withOlder(read: FeedReader, feed: Feed): Promise<Feed> {
  if (feed.floor === null) return feed;
  const page = await read({ limit: PAGE, before: feed.floor });
  const events = mergeNewer(page, feed.events);
  return { events, floor: page.length === PAGE ? oldest(page) : null };
}

export type Watch = {
  /** Read the feed: the first page when none is held yet (so a first read that failed is tried again), else a refresh. Skipped when
   * a read is under way. */
  refresh(): Promise<void>;
  /** Add the page before the floor. Skipped when one is already asked for, so two clicks add one page. */
  older(): Promise<void>;
  stop(): void;
};

/** The page's feed, read by one request at a time: a refresh and a "Show older" never overlap, so neither undoes the other and no
 * answer arrives out of turn. Each reading that succeeds goes to `on.feed` and each that fails to `on.error`; after `stop`, neither. */
export function watchFeed(read: FeedReader, on: { feed(feed: Feed): void; error(e: unknown): void }): Watch {
  let feed: Feed | null = null;
  let waiting = 0;
  let olderAsked = false;
  let stopped = false;
  let tail: Promise<void> = Promise.resolve();
  const run = (make: (now: Feed | null) => Promise<Feed>): Promise<void> => {
    waiting += 1;
    tail = tail.then(async () => {
      try {
        if (stopped) return;
        const next = await make(feed);
        if (stopped) return;
        feed = next;
        on.feed(next);
      } catch (e) {
        if (!stopped) on.error(e);
      } finally {
        waiting -= 1;
      }
    });
    return tail;
  };
  return {
    refresh: () => (waiting || stopped ? tail : run((now) => (now === null ? firstPage(read) : refreshed(read, now)))),
    older: () => {
      if (olderAsked || stopped || feed === null || feed.floor === null) return tail;
      olderAsked = true;
      return run((now) => (now === null ? firstPage(read) : withOlder(read, now))).then(() => { olderAsked = false; });
    },
    stop: () => { stopped = true; },
  };
}

/** What the poll needs of the page it runs on; the tests give it a clock and a tab of their own. */
export type PollEnv = {
  hidden(): boolean;
  /** Calls back each time the tab comes back into view; returns how to stop listening. */
  onShown(shown: () => void): () => void;
  later(run: () => void, ms: number): unknown;
  cancel(timer: unknown): void;
};

const browser: PollEnv = {
  hidden: () => document.hidden,
  onShown: (shown) => {
    const changed = () => { if (!document.hidden) shown(); };
    document.addEventListener("visibilitychange", changed);
    return () => document.removeEventListener("visibilitychange", changed);
  },
  later: (run, ms) => window.setTimeout(run, ms),
  cancel: (timer) => window.clearTimeout(timer as number),
};

/** Runs `task` now and again `ms` after each run ends, so two runs never overlap however slow one is. While the tab is hidden
 * nothing runs; when it is shown again the task runs at once. Returns how to stop. */
export function poll(task: () => Promise<unknown>, ms: number, env: PollEnv = browser): () => void {
  let timer: unknown = null;
  let running = false;
  let stopped = false;
  const tick = async () => {
    timer = null;
    if (stopped || running || env.hidden()) return;
    running = true;
    try { await task(); } catch { /* the task says what failed, to its own reader */ }
    running = false;
    if (!stopped) timer = env.later(() => void tick(), ms);
  };
  const unlisten = env.onShown(() => {
    if (timer !== null) { env.cancel(timer); timer = null; }
    void tick();
  });
  void tick();
  return () => {
    stopped = true;
    if (timer !== null) env.cancel(timer);
    unlisten();
  };
}

// --------------------------------------------------------------------------------------------------------------- the readings

const GOOD = new Set(["kept", "proposed", "approved", "running", "done"]);
const WARN = new Set(["question", "partly dropped", "capped", "unavailable", "stopped", "not used", "turned back"]);
const BAD = new Set(["refused", "set aside", "declined", "cut short"]);

/** How a row's outcome reads at a glance. A call answered by a model outside the checked list is flagged whatever its outcome. A
 * plan's call whose own part the records do not tell ("plan done") reads as its plan does. */
export function toneOf(event: Pick<ActivityEvent, "outcome" | "checked">): Tone {
  if (event.checked === false) return "bad";
  const outcome = event.outcome.startsWith("plan ") ? event.outcome.slice(5) : event.outcome;
  if (BAD.has(outcome)) return "bad";
  if (WARN.has(outcome)) return "warn";
  return GOOD.has(outcome) ? "good" : "quiet";
}

/** The newer events on top of the ones shown, each once, told apart by their keys (two calls of one plan can share an instant, a
 * run and a feature, and are still two). */
export function mergeNewer(shown: ActivityEvent[], newer: ActivityEvent[]): ActivityEvent[] {
  const seen = new Set(shown.map((e) => e.key));
  return [...newer.filter((e) => !seen.has(e.key)), ...shown];
}

/** US dollars the way the page prints them: cents for most calls, tenths of a cent for the small ones; a dash when not priced. */
export function money(usd: number | null): string {
  if (usd === null) return "–";
  return usd >= 0.1 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(3)}`;
}

/** A time in the viewer's own time zone: the hour and minute today, else the day too. */
export function clock(iso: string, now: Date = new Date()): string {
  const at = new Date(iso);
  const time = at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return at.toDateString() === now.toDateString() ? time : `${at.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${time}`;
}

/** Who a row is for, short: a founder by the name before the @, a customer by their tag, a robot or this machine as it is. */
export function whoShort(who: string): string {
  return who.includes("@") ? who.split("@")[0] : who;
}

export type StoryLine = { tone: Tone; head: string; detail?: string };

const STATE_LINE: Record<string, string> = {
  proposed: "Waiting for the engineer's approval",
  question: "Asked a question back instead of a plan",
  refused: "Refused: no plan the checks would pass",
  unavailable: "No model answered; the page read the sentence as before",
  capped: "Not asked: the day's planned requests were used",
};

/** A plan's story as lines, in the order it happened: the sentence, each answer the checks turned back, each call, what the plan came
 * to, the approval, the version it made, each step and the job. What a customer wrote is not in it (the API leaves it out). */
export function storyLines(story: PlanStory): StoryLine[] {
  const lines: StoryLine[] = [{ tone: "good", head: "Sentence read", detail: story.ask }];
  story.turned_back.forEach((t, i) => {
    lines.push({ tone: "warn", head: `Answer ${i + 1} turned back by the checks`, detail: t.reasons.join("; ") });
  });
  for (const c of story.calls) {
    const unchecked = c.checked === false ? ", a model outside the checked list" : "";
    // the call's own outcome: "turned back" when the checks turned its answer back, not the state its plan came to later
    lines.push({ tone: toneOf(c), head: `Model call: ${c.what}`,
      detail: `${c.model}${unchecked} · ${c.outcome} · ${c.seconds.toFixed(1)} s · ${c.input_tokens} in, ${c.output_tokens} out · ${money(c.cost_usd)}` });
  }
  const said = STATE_LINE[story.state];
  if (said) {
    const detail = story.state === "question" ? story.question ?? undefined : story.reason ?? undefined;
    lines.push({ tone: story.state === "proposed" ? "quiet" : story.state === "refused" ? "bad" : "warn", head: said, detail });
  }
  if (story.approved_at) lines.push({ tone: "good", head: `Approved by ${whoShort(story.who)}`, detail: clock(story.approved_at) });
  if (story.version) {
    lines.push({ tone: "good", head: `New version ${story.version.n}, made by ${story.version.made_by}`,
      detail: `${story.version.changes} change${story.version.changes === 1 ? "" : "s"}` });
  }
  if (story.approved_at) {
    for (const s of story.steps) {
      const tone: Tone = s.state === "done" ? "good" : s.state === "failed" ? "bad" : s.state === "running" ? "warn" : "quiet";
      lines.push({ tone, head: `${s.role}: ${s.line ?? s.tool}`, detail: [s.state, s.note].filter(Boolean).join(" · ") });
    }
  }
  if (story.job) {
    const ended = story.job.finished_at ? `ended ${clock(story.job.finished_at)}` : "still going";
    const tone: Tone = story.job.state === "done" ? "good" : story.job.state === "stopped" || story.job.state === "refused" ? "bad" : "warn";
    lines.push({ tone, head: `Run on the solver pool: ${story.job.state}`,
      detail: `${story.job.stages_done} of ${story.job.stages} stages · ${ended}` });
  }
  return lines;
}
