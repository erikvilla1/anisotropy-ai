/**
 * A wing's and a repair's plan as the page shows it while it runs (ADR-0144, step 5): the server makes the changes and carries the runs at
 * the approval (on a wing the hand calculation and the start of the finite element check; on a repair the sweep, its pick, the solve and
 * the bond); the page follows a wing's check and gives each answer, and reports them. Each step's state is read from the plan the approval
 * answered, the check as last read and the answers given. Pure, so `tests/plan-kinds.test.ts` holds it.
 */
import { bannedIn, customerText, sectionProse } from "./studio-copy";
import { readRepairBond, readRepairSolve, readRepairSweep, readWingAnswer, readWingFeCheck, type Plan, type PlanRun, type ReferenceSection,
  type StepState } from "./studio-api";
import type { StepView } from "./plan-steps";
import { readRepairAsk, repairAnswer, type RepairHeld, type RepairSaid, type RepairSweepAnswer, type SweepCheck } from "./repair-chat";
import { readWingAsk, wingAnswer, type WingSaid } from "./wing-chat";
import { kindOf, type RepairBond, type RepairSolve } from "./repair";
import { answerWords, FE_STOPPED, feProgress, feWords, type WingAnswer, type WingDescription, type WingFeCheck, type WingReport } from "./wing";

export type PlannedKind = "wing" | "repair";
/** The steps the page reports, by kind: on a wing its check as the job ends, and each answer; on a repair each answer. */
export const REPORTED: Record<PlannedKind, ReadonlySet<string>> = { wing: new Set(["check", "answer"]), repair: new Set(["answer"]) };
const ENDED = new Set<StepState>(["done", "failed", "skipped"]);
const capital = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

/** An answer step the page gives: under way, or given in words (`heading` first, the rest under Details), or not given and why. */
export type PlanAnswer = { state: "running" | "done" | "failed"; heading: string | null; more: string[]; note: string | null };
/** What the page holds of a wing's or a repair's plan as it runs. */
export type KindProgress = {
  approved: boolean;
  /** a wing's check as last read, once the approval started one */
  check: WingFeCheck | null;
  /** the hand calculation the approval carried, for its step's line */
  analyze?: WingReport | null;
  /** each answer the page gives, by its step's number */
  answers: Record<number, PlanAnswer>;
};

/** Where a wing's or a repair's plan stands on the page, kept in the chat's entry so the card survives the chat re-rendering it: the plan,
 * its stage as the coupon's card has it, the words of an approval that did not go through, when the approval was sent (the waiting
 * state counts from it), the runs it answered with, a wing's check as last read, what the approval left (the wing's key, or the
 * repair), each answer the page gave and what was reported of each step. */
export type KindFlow = {
  plan: Plan;
  stage: "proposed" | "approving" | "approved" | "stale" | "edited";
  problem: string | null;
  since: number | null;
  runs: PlanRun[];
  check: WingFeCheck | null;
  left: string | null;
  answers: Record<number, PlanAnswer>;
  reported: Record<number, StepState>;
};

export const newKindFlow = (plan: Plan): KindFlow => ({ plan, stage: "proposed", problem: null, since: null, runs: [], check: null, left: null, answers: {},
  reported: {} });

/** Every step with its state as the plan goes, in its order: the server's for the steps it carried; a wing's check as the job stands;
 * each answer as the page gives it, skipped once a step before it failed or was skipped. */
export function kindViews(plan: Plan, p: KindProgress): StepView[] {
  let stopped = false;
  return plan.steps.map((step) => {
    let state: StepState = step.state, note = step.note;
    if (p.approved && !ENDED.has(step.state) && step.tool === "check") {
      const c = p.check;
      if (!c || c.state === "queued" || c.state === "running") { state = "running"; note = c ? feProgress(c) : null; }
      else if (c.state === "done" && c.report) { state = "done"; note = feWords(c.report).headline; }
      else { state = "failed"; note = c.message ?? FE_STOPPED; }
    } else if (p.approved && !ENDED.has(step.state) && step.tool === "answer") {
      const a = p.answers[step.n];
      if (stopped) { state = "skipped"; note = null; }
      else if (a) { state = a.state; note = a.heading; }
      else { state = "planned"; note = null; }
    } else if (p.approved && step.tool === "analyze" && step.state === "done" && p.analyze && !note) {
      note = answerWords(p.analyze).verdict;
    }
    if (state === "failed" || state === "skipped") stopped = true;
    return { n: step.n, role: step.role, tool: step.tool, line: step.line, state, note };
  });
}

/** Whether every step before the answer `n` has ended done: the answer reads what they gave. */
export function readyToAnswer(views: StepView[], n: number): boolean {
  return views.filter((v) => v.n < n && v.tool !== "answer").every((v) => v.state === "done");
}

/** The steps the page carries that changed since last reported, with what to report: each once it ends, an answer also when it starts;
 * a wing's check is the server's while it runs. */
export function kindReports(kind: PlannedKind, views: StepView[], reported: Record<number, StepState>): { n: number; state: StepState; note: string | null }[] {
  return views.filter((v) => REPORTED[kind].has(v.tool) && v.state !== "planned" && reported[v.n] !== v.state && !(v.tool === "check" && v.state === "running"))
    .map((v) => ({ n: v.n, state: v.state, note: v.note }));
}

