"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { analyzeRepair, StudioError } from "@/lib/studio-api";
import { answerWords, EXAMPLE_REPAIR, needsWords, repairFileName, sameRepair, sentence, statedGroups, type RepairAnswer, type RepairDescription } from "@/lib/repair";
import { REPAIR_HREF } from "@/lib/workspaces";
import { storedRepair, storedSolve, type KeptSolve } from "./repair-context";
import { LapTable, Limits, SizesTable, SliceResults } from "./repair-details";
import { BondChart, ForceChart, sliceCaption, SliceDrawing, SliceLegend } from "./repair-drawings";

/** The repair's report (ADR-0135): the repair this browser holds, laid out for paper. It reads the repair and the last solved slice
 * the page kept, asks for the hand calculation again, and prints what the page shows: what the repair is, its slice, the
 * hand calculation, the solved slice when it belongs to this repair, and what the analysis is not. The browser's own print saves it
 * as a PDF. Every number is the engine's or the solver's. */
export function RepairReport({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [repair, setRepair] = useState<RepairDescription | null>(null);
  const [kept, setKept] = useState<KeptSolve | null>(null);
  const [answer, setAnswer] = useState<RepairAnswer | null>(null);
  const [problem, setProblem] = useState("");
  const [printed, setPrinted] = useState("");

  useEffect(() => {
    const found = storedRepair() ?? EXAMPLE_REPAIR;
    setRepair(found);
    setKept(storedSolve());
    setPrinted(new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }));
    if (!apiBaseUrl) { setProblem("The analysis service is not set up on this page."); return; }
    const controller = new AbortController();
    analyzeRepair(apiBaseUrl, { repair: found }, controller.signal).then(setAnswer).catch((error) => {
      if (controller.signal.aborted) return;
      setProblem(error instanceof StudioError ? error.message : "The repair could not be worked. Try again.");
    });
    return () => controller.abort("left");
  }, [apiBaseUrl]);

  const title = repair && typeof repair.title === "string" && repair.title.trim() ? repair.title.trim() : "Untitled repair";
  useEffect(() => { // the browser offers the page's title as the PDF's file name: the repair's own name while it prints
    if (!repair) return;
    let before = "";
    const naming = () => { before = document.title; document.title = repairFileName(repair, "pdf").replace(/\.pdf$/, "-report"); };
    const restoring = () => { if (before) document.title = before; before = ""; };
    window.addEventListener("beforeprint", naming);
    window.addEventListener("afterprint", restoring);
    return () => { window.removeEventListener("beforeprint", naming); window.removeEventListener("afterprint", restoring); };
  }, [repair]);

  // the solve belongs to this report only when it was made of the repair this browser holds now, value for value
  const solve = answer && kept && sameRepair(kept.repair, repair) ? kept.solve : null;
  const staleSolve = answer !== null && kept !== null && !solve;
  const words = answer ? answerWords(answer.report) : null;
  let section = 0;
  const next = () => { section += 1; return section; };

  return (
    <div className="repair-report-page" data-testid="repair-report-page">
      <div className="repair-report-bar">
        <Link className="studio-button" href={REPAIR_HREF} data-testid="repair-report-back">Back to the repair</Link>
        <button type="button" className="studio-button studio-button-primary" onClick={() => window.print()} disabled={!answer} data-testid="repair-report-print">Print or save as PDF</button>
        <span className="studio-hint">In the print window, choose “Save as PDF” as the printer.</span>
      </div>
      <article className="repair-report" data-testid="repair-report" data-state={answer ? "ready" : problem ? "problem" : "working"}>
        <header className="repair-report-head">
          <p className="repair-report-eyebrow">Patch repair report</p>
          <h1 data-testid="repair-report-title">{title}</h1>
          <p className="repair-report-meta">{printed ? `Printed ${printed}` : ""}{answer ? ` · Anisotropy ${answer.engine_version}` : ""}</p>
        </header>
        {problem ? <p className="studio-alert" role="alert" data-testid="repair-report-problem">{problem}</p> : null}
        {!answer && !problem ? <p role="status">Working the repair…</p> : null}
        {answer && words && repair ? (
          <>
            <section className="repair-report-summary" data-testid="repair-report-summary">
              <h2>Summary</h2>
              <p><strong>{words.headline}.</strong> {words.detail}</p>
              {solve ? <p data-testid="repair-report-solve-line">Solved slice: {sentence(solve.headline)}</p>
                : <p data-testid="repair-report-solve-line">{staleSolve ? "The slice was solved for an earlier state of this repair, so its results are left out of this report."
                  : answer.needs.length ? `The slice was not solved. ${needsWords(answer.needs)}` : "The slice was not solved for this report; the bondline is worked by hand only."}</p>}
              <p className="repair-report-facts">{words.facts.join(" · ")}</p>
            </section>

            <section>
              <h2>{next()}. The repair as stated</h2>
              {typeof repair.source === "string" && repair.source.trim() ? <p className="repair-report-note">{repair.source}</p> : null}
              <div className="repair-report-stated" data-testid="repair-report-stated">
                {statedGroups(repair).map((group) => (
                  <table className="studio-table" key={group.title}>
                    <thead><tr><th colSpan={2}>{group.title}</th></tr></thead>
                    <tbody>{group.rows.map(([name, value]) => <tr key={name}><th scope="row">{name}</th><td>{value}</td></tr>)}</tbody>
                  </table>
                ))}
              </div>
            </section>

            <section>
              <h2>{next()}. The repair as measured</h2>
              <figure className="repair-report-figure">
                <SliceDrawing report={answer.report} views={answer.views} />
                <SliceLegend report={answer.report} />
                <figcaption>{sliceCaption(answer.report, answer.views)}</figcaption>
              </figure>
              <SizesTable report={answer.report} />
            </section>

            <section>
              <h2>{next()}. The bondline by hand</h2>
              <p>The lap is worked one step at a time. Over each step the patch and the laminate under it are two bars that stretch along the load, joined by an adhesive that carries shear only. The force passes from one bar to the other through the adhesive, most of it near the ends of each step. The steps are joined by the force the patch carries where one ends and the next begins.</p>
              {answer.views.lap ? (
                <figure className="repair-report-figure">
                  <BondChart report={answer.report} views={answer.views} slice={solve?.report ?? null} />
                  <figcaption>The adhesive&apos;s stresses along the bond, on the scale of the slice above. The upright lines are the ends of the lap&apos;s steps.</figcaption>
                </figure>
              ) : <p>No load is stated, so the lap is described and not worked.</p>}
              <LapTable report={answer.report} />
            </section>

            {solve ? (
              <section data-testid="repair-report-slice">
                <h2>{next()}. The solved slice</h2>
                <p>The half slice drawn above is meshed, every ply and the adhesive as it is, and solved as a plane held flat across the load. It adds what the hand calculation leaves out: the stress that peels the patch off, and each ply&apos;s own stresses.</p>
                <SliceResults slice={solve.report} stale={false} />
                <figure className="repair-report-figure">
                  <ForceChart report={answer.report} views={answer.views} slice={solve.report} />
                  <figcaption>The force per unit width in the patch and in the laminate along the slice.</figcaption>
                </figure>
              </section>
            ) : null}

            <section className="repair-report-last">
              <h2>{next()}. What these numbers are not</h2>
              <Limits />
              <p className="repair-report-foot">Every number in this report was computed from the repair as stated in section 1{solve ? ", by hand calculation or by the solved slice" : ", by hand calculation"}. None was typed or estimated.</p>
            </section>
          </>
        ) : null}
      </article>
    </div>
  );
}
