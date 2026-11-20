"use client";

import { answerWords, CHECK_WORDS, marginText, whereWords, type WingCheckName, type WingReport } from "@/lib/wing";
import { WingChat } from "./wing-chat";
import { useWing } from "./wing-context";
import { showPanel } from "./panels/step-panel";

/** What raises each check's margin, in general words: no number, and not a design for this wing. */
const WHAT_RAISES: Record<WingCheckName, { why: string; raise: string[]; panel: string }> = {
  "skin plies": {
    why: "A skin ply reaches its strength first. Bending stretches one skin and squeezes the other, most where the box is deepest; the shear flow adds its share at the spar corners.",
    raise: ["More 0° plies in the skins for bending, more ±45° plies where shear governs", "A deeper box: the spars where the airfoil is thicker", "A stronger ply material"],
    panel: "wing-layup",
  },
  "spar plies": {
    why: "A spar web ply reaches its strength first. The webs carry most of the lift's shear, the taller front web the larger share.",
    raise: ["More ±45° plies in the webs", "A taller web: the spar where the airfoil is thicker"],
    panel: "wing-layup",
  },
  "skin buckling": {
    why: "A skin panel buckles under the spanwise compression before its plies fail.",
    raise: ["Ribs closer together: a shorter panel", "A thicker core in the skins", "Spars closer together: a narrower panel"],
    panel: "wing-geometry",
  },
  "web buckling": {
    why: "A spar web buckles in shear between two ribs before its plies fail: it is thin for the shear it carries.",
    raise: ["More ±45° plies in the webs", "Ribs closer together: a shorter bay", "A core in the webs"],
    panel: "wing-layup",
  },
};

function Governing({ report }: { report: WingReport }) {
  const g = report.governing;
  if (!g) return null;
  const check = report.cases.find((c) => c.number === g.case && c.altitude === g.altitude)?.checks[g.check];
  const advice = WHAT_RAISES[g.check];
  return (
    <div className="wing-explain" data-testid="wing-explain">
      <h3>{CHECK_WORDS[g.check]} governs</h3>
      <p><strong>{marginText(g.margin_ultimate)}</strong> at ultimate load, case {g.case} ({g.label}){check ? `: ${whereWords(check, report.units)}` : ""}.</p>
      <p>{advice.why}</p>
      <p className="studio-hint">What usually raises it:</p>
      <ul>{advice.raise.map((r) => <li key={r}>{r}</li>)}</ul>
      <button type="button" className="studio-text-button" onClick={() => showPanel(advice.panel)}>Open {advice.panel === "wing-layup" ? "Layup" : "Geometry"}</button>
    </div>
  );
}

/** The right column of the wing workspace (ADR-0118): the answer in words, what governs and why, what each waiting case needs, and the
 * wing's chat (ADR-0128). It words the engine's report and computes nothing; the chat changes the wing only when the engineer taps Apply. */
export function WingAssistant() {
  const { answer, problem } = useWing();
  return (
    <div className="studio-panel wing-assistant" data-testid="wing-assistant">
      <h3>Wing assistant</h3>
      {problem ? <p className="studio-alert" role="alert">{problem}</p> : null}
      {answer ? (
        <>
          <p className="wing-verdict"><strong>{answerWords(answer.report).verdict}.</strong></p>
          <Governing report={answer.report} />
          {answer.report.not_run.length ? (
            <p className="studio-hint">{answer.report.not_run.length} case{answer.report.not_run.length === 1 ? "" : "s"} wait for inputs: the list is under the results. <button type="button" className="studio-text-button" onClick={() => showPanel("wing-loads")}>Open Loads</button></p>
          ) : null}
          <p className="studio-hint">This is the hand calculation: the box between the spars as a thin-walled beam, worked in a fraction of a second on every change.</p>
        </>
      ) : <p className="studio-muted">The wing&apos;s answer appears here once it is worked.</p>}
      <WingChat />
    </div>
  );
}
