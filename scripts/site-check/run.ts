/** The site check's robot (ADR-0138): it opens the live site in a real browser as a customer would, brings each page to the state a bank
 * asks its questions on, types each question into the chat, and reads the answer as it is shown. It writes what it saw for the judge
 * (`scripts/site-check-judge.py`) and the report (`report.ts`), and nothing else:
 *
 *   npx tsx scripts/site-check/run.ts --site https://anisotropy.dev --mode quick|full [--features a,b] [--cap 1] [--store dir] [--work dir]
 *   npx tsx scripts/site-check/run.ts --dry-run --mode full      says what a run would ask, and opens no browser
 *
 * Behind Cloudflare Access it signs in with the service token in CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET, the deploy check's.
 * What keeps it safe: the token's two headers go on the site's own requests only, never to the bucket or anywhere else; the browser
 * records no trace, video, network log or storage, which would hold the token or the session cookie; the API's answers are read for
 * their numbers in memory and never written; every text written is scrubbed (`scrub.ts`); the requests are labelled with the actor
 * `test`, as the deploy check's are, so its runs and model calls are told from people's. */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { chromium, type BrowserContext, type Page, type Response } from "@playwright/test";
import { Budget, headerCost, modelSlots, runCap, type Entry } from "./budget";
import { ask, chatPane, pageText, type Asked } from "./chat";
import { fixedChecks } from "./grade";
import { NumberPool, untraced } from "./numbers";
import { setUp, stillOn } from "./pages";
import { moves, NOT_OFFERED, plan, type Mode, type Planned } from "./plan";
import type { PageResult, QuestionResult } from "./record";
import { runSecrets, scrubbed } from "./scrub";

type Args = { site: string; mode: Mode; features: string[]; cap: number; store: string; work: string; dryRun: boolean };

function args(argv: string[]): Args {
  const get = (name: string, fallback: string) => { const i = argv.indexOf(`--${name}`); return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : fallback; };
  const mode = get("mode", "quick");
  if (mode !== "quick" && mode !== "full") throw new Error(`--mode is quick or full, not ${mode}`);
  const cap = Number(get("cap", "1"));
  if (!Number.isFinite(cap) || cap < 0) throw new Error(`--cap is dollars, not ${get("cap", "")}`);
  return { site: get("site", "https://anisotropy.dev").replace(/\/$/, ""), mode, features: get("features", "").split(",").filter((f) => f.trim()), cap,
    store: get("store", ".local/site-check/store"), work: get("work", ".local/site-check/work"), dryRun: argv.includes("--dry-run") };
}

/** The bank's model questions, the reader paths the page sends them to: a call there costs, whether or not the answer says so. */
const MODEL_PATHS = /\/v1\/workspace\/(proposals|result-questions|result-answers|questions)$/;
const ANSWER_LIMIT = { page: 45_000, model: 120_000 };

/** A context that reaches the site through Access: the token on the site's own requests, a job's file fetched from the bucket's signed
 * link as a browser would (without the token), the actor relabelled `test`. Nothing is recorded. */
