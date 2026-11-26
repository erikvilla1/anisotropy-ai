/** What a run of the site check writes, in a form the founders' QA page will read later (ADR-0138): `results.json`, one file per run,
 * with `schema` naming its version. A new field may be added within a version; a field renamed or removed raises it. Everything in it
 * is scrubbed before it is written (`scrub.ts`). */
import type { CardPlan } from "./chat";
import type { Check } from "./grade";
import type { Mode } from "./plan";

export const SCHEMA = "anisotropy-site-check/1";

export type Verdict = "holds" | "weak" | "fails" | "not-asked";

/** One question as the run asked it, with what the page showed and how it was graded. */
export type QuestionResult = {
  id: string;
  feature: string;
  ask: string;
  /** The messages sent before it in the same conversation. */
  after: string[];
  kind: string;
  style: string;
  page: string;
  /** The way the bank expects it to be answered with a model reading, as on the site. */
  route: string;
  modelRead: boolean;
  /** The known gap the bank marks, if any: a failure there is expected and does not make the run fail. */
  gap: string | null;
  /** Numbers a yes-or-no question quotes that this result does not hold: the bank wrote them of its example's result (see `grade.ts`). */
  foreign: string[];
  asked: boolean;
  /** Why it was not asked, when it was not. */
  reason: string | null;
  /** What the chat showed; `interim`, the answer it showed first, when the page then worked and replaced it (a sweep, a solve). */
  answer: { heading: string; shown: string; folded: string; parts: string[]; applies: boolean; interim?: { heading: string; shown: string } } | null;
  /** A planner question's plan card as shown (ADR-0144, step 4), never approved: its stage and state, heading, steps, and reason or
   * question back. Absent for every other question, and in results written before it. */
  plan?: CardPlan | null;
  seconds: number | null;
  modelCalls: number;
  /** What the site's calls to the model cost for it, in dollars, as the site's answer said. */
  cost: number;
  checks: Check[];
  judge: { verdict: "holds" | "weak" | "fails"; criteria: number[]; why: string } | null;
  verdict: Verdict;
  /** The picture of the chat, when the answer did not hold: a file beside the report. */
  picture: string | null;
};

export type PageResult = { page: string; state: "set-up" | "failed" | "not-offered"; seconds: number | null; reason: string | null; picture: string | null };

export type RunResult = {
  schema: typeof SCHEMA;
  site: string;
  mode: Mode;
  started: string;
  finished: string;
  /** The commit the site's API answered with, when it said. */
  commit: string | null;
  /** The commit whose banks were asked, when the run was started for one (a deploy's run). */
  expected?: string | null;
  /** Why the run tells nothing, when it does not: the site ran another commit than the banks', or changed while the run asked. No issue
   * is opened, commented on or closed for it, and the questions that failed before are kept for the next run. */
  void: string | null;
  cap: number;
  spent: { site: number; judge: number; month: number };
  /** Why the run stopped asking the model's questions, when it did. */
  stopped: string | null;
  pages: PageResult[];
  questions: QuestionResult[];
  counts: Record<Verdict, number>;
  /** Whether the run found a failure that is not a known gap, or a page it could not set up: the founder is told. */
  failed: boolean;
  /** Questions that failed in an earlier run and were not asked again in this one (a quick run asks no model's question): the issue that
   * tells the founder stays open until each is asked again and holds. */
  unresolved: string[];
  /** What fails now and did not when the issue last heard (question ids, and `page:<name>` for a page not set up): only these are added
   * to an open issue, so a failure that stays is told once, not after every deploy. */
  newlyFailing: string[];
};

/** Whether two commits are the same, one of them perhaps shortened. */
export const sameCommit = (a: string | null | undefined, b: string | null | undefined): boolean =>
  !!a && !!b && (a.toLowerCase().startsWith(b.toLowerCase()) || b.toLowerCase().startsWith(a.toLowerCase()));

/** The verdict of a question from its fixed checks and its judge. */
export function verdictOf(asked: boolean, checks: readonly Check[], judge: QuestionResult["judge"]): Verdict {
  if (!asked) return "not-asked";
  if (checks.some((c) => c.level === "fails")) return "fails";
  if (judge?.verdict === "fails") return "fails";
  if (checks.length || judge?.verdict === "weak") return "weak";
  return "holds";
}

export function countOf(questions: readonly QuestionResult[]): Record<Verdict, number> {
  const out: Record<Verdict, number> = { holds: 0, weak: 0, fails: 0, "not-asked": 0 };
  for (const q of questions) out[q.verdict] += 1;
  return out;
}

/** Whether a run must tell the founder: a failure that no known gap explains, or a page that could not be set up. */
export function runFailed(questions: readonly QuestionResult[], pages: readonly PageResult[]): boolean {
  return questions.some((q) => q.verdict === "fails" && !q.gap) || pages.some((p) => p.state === "failed");
}
