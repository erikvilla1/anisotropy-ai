"use client";

import { answerWords, needsWords, NOT_THE_STRENGTH, peakPlace, shown, unitText, type RepairReport } from "@/lib/repair";
import { showPanel } from "./panels/step-panel";
import { RepairChat } from "./repair-chat";
import { useRepair } from "./repair-context";

/** Why the adhesive's shear stress peaks where it does, and what usually lowers it: general words, no number, and not a design for
 * this repair. */
function Peak({ report }: { report: RepairReport }) {
  const answer = report.lap.answer;
  if (!answer) return null;
  const stress = unitText(report.units.stress);
  return (
    <div className="wing-explain repair-explain" data-testid="repair-explain">
      <h3>Where the adhesive works hardest</h3>
      <p><strong>{shown(Math.abs(answer.peak_shear.value))} {stress}</strong> by hand, {peakPlace(report)}.</p>
      <p>The adhesive carries load between the laminate and the patch mostly at the ends of each step, where one of the two is much stiffer than the other. In the middle of a long step it carries little.</p>
      <p className="studio-hint">What usually lowers the largest stress:</p>
      <ul>
        <li>More steps, each removing fewer plies</li>
        <li>A patch whose stiffness matches the plies it replaces</li>
        <li>A thicker or softer adhesive, within what the adhesive&apos;s data allow</li>
      </ul>
      <button type="button" className="studio-text-button" onClick={() => showPanel("repair-damage")}>Open the steps</button>
    </div>
  );
}

/** The right column of the repair's page (ADR-0135): the answer in words, what the numbers are and are not, and what a solve still
 * needs, with the repair's chat under them (ADR-0136). It words the engine's report and computes nothing. */
export function RepairAssistant() {
  const { answer, problem, solve, solveStale } = useRepair();
  return (
    <div className="studio-panel wing-assistant" data-testid="repair-assistant">
      <h3>Repair assistant</h3>
      {problem ? <p className="studio-alert" role="alert">{problem}</p> : null}
      {answer ? (
        <>
          <p className="wing-verdict"><strong>{answerWords(answer.report).headline}.</strong></p>
          <Peak report={answer.report} />
          <div className="wing-explain repair-explain" data-testid="repair-two-answers">
            <h3>Two answers, one repair</h3>
            <p>The hand calculation is worked again on every change, in a fraction of a second. It gives the adhesive&apos;s shear stress only.</p>
            <p>{solve && !solveStale ? "The solved slice is shown beside it: it adds the peel stress and each ply's stresses."
              : solve ? "The slice was solved for the repair as it was. Solve it again to compare the two."
              : answer.needs.length ? needsWords(answer.needs)
              : "Solving the slice adds the peel stress and each ply's stresses. It takes a few seconds."}</p>
            <button type="button" className="studio-text-button" onClick={() => showPanel("repair-solve")}>Open Solve</button>
          </div>
          {answer.report.lap.answer?.elastic_limit_load !== undefined ? <p className="studio-hint" data-testid="repair-not-strength">{NOT_THE_STRENGTH} Neither answer is a failure load.</p> : null}
        </>
      ) : <p className="studio-muted">The repair&apos;s answer appears here once it is worked.</p>}
      <RepairChat />
    </div>
  );
}
