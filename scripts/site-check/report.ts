/** The site check's report (ADR-0138): what the robot read (`run.ts`) and the judge's grades (`site-check-judge.py`) joined into one
 * verdict per question, written three ways: `results.json` for the founders' QA page to read later, `report.md` for the run's page on
 * GitHub, and `report.html`, a page that holds a picture of the chat for each answer that did not hold. It also keeps the run's spend
 * in the ledger and the time each question was asked, both in the store carried to the next run.
 *
 *   npx tsx scripts/site-check/report.ts --work <work> --store <store> --out <out> [--run-url <link to the run>]
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { monthSpent, MONTH_CAP, type Entry } from "./budget";
import { countOf, runFailed, SCHEMA, verdictOf, type PageResult, type QuestionResult, type RunResult, type Verdict } from "./record";
import { runSecrets, scrub, scrubbed } from "./scrub";

type Asked = { run: { site: string; mode: "quick" | "full"; started: string; finished: string; commit: string | null; cap: number; siteSpent: number; stopped: string | null };
  pages: PageResult[]; questions: QuestionResult[] };
type Judged = { grades: Record<string, NonNullable<QuestionResult["judge"]>>; spent: number; stopped: string | null };

const money = (dollars: number) => `$${dollars.toFixed(2)}`;
const SHOWN_IN_REPORT = 300;

/** The run's result, from what the robot read and what the judge graded. */
export function combine(asked: Asked, judged: Judged, ledger: readonly Entry[], now: Date, failingBefore: readonly string[] = []): RunResult {
  const questions = asked.questions.map((q) => {
    const judge = judged.grades[q.id] ?? null;
    return { ...q, judge, verdict: verdictOf(q.asked, q.checks, judge) };
  }).sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));
  const spent = { site: asked.run.siteSpent, judge: judged.spent, month: monthSpent(ledger, now) + asked.run.siteSpent + judged.spent };
  const stopped = [asked.run.stopped, judged.stopped].filter(Boolean).join("; ") || null;
  const askedNow = new Set(questions.filter((q) => q.asked).map((q) => q.id));
  return { schema: SCHEMA, site: asked.run.site, mode: asked.run.mode, started: asked.run.started, finished: now.toISOString(), commit: asked.run.commit,
    cap: asked.run.cap, spent, stopped, pages: asked.pages, questions, counts: countOf(questions), failed: runFailed(questions, asked.pages),
    unresolved: failingBefore.filter((id) => !askedNow.has(id)) };
}

/** The questions that fail now and are no known gap, with those that failed before and were not asked again: the next run's `failingBefore`. */
export function stillFailing(r: RunResult): string[] {
  return [...new Set([...r.questions.filter((q) => q.verdict === "fails" && !q.gap).map((q) => q.id), ...r.unresolved])].sort();
}

const one = (text: string, length = SHOWN_IN_REPORT) => { const flat = text.replace(/\s+/g, " ").trim(); return flat.length > length ? `${flat.slice(0, length - 1)}…` : flat; };

/** Why a question did not hold, in one line: its failed checks, then the judge's reason. */
export function why(q: QuestionResult): string {
  const notes = q.checks.filter((c) => q.verdict !== "fails" || c.level === "fails").map((c) => c.criterion ? `${c.note} (criterion ${c.criterion})` : c.note);
  if (q.judge && q.judge.verdict !== "holds") notes.push(`judge: ${q.judge.why}${q.judge.criteria.length ? ` (criteria ${q.judge.criteria.join(", ")})` : ""}`);
  return notes.join("; ");
}

