"use client";

import { useRouter } from "next/navigation";
import { projectTitle } from "@/lib/project-store";
import { CouponChat, CouponSpec } from "@/components/studio/coupon-chat";
import { CouponStudio } from "@/components/studio/coupon-studio";
import { ProjectProvider, useProject } from "@/components/studio/project-context";
import { TowStage } from "@/components/studio/tow-stage";
import { isTow } from "@/lib/studio-tow";
import { FeaRail } from "./fea-rail";
import { TensionScreen } from "./tension-screen";
import { WorkspaceShell } from "./shell";

/** The coupon FEA workspace (ADR-0062): one panel per step on the left, the sketch, the model and the results in the centre, the coupon
 * assistant on the right, all three on the one project store. */
export function FeaWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return (
    <ProjectProvider apiBaseUrl={apiBaseUrl}>
      <FeaColumns apiBaseUrl={apiBaseUrl} onLaminate={() => router.push("/workspace/laminate")} />
    </ProjectProvider>
  );
}

function FeaColumns({ apiBaseUrl, onLaminate }: { apiBaseUrl: string; onLaminate: () => void }) {
  const { project, form, rename, allTests } = useProject();
  return (
    <WorkspaceShell
      kind="Coupon FEA"
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      rail={allTests ? <FeaRail apiBaseUrl={apiBaseUrl} /> : <TensionScreen apiBaseUrl={apiBaseUrl} />}
      stage={isTow(form) && allTests ? <TowStage /> : <><CouponSpec form={form} /><CouponStudio apiBaseUrl={apiBaseUrl} /></>}
      assistant={<CouponChat apiBaseUrl={apiBaseUrl} onLaminate={onLaminate} />}
    />
  );
}
