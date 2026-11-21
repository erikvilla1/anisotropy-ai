"use client";

import { answerWords, needsWords, sentence, type RepairAnswer } from "@/lib/repair";
import { DetailsToggle, Slot, useCanvasSlots } from "./canvas-slots";
import { showPanel } from "./panels/step-panel";
import { useRepair } from "./repair-context";
import { Limits, LapTable, SizesTable, SliceResults } from "./repair-details";
import { BondChart, ForceChart, sliceCaption, SliceDrawing, SliceLegend } from "./repair-drawings";

/** The centre of the repair's page (ADR-0135): the half slice as the engine cut it, the adhesive's stresses along the bond under it on
 * the same scale, the answer in its short form in the card, and the tables under Details. Every number is the engine's or the
 * solver's; the page picks, draws and words. */
export function RepairStage() {
  const { answer, stale, working, problem } = useRepair();
  if (!answer) {
    return (
      <div className="studio-panel wing-stage wing-waiting" data-testid="repair-stage" data-state="waiting">
        <p className={problem ? "studio-alert" : "studio-muted"} role={problem ? "alert" : "status"}>{problem || (working ? "Working the repair…" : "The repair appears here.")}</p>
      </div>
    );
  }
  return <Answer answer={answer} stale={stale} problem={problem} />;
}

function Answer({ answer, stale, problem }: { answer: RepairAnswer; stale: boolean; problem: string }) {
  const { report, views, needs } = answer;
  const { solve, solveStale, solving, solveSlice, solveProblem } = useRepair();
  const slots = useCanvasSlots();
  const words = answerWords(report);
  const slice = solve?.report ?? null;
  const can = needs.length === 0 && !stale && !problem;
  return (
    <div className="wing-stage wing-canvas repair-canvas" data-testid="repair-stage" data-state={stale ? "stale" : "current"}>
      <div className="repair-views">
        <figure className="wing-figure">
          <h3>The slice through the repair</h3>
          <SliceDrawing report={report} views={views} />
        </figure>
        <figure className="wing-figure">
          <h3>The adhesive&apos;s stresses along the bond</h3>
          <BondChart report={report} views={views} slice={slice} stale={solveStale} />
        </figure>
      </div>
      <Slot name="view">
        <div className="cv-model-words wing-card-views" data-testid="repair-card-views">
          <SliceLegend report={report} />
          <p data-testid="repair-slice-caption">{sliceCaption(report, views)} The chart stands under it on the same scale.</p>
        </div>
      </Slot>
      <Slot name="answer">
        <section className="studio-panel wing-answer" data-testid="repair-answer">
          <p className="cv-eyebrow">Patch repair · the bondline</p>
          <h2 data-testid="repair-headline">{words.headline}</h2>
          <p data-testid="repair-detail">{words.detail}</p>
          <p className="studio-muted">{words.facts.join(" · ")}{stale ? " · updating for your last change" : ""}</p>
          {problem ? <p className="studio-alert" role="alert">{problem} The results shown are for the last repair that could be worked.</p> : null}
          {slice ? (
            <p className="cv-answer-note" data-testid="repair-slice-short">{solveStale ? "The slice was solved for the repair as it was. Solve it again for this one."
              : `Solved slice: ${sentence(solve?.headline ?? "")}`}</p>
          ) : (
            <p className="cv-answer-note" data-testid="repair-slice-short">{needs.length ? needsWords(needs) : "The slice is not solved yet: it adds the peel stress and each ply's stresses."}</p>
          )}
          {solveProblem ? <p className="studio-alert" role="alert">{solveProblem}</p> : null}
          <div className="cv-answer-actions">
            {!slice || solveStale ? (
              can ? <button type="button" className="studio-text-button" onClick={() => void solveSlice()} disabled={solving} data-testid="repair-solve-here">{solving ? "Solving the slice…" : slice ? "Solve the slice again" : "Solve the slice"}</button>
                : needs.length ? <button type="button" className="studio-text-button" onClick={() => showPanel("repair-solve")}>What it needs</button> : null
            ) : null}
            {slots ? <DetailsToggle open={slots.details} onToggle={slots.setDetails} /> : null}
          </div>
        </section>
      </Slot>
      <Slot name="details">
        {slice ? (
          <section className="studio-panel">
            <h3>The solved slice</h3>
            <SliceResults slice={slice} stale={solveStale} />
          </section>
        ) : null}
        {views.lap || slice ? (
          <section className="studio-panel">
            <h3>Force along the slice</h3>
            <ForceChart report={report} views={views} slice={solveStale ? null : slice} />
          </section>
        ) : null}
        <section className="studio-panel">
          <h3>The lap, by hand</h3>
          <LapTable report={report} />
        </section>
        <section className="studio-panel">
          <h3>The repair as measured</h3>
          <SizesTable report={report} />
        </section>
        <section className="studio-panel">
          <h3>What these numbers are not</h3>
          <Limits />
        </section>
      </Slot>
    </div>
  );
}
