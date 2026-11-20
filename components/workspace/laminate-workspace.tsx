"use client";

import { useRouter } from "next/navigation";
import { LaminateProvider, useLaminate } from "@/components/studio/laminate-context";
import { LaminateChat } from "@/components/studio/laminate-chat";
import { projectTitle } from "@/lib/project-store";
import { workspace } from "@/lib/workspaces";
import { LaminateRail } from "./laminate-rail";
import { LaminateStage } from "./laminate-stage";
import { WorkspaceShell } from "./shell";
import { goTo } from "./go-to";
import type { WorkTarget } from "@/lib/work-intent";

/** The Laminate section (ADR-0062, part 5; ADR-0124): the problem's panels on the left, the stack and the answer in the centre, the
 * laminate assistant of ADR-0060 on the right, all three on one laminate project. "Back to FEA" opens the newest FEA project; FEA or CAD
 * asked for in the chat opens it with the message, asking first when the problem holds work. */
export function LaminateWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return (
    <LaminateProvider apiBaseUrl={apiBaseUrl}>
      <LaminateColumns onBack={() => router.push(workspace("fea").href)}
        onSwitch={(target, carried) => goTo(target, target === "coupon" ? { setUp: carried, prompt: /\d|\[/.test(carried) ? carried : "" } : { prompt: carried }, router.push)} />
    </LaminateProvider>
  );
}

function LaminateColumns({ onBack, onSwitch }: { onBack: () => void; onSwitch: (target: WorkTarget, carried: string) => void }) {
  const { project, rename } = useLaminate();
  return (
    <WorkspaceShell
      kind={workspace("laminate").title}
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      rail={<LaminateRail />}
      stage={<LaminateStage />}
      assistant={<LaminateChat onBack={onBack} onSwitch={onSwitch} />}
    />
  );
}
