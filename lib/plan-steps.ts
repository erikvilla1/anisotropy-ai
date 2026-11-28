/**
 * A plan's steps as the page shows them while it runs (ADR-0144): the server applies the changes, checks the setup and starts the run at
 * approval; the page follows the run and carries the last two steps, the QA and the answer. Each step's state is read from what the page
 * holds: the approval, the job as it is polled, the QA reading and the answer. Pure, so `tests/plan-steps.test.ts` holds it.
 */
import { EDGE_NORMAL } from "./plate-edits";
import type { JobStatus, Plan, PlanRole, PlanStep, StepState } from "./studio-api";
import { runHeadline, runProblem } from "./studio-copy";
import type { QaReading } from "./plan-qa";

/** The steps the page carries and reports (`reportPlanStep`); every other step is the server's. */
export const PAGE_TOOLS = new Set(["qa", "answer"]);
const SOLVER_TOOLS = new Set(["check", "run"]);
const ENDED = new Set<StepState>(["done", "failed", "skipped"]);

/** An answer step as the page holds it: under way, given (its first line) or not given. */
export type AnswerProgress = { state: "running" | "done" | "failed"; line: string | null };
/** What the page holds of a plan's run: whether the approval came back, the job it started as last polled, the QA once read, and the
 * answers. A plan may have several answer steps: `answers` holds each by its step's number; `answer` is the first answer step's, for a
 * caller that holds one, and no other answer step ever takes its words. */
export type PlanProgress = {
  approved: boolean;
  job: Pick<JobStatus, "state" | "stage" | "message" | "result" | "documents" | "outputs"> | null;
  qa: QaReading | null;
  answer: AnswerProgress | null;
  answers?: Record<number, AnswerProgress>;
};
export type StepView = { n: number; role: PlanRole; tool: string; line: string; state: StepState; note: string | null };

function stateOf(step: PlanStep, plan: Plan, p: PlanProgress, before: Map<string, StepState>): { state: StepState; note: string | null } {
  const server = { state: step.state, note: step.note };
  if (!p.approved) return { state: step.state === "planned" ? "planned" : step.state, note: step.note };
  if (!SOLVER_TOOLS.has(step.tool) && !PAGE_TOOLS.has(step.tool)) return step.state === "failed" || step.state === "skipped" ? server : { state: "done", note: step.note };
  const job = p.job;
  if (step.tool === "check") {
    if (ENDED.has(step.state)) return server;
    return job ? { state: "done", note: null } : plan.state === "stopped" ? { state: "failed", note: step.note } : { state: "running", note: null };
  }
  if (step.tool === "run") {
    if (!job) return ENDED.has(step.state) ? server : plan.state === "stopped" ? { state: "skipped", note: step.note } : { state: "planned", note: null };
    if (job.state === "queued" || job.state === "running") return { state: "running", note: runHeadline(job) };
    if (job.state === "done") return { state: "done", note: null };
    return { state: "failed", note: runProblem(job) };
  }
  const ran = before.get("run");
  const stopped = ran === "failed" || ran === "skipped" || (ran === undefined && plan.state === "stopped");
  if (step.tool === "qa") {
    if (stopped) return { state: "skipped", note: null };
    if (!p.qa) return { state: ran === "done" ? "running" : "planned", note: null };
    return { state: p.qa.verdict === "stop" ? "failed" : "done", note: p.qa.headline };
  }
  // an answer: given only on a result the QA let through, each answer step its own, in order; none after one that was not given
  const earlier = before.get("answer");
  if (stopped || before.get("qa") === "failed" || before.get("qa") === "skipped" || earlier === "failed" || earlier === "skipped") return { state: "skipped", note: null };
  const mine = p.answers ? p.answers[step.n] ?? null : earlier === undefined ? p.answer : null;
  if (!mine) return { state: "planned", note: null };
  return { state: mine.state, note: mine.line };
}

/** Every step with its state as the run goes, in the plan's order. */
export function stepViews(plan: Plan, progress: PlanProgress): StepView[] {
  const before = new Map<string, StepState>();
  return plan.steps.map((step) => {
    const { state, note } = stateOf(step, plan, progress, before);
    before.set(step.tool, state);
    return { n: step.n, role: step.role, tool: step.tool, line: step.line, state, note };
  });
}

/** The answer step to ask now, by its number: the first one that is not done, when it has not started, the QA let the result through
 * and every answer before it is done. Null while one is under way, after one that was not given, and when none is left. So a plan's
 * answers are asked one at a time, in the plan's order, each once. */
export function answerDue(views: StepView[]): number | null {
  const qa = views.find((v) => v.tool === "qa");
  if (qa && qa.state !== "done") return null;
  const next = views.filter((v) => v.tool === "answer").find((v) => v.state !== "done");
  return next && next.state === "planned" ? next.n : null;
}

/** Whether every step has ended, and how many are done: the card's count ("4 of 6 done"). */
export function planCount(views: StepView[]): { done: number; of: number; ended: boolean } {
  return { done: views.filter((v) => v.state === "done").length, of: views.length, ended: views.every((v) => ENDED.has(v.state)) };
}

/** The steps the page carries that have changed since last reported, with what to report: each once it ends, the answer also when it starts. */
export function stepsToReport(views: StepView[], reported: Record<number, StepState>): { n: number; state: StepState; note: string | null }[] {
  return views.filter((v) => PAGE_TOOLS.has(v.tool) && v.state !== "planned" && reported[v.n] !== v.state && !(v.state === "running" && v.tool === "qa"))
    .map((v) => ({ n: v.n, state: v.state, note: v.note }));
}

/** The supports and loads a plan's changes put on the model, drawn dashed before anything applies (ADR-0110, ADR-0101): a hold and a
 * move as a support, a force along its direction (by its sense, along the edge's outward normal), a pressure along the face's normal.
 * Rows of size, material and layup draw nothing. Null when the plan draws nothing. */
export type PlanDrawing = { supports: { region: string; dofs: number[] }[];
  loads: { region: string; kind: "force" | "pressure"; dof: number | null; value: string; unit: string }[] };

const text = (v: unknown): string => (typeof v === "string" ? v : typeof v === "number" ? String(v) : "");
const flipped = (value: string) => (value.trim().startsWith("-") ? value.trim().slice(1) : `-${value.trim()}`);

export function planDrawing(plan: Pick<Plan, "steps">): PlanDrawing | null {
  const out: PlanDrawing = { supports: [], loads: [] };
  for (const step of plan.steps) {
    const c = step.change;
    if (!c || typeof c.region !== "string") continue;
    const region = c.region, value = text(c.value), unit = text(c.unit);
    if (c.action === "hold" && Array.isArray(c.dofs)) out.supports.push({ region, dofs: c.dofs.filter((d): d is number => typeof d === "number") });
    else if (c.action === "move" && typeof c.dof === "number") out.supports.push({ region, dofs: [c.dof] });
    else if (c.action === "pressure" && value) out.loads.push({ region, kind: "pressure", dof: null, value, unit });
    else if (c.action === "force" && value) {
      if (typeof c.dof === "number") out.loads.push({ region, kind: "force", dof: c.dof, value, unit });
      else if (c.sense === "tension" || c.sense === "compression") {
        const normal = EDGE_NORMAL[region];
        if (!normal) continue;
        const sign = c.sense === "tension" ? normal[1] : -normal[1];
        out.loads.push({ region, kind: "force", dof: normal[0], value: sign < 0 ? flipped(value) : value, unit });
      }
    }
  }
  return out.supports.length || out.loads.length ? out : null;
}
