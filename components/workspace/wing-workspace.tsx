"use client";

import { workspace } from "@/lib/workspaces";
import { WorkspaceShell } from "./shell";
import { WingAssistant } from "./wing-assistant";
import { useWing, WingProvider } from "./wing-context";
import { WingRail } from "./wing-rail";
import { WingStage } from "./wing-stage";

/** The wing workspace (ADR-0118): the description's steps on the left, the answer and its drawings in the centre, the answer in words
 * on the right, all on one wing project (ADR-0120), kept with the person's other projects, and carried by a wing file. */
export function WingWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  return (
    <WingProvider apiBaseUrl={apiBaseUrl}>
      <WingColumns />
    </WingProvider>
  );
}

function WingColumns() {
  const { wing, setValue } = useWing();
  return (
    <WorkspaceShell
      kind={workspace("wing").title}
      title={<input type="text" aria-label="Wing name" value={typeof wing.title === "string" ? wing.title : ""} placeholder="Untitled wing" onChange={(e) => setValue("title", e.target.value)} data-testid="project-name" />}
      rail={<WingRail />}
      stage={<WingStage />}
      assistant={<WingAssistant />}
    />
  );
}
