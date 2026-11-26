"use client";

import { useEffect, useMemo, useRef } from "react";
import { Check, Circle, CircleAlert, LoaderCircle, Minus, X } from "lucide-react";
import { answerResult, reportPlanStep, type Plan, type StepState } from "@/lib/studio-api";
import { planCount, planDrawing, stepsToReport, stepViews, type StepView } from "@/lib/plan-steps";
import { qaNote, qaReady, readQa, type QaReading } from "@/lib/plan-qa";
import { factsOf, readAt, whyLines } from "@/lib/result-why";
import { answerStat } from "@/lib/studio-answer";
import { printed } from "@/lib/studio-colors";
import { customerText } from "@/lib/studio-copy";
import { unreadLines } from "@/lib/proposals";
import { revealPanel } from "@/components/workspace/panels/step-panel";
import { UnreadList } from "./proposal-card";
import { useProject } from "./project-context";

/** Where a plan stands on the page (ADR-0144): shown and waiting for the engineer, being approved, approved and running, changed under
 * it (the server's 409), put back into the chat box to edit, or not approved for another reason (`problem`). The QA and the answer are
 * the page's own steps, kept here with what was reported of each, so the card survives the chat re-rendering it. */
export type PlanFlow = {
  plan: Plan;
  stage: "proposed" | "approving" | "approved" | "stale" | "edited";
  /** the run the approval started, followed as one this page started */
  job: string | null;
  /** the words of an approval that did not go through, or of a stale plan */
  problem: string | null;
  /** the setup check's lines when the server stopped the plan at its check */
  blocked: string[];
  qa: QaReading | null;
  answer: { state: "running" | "done" | "failed"; heading: string | null; more: string[]; note: string | null } | null;
  reported: Record<number, StepState>;
  /** whether the Results tab was opened for this plan's run */
  opened: boolean;
};

export const newFlow = (plan: Plan): PlanFlow => ({ plan, stage: "proposed", job: null, problem: null, blocked: [], qa: null, answer: null, reported: {}, opened: false });

const ROLE_CLASS: Record<string, string> = { Geometry: "geometry", Setup: "setup", Solver: "solver", QA: "qa", Report: "report" };
const QA_MARK = { pass: <Check size={13} aria-label="pass" />, warning: <CircleAlert size={13} aria-label="warning" />, stop: <X size={13} aria-label="stop" /> };

function StateMark({ state }: { state: StepState }) {
  if (state === "done") return <Check size={14} aria-label="done" />;
  if (state === "running") return <LoaderCircle size={14} className="plan-spin" aria-label="running" />;
  if (state === "failed") return <X size={14} aria-label="failed" />;
  if (state === "skipped") return <Minus size={14} aria-label="skipped" />;
  return <Circle size={14} aria-label="waiting" />;
}

/** A plan made from the engineer's sentence (ADR-0144): its steps under their roles, one plain line each, the regions it holds and loads
 * drawn dashed on the model, and one approval. Once approved, each step ticks off as the run goes; the page carries the QA (the result's
 * own checks, `lib/plan-qa.ts`) and the answer (the step's question, answered in words from the result's fact sheet), and reports each. */
