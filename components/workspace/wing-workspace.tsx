"use client";

import { feaKind, workspace } from "@/lib/workspaces";
import { CanvasShell } from "./canvas-shell";
import { WingAssistant } from "./wing-assistant";
import { useWing, WingProvider } from "./wing-context";
import { WingRail } from "./wing-rail";
import { WingStage } from "./wing-stage";

/** The wing workspace (ADR-0118): the description's steps in the model tree, the answer's drawings across the model's area, the answer in
 * the results card and in words on the right, all on one wing project (ADR-0122), kept with the person's other projects, and carried by a
 * wing file. A page of the FEA section, "FEA · Wing analysis" (ADR-0118 amendment 1), in layout D (ADR-0134). */
export function WingWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  return (
    <WingProvider apiBaseUrl={apiBaseUrl}>
      <WingColumns />
    </WingProvider>
  );
}

function WingColumns() {
  const { wing, setValue, answer } = useWing();
  return (
    // the wing is worked on every change, so its steps stay open beside the drawings on a wide screen; on a phone its first answer
    // turns the sheet under the drawings to the card, as a coupon's first results do
    <CanvasShell
      results={answer !== null}
      keepTree
      kind={`${workspace("fea").title} · ${feaKind("wing").title}`}
      title={<input type="text" aria-label="Wing name" value={typeof wing.title === "string" ? wing.title : ""} placeholder="Untitled wing" onChange={(e) => setValue("title", e.target.value)} data-testid="project-name" />}
      status={<WingStatus />}
      tree={<WingRail />}
      stage={<WingStage />}
      assistant={<WingAssistant />}
    />
  );
}

/** What the wing is at, under its name in the card. */
function WingStatus() {
  const { answer, stale, working } = useWing();
  const [state, words] = working && !answer ? ["working", "Working the wing…"]
    : stale ? ["stale", "Updating for your last change…"]
    : answer ? ["current", "Worked again on every change: change it in the model tree or in the chat."]
    : ["waiting", "Describe the wing in the model tree or in the chat."];
  return <p className="cv-status" data-testid="project-status" data-state={state} role="status">{words}</p>;
}