async function context(browser: Awaited<ReturnType<typeof chromium.launch>>, site: string): Promise<BrowserContext> {
  const ctx = await browser.newContext({ baseURL: site, viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const id = process.env.CF_ACCESS_CLIENT_ID?.trim(), secret = process.env.CF_ACCESS_CLIENT_SECRET?.trim();
  const origin = new URL(site).origin;
  const FILE = /\/v1\/coupon-jobs\/[^/]+\/files\/[^/]+$/;
  await ctx.route((url) => url.origin === origin, async (route) => {
    const sent = route.request().headers();
    const headers: Record<string, string> = { ...sent, ...(id && secret ? { "CF-Access-Client-Id": id, "CF-Access-Client-Secret": secret } : {}) };
    if (sent["x-anisotropy-actor"]) headers["x-anisotropy-actor"] = "test";
    if (!FILE.test(new URL(route.request().url()).pathname)) return route.continue({ headers });
    const answer = await route.fetch({ headers, maxRedirects: 0 });
    const link = answer.headers()["location"];
    if (answer.status() !== 307 || !link) return route.fulfill({ response: answer });
    return route.fulfill({ response: await ctx.request.get(link, { headers: { Origin: origin } }) });
  });
  return ctx;
}

/** What the site's API answered with while a question was asked: its numbers, its calls to the model and what they cost. */
class Listening {
  pool = new NumberPool();
  calls = 0;
  dollars = 0;
  errors: string[] = [];

  constructor(private readonly origin: string) {}

  reset(): void {
    this.calls = 0;
    this.dollars = 0;
    this.errors = [];
  }

  async heard(response: Response): Promise<void> {
    const url = new URL(response.url());
    const json = (response.headers()["content-type"] ?? "").includes("json");
    if (url.origin === this.origin && MODEL_PATHS.test(url.pathname) && response.request().method() === "POST") {
      const cost = headerCost(response.headers()["x-anisotropy-model-cost"], 1);
      this.calls += cost.calls;
      this.dollars += cost.dollars;
    }
    if (!json || response.status() >= 400) return;
    try {
      this.pool.addJson(await response.json()); // read for its numbers, in memory only
    } catch { /* a body already gone, or not JSON after all */ }
  }
}

function blankResult(p: Planned): QuestionResult {
  const q = p.question;
  return { id: p.id, feature: p.feature, ask: q.ask, after: q.after ?? [], kind: q.kind, style: q.style, page: q.page, route: q.route, modelRead: p.modelRead,
    gap: q.gap ?? null, foreign: [], asked: false, reason: null, answer: null, seconds: null, modelCalls: 0, cost: 0, checks: [], judge: null, verdict: "not-asked", picture: null };
}

async function main(): Promise<number> {
  if (process.argv.includes("--help") || process.argv.includes("-h")) {
    console.log("npx tsx scripts/site-check/run.ts --site <url> --mode quick|full [--features a,b] [--cap dollars] [--store dir] [--work dir] [--dry-run]");
    return 0;
  }
  const a = args(process.argv.slice(2));
  const started = new Date();
  const ledgerFile = join(a.store, "ledger.json");
  const ledger: Entry[] = existsSync(ledgerFile) ? JSON.parse(readFileSync(ledgerFile, "utf8")) : [];
  const cap = runCap(a.cap, ledger, started);
  const turnsFile = join(a.store, "last-asked.json");
  const lastAsked: Record<string, string> = existsSync(turnsFile) ? JSON.parse(readFileSync(turnsFile, "utf8")) : {};
  const { asked: planned, skipped } = plan(a.mode, a.features, undefined, { slots: modelSlots(cap, ledger), lastAsked });
  const models = planned.filter((p) => p.modelRead).length;
  console.log(`${planned.length} questions to ask (${models} read by the site's model), ${skipped.length} left out; this run may spend $${cap.toFixed(2)}.`);
  if (a.dryRun) {
    const byPage = new Map<string, number>();
    for (const p of planned) byPage.set(p.question.page, (byPage.get(p.question.page) ?? 0) + 1);
    for (const [page, n] of byPage) console.log(`  ${page}: ${n}`);
    for (const s of [...new Set(skipped.map((s) => s.reason))]) console.log(`  left out, ${skipped.filter((x) => x.reason === s).length}: ${s}`);
    return 0;
  }
  mkdirSync(join(a.work, "pictures"), { recursive: true });
  const secrets = runSecrets();
  const budget = new Budget(cap, planned.length);
  const results: QuestionResult[] = skipped.map((s) => ({ ...blankResult({ id: s.id, feature: s.feature, question: s.question, modelRead: false }), reason: s.reason }));
  const pages: PageResult[] = Object.entries(NOT_OFFERED).filter(([page]) => skipped.some((s) => s.page === page))
    .map(([page, reason]) => ({ page, state: "not-offered", seconds: null, reason: reason ?? null, picture: null }));
  let stopped: string | null = null;
  let commit: string | null = null;

  const browser = await chromium.launch();
  const origin = new URL(a.site).origin;
  try {
    const groups = new Map<string, Planned[]>();
    for (const p of planned) groups.set(p.question.page, [...(groups.get(p.question.page) ?? []), p]);
    for (const [which, questions] of groups) {
      let ctx: BrowserContext | null = null;
      let page: Page | null = null;
      const listening = new Listening(origin);
      const pageErrors: string[] = [];
      const open = async (): Promise<boolean> => {
        await ctx?.close().catch(() => undefined);
        ctx = await context(browser, a.site);
        page = await ctx.newPage();
        page.on("response", (r) => void listening.heard(r));
        page.on("pageerror", (e) => pageErrors.push(e.message));
        const t0 = Date.now();
        try {
          await setUp(page, which as never);
          if (commit === null) {
            const version = await ctx.request.get(`${a.site}/api/version`).catch(() => null);
            commit = version?.ok() ? ((await version.json()) as { git_commit?: string }).git_commit ?? null : null;
          }
          listening.pool.addText(await pageText(page));
          if (!pages.some((x) => x.page === which)) pages.push({ page: which, state: "set-up", seconds: (Date.now() - t0) / 1000, reason: null, picture: null });
          return true;
        } catch (error) {
          const picture = join(a.work, "pictures", `page-${which}.jpg`);
          await page.screenshot({ path: picture, type: "jpeg", quality: 70 }).catch(() => undefined);
          const reason = (error instanceof Error ? error.message : String(error)).split("\n").slice(0, 3).join(" ");
          const kept = pages.find((x) => x.page === which);
          if (kept) Object.assign(kept, { state: "failed", reason, picture: `page-${which}.jpg` });
          else pages.push({ page: which, state: "failed", seconds: (Date.now() - t0) / 1000, reason, picture: `page-${which}.jpg` });
          console.log(`The ${which} page could not be set up: ${reason}`);
          return false;
        }
      };
      let ready = await open();
      let previous: string | undefined;
      for (const p of questions) {
        const result = blankResult(p);
        results.push(result);
        if (!ready) { result.reason = `the ${which} page could not be set up`; continue; }
        if (p.modelRead && !budget.fits()) {
          stopped ??= `the run's cap of $${cap.toFixed(2)} was near: $${budget.site.toFixed(2)} spent on the site's model, the judge's share kept back`;
          result.reason = "left for the next run: the run's cap was reached";
          continue;
        }
        if (!(await stillOn(page!, which as never))) ready = await open();
        if (!ready) { result.reason = `the ${which} page could not be set up again`; continue; }
        const q = p.question;
        const words = [q.ask, ...(q.after ?? [])].join("\n");
        const own = new NumberPool();
        own.addText(words);
        listening.reset();
        pageErrors.length = 0;
        let seen: Asked;
        try {
          previous = undefined;
          for (const earlier of q.after ?? []) previous = (await ask(page!, earlier, ANSWER_LIMIT.model)).heading;
          seen = await ask(page!, q.ask, p.modelRead ? ANSWER_LIMIT.model : ANSWER_LIMIT.page);
        } catch (error) {
          result.reason = `the chat could not be used: ${error instanceof Error ? error.message.split("\n")[0] : String(error)}`;
          ready = await open();
          continue;
        }
        result.asked = true;
        result.answer = { heading: seen.heading, shown: seen.shown, folded: seen.folded, parts: seen.parts, applies: seen.applies,
          ...(seen.interim ? { interim: { heading: seen.interim.heading, shown: seen.interim.shown } } : {}) };
        result.seconds = Math.round(seen.seconds * 10) / 10;
        result.modelCalls = listening.calls;
        result.cost = listening.dollars;
        if (listening.calls) budget.add(listening.dollars);
        const pane = await chatPane(page!);
        const picture = `${p.id.replace(/[^\w-]/g, "_")}.jpg`;
        if (pane && await pane.screenshot({ path: join(a.work, "pictures", picture), type: "jpeg", quality: 70 }).then(() => true, () => false)) result.picture = picture;
        listening.pool.addText(await pageText(page!).catch(() => ""));
        // a yes-or-no question that quotes a result states the bank's example's numbers: where the answer gives others, "No" may be right.
        // They are held against the answer's own numbers, not the whole pool, where some value of thousands lies near any number.
        const answered = new NumberPool();
        answered.addText([seen.heading, seen.shown, seen.folded].join("\n"));
        result.foreign = q.kind === "yes-no" ? untraced(words, answered) : [];
        result.checks = fixedChecks(q, { ...seen, modelCalls: listening.calls, errors: [...pageErrors], before: previous, foreign: result.foreign },
          [listening.pool, own], p.modelRead);
        console.log(`${p.id} ${result.checks.length ? result.checks.map((c) => `${c.level}: ${c.note}`).join("; ") : "passes the fixed checks"}${q.gap ? " (a known gap)" : ""} (${result.seconds} s)`);
        if (moves(q) || seen.parts.includes("opened-page")) ready = await open();
      }
      await (ctx as BrowserContext | null)?.close().catch(() => undefined);
    }
  } finally {
    await browser.close();
  }
  const run = { site: a.site, mode: a.mode, started: started.toISOString(), finished: new Date().toISOString(), commit, cap, siteSpent: budget.site, stopped };
  writeFileSync(join(a.work, "asked.json"), JSON.stringify(scrubbed({ run, pages, questions: results }, secrets), null, 1));
  console.log(`Asked ${results.filter((r) => r.asked).length}; the site's model cost $${budget.site.toFixed(3)}.`);
  return 0;
}

main().then((code) => process.exit(code), (error) => { console.error(error instanceof Error ? error.message : error); process.exit(2); });
