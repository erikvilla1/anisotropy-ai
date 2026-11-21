"use client";

import { feaKind, workspace } from "@/lib/workspaces";
import { CanvasShell } from "./canvas-shell";
import { RepairAssistant } from "./repair-assistant";
import { RepairProvider, useRepair } from "./repair-context";
import { RepairRail } from "./repair-rail";
import { RepairStage } from "./repair-stage";

/** The repair's page (ADR-0135): the repair file's tables as steps in the model tree, the slice and the bondline's stresses across the
 * model's area, the answer in the results card and in words on the right. One repair, kept in this browser and carried by a repair
 * file. A page of the FEA section, "FEA · Patch repair", in layout D (ADR-0134). */
export function RepairWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  return (
    <RepairProvider apiBaseUrl={apiBaseUrl}>
      <RepairColumns />
    </RepairProvider>
  );
}

function RepairColumns() {
  const { repair, setValue, answer } = useRepair();
  return (
    // worked on every change, as the wing is: its steps stay open beside the drawings on a wide screen
    <CanvasShell
      results={answer !== null}
      keepTree
      kind={`${workspace("fea").title} · ${feaKind("repair").title}`}
      title={<input type="text" aria-label="Repair name" value={typeof repair.title === "string" ? repair.title : ""} placeholder="Untitled repair" onChange={(e) => setValue("title", e.target.value)} data-testid="project-name" />}
      status={<RepairStatus />}
      tree={<RepairRail />}
      stage={<RepairStage />}
      assistant={<RepairAssistant />}
    />
  );
}

/** What the repair is at, under its name in the card. */
function RepairStatus() {
  const { answer, stale, working, solve, solveStale } = useRepair();
  const [state, words] = working && !answer ? ["working", "Working the repair…"]
    : stale ? ["stale", "Updating for your last change…"]
    : answer ? ["current", solve && !solveStale ? "Worked by hand and as a solved slice. Kept in this browser." : "Worked by hand on every change. Kept in this browser."]
    : ["waiting", "Describe the repair in the model tree."];
  return <p className="cv-status" data-testid="project-status" data-state={state} role="status">{words}</p>;
}
