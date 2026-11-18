"use client";

import { useRouter } from "next/navigation";
import { projectTitle } from "@/lib/project-store";
import { CouponChat, CouponSpec } from "@/components/studio/coupon-chat";
import { CouponStudio } from "@/components/studio/coupon-studio";
import { ImportedStage } from "@/components/studio/imported-stage";
import { PastStage } from "@/components/studio/past-stage";
import { ProjectProvider, useProject } from "@/components/studio/project-context";
import { TowStage } from "@/components/studio/tow-stage";
import { isTow } from "@/lib/studio-tow";
import { workspace } from "@/lib/workspaces";
import { FeaRail } from "./fea-rail";
import { ImportRail } from "./import-rail";
import { PastRail } from "./past-rail";
import { TensionScreen } from "./tension-screen";
import { WorkspaceShell } from "./shell";

/** The coupon FEA workspace (ADR-0062): one panel per step on the left, the sketch, the model and the results in the centre, the coupon
 * assistant on the right, all three on the one project store. A model brought in as a file takes the left and the centre while it is
 * open, and the assistant answers from it (ADR-0105); so does a past analysis opened again (ADR-0109). */
export function FeaWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return (
    <ProjectProvider apiBaseUrl={apiBaseUrl}>
      <FeaColumns apiBaseUrl={apiBaseUrl} onLaminate={() => router.push("/workspace/laminate")} />
    </ProjectProvider>
  );
}

function FeaColumns({ apiBaseUrl, onLaminate }: { apiBaseUrl: string; onLaminate: () => void }) {
  const { project, form, rename, allTests, imported, past } = useProject();
  // the tension screen (ADR-0090) leaves the test, the size and the pull to the software: the strip shows what it chose once checked
  return (
    <WorkspaceShell
      kind={workspace("fea").title}
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      // a model brought in as a file has the left and the centre while it is open (ADR-0105); the coupon's rows wait behind it
      // a past analysis opened again has them too, shown as it was solved (ADR-0109); the project's rows wait behind it
      rail={imported.open ? <ImportRail apiBaseUrl={apiBaseUrl} /> : past.open ? <PastRail apiBaseUrl={apiBaseUrl} />
        : allTests ? <FeaRail apiBaseUrl={apiBaseUrl} /> : <TensionScreen apiBaseUrl={apiBaseUrl} />}
      stage={imported.open ? <ImportedStage apiBaseUrl={apiBaseUrl} /> : past.open ? <PastStage apiBaseUrl={apiBaseUrl} />
        // the model tree says the setup tab by tab (ADR-0111), so its view gives the model the room the summary strip took
        : isTow(form) && allTests ? <TowStage /> : allTests ? <><CouponSpec form={form} /><CouponStudio apiBaseUrl={apiBaseUrl} /></>
        : <CouponStudio apiBaseUrl={apiBaseUrl} />}
      assistant={<CouponChat apiBaseUrl={apiBaseUrl} onLaminate={onLaminate} />}
    />
  );
}
