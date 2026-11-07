"use client";

import { useRouter } from "next/navigation";
import { LaminateProvider, useLaminate } from "@/components/studio/laminate-context";
import { LaminateChat } from "@/components/studio/laminate-chat";
import { projectTitle } from "@/lib/project-store";
import { LaminateRail } from "./laminate-rail";
import { LaminateStage } from "./laminate-stage";
import { WorkspaceShell } from "./shell";

/** The laminate response workspace (ADR-0062, part 5): the problem's panels on the left, the stack and the answer in the centre, the
 * laminate assistant of ADR-0060 on the right, all three on one laminate project. "Back to the coupon tests" opens the coupon FEA workspace. */
export function LaminateWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return (
    <LaminateProvider apiBaseUrl={apiBaseUrl}>
      <LaminateColumns onBack={() => router.push("/workspace/fea")} />
    </LaminateProvider>
  );
}

function LaminateColumns({ onBack }: { onBack: () => void }) {
  const { project, rename } = useLaminate();
  return (
    <WorkspaceShell
      kind="Laminate response"
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      rail={<LaminateRail />}
      stage={<LaminateStage />}
      assistant={<LaminateChat onBack={onBack} />}
    />
  );
}
