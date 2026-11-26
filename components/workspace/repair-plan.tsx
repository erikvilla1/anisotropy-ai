"use client";

import { useEffect, useMemo, useRef } from "react";
import { repairReferences, reportRepairPlanStep } from "@/lib/studio-api";
import { kindReports, kindViews, readyToAnswer, refusalLines, repairPlanAnswer, repairRuns, waitingWords, withSection, type KindFlow,
  type RepairRuns } from "@/lib/plan-kinds";
import { bondWords, LET_GO_IS_NOT_THE_STRENGTH, NOT_THE_STRENGTH, sliceWords } from "@/lib/repair";
import { PlanAnswerBlock, PlanFrame, PlanWaiting } from "@/components/studio/plan-card";
import { heldOf, useRepair } from "./repair-context";
import { Sweep } from "./repair-sweep";

const SERVER_RUNS = new Set(["sweep", "solve", "bond"]);

/** A repair's plan (ADR-0144, step 5), on the coupon's card: its steps under their roles, Approve and Edit. The approval carries the
 * changes, the sweep, its pick, the solve and the bond inside the request, so the card says what runs and counts the seconds; then the
 * repair it leaves becomes the page's, the sweep is shown with its pick, the solved slice with what it says of the pick, and the bond;
 * the page answers each answer step as the repair's chat would, and reports it. */
export function RepairPlanCard({ flow, onFlow, onApprove, onEdit, onPlanAgain, onUsual }: {
  flow: KindFlow;
  onFlow: (update: (flow: KindFlow) => KindFlow) => void;
  onApprove: () => void;
  onEdit: () => void;
  onPlanAgain: () => void;
  onUsual: () => void;
}) {
  const ctx = useRepair();
  const { apiBaseUrl } = ctx;
  const { plan, stage } = flow;
  const runs = useMemo(() => repairRuns(plan, flow.runs), [plan, flow.runs]);
  const views = useMemo(() => kindViews(plan, { approved: stage === "approved", check: null, answers: flow.answers }), [plan, stage, flow.answers]);

  // each answer, once every step before it is done and the page has worked by hand the repair the plan left
  const asking = useRef(new Set<number>());
  const leftNow = flow.left !== null && JSON.stringify(ctx.repair) === flow.left;
  const ready = leftNow && !!ctx.answer && !ctx.stale && !ctx.working;
  useEffect(() => {
    if (stage !== "approved") return;
    for (const step of plan.steps) {
      if (step.tool !== "answer" || flow.answers[step.n] || asking.current.has(step.n) || !readyToAnswer(views, step.n)) continue;
      if (flow.left !== null && !leftNow) {
        asking.current.add(step.n);
        onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: { state: "failed", heading: "The repair changed before this was answered", more: [], note: null } } }));
        continue;
      }
      if (!ready) continue;
      asking.current.add(step.n);
      const question = step.question ?? plan.ask;
      const found = repairPlanAnswer(question, heldOf(ctx));
      const { kind, ...answer } = found;
      if (kind !== "reference" || !apiBaseUrl) { onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: answer } })); continue; }
      onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: { state: "running", heading: null, more: [], note: null } } }));
      repairReferences(apiBaseUrl, question).catch(() => [])
        .then((sections) => onFlow((f) => ({ ...f, answers: { ...f.answers, [step.n]: withSection(answer, kind, sections) } })));
    }
  }, [stage, plan, views, flow.answers, flow.left, leftNow, ready, ctx, apiBaseUrl, onFlow]);

  // each answer is reported to the plan as it starts and ends; a report that does not go through is not tried again
  const sent = useRef(new Set<string>());
  useEffect(() => {
    if (stage !== "approved" || !apiBaseUrl) return;
    const due = kindReports("repair", views, flow.reported).filter((r) => !sent.current.has(`${r.n}:${r.state}`));
    if (!due.length) return;
    for (const r of due) {
      sent.current.add(`${r.n}:${r.state}`);
      void reportRepairPlanStep(apiBaseUrl, plan.id, r.n, r.state, r.note).catch(() => undefined);
    }
    onFlow((f) => ({ ...f, reported: { ...f.reported, ...Object.fromEntries(due.map((r) => [r.n, r.state])) } }));
  }, [views, stage, flow.reported, apiBaseUrl, plan.id, onFlow]);

  const reasons = refusalLines(plan.reason);
  return (
    <PlanFrame plan={plan} stage={stage} views={views} problem={flow.problem} reasons={reasons.length ? reasons : undefined}
      approveLabel={plan.steps.some((s) => SERVER_RUNS.has(s.tool)) ? "Approve and run" : "Approve"}
      waiting={<PlanWaiting words={waitingWords(plan)} since={flow.since} />}
      onApprove={onApprove} onEdit={onEdit} onPlanAgain={onPlanAgain} onUsual={() => { onFlow((f) => ({ ...f, stage: "edited" })); onUsual(); }}>
      {stage === "approved" ? <RepairPlanRuns runs={runs} /> : null}
      {plan.steps.filter((s) => s.tool === "answer").map((s) => {
        const answer = flow.answers[s.n];
        return answer && answer.state !== "running" ? <PlanAnswerBlock key={s.n} n={s.n} answer={answer} /> : null;
      })}
    </PlanFrame>
  );
}

/** What a repair plan's runs gave, each as the page shows its own: the sweep with its pick, the solved slice (after the pick, what it
 * says of the pick at the load the sweep named, which may be no), and the bond followed until it lets go. */
function RepairPlanRuns({ runs }: { runs: RepairRuns }) {
  const { sweep, solve, check, bond } = runs;
  const slice = solve ? sliceWords(solve.report) : null;
  const followed = bond ? bondWords(bond.report) : null;
  return (
    <>
      {sweep ? <div className="plan-run" data-testid="plan-run-sweep"><Sweep sweep={sweep} /></div> : null}
      {solve && slice ? (
        <div className="plan-run" data-testid="plan-run-solve">
          <h4>{slice.first ? slice.first.replace(/\.$/, "") : "The slice is solved"}</h4>
          {check ? (
            <p className={check.holds === false ? "plan-run-check plan-run-check-no" : "plan-run-check"} data-testid="plan-run-check"
              data-holds={check.close ? "close" : check.holds === null ? "unchecked" : String(check.holds)}>{check.words.join(" ")}</p>
          ) : <p data-testid="plan-run-solve-headline">{solve.headline}.</p>}
          <details className="chat-details"><summary>Details</summary>
            {check ? <p data-testid="plan-run-solve-headline">{solve.headline}.</p> : null}
            <p>{slice.shear}</p>
            <p>{slice.peel}</p>
            <p>{slice.ply}</p>
          </details>
          <p className="chat-note">{NOT_THE_STRENGTH}</p>
        </div>
      ) : null}
      {bond && followed ? (
        <div className="plan-run" data-testid="plan-run-bond">
          <h4>{followed.headline}</h4>
          <p>{followed.softens}</p>
          {followed.extent ? <p>{followed.extent}</p> : <p>{followed.short}</p>}
          {bond.report.let_go ? <p className="chat-note">{LET_GO_IS_NOT_THE_STRENGTH}</p> : null}
        </div>
      ) : null}
    </>
  );
}
