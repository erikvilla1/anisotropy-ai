/** What a plan must hold (ADR-0144, build step 4), wherever it is seen: the API's answer in the real-model run of the question banks
 * (`harness.ts`, `liveFaults`) and the plan card on the live site (`scripts/site-check/grade.ts`). The contract every plan keeps, then
 * what a bank's question says its plan should be (`live.plan`). Nothing here reads a model. */

/** The roles a step may take, as the card shows them. */
export const PLAN_ROLES = ["Geometry", "Setup", "Solver", "QA", "Report"] as const;
/** A plan's steps at most, the server's check and qa among them. */
export const MAX_PLAN_STEPS = 12;
/** What a plan may be before anyone approves it; the robot and the real-model run never do. */
export const UNAPPROVED = ["proposed", "question", "refused", "capped", "unavailable"] as const;
/** The steps the server adds around the run, and the steps that change nothing. */
const SERVER = new Set(["check", "run", "qa"]);
const READS = new Set(["check", "run", "qa", "answer"]);

/** What a bank's question expects of its plan (`live.plan`). */
export type PlanWant = {
  /** The plan's state, or the states any of which is right. */
  state: string | string[];
  /** Its steps' tools in order, the server's check, run and qa among them. */
  tools?: string[];
  /** Tools it holds somewhere, and tools it never holds. */
  has?: string[];
  never?: string[];
  /** Rows its changes set, by key, the value as written, and rows it never sets (the API's answer holds them; the card does not). */
  rows?: Record<string, string>;
  leaves?: string[];
  /** Regions its changes name (the API's answer holds them; the card does not). */
  regions?: string[];
  /** Words its reason or its question holds, each as written, case aside. */
  says?: string[];
};

/** A plan as it was seen: the API's answer, or the card on the page. */
export type PlanSeen = {
  state: string;
  steps: { tool: string; role: string; state: string; line?: string; change?: Record<string, unknown> | null; regions?: string[] }[];
  question?: string | null;
  reason?: string | null;
};

/** What the API answers for a plan, as the card's own words would read it. */
export function planSeen(answer: Record<string, unknown>): PlanSeen {
  const steps = Array.isArray(answer.steps) ? (answer.steps as Record<string, unknown>[]) : [];
  return {
    state: String(answer.state),
    steps: steps.map((s) => ({ tool: String(s.tool), role: String(s.role), state: String(s.state), line: typeof s.line === "string" ? s.line : undefined,
      change: (s.change ?? null) as Record<string, unknown> | null, regions: Array.isArray(s.regions) ? (s.regions as string[]) : undefined })),
    question: typeof answer.question === "string" ? answer.question : null,
    reason: typeof answer.reason === "string" ? answer.reason : null,
  };
}

/** The card's heading for a plan before its approval, as `components/studio/plan-card.tsx` writes it. */
export function planHeading(plan: PlanSeen): string {
  if (plan.state === "question") return "One question first";
  if (plan.state === "capped") return "No more plans today";
  if (plan.state === "refused") return "No plan for that";
  if (plan.state === "unavailable") return "Read as before";
  return `Plan · ${plan.steps.length} ${plan.steps.length === 1 ? "step" : "steps"}`;
}

/** What the contract says of any plan seen before approval: the order of its steps, its roles and states, and a reason or a question
 * where it has no steps. */