export function markdown(r: RunResult, runUrl: string | null): string {
  const asked = r.questions.filter((q) => q.asked);
  const lines = [`# Site check, ${r.mode} run, ${r.started.slice(0, 16).replace("T", " ")} UTC`, "",
    `${r.site}${r.commit ? `, the API on ${r.commit.slice(0, 7)}` : ""}. Asked ${asked.length}: ${r.counts.holds} hold, ${r.counts.weak} weak, ${r.counts.fails} fail` +
    `${r.questions.some((q) => q.verdict === "fails" && q.gap) ? ` (${r.questions.filter((q) => q.verdict === "fails" && q.gap).length} of them known gaps)` : ""}; ` +
    `${r.counts["not-asked"]} not asked.`, "",
    `Spent ${money(r.spent.site + r.spent.judge)} of ${money(r.cap)} (the site's model ${money(r.spent.site)}, the judge ${money(r.spent.judge)}); this month ${money(r.spent.month)} of ${money(MONTH_CAP)}.` +
    (r.stopped ? ` Stopped early: ${r.stopped}.` : ""), ""];
  if (r.unresolved.length) lines.push(`Failed in an earlier run and not asked in this one: ${r.unresolved.join(", ")}.`, "");
  if (runUrl) lines.push(`The report with a picture of each answer that did not hold: the run's "site-check-report" file, ${runUrl}`, "");
  lines.push("| Feature | Asked | Holds | Weak | Fails | Not asked |", "| --- | ---: | ---: | ---: | ---: | ---: |");
  for (const feature of [...new Set(r.questions.map((q) => q.feature))].sort()) {
    const mine = r.questions.filter((q) => q.feature === feature);
    const n = (v: Verdict) => mine.filter((q) => q.verdict === v).length;
    lines.push(`| ${feature} | ${mine.filter((q) => q.asked).length} | ${n("holds")} | ${n("weak")} | ${n("fails")} | ${n("not-asked")} |`);
  }
  const failedPages = r.pages.filter((p) => p.state === "failed");
  if (failedPages.length) {
    lines.push("", "## Pages that could not be set up", "");
    for (const p of failedPages) lines.push(`- **${p.page}**: ${p.reason}`);
  }
  for (const [title, verdict] of [["What fails", "fails"], ["What is weak", "weak"]] as const) {
    const mine = r.questions.filter((q) => q.verdict === verdict);
    if (!mine.length) continue;
    lines.push("", `## ${title}`, "");
    for (const q of mine) {
      const shown = q.answer ? one([q.answer.heading, q.answer.shown].filter(Boolean).join(" · ")) : "";
      lines.push(`- ${q.id} “${q.ask}” (${q.page}${q.gap ? `; known gap: ${q.gap}` : ""}): ${why(q)}.${shown ? ` Shown: ${shown}` : ""}`);
    }
  }
  const reasons = new Map<string, number>();
  for (const q of r.questions.filter((q) => !q.asked)) reasons.set(q.reason ?? "not asked", (reasons.get(q.reason ?? "not asked") ?? 0) + 1);
  if (reasons.size) {
    lines.push("", "## Not asked", "");
    for (const [reason, n] of [...reasons].sort((a, b) => b[1] - a[1])) lines.push(`- ${n}: ${reason}`);
  }
  return lines.join("\n") + "\n";
}

