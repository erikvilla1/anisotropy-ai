"use client";

import { useEffect, useMemo, useRef } from "react";
import { reportPlanStep, wingReferences } from "@/lib/studio-api";
import { kindReports, kindViews, readyToAnswer, refusalLines, waitingWords, wingPlanAnswer, wingRuns, withSection, type KindFlow } from "@/lib/plan-kinds";
import { wingKey } from "@/lib/wing-versions";
import { PlanAnswerBlock, PlanFrame, PlanWaiting } from "@/components/studio/plan-card";
import { useWing } from "./wing-context";

/** Answers the reference pages explain, beside the wing's own facts, as the wing's chat has them. */
const EXPLAINED = new Set(["reference", "rule-limit", "rules", "strengths"]);

/** A wing's plan (ADR-0144, step 5), on the coupon's card: its steps under their roles, Approve and Edit. The approval makes the changes
 * of plies on the server, works the wing by hand and starts the finite element check; the page then takes the wing it left (a version by
 * the assistant, with the sentence as why), shows the hand calculation as its own answer, follows the check as one started here, and
 * answers each answer step as the wing's chat would, reporting the check and each answer as they end. */
export function WingPlanCard({ flow, onFlow, onApprove, onEdit, onPlanAgain, onUsual }: {
  flow: KindFlow;
  onFlow: (update: (flow: KindFlow) => KindFlow) => void;
  onApprove: () => void;
  onEdit: () => void;
  onPlanAgain: () => void;
  onUsual: () => void;
}) {
  const { apiBaseUrl, project, wing, answer, stale, working, feCheck } = useWing();
  const { plan, stage } = flow;
  const runs = useMemo(() => wingRuns(flow.runs), [flow.runs]);

  // the check the approval started, as the page follows it; kept on the card, so another check started later does not take its place
  useEffect(() => {
    if (stage !== "approved" || !feCheck || !plan.job || feCheck.job_id !== plan.job || feCheck === flow.check) return;
    onFlow((f) => ({ ...f, check: feCheck }));
  }, [stage, feCheck, plan.job, flow.check, onFlow]);

  const views = useMemo(() => kindViews(plan, { approved: stage === "approved", check: flow.check, analyze: runs.analyze?.report ?? null, answers: flow.answers }),
    [plan, stage, flow.check, runs.analyze, flow.answers]);

  // each answer, once every step before it is done and the page holds the hand calculation of the wing the plan left
  const asking = useRef(new Set<number>());
  const leftNow = flow.left !== null && wingKey(wing) === flow.left;
  const ready = leftNow && !!answer && !stale && !working;
  useEffect(() => {
    if (stage !== "approved") return;
    for (const step of plan.steps) {
      if (step.tool !== "answer" || flow.answers[step.n] || asking.current.has(step.n) || !readyToAnswer(views, step.n)) continue;
      if (flow.left !== null && !leftNow) {
        asking.current.add(step.n);
        onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: { state: "failed", heading: "The wing changed before this was answered", more: [], note: null } } }));
        continue;
      }
      if (!ready || !answer) continue;
      asking.current.add(step.n);
      const question = step.question ?? plan.ask;
      const { kind, ...given } = wingPlanAnswer(question, answer.report, wing, flow.check);
      if (!EXPLAINED.has(kind) || !apiBaseUrl) { onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: given } })); continue; }
      onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: { state: "running", heading: null, more: [], note: null } } }));
      wingReferences(apiBaseUrl, question).catch(() => [])
        .then((sections) => onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: withSection(given, kind, sections) } })));
    }
  }, [stage, plan, views, flow.answers, flow.left, flow.check, leftNow, ready, answer, wing, apiBaseUrl, onFlow]);

  // the check and each answer are reported to the plan as they end (an answer also as it starts); a report not taken is not tried again
  const sent = useRef(new Set<string>());
  useEffect(() => {
    if (stage !== "approved" || !apiBaseUrl) return;
    const due = kindReports("wing", views, flow.reported).filter((r) => !sent.current.has(`${r.n}:${r.state}`));
    if (!due.length) return;
    for (const r of due) {
      sent.current.add(`${r.n}:${r.state}`);
      void reportPlanStep(apiBaseUrl, project.id, plan.id, r.n, r.state, r.note).catch(() => undefined);
    }
    onFlow((f) => ({ ...f, reported: { ...f.reported, ...Object.fromEntries(due.map((r) => [r.n, r.state])) } }));
  }, [views, stage, flow.reported, apiBaseUrl, project.id, plan.id, onFlow]);

  const reasons = refusalLines(plan.reason);
  const checks = plan.steps.some((s) => s.tool === "check");
  const checkState = views.find((v) => v.tool === "check")?.state;
  const beside = checkState === "done" ? ", with the finite element check beside it" : checkState === "planned" || checkState === "running" ? ", and the finite element check as it runs" : "";
  return (
    <PlanFrame plan={plan} stage={stage} views={views} problem={flow.problem} reasons={reasons.length ? reasons : undefined}
      approveLabel={checks ? "Approve and run" : "Approve"} waiting={<PlanWaiting words={waitingWords(plan)} since={flow.since} />}
      onApprove={onApprove} onEdit={onEdit} onPlanAgain={onPlanAgain} onUsual={() => { onFlow((f) => ({ ...f, stage: "edited" })); onUsual(); }}>
      {stage === "approved" && runs.analyze ? (
        <p className="chat-note" data-testid="plan-run-analyze">The results show the changed wing, worked by hand{beside}.</p>
      ) : null}
      {plan.steps.filter((s) => s.tool === "answer").map((s) => {
        const said = flow.answers[s.n];
        return said && said.state !== "running" ? <PlanAnswerBlock key={s.n} n={s.n} answer={said} /> : null;
      })}
    </PlanFrame>
  );
}