export function contractFaults(plan: PlanSeen): string[] {
  const out: string[] = [];
  const tools = plan.steps.map((s) => s.tool);
  if (!(UNAPPROVED as readonly string[]).includes(plan.state)) out.push(`the plan is ${plan.state}, though nobody approved it`);
  if (plan.state !== "proposed") {
    if (plan.steps.length) out.push(`the ${plan.state} plan shows ${plan.steps.length} steps`);
    if (plan.state === "question" && !/\?\s*$/.test(plan.question ?? "")) out.push("the question back is no question");
    if (plan.state === "refused" && !(plan.reason ?? "").trim()) out.push("a refused plan gives no reason");
    return out;
  }
  if (!plan.steps.length) out.push("a proposed plan with no step");
  if (plan.steps.length > MAX_PLAN_STEPS) out.push(`${plan.steps.length} steps; a plan has at most ${MAX_PLAN_STEPS}`);
  for (const s of plan.steps) {
    if (!(PLAN_ROLES as readonly string[]).includes(s.role)) out.push(`step ${s.tool} has the role ${s.role}`);
    if (s.state !== "planned") out.push(`step ${s.tool} is ${s.state} before the approval`);
  }
  const runs = tools.filter((t) => t === "run").length;
  if (runs > 1) out.push(`${runs} runs; a plan runs once`);
  const run = tools.indexOf("run");
  if (run >= 0 && (tools[run - 1] !== "check" || tools[run + 1] !== "qa")) out.push("the run is not between the setup check and the result's checks");
  if (run < 0 && tools.some((t) => SERVER.has(t))) out.push("a check or a QA step with no run");
  tools.forEach((t, i) => {
    if (!READS.has(t) && run >= 0 && i > run) out.push(`the change ${t} comes after the run`);
    if (t === "answer" && (run < 0 || i < run)) out.push("an answer before any run");
  });
  return out;
}

const sameRegion = (a: string, b: string) => {
  const words = (name: string) => name.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean).sort().join(" ");
  return words(a) === words(b);
};

/** What is wrong with a plan seen, by the contract and by what the bank's question expects of it; none when it holds. With no plan seen,
 * only an expected one is missed. */
export function planFaults(want: PlanWant | undefined, plan: PlanSeen | null): string[] {
  if (!plan) return want ? [`no plan was made; expected ${[want.state].flat().join(" or ")}`] : [];
  const out = contractFaults(plan);
  if (!want) return out;
  const states = [want.state].flat();
  if (!states.includes(plan.state)) out.push(`the plan is ${plan.state}, expected ${states.join(" or ")}`);
  const tools = plan.steps.map((s) => s.tool);
  if (want.tools && plan.state === "proposed" && tools.join(" ") !== want.tools.join(" ")) out.push(`steps ${tools.join(", ")}, expected ${want.tools.join(", ")}`);
  for (const t of want.has ?? []) if (plan.state === "proposed" && !tools.includes(t)) out.push(`no ${t} step`);
  for (const t of want.never ?? []) if (tools.includes(t)) out.push(`a ${t} step`);
  if (want.rows && plan.state === "proposed" && plan.steps.some((s) => s.change !== undefined)) {
    const rows = Object.fromEntries(plan.steps.filter((s) => s.change?.action === "row").map((s) => [String(s.change!.key), String(s.change!.value)]));
    for (const [key, value] of Object.entries(want.rows)) {
      const got = rows[key];
      const same = got !== undefined && (got === value || (Number.isFinite(Number(value)) && Number(got) === Number(value)));
      if (!same) out.push(`sets ${key} to ${got ?? "nothing"}, expected ${value}`);
    }
  }
  for (const key of want.leaves ?? []) {
    if (plan.steps.some((s) => s.change?.action === "row" && s.change.key === key)) out.push(`sets ${key}, which the sentence does not ask for`);
  }
  if (want.regions && plan.state === "proposed" && plan.steps.some((s) => s.change !== undefined)) {
    const named = [...new Set(plan.steps.flatMap((s) => [...(s.regions ?? []), ...(typeof s.change?.region === "string" ? [s.change.region] : [])]))];
    for (const region of want.regions) if (!named.some((n) => sameRegion(n, region))) out.push(`no step on the ${region}; regions: ${named.join(", ") || "none"}`);
  }
  const words = `${plan.reason ?? ""}\n${plan.question ?? ""}`.toLowerCase();
  for (const w of want.says ?? []) if (!words.includes(w.toLowerCase())) out.push(`does not say “${w}”`);
  return out;
}
