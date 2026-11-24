/** How the founder hears of a site check that failed (ADR-0138): one GitHub issue, labelled `site-check` and assigned to him, so GitHub
 * emails him. A failed run opens it, or adds a comment to the one already open; the first run that passes closes it with a comment. A run
 * that passes with no issue open says nothing. The issue holds the counts, the questions that failed and why, and the link to the run: the
 * bank's questions are public already, and the answers stay on the run's page.
 *
 *   npx tsx scripts/site-check/issue.ts --results <out>/results.json --run-url <link>
 *
 * It needs GITHUB_TOKEN with issues: write and GITHUB_REPOSITORY; ISSUE_ASSIGNEE names who is assigned (the repository's owner). */
import { readFileSync } from "node:fs";
import type { RunResult } from "./record";
import { runSecrets, scrub } from "./scrub";

export const LABEL = "site-check";
export const TITLE = "Site check: answers on anisotropy.dev that do not hold";

/** The words of a failed run, for the issue or its comment. */
export function failureText(r: RunResult, runUrl: string): string {
  const failing = r.questions.filter((q) => q.verdict === "fails" && !q.gap);
  const pages = r.pages.filter((p) => p.state === "failed");
  const lines = [`The ${r.mode} run of ${r.started.slice(0, 16).replace("T", " ")} UTC${r.commit ? ` (the API on ${r.commit.slice(0, 7)})` : ""} found ` +
    `${failing.length} answer${failing.length === 1 ? "" : "s"} that fail${failing.length === 1 ? "s" : ""}${pages.length ? ` and ${pages.length} page${pages.length === 1 ? "" : "s"} it could not set up` : ""}.`, ""];
  for (const p of pages) lines.push(`- Page **${p.page}** not set up: ${p.reason ?? ""}`);
  for (const q of failing.slice(0, 25)) {
    const notes = q.checks.filter((c) => c.level === "fails").map((c) => c.note);
    if (q.judge?.verdict === "fails") notes.push(`judge: ${q.judge.why}`);
    lines.push(`- ${q.id} “${q.ask}” (${q.page}): ${notes.join("; ")}`);
  }
  if (failing.length > 25) lines.push(`- and ${failing.length - 25} more`);
  lines.push("", `The report, with a picture of each answer: ${runUrl}`, "", "This issue closes itself when a later run asks these questions again and they hold.");
  return lines.join("\n");
}

async function github(path: string, init: { method?: string; body?: unknown } = {}): Promise<unknown> {
  const answer = await fetch(`https://api.github.com/repos/${process.env.GITHUB_REPOSITORY}${path}`, {
    method: init.method ?? "GET",
    headers: { Authorization: `Bearer ${process.env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (!answer.ok) throw new Error(`GitHub answered ${answer.status} to ${init.method ?? "GET"} ${path}`);
  return answer.status === 204 ? null : answer.json();
}

async function main(): Promise<number> {
  const argv = process.argv.slice(2);
  const get = (name: string) => { const i = argv.indexOf(`--${name}`); return i >= 0 ? argv[i + 1] ?? "" : ""; };
  const result: RunResult = JSON.parse(readFileSync(get("results"), "utf8"));
  const runUrl = get("run-url");
  if (!process.env.GITHUB_TOKEN || !process.env.GITHUB_REPOSITORY) {
    console.log("No GITHUB_TOKEN or GITHUB_REPOSITORY: no issue is opened or closed.");
    return 0;
  }
  const secrets = runSecrets();
  const open = (await github(`/issues?state=open&labels=${LABEL}&per_page=5`)) as { number: number }[];
  const current = open[0]?.number;
  if (result.failed) {
    const text = scrub(failureText(result, runUrl), secrets);
    if (current) {
      await github(`/issues/${current}/comments`, { method: "POST", body: { body: text } });
      console.log(`Added the run's failures to issue #${current}.`);
    } else {
      const assignee = process.env.ISSUE_ASSIGNEE?.trim();
      const made = (await github("/issues", { method: "POST", body: { title: TITLE, body: text, labels: [LABEL], ...(assignee ? { assignees: [assignee] } : {}) } })) as { number: number };
      console.log(`Opened issue #${made.number}.`);
    }
  } else if (current && result.unresolved.length) {
    console.log(`Issue #${current} stays open: ${result.unresolved.length} questions that failed before were not asked in this run.`);
  } else if (current) {
    await github(`/issues/${current}/comments`, { method: "POST", body: { body: `The ${result.mode} run passed: every answer that failed before now holds or is a known gap. ${runUrl}` } });
    await github(`/issues/${current}`, { method: "PATCH", body: { state: "closed", state_reason: "completed" } });
    console.log(`Closed issue #${current}.`);
  }
  return 0;
}

if (process.argv[1]?.endsWith("issue.ts")) main().then((code) => process.exit(code), (error) => { console.error(error instanceof Error ? error.message : error); process.exit(1); });
