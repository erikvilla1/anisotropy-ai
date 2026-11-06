"use client";

import { useRouter } from "next/navigation";
import { projectTitle } from "@/lib/project-store";
import { CouponChat, CouponSpec } from "@/components/studio/coupon-chat";
import { CouponStudio } from "@/components/studio/coupon-studio";
import { ProjectProvider, useProject } from "@/components/studio/project-context";
import { FeaRail } from "./fea-rail";
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
  const { project, form, rename } = useProject();
  const showForm = () => document.querySelector('[data-testid="ws-rail"]')?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <WorkspaceShell
      kind="Coupon FEA"
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      rail={<FeaRail apiBaseUrl={apiBaseUrl} />}
      stage={<><CouponSpec form={form} /><CouponStudio apiBaseUrl={apiBaseUrl} /></>}
      assistant={<CouponChat apiBaseUrl={apiBaseUrl} bench={false} onOpenForm={showForm} onLaminate={onLaminate} />}
    />
  );
}