export function PlanCard({ flow, onFlow, onApprove, onEdit, onPlanAgain, onUsual }: {
  flow: PlanFlow;
  onFlow: (update: (flow: PlanFlow) => PlanFlow) => void;
  onApprove: () => void;
  /** the sentence back in the message box */
  onEdit: () => void;
  onPlanAgain: () => void;
  /** the message read as before, by the page's own readers and a model's reading of the setup */
  onUsual: () => void;
}) {
  const { apiBaseUrl, run, project } = useProject();
  const { plan, stage } = flow;
  const ours = stage === "approved" && !!flow.job && run.job?.job_id === flow.job;
  const job = ours ? run.job : null;
  const lastJob = useRef(job);
  if (job) lastJob.current = job;
  const views = useMemo(() => stepViews(plan, { approved: stage === "approved", job: job ?? (stage === "approved" ? lastJob.current : null), qa: flow.qa,
    answer: flow.answer ? { state: flow.answer.state, line: flow.answer.heading } : null }), [plan, stage, job, flow.qa, flow.answer]);
  const count = planCount(views);
  const results = ours && run.loadedJob === flow.job ? run.fields : null;

  // the Results tab opens once the run's results are read
  useEffect(() => {
    if (!results || flow.opened) return;
    window.setTimeout(() => revealPanel("outputs"), 0);
    onFlow((f) => ({ ...f, opened: true }));
  }, [results, flow.opened, onFlow]);

  // the QA: the result's own checks, once the run is done and its fields read with the mesh study it wrote
  useEffect(() => {
    if (flow.qa || !job || !results || !qaReady(job, results)) return;
    onFlow((f) => ({ ...f, qa: readQa(job, results) }));
  }, [flow.qa, job, results, onFlow]);

  // the answer: the step's question, answered in words from the result's fact sheet; the package's own verdict where none is written
  const asking = useRef(false);
  const answerStep = plan.steps.find((s) => s.tool === "answer");
  useEffect(() => {
    if (!answerStep || !flow.qa || flow.qa.verdict === "stop" || flow.answer || asking.current || !results) return;
    asking.current = true;
    onFlow((f) => ({ ...f, answer: { state: "running", heading: null, more: [], note: null } }));
    const facts = factsOf(run.explanation);
    const stat = answerStat(results, printed);
    const fallback = () => (stat ? { state: "done" as const, heading: `${stat.verdict}, R = ${stat.factor}`, more: [], note: stat.facts }
      : { state: "failed" as const, heading: "No answer to read in this result", more: [], note: null });
    const question = answerStep.question ?? plan.ask;
    (facts && apiBaseUrl ? answerResult(apiBaseUrl, question, facts) : Promise.reject(new Error("no fact sheet")))
      .then((answer) => {
        const lines = whyLines(answer, false, readAt(facts));
        onFlow((f) => ({ ...f, answer: lines.prose.length ? { state: "done", heading: lines.heading, more: lines.more, note: lines.note } : fallback() }));
      })
      .catch(() => onFlow((f) => ({ ...f, answer: fallback() })));
  }, [answerStep, flow.qa, flow.answer, results, run.explanation, apiBaseUrl, plan.ask, onFlow]);

  // each step the page carries is reported to the plan as it starts and ends; a report that does not go through is not tried again
  const sent = useRef(new Set<string>());
  useEffect(() => {
    if (stage !== "approved" || !apiBaseUrl) return;
    const due = stepsToReport(views, flow.reported).filter((r) => !sent.current.has(`${r.n}:${r.state}`));
    if (!due.length) return;
    for (const r of due) {
      sent.current.add(`${r.n}:${r.state}`);
      const note = r.n === plan.steps.find((s) => s.tool === "qa")?.n && flow.qa ? qaNote(flow.qa) : r.note;
      void reportPlanStep(apiBaseUrl, project.id, plan.id, r.n, r.state, note).catch(() => undefined);
    }
    onFlow((f) => ({ ...f, reported: { ...f.reported, ...Object.fromEntries(due.map((r) => [r.n, r.state])) } }));
  }, [views, stage, flow.reported, flow.qa, apiBaseUrl, project.id, plan.id, plan.steps, onFlow]);

  if (plan.state === "question") {
    return (
      <div className="plan-card" data-testid="plan-card" data-state="question">
        <h4>One question first</h4>
        <p className="proposal-question" data-testid="plan-question">{customerText(plan.question) ?? "Which region do you mean?"}</p>
        <p className="chat-note">Answer here, and the plan is made again with your answer.</p>
      </div>
    );
  }
  if (plan.state === "refused" || plan.state === "capped") {
    const said = customerText(plan.reason);
    return (
      <div className="plan-card" data-testid="plan-card" data-state={plan.state}>
        <h4>{plan.state === "capped" ? "No more plans today" : "No plan for that"}</h4>
        <p data-testid="plan-reason">{said ?? (plan.state === "capped" ? "Today's plans are used. Messages are read the usual way until midnight UTC."
          : "It could not be done with the steps on offer.")}</p>
        <UnreadList lines={unreadLines(plan.unread)} />
        {stage === "edited" ? null : (
          <div className="chat-chips">
            <button type="button" data-testid="plan-usual" onClick={() => { onFlow((f) => ({ ...f, stage: "edited" })); onUsual(); }}>Read it the usual way</button>
            <button type="button" data-testid="plan-edit" onClick={onEdit}>Edit the message</button>
          </div>
        )}
      </div>
    );
  }

  const drawn = stage === "proposed" && planDrawing(plan) !== null;
  const hasRun = plan.steps.some((s) => s.tool === "run");
  const heading = stage === "approved" ? (count.ended ? `Plan done · ${count.done} of ${count.of} steps` : `Plan running · ${count.done} of ${count.of} done`)
    : `Plan · ${plan.steps.length} ${plan.steps.length === 1 ? "step" : "steps"}`;
  const aside = stage === "proposed" ? "Nothing changes until you approve" : stage === "approving" ? "Approving…" : stage === "approved" ? "Approved by you"
    : stage === "stale" ? "Not applied" : "Put back in the message box";
  return (
    <div className="plan-card" data-testid="plan-card" data-state={stage} data-plan-state={plan.state}>
      <div className="plan-head"><h4 data-testid="plan-heading">{heading}</h4><span className="plan-aside">{aside}</span></div>
      <ol className="plan-steps" data-testid="plan-steps">
        {views.map((v: StepView) => (
          <li key={v.n} data-step={v.n} data-tool={v.tool} data-role={v.role} data-state={v.state}>
            <span className={`plan-mark plan-mark-${v.state}`}><StateMark state={v.state} /></span>
            <span className={`plan-role plan-role-${ROLE_CLASS[v.role] ?? "setup"}`}>{v.role}</span>
            <span className="plan-line">{v.line}{v.note && v.tool !== "answer" ? <span className="plan-note" data-testid="plan-step-note">{v.note}</span> : null}</span>
          </li>
        ))}
      </ol>
      {drawn ? <p className="chat-note" data-testid="plan-drawn">The regions it holds and loads are drawn dashed on the model.</p> : null}
      {/* what the sentence asked that no step does, shown before the approval as a refused plan shows it (ADR-0144, step 4) */}
      {stage === "proposed" || stage === "approving" ? <UnreadList lines={unreadLines(plan.unread)} /> : null}
      {flow.blocked.length ? <ul className="chat-understood" data-testid="plan-blocked">{flow.blocked.map((line) => <li key={line}>{line}</li>)}</ul> : null}
      {flow.problem ? <p className="chat-problem" data-testid="plan-problem">{flow.problem}</p> : null}
      {flow.qa ? (
        <ul className="plan-qa" data-testid="plan-qa" data-verdict={flow.qa.verdict}>
          {flow.qa.checks.map((c) => <li key={c.id} data-check={c.id} data-verdict={c.verdict} className={`plan-qa-${c.verdict}`}>{QA_MARK[c.verdict]} <span>{c.line}</span></li>)}
        </ul>
      ) : null}
      {flow.answer && flow.answer.state !== "running" ? (
        <div className="plan-answer" data-testid="plan-answer" data-state={flow.answer.state}>
          <p className="plan-answer-heading" data-testid="plan-answer-heading"><strong>{flow.answer.heading}</strong></p>
          {flow.answer.more.length || flow.answer.note ? (
            <details className="chat-details"><summary>Details</summary>
              {flow.answer.more.map((line, i) => <p key={i}>{line}</p>)}
              {flow.answer.note ? <p className="chat-note">{flow.answer.note}</p> : null}
            </details>
          ) : null}
        </div>
      ) : null}
      {stage === "proposed" || stage === "approving" ? (
        <div className="chat-actions">
          <button type="button" className="chat-primary" data-testid="plan-approve" disabled={stage === "approving"} onClick={onApprove}>
            <Check size={14} /> {hasRun ? "Approve and run" : "Approve"}</button>
          <button type="button" className="chat-secondary" data-testid="plan-edit" disabled={stage === "approving"} onClick={onEdit}>Edit</button>
        </div>
      ) : stage === "stale" ? (
        <div className="chat-actions"><button type="button" className="chat-primary" data-testid="plan-again" onClick={onPlanAgain}>Plan again</button></div>
      ) : null}
    </div>
  );
}