/** A refused plan's reasons, one line each and fit to show: the server joins them with "; ", each opening with its step's number. */
export function refusalLines(reason: string | null): string[] {
  if (!reason) return [];
  return reason.split(/;\s*(?=step \d+: )/).map((part) => customerText(capital(part.replace(/^step \d+:\s*/, "").trim())))
    .filter((line): line is string => !!line);
}

/** What the card says while the approval carries the runs: the runs it waits for, and about how long. */
export function waitingWords(plan: Plan): string {
  const tools = new Set(plan.steps.map((s) => s.tool));
  const runs = [tools.has("sweep") && "the sweep", tools.has("solve") && "the solve of the slice", tools.has("bond") && "the bond until it lets go",
    tools.has("analyze") && "the hand calculation", tools.has("check") && "the start of the check"].filter((w): w is string => !!w);
  const listed = runs.length > 1 ? `${runs.slice(0, -1).join(", ")} and ${runs[runs.length - 1]}` : runs[0] ?? "the changes";
  const long = tools.has("solve") || tools.has("bond");
  return `${capital(listed)} ${runs.length > 1 ? "run" : "runs"} now: ${long ? "a few seconds, up to about two minutes" : "a moment"}. Stay on this page.`;
}

const readOr = <T>(read: (payload: unknown) => T, payload: unknown): T | null => { try { return read(payload); } catch { return null; } };
const runOf = (runs: PlanRun[], tool: string): unknown => runs.find((r) => r.tool === tool)?.answer;

/** A wing's runs as the approval answered them: the hand calculation of the wing the plan leaves, and the check it started. */
export function wingRuns(runs: PlanRun[]): { analyze: WingAnswer | null; check: WingFeCheck | null } {
  return { analyze: readOr(readWingAnswer, runOf(runs, "analyze")), check: readOr(readWingFeCheck, runOf(runs, "check")) };
}

/** A repair's runs as the approval answered them: the sweep, the solved slice with the cut faces it was solved with (and, after the
 * sweep's pick, the pick held to the load the sweep named), and the bond followed until it lets go. */
export type RepairRuns = { sweep: RepairSweepAnswer | null; solve: RepairSolve | null; cutFaces: "open" | "bonded"; check: SweepCheck | null; bond: RepairBond | null };

export function repairRuns(plan: Plan, runs: PlanRun[]): RepairRuns {
  const solved = runOf(runs, "solve");
  const check = solved && typeof solved === "object" && "check" in solved ? (solved as { check: unknown }).check : null;
  const cut = plan.steps.find((s) => s.tool === "solve")?.change?.cut_faces;
  const solve = readOr(readRepairSolve, solved);
  const bond = readOr(readRepairBond, runOf(runs, "bond"));
  return {
    sweep: readOr(readRepairSweep, runOf(runs, "sweep")),
    solve: solve ? { ...solve, run_id: solve.run_id ?? null } : null,
    cutFaces: cut === "bonded" ? "bonded" : "open",
    check: check && typeof check === "object" && Array.isArray((check as SweepCheck).words) ? check as SweepCheck : null,
    bond: bond ? { ...bond, run_id: bond.run_id ?? null } : null,
  };
}

/** An answer as the chat gives it, put as the plan's answer: what it read the question as decides whether it is one the page answers. */
function given(said: WingSaid | RepairSaid, extra: string[] = []): PlanAnswer {
  if (["redirect", "none", "refused", "ask"].includes(said.kind) || !said.heading) {
    return { state: "failed", heading: "Not a question the page answers from this result", more: [], note: said.lines.join(" ") || null };
  }
  return { state: "done", heading: said.heading, more: [...said.lines, ...extra].filter(Boolean), note: null };
}

/** An answer of why, with the sections of our pages its question's words find, as the chats show one (ADR-0127, ADR-0136): a question
 * of why opens with the first section fit to show, its title and first paragraph; any other answer names the section as its reason. */
export function withSection(answer: PlanAnswer, kind: string, sections: ReferenceSection[]): PlanAnswer {
  const first = sections.find((s) => !bannedIn(`${s.title}\n${s.text}`).length && sectionProse(s.text).length);
  if (kind === "reference") {
    if (!first) return { state: "failed", heading: "Our pages do not cover that yet", more: [], note: null };
    return { state: "done", heading: first.title, more: [sectionProse(first.text)[0], ...answer.more], note: `From our pages: ${first.document}, ${first.title}` };
  }
  return first ? { ...answer, note: `Why: ${first.document}, ${first.title}` } : answer;
}

/** A wing plan's answer, as the wing's chat answers the question from the hand calculation of the wing as the plan left it; with a
 * check done, its headline too. A question of why is answered from our reference pages by the card, as the chat does. */
export function wingPlanAnswer(question: string, report: WingReport, wing: WingDescription, check: WingFeCheck | null): PlanAnswer & { kind: string } {
  const said = wingAnswer(readWingAsk(question), report, wing);
  // the check's lowest is read away from the clamped root, the hand calculation's own answer over the whole wing: where goes with it
  const words = check?.state === "done" && check.report ? feWords(check.report) : null;
  const fe = words ? [words.headline, words.where] : [];
  return { ...given(said, fe), kind: said.kind };
}

/** A repair plan's answer, as the repair's chat answers the question from what the page holds once the plan has run. */
export function repairPlanAnswer(question: string, held: RepairHeld): PlanAnswer & { kind: string } {
  const said = repairAnswer(readRepairAsk(question, kindOf(held.repair)), held);
  return { ...given(said), kind: said.kind };
}