const esc = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** The report as a page of its own: the counts, then each answer that did not hold with its picture beside it. */
export function html(r: RunResult, pictures: (name: string) => string | null): string {
  const asked = r.questions.filter((q) => q.asked);
  const rows = [...new Set(r.questions.map((q) => q.feature))].sort().map((feature) => {
    const mine = r.questions.filter((q) => q.feature === feature);
    const n = (v: Verdict) => mine.filter((q) => q.verdict === v).length;
    return `<tr><th>${esc(feature)}</th><td>${mine.filter((q) => q.asked).length}</td><td>${n("holds")}</td><td>${n("weak")}</td><td class="${n("fails") ? "bad" : ""}">${n("fails")}</td><td>${n("not-asked")}</td></tr>`;
  }).join("");
  const cards = r.questions.filter((q) => q.verdict === "fails" || q.verdict === "weak").map((q) => {
    const picture = q.picture ? pictures(q.picture) : null;
    return `<article class="${q.verdict}"><header><span class="tag">${q.verdict}${q.gap ? " · known gap" : ""}</span> <code>${esc(q.id)}</code> on ${esc(q.page)}</header>
<h3>“${esc(q.ask)}”</h3>${q.after.length ? `<p class="muted">After: ${q.after.map((m) => `“${esc(m)}”`).join(", ")}</p>` : ""}
<p>${esc(why(q))}</p>${q.answer ? `<details><summary>What the chat showed</summary><pre>${esc([q.answer.heading, q.answer.shown, q.answer.folded].filter(Boolean).join("\n\n"))}</pre></details>` : ""}
${picture ? `<img alt="The chat after the question" src="${picture}">` : ""}</article>`;
  }).join("\n");
  const failedPages = r.pages.filter((p) => p.state === "failed").map((p) => {
    const picture = p.picture ? pictures(p.picture) : null;
    return `<article class="fails"><header><span class="tag">page not set up</span> ${esc(p.page)}</header><p>${esc(p.reason ?? "")}</p>${picture ? `<img alt="The page when it stopped" src="${picture}">` : ""}</article>`;
  }).join("\n");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Site check report</title><style>
:root{--bg:#fff;--fg:#1b1d1c;--muted:#5d625f;--line:#dfe2e0;--bad:#b3261e;--weak:#8a5a00;--card:#f6f7f6}
@media (prefers-color-scheme:dark){:root{--bg:#121413;--fg:#e8eae9;--muted:#a2a8a5;--line:#2c302e;--bad:#ff8a80;--weak:#f2c46d;--card:#1b1e1c}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}h3{font-size:15px;margin:6px 0}
.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child{text-align:left}td.bad{color:var(--bad);font-weight:600}article{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:12px 0}
article.fails{border-left:4px solid var(--bad)}article.weak{border-left:4px solid var(--weak)}.tag{font-weight:600;text-transform:uppercase;font-size:12px}
article.fails .tag{color:var(--bad)}article.weak .tag{color:var(--weak)}img{max-width:100%;border:1px solid var(--line);border-radius:6px;margin-top:8px}
pre{white-space:pre-wrap;font-size:13px}code{font-size:13px}.wrap{overflow-x:auto}</style></head><body><main>
<h1>Site check, ${esc(r.mode)} run</h1><p class="muted">${esc(r.started.slice(0, 16).replace("T", " "))} UTC · ${esc(r.site)}${r.commit ? ` · API ${esc(r.commit.slice(0, 7))}` : ""}</p>
<p>Asked ${asked.length}: <strong>${r.counts.holds}</strong> hold, <strong>${r.counts.weak}</strong> weak, <strong>${r.counts.fails}</strong> fail; ${r.counts["not-asked"]} not asked.
Spent ${money(r.spent.site + r.spent.judge)} of ${money(r.cap)}; this month ${money(r.spent.month)} of ${money(MONTH_CAP)}.${r.stopped ? ` Stopped early: ${esc(r.stopped)}.` : ""}</p>
<div class="wrap"><table><thead><tr><th>Feature</th><th>Asked</th><th>Holds</th><th>Weak</th><th>Fails</th><th>Not asked</th></tr></thead><tbody>${rows}</tbody></table></div>
${failedPages ? `<h2>Pages that could not be set up</h2>${failedPages}` : ""}
${cards ? `<h2>Answers that did not hold</h2>${cards}` : "<h2>Every answer asked held</h2>"}
</main></body></html>
`;
}

function main(): number {
  const argv = process.argv.slice(2);
  const get = (name: string) => { const i = argv.indexOf(`--${name}`); return i >= 0 ? argv[i + 1] ?? null : null; };
  const work = get("work") ?? ".local/site-check/work", store = get("store") ?? ".local/site-check/store", out = get("out") ?? ".local/site-check/report";
  const runUrl = get("run-url");
  const secrets = runSecrets();
  const now = new Date();
  const asked: Asked = JSON.parse(readFileSync(join(work, "asked.json"), "utf8"));
  const judgedFile = join(work, "judged.json");
  const judged: Judged = existsSync(judgedFile) ? JSON.parse(readFileSync(judgedFile, "utf8")) : { grades: {}, spent: 0, stopped: "the judge did not run" };
  const ledgerFile = join(store, "ledger.json");
  const ledger: Entry[] = existsSync(ledgerFile) ? JSON.parse(readFileSync(ledgerFile, "utf8")) : [];
  const failingFile = join(store, "failing.json");
  const failingBefore: string[] = existsSync(failingFile) ? JSON.parse(readFileSync(failingFile, "utf8")) : [];
  const result = scrubbed(combine(asked, judged, ledger, now, failingBefore), secrets);
  mkdirSync(join(out, "pictures"), { recursive: true });
  for (const q of result.questions) { // a picture goes with the report only for an answer that did not hold
    if (q.picture && (q.verdict === "fails" || q.verdict === "weak") && existsSync(join(work, "pictures", q.picture))) copyFileSync(join(work, "pictures", q.picture), join(out, "pictures", q.picture));
    else q.picture = null;
  }
  for (const p of result.pages) if (p.picture && existsSync(join(work, "pictures", p.picture))) copyFileSync(join(work, "pictures", p.picture), join(out, "pictures", p.picture));
  const embed = (name: string) => existsSync(join(out, "pictures", name)) ? `data:image/jpeg;base64,${readFileSync(join(out, "pictures", name)).toString("base64")}` : null;
  writeFileSync(join(out, "results.json"), JSON.stringify(result, null, 1));
  writeFileSync(join(out, "report.md"), scrub(markdown(result, runUrl), secrets));
  writeFileSync(join(out, "report.html"), html(result, embed));
  mkdirSync(store, { recursive: true });
  const models = result.questions.filter((q) => q.asked && q.modelRead).length;
  writeFileSync(ledgerFile, JSON.stringify([...ledger, { at: now.toISOString(), mode: result.mode, site: result.spent.site, judge: result.spent.judge, models }].slice(-400), null, 1));
  const turnsFile = join(store, "last-asked.json");
  const turns: Record<string, string> = existsSync(turnsFile) ? JSON.parse(readFileSync(turnsFile, "utf8")) : {};
  for (const q of result.questions) if (q.asked) turns[q.id] = now.toISOString();
  writeFileSync(turnsFile, JSON.stringify(turns, null, 1));
  writeFileSync(failingFile, JSON.stringify(stillFailing(result), null, 1));
  console.log(markdown(result, runUrl));
  writeFileSync(join(out, "failed"), result.failed ? "yes\n" : "no\n");
  return 0;
}

if (process.argv[1]?.endsWith("report.ts")) process.exit(main());
