/** The founders' AI activity page (ADR-0145): what the API's oversight routes answer, how the page asks for it, and the pure readings the
 * page draws from it (a row's tone, a plan's story as lines, the money and the times). Read only: the page changes nothing and calls no
 * model. The API decides who may read it; anyone but a founder is answered 404, which the page shows as a page that is not there. */

export type ActivityEvent = {
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
  cost_usd: number | null; stop_reason: string | null; sent: string | null; run: string | null;
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

const ACTOR = "studio";
const REFRESH_MS = 10_000;
export { REFRESH_MS };

function base(url: string): string { return url.replace(/\/+$/, ""); }

async function read<T>(apiBase: string, path: string, signal?: AbortSignal): Promise<T> {
  // Same-origin credentials: hosted, the page and /api share anisotropy.dev and the Access sign-in cookie goes with the call (ADR-0056).
  const response = await fetch(`${base(apiBase)}${path}`, { headers: { "X-Anisotropy-Actor": ACTOR }, credentials: "same-origin", cache: "no-store", signal });
  if (response.status === 404) throw new NotHere();
  if (!response.ok) throw new Error(`The activity could not be read (${response.status}). Try again in a minute.`);
  return (await response.json()) as T;
}

/** The newest events; `before` pages back, `since` reads only what came after (the refresh, which the API does not keep as a view). */
export async function readActivity(apiBase: string, opts: { before?: string; since?: string; limit?: number } = {}, signal?: AbortSignal): Promise<ActivityEvent[]> {
  const query = new URLSearchParams();
  if (opts.limit) query.set("limit", String(opts.limit));
  if (opts.before) query.set("before", opts.before);
  if (opts.since) query.set("since", opts.since);
  const tail = query.toString();
  return (await read<{ events: ActivityEvent[] }>(apiBase, `/v1/oversight/activity${tail ? `?${tail}` : ""}`, signal)).events;
}

export function readPlanStory(apiBase: string, plan: string, signal?: AbortSignal): Promise<PlanStory> {
  return read<PlanStory>(apiBase, `/v1/oversight/plans/${encodeURIComponent(plan)}`, signal);
}

export function readWeekly(apiBase: string, signal?: AbortSignal): Promise<Weekly> {
  return read<Weekly>(apiBase, "/v1/oversight/weekly", signal);
}

// --------------------------------------------------------------------------------------------------------------- the readings

const GOOD = new Set(["kept", "proposed", "approved", "running", "done"]);
const WARN = new Set(["question", "partly dropped", "capped", "unavailable", "stopped", "not used"]);
const BAD = new Set(["refused", "set aside", "declined", "cut short"]);

/** How a row's outcome reads at a glance. A call answered by a model outside the checked list is flagged whatever its outcome. */
export function toneOf(event: Pick<ActivityEvent, "outcome" | "checked">): Tone {
  if (event.checked === false) return "bad";
  if (BAD.has(event.outcome)) return "bad";
  if (WARN.has(event.outcome)) return "warn";
  return GOOD.has(event.outcome) ? "good" : "quiet";
}

/** The newer events on top of the ones shown, each once (a refresh can overlap the last read by a moment). */
export function mergeNewer(shown: ActivityEvent[], newer: ActivityEvent[]): ActivityEvent[] {
  const key = (e: ActivityEvent) => `${e.kind}|${e.at}|${e.plan ?? ""}|${e.run ?? ""}|${e.what}`;
  const seen = new Set(shown.map(key));
  return [...newer.filter((e) => !seen.has(key(e))), ...shown];
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
    lines.push({ tone: c.checked === false ? "bad" : c.stop_reason === "refusal" ? "bad" : "good", head: `Model call: ${c.what}`,
      detail: `${c.model}${unchecked} · ${c.seconds.toFixed(1)} s · ${c.input_tokens} in, ${c.output_tokens} out · ${money(c.cost_usd)}` });
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
